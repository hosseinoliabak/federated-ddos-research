"""Create an auditable proposal; never assign rows or alter source labels."""

from pathlib import Path
import hashlib, json, re
from datetime import date
from research_workspace import workspace_root

ROOT = workspace_root()
OUT = ROOT / "config"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    if (OUT / "split-proposal.json").exists():
        raise FileExistsError("Existing proposal preserved; choose a new workspace")
    audit = json.loads((ROOT / "reports/dataset-audit/audit.json").read_text())
    assert audit["status"] == "complete"
    observed = {
        ds: sorted({label for f in audit["files"] if f["dataset"] == ds for label in f["labels"]})
        for ds in ["flnet2023", "cicddos2019"]
    }
    allowed = {
        "flnet2023": {"Normal": 0, "DDoS-bot": 1, "DDoS-tcp": 1, "DDoS-stomp": 1, "DDoS-dyn": 1},
        "cicddos2019": {
            "BENIGN": 0,
            "DrDoS_DNS": 1,
            "DrDoS_LDAP": 1,
            "DrDoS_MSSQL": 1,
            "DrDoS_NetBIOS": 1,
            "DrDoS_NTP": 1,
            "DrDoS_SNMP": 1,
            "DrDoS_SSDP": 1,
            "DrDoS_UDP": 1,
            "Syn": 1,
            "TFTP": 1,
            "UDP-lag": 1,
            "WebDDoS": 1,
        },
    }
    maps = {
        ds: {k: allowed[ds][k] for k in labels if k in allowed[ds]}
        for ds, labels in observed.items()
    }
    unknown = {ds: [k for k in labels if k not in allowed[ds]] for ds, labels in observed.items()}
    files = []
    for ds in observed:
        for f in json.loads((ROOT / "datasets" / ds / "extraction.json").read_text()):
            if f["status"] not in ("extracted_crc_passed", "registered_existing_csv"):
                continue
            p = f["path"]
            is_test = "/TEST/" in p or "/03-11/" in p
            client = None
            if ds == "flnet2023" and not is_test:
                client = int(re.search(r"Dataset-(\d+)", p).group(1))
            files.append(
                {
                    "dataset": ds,
                    "path": p,
                    "sha256": f["sha256"],
                    "source_role": "reserved_test" if is_test else "development",
                    "client_id": client,
                    "row_split_assigned": False,
                }
            )
    proposal = {
        "schema_version": 1,
        "status": "proposed_not_frozen",
        "created_on": date.today().isoformat(),
        "task": "Binary DDoS versus benign; preserve original labels",
        "files": files,
        "observed_development_label_mapping": maps,
        "unmapped_development_labels": unknown,
        "unknown_label_action": "Stop preparation; do not map unknown attacks to benign",
        "training_validation_target": {
            "training": 0.8,
            "validation": 0.2,
            "denominator": "Development records only; approximate target subject to valid independent groups and class support",
        },
        "test_policy": "Reserved sources remain outside fitting, tuning, threshold selection, feature selection, and early stopping. Any integrity or overlap inspection must be documented separately.",
        "client_policy": {
            "flnet2023": "Preserve published client numbers and original class skew",
            "cicddos2019": "No natural client mapping established; explicitly declared synthetic clients required",
        },
        "grouping_status": "Not resolved. CSV shards, hours, and identical feature vectors are not assumed to be independent sessions.",
        "blocking_checks": [
            "Confirm capture/session grouping and coordinate exact shared-record groups between clients; do not split clients independently",
            "Resolve FLNET2023 temporal class separation before making a future-traffic claim",
            "Check CICDDoS2019 stored calendar strings against original collection provenance",
            "Resolve PortMap versus PortScan naming before final test-family inclusion",
            "Check cross-partition and cross-client overlap before assigning row roles",
            "Specify feature semantics and per-client treatment of missing or nonfinite values",
        ],
        "preprocessing_policy": "Fit learned transformations only on training records. Explicitly choose local-client or federated preprocessing; do not silently use a pooled global fit.",
        "original_files_modified": False,
        "training_started": False,
        "external_review_of_generated_proposal": False,
    }
    (OUT / "split-proposal.json").write_text(json.dumps(proposal, indent=2) + "\n")
    snapshot = {
        "audit_date": date.today().isoformat(),
        "files": {
            "scripts/" + p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(Path(__file__).resolve().parent.glob("*.py"))
        },
        "audit_sha256": hashlib.sha256(
            (ROOT / "reports/dataset-audit/audit.json").read_bytes()
        ).hexdigest(),
    }
    (OUT / "audit-code-manifest.json").write_text(json.dumps(snapshot, indent=2) + "\n")
    print(
        json.dumps(
            {"proposed_file_roles": len(files), "unmapped_labels": unknown, "row_assignments": 0}
        )
    )


if __name__ == "__main__":
    main()
