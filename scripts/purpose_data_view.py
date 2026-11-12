"""Read-only, purpose-filtered views of the sealed candidate; no fitting.

A trusted-code API guard, not an enclave or remote attestation. Callers supply
known candidate/assignment/feature pins. Training methods never accept a role.
"""
from dataclasses import dataclass
from pathlib import Path
import re
import numpy as np
import load_grouped_candidate as L

IDENTITY_FIELDS = ("source_id", "source_row", "observer_id", "role_id", "group_sha256")
ACCESS = {"supervised_train": ("train", True), "unlabeled_train": ("train", False),
          "anchor_train": ("train", False), "validation_selection": ("validation", True),
          "frozen_validation_scoring": ("validation", False),
          "frozen_calibration_scoring": ("calibration", False)}


def require(ok, reason):
    if not ok: raise ValueError(reason)


def declaration(value):
    require(isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", value), "Explicit declaration ID required")


def observer(value):
    require(type(value) is int and 1 <= value <= 10, "Observer must be in 1..10")


def immutable(array):
    a = np.ascontiguousarray(array)
    return np.frombuffer(a.tobytes(), dtype=a.dtype).reshape(a.shape)


@dataclass(frozen=True)
class RowIdentity:
    source_id: int
    source_row: int
    observer_id: int
    role_id: int
    group_sha256: str

    def __getitem__(self, name):
        if name not in IDENTITY_FIELDS: raise KeyError("Field is not available in row identity")
        return getattr(self, name)


@dataclass(frozen=True)
class UnlabeledBatch:
    X: np.ndarray
    identities: tuple[RowIdentity, ...]


@dataclass(frozen=True)
class LabeledBatch:
    X: np.ndarray
    identities: tuple[RowIdentity, ...]
    y: np.ndarray


@dataclass(frozen=True)
class PurposeView:
    _dataset: "PurposeDataset"
    purpose: str
    observer_id: int
    declaration_id: str
    _indices: tuple[int, ...] | None = None
    _excluded_anchor_indices: tuple[int, ...] = ()
    frozen_scorer_id: str | None = None

    def __post_init__(self):
        observer(self.observer_id); declaration(self.declaration_id)
        require(self.purpose in ACCESS, "Unknown purpose")
        if self.purpose.startswith("frozen_"):
            require(isinstance(self.frozen_scorer_id, str) and L.HEX.fullmatch(self.frozen_scorer_id), "Frozen scorer digest required")
        else:
            require(self.frozen_scorer_id is None, "Scorer ID belongs only to scoring views")
        require(not self._excluded_anchor_indices or self.purpose == "unlabeled_train", "Anchor exclusion belongs only to worker training")
        require((self._indices is not None) == (self.purpose == "anchor_train"), "Explicit anchor identity selection required")

    @property
    def role(self): return ACCESS[self.purpose][0]

    @property
    def features(self): return self._dataset.features

    def batches(self, batch_rows):
        require(type(batch_rows) is int and 1 <= batch_rows <= 100000, "Invalid batch bound")
        labelled = ACCESS[self.purpose][1]
        if self._indices is not None:
            selections = (np.asarray(self._indices[i:i + batch_rows], dtype=np.int64)
                          for i in range(0, len(self._indices), batch_rows))
        else:
            # Scan metadata only, retaining order and every final partial batch.
            selections = self._dataset._selections(self.role, self.observer_id, batch_rows, self._excluded_anchor_indices)
        for positions in selections:
            self._dataset._check_positions(positions, self.role, self.observer_id)
            ids = self._dataset._identities(positions)
            X = immutable(self._dataset._X[positions])
            require(bool(np.isfinite(X).all()), "Nonfinite prepared predictor")
            if labelled:
                y = self._dataset._labels(positions)
                yield LabeledBatch(X, ids, y)
            else:
                yield UnlabeledBatch(X, ids)

    def reporting_labels(self, identities):
        require(self.purpose.startswith("frozen_"), "Labels for reporting require a declared frozen-scoring view")
        positions = self._dataset._address(identities, self.role, self.observer_id)
        return self._dataset._labels(positions)


class PurposeDataset:
    """Open via the loader seal, validate schema/ownership/roles, then issue views."""
    def __init__(self, directory, *, expected_features, candidate_sha256, assignment_sha256):
        for pin in (candidate_sha256, assignment_sha256):
            require(isinstance(pin, str) and L.HEX.fullmatch(pin), "Explicit candidate/assignment pins required")
        require(type(expected_features) is tuple and len(expected_features) == 73
                and all(isinstance(n, str) for n in expected_features)
                and len(set(expected_features)) == 73, "Expected exact ordered 73-field schema")
        schema, X, records = L.open_arrays(directory)
        require(schema["features"] == list(expected_features)
                and not set(expected_features) & set(L.META + L.EXCLUDED_IAT), "Feature schema differs")
        require(schema["roles"] == L.ROLE_IDS and schema["original_labels"] == L.LABEL_IDS
                and schema["binary_labels"] == L.roles.LABELS, "Role/label schema differs")
        require(schema["feature_dtype"] == "<f8" and schema["feature_shape"] == list(X.shape)
                and schema["source_row_origin"] == "zero-based parsed CSV data row, excluding header"
                and schema["record_itemsize"] == L.RECORD_DTYPE.itemsize
                and schema["record_dtype"] == [list(v) for v in L.RECORD_DTYPE.descr], "Malformed storage schema")
        summary = L.read_json(Path(directory) / "summary.json")
        require(summary["input_sha256"]["candidate"] == candidate_sha256
                and summary["assignment_sha256"] == assignment_sha256, "Candidate/assignment binding differs")
        require(summary["rows"] == len(X) and summary["rows_by_role"] ==
                {name: sum(q["benign"] + q["attack"] for q in summary["binary_support"] if q["role"] == name)
                 for name in L.ROLE_IDS}, "Malformed support accounting")
        sources = summary["sources"]
        require(type(sources) is list and len(sources) == 14
                and {s["path"] for s in sources} == L.EXPECTED_PATHS, "Source inventory differs")
        require(L.read_json(Path(directory) / "source-map.json") ==
                [{k: s[k] for k in ("path", "sha256", "client_id")} for s in sources], "Source map differs")
        offsets = {}; offset = 0; totals = {r: 0 for r in L.ROLE_IDS}
        for sid, source in enumerate(sources):
            require(source["source_id"] == sid and type(source["rows"]) is int and source["rows"] > 0,
                    "Invalid source row accounting")
            observer(source["client_id"]); require(L.HEX.fullmatch(source["sha256"]), "Invalid source hash")
            offsets[sid] = (offset, source["rows"], source["client_id"])
            for begin in range(offset, offset + source["rows"], 10000):
                end = min(begin + 10000, offset + source["rows"]); part = records[begin:end]
                require(bool((part["source_id"] == sid).all()) and
                        np.array_equal(part["source_row"], np.arange(begin - offset, end - offset, dtype="<u8")), "Source-row identities differ")
                require(bool((part["observer_id"] == source["client_id"]).all()), "Observer/source ownership differs")
                require(bool(np.isin(part["role_id"], list(L.ROLE_IDS.values())).all()), "Unknown prepared role")
                for role, rid in L.ROLE_IDS.items(): totals[role] += int((part["role_id"] == rid).sum())
            offset += source["rows"]
        require(offset == len(X) and totals == summary["rows_by_role"], "Row/role totals differ")
        require(not X.flags.writeable and not records.flags.writeable, "Prepared arrays must be read-only")
        self.features = expected_features
        self._X, self._records, self._offsets = X, records, offsets
        self.schema, self.summary = schema, summary

    def _selections(self, role, owner, batch_rows, excluded=()):
        rid = L.ROLE_IDS[role]; pending = []; excluded = set(excluded)
        for start in range(0, len(self._records), 10000):
            part = self._records[start:start + 10000]
            hits = np.flatnonzero((part["role_id"] == rid) & (part["observer_id"] == owner)) + start
            pending.extend(i for i in hits.tolist() if i not in excluded)
            while len(pending) >= batch_rows:
                yield np.asarray(pending[:batch_rows], dtype=np.int64); del pending[:batch_rows]
        if pending: yield np.asarray(pending, dtype=np.int64)

    def _check_positions(self, positions, role, owner):
        require(role in L.ROLE_IDS, "Unknown role")
        require(bool((self._records["role_id"][positions] == L.ROLE_IDS[role]).all()), "Role leakage")
        require(bool((self._records["observer_id"][positions] == owner).all()), "Observer leakage")

    def _identities(self, positions):
        cols = {name: self._records[name][positions] for name in IDENTITY_FIELDS}
        return tuple(RowIdentity(int(cols["source_id"][i]), int(cols["source_row"][i]),
                                 int(cols["observer_id"][i]), int(cols["role_id"][i]),
                                 bytes(cols["group_sha256"][i]).decode("ascii")) for i in range(len(positions)))

    def _address(self, identities, role, owner):
        identities = tuple(identities)
        positions = []; seen = set()
        for identity in identities:
            require(isinstance(identity, RowIdentity), "Exact row identities required")
            sid, row = identity.source_id, identity.source_row
            require(type(sid) is int and type(row) is int and sid in self._offsets, "Unknown source identity")
            offset, n, source_owner = self._offsets[sid]
            require(0 <= row < n and source_owner == owner, "Source row or owner differs")
            require((sid, row) not in seen, "Duplicate selection identity"); seen.add((sid, row))
            positions.append(offset + row)
        pos = np.asarray(positions, dtype=np.int64); self._check_positions(pos, role, owner)
        require(self._identities(pos) == tuple(identities), "Row identity differs")
        return pos

    def _labels(self, positions):
        y = self._records["binary_label"][positions]
        original = self._records["original_label_id"][positions]
        require(bool(np.isin(y, [0, 1]).all()) and bool(np.isin(original, list(L.LABEL_IDS.values())).all()), "Unknown label")
        expected = np.asarray([L.roles.LABELS[name] for name in L.LABEL_NAMES], dtype="u1")
        require(np.array_equal(y, expected[original]), "Original/binary label mismatch")
        return immutable(y)

    def supervised_train(self, owner): return PurposeView(self, "supervised_train", owner, "supervised-train")
    def unlabeled_train(self, owner, *, exclude_anchor=None):
        if exclude_anchor is None: return PurposeView(self, "unlabeled_train", owner, "unlabeled-train")
        require(isinstance(exclude_anchor, PurposeView) and exclude_anchor._dataset is self
                and exclude_anchor.purpose == "anchor_train" and exclude_anchor.observer_id == owner,
                "Only this observer's approved anchor may be excluded")
        return PurposeView(self, "unlabeled_train", owner, exclude_anchor.declaration_id,
                           _excluded_anchor_indices=exclude_anchor._indices)

    def trusted_benign_anchor(self, owner, identities, *, approval_id):
        observer(owner); declaration(approval_id)
        identities = tuple(identities); require(len(identities) >= 2, "Anchor requires at least two declared rows")
        positions = self._address(identities, "train", owner)
        require(bool((self._labels(positions) == 0).all()) and
                bool((self._records["original_label_id"][positions] == L.LABEL_IDS["Normal"]).all()), "Anchor includes non-benign rows")
        return PurposeView(self, "anchor_train", owner, approval_id, tuple(int(i) for i in positions))

    def validation_selection(self, owner, *, declaration_id):
        return PurposeView(self, "validation_selection", owner, declaration_id)

    def scoring(self, role, owner, *, declaration_id, frozen_scorer_id):
        require(role in {"validation", "calibration"}, "Only declared held-out scoring roles allowed")
        return PurposeView(self, "frozen_" + role + "_scoring", owner, declaration_id,
                           frozen_scorer_id=frozen_scorer_id)
