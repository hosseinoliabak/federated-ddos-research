from pathlib import Path
import os
import sys
import tempfile
import unittest
import json
from unittest.mock import patch
import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from research_workspace import contained_path, workspace_root
from engineering_pilot import connection_key, group_choice, weighted_average, fit_scaler
import engineering_pilot as pilot


class ResearchInvariants(unittest.TestCase):
    def test_unmapped_labels_stop_before_sampling(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "config").mkdir()
            (root / "config/split-proposal.json").write_text(
                json.dumps(
                    {"unmapped_development_labels": {"flnet2023": ["UnknownAttack"]}, "files": []}
                )
            )
            with patch.object(pilot, "ROOT", root):
                with self.assertRaisesRegex(ValueError, "Unmapped FLNET"):
                    pilot.prepare(root / "out")

    def test_direction_does_not_change_group(self):
        a = connection_key("a", "b", 10, 20, 2048)
        self.assertEqual(a, connection_key("b", "a", 20, 10, 2048))
        self.assertNotEqual(a, connection_key("a", "b", 20, 10, 2048))
        self.assertEqual(group_choice(a), group_choice(a))

    def test_unequal_client_aggregation_and_permutation(self):
        states = [{"w": torch.tensor([1.0, 3.0])}, {"w": torch.tensor([5.0, 7.0])}]
        expected = torch.tensor([4.0, 6.0])
        self.assertTrue(torch.equal(weighted_average(states, [1, 3])["w"], expected))
        self.assertTrue(torch.equal(weighted_average(states[::-1], [3, 1])["w"], expected))
        with self.assertRaises(ValueError):
            weighted_average(states, [0, 1])

    def test_scaler_handles_constant_feature(self):
        mean, scale = fit_scaler(np.array([[1.0, 4.0], [3.0, 4.0]]))
        np.testing.assert_array_equal(mean, [2.0, 4.0])
        np.testing.assert_array_equal(scale, [1.0, 1.0])

    def test_workspace_override_and_path_escape(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            with patch.dict(os.environ, {"FDDOS_WORKSPACE": str(root)}):
                self.assertEqual(workspace_root(), root)
            self.assertEqual(contained_path(root, "datasets/a.csv"), root / "datasets/a.csv")
            for relative in ["../outside", "/tmp/outside", "x/../../outside", "x\\outside"]:
                with self.assertRaises(ValueError):
                    contained_path(root, relative)
            (root / "link").symlink_to(root.parent, target_is_directory=True)
            with self.assertRaises(ValueError):
                contained_path(root, "link/outside")


if __name__ == "__main__":
    unittest.main()
