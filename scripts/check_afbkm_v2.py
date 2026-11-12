"""Hand-computable v1/v2 singleton counterexample, fabricated points only."""
import json
import numpy as np
import afbkm_adapter as V1
import afbkm_adapter_v2 as V2
import check_afbkm_adapter as C


def check():
    scope = V1.TrainingScope(V1.digest("synthetic-v2-candidate"), V1.digest("synthetic-v2-roles"),
                             ("x",), tuple((i, V1.digest(["source", i])) for i in range(5)))
    anchor = C.fake_batch(scope, 0, [[0.0], [2.0]])
    parameters = V1.Parameters(0.5, 3, 0.5, 3)
    old, oa = V1.initialize_anchor(anchor, parameters, "counterexample", trusted_benign=True)
    new, na = V2.initialize_anchor(anchor, parameters, "counterexample", trusted_benign=True)
    batches = [C.fake_batch(scope, i, [[0.0], [2.0]]) for i in (1, 2, 3)] + [C.fake_batch(scope, 4, [[2.0]])]
    ou = [V1.summarize(b, old) for b in batches]; nu = [V2.summarize(b, new) for b in batches]
    old_result, old_audit = V1.merge(old, oa, ou, [u.permit for u in ou])
    new_result, new_audit = V2.merge(new, na, nu, [u.permit for u in nu])
    assert old_result.mean.array()[0] == 0.5
    assert np.isclose(new_result.mean.array()[0], 15 / 28, rtol=0, atol=1e-15)
    return {"synthetic_only": True, "old_centroid": old_result.mean.values(), "paper_v2_centroid": new_result.mean.values(),
            "old_singleton_candidate": ou[-1].threshold_candidate, "paper_v2_singleton_candidate": nu[-1].threshold_candidate,
            "old_singleton_merge_status": old_audit["workers"][-1]["merge_status"],
            "paper_v2_singleton_gate_reason": new_audit["workers"][-1]["gate_reason"],
            "expected_new_centroid": "15/28", "source_rule": "Eq5 candidate at n1 is its finite distance, with MAD0"}


if __name__ == "__main__": print(json.dumps(check(), indent=2))
