"""Whitelisted binary application frames for the synthetic-first cost runner."""
from dataclasses import dataclass
import hashlib
import json
import math
import struct
import numpy as np
from afbkm_adapter import canonical, require, scalar, integer, hex_id

VERSION = "matched-cost-messages-v1"
MAX_FRAME = 2 * 1024 * 1024
META = {"arm", "owner", "count", "scope", "schema", "role", "round", "parent", "state"}
BLOCKS = {"moments": ("mean", "M2"), "transform": ("mean", "denominator"),
          "model": ("0.weight", "0.bias", "2.weight", "2.bias"),
          "pooled_raw": ("X", "y", "identities")}
ARMS = {"independent_local", "pooled_central", "fedavg", "local_shared_moments"}
IDENTITY_DTYPE = np.dtype([("source_id", "u1"), ("source_row", "<u8"),
                           ("observer_id", "u1"), ("role_id", "u1"), ("group_sha256", "S64")])


def strict_keys(obj, expected):
    require(type(obj) is dict and set(obj) == expected, "message_key_mismatch")


def model_digest(arrays):
    h = hashlib.sha256()
    for key in BLOCKS["model"]:
        a = arrays[key]
        h.update(canonical([key, a.dtype.str, list(a.shape)])); h.update(a.tobytes(order="C"))
    return h.hexdigest()


def validate(kind, meta, arrays):
    require(kind in BLOCKS, "message_kind"); strict_keys(meta, META)
    require(meta["arm"] in ARMS and meta["role"] == "train", "message_purpose")
    for k in ("owner", "count", "round"): integer(meta[k])
    require(meta["owner"] <= 10, "message_owner")
    for k in ("scope", "schema", "parent", "state"): hex_id(meta[k])
    require(tuple(arrays) == BLOCKS[kind], "message_blocks")
    for a in arrays.values():
        require(isinstance(a, np.ndarray) and a.dtype.str in {"<f8", "<f4", "|u1"}
                and bool(np.isfinite(a).all()), "message_numeric_array")
    if kind in {"moments", "transform"}:
        first, second = arrays.values()
        require(first.dtype.str == second.dtype.str == "<f8" and first.ndim == 1
                and first.shape == second.shape and len(first) == 73, "message_vector_shape")
        if kind == "moments":
            require(1 <= meta["owner"] <= 10 and bool((second >= 0).all()), "invalid_moment_message")
            if meta["count"] == 0: require(bool((first == 0).all() and (second == 0).all()), "nonzero_empty_moments")
        else:
            require(meta["owner"] == 0 and meta["count"] > 0 and bool((second > 0).all()), "invalid_transform_message")
    elif kind == "model":
        expected = ((16, 73), (16,), (1, 16), (1,))
        require(all(a.dtype.str == "<f4" and a.shape == shape for a, shape in zip(arrays.values(), expected)), "model_shape_or_dtype")
        require(meta["state"] == model_digest(arrays), "model_state_digest")
    else:
        X, y, identities = arrays.values(); n = meta["count"]
        require(meta["arm"] == "pooled_central" and 1 <= meta["owner"] <= 10, "raw_pooling_forbidden")
        require(X.dtype.str == "<f8" and X.shape == (n, 73) and y.dtype.str == "|u1" and y.shape == (n,)
                and identities.dtype.str == "|u1" and identities.shape == (n, IDENTITY_DTYPE.itemsize), "raw_shape")
        require(bool(np.isin(y, [0, 1]).all()), "raw_label")
        records = np.frombuffer(identities.tobytes(), dtype=IDENTITY_DTYPE)
        require(bool((records["observer_id"] == meta["owner"]).all() and (records["role_id"] == 0).all()
                     and (records["source_id"] < 14).all()), "raw_identity_boundary")
        for group in records["group_sha256"]: hex_id(bytes(group).decode("ascii"))


def encode(kind, meta, arrays):
    validate(kind, meta, arrays)
    blocks = [{"name": k, "dtype": a.dtype.str, "shape": list(a.shape), "bytes": a.nbytes}
              for k, a in arrays.items()]
    header = canonical({"version": VERSION, "kind": kind, "meta": meta, "blocks": blocks})
    payload = struct.pack(">Q", len(header)) + header + b"".join(a.tobytes(order="C") for a in arrays.values())
    require(len(payload) <= MAX_FRAME, "message_too_large"); return payload


