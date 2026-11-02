"""Bounded benign-only engineering pilot; never a final evaluation procedure.

The CLI requires an explicit execution flag. Importing this module and running its
synthetic unit tests do not read a dataset or train on real observations.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.metadata
import json
import platform
import re
import resource
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch import nn


VERSION = "new-source-benign-engineering-v2"
APPROVED_SELECTED_SHA256 = "e0d3812373cc304448e62aef23f3cf8c5dea2db35faf0b39e183768b310552ea"
TARGETS = (1, 5, 9, 10)
EXCLUDED = (
    "src_ip", "dst_ip", "src_port", "dst_port", "protocol", "timestamp",
    "label", "flow_iat_min", "fwd_iat_min", "bwd_iat_min",
)
METADATA = ("_source_path", "_source_row", "_client_id", "_group_id", "_role")
LIMITS = [
    "engineering_only_no_RQ_answer_or_novelty_claim",
    "previously_used_development_sample_not_untouched_final_data",
    "stored_date_determines_class_in_retained_release",
    "target_ID_and_attack_family_are_confounded",
    "candidate_key_separation_does_not_establish_independent_episodes",
    "feature_interface_provisional_physical_semantics_unverified",
    "5_percent_target_is_arbitrary_software_test_not_registered_operational_target",
    "attack_and_benign_probes_are_from_different_later_dates",
    "chronology_assumes_stored_ISO_timestamps_order_observations_clocks_unverified",
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path: Path, value) -> None:
    """Replace one run artifact atomically; preserve the old file on write failure."""
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
        temporary.replace(path)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass  # Do not mask the original write failure with a cleanup failure.


def validate_labels_and_control(frame: pd.DataFrame) -> None:
    """Reject ambiguous labels and an absent required control before any split."""
    if "label" not in frame or frame["label"].isna().any():
        raise ValueError("Labels must be present and nonmissing; no relabeling is permitted")
    if not frame["label"].map(lambda value: isinstance(value, str) and bool(value.strip())).all():
        raise ValueError("Labels must be nonblank strings; no relabeling is permitted")
    if "tot_fwd_pkts" not in frame:
        raise ValueError("Required packet-count control column tot_fwd_pkts is missing")


def target_role_accounting(target: pd.DataFrame, history: pd.DataFrame, parts: dict):
    """Account for every target row without assigning new learning roles."""
    identity = ["_source_path", "_source_row"]
    if target[identity].isna().any().any() or target.duplicated(identity).any():
        raise ValueError("Target row identities must be nonmissing and unique")

    def keys(rows):
        return set(rows[identity].itertuples(index=False, name=None))

    target_keys = keys(target)
    assigned = set()
    for rows in parts.values():
        current = keys(rows)
        if not current <= target_keys or assigned & current:
            raise ValueError("Invalid or duplicate target role assignment")
        assigned.update(current)
    history_keys = keys(history)
    discarded_keys = history_keys - keys(parts["target_fit"]) - keys(parts["target_calibration"])
    if assigned & discarded_keys:
        raise ValueError("Discarded target rows overlap assigned roles")
    unassigned_keys = target_keys - assigned - discarded_keys
    indices = pd.MultiIndex.from_frame(target[identity])
    discarded = target[indices.isin(discarded_keys)].copy()
    unassigned = target[indices.isin(unassigned_keys)].copy()

    def strata(rows):
        if rows.empty:
            return []
        grouped = rows.assign(stored_date=_times(rows).dt.strftime("%Y-%m-%d"))
        return [
            {"stored_date": date, "label": label, "rows": len(group),
             "candidate_groups": int(group["_group_id"].nunique())}
            for (date, label), group in grouped.groupby(["stored_date", "label"], dropna=False, sort=True)
        ]

    accounted = {**parts, "discarded_straddling": discarded, "unassigned": unassigned}
    counts = {name: {"rows": len(rows), "candidate_groups": int(rows["_group_id"].nunique()),
                     "by_stored_date_label": strata(rows)} for name, rows in accounted.items()}
    if sum(entry["rows"] for entry in counts.values()) != len(target):
        raise ValueError("Target row accounting is incomplete")
    return {"total_target_rows": len(target), "all_rows_accounted_for": True,
            "group_counts_are_distinct_within_each_role_not_additive": True,
            "roles": counts}, discarded, unassigned


def donor_shuffle_seed(seed: int, target: int, round_id: int, dense_rank: int) -> int:
    """Derive deterministic shuffle state from a tuple, not sparse client-ID offsets."""
    return int(np.random.SeedSequence([seed, target, round_id, dense_rank]).generate_state(1, dtype=np.uint64)[0])


def finalize_run(output: Path, record: dict) -> dict:
    """Write the summary and seal; retain a failed summary if sealing fails."""
    try:
        write_json(output / "summary.json", record)
        artifacts = {str(p.relative_to(output)): sha256(p) for p in sorted(output.rglob("*"))
                     if p.is_file() and p.name != "artifact-manifest.json"}
        write_json(output / "artifact-manifest.json", artifacts)
    except Exception as exc:
        record["status"] = "failed"
        record["failures"].append({"stage": "finalization", "exception": type(exc).__name__, "message": str(exc)})
        # If this also fails (e.g. an unwritable filesystem), propagate to the
        # execution wrapper, which must preserve stderr and a nonzero exit.
        write_json(output / "summary.json", record)
    return record


def guard_development_path(workspace: Path, relative_path: str) -> Path:
    """Validate provenance only; never open raw CSVs."""
    relative = Path(relative_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("A relative development path without traversal is required")
    if len(relative.parts) != 5 or relative.parts[:3] != (
        "datasets", "flnet2023", "extracted"
    ) or relative.parts[3] not in {"Normal", "DDoS"} or relative.suffix != ".csv":
        raise ValueError("Only FLNET Normal/DDoS development CSV provenance is allowed")
    root = workspace.resolve()
    resolved = (root / relative).resolve()
    if not resolved.is_relative_to(root / "datasets" / "flnet2023" / "extracted" / relative.parts[3]):
        raise ValueError("Resolved provenance path escaped the development folder")
    return resolved


def _times(frame: pd.DataFrame) -> pd.Series:
    try:
        result = pd.to_datetime(frame["timestamp"], format="ISO8601", errors="raise")
    except Exception as exc:
        raise ValueError("Invalid stored timestamp") from exc
    if result.isna().any():
        raise ValueError("Missing stored timestamp")
    return result


def validate_training_rows(frame: pd.DataFrame) -> None:
    if frame.empty or not frame["label"].eq("Normal").all():
        raise ValueError("Fitting/calibration requires nonempty Normal observations only")
    if not _times(frame).dt.strftime("%Y-%m-%d").eq("2023-05-11").all():
        raise ValueError("Fitting/calibration requires the early stored date May 11")


def chronological_history(frame: pd.DataFrame, fit_fraction: float = 0.5):
    validate_training_rows(frame)
    if not 0 < fit_fraction < 1:
        raise ValueError("fit_fraction must lie strictly between zero and one")
    stamps = _times(frame)
    unique = stamps.drop_duplicates().sort_values()
    if len(unique) < 2:
        raise ValueError("At least two distinct timestamp blocks are required")
    position = min(len(unique) - 2, max(0, int(len(unique) * fit_fraction) - 1))
    cutoff = unique.iloc[position]
    grouped = pd.DataFrame({"group": frame["_group_id"], "time": stamps}).groupby("group")["time"].agg(["min", "max"])
    fit_keys = set(grouped.index[grouped["max"] <= cutoff])
    cal_keys = set(grouped.index[grouped["min"] > cutoff])
    fit = frame[frame["_group_id"].isin(fit_keys)].copy()
    cal = frame[frame["_group_id"].isin(cal_keys)].copy()
    discarded = frame[~frame["_group_id"].isin(fit_keys | cal_keys)]
    if fit.empty or cal.empty or not (_times(fit).max() < _times(cal).min()):
        raise ValueError("Chronological group split leaves empty or unordered roles")
    return fit, cal, {
        "cutoff": cutoff.isoformat(), "rule": "midpoint_of_unique_timestamps",
        "fit_fraction_of_unique_times": fit_fraction,
        "discarded_straddling_rows": len(discarded),
        "discarded_straddling_groups": int(discarded["_group_id"].nunique()),
    }


def exclude_target_keys(frame: pd.DataFrame, target_id: int):
    keys = set(frame.loc[frame["_client_id"] == target_id, "_group_id"])
    if not keys:
        raise ValueError("Target has no candidate keys")
    other = frame[frame["_client_id"] != target_id]
    candidate_ids = set(int(x) for x in other["_client_id"].unique())
    early = _times(other).dt.strftime("%Y-%m-%d").eq("2023-05-11")
    donors = other[~other["_group_id"].isin(keys) & other["label"].eq("Normal") & early].copy()
    present = set(int(x) for x in donors["_client_id"].unique())
    if set(donors["_group_id"]) & keys:
        raise ValueError("Target candidate key reached donors")
    return donors, sorted(candidate_ids - present)


def fit_standardizer(values: np.ndarray) -> dict:
    x = np.asarray(values, dtype=np.float64)
    if x.ndim != 2 or not len(x) or not np.isfinite(x).all():
        raise ValueError("Scaler fitting requires a nonempty finite matrix")
    mean, scale = x.mean(axis=0), x.std(axis=0, ddof=0)
    scale[scale == 0] = 1.0
    if not np.isfinite(mean).all() or not np.isfinite(scale).all():
        raise ValueError("Nonfinite fitted scaling statistics")
    return {"mean": mean.tolist(), "scale": scale.tolist()}


def transform(values: np.ndarray, scaler: dict) -> np.ndarray:
    with np.errstate(over="ignore", invalid="ignore"):
        result = ((np.asarray(values, dtype=np.float64) - np.asarray(scaler["mean"])) / np.asarray(scaler["scale"])).astype(np.float32)
    if not np.isfinite(result).all():
        raise ValueError("Nonfinite standardized values; no imputation is permitted")
    return result


def weighted_average(states: list[dict], weights: list[int]) -> dict:
    if not states or len(states) != len(weights) or any(w <= 0 for w in weights):
        raise ValueError("FedAvg requires matching states and positive weights")
    if any(set(state) != set(states[0]) for state in states):
        raise ValueError("Model state names differ")
    total = float(sum(weights))
    answer = {}
    for name in states[0]:
        if any(state[name].shape != states[0][name].shape for state in states):
            raise ValueError("Model state shapes differ")
        value = sum(state[name].to(torch.float64) * (weight / total) for state, weight in zip(states, weights)).to(states[0][name].dtype)
        if not torch.isfinite(value).all():
            raise ValueError("Nonfinite aggregate")
        answer[name] = value
    return answer


def make_model(dimension: int) -> nn.Module:
    return nn.Sequential(nn.Linear(dimension, 16), nn.ReLU(), nn.Linear(16, dimension)).float()


def state_hash(state: dict) -> str:
    h = hashlib.sha256()
    for name, tensor in sorted(state.items()):
        h.update(name.encode())
        h.update(tensor.detach().cpu().contiguous().numpy().tobytes())
    return h.hexdigest()


def train_epochs(model: nn.Module, values: np.ndarray, epochs: int, seed: int):
    """The caller must validate fitting rows before constructing this matrix."""
    x = torch.from_numpy(values)
    optimizer = torch.optim.Adam(
        model.parameters(), lr=0.001, betas=(0.9, 0.999), eps=1e-8, weight_decay=0.0
    )
    generator = torch.Generator().manual_seed(seed)
    losses = []
    model.train()
    for _ in range(epochs):
        order = torch.randperm(len(x), generator=generator)
        total = 0.0
        for ids in order.split(256):
            batch = x[ids]
            optimizer.zero_grad(set_to_none=True)
            loss = torch.mean((model(batch) - batch) ** 2)
            if not torch.isfinite(loss):
                raise ValueError("Nonfinite fitting loss")
            loss.backward()
            optimizer.step()
            total += float(loss.detach()) * len(ids)
        if any(not torch.isfinite(p).all() for p in model.parameters()):
            raise ValueError("Nonfinite model parameter")
        losses.append(total / len(x))
    return losses


def scores(model: nn.Module, values: np.ndarray) -> np.ndarray:
    model.eval()
    result = []
    with torch.no_grad():
        for batch in torch.from_numpy(values).split(1024):
            predicted = model(batch)
            if not torch.isfinite(predicted).all():
                raise ValueError("Nonfinite prediction")
            result.append(torch.mean((predicted.to(torch.float64) - batch.to(torch.float64)) ** 2, dim=1).numpy())
    values = np.concatenate(result)
    if not np.isfinite(values).all():
        raise ValueError("Nonfinite reconstruction score")
    return values


def matrix(frame: pd.DataFrame, features: list[str]) -> np.ndarray:
    try:
        x = frame[features].apply(pd.to_numeric, errors="raise").to_numpy(dtype=np.float64)
    except Exception as exc:
        raise ValueError("Invalid provisional numeric feature") from exc
    if not len(x) or not np.isfinite(x).all():
        raise ValueError("Empty or nonfinite feature matrix")
    return x


def role_counts(frame: pd.DataFrame) -> dict:
    return {
        "rows": len(frame), "candidate_groups": int(frame["_group_id"].nunique()),
        "stored_timestamp_min": _times(frame).min().isoformat(),
        "stored_timestamp_max": _times(frame).max().isoformat(),
    }


def calibrate_threshold(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=np.float64)
    if values.ndim != 1 or not len(values) or not np.isfinite(values).all():
        raise ValueError("Threshold calibration requires nonempty finite scalar scores")
    return float(np.quantile(values, 0.95, method="higher"))


def _metric(target: int, method: str, role: str, score: np.ndarray, threshold: float, frame: pd.DataFrame, nominal: float | None):
    alerts = int(np.count_nonzero(score > threshold))
    return {
        "target_id": target, "method": method, "probe_role": role,
        "threshold": float(threshold), "alert_comparison": "strictly_greater_than",
        "nominal_FPR_software_target": nominal,
        "alerts": alerts, "denominator_rows": len(score),
        "observed_fraction": alerts / len(score),
        "metric_name": "attack_recall" if role == "attack_probe" else "benign_alert_fraction",
        "candidate_groups": int(frame["_group_id"].nunique()),
        "stored_dates": sorted(_times(frame).dt.strftime("%Y-%m-%d").unique()),
        "original_labels": sorted(frame["label"].unique()),
        "limitations": LIMITS,
    }


def run_target(frame: pd.DataFrame, features: list[str], target: int, seed: int, destination: Path):
    started = time.perf_counter()
    validate_labels_and_control(frame)
    target_rows = frame[frame["_client_id"] == target]
    dates = _times(target_rows).dt.strftime("%Y-%m-%d")
    history = target_rows[target_rows["label"].eq("Normal") & dates.eq("2023-05-11")]
    fit, cal, chronology = chronological_history(history)
    probes = {
        "attack_probe": target_rows[~target_rows["label"].eq("Normal") & dates.eq("2023-05-13")].copy(),
        "benign_probe": target_rows[target_rows["label"].eq("Normal") & dates.eq("2023-05-17")].copy(),
    }
    if any(part.empty for part in probes.values()):
        raise ValueError("A required later development probe is empty")
    donors, empty_donors = exclude_target_keys(frame, target)
    validate_training_rows(donors)
    validate_training_rows(fit)
    validate_training_rows(cal)
    parts = {"target_fit": fit, "target_calibration": cal, **probes}
    accounting, discarded, unassigned = target_role_accounting(target_rows, history, parts)
    for i, (left_name, left) in enumerate(parts.items()):
        for right_name, right in list(parts.items())[i + 1:]:
            if set(left["_group_id"]) & set(right["_group_id"]):
                raise ValueError(f"Candidate keys overlap {left_name} and {right_name}")
    if _times(donors).max() >= min(_times(p).min() for p in probes.values()):
        raise ValueError("Donor fitting does not precede both probes")
    destination.mkdir()
    provenance = []
    for name, rows in {"donor_fit": donors, **parts, "discarded_straddling": discarded, "unassigned": unassigned}.items():
        selected = rows[list(METADATA)].copy()
        selected["new_role"] = name
        provenance.append(selected)
    pd.concat(provenance).to_csv(destination / "role-provenance.csv", index=False)

    scaler_fl = fit_standardizer(matrix(donors, features))
    scaler_local = fit_standardizer(matrix(fit, features))
    write_json(destination / "scalers.json", {"federated": scaler_fl, "local": scaler_local})
    torch.manual_seed(seed + target)
    initial = make_model(len(features)).state_dict()
    initial = copy.deepcopy(initial)
    initial_digest = state_hash(initial)
    model_local, model_fl = make_model(len(features)), make_model(len(features))
    model_local.load_state_dict(initial)
    model_fl.load_state_dict(initial)
    if state_hash(model_local.state_dict()) != state_hash(model_fl.state_dict()):
        raise ValueError("Initialization differs between methods")
    progress = {"local_autoencoder": "not_started", "federated_autoencoder": "not_started"}
    progress["local_autoencoder"] = "training_started"
    write_json(destination / "training-progress.json", progress)
    local_started = time.perf_counter()
    local_losses = train_epochs(model_local, transform(matrix(fit, features), scaler_local), 3, seed + target)
    local_seconds = time.perf_counter() - local_started
    progress["local_autoencoder"] = "training_completed"
    progress["federated_autoencoder"] = "training_started"
    write_json(destination / "training-progress.json", progress)
    fl_started = time.perf_counter()
    rounds = []
    donor_parts = {int(k): v for k, v in donors.groupby("_client_id", sort=True)}
    for round_id in range(3):
        states, weights, logs = [], [], []
        broadcast = copy.deepcopy(model_fl.state_dict())
        for dense_rank, (client, rows) in enumerate(donor_parts.items()):
            validate_training_rows(rows)
            local = make_model(len(features))
            local.load_state_dict(broadcast)
            losses = train_epochs(local, transform(matrix(rows, features), scaler_fl), 1, donor_shuffle_seed(seed, target, round_id, dense_rank))
            states.append(copy.deepcopy(local.state_dict()))
            weights.append(len(rows))
            logs.append({"client_id": client, "dense_rank": dense_rank,
                         "shuffle_seed": donor_shuffle_seed(seed, target, round_id, dense_rank),
                         **role_counts(rows), "loss": losses[0]})
        model_fl.load_state_dict(weighted_average(states, weights))
        rounds.append({"round": round_id + 1, "clients": logs})
    fl_seconds = time.perf_counter() - fl_started
    progress["federated_autoencoder"] = "training_completed"
    write_json(destination / "training-progress.json", progress)
    metrics = []
    for name, model, scaler in [("local_autoencoder", model_local, scaler_local), ("federated_autoencoder", model_fl, scaler_fl)]:
        cal_scores = scores(model, transform(matrix(cal, features), scaler))
        threshold = calibrate_threshold(cal_scores)
        metrics.append(_metric(target, name, "target_calibration", cal_scores, threshold, cal, 0.05))
        for role, rows in probes.items():
            probe_scores = scores(model, transform(matrix(rows, features), scaler))
            metrics.append(_metric(target, name, role, probe_scores, threshold, rows, 0.05))
        np.savez_compressed(destination / f"{name}-weights.npz", **{k: v.detach().numpy() for k, v in model.state_dict().items()})
    control = {
        "predictor": "tot_fwd_pkts", "diagnostics_not_fitted_detectors": True,
        "historical_rule": {"method": "prior_exploratory_forward_packet_count_control", "threshold": 2.5, "nominal_FPR_software_target": None},
        "calibrated_score": {"method": "calibrated_forward_packet_count_score", "nominal_FPR_software_target": 0.05},
    }
    count_threshold = calibrate_threshold(matrix(cal, ["tot_fwd_pkts"])[:, 0])
    control["calibrated_score"]["threshold"] = count_threshold
    for role, rows in {"target_calibration": cal, **probes}.items():
        count_scores = matrix(rows, ["tot_fwd_pkts"])[:, 0]
        metrics.append(_metric(target, control["historical_rule"]["method"], role, count_scores, 2.5, rows, None))
        metrics.append(_metric(target, control["calibrated_score"]["method"], role, count_scores, count_threshold, rows, 0.05))
    control["status"] = "available_two_descriptive_controls_fixed_rule_has_different_operating_point"
    expected_pairs = {(method, role) for method in (
        "local_autoencoder", "federated_autoencoder", control["historical_rule"]["method"],
        control["calibrated_score"]["method"])
        for role in ("target_calibration", "attack_probe", "benign_probe")}
    actual_pairs = {(metric["method"], metric["probe_role"]) for metric in metrics}
    if actual_pairs != expected_pairs or len(metrics) != len(expected_pairs):
        raise ValueError("Required model/control metrics are incomplete or duplicated")
    record = {
        "target_id": target, "status": "completed_engineering_only", "limitations": LIMITS,
        "chronology": chronology, "target_row_accounting": accounting, "roles": {k: role_counts(v) for k, v in parts.items()},
        "donor_fit": role_counts(donors),
        "donors": [{"client_id": k, **role_counts(v)} for k, v in donor_parts.items()],
        "excluded_empty_donor_ids": empty_donors,
        "initial_state_sha256": initial_digest, "same_initial_weights": True,
        "local_epoch_losses": local_losses, "federated_rounds": rounds,
        "local_training_seconds": local_seconds, "federated_training_seconds": fl_seconds,
        "total_target_seconds": time.perf_counter() - started,
        "trivial_control": control, "metrics": metrics,
    }
    write_json(destination / "result.json", record)
    return record


def execute(workspace: Path, run_id: str, seed: int = 20261101):
    execution_started = time.perf_counter()
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", run_id):
        raise ValueError("run_id must be a simple lowercase versioned identifier")
    workspace = workspace.resolve()
    output = workspace / "runs" / run_id
    if output.exists():
        raise ValueError("Refusing to overwrite an existing run")
    source = workspace / "runs" / "engineering-smoke-v1" / "selected-records.parquet"
    preparation_path = source.parent / "preparation.json"
    preparation = json.loads(preparation_path.read_text())
    digest = sha256(source)
    if digest != APPROVED_SELECTED_SHA256 or digest != preparation["files"]["selected-records.parquet"]:
        raise ValueError("Historical selected-data hash mismatch")
    provenance = pd.read_parquet(source, columns=list(METADATA), engine="pyarrow")
    if len(provenance) != preparation["selected_rows"]:
        raise ValueError("Historical selected-row count mismatch")
    if set(EXCLUDED) != set(preparation["excluded_predictors"]):
        raise ValueError("Historical exclusion contract changed")
    for path in provenance["_source_path"].unique():
        guard_development_path(workspace, str(path))
    if provenance.isna().any().any() or provenance.duplicated(["_source_path", "_source_row"]).any():
        raise ValueError("Invalid or duplicate source-row provenance")
    frame = pd.read_parquet(source, engine="pyarrow")
    validate_labels_and_control(frame)
    features = [name for name in frame.columns if name not in EXCLUDED and name not in METADATA]
    if len(features) != preparation["feature_count"]:
        raise ValueError("Unexpected provisional feature count")
    # Validate the complete selected schema before constructing any model.
    matrix(frame, features)
    output.mkdir(parents=True)
    started = time.perf_counter()
    torch.set_num_threads(2)
    torch.use_deterministic_algorithms(True)
    np.random.seed(seed)
    config = {
        "version": VERSION, "purpose": "engineering_only", "targets": TARGETS,
        "approved_selected_sha256": APPROVED_SELECTED_SHA256,
        "seed": seed, "device": "cpu", "torch_threads": 2,
        "deterministic_algorithms": True, "architecture": [len(features), 16, len(features)],
        "hidden_activation": "ReLU", "loss": "mean_squared_reconstruction_error",
        "optimizer": "Adam", "learning_rate": 0.001, "batch_size": 256,
        "adam_betas": [0.9, 0.999], "adam_epsilon": 1e-8, "weight_decay": 0.0,
        "model_dtype": "float32", "reconstruction_score_arithmetic": "float64",
        "federated_rounds": 3, "local_epochs_per_federated_round": 1,
        "federated_optimizer_state": "reset_for_each_client_each_round",
        "donor_shuffle_seed": "numpy_SeedSequence_base_target_zero_based_round_dense_donor_rank",
        "local_baseline_epochs": 3, "local_baseline_optimizer_state": "carry_across_three_epochs",
        "aggregation": "donor_fit_row_count_weighted_parameter_average",
        "federated_scaler": "pooled_donor_fit_only_engineering_reference_not_private_protocol",
        "local_scaler": "target_local_fit_only", "target_CAL_rows_shared_across_methods": True,
        "threshold": "empirical_95th_percentile_numpy_higher_strict_greater_alert",
        "threshold_is_arbitrary_software_test": True,
        "stored_timestamp_assumption": "Use strict ISO strings as ordered observations; clocks, physical units, capture independence, and exact release extractor provenance remain unverified. Fail when target fit cannot strictly precede CAL.",
        "predictor_validation_scope": "Raw-value schema and finite numeric representation only, not physical measurement validity",
        "features": features, "excluded_predictors": EXCLUDED,
        "limitations": LIMITS,
    }
    records, failures = [], []
    environment = {"python": sys.version, "platform": platform.platform()}
    stage = "configuration"
    try:
        write_json(output / "config.json", config)
        stage = "dependency_metadata"
        for name in ("torch", "numpy", "pandas", "pyarrow"):
            environment[name] = importlib.metadata.version(name)
        stage = "targets"
        for target in TARGETS:
            try:
                records.append(run_target(frame, features, target, seed, output / f"target-{target}"))
            except Exception as exc:
                failures.append({"target_id": target, "stage": "target", "exception": type(exc).__name__, "message": str(exc), "limitations": LIMITS})
    except Exception as exc:
        failures.append({"stage": stage, "exception": type(exc).__name__, "message": str(exc)})

    def checked_hash(path):
        try:
            return sha256(path)
        except Exception as exc:
            failures.append({"stage": "final_metadata", "artifact": path.name,
                             "exception": type(exc).__name__, "message": str(exc)})
            return None

    unchanged = checked_hash(source) == digest
    if not unchanged:
        failures.append({"exception": "SourceMutation", "message": "Selected input hash changed or could not be verified"})
    usage = resource.getrusage(resource.RUSAGE_SELF)
    peak_bytes = usage.ru_maxrss if sys.platform == "darwin" else usage.ru_maxrss * 1024
    progress_records = []
    for path in output.glob("target-*/training-progress.json"):
        try:
            progress_records.append(json.loads(path.read_text()))
        except Exception as exc:
            failures.append({"stage": "training_progress_read", "artifact": str(path.relative_to(output)),
                             "exception": type(exc).__name__, "message": str(exc)})
    preparation_digest = checked_hash(preparation_path)
    script_digest = checked_hash(Path(__file__))
    config_digest = checked_hash(output / "config.json")
    record = {
        "version": VERSION, "status": "completed_engineering_only" if not failures else "failed",
        "source_relative_path": str(source.relative_to(workspace)), "source_sha256": digest,
        "source_unchanged": unchanged, "preparation_sha256": preparation_digest,
        "executed_script_sha256": script_digest, "config_sha256": config_digest,
        "environment": environment,
        "total_execution_seconds_after_input_validation": time.perf_counter() - started,
        "total_execution_seconds_including_input_validation": time.perf_counter() - execution_started,
        "peak_process_resident_bytes": peak_bytes,
        "memory_scope": "process_high_water_mark_includes_input_loading_and_all_targets",
        "successful_targets": len(records), "planned_trained_method_count": len(TARGETS) * 2,
        "training_started_method_count": sum(status != "not_started" for part in progress_records for status in part.values()),
        "training_completed_method_count": sum(status == "training_completed" for part in progress_records for status in part.values()),
        "completed_autoencoder_method_target_pairs": len(records) * 2,
        "completed_descriptive_control_target_pairs": sum(
            len({metric["method"] for metric in part["metrics"] if metric["method"] not in {
                "local_autoencoder", "federated_autoencoder"
            }}) for part in records
        ),
        "failures": failures,
        "raw_csv_files_opened": False, "reserved_test_opened": False,
        "limitations": LIMITS, "target_results": records,
    }
    return output, finalize_run(output, record)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--seed", type=int, default=20261101)
    parser.add_argument("--execute-development-pilot", action="store_true")
    args = parser.parse_args()
    if not args.execute_development_pilot:
        parser.error("Explicit --execute-development-pilot is required after protocol review")
    output, record = execute(args.workspace, args.run_id, args.seed)
    print(json.dumps({"output": str(output), "status": record["status"], "failures": record["failures"]}, indent=2))
    return 0 if not record["failures"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
