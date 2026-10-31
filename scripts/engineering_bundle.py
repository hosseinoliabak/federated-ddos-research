"""Export and load a bounded, offline-only MLP bundle from a completed engineering run.

This is not a packet extractor, live detector service, or validated deployment.
Only load bundles obtained from your own trusted run. Hashes detect changes;
they do not authenticate an unknown publisher.
"""

from pathlib import Path
from collections.abc import Mapping
import argparse
import hashlib
import json
import re

import numpy as np
import torch

from research_workspace import contained_path, workspace_root

VERSION = "engineering-bundle-v1"


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_json(path):
    if path.stat().st_size > 262144:
        raise ValueError("Oversized metadata")
    return json.loads(path.read_text())


def validate_metadata(meta):
    if meta.get("version") != VERSION or meta.get("use") != "offline_engineering_only":
        raise ValueError("Unsupported bundle scope or version")
    if meta.get("architecture") != "linear_relu_linear_binary_v1":
        raise ValueError("Unsupported architecture")
    features = meta.get("features")
    if not isinstance(features, list) or not 1 <= len(features) <= 256:
        raise ValueError("Invalid feature count")
    if any(
        not isinstance(n, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,79}", n) for n in features
    ):
        raise ValueError("Invalid feature names")
    if len(set(features)) != len(features):
        raise ValueError("Duplicate feature names")
    hidden = meta.get("hidden_units")
    if type(hidden) is not int or not 1 <= hidden <= 512:
        raise ValueError("Invalid hidden width")
    threshold = meta.get("threshold")
    if type(threshold) not in (int, float) or not np.isfinite(threshold) or not 0 < threshold < 1:
        raise ValueError("Invalid threshold")
    if meta.get("classes") != {"0": "Normal", "1": "DDoS"}:
        raise ValueError("Unsupported class mapping")
    mean = np.asarray(meta.get("mean"), dtype=np.float64)
    scale = np.asarray(meta.get("scale"), dtype=np.float64)
    if mean.shape != (len(features),) or scale.shape != mean.shape:
        raise ValueError("Invalid scaler dimensions")
    if not np.isfinite(mean).all() or not np.isfinite(scale).all() or (scale <= 0).any():
        raise ValueError("Invalid scaler values")
    return mean, scale


def make_model(meta):
    validate_metadata(meta)
    return torch.nn.Sequential(
        torch.nn.Linear(len(meta["features"]), meta["hidden_units"]),
        torch.nn.ReLU(),
        torch.nn.Linear(meta["hidden_units"], 1),
    )


def read_state(path, model):
    if path.stat().st_size > 8 * 1024 * 1024:
        raise ValueError("Oversized weights")
    state = torch.load(path, map_location="cpu", weights_only=True)
    if not isinstance(state, dict) or set(state) != set(model.state_dict()):
        raise ValueError("Unexpected weight keys")
    for key, expected in model.state_dict().items():
        value = state[key]
        if (
            not isinstance(value, torch.Tensor)
            or value.dtype != torch.float32
            or value.shape != expected.shape
        ):
            raise ValueError("Unexpected weight shape or dtype")
        if not torch.isfinite(value).all():
            raise ValueError("Nonfinite weights")
    model.load_state_dict(state, strict=True)
    return model.eval()


def load_bundle(directory):
    directory = Path(directory).resolve(strict=True)
    manifest = read_json(directory / "MANIFEST.json")
    if manifest.get("version") != VERSION or set(manifest.get("files", {})) != {
        "model.pt",
        "metadata.json",
    }:
        raise ValueError("Unexpected manifest")
    for name, sha in manifest["files"].items():
        path = directory / name
        limit = 262144 if name == "metadata.json" else 8 * 1024 * 1024
        if (
            path.is_symlink()
            or not path.is_file()
            or path.stat().st_size > limit
            or digest(path) != sha
        ):
            raise ValueError("Bundle integrity mismatch")
    meta = read_json(directory / "metadata.json")
    model = read_state(directory / "model.pt", make_model(meta))
    return meta, model


def select_features(meta, records):
    """Project bounded named flow records to the recorded inputs, without imputation.

    Extra fields are deliberately ignored. This name mapping does not verify
    extractor units or semantics and cannot turn packets into flow features.
    """
    validate_metadata(meta)
    if not isinstance(records, (list, tuple)) or not 1 <= len(records) <= 10000:
        raise ValueError("Use a bounded list of flow records")
    names = meta["features"]
    if any(
        not isinstance(row, Mapping) or any(name not in row for name in names) for row in records
    ):
        raise ValueError("Missing required named features")
    return np.asarray([[row[name] for name in names] for row in records], dtype=np.float64)


