"""Independent audit and purpose boundaries; all sources here are fabricated."""
from pathlib import Path
from dataclasses import FrozenInstanceError, replace
from unittest.mock import patch
import copy
import csv
import json
import sys
import unittest
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import audit_candidate_independently as I
import purpose_data_view as V
import load_grouped_candidate as L


class AuditAndViewTests(unittest.TestCase):
    def setUp(self):
        from test_grouped_loader import LoaderTests
        self.f = LoaderTests(); self.f.setUp(); self.addCleanup(self.f.doCleanups)
        self.f.run_loader("independent-fixture")
        self.prepared = self.f.root / "reports/development-preparation/independent-fixture"
        self.load()

    def load(self):
        self.args = dict(root=self.f.root, prepared_name=str(self.prepared), contract="config/contract.json",
                         registry="config/registry.json", contract_sha=L.sha(self.f.cp), registry_sha=L.sha(self.f.rp))
        self.plan = I.make_plan(**self.args)
        self.view = V.PurposeDataset(self.prepared, expected_features=tuple(self.f.features),
                                      candidate_sha256=L.sha(self.f.mp), assignment_sha256=self.f.manifest["assignment_sha256"])

    def reseal(self, name):
        seal = L.read_json(self.prepared / "COMPLETE.json"); path = self.prepared / name
        seal["artifacts"][name] = {"sha256": L.sha(path), "bytes": path.stat().st_size}
        (self.prepared / "COMPLETE.json").write_text(json.dumps(seal))

    def audit(self, name="checked"):
        plan_path = self.f.root / ("config/" + name + ".json"); I.save_plan(plan_path, self.plan)
        return I.run(**self.args, plan_path=plan_path, plan_sha=L.sha(plan_path),
                     output_name="reports/development-preparation/" + name)

    def identities(self, role, owner, benign=False):
        records = self.view._records
        positions = [i for i, r in enumerate(records) if r["role_id"] == L.ROLE_IDS[role] and r["observer_id"] == owner
                     and (not benign or r["binary_label"] == 0)]
        return self.view._identities(np.asarray(positions, dtype=np.int64))

    def test_plan_is_metadata_only_and_prespecifies_edges_and_boundaries(self):
        with patch.object(L, "open_arrays", side_effect=AssertionError("array opened")), patch.object(L, "open_source", side_effect=AssertionError("source opened")):
            plan = I.make_plan(**self.args)
        self.assertEqual(plan, self.plan); self.assertEqual(len(plan["sources"]), 14)
        for s in plan["sources"]:
            samples = {q["source_row"]: q["reasons"] for q in s["samples"]}
            self.assertIn("first", samples[0]); self.assertIn("last", samples[s["rows"] - 1])
            self.assertIn("before_source_write_boundary", samples[3])
            self.assertIn("after_source_write_boundary", samples[4])
            for boundary in range(((s["output_offset"] // 4) + 1) * 4, s["output_offset"] + s["rows"], 4):
                local = boundary - s["output_offset"]
                self.assertIn("before_global_array_boundary", samples[local - 1])
                self.assertIn("after_global_array_boundary", samples[local])
        original = copy.deepcopy(self.plan)
        self.assertRaises(FileExistsError, lambda: (I.save_plan(self.f.root / "config/exclusive-plan.json", original), I.save_plan(self.f.root / "config/exclusive-plan.json", original)))

    def test_independent_exact_source_row_float_and_timestamp_check_full_audit(self):
        result = self.audit()
        self.assertEqual(result["status"], "complete_independent_engineering_audit")
        self.assertEqual(result["source_rows_parsed"], len(self.f.expected))
        self.assertEqual(result["rows_by_role"], self.f.manifest["rows_by_role"])
        self.assertEqual(result["multiplicity_totals"]["rows"], len(self.f.expected))
        self.assertEqual(result["multiplicity_totals"]["keys"], self.f.manifest["candidate_groups"])
        self.assertFalse(result["model_fit_score_calibration_or_selection_performed"])
        self.assertTrue((self.f.root / "reports/development-preparation/checked/COMPLETE.json").is_file())
        for source in self.plan["sources"]:
            for sample in source["samples"]:
                pos = source["output_offset"] + sample["source_row"]
                self.assertEqual(int(self.view._records[pos]["source_row"]), sample["source_row"])

    def test_round_trip_decimal_and_stripped_timestamp(self):
        self.f.edit("num00", "0.3066101993807095471566981359501369297504425048828125")
        self.f.edit("timestamp", " 2023-05-13 15:00:00  ")
        self.f.run_loader("decimal-fixture"); self.prepared = self.f.root / "reports/development-preparation/decimal-fixture"; self.load()
        result = I.compare_samples(self.f.root, self.plan, self.view._X, self.view._records)
        self.assertEqual(result["total_rows_parsed"], len(self.f.expected))
        self.assertFalse(result["sample_values_written"])

    def test_sample_mismatch_retains_explicit_failed_receipt(self):
        X = np.load(self.prepared / "features.npy", mmap_mode="r+"); X[-1, 0] += 1; X.flush(); del X
        self.reseal("features.npy"); self.load()
        with self.assertRaisesRegex(ValueError, "Independent float64 sample differs"):
            self.audit("bad-sample")
        out = self.f.root / "reports/development-preparation/bad-sample"
        self.assertTrue((out / "FAILED.json").is_file()); self.assertFalse((out / "COMPLETE.json").exists())
        self.assertEqual(L.read_json(out / "FAILED.json")["failed_phase"], "independent_source_parse_and_sample_check")

    def test_timestamp_mismatch_is_not_repaired(self):
        records = np.load(self.prepared / "records.npy", mmap_mode="r+")
        records[0]["stored_timestamp"] = b"2023-05-13 15:00:01"; records.flush(); del records
        self.reseal("records.npy"); self.load()
        with self.assertRaisesRegex(ValueError, "Independent timestamp differs"):
            I.compare_samples(self.f.root, self.plan, self.view._X, self.view._records)

    def test_source_hash_failure_and_reserved_exclusion_before_open(self):
        p = self.f.root / self.plan["sources"][0]["path"]; p.write_bytes(p.read_bytes() + b"changed\n")
        actual = L.open_source; opened = []
        def guarded(root, item):
            self.assertIn(item["path"], L.EXPECTED_PATHS); opened.append(item["path"]); return actual(root, item)
        with patch.object(L, "open_source", side_effect=guarded):
            with self.assertRaisesRegex(ValueError, "Source hash mismatch before"):
                I.compare_samples(self.f.root, self.plan, self.view._X, self.view._records)
        self.assertEqual(len(opened), 1)
        forged = copy.deepcopy(self.plan); forged["sources"][0]["path"] = "datasets/flnet2023/extracted/TEST/poison.csv"
        with self.assertRaisesRegex(ValueError, "Unauthorized"):
            I.compare_samples(self.f.root, forged, self.view._X, self.view._records)

    def test_plan_hash_or_content_change_fails(self):
        self.plan["sources"][0]["samples"] = []
        with self.assertRaisesRegex(ValueError, "Prespecified plan/control/code binding differs"):
            self.audit("altered-plan")
        self.assertFalse((self.f.root / "reports/development-preparation/altered-plan/COMPLETE.json").exists())

    def test_integer_risk_scans_original_decimal_tokens_without_repair(self):
        self.f.edit("num00", "9007199254740993")
        self.f.run_loader("integer-fixture"); self.prepared = self.f.root / "reports/development-preparation/integer-fixture"; self.load()
        ranges = I.feature_ranges(self.view._X, self.f.features, chunk=3)
        feature = ranges[0]; self.assertTrue(feature["at_or_above_2pow53_integer_risk"])
        self.assertEqual(feature["max_abs_integral_value_exact_int"], 9007199254740992)
        tokens = I.inspect_integer_tokens(self.f.root, self.plan, ranges)
        self.assertEqual(tokens["status"], "integer_conversion_loss_detected")
        self.assertEqual(tokens["features"][0]["integer_conversion_loss"], 1)
        self.assertFalse(tokens["tokens_written"])

    def test_exact_ranges_integrality_signed_zero(self):
        X = np.array([[-0.0, 1.25], [0.0, -2.0], [2.0, 3.5]])
        ranges = I.feature_ranges(X, ["a", "b"], 2)
        self.assertEqual(ranges[0]["negative_zero_rows"], 1)
        self.assertEqual(ranges[1]["integral_float64_rows"], 1)
        self.assertEqual(ranges[1]["minimum_float64_hex"], (-2.0).hex())
        self.assertEqual(ranges[1]["maximum"], 3.5)
        self.assertRaises(ValueError, I.feature_ranges, np.array([[float("nan")]]), ["x"])

    def test_per_key_observer_multiplicity_and_exact_numeric_copies(self):
        X = np.array([[1., 2.], [1., 2.], [1., 2.], [1., 3.], [-0., 7.], [0., 7.]])
        records = np.zeros(6, dtype=L.RECORD_DTYPE)
        records["group_sha256"] = [b"a" * 64] * 4 + [b"b" * 64] * 2
        records["role_id"] = [0] * 4 + [1] * 2; records["observer_id"] = [1, 1, 2, 2, 3, 4]
        output = self.f.root / "multiplicity"; output.mkdir()
        result = I.multiplicities(X, records, output)["totals"]
        self.assertEqual(result["keys"], 2); self.assertEqual(result["rows"], 6)
        self.assertEqual(result["multi_observer_keys"], 2)
        self.assertEqual(result["multi_observer_keys_all_features_identical"], 1)
        self.assertEqual(result["cross_observer_identical_record_pairs"], 3)
        self.assertEqual(result["within_observer_identical_record_pairs"], 1)
        self.assertEqual(result["repeated_key_observer_pairs_with_feature_variation"], 1)
        with (output / "per-key-observer.csv").open() as f: rows = list(csv.DictReader(f))
        self.assertEqual(sum(int(r["rows"]) for r in rows), 6)
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0]["all_features_identical_within_key_observer"], "True")

    def test_global_key_roles_cannot_mix(self):
        X = np.array([[0.], [0.]])
        records = np.zeros(2, dtype=L.RECORD_DTYPE); records["group_sha256"] = b"a" * 64
        records["role_id"] = [0, 1]; records["observer_id"] = 1
        output = self.f.root / "bad-multiplicity"; output.mkdir()
        with self.assertRaisesRegex(ValueError, "spans global roles"): I.multiplicities(X, records, output)

    def test_seal_failure_and_schema_reordering_rejected(self):
        X = np.load(self.prepared / "features.npy", mmap_mode="r+"); X[0, 0] += 1; X.flush(); del X
        with self.assertRaisesRegex(ValueError, "integrity mismatch"): self.load()
        self.reseal("features.npy")
        schema = L.read_json(self.prepared / "schema.json"); schema["features"].reverse()
        (self.prepared / "schema.json").write_text(json.dumps(schema)); self.reseal("schema.json")
        with self.assertRaisesRegex(ValueError, "feature/role schema differs"): self.load()

    def test_unknown_role_observer_zero_or_wrong_source_address_rejected(self):
        for field, value, reason in [("role_id", 255, "Unknown prepared role"), ("observer_id", 0, "ownership differs"), ("source_row", 999, "Source-row identities differ")]:
            records = np.load(self.prepared / "records.npy", mmap_mode="r+"); before = records[0][field].copy(); records[0][field] = value
            records.flush(); del records; self.reseal("records.npy")
            with self.assertRaisesRegex(ValueError, reason): self.load()
            records = np.load(self.prepared / "records.npy", mmap_mode="r+"); records[0][field] = before; records.flush(); del records; self.reseal("records.npy")
        self.load()

    def test_worker_view_never_reads_labels_or_exposes_heldout_roles(self):
        class FieldTrap:
            def __init__(self, base): self.base = base
            def __len__(self): return len(self.base)
            def __getitem__(self, item):
                if isinstance(item, str):
                    if "label" in item: raise AssertionError("worker read forbidden label")
                    return self.base[item]
                return FieldTrap(self.base[item])
        expected = sum(r["observer_id"] == 1 and r["role_id"] == 0 for r in self.view._records)
        self.view._records = FieldTrap(self.view._records)
        batches = list(self.view.unlabeled_train(1).batches(3))
        self.assertEqual(sum(len(b.X) for b in batches), expected)
        for b in batches:
            self.assertFalse(hasattr(b, "y"))
            for identity in b.identities:
                self.assertEqual(identity.role_id, 0); self.assertEqual(identity.observer_id, 1)
                self.assertRaises(KeyError, identity.__getitem__, "binary_label")
        self.assertRaises(ValueError, self.view.unlabeled_train, 0)
        self.assertRaises(ValueError, self.view.supervised_train, 11)
        self.assertRaises(ValueError, self.view.unlabeled_train(1).reporting_labels, ())

    def test_supervised_and_anchor_train_are_immutable_and_exact(self):
        batches = list(self.view.supervised_train(1).batches(3))
        for b in batches:
            for j, identity in enumerate(b.identities):
                expected = self.f.expected[identity.source_id, identity.source_row]
                self.assertEqual(b.y[j], L.roles.LABELS[expected[1]])
                np.testing.assert_array_equal(b.X[j], expected[2])
            self.assertRaises(ValueError, b.X.setflags, write=True)
            self.assertRaises(ValueError, b.y.setflags, write=True)
        identities = self.identities("train", 1, benign=True)[:2]
        anchor = self.view.trusted_benign_anchor(1, identities, approval_id="synthetic-anchor")
        self.assertEqual(sum(len(b.X) for b in anchor.batches(1)), 2)
        self.assertRaises(FrozenInstanceError, setattr, anchor, "purpose", "frozen_calibration_scoring")
        self.assertFalse(self.view._X.flags.writeable); self.assertFalse(self.view._records.flags.writeable)
        self.assertRaises(ValueError, self.view._X.setflags, write=True)

    def test_anchor_rejects_heldout_owner_duplicate_and_attack_rows(self):
        train = self.identities("train", 1, True)
        held = self.identities("validation", 1)
        self.assertTrue(held)
        for ids in ((train[0], held[0]), (train[0], train[0]), self.identities("train", 2, True)[:2]):
            self.assertRaises(ValueError, self.view.trusted_benign_anchor, 1, ids, approval_id="declared")
        attack = [identity for identity in self.identities("train", 1) if identity not in train]
        self.assertTrue(attack)
        with self.assertRaisesRegex(ValueError, "non-benign"):
            self.view.trusted_benign_anchor(1, (train[0], attack[0]), approval_id="declared")

    def test_purpose_view_to_af_adapter_bridge_and_explicit_anchor_exclusion(self):
        import afbkm_adapter as A
        import check_afbkm_adapter as C
        ids = self.identities("train", 1, True)[:2]
        anchor_view = self.view.trusted_benign_anchor(1, ids, approval_id="fixture-approved-anchor")
        scope = A.TrainingScope(L.sha(self.f.mp), self.plan["assignment_sha256"], tuple(self.f.features),
                                tuple((q["source_id"], q["sha256"]) for q in self.plan["sources"]))
        def adapt(batch, owner):
            return A.training_batch(batch.X, batch.identities, range(len(batch.X)), scope, owner)
        anchor_batch = adapt(next(anchor_view.batches(2)), 1)
        state, context = A.initialize_anchor(anchor_batch, A.Parameters(1.0, 3, .5, 3), "view-fixture", trusted_benign=True)
        workers = {}; expected = {}
        for owner in range(1, 11):
            view = self.view.unlabeled_train(owner, exclude_anchor=anchor_view if owner == 1 else None)
            workers[owner] = [adapt(batch, owner) for batch in view.batches(3)]
            expected[str(owner)] = len(self.identities("train", owner)) - (2 if owner == 1 else 0)
        result = C.run_schedule(state, context, workers)
        self.assertEqual(result["rows_by_native_worker"], expected)
        self.assertEqual(result["total_worker_rows"] + 2, self.plan["rows_by_role"]["train"])
        self.assertRaises(ValueError, self.view.unlabeled_train, 2, exclude_anchor=anchor_view)
        excluded = {i for batch in self.view.unlabeled_train(1, exclude_anchor=anchor_view).batches(3) for i in batch.identities}
        self.assertFalse(set(ids) & excluded)

    def test_validation_selection_is_explicit_and_calibration_scoring_requires_frozen_id(self):
        self.assertRaises(TypeError, self.view.validation_selection, 1)
        self.assertRaises(ValueError, self.view.validation_selection, 1, declaration_id="")
        selected = list(self.view.validation_selection(1, declaration_id="declared-model-selection").batches(3))
        self.assertTrue(all(i.role_id == 1 for b in selected for i in b.identities))
        self.assertTrue(all(hasattr(b, "y") for b in selected))
        self.assertRaises(ValueError, self.view.scoring, "train", 1, declaration_id="x", frozen_scorer_id="a" * 64)
        self.assertRaises(ValueError, self.view.scoring, "calibration", 1, declaration_id="x", frozen_scorer_id="unknown")
        scoring = self.view.scoring("calibration", 1, declaration_id="post-freeze-report", frozen_scorer_id="a" * 64)
        for b in scoring.batches(2):
            self.assertFalse(hasattr(b, "y")); self.assertTrue(all(i.role_id == 2 for i in b.identities))
            self.assertEqual(len(scoring.reporting_labels(b.identities)), len(b.X))
        self.assertRaises(ValueError, scoring.reporting_labels, self.identities("train", 1))


if __name__ == "__main__": unittest.main()
