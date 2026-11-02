"""Synthetic checks for pilot boundaries; never opens real datasets."""

from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import benign_pilot as pilot
from benign_pilot import (
    _metric,
    calibrate_threshold,
    chronological_history,
    exclude_target_keys,
    fit_standardizer,
    guard_development_path,
    run_target,
    transform,
    validate_training_rows,
    weighted_average,
)


class ThresholdTests(unittest.TestCase):
    def test_calibration_uses_higher_empirical_quantile(self):
        self.assertEqual(calibrate_threshold(np.arange(20, dtype=np.float64)), 19.0)

    def test_scores_equal_to_threshold_are_not_alerts(self):
        frame = pd.DataFrame({
            "_group_id": ["a", "b", "c"],
            "timestamp": ["2023-05-17T14:00:00"] * 3,
            "label": ["Normal"] * 3,
        })
        metric = _metric(1, "synthetic", "benign_probe", np.array([1.0, 2.0, 3.0]), 2.0, frame, 0.05)
        self.assertEqual(metric["alerts"], 1)
        self.assertEqual(metric["denominator_rows"], 3)
        self.assertEqual(metric["observed_fraction"], 1.0 / 3.0)
        self.assertEqual(metric["alert_comparison"], "strictly_greater_than")

    def test_invalid_calibration_scores_fail_before_threshold_selection(self):
        for values in [np.array([]), np.array([1.0, np.nan]), np.array([[1.0, 2.0]])]:
            with self.subTest(values=values.tolist()):
                with self.assertRaises(ValueError):
                    calibrate_threshold(values)


class FedAvgTests(unittest.TestCase):
    def test_unequal_client_sizes_give_weighted_mean_without_mutating_inputs(self):
        states = [
            {"weight": torch.tensor([[1.0, 3.0]]), "bias": torch.tensor([2.0])},
            {"weight": torch.tensor([[5.0, 7.0]]), "bias": torch.tensor([10.0])},
        ]
        original = [{key: value.clone() for key, value in state.items()} for state in states]
        result = weighted_average(states, [1, 3])
        torch.testing.assert_close(result["weight"], torch.tensor([[4.0, 6.0]]))
        torch.testing.assert_close(result["bias"], torch.tensor([8.0]))
        for current, before in zip(states, original):
            for key in before:
                torch.testing.assert_close(current[key], before[key])

    def test_client_order_does_not_change_aggregation(self):
        states = [{"weight": torch.tensor([2.0, -2.0])}, {"weight": torch.tensor([8.0, 4.0])}]
        forward = weighted_average(states, [2, 1])
        reverse = weighted_average(states[::-1], [1, 2])
        torch.testing.assert_close(forward["weight"], reverse["weight"])


class StandardizerTests(unittest.TestCase):
    def test_fit_statistics_and_constant_feature_behavior(self):
        fitting = np.array([[1.0, 4.0], [3.0, 4.0]], dtype=np.float64)
        scaler = fit_standardizer(fitting)
        np.testing.assert_allclose(scaler["mean"], [2.0, 4.0])
        np.testing.assert_allclose(scaler["scale"], [1.0, 1.0])
        np.testing.assert_allclose(transform(fitting, scaler), [[-1.0, 0.0], [1.0, 0.0]])

    def test_calibration_and_probe_values_cannot_change_fitted_statistics(self):
        fitting = np.array([[0.0, 2.0], [2.0, 6.0]], dtype=np.float64)
        calibration = np.array([[1.0, 4.0]], dtype=np.float64)
        probe = np.array([[3.0, 8.0]], dtype=np.float64)
        scaler = fit_standardizer(fitting)
        before_mean = np.array(scaler["mean"], copy=True)
        before_scale = np.array(scaler["scale"], copy=True)
        before_fit = transform(fitting, scaler).copy()
        transform(calibration, scaler)
        transform(probe, scaler)
        calibration[:] = 1.0e9
        probe[:] = -1.0e9
        transform(calibration, scaler)
        transform(probe, scaler)
        np.testing.assert_array_equal(scaler["mean"], before_mean)
        np.testing.assert_array_equal(scaler["scale"], before_scale)
        np.testing.assert_array_equal(transform(fitting, scaler), before_fit)
        np.testing.assert_allclose(before_mean, [1.0, 4.0])
        np.testing.assert_allclose(before_scale, [1.0, 2.0])


