"""Profile FLNET development features and run bounded, exploratory one-feature checks."""

from collections import Counter
from pathlib import Path
import argparse
import hashlib
import json
import platform
import re
import time

import numpy as np
import pandas as pd
import sklearn
from sklearn.metrics import average_precision_score, confusion_matrix
from sklearn.tree import DecisionTreeClassifier

from research_workspace import contained_path, workspace_root

VERSION = "feature-validity-v2"
LABELS = {"Normal": 0, "DDoS-bot": 1, "DDoS-dyn": 1, "DDoS-stomp": 1, "DDoS-tcp": 1}
NONNUMERIC = {"src_ip", "dst_ip", "timestamp", "label"}
CHECK_FEATURES = ("flow_duration", "tot_fwd_pkts", "tot_bwd_pkts")
SOURCE_PATTERN = re.compile(
    r"datasets/flnet2023/extracted/(?:DDoS|Normal)/Dataset-\d+(?:-[A-Za-z]+)?\.csv"
)


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def dump(path, obj):
    path.write_text(json.dumps(obj, indent=2, allow_nan=False) + "\n")


def approved_sources(inventory):
    sources = [
        item
        for item in inventory["files"]
        if item["dataset"] == "flnet2023" and item["source_role"] == "development"
    ]
    if len(sources) != 14 or len({item["path"] for item in sources}) != 14:
        raise ValueError("Expected the fourteen distinct FLNET DDoS/Normal development files")
    if any(not SOURCE_PATTERN.fullmatch(item["path"]) for item in sources):
        raise ValueError("Source outside the development allowlist")
    if inventory.get("unmapped_development_labels", {}).get("flnet2023"):
        raise ValueError("Unmapped development labels require review")
    return sorted(sources, key=lambda item: item["path"])


def add_profile(state, frame):
    """Merge full-development extrema and counts without retaining the raw rows."""
    unknown = set(frame["label"]) - set(LABELS)
    if unknown:
        raise ValueError("Unmapped observed development label")
    for label, group in frame.groupby("label", sort=True):
        for name in group.columns:
            if name in NONNUMERIC:
                continue
            values = pd.to_numeric(group[name], errors="coerce").to_numpy(dtype=float)
            finite = values[np.isfinite(values)]
            key = (label, name)
            item = state.setdefault(
                key,
                dict(rows=0, finite=0, nonfinite=0, negative=0, zero=0, minimum=None, maximum=None),
            )
            item["rows"] += len(values)
            item["finite"] += len(finite)
            item["nonfinite"] += int((~np.isfinite(values)).sum())
            item["negative"] += int((finite < 0).sum())
            item["zero"] += int((finite == 0).sum())
            if len(finite):
                lo, hi = float(finite.min()), float(finite.max())
                item["minimum"] = lo if item["minimum"] is None else min(lo, item["minimum"])
                item["maximum"] = hi if item["maximum"] is None else max(hi, item["maximum"])


def rate_consistency(frame):
    """Check stored arithmetic only; physical units and extractor identity remain separate."""
    required = {"flow_duration", "flow_pkts_s", "tot_fwd_pkts", "tot_bwd_pkts"}
    if not required <= set(frame.columns):
        return {"unavailable_rows": len(frame)}
    n = frame[list(required)].apply(pd.to_numeric, errors="raise")
    duration = n.flow_duration.to_numpy(dtype=float)
    packets = (n.tot_fwd_pkts + n.tot_bwd_pkts).to_numpy(dtype=float)
    rate = n.flow_pkts_s.to_numpy(dtype=float)
    eligible = (duration > 0) & (packets > 0) & np.isfinite(duration + packets + rate)
    equal = np.isclose(
        duration[eligible] * rate[eligible], 1e6 * packets[eligible], rtol=1e-6, atol=1e-6
    )
    return dict(
        eligible_rows=int(eligible.sum()),
        matching_factor_1e6=int(equal.sum()),
        nonmatching_rows=int((~equal).sum()),
        zero_duration_rows=int((duration == 0).sum()),
        zero_duration_zero_rate_rows=int(((duration == 0) & (rate == 0)).sum()),
    )


