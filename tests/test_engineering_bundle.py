from pathlib import Path
import hashlib
import json
import sys
import tempfile
import unittest

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from engineering_bundle import (
    VERSION,
    export_bundle,
    load_bundle,
    make_model,
    predict,
    select_features,
)


class EngineeringBundle(unittest.TestCase):
    def fixture(self, root):
        run = root / "engineering-smoke-v1"
        run.mkdir()
        config = dict(
            purpose="engineering_only_not_confirmatory", rounds=3, hidden_units=1, threshold=0.5
        )
        scaler = dict(
            features=["first", "second"],
            mean=[1.0, 2.0],
            scale=[2.0, 4.0],
            scope="synthetic_fit_only",
        )
        meta = dict(
            version=VERSION,
            use="offline_engineering_only",
            architecture="linear_relu_linear_binary_v1",
            classes={"0": "Normal", "1": "DDoS"},
            hidden_units=1,
            threshold=0.5,
            **scaler,
        )
        model = make_model(meta)
        with torch.no_grad():
            model[0].weight.copy_(torch.tensor([[1.0, -1.0]]))
            model[0].bias.fill_(0)
            model[2].weight.fill_(2)
            model[2].bias.fill_(-1)
        torch.save(model.state_dict(), run / "sgd-round3.pt")
        for name, data in [
            ("config.json", config),
            ("scaler.json", scaler),
            ("training.json", dict(config=config, script_sha256="a" * 64)),
        ]:
            (run / name).write_text(json.dumps(data))
        files = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in run.iterdir()}
        (run / "COMPLETE.json").write_text(json.dumps(dict(status="complete", files=files)))
        return run

    def test_transfer_preserves_scaling_and_known_predictions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = self.fixture(root)
            out = root / "bundle"
            export_bundle(run, out, "sgd")
            meta, model = load_bundle(out)
            # Standardized rows are [0,0], [1,0], and [0,1]. Expected logits -1,1,-1.
            p, y = predict(meta, model, [[1, 2], [3, 2], [1, 6]], ["first", "second"])
            np.testing.assert_allclose(p, 1 / (1 + np.exp(-np.array([-1.0, 1.0, -1.0]))), rtol=1e-6)
            self.assertEqual(y.tolist(), [False, True, False])
            with self.assertRaises(FileExistsError):
                export_bundle(run, out, "sgd")

    def test_feature_contract_rejects_bad_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "bundle"
            export_bundle(self.fixture(root), out, "sgd")
            meta, model = load_bundle(out)
            for values, names in [
                ([[1, 2]], ["second", "first"]),
                ([[1]], ["first", "second"]),
                ([[np.nan, 2]], ["first", "second"]),
            ]:
                with self.assertRaises(ValueError):
                    predict(meta, model, values, names)
            meta["scale"][0] = 0
            with self.assertRaises(ValueError):
                predict(meta, model, [[1, 2]], ["first", "second"])

    def test_named_projection_and_overflow(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "bundle"
            export_bundle(self.fixture(root), out, "sgd")
            meta, model = load_bundle(out)
            values = select_features(
                meta, [{"second": 2, "label": "ignored", "first": 3, "src_ip": "ignored"}]
            )
            np.testing.assert_array_equal(values, [[3, 2]])
            p, _ = predict(meta, model, values, meta["features"])
            self.assertAlmostEqual(float(p[0]), 1 / (1 + np.exp(-1)), places=6)
            with self.assertRaisesRegex(ValueError, "Missing"):
                select_features(meta, [{"first": 3}])
            with torch.no_grad():
                model[0].weight.fill_(1e30)
            with self.assertRaisesRegex(ValueError, "logits"):
                predict(meta, model, [[1e30, 2]], meta["features"])

    def test_tamper_is_detected_before_inference(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "bundle"
            export_bundle(self.fixture(root), out, "sgd")
            (out / "model.pt").write_bytes(b"not trusted weights")
            with self.assertRaisesRegex(ValueError, "integrity"):
                load_bundle(out)

    def test_modified_source_is_not_exported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = self.fixture(root)
            out = root / "bundle"
            (run / "scaler.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "integrity"):
                export_bundle(run, out, "sgd")
            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