class RoleBoundaryTests(unittest.TestCase):
    @staticmethod
    def history(rows):
        return pd.DataFrame(rows, columns=["_group_id", "timestamp"]).assign(label="Normal")

    def test_chronological_split_discards_crossing_groups(self):
        history = self.history([
            ("early-a", "2023-05-11T14:00:00"),
            ("crossing", "2023-05-11T14:00:00"),
            ("early-b", "2023-05-11T14:01:00"),
            ("late-a", "2023-05-11T14:02:00"),
            ("crossing", "2023-05-11T14:03:00"),
            ("late-b", "2023-05-11T14:03:00"),
        ])
        fitting, calibration, diagnostics = chronological_history(history)
        self.assertEqual(set(fitting["_group_id"]), {"early-a", "early-b"})
        self.assertEqual(set(calibration["_group_id"]), {"late-a", "late-b"})
        self.assertTrue(set(fitting["_group_id"]).isdisjoint(calibration["_group_id"]))
        self.assertLess(pd.to_datetime(fitting["timestamp"]).max(), pd.to_datetime(calibration["timestamp"]).min())
        self.assertEqual(len(fitting) + len(calibration), len(history) - 2)
        self.assertIsInstance(diagnostics, dict)

    def test_one_timestamp_cannot_supply_chronological_roles(self):
        history = self.history([("a", "2023-05-11T14:00:00"), ("b", "2023-05-11T14:00:00")])
        with self.assertRaises(ValueError):
            chronological_history(history)

    def test_group_purge_cannot_leave_empty_roles(self):
        history = self.history([("crossing", "2023-05-11T14:00:00"), ("crossing", "2023-05-11T14:01:00")])
        with self.assertRaises(ValueError):
            chronological_history(history)

    def test_donor_exclusion_uses_all_target_keys_before_date_and_label_filtering(self):
        frame = pd.DataFrame([
            (1, "target-early", "Normal", "2023-05-11T14:00:00"),
            (1, "target-later", "Normal", "2023-05-17T14:00:00"),
            (1, "target-attack", "DDoS-bot", "2023-05-13T14:00:00"),
            (2, "target-later", "Normal", "2023-05-11T14:00:00"),
            (2, "target-attack", "Normal", "2023-05-11T14:00:00"),
            (2, "retained", "Normal", "2023-05-11T14:00:00"),
            (2, "wrong-date", "Normal", "2023-05-17T14:00:00"),
            (2, "wrong-label", "DDoS-stomp", "2023-05-11T14:00:00"),
            (3, "target-early", "Normal", "2023-05-11T14:00:00"),
        ], columns=["_client_id", "_group_id", "label", "timestamp"])
        donors, excluded_empty = exclude_target_keys(frame, 1)
        self.assertEqual(list(donors["_group_id"]), ["retained"])
        self.assertEqual(set(donors["_client_id"]), {2})
        self.assertEqual(set(excluded_empty), {3})
        self.assertTrue(set(donors["_group_id"]).isdisjoint(frame.loc[frame["_client_id"] == 1, "_group_id"]))

    def test_training_accepts_only_nonempty_early_benign_rows(self):
        good = self.history([("a", "2023-05-11T14:00:00")])
        validate_training_rows(good)
        bad_cases = [
            good.assign(label="DDoS-bot"),
            good.assign(label="BENIGN"),
            good.assign(timestamp="2023-05-17T14:00:00"),
            good.assign(timestamp="invalid-time"),
            good.iloc[:0].copy(),
        ]
        for bad in bad_cases:
            with self.subTest(case=bad.to_dict("list")):
                with self.assertRaises(ValueError):
                    validate_training_rows(bad)


class DevelopmentPathTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name).resolve()
        self.workspace = self.base / "workspace"
        self.workspace.mkdir()

    def tearDown(self):
        self.temporary.cleanup()

    def make_file(self, relative):
        path = self.workspace / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("synthetic fixture only\n", encoding="utf-8")
        return path

    def test_only_direct_flnet_development_csvs_are_allowed(self):
        for relative in [
            "datasets/flnet2023/extracted/Normal/Dataset-1.csv",
            "datasets/flnet2023/extracted/DDoS/Dataset-1-BOT.csv",
        ]:
            expected = self.make_file(relative)
            with self.subTest(path=relative):
                self.assertEqual(guard_development_path(self.workspace, relative), expected.resolve())

    def test_reserved_other_dataset_nested_and_wrong_suffix_paths_are_rejected(self):
        forbidden = [
            "datasets/flnet2023/extracted/TEST/normal.csv",
            "datasets/cicddos2019/extracted/03-11/Syn.csv",
            "datasets/cicddos2019/extracted/01-12/Syn.csv",
            "datasets/flnet2023/extracted/Normal/nested/example.csv",
            "datasets/flnet2023/extracted/Normal/example.txt",
        ]
        for relative in forbidden:
            self.make_file(relative)
            with self.subTest(path=relative):
                with self.assertRaises(ValueError):
                    guard_development_path(self.workspace, relative)

    def test_traversal_and_absolute_paths_are_rejected(self):
        self.make_file("datasets/flnet2023/extracted/TEST/normal.csv")
        direct = self.make_file("datasets/flnet2023/extracted/Normal/Dataset-1.csv")
        for path in [
            "datasets/flnet2023/extracted/Normal/../TEST/normal.csv",
            "../workspace/datasets/flnet2023/extracted/Normal/Dataset-1.csv",
            str(direct),
        ]:
            with self.subTest(path=path):
                with self.assertRaises(ValueError):
                    guard_development_path(self.workspace, path)

    def test_an_allowed_looking_symlink_cannot_escape_the_workspace(self):
        external = self.base / "outside.csv"
        external.write_text("synthetic fixture only\n", encoding="utf-8")
        relative = "datasets/flnet2023/extracted/Normal/linked.csv"
        link = self.workspace / relative
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(external)
        with self.assertRaises(ValueError):
            guard_development_path(self.workspace, relative)


