"""Confirm byte-identical CSV records within and between FLNET development files."""

from pathlib import Path
from collections import Counter
import json
from research_workspace import workspace_root

ROOT = workspace_root()
if (ROOT / "reports/dataset-audit/flnet-overlap.json").exists():
    raise FileExistsError("Existing overlap report preserved")
audit = json.loads((ROOT / "reports/dataset-audit/audit.json").read_text())
files = [f for f in audit["files"] if f["dataset"] == "flnet2023"]
assert sum((ROOT / f["path"]).stat().st_size for f in files) < 3 * 1024**3
seen = {}
pairs = Counter()
counts = {}
header = None
for item in files:
    p = ROOT / item["path"]
    n = 0
    with p.open("rb") as src:
        current = src.readline().rstrip(b"\r\n")
        if header is None:
            header = current
        assert header == current, "Header ordering differs"
        for raw in src:
            row = raw.rstrip(b"\r\n")
            assert row, "Blank physical row requires CSV-aware fallback"
            n += 1
            if row in seen:
                pairs[(seen[row], item["path"])] += 1
            else:
                seen[row] = item["path"]
    assert n == item["rows"], "Physical CSV line count differs from parsed record count"
    counts[item["path"]] = n
result = {
    "scope": "FLNET2023 DDoS and Normal development CSVs only",
    "method": "Byte equality of complete physical CSV records after removing line endings. Equal schemas and agreement of physical-line and parsed-record counts checked for every file. No fingerprint collisions involved.",
    "rows": sum(counts.values()),
    "distinct_records": len(seen),
    "repeated_records_beyond_first": sum(pairs.values()),
    "within_first_source_file_repeats": sum(v for (a, b), v in pairs.items() if a == b),
    "between_source_file_repeats": sum(v for (a, b), v in pairs.items() if a != b),
    "pairs": [
        {"first_source": a, "repeated_in": b, "records": n} for (a, b), n in sorted(pairs.items())
    ],
    "action": "No records removed; joint grouping needed before split assignment",
}
(ROOT / "reports/dataset-audit/flnet-overlap.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps({k: v for k, v in result.items() if k != "pairs"}))