def predict(meta, model, values, feature_names):
    mean, scale = validate_metadata(meta)
    if list(feature_names) != meta["features"]:
        raise ValueError("Feature names or order differ from the training contract")
    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 2 or array.shape[1] != len(mean) or not 1 <= len(array) <= 10000:
        raise ValueError("Use a bounded batch with the exact feature width")
    if not np.isfinite(array).all():
        raise ValueError("Nonfinite inputs")
    with np.errstate(over="ignore", invalid="ignore"):
        scaled = ((array - mean) / scale).astype(np.float32)
    if not np.isfinite(scaled).all():
        raise ValueError("Nonfinite standardized inputs")
    if next(model.parameters()).device.type != "cpu":
        raise ValueError("This portable inference reference requires CPU weights")
    with torch.inference_mode():
        logits = model(torch.from_numpy(scaled))
        if not torch.isfinite(logits).all():
            raise ValueError("Nonfinite logits")
        probabilities = torch.sigmoid(logits).squeeze(1).numpy()
    if not np.isfinite(probabilities).all():
        raise ValueError("Nonfinite predictions")
    return probabilities, probabilities >= meta["threshold"]


def export_bundle(run, out, optimizer):
    run, out = Path(run), Path(out)
    if optimizer not in ("sgd", "adam"):
        raise ValueError("Select SGD or Adam")
    if out.exists():
        raise FileExistsError("Preserve completed or partial bundles; choose a new version")
    complete = read_json(run / "COMPLETE.json")
    if complete.get("status") != "complete":
        raise ValueError("Incomplete source run")
    for name in ("config.json", "scaler.json", "training.json"):
        if digest(run / name) != complete["files"][name]:
            raise ValueError("Source run integrity mismatch")
    config = read_json(run / "config.json")
    scaler = read_json(run / "scaler.json")
    training = read_json(run / "training.json")
    if (
        config.get("purpose") != "engineering_only_not_confirmatory"
        or training.get("config") != config
    ):
        raise ValueError("Not a matching engineering configuration")
    rounds = config.get("rounds")
    if type(rounds) is not int or not 1 <= rounds <= 1000:
        raise ValueError("Invalid completed round count")
    weight_name = f"{optimizer}-round{rounds}.pt"
    if digest(run / weight_name) != complete["files"][weight_name]:
        raise ValueError("Source checkpoint integrity mismatch")
    meta = dict(
        version=VERSION,
        use="offline_engineering_only",
        architecture="linear_relu_linear_binary_v1",
        features=scaler["features"],
        mean=scaler["mean"],
        scale=scaler["scale"],
        hidden_units=config["hidden_units"],
        threshold=config["threshold"],
        classes={"0": "Normal", "1": "DDoS"},
        optimizer=optimizer,
        extractor_identity="unverified_flnet_release",
        scaler_scope=scaler["scope"],
        source=dict(
            run=run.name,
            complete_sha256=digest(run / "COMPLETE.json"),
            training_sha256=digest(run / "training.json"),
            training_script_sha256=training["script_sha256"],
            checkpoint_sha256=digest(run / weight_name),
        ),
        limits=[
            "Not calibrated for operational traffic",
            "No live packet or flow input adapter",
            "No final test or deployment validation",
            "Historical CPU training; export does not retrain",
            "The pooled engineering scaler does not establish private federated preprocessing",
        ],
    )
    model = read_state(run / weight_name, make_model(meta))
    out.mkdir(parents=True, exist_ok=False)
    torch.save(model.state_dict(), out / "model.pt")
    (out / "metadata.json").write_text(json.dumps(meta, indent=2, allow_nan=False) + "\n")
    manifest = dict(
        version=VERSION,
        files={n: digest(out / n) for n in ("model.pt", "metadata.json")},
        exporter_sha256=digest(Path(__file__)),
    )
    (out / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")
    load_bundle(out)
    return meta


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", default="engineering-smoke-v1")
    parser.add_argument("--optimizer", choices=["sgd", "adam"], required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"engineering-smoke-v[0-9]+(?:-portable)?", args.run):
        raise ValueError("Use a named engineering run")
    root = workspace_root()
    output = contained_path(root, f"bundles/{args.run}-{args.optimizer}-v1")
    meta = export_bundle(contained_path(root, f"runs/{args.run}"), output, args.optimizer)
    print(
        json.dumps(
            dict(
                status="exported",
                use=meta["use"],
                path=str(output),
                features=len(meta["features"]),
                manifest_sha256=digest(output / "MANIFEST.json"),
            )
        )
    )


if __name__ == "__main__":
    main()
