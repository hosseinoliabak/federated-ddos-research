from pathlib import Path
import sys
import unittest

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from audit_feature_validity import (
    add_profile,
    one_feature_checks,
    rate_consistency,
    approved_sources,
    score,
)


class FeatureValidity(unittest.TestCase):
    def test_extrema_are_numeric_and_chunk_independent(self):
        data = pd.DataFrame({"label": ["Normal"] * 4, "flow_duration": ["2", "100", "-3", "nan"]})
        full, chunks = {}, {}
        add_profile(full, data)
        add_profile(chunks, data.iloc[:2])
        add_profile(chunks, data.iloc[2:])
        self.assertEqual(full, chunks)
        self.assertEqual(full[("Normal", "flow_duration")]["minimum"], -3)
        self.assertEqual(full[("Normal", "flow_duration")]["maximum"], 100)
        self.assertEqual(full[("Normal", "flow_duration")]["nonfinite"], 1)

    def test_validation_cannot_choose_threshold(self):
        data = pd.DataFrame(
            dict(
                flow_duration=[0, 2, 8, 10, 3, 9],
                label=["Normal", "Normal", "DDoS-tcp", "DDoS-tcp", "Normal", "DDoS-tcp"],
                _role=["fit"] * 4 + ["validation"] * 2,
                _group_id=list("abcdef"),
            )
        )
        first = one_feature_checks(data)[0]
        data.loc[4:, "flow_duration"] = [10000, -10000]
        data.loc[4:, "label"] = ["DDoS-tcp", "Normal"]
        second = one_feature_checks(data)[0]
        self.assertEqual(first["threshold"], 5)
        self.assertEqual(first["threshold"], second["threshold"])
        self.assertEqual(first["fit"], second["fit"])
        data.loc[5, "_group_id"] = "a"
        with self.assertRaisesRegex(ValueError, "crosses roles"):
            one_feature_checks(data)

    def test_rate_zero_duration_is_not_unit_evidence(self):
        frame = pd.DataFrame(
            dict(
                flow_duration=[10, 0, 10],
                flow_pkts_s=[200000, 0, 1],
                tot_fwd_pkts=[1, 1, 1],
                tot_bwd_pkts=[1, 0, 1],
            )
        )
        result = rate_consistency(frame)
        self.assertEqual(result["eligible_rows"], 2)
        self.assertEqual(result["matching_factor_1e6"], 1)
        self.assertEqual(result["nonmatching_rows"], 1)
        self.assertEqual(result["zero_duration_zero_rate_rows"], 1)

    def test_single_class_average_precision_is_not_reported(self):
        for target in (np.array([1, 1]), np.array([0, 0])):
            result = score(target, np.array([0, 1]), np.array([0.2, 0.8]))
            self.assertIsNone(result["average_precision"])
        attacks = score(np.array([1, 1]), np.array([0, 1]), np.array([0.2, 0.8]))
        self.assertEqual(attacks["recall"], 0.5)
        self.assertIsNone(attacks["false_positive_rate"])
        mixed = score(np.array([0, 1]), np.array([0, 1]), np.array([0.2, 0.8]))
        self.assertEqual(mixed["average_precision"], 1.0)

    def test_reserved_path_rejected_even_if_mislabelled_development(self):
        files = [
            dict(
                dataset="flnet2023",
                source_role="development",
                path=f"datasets/flnet2023/extracted/Normal/Dataset-{i}.csv",
            )
            for i in range(14)
        ]
        files[-1]["path"] = "datasets/flnet2023/extracted/TEST/Dataset-1.csv"
        with self.assertRaisesRegex(ValueError, "allowlist"):
            approved_sources({"files": files})


if __name__ == "__main__":
    unittest.main()
