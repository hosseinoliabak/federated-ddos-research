"""Disposable 73-field/14-source fixture builder. Never takes an actual dataset."""
from pathlib import Path
import csv
import json
import numpy as np
import load_grouped_candidate as L
import prepare_grouped_roles as R
from purpose_data_view import PurposeDataset


def prepared_fixture(root, *, small=False, no_anchor=False):
    root = Path(root).resolve(); (root / "config").mkdir(parents=True)
    features = [f"feature_{i:02}" for i in range(73)]
    header = list(L.META[:-1]) + features + list(L.EXCLUDED_IAT) + ["label"]
    sources = []
    for sid, relative in enumerate(sorted(L.EXPECTED_PATHS)):
        owner = int(Path(relative).stem.split("-")[1]); normal = "/Normal/" in relative
        label = "Normal" if normal else {1:"DDoS-bot",5:"DDoS-stomp",9:"DDoS-dyn",10:"DDoS-tcp"}[owner]
        if no_anchor and normal and owner == 1: label = "DDoS-bot"
        n = (35 + owner * 3 if normal else 17 + owner) if small else (300 + owner * 7 if normal else 200 + owner * 11)
        path = root / relative; path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="") as stream:
            writer = csv.writer(stream); writer.writerow(header)
            for row in range(n):
                values = [float((row * (j % 5 + 1) + owner * 3 + sid) % (17 + j % 7)) / (j + 1)
                          + (0.2 if not normal else 0) for j in range(73)]
                values[-1] = 5.0  # Explicit constant feature.
                writer.writerow([f"192.0.2.{owner}", "198.51.100.1", 1000 + sid * 2000 + row, 443,
                                 2048, "2023-05-13 15:00:00", *values, -1, -1, -1, label])
        sources.append({"dataset":"flnet2023", "source_role":"development", "path":relative,
                        "client_id":owner, "sha256":L.sha(path)})
    # Deliberately invalid reserved contents. The preparer/loader must never open them.
    for dataset, relative in [("flnet2023", "datasets/flnet2023/extracted/TEST/poison.csv"),
                              ("cicddos2019", "datasets/cicddos2019/extracted/03-11/poison.csv")]:
        path = root / relative; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(b"invalid reserved fixture")
        sources.append({"dataset":dataset,"source_role":"reserved_test","path":relative})
    proposal = {"files":sources,"observed_development_label_mapping":{"flnet2023":R.LABELS},
                "unmapped_development_labels":{"flnet2023":[]}}
    (root / "config/proposal.json").write_text(json.dumps(proposal))
    policy = {"version":R.VERSION,"candidate_id":"synthetic-five-arm-cost-v1","dataset":"flnet2023",
              "claim_scope":"within_release_grouped_holdout","group_definition":R.GROUP_DEFINITION,
              "role_seed":"synthetic-five-arm-roles","role_weights":{"train":8,"validation":1,"calibration":1},
              "minimum_rows_per_client_role":1}
    (root / "config/policy.json").write_text(json.dumps(policy))
    manifest = R.prepare(root,"config/proposal.json","config/policy.json","reports/development-preparation/candidate")
    mp = root / "reports/development-preparation/candidate/candidate-manifest.json"; sp = mp.with_name("COMPLETE.json")
    registry = {"fields":[{"name":v} for v in header],"historical_csv73_ordered_inputs":features}
    registry_path = root / "config/registry.json"; registry_path.write_text(json.dumps(registry))
    pin = {"path":str(mp),"sha256":L.sha(mp),"proposal_path":str(root / "config/proposal.json"),
           "proposal_sha256":L.sha(root / "config/proposal.json"),"policy_path":str(root / "config/policy.json"),
           "policy_sha256":L.sha(root / "config/policy.json"),"seal_path":str(sp),"seal_sha256":L.sha(sp),
           "assignment_sha256":manifest["assignment_sha256"],"executed_role_source_sha256":manifest["source_code_sha256"],
           "executed_role_code_commit":manifest["code_context"]["commit_context"]}
    contract = root / "config/contract.json"; contract.write_text(json.dumps({"candidate":pin,"input":{"features":features}}))
    directory = "reports/development-preparation/prepared"
    L.prepare(root,"config/contract.json","config/registry.json",directory,L.sha(contract),L.sha(registry_path))
    return PurposeDataset(root / directory,expected_features=tuple(features),candidate_sha256=L.sha(mp),
                          assignment_sha256=manifest["assignment_sha256"])
