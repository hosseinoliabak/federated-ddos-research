"""Exact AF-BKM candidate application payloads; no transport/security layer."""
from dataclasses import replace
import json

from afbkm_adapter import (AdapterError, VERSION, BatchPermit, FrozenArray,
                          GlobalState, Parameters, WorkerSummary, canonical,
                          require)

MAX_PAYLOAD_BYTES = 2 * 1024 * 1024  # Engineering parser bound, not research budget.
FIXED = {"version", "model_id", "scope_id", "schema_id", "features", "parameters",
         "scaler_min", "scaler_denominator", "anchor_mean", "inverse_covariance", "anchor_id"}
STATE = FIXED | {"round_id", "mean", "internal_threshold"}
PERMIT = {"worker_id", "model_id", "round_id", "state_id", "scope_id", "schema_id",
          "batch_id", "rows_seen", "role"}
SUMMARY = {"permit", "accepted", "rejected", "mean", "dispersion", "threshold_candidate", "status"}


def keys(value, expected):
    require(type(value) is dict and set(value) == expected, "wire_key_mismatch")


def pack(kind, payload):
    data = canonical({"kind": kind, "version": VERSION, "payload": payload})
    require(len(data) <= MAX_PAYLOAD_BYTES, "wire_payload_too_large")
    return data


def unpack(data, kind):
    require(type(data) is bytes and len(data) <= MAX_PAYLOAD_BYTES, "wire_payload_type_or_size")
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "wire_duplicate_key")
            result[key] = value
        return result
    def invalid_constant(value):
        raise AdapterError("wire_nonfinite_constant", value)
    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=pairs,
                           parse_constant=invalid_constant)
        keys(value, {"kind", "version", "payload"})
        require(value["kind"] == kind and value["version"] == VERSION, "wire_kind_or_version")
        require(canonical(value) == data, "wire_noncanonical_encoding")
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, OverflowError, RecursionError) as exc:
        if isinstance(exc, AdapterError):
            raise
        raise AdapterError("wire_decode_failure", type(exc).__name__) from exc
    return value["payload"]


def encode_initial(state):
    state.validate(); require(state.round_id == 0, "initial_state_round")
    return pack("initial_state", {"state": state.payload(), "state_id": state.state_id})


def decode_initial(data):
    p = unpack(data, "initial_state"); keys(p, {"state", "state_id"})
    obj = p["state"]; keys(obj, STATE)
    keys(obj["parameters"], {"ridge", "mad_k", "blend", "trust_k"})
    require(obj["version"] == VERSION, "wire_kind_or_version")
    require(type(obj["features"]) is list, "wire_feature_schema")
    state = GlobalState(obj["model_id"], obj["round_id"], obj["scope_id"], obj["schema_id"],
                        tuple(obj["features"]), Parameters(**obj["parameters"]),
                        FrozenArray.of(obj["scaler_min"]), FrozenArray.of(obj["scaler_denominator"]),
                        FrozenArray.of(obj["anchor_mean"]), FrozenArray.of(obj["inverse_covariance"]),
                        FrozenArray.of(obj["mean"]), obj["internal_threshold"], obj["anchor_id"])
    require(state.round_id == 0 and state.state_id == p["state_id"], "wire_state_identity")
    return state


def encode_delta(previous, current):
    previous.validate(); current.validate()
    require(current.fixed_id == previous.fixed_id, "fixed_state_changed")
    require(current.round_id == previous.round_id + 1, "model_round_state_mismatch")
    return pack("round_state", {"model_id": current.model_id, "round_id": current.round_id,
                "previous_state_id": previous.state_id, "fixed_state_id": current.fixed_id,
                "state_id": current.state_id, "mean": current.mean.values(),
                "internal_threshold": current.internal_threshold})


def apply_delta(previous, data):
    previous.validate(); p = unpack(data, "round_state")
    keys(p, {"model_id", "round_id", "previous_state_id", "fixed_state_id", "state_id", "mean", "internal_threshold"})
    require(p["model_id"] == previous.model_id and p["round_id"] == previous.round_id + 1
            and p["previous_state_id"] == previous.state_id, "model_round_state_mismatch")
    require(p["fixed_state_id"] == previous.fixed_id, "fixed_state_changed")
    current = replace(previous, round_id=p["round_id"], mean=FrozenArray.of(p["mean"]),
                      internal_threshold=p["internal_threshold"])
    require(current.state_id == p["state_id"], "wire_state_identity")
    return current


def encode_summary(summary, dimension):
    summary.validate(dimension)
    return pack("worker_summary", {"permit": summary.permit.payload(), "accepted": summary.accepted,
                "rejected": summary.rejected, "mean": None if summary.mean is None else summary.mean.values(),
                "dispersion": summary.dispersion, "threshold_candidate": summary.threshold_candidate,
                "status": summary.status})


def decode_summary(data, dimension):
    p = unpack(data, "worker_summary"); keys(p, SUMMARY); keys(p["permit"], PERMIT)
    summary = WorkerSummary(BatchPermit(**p["permit"]), p["accepted"], p["rejected"],
                            None if p["mean"] is None else FrozenArray.of(p["mean"]),
                            p["dispersion"], p["threshold_candidate"], p["status"])
    summary.validate(dimension)
    return summary
