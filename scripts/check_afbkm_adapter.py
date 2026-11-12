"""Synthetic-only ownership/tail/wire integration. No dataset input option."""
from __future__ import annotations

import argparse
from collections import Counter
import json
import sys

import numpy as np

import afbkm_adapter as A
import afbkm_wire as W


def run_schedule(state, anchor, workers):
    """Consume every submitted training batch without equal-length truncation.

    Worker windows must be disjoint from the anchor and from earlier windows.
    This schedule is batch-order deterministic, not an asserted capture timeline.
    """
    state.validate()
    owners = sorted(workers)
    for owner in owners: A.integer(owner)
    initial = W.encode_initial(state)
    replicas = {owner: W.decode_initial(initial) for owner in owners}
    streams = {owner: iter(workers[owner]) for owner in owners}
    seen = {(r.source_id, r.source_row) for r in anchor.refs}
    observed = Counter(); rounds = []; update_bytes = 0; later_bytes = 0
    while streams:
        tasks = {}
        for owner in sorted(list(streams)):
            try:
                batch = next(streams[owner])
            except StopIteration:
                del streams[owner]; continue
            A.require(isinstance(batch, A.TrainingBatch) and batch.observer_id == owner, "ownership_mismatch")
            for ref in batch.refs:
                key = (ref.source_id, ref.source_row)
                A.require(key not in seen, "reused_training_row"); seen.add(key)
            tasks[owner] = batch
        if not tasks: break
        permits = [A.authorize(tasks[owner], state) for owner in sorted(tasks)]
        summaries = []; lengths = []
        for owner in sorted(tasks):
            A.require(replicas[owner].state_id == state.state_id, "replica_state_mismatch")
            summary = A.summarize(tasks[owner], replicas[owner])
            payload = W.encode_summary(summary, len(state.features))
            rebuilt = W.decode_summary(payload, len(state.features))
            A.require(W.encode_summary(rebuilt, len(state.features)) == payload, "wire_roundtrip_mismatch")
            summaries.append(rebuilt); lengths.append({"worker_id": owner, "bytes": len(payload)})
            observed[owner] += len(tasks[owner].refs); update_bytes += len(payload)
        current, audit = A.merge(state, anchor, summaries, permits)
        payload = W.encode_delta(state, current)
        for owner in owners:
            replicas[owner] = W.apply_delta(replicas[owner], payload)
            A.require(replicas[owner].state_id == current.state_id, "wire_roundtrip_mismatch")
        later_bytes += len(payload) * len(owners)
        audit.update(worker_payload_lengths=lengths, round_state_bytes=len(payload),
                     round_state_recipient_count=len(owners))
        rounds.append(audit); state = current
    return {"status": "synthetic_integration_complete", "synthetic_only": True,
            "rows_by_native_worker": {str(k): observed[k] for k in owners},
            "total_worker_rows": sum(observed.values()), "anchor_rows": len(anchor.refs),
            "all_supplied_batches_consumed": True, "rounds": rounds,
            "final_state_id": state.state_id, "fixed_state_id": state.fixed_id,
            "initial_distribution": {"bytes_per_worker": len(initial), "recipients": len(owners),
                                     "total_application_bytes": len(initial) * len(owners),
                                     "includes_fixed_covariance_and_scaler": True},
            "later_round_state_application_bytes": later_bytes,
            "worker_summary_application_bytes": update_bytes,
            "transport_bytes_measured": False, "real_dataset_read": False,
            "external_reporting_calibration_performed": False}


def fake_scope(dimension=1):
    return A.TrainingScope(A.digest("fabricated-candidate"), A.digest("fabricated-roles"),
                           tuple("x" + str(i) for i in range(dimension)),
                           tuple((i, A.digest("fabricated-source-" + str(i))) for i in range(4)))


def fake_batch(scope, owner, values, *, source=None, offset=0):
    source = owner if source is None else source
    X = np.asarray(values, dtype=float).reshape((-1, len(scope.features)))
    refs = tuple(A.RowRef(source, offset + i, owner, 0, A.digest([source, offset + i])) for i in range(len(X)))
    return A.TrainingBatch(scope, owner, refs, A.FrozenArray.of(X))


def synthetic_check():
    scope = fake_scope()
    anchor_batch = fake_batch(scope, 0, [[-1.0], [1.0]])
    state, anchor = A.initialize_anchor(anchor_batch, A.Parameters(0.5, 3, 0.5, 3),
                                       "fabricated-model", trusted_benign=True)
    workers = {1: [fake_batch(scope, 1, [[0.0]] * 4), fake_batch(scope, 1, [[0.2]] * 3, offset=4)],
               2: [fake_batch(scope, 2, [[-0.2]] * 3), fake_batch(scope, 2, [], offset=3)],
               3: [fake_batch(scope, 3, [[3.0]] * 4), fake_batch(scope, 3, [[3.0]] * 4, offset=4),
                   fake_batch(scope, 3, [[3.0]] * 2, offset=8)]}
    result = run_schedule(state, anchor, workers)
    A.require(result["rows_by_native_worker"] == {"1": 7, "2": 3, "3": 10}
              and result["total_worker_rows"] == 20 and len(result["rounds"]) == 3, "synthetic_schedule_failure")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    try:
        result = synthetic_check()
    except (A.AdapterError, FloatingPointError) as exc:
        print(json.dumps({"status": "synthetic_integration_failed", "failure_reason": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
