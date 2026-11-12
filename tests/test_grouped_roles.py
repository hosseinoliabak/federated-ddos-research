"""Scientific boundary checks using synthetic metadata, never real datasets."""

from pathlib import Path
from unittest.mock import patch
import copy
import csv
import hashlib
import json
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import prepare_grouped_roles as candidate
from flow_metadata import connection_key


class GroupedRoleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "config").mkdir()
        self.policy = dict(version=candidate.VERSION, candidate_id="synthetic-check",
                           dataset="flnet2023", claim_scope="within_release_grouped_holdout",
                           group_definition=candidate.GROUP_DEFINITION, role_seed="fixture-seed",
                           role_weights=dict(train=8, validation=1, calibration=1),
                           minimum_rows_per_client_role=1)
        self.proposal = dict(files=[], observed_development_label_mapping={"flnet2023": candidate.LABELS},
                             unmapped_development_labels={"flnet2023": []})

    def add_source(self, client=1, label="Normal", rows=None, header=None):
        suffix = "" if label == "Normal" else "-BOT"
        directory = "Normal" if label == "Normal" else "DDoS"
        relative = f"datasets/flnet2023/extracted/{directory}/Dataset-{client}{suffix}.csv"
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if rows is None:
            rows = [["192.0.2.1", "198.51.100.2", port, 443, 2048, "2023-05-13 15:00:00", label,
                     "not a numeric predictor"] for port in range(1025, 1085)]
        with path.open("w", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(header or list(candidate.FIELDS) + ["synthetic_predictor"])
            writer.writerows(rows)
        self.proposal["files"].append(dict(dataset="flnet2023", source_role="development", path=relative,
                                           client_id=client, sha256=candidate.sha(path)))
        return path

    def run_candidate(self, name="candidate"):
        (self.root / "config/policy.json").write_text(json.dumps(self.policy))
        (self.root / "config/proposal.json").write_text(json.dumps(self.proposal))
        return candidate.prepare(self.root, "config/proposal.json", "config/policy.json",
                                 f"reports/development-preparation/{name}")

    def test_direction_symmetry_preserves_exact_historical_key(self):
        key = connection_key("a", "b", 123, 456, 2048)
        self.assertEqual(key, '[[["a","123"],["b","456"]],"2048"]')
        self.assertEqual(key, connection_key("b", "a", 456, 123, 2048))
        self.assertNotEqual(key, connection_key("a", "b", 456, 123, 2048))
        self.assertEqual(candidate.assign_role(key, self.policy), candidate.assign_role(key, self.policy))

    def test_invalid_policy_cannot_silently_change_roles(self):
        for weights in [dict(train=True, validation=1, calibration=1), dict(train=8.0, validation=1, calibration=1),
                        dict(train=8, validation=0, calibration=1), dict(train=8, validation=-1, calibration=1),
                        dict(train=8, validation=1), dict(train=10000, validation=1, calibration=1)]:
            with self.subTest(weights=weights):
                policy = self.policy | {"role_weights": weights}
                with self.assertRaises(ValueError):
                    candidate.validate_policy(policy)
        with self.assertRaises(ValueError):
            candidate.validate_policy(self.policy | {"undocumented_option": True})

    def test_shared_keys_and_invalid_predictors_are_accounted_without_training(self):
        self.add_source(1)
        self.add_source(2, "DDoS-bot")  # same keys, different observer and label
        result = self.run_candidate()
        self.assertEqual(result["rows"], 120)
        self.assertEqual(result["candidate_groups"], 60)
        self.assertEqual(result["groups_seen_at_multiple_observers"], 60)
        self.assertEqual(result["groups_with_multiple_original_labels"], 60)
        self.assertFalse(result["model_fitted"])
        self.assertFalse(result["predictor_values_analyzed"])
        self.assertFalse(result["reserved_test_opened"])
        by_client = {(r["client_id"], r["role"]): r for r in result["support_checks"]["binary_class_counts"]}
        for role in candidate.ROLES:
            self.assertEqual(by_client[(1, role)]["benign"], by_client[(2, role)]["attack"])
        self.assertEqual(sum(result["rows_by_role"].values()), 120)
        self.assertEqual(result["status"], "candidate_not_frozen")

    def test_reserved_sources_are_not_opened_even_with_invalid_bytes(self):
        self.add_source()
        reserved = self.root / "datasets/flnet2023/extracted/TEST/Dataset-1.csv"
        reserved.parent.mkdir(parents=True)
        reserved.write_bytes(b"\xff\x00invalid test")
        self.proposal["files"].append(dict(dataset="flnet2023", source_role="reserved_test", path=str(reserved.relative_to(self.root)), sha256="wrong"))
        before = reserved.read_bytes()
        result = self.run_candidate()
        self.assertEqual(result["rows"], 60)
        self.assertEqual(reserved.read_bytes(), before)

    def test_forged_reserved_development_path_rejected_before_hashing(self):
        self.proposal["files"].append(dict(dataset="flnet2023", source_role="development",
            path="datasets/flnet2023/extracted/TEST/Dataset-1.csv", client_id=1, sha256="0" * 64))
        with patch.object(candidate, "sha", side_effect=AssertionError("dataset opened")):
            with self.assertRaisesRegex(ValueError, "Reserved path"):
                self.run_candidate()

    def test_symlink_to_reserved_file_rejected_before_hashing(self):
        path = self.add_source()
        reserved = self.root / "datasets/flnet2023/extracted/TEST/Dataset-1.csv"
        reserved.parent.mkdir(parents=True)
        path.rename(reserved)
        path.symlink_to(reserved)
        with patch.object(candidate, "sha", side_effect=AssertionError("dataset opened")):
            with self.assertRaisesRegex(ValueError, "Reserved path"):
                self.run_candidate()

    def test_unmapped_label_fails_without_completion(self):
        path = self.add_source(label="Unexpected")
        before = candidate.sha(path)
        with self.assertRaisesRegex(ValueError, "Unmapped original"):
            self.run_candidate()
        output = self.root / "reports/development-preparation/candidate"
        self.assertTrue((output / "FAILED.json").is_file())
        self.assertFalse((output / "COMPLETE.json").exists())
        self.assertEqual(candidate.sha(path), before)

    def test_missing_or_duplicate_metadata_fails(self):
        for index, header in enumerate([list(candidate.FIELDS[:-1]) + ["other", "numeric"],
                                        list(candidate.FIELDS) + ["label"]]):
            self.add_source(header=header)
            # Keep only the latest overwritten source entry.
            self.proposal["files"] = self.proposal["files"][-1:]
            with self.assertRaisesRegex(ValueError, "metadata header"):
                self.run_candidate(f"header-{index}")

    def test_source_hash_mismatch_fails(self):
        path = self.add_source()
        path.write_text(path.read_text() + "changed\n")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            self.run_candidate()

    def test_file_order_does_not_change_assignment_digest(self):
        self.add_source(1)
        self.add_source(2)
        first = self.run_candidate("first")
        self.proposal["files"].reverse()
        second = self.run_candidate("second")
        self.assertEqual(first["assignment_sha256"], second["assignment_sha256"])
        self.assertEqual(first["rows_by_role"], second["rows_by_role"])

    def test_small_role_support_is_reported_not_declared_frozen(self):
        self.add_source()
        self.policy["minimum_rows_per_client_role"] = 1000
        result = self.run_candidate()
        self.assertFalse(result["support_checks"]["total_row_minimum_passed"])
        self.assertEqual(len(result["support_checks"]["issues"]), 3)
        self.assertEqual(result["status"], "candidate_not_frozen")

    def test_overwrite_refusal_preserves_completed_evidence(self):
        self.add_source()
        self.run_candidate()
        complete = self.root / "reports/development-preparation/candidate/COMPLETE.json"
        before = complete.read_bytes()
        with self.assertRaises(FileExistsError):
            self.run_candidate()
        self.assertEqual(complete.read_bytes(), before)

    def test_observer_identity_and_duplicate_alias_cannot_change_ownership(self):
        self.add_source()
        self.proposal["files"][0]["client_id"] = 2
        with self.assertRaisesRegex(ValueError, "observer ID"):
            self.run_candidate()
        self.proposal["files"][0]["client_id"] = 1
        self.proposal["files"].append(copy.deepcopy(self.proposal["files"][0]))
        with self.assertRaisesRegex(ValueError, "Duplicate source"):
            self.run_candidate()


if __name__ == "__main__":
    unittest.main()
