"""AF-BKM-family candidate adaptation; synthetic verification, not replication.

Equations: Saleh & Azar (2026), doi:10.3390/iot7030067, §§4.1–4.4,
Algorithm 1. Compared with public source commit
8f6ac0f80bdc8d40ce2bd22227f6544facad0487 (MIT; licenses/AF-BKM-MIT.txt).
Copyright (c) 2026 Mohammed Al Saleh, Joseph Azar, Rima Shbaro.
See docs/afbkm-adapter.md for the source/adaptation map and access assumptions.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
import math
import re
from typing import Iterable

import numpy as np

VERSION = "afbkm-candidate-v1"
MAD_SCALE = 1.4826


class AdapterError(ValueError):
    """Explicit numerical or access-boundary failure; never a benign score."""
    def __init__(self, code: str, detail: str = ""):
        self.code = code
        super().__init__(code + (": " + detail if detail else ""))


def require(condition, code, detail=""):
    if not condition:
        raise AdapterError(code, detail)


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def digest(value) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def hex_id(value):
    require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value), "invalid_digest")


def name_id(value):
    require(isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", value), "invalid_identifier")


def integer(value, minimum=0):
    require(type(value) is int and value >= minimum, "invalid_integer")


def metadata_integer(value):
    require(isinstance(value, (int, np.integer)) and not isinstance(value, (bool, np.bool_)), "invalid_metadata_integer")
    result = int(value); integer(result); return result


def scalar(value, *, minimum=None):
    require(isinstance(value, (int, float, np.integer, np.floating))
            and not isinstance(value, (bool, np.bool_)), "invalid_scalar")
    result = float(value)
    require(math.isfinite(result), "nonfinite_scalar")
    require(minimum is None or result >= minimum, "scalar_out_of_range")
    return result


def numeric(value, ndim=None):
    try:
        raw = np.asarray(value)
    except (ValueError, TypeError, OverflowError) as exc:
        raise AdapterError("numeric_conversion", type(exc).__name__) from exc
    require(raw.dtype.kind in "fiu", "non_real_numeric_input")
    with np.errstate(over="raise", invalid="raise", divide="raise"):
        try:
            arr = np.asarray(raw, dtype="<f8", order="C")
        except (FloatingPointError, OverflowError, ValueError) as exc:
            raise AdapterError("numeric_conversion", str(exc)) from exc
    require(ndim is None or arr.ndim == ndim, "shape_mismatch")
    require(bool(np.isfinite(arr).all()), "nonfinite_input")
    return arr


@dataclass(frozen=True)
class FrozenArray:
    """Immutable bytes own the array; callers cannot re-enable writing."""
    shape: tuple[int, ...]
    data: bytes

    def __post_init__(self):
        require(type(self.shape) is tuple and 1 <= len(self.shape) <= 2, "shape_mismatch")
        for n in self.shape:
            integer(n)
        require(type(self.data) is bytes and len(self.data) == math.prod(self.shape) * 8, "array_storage_mismatch")
        require(bool(np.isfinite(self.array()).all()), "nonfinite_array")

    @classmethod
    def of(cls, value):
        arr = numeric(value)
        return cls(tuple(arr.shape), arr.tobytes(order="C"))

    def array(self):
        return np.frombuffer(self.data, dtype="<f8").reshape(self.shape)

    def values(self):
        return self.array().tolist()


@dataclass(frozen=True)
class Parameters:
    ridge: float
    mad_k: float
    blend: float
    trust_k: float

    def __post_init__(self):
        for key in ("ridge", "mad_k", "blend", "trust_k"):
            object.__setattr__(self, key, scalar(getattr(self, key), minimum=0))
        require(self.ridge > 0 and self.blend <= 1, "parameter_out_of_range")

    def payload(self):
        return {key: getattr(self, key) for key in ("ridge", "mad_k", "blend", "trust_k")}


@dataclass(frozen=True)
class TrainingScope:
    """Caller-approved source/role manifest. This is not remote attestation."""
    candidate_sha256: str
    assignment_sha256: str
    features: tuple[str, ...]
    sources: tuple[tuple[int, str], ...]
    train_role_id: int = 0

    def __post_init__(self):
        hex_id(self.candidate_sha256); hex_id(self.assignment_sha256)
        require(type(self.features) is tuple and len(self.features) > 0
                and all(isinstance(v, str) and 0 < len(v) <= 128 for v in self.features)
                and len(set(self.features)) == len(self.features), "invalid_feature_schema")
        require(type(self.sources) is tuple and len(self.sources) > 0, "invalid_source_manifest")
        ids = []
        for entry in self.sources:
            require(type(entry) is tuple and len(entry) == 2, "invalid_source_manifest")
            sid, sha = entry; integer(sid); hex_id(sha); ids.append(sid)
        require(len(set(ids)) == len(ids), "duplicate_source")
        integer(self.train_role_id)
        require(self.train_role_id == 0, "training_role_mapping_mismatch")

    @property
    def schema_id(self):
        return digest(list(self.features))

    @property
    def scope_id(self):
        return digest({"candidate": self.candidate_sha256, "assignment": self.assignment_sha256,
                       "schema": self.schema_id, "sources": self.sources, "train_role": self.train_role_id})


@dataclass(frozen=True)
class RowRef:
    source_id: int
    source_row: int
    observer_id: int
    role_id: int
    group_sha256: str

    def __post_init__(self):
        for key in ("source_id", "source_row", "observer_id", "role_id"):
            integer(getattr(self, key))
        hex_id(self.group_sha256)

    def payload(self):
        return [self.source_id, self.source_row, self.observer_id, self.role_id, self.group_sha256]


@dataclass(frozen=True)
class TrainingBatch:
    scope: TrainingScope
    observer_id: int
    refs: tuple[RowRef, ...]
    values: FrozenArray

    def __post_init__(self):
        require(isinstance(self.scope, TrainingScope) and isinstance(self.values, FrozenArray), "invalid_batch")
        integer(self.observer_id)
        require(type(self.refs) is tuple and all(isinstance(r, RowRef) for r in self.refs), "invalid_refs")
        require(self.values.shape == (len(self.refs), len(self.scope.features)), "shape_mismatch")
        allowed = dict(self.scope.sources); seen = set()
        for row in self.refs:
            require(row.role_id == self.scope.train_role_id, "non_training_update")
            require(row.observer_id == self.observer_id, "ownership_mismatch")
            require(row.source_id in allowed, "unapproved_source")
            identity = (row.source_id, row.source_row)
            require(identity not in seen, "duplicate_source_row"); seen.add(identity)

    @property
    def batch_id(self):
        return digest({"scope": self.scope.scope_id, "observer": self.observer_id,
                       "rows": [r.payload() for r in self.refs],
                       "features_sha256": hashlib.sha256(self.values.data).hexdigest()})


def training_batch(X, records, positions: Iterable[int], scope, observer_id) -> TrainingBatch:
    """Read whitelisted metadata first, then predictors. No label fields accessed.

    X and records may be the reviewed loader's sealed arrays. The caller must
    supply its verified scope. Selection never filters, shuffles, or remaps roles.
    """
    require(isinstance(scope, TrainingScope), "invalid_scope")
    require(len(X) == len(records), "record_feature_count_mismatch")
    indices = []; refs = []; allowed = dict(scope.sources)
    for pos in positions:
        integer(pos); require(pos < len(records), "row_index_out_of_range")
        row = records[pos]
        role = metadata_integer(row["role_id"]); owner = metadata_integer(row["observer_id"]); sid = metadata_integer(row["source_id"])
        require(role == scope.train_role_id, "non_training_update")
        require(owner == observer_id, "ownership_mismatch")
        require(sid in allowed, "unapproved_source")
        group = row["group_sha256"]
        if isinstance(group, (bytes, np.bytes_)):
            try:
                group = bytes(group).decode("ascii")
            except UnicodeDecodeError as exc:
                raise AdapterError("invalid_group_digest") from exc
        refs.append(RowRef(sid, metadata_integer(row["source_row"]), owner, role, group)); indices.append(pos)
    # Advanced indexing is a bounded batch copy, after the access checks.
    values = numeric(X[indices], 2)
    return TrainingBatch(scope, observer_id, tuple(refs), FrozenArray.of(values))


@dataclass(frozen=True)
class GlobalState:
    model_id: str
    round_id: int
    scope_id: str
    schema_id: str
    features: tuple[str, ...]
    parameters: Parameters
    scaler_min: FrozenArray
    scaler_denominator: FrozenArray
    anchor_mean: FrozenArray
    inverse_covariance: FrozenArray
    mean: FrozenArray
    internal_threshold: float
    anchor_id: str

    def __post_init__(self):
        self.validate()

    def validate(self):
        name_id(self.model_id); integer(self.round_id)
        for value in (self.scope_id, self.schema_id, self.anchor_id): hex_id(value)
        require(type(self.features) is tuple and len(self.features) > 0 and
                all(isinstance(v, str) and 0 < len(v) <= 128 for v in self.features)
                and self.schema_id == digest(list(self.features)) and len(set(self.features)) == len(self.features), "schema_mismatch")
        require(isinstance(self.parameters, Parameters), "invalid_parameters")
        # Revalidate objects even at scoring boundaries.
        Parameters(**self.parameters.payload())
        d = len(self.features)
        for value in (self.scaler_min, self.scaler_denominator, self.anchor_mean, self.mean):
            require(isinstance(value, FrozenArray) and value.shape == (d,), "shape_mismatch")
            numeric(value.array(), 1)
        inv = self.inverse_covariance
        require(isinstance(inv, FrozenArray) and inv.shape == (d, d), "shape_mismatch")
        positive_definite(inv.array())
        require(bool((self.scaler_denominator.array() > 0).all()), "invalid_scaler")
        scalar(self.internal_threshold, minimum=0)

    def fixed_payload(self):
        return {"version": VERSION, "model_id": self.model_id, "scope_id": self.scope_id,
                "schema_id": self.schema_id, "features": list(self.features),
                "parameters": self.parameters.payload(), "scaler_min": self.scaler_min.values(),
                "scaler_denominator": self.scaler_denominator.values(),
                "anchor_mean": self.anchor_mean.values(), "inverse_covariance": self.inverse_covariance.values(),
                "anchor_id": self.anchor_id}

    @property
    def fixed_id(self):
        return digest(self.fixed_payload())

    def payload(self):
        return {**self.fixed_payload(), "round_id": self.round_id,
                "mean": self.mean.values(), "internal_threshold": self.internal_threshold}

    @property
    def state_id(self):
        return digest(self.payload())


def positive_definite(matrix):
    a = numeric(matrix, 2)
    require(a.shape[0] == a.shape[1] and a.shape[0] > 0, "shape_mismatch")
    require(bool(np.array_equal(a, a.T)), "asymmetric_covariance")
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            chol = np.linalg.cholesky(a)
        require(bool(np.isfinite(chol).all()), "invalid_cholesky")
    except (np.linalg.LinAlgError, FloatingPointError) as exc:
        raise AdapterError("non_positive_definite_covariance", str(exc)) from exc


def transform(X, state):
    state.validate(); X = numeric(X, 2)
    require(X.shape[1] == len(state.features), "shape_mismatch")
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            scaled = (X - state.scaler_min.array()) / state.scaler_denominator.array()
        return numeric(scaled, 2)
    except FloatingPointError as exc:
        raise AdapterError("scaling_arithmetic", str(exc)) from exc


def distances(scaled, mean, inverse):
    """Strict Mahalanobis distance. Any negative quadratic form is a failure."""
    X = numeric(scaled, 2); mu = numeric(mean, 1); inv = numeric(inverse, 2)
    require(X.shape[1] == len(mu) and inv.shape == (len(mu), len(mu)), "shape_mismatch")
    positive_definite(inv)
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            centered = X - mu
            q = np.einsum("ij,jk,ik->i", centered, inv, centered)
            require(bool(np.isfinite(q).all()), "nonfinite_quadratic_form")
            require(bool((q >= 0).all()), "negative_quadratic_form")
            result = np.sqrt(q)
        return numeric(result, 1)
    except FloatingPointError as exc:
        raise AdapterError("distance_arithmetic", str(exc)) from exc


def score(X, state):
    return distances(transform(X, state), state.mean.array(), state.inverse_covariance.array())


def mad_rule(D, k):
    values = numeric(D, 1); require(len(values) > 0, "empty_threshold_input")
    require(bool((values >= 0).all()), "negative_distance")
    k = scalar(k, minimum=0)
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            med = np.median(values); mad = np.median(np.abs(values - med))
            threshold = med + k * MAD_SCALE * mad
        return scalar(threshold, minimum=0), scalar(mad, minimum=0)
    except FloatingPointError as exc:
        raise AdapterError("threshold_arithmetic", str(exc)) from exc


@dataclass(frozen=True)
class AnchorContext:
    """Coordinator's fixed training anchor only; never serialized to workers."""
    batch_id: str
    scope_id: str
    scaled: FrozenArray
    refs: tuple[RowRef, ...]

    def __post_init__(self):
        hex_id(self.batch_id); hex_id(self.scope_id)
        require(isinstance(self.scaled, FrozenArray) and len(self.scaled.shape) == 2
                and self.scaled.shape[0] >= 2, "invalid_anchor")
        require(type(self.refs) is tuple and len(self.refs) == self.scaled.shape[0]
                and all(isinstance(r, RowRef) for r in self.refs), "invalid_anchor_refs")


