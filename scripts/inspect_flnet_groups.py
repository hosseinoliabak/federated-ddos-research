"""Inspect candidate connection groups in FLNET development data without assigning roles."""

from pathlib import Path
from collections import Counter
import hashlib, json, re, time, platform
import numpy as np
import pandas as pd
from research_workspace import workspace_root

ROOT = workspace_root()
OUT = ROOT / "reports/development-preparation"
LABELS = ["Normal", "DDoS-bot", "DDoS-tcp", "DDoS-stomp", "DDoS-dyn"]
FIELDS = ["src_ip", "dst_ip", "src_port", "dst_port", "protocol", "timestamp", "label"]


def connection_key(src, dst, sport, dport, protocol):
    left = (str(src).strip(), str(sport).strip())
    right = (str(dst).strip(), str(dport).strip())
    return (
        (left, right, str(protocol).strip())
        if left <= right
        else (right, left, str(protocol).strip())
    )


def main():
    started = time.monotonic()
    OUT.mkdir(parents=True, exist_ok=True)
    destination = OUT / "flnet-connection-groups.json"
    if destination.exists():
        raise RuntimeError("Existing report preserved; select a new version before rerunning.")
    audit = json.loads((ROOT / "reports/dataset-audit/audit.json").read_text())
    sources = [f for f in audit["files"] if f["dataset"] == "flnet2023"]
    if len(sources) != 14:
        raise RuntimeError("Unexpected development inventory.")
    inventory = {
        f["path"]: f
        for f in json.loads((ROOT / "datasets/flnet2023/extraction.json").read_text())
        if f.get("status") in ("extracted_crc_passed", "registered_existing_csv")
    }
    groups = {}
    file_summaries = []
    date_labels = Counter()
    protocols = Counter()
    port_ranges = {}
    ambiguous_rows = 0
    for item in sources:
        path = ROOT / item["path"]
        if not re.fullmatch(
            r"datasets/flnet2023/extracted/(?:Normal|DDoS)/Dataset-\d+(?:-[A-Za-z]+)?\.csv",
            item["path"],
        ):
            raise RuntimeError("Input is not approved development data.")
        client = int(re.search(r"Dataset-(\d+)", path.name).group(1))
        checksum = hashlib.file_digest(path.open("rb"), "sha256").hexdigest()
        if checksum != inventory[item["path"]]["sha256"]:
            raise RuntimeError("Input checksum changed.")
        rows = 0
        file_groups = set()
        labels = Counter()
        dates = Counter()
        for frame in pd.read_csv(
            path,
            usecols=FIELDS,
            dtype=str,
            keep_default_na=False,
            chunksize=100000,
            on_bad_lines="error",
        ):
            frame = frame[FIELDS]
            for src, dst, sport, dport, protocol, stamp, label in frame.itertuples(
                index=False, name=None
            ):
                if label not in LABELS:
                    raise RuntimeError("Unmapped label.")
                if not re.match(r"^\d{4}-\d{2}-\d{2}[ T]", stamp):
                    raise RuntimeError("Unexpected timestamp representation.")
                if not sport.isdigit() or not dport.isdigit():
                    raise RuntimeError("Noninteger port field.")
                key = connection_key(src, dst, sport, dport, protocol)
                state = groups.get(key)
                if state is None:
                    state = [0, 0, 0, set()]
                    groups[key] = state
                state[0] += 1
                state[1] |= 1 << (client - 1)
                state[2] |= 1 << LABELS.index(label)
                state[3].add(stamp[:10])
                file_groups.add(key)
                rows += 1
                labels[label] += 1
                dates[stamp[:10]] += 1
                date_labels[(stamp[:10], label)] += 1
                protocols[protocol] += 1
                for name, value in [("src_port", int(sport)), ("dst_port", int(dport))]:
                    if name not in port_ranges:
                        port_ranges[name] = [value, value]
                    else:
                        port_ranges[name] = [
                            min(port_ranges[name][0], value),
                            max(port_ranges[name][1], value),
                        ]
        if rows != item["rows"]:
            raise RuntimeError("Row count changed.")
        file_summaries.append(
            {
                "path": item["path"],
                "client_id": client,
                "sha256": checksum,
                "rows": rows,
                "candidate_groups": len(file_groups),
                "labels": dict(labels),
                "dates": dict(dates),
            }
        )
        print(
            json.dumps({"file": path.name, "rows": rows, "candidate_groups": len(file_groups)}),
            flush=True,
        )
    sizes = np.asarray([v[0] for v in groups.values()], dtype=np.int64)
    per_label = {
        label: sum(bool(v[2] & (1 << i)) for v in groups.values()) for i, label in enumerate(LABELS)
    }
    result = {
        "schema": 1,
        "status": "diagnostic_complete_not_a_frozen_split",
        "scope": "14 FLNET2023 DDoS/Normal development files only; reserved TEST files not opened",
        "candidate_group_definition": "Unordered pair of stored address-port endpoints plus stored protocol value, shared globally between source clients and dates. Label, client ID, and timestamp do not enter the identity. This is a conservative connection-key diagnostic, not proof of independent sessions or captures.",
        "source_hashes_verified": True,
        "source_files_modified": False,
        "rows_assigned": 0,
        "rows": int(sizes.sum()),
        "candidate_groups": len(groups),
        "groups_seen_at_multiple_clients": sum(v[1].bit_count() > 1 for v in groups.values()),
        "groups_spanning_multiple_dates": sum(len(v[3]) > 1 for v in groups.values()),
        "groups_with_multiple_labels": sum(v[2].bit_count() > 1 for v in groups.values()),
        "rows_in_multilabel_groups": sum(v[0] for v in groups.values() if v[2].bit_count() > 1),
        "groups_by_label": per_label,
        "group_row_quantiles": {
            str(q): float(np.quantile(sizes, q)) for q in [0, 0.5, 0.9, 0.99, 1]
        },
        "stored_protocol_counts": dict(protocols),
        "stored_port_ranges": port_ranges,
        "date_label_counts": [
            {"date": d, "label": label, "rows": n} for (d, label), n in sorted(date_labels.items())
        ],
        "files": file_summaries,
        "limits": [
            "Candidate connection keys do not establish independent attack campaigns or captures.",
            "Field names and stored protocol values require semantic verification before interpreting these groups as transport sessions.",
            "No chronological generalization or leakage-free final split is claimed.",
        ],
        "seconds": round(time.monotonic() - started, 2),
        "environment": {
            "python": platform.python_version(),
            "pandas": pd.__version__,
            "numpy": np.__version__,
        },
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    destination.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: v
                for k, v in result.items()
                if k not in ["files", "date_label_counts", "limits", "environment"]
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