def score(target, prediction, probability):
    tn, fp, fn, tp = [int(v) for v in confusion_matrix(target, prediction, labels=[0, 1]).ravel()]
    return dict(
        rows=len(target),
        tn=tn,
        fp=fp,
        fn=fn,
        tp=tp,
        recall=tp / (tp + fn) if tp + fn else None,
        false_positive_rate=fp / (fp + tn) if fp + tn else None,
        average_precision=float(average_precision_score(target, probability))
        if np.unique(target).size == 2
        else None,
    )


def one_feature_checks(data):
    """Fit each prespecified stump on fit rows only; validation never chooses the threshold."""
    if set(data["_role"]) != {"fit", "validation"}:
        raise ValueError("Expected only fit and validation roles")
    if not set(data["label"]) <= set(LABELS):
        raise ValueError("Unknown label in prepared records")
    if data.groupby("_group_id")["_role"].nunique().max() != 1:
        raise ValueError("Candidate group crosses roles")
    fit = data["_role"].eq("fit").to_numpy()
    y = data["label"].map(LABELS).to_numpy(dtype=int)
    if set(y[fit]) != {0, 1}:
        raise ValueError("Both labels are needed in fitting rows")
    results = []
    for name in CHECK_FEATURES:
        if name not in data:
            continue
        x = pd.to_numeric(data[name], errors="raise").to_numpy(dtype=float).reshape(-1, 1)
        if not np.isfinite(x).all():
            raise ValueError("Nonfinite input to one-feature diagnostic")
        estimator = DecisionTreeClassifier(max_depth=1, random_state=20261031)
        estimator.fit(x[fit], y[fit])
        prediction = estimator.predict(x)
        probability = estimator.predict_proba(x)[:, list(estimator.classes_).index(1)]
        split = int(estimator.tree_.feature[0]) >= 0
        summary = dict(
            feature=name,
            split=split,
            threshold=float(estimator.tree_.threshold[0]) if split else None,
            fit=score(y[fit], prediction[fit], probability[fit]),
            validation=score(y[~fit], prediction[~fit], probability[~fit]),
        )
        summary["validation_by_label"] = {
            label: score(y[m], prediction[m], probability[m])
            for label in sorted(set(data.loc[~fit, "label"]))
            if (m := (~fit & data["label"].eq(label).to_numpy())).any()
        }
        results.append(summary)
    return results