def anchor_digest(context):
    return digest({"batch": context.batch_id, "scaled_sha256": hashlib.sha256(context.scaled.data).hexdigest(),
                   "refs": [r.payload() for r in context.refs]})


def initialize_anchor(batch, parameters, model_id, *, trusted_benign: bool):
    """Caller explicitly approves benign TRAIN rows; no worker labels are read.

    Benign eligibility must be established outside this adapter before calling.
    No feature selection or non-anchor moment estimation occurs here.
    """
    require(isinstance(batch, TrainingBatch) and type(trusted_benign) is bool
            and trusted_benign, "unapproved_anchor")
    require(isinstance(parameters, Parameters), "invalid_parameters")
    X = batch.values.array(); require(len(X) >= 2, "anchor_requires_two_rows")
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            minimum = X.min(axis=0); span = X.max(axis=0) - minimum
            denominator = np.where(span == 0, 1.0, span)
            scaled = (X - minimum) / denominator
            mean = scaled.mean(axis=0)
            cov = np.atleast_2d(np.cov(scaled, rowvar=False, ddof=1))
            regularized = cov + parameters.ridge * np.eye(X.shape[1])
            positive_definite(regularized)
            inv = np.linalg.solve(regularized, np.eye(X.shape[1]))
            inv = 0.5 * inv + 0.5 * inv.T
        positive_definite(inv)
        threshold, _ = mad_rule(distances(scaled, mean, inv), parameters.mad_k)
    except (np.linalg.LinAlgError, FloatingPointError) as exc:
        raise AdapterError("anchor_arithmetic", str(exc)) from exc
    context = AnchorContext(batch.batch_id, batch.scope.scope_id, FrozenArray.of(scaled), batch.refs)
    state = GlobalState(model_id, 0, batch.scope.scope_id, batch.scope.schema_id, batch.scope.features,
                        parameters, FrozenArray.of(minimum), FrozenArray.of(denominator),
                        FrozenArray.of(mean), FrozenArray.of(inv), FrozenArray.of(mean), threshold,
                        anchor_digest(context))
    return state, context


