"""Paper-literal singleton E1 candidates; reviewed v1 remains reproducible.

Al Saleh & Azar (2026), doi:10.3390/iot7030067, Eq5/Algorithm1.
Public source8f6ac0f omits singleton candidates; this version deliberately does
not. Reuses v1's strict numerical/state/access machinery and retained MIT notice.
"""
from dataclasses import dataclass
import numpy as np
import afbkm_adapter as V1
from afbkm_adapter import (AdapterError, FrozenArray, Parameters, TrainingScope,
                           TrainingBatch, BatchPermit, AnchorContext, RowRef,
                           canonical, digest, require, scalar, numeric, integer,
                           transform, distances, score, mad_rule, authorize,
                           training_batch, positive_definite)

VERSION = "afbkm-candidate-v2-paper-singleton"


@dataclass(frozen=True)
class GlobalState(V1.GlobalState):
    def fixed_payload(self):
        return {**super().fixed_payload(), "version": VERSION}


def initialize_anchor(batch, parameters, model_id, *, trusted_benign):
    previous, context = V1.initialize_anchor(batch, parameters, model_id, trusted_benign=trusted_benign)
    fields = {name: getattr(previous, name) for name in previous.__dataclass_fields__}
    return GlobalState(**fields), context


@dataclass(frozen=True)
class WorkerSummary(V1.WorkerSummary):
    def validate(self, d):
        if self.accepted == 1:
            scalar(self.threshold_candidate, minimum=0)
            # Reuse all v1 shape/count/status conditions; only the candidate differs.
            V1.WorkerSummary(self.permit, self.accepted, self.rejected, self.mean,
                             self.dispersion, None, self.status).validate(d)
        else:
            super().validate(d)


def summarize(batch, state):
    require(type(state) is GlobalState, "wrong_af_version")
    permit = authorize(batch, state); X = transform(batch.values.array(), state)
    D = distances(X, state.mean.array(), state.inverse_covariance.array())
    mask = D <= state.internal_threshold; n = int(mask.sum())
    if n == 0:
        summary = WorkerSummary(permit, 0, len(X), None, None, None,
                                "empty_batch" if len(X) == 0 else "no_accepted_rows")
    else:
        try:
            with np.errstate(over="raise", invalid="raise", divide="raise"):
                mean = FrozenArray.of(X[mask].mean(axis=0))
            candidate, dispersion = mad_rule(D[mask], state.parameters.mad_k)
        except FloatingPointError as exc:
            raise AdapterError("summary_arithmetic", str(exc)) from exc
        summary = WorkerSummary(permit, n, len(X) - n, mean, dispersion, candidate,
                                "singleton_accepted" if n == 1 else "accepted_set")
    summary.validate(len(state.features)); return summary


def merge(state, anchor, updates, permits):
    require(type(state) is GlobalState, "wrong_af_version")
    updates = tuple(updates)
    require(all(type(u) is WorkerSummary for u in updates), "wrong_af_summary_version")
    current, audit = V1.merge(state, anchor, updates, permits)
    audit["version"] = VERSION; audit["singleton_candidate_rule"] = "Eq5: distance; MAD0"
    audit["finite_candidate_count"] = sum(u.accepted > 0 for u in updates)
    for row in audit["workers"]:
        if row["accepted"] == 0:
            row["gate_reason"] = row["status"]
        elif row["merge_status"] == "trust_gate_rejected":
            row["gate_reason"] = "finite_candidate_outside_exact_mad_gate"
        elif audit["gate"] == "active_exact_mad":
            row["gate_reason"] = "finite_candidate_inside_exact_mad_gate"
        else:
            row["gate_reason"] = audit["gate"]
    return current, audit
