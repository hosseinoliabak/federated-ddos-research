"""Synthetic-first, purpose-view-backed five-arm cost runner. No quality evaluation."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter
import argparse
import hashlib
import json
import os
import platform
import resource
import sys
import subprocess
import tempfile
import time
# The standalone fresh-process CLI sets native-library caps before imports.
if __name__ == "__main__":
    for _name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
        os.environ[_name] = "2"
import numpy as np
import torch
from threadpoolctl import threadpool_limits, threadpool_info
import load_grouped_candidate as L
from purpose_data_view import PurposeDataset, RowIdentity, immutable
import afbkm_adapter_v2 as A
import afbkm_wire_v2 as AW
import workload_messages as M

VERSION = "matched-five-arm-cost-v1"
OWNERS = tuple(range(1, 11))


@dataclass(frozen=True)
class PilotConfig:
    seed: int = 20261112
    cpu_threads: int = 2
    batch_rows: int = 256
    learning_rate: float = 0.01
    anchor_owner: int = 1
    af_ridge: float = 0.001
    af_mad_k: float = 3.0
    af_blend: float = 0.5
    af_trust_k: float = 3.0

    def validate(self):
        for value in (self.seed, self.cpu_threads, self.batch_rows, self.anchor_owner): A.integer(value)
        A.require(1 <= self.anchor_owner <= 10 and 1 <= self.cpu_threads <= 18
                  and 1 <= self.batch_rows <= 1024, "invalid_cost_config")
        A.require(A.scalar(self.learning_rate, minimum=0) > 0, "invalid_learning_rate")
        A.Parameters(self.af_ridge, self.af_mad_k, self.af_blend, self.af_trust_k)


@dataclass(frozen=True)
class Store:
    owner: int
    X: np.ndarray
    identities: tuple[RowIdentity, ...]
    y: np.ndarray | None = None

    def validate(self):
        A.require(type(self.owner) is int and self.owner in OWNERS and self.X.shape == (len(self.identities), 73)
                  and self.X.dtype == np.dtype("<f8") and bool(np.isfinite(self.X).all()), "invalid_worker_store")
        seen = set()
        for row in self.identities:
            A.require(isinstance(row, RowIdentity) and row.observer_id == self.owner and row.role_id == 0, "worker_identity_boundary")
            key = row.source_id, row.source_row
            A.require(key not in seen, "reused_source_row"); seen.add(key)
        if self.y is not None:
            A.require(self.y.shape == (len(self.X),) and self.y.dtype == np.dtype("u1")
                      and bool(np.isin(self.y, [0, 1]).all()), "invalid_worker_labels")


def row_key(row): return row.source_id, row.source_row


def order_for(store, seed, full_identities=None):
    """SeedSequence([seed,owner])/PCG64 on full native TRAIN order, then filter.

    Exclusion is by exact source-row identity; the surviving AF sequence is the
    same relative permutation as the neural stream, not a second reshuffle.
    """
    store.validate(); full = tuple(full_identities) if full_identities is not None else store.identities
    A.require(len({row_key(r) for r in full}) == len(full), "duplicate_schedule_identity")
    A.require(all(r.observer_id == store.owner and r.role_id == 0 for r in full), "schedule_owner_role_mismatch")
    full_map = {row_key(r): r for r in full}
    A.require(all(full_map.get(row_key(r)) == r for r in store.identities), "schedule_identity_mismatch")
    lookup = {row_key(r): i for i, r in enumerate(store.identities)}
    generator = np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed, store.owner])))
    order = np.asarray([lookup[row_key(full[i])] for i in generator.permutation(len(full))
                        if row_key(full[i]) in lookup], dtype=np.int64)
    A.require(len(order) == len(store.X) and len(np.unique(order)) == len(order), "schedule_coverage_mismatch")
    return order


def identity_digest(identities):
    h = hashlib.sha256()
    for r in identities: h.update(A.canonical([r.source_id, r.source_row, r.observer_id, r.role_id, r.group_sha256]) + b"\n")
    return h.hexdigest()


def stage(view, batch_rows, access, arm):
    start = time.monotonic(); chunks = []; ys = []; ids = []; labelled = view.purpose in {"supervised_train", "validation_selection"}
    A.require(view.role == "train" and view.purpose != "validation_selection", "non_training_stage")
    for batch in view.batches(batch_rows):
        chunks.append(batch.X); ids.extend(batch.identities)
        if labelled: ys.append(batch.y)
        else: A.require(not hasattr(batch, "y"), "worker_labels_exposed")
    X = immutable(np.concatenate(chunks) if chunks else np.empty((0, 73), dtype="<f8"))
    y = immutable(np.concatenate(ys) if ys else np.empty(0, dtype="u1")) if labelled else None
    store = Store(view.observer_id, X, tuple(ids), y); store.validate()
    access.append({"arm": arm, "purpose": view.purpose, "owner": view.observer_id, "feature_rows_read": len(X),
                   "label_rows_exposed": len(X) if labelled else 0, "seconds": time.monotonic() - start,
                   "source_identity_sha256": identity_digest(ids)})
    return store


def template_model():
    return torch.nn.Sequential(torch.nn.Linear(73, 16, device="cpu", dtype=torch.float32),
                               torch.nn.ReLU(), torch.nn.Linear(16, 1, device="cpu", dtype=torch.float32))


def snapshot(model):
    return {k: immutable(v.detach().cpu().numpy()) for k, v in model.state_dict().items()}


def clone_model(initial):
    model = template_model()
    model.load_state_dict({k: torch.from_numpy(v.copy()) for k, v in initial.items()}, strict=True)
    A.require(M.model_digest(snapshot(model)) == M.model_digest(initial), "neural_initialization_mismatch")
    return model


def train(model, store, mean, scale, order, config, optimizer=None, progress=None):
    A.require(store.y is not None, "supervised_labels_missing")
    start = time.monotonic(); steps = 0; sizes = []
    progress = {} if progress is None else progress
    progress.update(owner=store.owner, planned_rows=len(order), transformed_rows=0, forward_rows_attempted=0,
                    backward_steps_attempted=0, optimizer_steps_attempted=0, finite_steps_completed=0)
    optimizer = optimizer or torch.optim.SGD(model.parameters(), lr=config.learning_rate,
                   momentum=0, weight_decay=0, foreach=False, fused=False)
    for begin in range(0, len(order), config.batch_rows):
        positions = order[begin:begin + config.batch_rows]
        values = M.standardize(store.X[positions], mean, scale)
        progress["transformed_rows"] += len(positions)
        x = torch.from_numpy(values); y = torch.from_numpy(store.y[positions].astype("<f4"))
        optimizer.zero_grad(set_to_none=True)
        progress["forward_rows_attempted"] += len(positions)
        loss = torch.nn.functional.binary_cross_entropy_with_logits(model(x).squeeze(1), y)
        A.require(bool(torch.isfinite(loss)), "nonfinite_training_loss")
        progress["backward_steps_attempted"] += 1; loss.backward()
        A.require(all(p.grad is not None and bool(torch.isfinite(p.grad).all()) for p in model.parameters()), "nonfinite_training_gradient")
        progress["optimizer_steps_attempted"] += 1; optimizer.step()
        A.require(all(bool(torch.isfinite(p).all()) for p in model.parameters()), "nonfinite_neural_parameter")
        progress["finite_steps_completed"] += 1
        steps += 1; sizes.append(len(positions))
    return {"owner": store.owner, "training_presentations": len(order), "optimizer_steps": steps,
            "batch_sizes": sizes, "tail_rows": sizes[-1] if sizes else 0, "seconds": time.monotonic() - start,
            "order_sha256": identity_digest(store.identities[i] for i in order),
            "benign_rows": int((store.y == 0).sum()), "attack_rows": int((store.y == 1).sum()),
            "status": "trained" if len(order) else "empty_worker_untrained", "work_counters": dict(progress)}


def weighted_models(states, counts):
    A.require(len(states) == len(counts) and len(states) > 0 and all(type(n) is int and n >= 0 for n in counts)
              and sum(counts) > 0, "invalid_neural_aggregation_counts")
    total = sum(counts); result = {}
    for key in M.BLOCKS["model"]:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            value = sum(s[key].astype("<f8") * (n / total) for s, n in zip(states, counts)).astype("<f4")
        A.require(bool(np.isfinite(value).all()), "nonfinite_neural_aggregate"); result[key] = immutable(value)
    return result


class Ledger:
    def __init__(self, out):
        self.path = out / "messages.jsonl"; self.path.touch(exist_ok=False)
        self.counts = Counter(); self.bytes = Counter(); self.serialization_seconds = Counter()

    def record(self, arm, kind, sender, recipient, payload, elapsed, *, round_id=0, fields=()):
        A.require(sender in range(11) and recipient in range(11), "message_endpoint")
        key = arm + ":" + kind; self.counts[key] += 1; self.bytes[key] += len(payload); self.serialization_seconds[arm] += elapsed
        with self.path.open("a") as stream:
            stream.write(json.dumps({"arm": arm, "kind": kind, "sender": sender, "recipient": recipient,
                         "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest(),
                         "round_id": round_id, "logical_fields": list(fields)}, sort_keys=True) + "\n")

    def transfer(self, kind, meta, arrays, sender, recipient):
        t = time.monotonic(); payload = M.encode(kind, meta, arrays); k, m, decoded = M.decode(payload)
        A.require(M.encode(k, m, decoded) == payload, "message_roundtrip_mismatch")
        label = kind
        if kind == "model": label = "model_initial" if meta["round"] == 0 else ("model_final" if meta["owner"] == 0 else "model_update")
        self.record(meta["arm"], label, sender, recipient, payload, time.monotonic() - t,
                    round_id=meta["round"], fields=tuple(arrays))
        return m, decoded


def meta(scope, arm, owner, count, *, round_id=0, parent="0" * 64, state="0" * 64):
    return {"arm": arm, "owner": owner, "count": count, "scope": scope.scope_id, "schema": scope.schema_id,
            "role": "train", "round": round_id, "parent": parent, "state": state}


def shared_moments(dataset, scope, arm, config, access, ledger):
    started = time.monotonic(); combined = M.empty_moments(); owners = []
    for owner in OWNERS:
        store = stage(dataset.unlabeled_train(owner), config.batch_rows, access, arm)
        t = time.monotonic(); moments = M.fit_moments(store.X, config.batch_rows)
        owners.append({"owner": owner, "moment_input_rows": moments.count, "seconds": time.monotonic() - t})
        header, arrays = ledger.transfer("moments", meta(scope, arm, owner, moments.count),
                         {"mean": moments.mean, "M2": moments.M2}, owner, 0)
        A.require(header == meta(scope, arm, owner, len(store.X)), "moment_admission_mismatch")
        combined = M.merge_moments(combined, M.Moments(header["count"], arrays["mean"], arrays["M2"]))
    scale = M.denominator(combined); recipients = {}
    for owner in OWNERS:
        header, arrays = ledger.transfer("transform", meta(scope, arm, 0, combined.count),
                                        {"mean": combined.mean, "denominator": scale}, 0, owner)
        A.require(header == meta(scope, arm, 0, combined.count), "transform_admission_mismatch")
        recipients[owner] = arrays
    return combined, recipients, {"seconds": time.monotonic() - started, "owners": owners,
             "rows": combined.count, "moment_sha256": A.digest([combined.mean.tolist(), combined.M2.tolist()])}


def raw_arrays(store, begin, end):
    rows = store.identities[begin:end]; packed = np.empty(len(rows), dtype=M.IDENTITY_DTYPE)
    for j, row in enumerate(rows): packed[j] = (row.source_id, row.source_row, row.observer_id, row.role_id, row.group_sha256.encode())
    return {"X": store.X[begin:end], "y": store.y[begin:end],
            "identities": np.frombuffer(packed.tobytes(), dtype="u1").reshape(len(rows), M.IDENTITY_DTYPE.itemsize)}


def received_store(owner, chunks):
    X = []; y = []; ids = []
    for c in chunks:
        X.append(c["X"]); y.append(c["y"])
        records = np.frombuffer(c["identities"].tobytes(), dtype=M.IDENTITY_DTYPE)
        ids.extend(RowIdentity(int(r["source_id"]), int(r["source_row"]), int(r["observer_id"]), int(r["role_id"]), bytes(r["group_sha256"]).decode()) for r in records)
    store = Store(owner, immutable(np.concatenate(X) if X else np.empty((0, 73), dtype="<f8")), tuple(ids),
                  immutable(np.concatenate(y) if y else np.empty(0, dtype="u1")))
    store.validate(); return store


def neural_arm(dataset, scope, arm, initial, config, access, ledger, out, progress):
    started = time.monotonic(); clients = []; states = []; counts = []; local_moment_ids = {}; prep = {}
    pooled = {}; pooled_moments = M.empty_moments(); global_moments = None; transforms = None
    if arm in {"fedavg", "local_shared_moments"}:
        global_moments, transforms, prep = shared_moments(dataset, scope, arm, config, access, ledger)
    if arm == "pooled_central":
        t = time.monotonic()
        for owner in OWNERS:
            local = stage(dataset.supervised_train(owner), config.batch_rows, access, arm); chunks = []
            for begin in range(0, len(local.X), config.batch_rows):
                end = min(begin + config.batch_rows, len(local.X))
                header, arrays = ledger.transfer("pooled_raw", meta(scope, arm, owner, end - begin), raw_arrays(local, begin, end), owner, 0)
                A.require(header == meta(scope, arm, owner, end - begin), "raw_admission_mismatch"); chunks.append(arrays)
            central = received_store(owner, chunks)
            A.require(central.identities == local.identities and np.array_equal(central.X, local.X) and np.array_equal(central.y, local.y), "pooled_movement_mismatch")
            pooled[owner] = central
            pooled_moments = M.merge_moments(pooled_moments, M.fit_moments(central.X, config.batch_rows))
        global_moments = pooled_moments
        prep = {"seconds": time.monotonic() - t, "rows": global_moments.count,
                "moment_sha256": A.digest([global_moments.mean.tolist(), global_moments.M2.tolist()]),
                "raw_data_access": "coordinator receives declared numeric training rows, labels and whitelisted identities"}
    initial_id = M.model_digest(initial); pooled_model = clone_model(initial) if arm == "pooled_central" else None
    pooled_optimizer = torch.optim.SGD(pooled_model.parameters(), lr=config.learning_rate, momentum=0,
                                       weight_decay=0, foreach=False, fused=False) if pooled_model is not None else None
    for owner in OWNERS:
        progress.update(active_owner=owner, phase="client_preparation")
        if arm == "independent_local":
            t = time.monotonic(); unlabelled = stage(dataset.unlabeled_train(owner), config.batch_rows, access, arm)
            moments = M.fit_moments(unlabelled.X, config.batch_rows)
            local_moment_ids[str(owner)] = A.digest([moments.mean.tolist(), moments.M2.tolist()])
            prep[str(owner)] = {"moment_input_rows": moments.count, "seconds": time.monotonic() - t}
            mean, scale = (moments.mean, M.denominator(moments)) if moments.count else (np.zeros(73), np.ones(73))
        elif arm == "pooled_central": mean, scale = global_moments.mean, M.denominator(global_moments)
        else: mean, scale = transforms[owner]["mean"], transforms[owner]["denominator"]
        store = pooled[owner] if arm == "pooled_central" else stage(dataset.supervised_train(owner), config.batch_rows, access, arm)
        model = pooled_model or clone_model(initial)
        if arm == "fedavg":
            header, arrays = ledger.transfer("model", meta(scope, arm, 0, 0, state=initial_id), initial, 0, owner)
            A.require(header == meta(scope, arm, 0, 0, state=initial_id), "initial_model_admission_mismatch"); model = clone_model(arrays)
        t = time.monotonic(); order = order_for(store, config.seed); order_seconds = time.monotonic() - t
        client_start = M.model_digest(snapshot(model))
        progress["phase"] = "client_training"; progress["training"] = {}
        result = train(model, store, mean, scale, order, config, pooled_optimizer, progress["training"]); result["schedule_seconds"] = order_seconds
        result["client_start_state_id"] = client_start
        state = snapshot(model); result["arm_initial_state_id"] = initial_id; result["final_state_id"] = M.model_digest(state)
        if arm == "fedavg":
            expected = meta(scope, arm, owner, len(store.X), round_id=1, parent=initial_id, state=result["final_state_id"])
            header, state = ledger.transfer("model", expected, state, owner, 0)
            A.require(header == expected, "update_admission_mismatch"); states.append(state); counts.append(len(store.X))
        if arm != "pooled_central":
            payload = M.encode("model", meta(scope, arm, owner, len(store.X), round_id=1, parent=initial_id, state=result["final_state_id"]), state)
            (out / (arm + "-owner" + str(owner) + ".bin")).write_bytes(payload)
            result["checkpoint_application_bytes"] = len(payload)
        clients.append(result); progress["completed_clients"] = [{"owner": c["owner"], "rows": c["training_presentations"], "steps": c["optimizer_steps"]} for c in clients]
    if arm == "fedavg":
        t = time.monotonic(); final = weighted_models(states, counts); aggregation_seconds = time.monotonic() - t
        for owner in OWNERS:
            expected_final = meta(scope, arm, 0, sum(counts), round_id=1, parent=initial_id, state=M.model_digest(final))
            header, arrays = ledger.transfer("model", expected_final, final, 0, owner)
            A.require(header == expected_final and M.model_digest(arrays) == M.model_digest(final), "final_model_admission_mismatch")
    elif arm == "pooled_central": final = snapshot(pooled_model); aggregation_seconds = 0.0
    else: final = None; aggregation_seconds = 0.0
    if final is not None:
        payload = M.encode("model", meta(scope, arm, 0, sum(c["training_presentations"] for c in clients), round_id=1,
                            parent=initial_id, state=M.model_digest(final)), final)
        (out / (arm + "-final.bin")).write_bytes(payload)
    return {"arm": arm, "seconds": time.monotonic() - started, "clients": clients, "preprocessing": prep,
            "local_moment_ids": local_moment_ids, "aggregation_seconds": aggregation_seconds,
            "total_presentations": sum(c["training_presentations"] for c in clients),
            "total_optimizer_steps": sum(c["optimizer_steps"] for c in clients),
            "final_state_id": M.model_digest(final) if final is not None else None,
            "global_moment_id": A.digest([global_moments.mean.tolist(), global_moments.M2.tolist()]) if global_moments is not None else None,
            "held_out_scoring_or_selection": False}


def adapt(store, indices, scope):
    A.require(store.y is None, "af_worker_has_labels")
    return A.training_batch(store.X, store.identities, (int(i) for i in indices), scope, store.owner)


def af_arm(dataset, scope, config, access, ledger, out, progress):
    arm = "statistical_complete"; started = time.monotonic()
    progress.update(phase="anchor_eligibility", worker_rows_attempted=0, worker_rows_completed=0, completed_rounds=0)
    # Eligibility is outside the detector. Worker stores below never receive y.
    selector = stage(dataset.supervised_train(config.anchor_owner), config.batch_rows, access, "af_anchor_eligibility")
    anchor_ids = tuple(r for r, y in zip(selector.identities, selector.y) if y == 0)
    anchor_view = dataset.trusted_benign_anchor(config.anchor_owner, anchor_ids, approval_id="cost-pilot-all-normal-train-owner1")
    anchor_store = stage(anchor_view, config.batch_rows, access, arm)
    anchor_batch = adapt(anchor_store, np.arange(len(anchor_store.X)), scope)
    progress["phase"] = "anchor_initialization"
    t = time.monotonic(); state, context = A.initialize_anchor(anchor_batch, A.Parameters(config.af_ridge, config.af_mad_k,
                         config.af_blend, config.af_trust_k), "cost-pilot-af-v2", trusted_benign=True)
    initialization_seconds = time.monotonic() - t
    stores = {}; orders = {}; cursors = {}; replicas = {}; rounds = []; seen = {row_key(r) for r in anchor_ids}
    for owner in OWNERS:
        stores[owner] = stage(dataset.unlabeled_train(owner, exclude_anchor=anchor_view if owner == config.anchor_owner else None), config.batch_rows, access, arm)
        orders[owner] = order_for(stores[owner], config.seed, selector.identities if owner == config.anchor_owner else None); cursors[owner] = 0
        t = time.monotonic(); initial = AW.encode_initial(state); replicas[owner] = AW.decode_initial(initial)
        ledger.record(arm, "af_initial_fixed_state", 0, owner, initial, time.monotonic() - t, round_id=0, fields=("mean", "internal_threshold", "inverse_covariance", "scaler_min", "scaler_denominator"))
    while any(cursors[o] < len(orders[o]) for o in OWNERS):
        progress.update(phase="af_round", round_id=state.round_id)
        t_round = time.monotonic(); updates = []; permits = []; statuses = []; worker_times = []
        for owner in OWNERS:
            start = cursors[owner]; stop = min(start + config.batch_rows, len(orders[owner])); indices = orders[owner][start:stop]
            if start == stop:
                statuses.append({"owner": owner, "status": "empty_worker" if len(orders[owner]) == 0 else "exhausted", "rows": 0}); continue
            t_worker = time.monotonic(); batch = adapt(stores[owner], indices, scope)
            for ref in batch.refs:
                key = ref.source_id, ref.source_row
                A.require(key not in seen, "af_anchor_or_window_overlap"); seen.add(key)
            progress["active_owner"] = owner; progress["worker_rows_attempted"] += len(indices)
            permit = A.authorize(batch, state); summary = A.summarize(batch, replicas[owner])
            t = time.monotonic(); payload = AW.encode_summary(summary, 73); rebuilt = AW.decode_summary(payload, 73)
            A.require(AW.encode_summary(rebuilt, 73) == payload, "af_summary_roundtrip")
            ledger.record(arm, "af_summary", owner, 0, payload, time.monotonic() - t, round_id=state.round_id, fields=("accepted_mean", "accepted_count", "dispersion_mad", "threshold_candidate", "permit"))
            permits.append(permit); updates.append(rebuilt); cursors[owner] = stop
            progress["worker_rows_completed"] += len(indices)
            statuses.append({"owner": owner, "status": summary.status, "rows": len(indices)})
            worker_times.append({"owner": owner, "seconds": time.monotonic() - t_worker})
        t = time.monotonic(); current, audit = A.merge(state, context, updates, permits); merge_seconds = time.monotonic() - t
        # Declared engineering policy: fan out each new state to every configured owner,
        # including exhausted owners; no transport latency is inferred from this loop.
        for owner in OWNERS:
            t = time.monotonic(); payload = AW.encode_delta(state, current); replicas[owner] = AW.apply_delta(replicas[owner], payload)
            ledger.record(arm, "af_later_state", 0, owner, payload, time.monotonic() - t, round_id=current.round_id, fields=("mean", "internal_threshold", "identity"))
        audit.update(seconds=time.monotonic() - t_round, merge_including_anchor_rescore_seconds=merge_seconds,
                     worker_seconds=worker_times, schedule_statuses=statuses)
        rounds.append(audit); state = current; progress["completed_rounds"] = len(rounds)
    nworkers = sum(len(s.X) for s in stores.values())
    A.require(len(seen) == nworkers + len(anchor_ids) and nworkers + len(anchor_ids) == dataset.summary["rows_by_role"]["train"], "af_full_train_coverage")
    payload = A.canonical(state.payload()); (out / "statistical-complete-final.json").write_bytes(payload)
    return {"arm": arm, "seconds": time.monotonic() - started, "initialization_seconds": initialization_seconds,
            "anchor_owner": config.anchor_owner, "anchor_rows": len(anchor_ids),
            "initial_anchor_rows_scored": len(anchor_ids), "anchor_eligibility_label_reads_are_outside_detector": True,
            "anchor_identity_sha256": identity_digest(anchor_ids), "anchor_label_rows_examined": len(selector.X),
            "worker_rows": nworkers, "total_presentations_including_anchor_once": nworkers + len(anchor_ids),
            "worker_rows_by_owner": {str(o): len(stores[o].X) for o in OWNERS},
            "worker_order_sha256": {str(o): identity_digest(stores[o].identities[i] for i in orders[o]) for o in OWNERS},
            "internal_anchor_rows_rescored_after_initialization": sum(r["anchor_rows_rescored"] for r in rounds),
            "rounds": rounds, "final_state_id": state.state_id, "fixed_state_id": state.fixed_id,
            "covariance_updates_after_initialization": 0, "external_reporting_calibration_performed": False}


def run(dataset, config, output, *, synthetic_only=False, input_setup_receipt=None):
    A.require(isinstance(dataset, PurposeDataset), "sealed_purpose_dataset_required"); config.validate()
    out = Path(output); A.require(out.absolute() == out.resolve(), "Output symlink escape"); out.mkdir(parents=True, exist_ok=False)
    started = time.monotonic(); access = []; results = {}; ledger = Ledger(out); phase = "initialization"; progress = {}
    source = L.code_context(); source["runner_sources"] = {p.name: L.sha(p) for p in Path(__file__).parent.glob("*.py")
                    if p.name in {"run_matched_workload.py", "workload_messages.py", "afbkm_adapter_v2.py", "afbkm_wire_v2.py", "purpose_data_view.py", "afbkm_adapter.py", "afbkm_wire.py", "synthetic_workload_fixture.py", "check_afbkm_v2.py"}}
    base = {"version": VERSION, "status": "running", "started_utc": datetime.now(timezone.utc).isoformat(),
            "config": asdict(config), "config_sha256": A.digest(asdict(config)), "code": source,
            "candidate_sha256": dataset.summary["input_sha256"]["candidate"], "assignment_sha256": dataset.summary["assignment_sha256"],
            "input_pins": dataset.summary["input_sha256"], "native_sources": dataset.summary["sources"],
            "prepared_array_artifacts": dataset.summary["artifacts"], "features": list(dataset.features),
            "rows_by_role": dataset.summary["rows_by_role"], "native_training_support":
                 [q for q in dataset.summary["binary_support"] if q["role"] == "train"],
            "synthetic_only": synthetic_only, "input_setup_receipt": input_setup_receipt or {"status": "not_timed_by_caller"}, "quality_evaluation_requested": False, "held_out_access": False,
            "device": "cpu", "framework": {"python": platform.python_version(), "numpy": np.__version__, "torch": torch.__version__},
            "single_process_simulation": True, "distributed_latency_privacy_or_network_packets_measured": False}
    L.write_json(out / "run-state.json", base)
    controller = None
    try:
        torch.set_num_threads(config.cpu_threads); torch.use_deterministic_algorithms(True); torch.manual_seed(config.seed)
        controller = threadpool_limits(limits=config.cpu_threads)
        hardware = {"os": platform.platform(), "machine": platform.machine()}
        for key in ("machdep.cpu.brand_string", "hw.memsize", "hw.physicalcpu", "hw.logicalcpu"):
            if platform.system() == "Darwin":
                probe = subprocess.run(["sysctl", "-n", key], text=True, capture_output=True)
                hardware[key] = probe.stdout.strip() if probe.returncode == 0 else "unavailable"
        base["hardware"] = hardware
        base["thread_control"] = {"requested_numerical_threads": config.cpu_threads,
             "torch_intraop_threads": torch.get_num_threads(),
             "supported_pools": [{k: p.get(k) for k in ("user_api", "internal_api", "num_threads", "prefix", "version")} for p in threadpool_info()],
             "startup_environment": {k: os.environ.get(k) for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS")},
             "limit": "threadpoolctl covers detected supported pools; Accelerate thread count is not exposed here. Fresh-process CLI sets startup caps before imports; OS thread count is not measured."}
        initial = snapshot(template_model()); scope = A.TrainingScope(base["candidate_sha256"], base["assignment_sha256"],
                         dataset.features, tuple((q["source_id"], q["sha256"]) for q in dataset.summary["sources"]))
        base["initial_neural_state_id"] = M.model_digest(initial)
        for arm in ("independent_local", "pooled_central", "fedavg", "local_shared_moments"):
            phase = arm; progress.clear(); progress.update(arm=arm, phase="preprocessing", completed_clients=[])
            L.write_json(out / "run-state.json", base | {"active_arm": arm, "completed_arms": list(results)})
            results[arm] = neural_arm(dataset, scope, arm, initial, config, access, ledger, out, progress)
            L.write_json(out / (arm + ".json"), results[arm])
        expected = dataset.summary["rows_by_role"]["train"]
        A.require(all(r["total_presentations"] == expected for r in results.values()), "neural_full_train_coverage")
        A.require(len({results[a]["global_moment_id"] for a in ("pooled_central", "fedavg", "local_shared_moments")}) == 1, "shared_pooled_moment_mismatch")
        for owner in OWNERS:
            digests = {r["clients"][owner - 1]["order_sha256"] for r in results.values()}
            A.require(len(digests) == 1, "neural_stream_mismatch")
        phase = "statistical_complete"; L.write_json(out / "run-state.json", base | {"active_arm": phase, "completed_arms": list(results)})
        progress.clear(); progress["arm"] = phase
        results[phase] = af_arm(dataset, scope, config, access, ledger, out, progress); L.write_json(out / (phase + ".json"), results[phase])
        result = base | {"status": "complete_cost_pilot", "finished_utc": datetime.now(timezone.utc).isoformat(),
                 "elapsed_monotonic_seconds": time.monotonic() - started, "arms": results, "source_access_passes": access,
                 "message_counts": dict(ledger.counts), "application_bytes": dict(ledger.bytes),
                 "encode_decode_roundtrip_seconds": dict(ledger.serialization_seconds),
                 "peak_process_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if platform.system() == "Darwin" else 1024),
                 "quality_decisions_requested": 0, "quality_decisions_produced": 0, "missing_quality_decisions": "not_requested_cost_only",
                 "elapsed_boundary": "After new output-directory creation through arms and checkpoint writes, before final summary/seal hashing/writes; dataset seal opening is caller-timed separately.",
                 "limits": ["Single-process cost check, not distributed latency or detection-quality evidence.",
                            "Equal source-row weights preserve copies; keys are not physical episodes.",
                            "AF singleton mean may reveal the scaled point; no privacy guarantee.",
                            "No held-out scoring, tuning, external calibration or final evaluation."]}
        L.write_json(out / "summary.json", result); L.write_json(out / "run-state.json", result)
        artifacts = {p.name: {"bytes": p.stat().st_size, "sha256": L.sha(p)} for p in out.iterdir() if p.is_file()}
        L.write_json(out / "COMPLETE.json", {"version": VERSION, "status": result["status"], "artifacts": artifacts})
        return result
    except Exception as exc:
        failure = base | {"status": "failed_cost_pilot", "failed_phase": phase, "finished_utc": datetime.now(timezone.utc).isoformat(),
                          "elapsed_monotonic_seconds": time.monotonic() - started, "completed_arms": list(results),
                          "source_access_passes": access, "message_counts": dict(ledger.counts), "application_bytes": dict(ledger.bytes),
                          "error_type": type(exc).__name__, "error": str(exc), "quality_decisions_produced": 0, "partial_work_progress": progress}
        L.write_json(out / "FAILED.json", failure); L.write_json(out / "run-state.json", failure); raise
    finally:
        if controller is not None: controller.restore_original_limits()


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--synthetic", action="store_true", required=True)
    parser.add_argument("--output", type=Path, required=True); args = parser.parse_args()
    from synthetic_workload_fixture import prepared_fixture
    with tempfile.TemporaryDirectory(prefix="matched-cost-synthetic-") as temp:
        t = time.monotonic(); dataset = prepared_fixture(Path(temp).resolve())
        setup = {"phase": "synthetic_fixture_generation_preparation_and_seal_open", "seconds": time.monotonic() - t}
        result = run(dataset, PilotConfig(), args.output.resolve(), synthetic_only=True, input_setup_receipt=setup)
    print(json.dumps({"status": result["status"], "synthetic_only": True, "rows_per_neural_arm": result["arms"]["fedavg"]["total_presentations"],
                      "af_rounds": len(result["arms"]["statistical_complete"]["rounds"]), "application_bytes": result["application_bytes"]}))


if __name__ == "__main__": main()