@dataclass(frozen=True)
class BatchPermit:
    worker_id: int
    model_id: str
    round_id: int
    state_id: str
    scope_id: str
    schema_id: str
    batch_id: str
    rows_seen: int
    role: str = "train"

    def __post_init__(self):
        integer(self.worker_id); name_id(self.model_id); integer(self.round_id); integer(self.rows_seen)
        for v in (self.state_id, self.scope_id, self.schema_id, self.batch_id): hex_id(v)
        require(self.role == "train", "non_training_update")

    def payload(self):
        return {key: getattr(self, key) for key in self.__dataclass_fields__}


def authorize(batch, state):
    state.validate()
    require(isinstance(batch, TrainingBatch), "invalid_batch")
    require(batch.scope.scope_id == state.scope_id and batch.scope.schema_id == state.schema_id, "scope_mismatch")
    return BatchPermit(batch.observer_id, state.model_id, state.round_id, state.state_id,
                       state.scope_id, state.schema_id, batch.batch_id, len(batch.refs))


@dataclass(frozen=True)
class WorkerSummary:
    permit: BatchPermit
    accepted: int
    rejected: int
    mean: FrozenArray | None
    dispersion: float | None
    threshold_candidate: float | None
    status: str

    def validate(self, d):
        require(isinstance(self.permit, BatchPermit), "invalid_permit")
        BatchPermit(**self.permit.payload())
        integer(self.accepted); integer(self.rejected)
        require(self.accepted + self.rejected == self.permit.rows_seen, "summary_count_mismatch")
        if self.accepted == 0:
            require(self.mean is None and self.dispersion is None and self.threshold_candidate is None,
                    "empty_summary_has_statistics")
            require(self.status == ("empty_batch" if self.permit.rows_seen == 0 else "no_accepted_rows"), "invalid_summary_status")
        else:
            require(self.status == ("singleton_accepted" if self.accepted == 1 else "accepted_set"), "invalid_summary_status")
            require(isinstance(self.mean, FrozenArray) and self.mean.shape == (d,), "shape_mismatch")
            numeric(self.mean.array(), 1); scalar(self.dispersion, minimum=0)
            if self.accepted == 1:
                require(self.dispersion == 0 and self.threshold_candidate is None, "invalid_singleton_summary")
            else:
                scalar(self.threshold_candidate, minimum=0)


