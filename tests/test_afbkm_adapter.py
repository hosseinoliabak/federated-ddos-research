"""Scientific and message-boundary regressions, using fabricated records only."""
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from unittest.mock import patch
import copy
import json
import io
from contextlib import redirect_stdout
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import afbkm_adapter as A
import afbkm_wire as W
import check_afbkm_adapter as C


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.scope = C.fake_scope()
        self.anchor_batch = C.fake_batch(self.scope, 0, [[0.0], [2.0]])
        self.parameters = A.Parameters(0.5, 3, 0.5, 3)
        self.state, self.anchor = A.initialize_anchor(self.anchor_batch, self.parameters,
                                                      "fixture", trusted_benign=True)

    def batch(self, owner=1, values=((1.0,), (1.0,)), offset=0):
        return C.fake_batch(self.scope, owner, values, offset=offset)

    def summary(self, owner=1, values=((1.0,), (1.0,))):
        return A.summarize(self.batch(owner, values), self.state)

    def merge(self, summaries, state=None, anchor=None):
        return A.merge(state or self.state, anchor or self.anchor, summaries, [s.permit for s in summaries])

    def assertFailure(self, code, function, *args, **kwargs):
        with self.assertRaises(A.AdapterError) as caught:
            function(*args, **kwargs)
        self.assertEqual(caught.exception.code, code)

    def test_published_equations_5_to_8_hand_computable(self):
        # Scaled anchor [0,1]; sample cov=.5; ridge=.5 gives inverse=1.
        np.testing.assert_array_equal(self.state.scaler_min.array(), [0.0])
        np.testing.assert_array_equal(self.state.scaler_denominator.array(), [2.0])
        np.testing.assert_array_equal(self.state.inverse_covariance.array(), [[1.0]])
        self.assertEqual(self.state.internal_threshold, 0.5)
        u1 = self.summary(1)
        u2 = self.summary(2, [[0.0]] * 4)
        current, audit = self.merge([u1, u2])
        self.assertEqual([w["weight"] for w in audit["normalized_weights"]], [1 / 3, 2 / 3])
        self.assertAlmostEqual(current.mean.array()[0], 1 / 3)
        self.assertAlmostEqual(current.internal_threshold, 0.5 + 3 * 1.4826 / 6)
        self.assertEqual(current.fixed_id, self.state.fixed_id)
        self.assertEqual(current.inverse_covariance, self.state.inverse_covariance)

    def test_quality_weight_uses_unscaled_distance_mad(self):
        u1 = self.summary(1)
        u2 = self.summary(2, [[0.0], [0.2], [0.4]])
        self.assertAlmostEqual(u2.dispersion, 0.1)
        current, audit = self.merge([u1, u2])
        # Raw quality weights 2 and 3/1.1; weighted mean 7/26.
        self.assertAlmostEqual(audit["normalized_weights"][0]["weight"], 11 / 26)
        self.assertAlmostEqual(current.mean.array()[0], 5 / 13)
        self.assertAlmostEqual(current.internal_threshold, 0.5 + 3 * 1.4826 * 3 / 26)

    def test_blend_is_fixed_original_anchor_not_previous_global_mean(self):
        first, _ = self.merge([self.summary(1, [[0.0], [0.0]])])
        self.assertEqual(first.mean.array()[0], 0.25)
        second_batch = self.batch(1, [[0.0], [0.0]], offset=2)
        second, _ = self.merge([A.summarize(second_batch, first)], state=first)
        self.assertEqual(second.mean.array()[0], 0.25)

    def test_exact_threshold_boundary_is_accepted(self):
        summary = self.summary(1, [[0.0], [2.0], [2.0001]])
        self.assertEqual((summary.accepted, summary.rejected), (2, 1))
        self.assertEqual(summary.mean.array()[0], 0.5)

    def test_all_empty_accepted_sets_leave_parameters_unchanged_advance_round(self):
        empty = self.summary(1, [])
        rejected = self.summary(2, [[20.0], [21.0]])
        state, audit = self.merge([empty, rejected])
        self.assertEqual(state.mean, self.state.mean)
        self.assertEqual(state.internal_threshold, self.state.internal_threshold)
        self.assertEqual(state.round_id, self.state.round_id + 1)
        self.assertEqual([w["status"] for w in audit["workers"]], ["empty_batch", "no_accepted_rows"])
        self.assertEqual(audit["anchor_rows_rescored"], 0)
        self.assertFalse(audit["internal_threshold_updated"])

    def test_no_workers_no_parameter_update(self):
        state, audit = self.merge([])
        self.assertEqual(state.mean, self.state.mean)
        self.assertEqual(state.round_id, 1)
        self.assertEqual(audit["workers"], [])

    def test_singleton_has_finite_zero_dispersion_and_no_candidate(self):
        summary = self.summary(1, [[0.0]])
        self.assertEqual(summary.dispersion, 0.0)
        self.assertIsNone(summary.threshold_candidate)
        state, audit = self.merge([summary])
        self.assertEqual(state.mean.array()[0], 0.25)
        self.assertEqual(audit["gate"], "abstain_fewer_than_three_candidates")

    def test_tied_candidates_zero_mad_reject_outlier_exactly(self):
        summaries = [self.summary(1), self.summary(2), self.summary(3, [[0.0], [0.0]])]
        state, audit = self.merge(summaries)
        self.assertEqual(audit["candidate_scaled_mad"], 0.0)
        self.assertEqual(audit["gate"], "active_exact_mad")
        self.assertEqual(audit["workers"][2]["merge_status"], "trust_gate_rejected")
        self.assertEqual(state.mean, self.state.mean)
        # No upstream +1e-12 tolerance: any different finite candidate is outside.
        summaries[2] = replace(summaries[2], threshold_candidate=1e-13)
        _, audit2 = self.merge(summaries)
        self.assertEqual(audit2["workers"][2]["merge_status"], "trust_gate_rejected")

    def test_nonzero_mad_gate_rejects_large_candidate(self):
        scope = replace(self.scope, sources=self.scope.sources + ((4, A.digest("four")),))
        # Same scope is needed at initialization; candidate values are deliberate reports.
        anchor = C.fake_batch(scope, 0, [[0.0], [2.0]])
        state, context = A.initialize_anchor(anchor, self.parameters, "four-workers", trusted_benign=True)
        summaries = [A.summarize(C.fake_batch(scope, i, [[1.0], [1.0]]), state) for i in (1, 2, 3, 4)]
        summaries = [replace(u, threshold_candidate=v) for u, v in zip(summaries, (0.0, 0.1, 0.2, 20.0))]
        _, audit = self.merge(summaries, state, context)
        self.assertAlmostEqual(audit["candidate_median"], 0.15)
        self.assertAlmostEqual(audit["candidate_scaled_mad"], 0.14826)
        self.assertEqual(audit["workers"][3]["merge_status"], "trust_gate_rejected")

    def test_active_gate_excludes_null_singleton_candidate(self):
        scope = replace(self.scope, sources=self.scope.sources + ((4, A.digest("four")),))
        state, context = A.initialize_anchor(C.fake_batch(scope, 0, [[0.0], [2.0]]), self.parameters,
                                             "singleton-gate", trusted_benign=True)
        summaries = [A.summarize(C.fake_batch(scope, i, [[1.0]] * (1 if i == 4 else 2)), state) for i in (1, 2, 3, 4)]
        _, audit = self.merge(summaries, state, context)
        self.assertEqual(audit["workers"][3]["merge_status"], "trust_gate_rejected")

    def test_empty_gate_fallback_matches_algorithm_1(self):
        scope = replace(self.scope, sources=self.scope.sources + ((4, A.digest("four")),))
        state, context = A.initialize_anchor(C.fake_batch(scope, 0, [[0.0], [2.0]]),
                                             replace(self.parameters, trust_k=0), "fallback", trusted_benign=True)
        summaries = [replace(A.summarize(C.fake_batch(scope, i, [[1.0]] * 2), state), threshold_candidate=float(i - 1))
                     for i in (1, 2, 3, 4)]
        _, audit = self.merge(summaries, state, context)
        self.assertEqual(audit["gate"], "abstain_empty_gate_fallback")
        self.assertTrue(all(w["merge_status"] == "kept" for w in audit["workers"]))

    def test_constant_collinear_anchor_and_fixed_covariance(self):
        scope = C.fake_scope(3)
        batch = C.fake_batch(scope, 0, [[2, 4, 7], [3, 6, 7], [4, 8, 7]])
        state, context = A.initialize_anchor(batch, A.Parameters(1e-5, 3, 0.5, 3), "collinear", trusted_benign=True)
        np.testing.assert_array_equal(state.scaler_denominator.array(), [2, 4, 1])
        self.assertTrue(np.isfinite(A.score([[3, 6, 7], [9, 18, 8]], state)).all())
        worker = C.fake_batch(scope, 1, [[3, 6, 7]] * 2)
        updated, _ = A.merge(state, context, [A.summarize(worker, state)], [A.authorize(worker, state)])
        self.assertEqual(updated.inverse_covariance.data, state.inverse_covariance.data)
        self.assertEqual(updated.fixed_id, state.fixed_id)

    def test_scaler_is_anchor_only_and_does_not_clip_future_values(self):
        np.testing.assert_array_equal(A.transform([[4.0]], self.state), [[2.0]])
        self.assertEqual(self.state.scaler_denominator.array()[0], 2)

    def test_invalid_anchor_approval_and_small_anchor(self):
        self.assertFailure("unapproved_anchor", A.initialize_anchor, self.anchor_batch, self.parameters, "x", trusted_benign=False)
        self.assertFailure("anchor_requires_two_rows", A.initialize_anchor, self.batch(values=[[1.0]]), self.parameters, "x", trusted_benign=True)

    def test_arrays_and_global_state_are_immutable(self):
        self.assertRaises(FrozenInstanceError, setattr, self.state, "round_id", 7)
        arr = self.state.mean.array()
        self.assertRaises(ValueError, arr.__setitem__, 0, 100.0)
        self.assertRaises(ValueError, arr.setflags, write=True)
        raw = np.array([[0.0], [2.0]])
        copied = C.fake_batch(self.scope, 1, raw); raw[0, 0] = 999
        self.assertEqual(copied.values.array()[0, 0], 0)

    def test_invalid_parameters_and_metadata_types(self):
        for args in ((0, 3, .5, 3), (-1, 3, .5, 3), (.1, -1, .5, 3), (.1, 3, 1.1, 3), (.1, 3, .5, float("nan")), (True, 3, .5, 3)):
            self.assertRaises(A.AdapterError, A.Parameters, *args)
        self.assertRaises(A.AdapterError, replace, self.scope, train_role_id=1)
        self.assertRaises(A.AdapterError, A.RowRef, 0, -1, 1, 0, "a" * 64)

    def test_nonfinite_or_non_numeric_input_cannot_be_benign(self):
        for values in ([[float("nan")]], [[float("inf")]], [[-float("inf")]], [["1"]], [[True]], [[1 + 2j]]):
            self.assertRaises(A.AdapterError, A.score, values, self.state)
        self.assertFailure("nonfinite_quadratic_form", A.score, [[1e308]], self.state)
        self.assertFailure("shape_mismatch", A.score, [[1.0, 2.0]], self.state)
        self.assertFailure("negative_distance", A.mad_rule, [-1.0, 1.0], 3)
        self.assertFailure("empty_threshold_input", A.mad_rule, [], 3)

    def test_invalid_state_and_quadratic_form_fail_explicitly(self):
        self.assertRaises(A.AdapterError, replace, self.state, internal_threshold=float("nan"))
        self.assertFailure("non_positive_definite_covariance", replace, self.state,
                           inverse_covariance=A.FrozenArray.of([[-1.0]]))
        # Simulate a negative/invalid intermediate despite a valid inverse.
        with patch.object(A.np, "einsum", return_value=np.array([-1e-16])):
            self.assertFailure("negative_quadratic_form", A.score, [[0.0]], self.state)
        with patch.object(A.np, "einsum", return_value=np.array([float("inf")])):
            self.assertFailure("nonfinite_quadratic_form", A.score, [[0.0]], self.state)
        corrupt = copy.copy(self.state)
        object.__setattr__(corrupt, "internal_threshold", float("inf"))
        self.assertFailure("nonfinite_scalar", A.summarize, self.batch(), corrupt)

    def test_model_round_scope_and_anchor_identity_enforced(self):
        summary = self.summary()
        self.assertFailure("model_round_state_mismatch", self.merge, [summary], replace(self.state, round_id=1))
        self.assertFailure("model_round_state_mismatch", self.merge, [summary], replace(self.state, model_id="different"))
        different_scope = replace(self.scope, candidate_sha256=A.digest("other"))
        self.assertFailure("scope_mismatch", A.authorize, C.fake_batch(different_scope, 1, [[1.0]]), self.state)
        self.assertFailure("anchor_mismatch", self.merge, [summary], None,
                           replace(self.anchor, scaled=A.FrozenArray.of([[0.0], [0.1]])))

    def test_duplicate_missing_and_unauthorized_summaries_fail(self):
        summary = self.summary()
        self.assertFailure("duplicate_worker_update", A.merge, self.state, self.anchor, [summary, summary], [summary.permit])
        self.assertFailure("missing_worker_update", A.merge, self.state, self.anchor, [], [summary.permit])
        self.assertFailure("unauthorized_summary", A.merge, self.state, self.anchor, [summary], [])
        self.assertFailure("duplicate_worker_permit", A.merge, self.state, self.anchor, [summary], [summary.permit, summary.permit])
        changed = replace(summary, permit=replace(summary.permit, batch_id=A.digest("unapproved")))
        self.assertFailure("unauthorized_summary", A.merge, self.state, self.anchor, [changed], [summary.permit])

    def test_invalid_summary_statistics_and_counts_fail(self):
        summary = self.summary()
        for change in ({"dispersion": float("nan")}, {"threshold_candidate": float("inf")},
                       {"dispersion": -1.0}, {"accepted": 3}, {"status": "quietly_repaired"}):
            self.assertRaises(A.AdapterError, self.merge, [replace(summary, **change)])
        empty = self.summary(values=[])
        self.assertFailure("empty_summary_has_statistics", self.merge,
                           [replace(empty, mean=A.FrozenArray.of([0.0]))])

    def records(self, role=0):
        return [{"source_id": 1, "source_row": i, "observer_id": 1, "role_id": role,
                 "group_sha256": A.digest([1, i]), "binary_label": i % 2, "original_label_id": i % 5}
                for i in range(2)]

    def test_worker_label_values_and_access_cannot_affect_summary(self):
        class LabelTrap(dict):
            def __getitem__(self, key):
                if "label" in key: raise AssertionError("worker read a label")
                return super().__getitem__(key)
        records = self.records(); X = np.array([[0.0], [2.0]])
        first = A.summarize(A.training_batch(X, records, [0, 1], self.scope, 1), self.state)
        for r in records: r.update(binary_label=999, original_label_id=-999, label="arbitrary")
        second = A.summarize(A.training_batch(X, [LabelTrap(r) for r in records], [0, 1], self.scope, 1), self.state)
        self.assertEqual(W.encode_summary(first, 1), W.encode_summary(second, 1))

    def test_non_training_roles_fail_before_feature_read(self):
        class FeatureTrap:
            def __len__(self): return 2
            def __getitem__(self, key): raise AssertionError("read forbidden predictors")
        for role in (1, 2, 3, 255):
            self.assertFailure("non_training_update", A.training_batch, FeatureTrap(), self.records(role), [0, 1], self.scope, 1)
        self.assertFailure("ownership_mismatch", A.training_batch, FeatureTrap(), self.records(), [0], self.scope, 2)
        records = self.records(); records[0]["source_id"] = 100
        self.assertFailure("unapproved_source", A.training_batch, FeatureTrap(), records, [0], self.scope, 1)

    def test_metadata_not_coerced_and_duplicate_rows_not_hidden(self):
        X = np.array([[0.0], [2.0]])
        records = self.records(); records[0]["source_row"] = 0.5
        self.assertFailure("invalid_metadata_integer", A.training_batch, X, records, [0], self.scope, 1)
        self.assertFailure("duplicate_source_row", A.training_batch, X, self.records(), [0, 0], self.scope, 1)
        self.assertFailure("row_index_out_of_range", A.training_batch, X, self.records(), [2], self.scope, 1)

    def test_unequal_workers_all_tail_rows_and_empty_batches(self):
        result = C.synthetic_check()
        self.assertEqual(result["rows_by_native_worker"], {"1": 7, "2": 3, "3": 10})
        self.assertEqual(result["total_worker_rows"], 20)
        self.assertEqual(len(result["rounds"]), 3)
        self.assertEqual(result["rounds"][2]["workers"][0]["rows_seen"], 2)
        self.assertEqual(result["rounds"][1]["workers"][1]["status"], "empty_batch")
        self.assertFalse(result["real_dataset_read"])

    def test_schedule_rejects_ownership_swap_row_reuse_and_anchor_reuse(self):
        self.assertFailure("ownership_mismatch", C.run_schedule, self.state, self.anchor, {2: [self.batch()]})
        self.assertFailure("reused_training_row", C.run_schedule, self.state, self.anchor, {1: [self.batch(), self.batch()]})
        self.assertFailure("reused_training_row", C.run_schedule, self.state, self.anchor, {0: [self.anchor_batch]})

    def test_reviewed_loader_schema_bridge_on_fabricated_sources_only(self):
        # Reuse the loader's 14 fabricated sources. Nothing reads actual datasets.
        from test_grouped_loader import LoaderTests
        import load_grouped_candidate as L
        fixture = LoaderTests(); fixture.setUp()
        try:
            fixture.run_loader("adapter-bridge")
            schema, X, records = L.open_arrays(fixture.root / "reports/development-preparation/adapter-bridge")
            scope = A.TrainingScope(L.sha(fixture.mp), fixture.manifest["assignment_sha256"],
                                    tuple(schema["features"]), tuple((i, source["sha256"]) for i, source in
                                    enumerate(sorted(fixture.manifest["sources"], key=lambda v: v["path"]))))
            train = [i for i, row in enumerate(records) if row["role_id"] == 0]
            # Benign anchor approval happens outside the detector, on TRAIN only.
            anchor_rows = [i for i in train if records[i]["observer_id"] == 1
                           and records[i]["binary_label"] == 0][:2]
            self.assertEqual(len(anchor_rows), 2)
            anchor_batch = A.training_batch(X, records, anchor_rows, scope, 1)
            state, context = A.initialize_anchor(anchor_batch, A.Parameters(1.0, 3, .5, 3),
                                                 "sealed-synthetic-bridge", trusted_benign=True)
            workers = {}; expected = {}
            for owner in range(1, 11):
                rows = [i for i in train if records[i]["observer_id"] == owner and i not in anchor_rows]
                workers[owner] = [A.training_batch(X, records, rows[j:j + 3], scope, owner)
                                  for j in range(0, len(rows), 3)]
                expected[str(owner)] = len(rows)
            result = C.run_schedule(state, context, workers)
            self.assertEqual(result["rows_by_native_worker"], expected)
            self.assertEqual(result["total_worker_rows"], len(train) - 2)
            self.assertEqual(state.features, tuple(schema["features"]))
        finally:
            fixture.doCleanups()

    def test_merge_worker_order_invariant(self):
        summaries = [self.summary(1), self.summary(2, [[0.0]] * 4)]
        left, la = self.merge(summaries); right, ra = self.merge(list(reversed(summaries)))
        self.assertEqual(left.state_id, right.state_id); self.assertEqual(la, ra)

    def test_initial_round_and_summary_exact_serialization_reconstruction(self):
        initial = W.encode_initial(self.state); restored = W.decode_initial(initial)
        self.assertEqual(W.encode_initial(restored), initial)
        summaries = [self.summary(), self.summary(2, []), self.summary(3, [[0.0]])]
        for summary in summaries:
            data = W.encode_summary(summary, 1)
            self.assertEqual(W.encode_summary(W.decode_summary(data, 1), 1), data)
            self.assertNotIn(b"label", data); self.assertNotIn(b"inverse_covariance", data)
            self.assertNotIn(b"distances", data); self.assertNotIn(b"features", data)
        current, _ = self.merge(summaries)
        data = W.encode_delta(self.state, current)
        self.assertEqual(W.apply_delta(restored, data).state_id, current.state_id)
        self.assertNotIn(b"inverse_covariance", data); self.assertNotIn(b"scaler_", data)
        self.assertNotIn(b"anchor_mean", data)
        decode_initial, decode_summary, apply_delta = W.decode_initial, W.decode_summary, W.apply_delta
        fake_batch = C.fake_batch
        for adjacent_negative in (False, True):
            with self.subTest(adjacent_negative=adjacent_negative):
                initial_frames, summary_frames, delta_frames = [], [], []

                def receive_initial(payload):
                    initial_frames.append(payload)
                    return decode_initial(payload)

                def receive_summary(payload, dimension):
                    restored = decode_summary(payload, dimension)
                    summary_frames.append((restored.permit.worker_id, payload))
                    return restored

                def receive_delta(previous, payload):
                    delta_frames.append(payload)
                    return apply_delta(previous, payload)

                def fixture_batch(scope, owner, values, **kwargs):
                    X = np.asarray(values, dtype=float)
                    if adjacent_negative:
                        # A finite one-ULP variant can change a JSON number's byte length.
                        X = np.where(X == -0.2, np.nextafter(-0.2, -np.inf), X)
                    return fake_batch(scope, owner, X, **kwargs)

                with patch.object(W, "decode_initial", side_effect=receive_initial), \
                     patch.object(W, "decode_summary", side_effect=receive_summary), \
                     patch.object(W, "apply_delta", side_effect=receive_delta), \
                     patch.object(C, "fake_batch", side_effect=fixture_batch):
                    result = C.synthetic_check()

                # Count the exact frames received, including each replica's fanout.
                self.assertEqual(len(initial_frames), 3)
                self.assertEqual(len(set(initial_frames)), 1)
                initial = result["initial_distribution"]
                self.assertEqual(initial["recipients"], len(initial_frames))
                self.assertEqual(initial["bytes_per_worker"], len(initial_frames[0]))
                self.assertEqual(initial["total_application_bytes"], sum(map(len, initial_frames)))
                self.assertEqual(result["worker_summary_application_bytes"],
                                 sum(len(payload) for _, payload in summary_frames))
                expected_summaries = [(p["worker_id"], p["bytes"])
                                      for r in result["rounds"] for p in r["worker_payload_lengths"]]
                self.assertEqual(expected_summaries,
                                 [(owner, len(payload)) for owner, payload in summary_frames])
                self.assertEqual(len(delta_frames), len(result["rounds"]) * len(initial_frames))
                self.assertEqual(result["later_round_state_application_bytes"], sum(map(len, delta_frames)))
                for index, round_audit in enumerate(result["rounds"]):
                    received = delta_frames[index * 3:(index + 1) * 3]
                    self.assertEqual(len(set(received)), 1)
                    self.assertEqual(round_audit["round_state_recipient_count"], len(received))
                    self.assertEqual(round_audit["round_state_bytes"], len(received[0]))

    def test_exact_wire_whitelist_and_hostile_encoding(self):
        summary = self.summary(); data = W.encode_summary(summary, 1)
        value = json.loads(data)
        for addition in ("labels", "raw_rows", "raw_distances", "inverse_covariance", "unknown"):
            altered = copy.deepcopy(value); altered["payload"][addition] = [1.0]
            self.assertFailure("wire_key_mismatch", W.decode_summary, A.canonical(altered), 1)
        nested = copy.deepcopy(value); nested["payload"]["permit"]["label"] = 1
        self.assertFailure("wire_key_mismatch", W.decode_summary, A.canonical(nested), 1)
        self.assertFailure("wire_duplicate_key", W.decode_summary, b'{"kind":1,"kind":2}', 1)
        for payload in (b'\xff', b'{', data + b' ', b'[]', b'{"x":NaN}', b'{"x":1e400}'):
            self.assertRaises(A.AdapterError, W.decode_summary, payload, 1)
        self.assertFailure("wire_payload_type_or_size", W.decode_summary, b" " * (W.MAX_PAYLOAD_BYTES + 1), 1)

    def test_command_failure_receipt_does_not_emit_benign_result(self):
        output = io.StringIO()
        with patch.object(sys, "argv", ["check_afbkm_adapter.py"]), patch.object(C, "synthetic_check", side_effect=A.AdapterError("invalid_fixture_state")), redirect_stdout(output):
            status = C.main()
        self.assertEqual(status, 1)
        receipt = json.loads(output.getvalue())
        self.assertEqual(receipt, {"status": "synthetic_integration_failed", "failure_reason": "invalid_fixture_state"})
        self.assertNotIn("score", receipt)

    def test_malformed_feature_schema_or_ragged_payload_has_explicit_failure(self):
        self.assertRaises(A.AdapterError, A.FrozenArray.of, [[1.0], [1.0, 2.0]])
        features = ({"bad": "name"},)
        self.assertFailure("schema_mismatch", replace, self.state, features=features,
                           schema_id=A.digest(list(features)))

    def test_stale_delta_and_bad_identity_rejected(self):
        current, _ = self.merge([self.summary()]); data = W.encode_delta(self.state, current)
        self.assertFailure("model_round_state_mismatch", W.apply_delta, current, data)
        value = json.loads(data); value["payload"]["state_id"] = "0" * 64
        self.assertFailure("wire_state_identity", W.apply_delta, self.state, A.canonical(value))
        value = json.loads(data); value["payload"]["fixed_state_id"] = "0" * 64
        self.assertFailure("fixed_state_changed", W.apply_delta, self.state, A.canonical(value))
        self.assertFailure("initial_state_round", W.encode_initial, current)
        initial = json.loads(W.encode_initial(self.state)); initial["payload"]["state_id"] = "0" * 64
        self.assertFailure("wire_state_identity", W.decode_initial, A.canonical(initial))


if __name__ == "__main__":
    unittest.main()
