"""Confirm full-row equality in the bounded FLNET2023 TCP source file."""

from pathlib import Path
import json
import pandas as pd
from research_workspace import workspace_root

ROOT = workspace_root()
if (ROOT / "reports/dataset-audit/flnet-tcp-duplicates.json").exists():
    raise FileExistsError("Existing duplicate report preserved")
p = ROOT / "datasets/flnet2023/extracted/DDoS/Dataset-10-TCP.csv"
assert p.stat().st_size < 1024**3, "This bounded confirmation is for the TCP CSV only"
f = pd.read_csv(p, dtype=str, keep_default_na=False, on_bad_lines="error")
result = {
    "file": str(p.relative_to(ROOT)),
    "rows": len(f),
    "columns": len(f.columns),
    "exact_duplicate_rows_beyond_first": int(f.duplicated(keep="first").sum()),
    "method": "pandas full-row equality on original CSV string fields, including metadata and labels",
    "action": "No rows removed",
}
(ROOT / "reports/dataset-audit/flnet-tcp-duplicates.json").write_text(
    json.dumps(result, indent=2) + "\n"
)
print(json.dumps(result))
