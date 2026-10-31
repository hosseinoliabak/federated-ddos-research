"""Bounded development-data audit. Held-out test contents are not profiled."""

from pathlib import Path
from collections import Counter
import csv, hashlib, json, platform, re, sys, time
from datetime import date
from concurrent.futures import ProcessPoolExecutor, as_completed
import numpy as np
import pandas as pd
from research_workspace import workspace_root

ROOT = workspace_root()
OUT = ROOT / "reports/dataset-audit"
META = {
    "src_ip",
    "dst_ip",
    "timestamp",
    "label",
    "flow id",
    "source ip",
    "destination ip",
    "simillarhttp",
    "inbound",
}


def atomic(path, obj):
    temp = path.with_suffix(path.suffix + ".partial")
    temp.write_text(json.dumps(obj, indent=2, allow_nan=False) + "\n")
    temp.replace(path)


def inspect_file(path, dataset):
    start = time.monotonic()
    rows = 0
    labels = Counter()
    missing = Counter()
    invalid = Counter()
    inf = Counter()
    hours = Counter()
    numeric_min = {}
    numeric_max = {}
    date_bad = 0
    schema = None
    hashes = []
    feature_hashes = []
    for frame in pd.read_csv(
        path, dtype=str, keep_default_na=False, chunksize=100000, on_bad_lines="error"
    ):
        frame.columns = [c.strip() for c in frame.columns]
        assert len(set(frame.columns)) == len(frame.columns), "Duplicate normalized headers"
        schema = list(frame.columns)
        n = len(frame)
        rows += n
        label = next(c for c in schema if c.lower() == "label")
        ts = next(c for c in schema if c.lower() == "timestamp")
        y = frame[label].str.strip()
        labels.update(y.value_counts().to_dict())
        times = pd.to_datetime(frame[ts].str.strip(), format="ISO8601", errors="coerce")
        date_bad += int(times.isna().sum())
        grouped = pd.DataFrame({"label": y, "hour": times.dt.floor("h")}).value_counts(dropna=False)
        hours.update(
            {
                str(a) + " | " + ("UNPARSEABLE" if pd.isna(b) else b.strftime("%Y-%m-%d %H")): int(
                    v
                )
                for (a, b), v in grouped.items()
            }
        )
        features = []
        for c in schema:
            s = frame[c].str.strip()
            null = s.str.lower().isin(["", "nan", "na", "null", "none"])
            missing[c] += int(null.sum())
            if c.lower() in META or c.lower().startswith("unnamed:"):
                continue
            features.append(c)
            numeric = pd.to_numeric(s.mask(null), errors="coerce").to_numpy(
                dtype=np.float64, na_value=np.nan
            )
            invalid[c] += int((np.isnan(numeric) & ~null.to_numpy()).sum())
            inf[c] += int(np.isinf(numeric).sum())
            finite = numeric[np.isfinite(numeric)]
            if len(finite):
                numeric_min[c] = min(numeric_min.get(c, float("inf")), float(finite.min()))
                numeric_max[c] = max(numeric_max.get(c, float("-inf")), float(finite.max()))
        record_cols = [c for c in schema if not c.lower().startswith("unnamed:")]
        hashes.append(pd.util.hash_pandas_object(frame[record_cols], index=False).to_numpy())
        feature_hashes.append(pd.util.hash_pandas_object(frame[features], index=False).to_numpy())
        if rows % 1000000 == 0:
            print(json.dumps({"file": path.name, "rows_scanned": rows}), flush=True)
    h = np.concatenate(hashes)
    fh = np.concatenate(feature_hashes)
    report = {
        "path": str(path.relative_to(ROOT)),
        "dataset": dataset,
        "rows": rows,
        "columns": schema,
        "candidate_numeric_features": features,
        "labels": dict(labels),
        "missing_by_column": {k: v for k, v in missing.items() if v},
        "non_numeric_by_column": {k: v for k, v in invalid.items() if v},
        "infinite_by_column": {k: v for k, v in inf.items() if v},
        "numeric_min": numeric_min,
        "numeric_max": numeric_max,
        "constant_numeric_columns": [c for c in numeric_min if numeric_min[c] == numeric_max[c]],
        "unparseable_timestamps": date_bad,
        "label_hour_counts": dict(sorted(hours.items())),
        "duplicate_record_hash_excess": int(rows - len(np.unique(h))),
        "duplicate_feature_hash_excess": int(rows - len(np.unique(fh))),
        "seconds": round(time.monotonic() - start, 2),
    }
    print(
        json.dumps(
            {
                "audited": path.name,
                "rows": rows,
                "labels": dict(labels),
                "seconds": report["seconds"],
            }
        ),
        flush=True,
    )
    return report, h, fh


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    if (OUT / "audit.json").exists():
        raise FileExistsError(
            "Preserve the existing audit or select a fresh workspace before rerunning"
        )
    report = {
        "status": "in_progress",
        "audit_date": date.today().isoformat(),
        "scope": "Development data only. Test CSV headers are checked separately; no test label/feature profiling or model evaluation.",
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "pandas": pd.__version__,
            "numpy": np.__version__,
        },
        "timestamp_policy": "Strict ISO8601 interpretation of stored strings; no day/month reinterpretation or calendar repair. Unparseable values are reported.",
        "duplicate_method": "64-bit pandas row fingerprints. Counts indicate candidate equality, not collision-free proof. Raw textual values are hashed; numeric formatting differences are not normalized.",
        "files": [],
        "dataset_totals": {},
        "test_headers": [],
    }
    jobs = []
    fingerprints = {ds: [[], []] for ds in ["flnet2023", "cicddos2019"]}
    for dataset in ["flnet2023", "cicddos2019"]:
        base = ROOT / "datasets" / dataset / "extracted"
        paths = (
            sorted(base.glob("DDoS/*.csv")) + sorted(base.glob("Normal/*.csv"))
            if dataset == "flnet2023"
            else sorted(base.glob("01-12/*.csv"))
        )
        assert paths
        jobs.extend((path, dataset) for path in paths)
        tests = (
            sorted(base.glob("TEST/*.csv"))
            if dataset == "flnet2023"
            else sorted(base.glob("03-11/*.csv"))
        )
        for path in tests:
            with path.open(newline="", encoding="utf-8-sig") as f:
                header = next(csv.reader(f))
            report["test_headers"].append(
                {
                    "path": str(path.relative_to(ROOT)),
                    "columns": [c.strip() for c in header],
                    "contents_profiled": False,
                }
            )
    report["workers"] = 3
    atomic(OUT / "audit.json", report)
    with ProcessPoolExecutor(max_workers=3) as pool:
        pending = {
            pool.submit(inspect_file, path, ds): ds
            for path, ds in sorted(jobs, key=lambda x: x[0].stat().st_size, reverse=True)
        }
        for future in as_completed(pending):
            ds = pending.pop(future)
            item, h, fh = future.result()
            report["files"].append(item)
            fingerprints[ds][0].append(h)
            fingerprints[ds][1].append(fh)
            atomic(OUT / "audit.json", report)
    for dataset, (hs, fs) in fingerprints.items():
        h = np.concatenate(hs)
        fh = np.concatenate(fs)
        total = len(h)
        report["dataset_totals"][dataset] = {
            "rows": total,
            "files": len(hs),
            "duplicate_record_hash_excess": int(total - len(np.unique(h))),
            "duplicate_feature_hash_excess": int(total - len(np.unique(fh))),
        }
        hs.clear()
        fs.clear()
    report["files"].sort(key=lambda f: (f["dataset"], f["path"]))
    report["status"] = "complete"
    atomic(OUT / "audit.json", report)
    print(json.dumps({"complete": report["dataset_totals"]}), flush=True)


if __name__ == "__main__":
    main()