def read_prepared(root, name, sources):
    if not re.fullmatch(r"engineering-smoke-v[0-9]+(?:-portable)?", name):
        raise ValueError("Use a named engineering run")
    run = contained_path(root, "runs/" + name)
    complete = json.loads((run / "COMPLETE.json").read_text())
    if complete.get("status") != "complete":
        raise ValueError("Engineering run is incomplete")
    for filename in ("selected-records.parquet", "preparation.json", "config.json"):
        if sha(run / filename) != complete["files"][filename]:
            raise ValueError("Prepared artifact hash mismatch")
    preparation = json.loads((run / "preparation.json").read_text())
    expected = {item["path"]: item["sha256"] for item in sources}
    observed = {item["path"]: item["sha256"] for item in preparation["sources"]}
    if expected != observed or preparation.get("reserved_test_opened") is not False:
        raise ValueError("Prepared data provenance does not match approved development sources")
    data = pd.read_parquet(run / "selected-records.parquet")
    if set(data["_source_path"]) != set(expected):
        raise ValueError("Unexpected source in prepared records")
    return data, dict(
        run=name,
        completion_sha256=sha(run / "COMPLETE.json"),
        selected_records_sha256=complete["files"]["selected-records.parquet"],
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engineering-run", default="engineering-smoke-v1-portable")
    args = parser.parse_args()
    root = workspace_root()
    out = contained_path(root, "reports/development-preparation/" + VERSION)
    if out.exists():
        raise FileExistsError("Keep completed/partial diagnostics; use a new reviewed version")
    inventory_path = root / "config/split-proposal.json"
    sources = approved_sources(json.loads(inventory_path.read_text()))
    data, prepared = read_prepared(root, args.engineering_run, sources)
    out.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()
    profiles, labels, dates, rates = {}, Counter(), Counter(), Counter()
    file_reports, columns = [], None
    for item in sources:
        path = contained_path(root, item["path"])
        if sha(path) != item["sha256"]:
            raise ValueError("Development source hash changed")
        counts, local_rates, local_dates = Counter(), Counter(), Counter()
        for frame in pd.read_csv(
            path, dtype=str, keep_default_na=False, chunksize=100000, on_bad_lines="error"
        ):
            if columns is None:
                columns = list(frame.columns)
            if columns != list(frame.columns):
                raise ValueError("Inconsistent source schema")
            add_profile(profiles, frame)
            counts.update(frame["label"])
            parsed = pd.to_datetime(frame["timestamp"], format="%Y-%m-%d %H:%M:%S", errors="raise")
            local_dates.update(zip(parsed.dt.strftime("%Y-%m-%d"), frame["label"]))
            local_rates.update(rate_consistency(frame))
        # Verify after profiling too; input data remain read-only throughout.
        if sha(path) != item["sha256"]:
            raise ValueError("Development source changed during profiling")
        labels.update(counts)
        dates.update(local_dates)
        rates.update(local_rates)
        file_reports.append(
            dict(
                path=item["path"],
                sha256=item["sha256"],
                client_id=item["client_id"],
                rows=sum(counts.values()),
                labels=counts,
            )
        )
        print(json.dumps(dict(source=path.name, rows=sum(counts.values()))), flush=True)
    rows = [
        dict(label=label, feature=name, **values)
        for (label, name), values in sorted(profiles.items())
    ]
    pd.DataFrame(rows).to_csv(out / "feature-profiles.csv", index=False)
    constants = {}
    for name in columns:
        stats = [v for (label, feature), v in profiles.items() if feature == name]
        if stats and not sum(v["nonfinite"] for v in stats):
            lo, hi = min(v["minimum"] for v in stats), max(v["maximum"] for v in stats)
            if lo == hi:
                constants[name] = lo
    summary = dict(
        schema=1,
        version=VERSION,
        purpose="exploratory_feature_validity_not_confirmatory",
        scope="Four DDoS and ten Normal FLNET development CSVs only",
        source_manifest_sha256=sha(inventory_path),
        sources=file_reports,
        rows=sum(labels.values()),
        label_counts=dict(labels),
        columns=columns,
        constant_numeric_fields=constants,
        negative_fields=[r for r in rows if r["negative"]],
        nonfinite_fields=[r for r in rows if r["nonfinite"]],
        date_label_counts=[
            dict(date=d, label=label, rows=count) for (d, label), count in sorted(dates.items())
        ],
        packet_rate_arithmetic=dict(rates),
        duration_by_label=[r for r in rows if r["feature"] == "flow_duration"],
        packet_counts_by_label=[
            r for r in rows if r["feature"] in ("tot_fwd_pkts", "tot_bwd_pkts")
        ],
        prepared_subset=prepared,
        one_feature_checks=one_feature_checks(data),
        reserved_test_opened=False,
        raw_sources_modified=False,
        synthetic_only=(root / "SYNTHETIC_ONLY.json").exists(),
        environment=dict(
            python=platform.python_version(),
            numpy=np.__version__,
            pandas=pd.__version__,
            sklearn=sklearn.__version__,
        ),
        seconds=round(time.monotonic() - start, 3),
        limits=[
            "Descriptive profiling uses development labels; it is exploratory, not a final feature-selection protocol.",
            "Each of three named feature checks fits one depth-one tree on existing fit rows only.",
            "Validation is reused from the engineering check; diagnostics do not estimate final generalization.",
            "No independent capture, cross-day, cross-organization, or optimizer comparison is established.",
            "Stored arithmetic does not identify the extractor version or independently validate physical units.",
            "No feature removal, relabeling, rescaling, deduplication, or final split is performed.",
        ],
    )
    dump(out / "summary.json", summary)
    dump(
        out / "COMPLETE.json",
        dict(
            status="complete",
            version=VERSION,
            sources_sha256={
                "scripts/audit_feature_validity.py": sha(Path(__file__)),
                "scripts/research_workspace.py": sha(
                    Path(__file__).with_name("research_workspace.py")
                ),
            },
            dependency_lock_sha256=sha(Path(__file__).resolve().parents[1] / "uv.lock"),
            files={name: sha(out / name) for name in ("feature-profiles.csv", "summary.json")},
        ),
    )
    print(json.dumps(dict(status="complete", rows=summary["rows"], reserved_test_opened=False)))


if __name__ == "__main__":
    main()