def decode(data):
    require(type(data) is bytes and 8 <= len(data) <= MAX_FRAME, "message_size")
    n = struct.unpack(">Q", data[:8])[0]; require(0 < n <= 65536 and 8 + n <= len(data), "message_header_size")
    def unique(pairs):
        d = {}
        for k, v in pairs: require(k not in d, "message_duplicate_key"); d[k] = v
        return d
    try:
        h = json.loads(data[8:8 + n].decode("utf-8"), object_pairs_hook=unique,
                       parse_constant=lambda v: (_ for _ in ()).throw(ValueError("Nonfinite JSON")))
        strict_keys(h, {"version", "kind", "meta", "blocks"})
        require(h["version"] == VERSION and canonical(h) == data[8:8 + n], "message_version_or_encoding")
        require(h["kind"] in BLOCKS and type(h["blocks"]) is list, "message_kind")
        arrays = {}; offset = 8 + n
        for block in h["blocks"]:
            strict_keys(block, {"name", "dtype", "shape", "bytes"})
            require(block["dtype"] in {"<f8", "<f4", "|u1"} and type(block["shape"]) is list
                    and 1 <= len(block["shape"]) <= 2, "message_dtype_or_shape")
            for value in block["shape"]: integer(value)
            size = math.prod(block["shape"]) * np.dtype(block["dtype"]).itemsize
            require(block["name"] not in arrays and type(block["bytes"]) is int and block["bytes"] == size
                    and offset + size <= len(data), "message_block_size")
            arrays[block["name"]] = np.frombuffer(data[offset:offset + size], dtype=block["dtype"]).reshape(block["shape"])
            offset += size
        require(offset == len(data), "message_trailing_bytes")
        validate(h["kind"], h["meta"], arrays)
    except (UnicodeError, json.JSONDecodeError, OverflowError, RecursionError, TypeError) as exc:
        raise ValueError("Invalid application frame") from exc
    return h["kind"], h["meta"], arrays


@dataclass(frozen=True)
class Moments:
    count: int
    mean: np.ndarray
    M2: np.ndarray

    def __post_init__(self):
        self.validate()
        for name in ("mean", "M2"):
            value = getattr(self, name)
            object.__setattr__(self, name, np.frombuffer(np.ascontiguousarray(value).tobytes(), dtype="<f8"))

    def validate(self):
        integer(self.count)
        require(self.mean.shape == self.M2.shape == (73,) and self.mean.dtype == self.M2.dtype == np.dtype("<f8")
                and bool(np.isfinite(self.mean).all() and np.isfinite(self.M2).all() and (self.M2 >= 0).all()), "invalid_moments")
        if self.count == 0: require(bool((self.mean == 0).all() and (self.M2 == 0).all()), "nonzero_empty_moments")


def empty_moments(): return Moments(0, np.zeros(73, dtype="<f8"), np.zeros(73, dtype="<f8"))


def merge_moments(a, b):
    a.validate(); b.validate()
    if not a.count: return b
    if not b.count: return a
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            n = a.count + b.count; delta = b.mean - a.mean
            result = Moments(n, a.mean + delta * (b.count / n),
                             a.M2 + b.M2 + delta * delta * ((a.count / n) * b.count))
        result.validate(); return result
    except FloatingPointError as exc: raise ValueError("Moment merge arithmetic failed") from exc


def fit_moments(X, chunk):
    require(type(chunk) is int and chunk > 0, "invalid_moment_chunk")
    require(X.ndim == 2 and X.shape[1] == 73 and bool(np.isfinite(X).all()), "invalid_moment_input")
    result = empty_moments()
    for start in range(0, len(X), chunk):
        part = X[start:start + chunk]
        try:
            with np.errstate(over="raise", invalid="raise", divide="raise"):
                mean = part.mean(axis=0); centered = part - mean
                local = Moments(len(part), mean, (centered * centered).sum(axis=0))
            result = merge_moments(result, local)
        except FloatingPointError as exc: raise ValueError("Moment fitting arithmetic failed") from exc
    return result


def denominator(moments):
    moments.validate(); require(moments.count > 0, "no_training_moments")
    with np.errstate(over="raise", invalid="raise", divide="raise"):
        value = np.sqrt(moments.M2 / moments.count)
    require(bool(np.isfinite(value).all()), "nonfinite_denominator")
    return np.where(value == 0, 1.0, value)


def standardize(X, mean, scale):
    require(X.ndim == 2 and X.shape[1] == 73 and mean.shape == scale.shape == (73,)
            and bool(np.isfinite(mean).all() and np.isfinite(scale).all() and (scale > 0).all()), "invalid_transform")
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            value = ((X - mean) / scale).astype("<f4")
        require(bool(np.isfinite(value).all()), "nonfinite_transformed_input"); return value
    except FloatingPointError as exc: raise ValueError("Standardization arithmetic failed") from exc