def summarize(batch, state):
    permit = authorize(batch, state)
    X = transform(batch.values.array(), state)
    D = distances(X, state.mean.array(), state.inverse_covariance.array())
    mask = D <= state.internal_threshold; n = int(mask.sum())
    if n == 0:
        summary = WorkerSummary(permit, 0, len(X), None, None, None,
                                "empty_batch" if len(X) == 0 else "no_accepted_rows")
    else:
        try:
            with np.errstate(over="raise", invalid="raise", divide="raise"):
                mean = FrozenArray.of(X[mask].mean(axis=0))
            candidate, dispersion = mad_rule(D[mask], state.parameters.mad_k) if n > 1 else (None, 0.0)
        except FloatingPointError as exc:
            raise AdapterError("summary_arithmetic", str(exc)) from exc
        summary = WorkerSummary(permit, n, len(X) - n, mean, dispersion, candidate,
                                "singleton_accepted" if n == 1 else "accepted_set")
    summary.validate(len(state.features))
    return summary


def merge(state, anchor, updates, permits):
    """Summary-only E2 merge. Only the coordinator's fixed anchor is rescored.

    Permits must come from approved training batches before worker execution.
    Invalid/missing/duplicate messages abort explicitly. Empty and gate-rejected
    valid summaries are recorded. No remote-authentication guarantee is implied.
    """
    state.validate(); require(isinstance(anchor, AnchorContext), "invalid_anchor")
    require(anchor.scope_id == state.scope_id and anchor.scaled.shape[1] == len(state.features), "anchor_mismatch")
    require(state.anchor_id == anchor_digest(anchor), "anchor_mismatch")
    expected = {}
    for p in permits:
        require(isinstance(p, BatchPermit), "invalid_permit"); BatchPermit(**p.payload())
        require(p.model_id == state.model_id and p.round_id == state.round_id and p.state_id == state.state_id,
                "model_round_state_mismatch")
        require(p.scope_id == state.scope_id and p.schema_id == state.schema_id, "scope_mismatch")
        require(p.worker_id not in expected, "duplicate_worker_permit"); expected[p.worker_id] = p
    received = {}
    for u in updates:
        require(isinstance(u, WorkerSummary), "invalid_summary"); u.validate(len(state.features))
        worker = u.permit.worker_id
        require(worker in expected and u.permit == expected[worker], "unauthorized_summary")
        require(worker not in received, "duplicate_worker_update"); received[worker] = u
    require(set(received) == set(expected), "missing_worker_update")
    valid = [received[k] for k in sorted(received) if received[k].accepted > 0]
    candidates = [u for u in valid if u.threshold_candidate is not None]
    kept = valid; gate = "abstain_fewer_than_three_candidates"; center = None; width = None
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            if len(candidates) >= 3:
                c = numeric([u.threshold_candidate for u in candidates], 1)
                center = scalar(np.median(c)); width = scalar(MAD_SCALE * np.median(np.abs(c - center)), minimum=0)
                radius = scalar(state.parameters.trust_k * width, minimum=0)
                kept = [u for u in candidates if abs(u.threshold_candidate - center) <= radius]
                gate = "active_exact_mad"
                if not kept:
                    kept = valid; gate = "abstain_empty_gate_fallback"
            weights = []
            if kept:
                raw = numeric([u.accepted / (1.0 + u.dispersion) for u in kept], 1)
                total = scalar(raw.sum(), minimum=0); require(total > 0, "nonpositive_weight_sum")
                weights = numeric(raw / total, 1).tolist()
                require(all(w > 0 for w in weights), "nonpositive_weight")
                worker_mean = np.tensordot(weights, np.stack([u.mean.array() for u in kept]), axes=(0, 0))
                mu = (1.0 - state.parameters.blend) * state.anchor_mean.array() + state.parameters.blend * worker_mean
                threshold, _ = mad_rule(distances(anchor.scaled.array(), mu, state.inverse_covariance.array()), state.parameters.mad_k)
                new_state = replace(state, round_id=state.round_id + 1, mean=FrozenArray.of(mu), internal_threshold=threshold)
            else:
                # Parameter state is unchanged; advance only protocol round identity.
                new_state = replace(state, round_id=state.round_id + 1)
    except (FloatingPointError, OverflowError) as exc:
        raise AdapterError("merge_arithmetic", str(exc)) from exc
    kept_ids = {u.permit.worker_id for u in kept}
    audit = {"round_id": state.round_id, "next_round_id": new_state.round_id,
             "previous_state_id": state.state_id, "state_id": new_state.state_id,
             "fixed_state_id": state.fixed_id, "parameters": state.parameters.payload(),
             "gate": gate, "candidate_median": center, "candidate_scaled_mad": width,
             "workers": [{"worker_id": k, "batch_id": u.permit.batch_id,
                          "rows_seen": u.permit.rows_seen, "accepted": u.accepted, "rejected": u.rejected,
                          "status": u.status, "merge_status": "empty" if u.accepted == 0 else
                          ("kept" if k in kept_ids else "trust_gate_rejected"),
                          "threshold_candidate": u.threshold_candidate, "dispersion": u.dispersion}
                         for k, u in sorted(received.items())],
             "normalized_weights": [{"worker_id": u.permit.worker_id, "weight": w} for u, w in zip(kept, weights)],
             "anchor_rows_rescored": anchor.scaled.shape[0] if kept else 0,
             "covariance_updated": False, "internal_threshold_updated": bool(kept),
             "external_reporting_threshold_updated": False}
    require(new_state.fixed_id == state.fixed_id, "fixed_state_changed")
    return new_state, audit