class SyntheticExecutionTests(unittest.TestCase):
    @staticmethod
    def generated_frame():
        rows = []

        def add(client, key, stamp, label, count, example):
            folder = "Normal" if label == "Normal" else "DDoS"
            rows.append({
                "_source_path": f"datasets/flnet2023/extracted/{folder}/Dataset-{client}.csv",
                "_source_row": len(rows),
                "_client_id": client,
                "_group_id": key,
                "_role": "synthetic_prior_role",
                "label": label,
                "timestamp": stamp,
                "tot_fwd_pkts": float(count),
                "example_feature": float(example),
            })

        for i in range(8):
            add(1, f"target-history-{i}", f"2023-05-11T14:{i:02d}:00", "Normal", 1 + i % 2, 2 * i)
        for i in range(3):
            add(1, f"target-attack-{i}", f"2023-05-13T14:{i:02d}:00", "DDoS-bot", 20 + 5 * i, 80 + 10 * i)
            add(1, f"target-benign-{i}", f"2023-05-17T14:{i:02d}:00", "Normal", 1 + min(i, 1), 7 + 2 * i)
        for i in range(8):
            add(2, f"donor-{i}", f"2023-05-11T14:{i:02d}:00", "Normal", 4 + 2 * (i % 2), 20 + 2 * i)
        add(3, "target-history-0", "2023-05-11T14:00:00", "Normal", 99, 999)
        return pd.DataFrame(rows)

    def test_generated_target_runs_all_methods_with_separate_scalers_and_roles(self):
        frame = self.generated_frame()
        original = frame.copy(deep=True)
        previous_threads = torch.get_num_threads()
        previous_determinism = torch.are_deterministic_algorithms_enabled()
        try:
            torch.set_num_threads(2)
            torch.use_deterministic_algorithms(True)
            with tempfile.TemporaryDirectory() as temporary:
                destination = Path(temporary) / "target-1"
                result = run_target(frame, ["tot_fwd_pkts", "example_feature"], 1, 20261101, destination)
                self.assertEqual(result["status"], "completed_engineering_only")
                self.assertTrue(result["same_initial_weights"])
                self.assertEqual(result["excluded_empty_donor_ids"], [3])
                self.assertEqual(len(result["local_epoch_losses"]), 3)
                self.assertTrue(np.isfinite(result["local_epoch_losses"]).all())
                self.assertEqual(len(result["federated_rounds"]), 3)
                for round_record in result["federated_rounds"]:
                    self.assertEqual([item["client_id"] for item in round_record["clients"]], [2])
                    self.assertTrue(all(np.isfinite(item["loss"]) for item in round_record["clients"]))

                expected_methods = {
                    "local_autoencoder", "federated_autoencoder",
                    "calibrated_forward_packet_count_score",
                    "prior_exploratory_forward_packet_count_control",
                }
                metrics = result["metrics"]
                self.assertEqual(len(metrics), 12)
                self.assertEqual({item["method"] for item in metrics}, expected_methods)
                for method in expected_methods:
                    self.assertEqual(
                        {item["probe_role"] for item in metrics if item["method"] == method},
                        {"target_calibration", "attack_probe", "benign_probe"},
                    )
                for item in metrics:
                    self.assertTrue(np.isfinite(item["threshold"]))
                    self.assertTrue(np.isfinite(item["observed_fraction"]))
                    self.assertGreaterEqual(item["observed_fraction"], 0.0)
                    self.assertLessEqual(item["observed_fraction"], 1.0)
                for field in ["local_training_seconds", "federated_training_seconds", "total_target_seconds"]:
                    self.assertTrue(np.isfinite(result[field]))
                    self.assertGreaterEqual(result[field], 0.0)

                scalers = json.loads((destination / "scalers.json").read_text())
                np.testing.assert_allclose(scalers["local"]["mean"], [1.5, 3.0])
                np.testing.assert_allclose(scalers["federated"]["mean"], [5.0, 27.0])
                self.assertFalse(np.allclose(scalers["local"]["mean"], scalers["federated"]["mean"]))

                for method in ["local_autoencoder", "federated_autoencoder"]:
                    with np.load(destination / f"{method}-weights.npz", allow_pickle=False) as archive:
                        self.assertTrue(archive.files)
                        for key in archive.files:
                            self.assertTrue(np.isfinite(archive[key]).all())

                provenance = pd.read_csv(destination / "role-provenance.csv")
                self.assertEqual(set(provenance["new_role"]), {
                    "donor_fit", "target_fit", "target_calibration", "attack_probe", "benign_probe",
                })
                self.assertTrue((provenance.groupby("_group_id")["new_role"].nunique() == 1).all())
                self.assertFalse(provenance.duplicated(["_source_path", "_source_row"]).any())
                self.assertEqual(set(provenance.loc[provenance["new_role"] == "donor_fit", "_client_id"]), {2})
                self.assertEqual(len(provenance[provenance["new_role"] == "target_fit"]), 4)
                self.assertEqual(len(provenance[provenance["new_role"] == "target_calibration"]), 4)

                perturbed = frame.copy(deep=True)
                changed_keys = {
                    *(f"target-history-{i}" for i in range(4, 8)),
                    *(f"target-attack-{i}" for i in range(3)),
                    *(f"target-benign-{i}" for i in range(3)),
                }
                mask = perturbed["_group_id"].isin(changed_keys)
                perturbed.loc[mask, ["tot_fwd_pkts", "example_feature"]] += 1000.0
                second_destination = Path(temporary) / "target-1-perturbed"
                second = run_target(perturbed, ["tot_fwd_pkts", "example_feature"], 1, 20261101, second_destination)
                second_scalers = json.loads((second_destination / "scalers.json").read_text())
                self.assertEqual(scalers, second_scalers)
                self.assertEqual(result["initial_state_sha256"], second["initial_state_sha256"])
                pd.testing.assert_frame_equal(frame, original)
        finally:
            torch.set_num_threads(previous_threads)
            torch.use_deterministic_algorithms(previous_determinism)

    def test_generated_execute_records_a_partial_failure_and_preserves_input(self):
        previous_threads = torch.get_num_threads()
        previous_determinism = torch.are_deterministic_algorithms_enabled()
        try:
            with tempfile.TemporaryDirectory() as temporary:
                workspace = Path(temporary)
                historical = workspace / "runs" / "engineering-smoke-v1"
                historical.mkdir(parents=True)
                source = historical / "selected-records.parquet"
                frame = self.generated_frame()
                frame.to_parquet(source, index=False)
                original_hash = pilot.sha256(source)
                preparation = {
                    "files": {"selected-records.parquet": original_hash},
                    "selected_rows": len(frame),
                    "excluded_predictors": list(pilot.EXCLUDED),
                    "feature_count": 2,
                }
                (historical / "preparation.json").write_text(json.dumps(preparation))
                actual_train_epochs = pilot.train_epochs
                calls = 0

                def fail_first_federated_fit(*args, **kwargs):
                    nonlocal calls
                    calls += 1
                    if calls == 2:
                        raise ValueError("Injected synthetic first-FL-client failure")
                    return actual_train_epochs(*args, **kwargs)

                with patch.object(pilot, "APPROVED_SELECTED_SHA256", original_hash), \
                     patch.object(pilot, "TARGETS", (1,)), \
                     patch.object(pilot, "train_epochs", side_effect=fail_first_federated_fit):
                    output, summary = pilot.execute(workspace, "synthetic-failed-v1", seed=20261101)

                self.assertEqual(calls, 2)
                self.assertEqual(summary["status"], "failed")
                self.assertEqual(summary["successful_targets"], 0)
                self.assertEqual(summary["training_started_method_count"], 2)
                self.assertEqual(summary["training_completed_method_count"], 1)
                self.assertEqual(summary["completed_autoencoder_method_target_pairs"], 0)
                self.assertEqual(summary["completed_descriptive_control_target_pairs"], 0)
                self.assertEqual(len(summary["failures"]), 1)
                self.assertEqual(summary["failures"][0]["target_id"], 1)
                self.assertIn("Injected synthetic", summary["failures"][0]["message"])
                self.assertEqual(summary["target_results"], [])
                self.assertTrue(summary["source_unchanged"])
                self.assertEqual(pilot.sha256(source), original_hash)
                self.assertFalse((output / "target-1" / "result.json").exists())
                progress = json.loads((output / "target-1" / "training-progress.json").read_text())
                self.assertEqual(progress, {
                    "local_autoencoder": "training_completed",
                    "federated_autoencoder": "training_started",
                })
                self.assertTrue((output / "summary.json").is_file())
                self.assertTrue((output / "artifact-manifest.json").is_file())
        finally:
            torch.set_num_threads(previous_threads)
            torch.use_deterministic_algorithms(previous_determinism)


class ReviewRegressionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary.name)
        self.threads = torch.get_num_threads()
        self.deterministic = torch.are_deterministic_algorithms_enabled()
        torch.set_num_threads(2)

    def tearDown(self):
        torch.set_num_threads(self.threads)
        torch.use_deterministic_algorithms(self.deterministic)
        self.temporary.cleanup()

    def historical_fixture(self):
        frame = SyntheticExecutionTests.generated_frame()
        historical = self.workspace / "runs" / "engineering-smoke-v1"
        historical.mkdir(parents=True)
        source = historical / "selected-records.parquet"
        frame.to_parquet(source, index=False, engine="pyarrow")
        digest = pilot.sha256(source)
        preparation = {"files": {"selected-records.parquet": digest},
                       "selected_rows": len(frame), "excluded_predictors": list(pilot.EXCLUDED),
                       "feature_count": 2}
        (historical / "preparation.json").write_text(json.dumps(preparation))
        return digest

    def test_all_missing_blank_and_nonstring_labels_fail_before_any_split_or_training(self):
        for value in [None, np.nan, pd.NA, "", "  ", 7]:
            for date in ["2023-05-11", "2023-05-13", "2023-05-17", "2023-05-19"]:
                with self.subTest(value=repr(value), date=date):
                    frame = SyntheticExecutionTests.generated_frame().astype({"label": object})
                    frame.loc[0, "label"] = value
                    frame.loc[0, "timestamp"] = date + "T14:00:00"
                    before = frame.copy(deep=True)
                    with patch.object(pilot, "chronological_history") as split, \
                         patch.object(pilot, "train_epochs") as train:
                        with self.assertRaisesRegex(ValueError, "Labels"):
                            run_target(frame, ["tot_fwd_pkts", "example_feature"], 1, 42,
                                       self.workspace / "must-not-exist")
                    split.assert_not_called()
                    train.assert_not_called()
                    self.assertFalse((self.workspace / "must-not-exist").exists())
                    pd.testing.assert_frame_equal(frame, before)

    def test_missing_required_control_fails_before_training(self):
        frame = SyntheticExecutionTests.generated_frame().drop(columns="tot_fwd_pkts")
        with patch.object(pilot, "train_epochs") as train:
            with self.assertRaisesRegex(ValueError, "control column"):
                run_target(frame, ["example_feature"], 1, 42, self.workspace / "missing-control")
        train.assert_not_called()
        self.assertFalse((self.workspace / "missing-control").exists())

    def test_target_accounting_retains_unassigned_date_and_label_and_straddlers(self):
        frame = SyntheticExecutionTests.generated_frame()
        extra = frame.iloc[[0]].copy()
        extra["_source_row"] = 1000
        extra["_group_id"] = "future-record"
        extra["timestamp"] = "2023-05-19T14:00:00"
        other = extra.copy()
        other["_source_row"] = 1001
        other["_group_id"] = "off-role-label"
        other["timestamp"] = "2023-05-17T14:01:00"
        other["label"] = "DDoS-bot"
        target = pd.concat([frame[frame["_client_id"] == 1], extra, other], ignore_index=True)
        target.loc[target["_group_id"].isin(["target-history-0", "target-history-7"]), "_group_id"] = "straddler"
        dates = pilot._times(target).dt.strftime("%Y-%m-%d")
        history = target[target["label"].eq("Normal") & dates.eq("2023-05-11")]
        fit, cal, _ = chronological_history(history)
        parts = {"target_fit": fit, "target_calibration": cal,
                 "attack_probe": target[dates.eq("2023-05-13")],
                 "benign_probe": target[dates.eq("2023-05-17") & target["label"].eq("Normal")]}
        result, discarded, unassigned = pilot.target_role_accounting(target, history, parts)
        self.assertTrue(result["all_rows_accounted_for"])
        self.assertEqual(result["total_target_rows"], 16)
        self.assertEqual(len(discarded), 2)
        self.assertEqual(set(discarded["_group_id"]), {"straddler"})
        self.assertEqual(set(unassigned["_group_id"]), {"future-record", "off-role-label"})
        self.assertEqual(result["roles"]["unassigned"]["by_stored_date_label"], [
            {"stored_date": "2023-05-17", "label": "DDoS-bot", "rows": 1, "candidate_groups": 1},
            {"stored_date": "2023-05-19", "label": "Normal", "rows": 1, "candidate_groups": 1},
        ])
        self.assertEqual(sum(v["rows"] for v in result["roles"].values()), len(target))
        for rows in parts.values():
            self.assertTrue(set(rows["_source_row"]).isdisjoint({1000, 1001}))
        with self.assertRaisesRegex(ValueError, "duplicate target role"):
            pilot.target_role_accounting(target, history, {**parts, "duplicate": fit})

    def test_dependency_failure_is_failed_summary_and_reads_pin_pyarrow(self):
        digest = self.historical_fixture()
        actual_read = pd.read_parquet
        with patch.object(pilot, "APPROVED_SELECTED_SHA256", digest), \
             patch.object(pilot, "TARGETS", (1,)), \
             patch.object(pilot.pd, "read_parquet", wraps=actual_read) as reader, \
             patch.object(pilot.importlib.metadata, "version", side_effect=RuntimeError("synthetic version failure")), \
             patch.object(pilot, "run_target") as target:
            output, result = pilot.execute(self.workspace, "metadata-failure-v2")
        target.assert_not_called()
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["successful_targets"], 0)
        self.assertTrue(any(v.get("stage") == "dependency_metadata" for v in result["failures"]))
        self.assertEqual(reader.call_count, 2)
        self.assertTrue(all(call.kwargs["engine"] == "pyarrow" for call in reader.call_args_list))
        self.assertEqual(reader.call_args_list[0].kwargs["columns"], list(pilot.METADATA))
        self.assertEqual(json.loads((output / "summary.json").read_text())["status"], "failed")
        manifest = json.loads((output / "artifact-manifest.json").read_text())
        self.assertEqual(manifest["summary.json"], pilot.sha256(output / "summary.json"))

    def test_missing_control_metric_cannot_complete_target(self):
        actual_metric = pilot._metric
        def corrupt_control(*args, **kwargs):
            metric = actual_metric(*args, **kwargs)
            if metric["method"] == "calibrated_forward_packet_count_score":
                metric["method"] = "prior_exploratory_forward_packet_count_control"
            return metric
        with patch.object(pilot, "_metric", side_effect=corrupt_control):
            with self.assertRaisesRegex(ValueError, "metrics are incomplete or duplicated"):
                run_target(SyntheticExecutionTests.generated_frame(), ["tot_fwd_pkts", "example_feature"],
                           1, 42, self.workspace / "missing-metric")
        self.assertFalse((self.workspace / "missing-metric" / "result.json").exists())

    def test_manifest_failure_changes_completed_run_status_and_cli_exit(self):
        digest = self.historical_fixture()
        actual_write = pilot.write_json
        def fail_manifest(path, value):
            if path.name == "artifact-manifest.json":
                raise OSError("synthetic manifest failure")
            return actual_write(path, value)
        with patch.object(pilot, "APPROVED_SELECTED_SHA256", digest), \
             patch.object(pilot, "TARGETS", (1,)), \
             patch.object(pilot, "write_json", side_effect=fail_manifest):
            output, result = pilot.execute(self.workspace, "manifest-failure-v2")
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["successful_targets"], 1)
        self.assertEqual(result["training_completed_method_count"], 2)
        self.assertEqual(result["failures"][-1]["stage"], "finalization")
        self.assertEqual(json.loads((output / "summary.json").read_text())["status"], "failed")
        self.assertTrue((output / "target-1" / "result.json").is_file())
        self.assertFalse((output / "artifact-manifest.json").exists())
        with patch.object(pilot, "execute", return_value=(output, result)), \
             patch.object(sys, "argv", ["benign_pilot.py", "--workspace", str(self.workspace),
                                        "--run-id", "synthetic-v2", "--execute-development-pilot"]), \
             patch("builtins.print"):
            self.assertEqual(pilot.main(), 1)

    def test_unwritable_failure_summary_propagates_and_atomic_write_preserves_prior_file(self):
        output = self.workspace / "unwritable"
        output.mkdir()
        record = {"status": "completed_engineering_only", "failures": []}
        with patch.object(pilot, "write_json", side_effect=OSError("synthetic unwritable filesystem")):
            with self.assertRaisesRegex(OSError, "unwritable"):
                pilot.finalize_run(output, record)
        path = output / "existing.json"
        path.write_text('{"old":true}\n')
        with self.assertRaises(ValueError):
            pilot.write_json(path, {"invalid": float("nan")})
        self.assertEqual(path.read_text(), '{"old":true}\n')
        self.assertFalse((output / ".existing.json.tmp").exists())

    def test_sparse_donor_ids_use_logged_dense_ranks_and_distinct_round_seeds(self):
        frame = SyntheticExecutionTests.generated_frame()
        extra = frame[frame["_client_id"] == 2].copy()
        extra["_client_id"] = 102
        extra["_source_row"] += 1000
        extra["_group_id"] = "extra-" + extra["_group_id"]
        extra["_source_path"] = "datasets/flnet2023/extracted/Normal/Dataset-102.csv"
        frame = pd.concat([frame, extra], ignore_index=True)
        result = run_target(frame, ["tot_fwd_pkts", "example_feature"], 1, 42, self.workspace / "sparse-donors")
        seeds = []
        for round_id, round_record in enumerate(result["federated_rounds"]):
            self.assertEqual([c["client_id"] for c in round_record["clients"]], [2, 102])
            self.assertEqual([c["dense_rank"] for c in round_record["clients"]], [0, 1])
            for c in round_record["clients"]:
                self.assertEqual(c["shuffle_seed"], pilot.donor_shuffle_seed(42, 1, round_id, c["dense_rank"]))
                seeds.append(c["shuffle_seed"])
        self.assertEqual(len(set(seeds)), 6)


if __name__ == "__main__":
    unittest.main()
