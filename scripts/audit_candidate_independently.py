"""Prespecified independent parser, integer-range and multiplicity audit; no fit."""
from __future__ import annotations
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
from pathlib import Path
import argparse
import csv
import hashlib
import json
import os
import platform
import resource
import subprocess
import sys
import time
import numpy as np
import pandas as pd
import load_grouped_candidate as L
from purpose_data_view import PurposeDataset
from research_workspace import workspace_root

VERSION = "loader-independent-audit-v1"
SEED = "prespecified-source-row-audit-20261112-v1"
EXTRA_DRAWS = 7
PARSER_CHUNK = 10000


def now(): return datetime.now(timezone.utc).isoformat()
def require(ok, reason):
    if not ok: raise ValueError(reason)


def directory(root, name):
    p = Path(name)
    if not p.is_absolute(): p = root / p
    require(p.is_relative_to(root / "reports/development-preparation") and p.resolve() == p,
            "Prepared/output directory must remain in development reports without symlinks")
    return p


def code_context():
    root = Path(__file__).resolve().parents[1]
    result = L.code_context()
    result["audit_source_sha256"] = {n: L.sha(root / "scripts" / n) for n in
                                    ["audit_candidate_independently.py", "purpose_data_view.py"]}
    return result


def checked_metadata(prepared):
    require(not (prepared / "COMPLETE.json").is_symlink(), "Symlinked loader seal")
    seal = L.read_json(prepared / "COMPLETE.json")
    require(seal["version"] == L.VERSION and seal["status"] == "complete_engineering_loader", "Incomplete loader output")
    values = {}
    for name in ("summary.json", "schema.json", "source-map.json"):
        p = prepared / name; entry = seal["artifacts"][name]
        require(p.resolve() == p and p.is_file() and p.stat().st_size == entry["bytes"]
                and L.sha(p) == entry["sha256"], "Loader metadata seal differs")
        values[name] = L.read_json(p)
    return seal, values


def make_plan(root, prepared_name, contract, registry, contract_sha, registry_sha):
    """Metadata only: called before any feature-array or source-row access."""
    root = Path(root).resolve(); prepared = directory(root, prepared_name)
    manifest, policy, header, features, sources, exclusions, pins = L.verify_controls(
        root, contract, registry, contract_sha, registry_sha)
    seal, meta = checked_metadata(prepared); summary = meta["summary.json"]
    require(summary["input_sha256"] == pins and summary["assignment_sha256"] == manifest["assignment_sha256"], "Loader/control binding differs")
    require(meta["schema.json"]["features"] == features and meta["schema.json"]["roles"] == L.ROLE_IDS, "Loader feature/role schema differs")
    chunk = summary["chunk_rows"]; require(type(chunk) is int and chunk > 0, "Invalid original chunk size")
    offset = 0; entries = []
    for sid, source in enumerate(summary["sources"]):
        require({k: source[k] for k in ("path", "sha256", "client_id")} == sources[sid]
                and source["source_id"] == sid and type(source["rows"]) is int and source["rows"] > 0,
                "Source metadata order/count differs")
        n = source["rows"]; require(n == next(q["rows"] for q in manifest["sources"] if q["path"] == source["path"]), "Source count differs from candidate")
        chosen = defaultdict(set)
        chosen[0].add("first"); chosen[n - 1].add("last")
        for boundary in range(chunk, n, chunk):
            chosen[boundary - 1].add("before_source_write_boundary"); chosen[boundary].add("after_source_write_boundary")
        first_global = ((offset // chunk) + 1) * chunk
        for boundary in range(first_global, offset + n, chunk):
            local = boundary - offset
            chosen[local - 1].add("before_global_array_boundary"); chosen[local].add("after_global_array_boundary")
        for draw in range(EXTRA_DRAWS):
            h = hashlib.sha256((SEED + "|" + source["path"] + "|" + str(draw)).encode()).digest()
            chosen[int.from_bytes(h, "big") % n].add("deterministic_hash_draw")
        entries.append(source | {"output_offset": offset, "samples":
                       [{"source_row": row, "reasons": sorted(reasons)} for row, reasons in sorted(chosen.items())]})
        offset += n
    require(len(entries) == 14 and offset == manifest["rows"], "Expected full fourteen-source candidate")
    return {"version": VERSION, "seed": SEED, "extra_hash_draws_per_source": EXTRA_DRAWS,
            "sampling_basis": "source identity/count/output offset only; no labels, feature values or outcomes",
            "source_row_origin": "zero-based parsed data row excluding header", "rows": offset,
            "features": features, "header": header, "original_loader_chunk_rows": chunk,
            "independent_parser_chunk_rows": PARSER_CHUNK,
            "input_pins": pins, "assignment_sha256": manifest["assignment_sha256"],
            "prepared_seal_sha256": L.sha(prepared / "COMPLETE.json"), "sources": entries,
            "exclusions": exclusions, "rows_by_role": manifest["rows_by_role"],
            "expected_groups": manifest["candidate_groups"],
            "expected_shared_observer_groups": manifest["groups_seen_at_multiple_observers"],
            "code": code_context()}


def save_plan(path, plan):
    with Path(path).open("x") as f: json.dump(plan, f, indent=2, allow_nan=False); f.write("\n")


def c_reader(binary, columns, dtypes, chunk=PARSER_CHUNK):
    return pd.read_csv(binary, engine="c", usecols=columns, dtype=dtypes,
                       float_precision="round_trip", chunksize=chunk, encoding="utf-8-sig",
                       keep_default_na=False, na_filter=False, skip_blank_lines=False,
                       on_bad_lines="error", index_col=False, compression=None)


def source_check(root, item, binary):
    before = os.fstat(binary.fileno()); digest = L.digest_stream(binary)
    require(digest == item["sha256"], "Source hash mismatch before independent parse")
    binary.seek(0)
    return before, digest


def source_finish(root, item, binary, before):
    binary.seek(0); digest = L.digest_stream(binary); after = os.fstat(binary.fileno())
    require(digest == item["sha256"], "Source hash mismatch after independent parse")
    require(L.fingerprint(before) == L.fingerprint(after) == L.fingerprint(L.source_path(root, item["path"]).stat()),
            "Source fingerprint changed")
    return digest


def compare_samples(root, plan, X, records):
    features = plan["features"]; columns = features + ["timestamp"]; results = []
    for source in plan["sources"]:
        selected = {q["source_row"] for q in source["samples"]}; checked = []; count = 0
        with L.open_source(root, source) as binary:
            before, first_hash = source_check(root, source, binary)
            actual_header = pd.read_csv(binary, engine="c", nrows=0, encoding="utf-8-sig").columns.tolist()
            require(actual_header == plan["header"], "Independent stored header differs"); binary.seek(0)
            with c_reader(binary, columns, {**dict.fromkeys(features, "float64"), "timestamp": str}) as reader:
                for frame in reader:
                    values = frame[features].to_numpy(dtype="<f8")
                    require(bool(np.isfinite(values).all()), "Nonfinite independent numeric input")
                    for row in sorted(q for q in selected if count <= q < count + len(frame)):
                        pos = source["output_offset"] + row; record = records[pos]
                        require(int(record["source_id"]) == source["source_id"] and int(record["source_row"]) == row,
                                "Sample source-row addressing differs")
                        independent = np.ascontiguousarray(values[row - count], dtype="<f8")
                        require(independent.tobytes() == X[pos].tobytes(),
                                f"Independent float64 sample differs at source {source['source_id']} row {row}")
                        stamp = str(frame["timestamp"].iloc[row - count]).strip().encode("ascii")
                        require(stamp == bytes(record["stored_timestamp"]).rstrip(b"\0"),
                                f"Independent timestamp differs at source {source['source_id']} row {row}")
                        checked.append(row)
                    count += len(frame)
            require(count == source["rows"] and set(checked) == selected, "Independent row count/sample coverage differs")
            last_hash = source_finish(root, source, binary, before)
        results.append({"source_id": source["source_id"], "path": source["path"], "rows_parsed": count,
                        "sampled_rows_checked": len(checked), "sample_id_sha256": hashlib.sha256(json.dumps(checked).encode()).hexdigest(),
                        "sha256_before": first_hash, "sha256_after": last_hash,
                        "exact_float64_and_stripped_timestamp_match": True})
    return {"parser": "pandas C engine, explicit float64, float_precision=round_trip", "pandas_version": pd.__version__,
            "sources": results, "total_rows_parsed": sum(q["rows_parsed"] for q in results),
            "sampled_rows_checked": sum(q["sampled_rows_checked"] for q in results), "sample_values_written": False}


def feature_ranges(X, features, chunk=PARSER_CHUNK):
    d = len(features); minimum = np.full(d, np.inf); maximum = np.full(d, -np.inf)
    integer_count = np.zeros(d, dtype=np.int64); zero_count = integer_count.copy(); negative_zero = integer_count.copy()
    max_abs_integer = np.zeros(d)
    for start in range(0, len(X), chunk):
        values = X[start:start + chunk]; require(bool(np.isfinite(values).all()), "Nonfinite sealed features")
        minimum = np.minimum(minimum, values.min(axis=0)); maximum = np.maximum(maximum, values.max(axis=0))
        integral = values == np.trunc(values); integer_count += integral.sum(axis=0)
        zero = values == 0; zero_count += zero.sum(axis=0); negative_zero += (zero & np.signbit(values)).sum(axis=0)
        max_abs_integer = np.maximum(max_abs_integer, np.where(integral, np.abs(values), 0).max(axis=0))
    return [{"feature": name, "rows": len(X), "minimum": float(minimum[j]), "maximum": float(maximum[j]),
             "minimum_float64_hex": float(minimum[j]).hex(), "maximum_float64_hex": float(maximum[j]).hex(),
             "integral_float64_rows": int(integer_count[j]), "nonintegral_float64_rows": len(X) - int(integer_count[j]),
             "all_stored_values_integral": bool(integer_count[j] == len(X)),
             "max_abs_integral_value_exact_int": int(max_abs_integer[j]), "zero_rows": int(zero_count[j]),
             "negative_zero_rows": int(negative_zero[j]),
             "at_or_above_2pow53_integer_risk": bool(max_abs_integer[j] >= 2**53), "physical_units_verified": False}
            for j, name in enumerate(features)]


def inspect_integer_tokens(root, plan, ranges):
    flagged = [q["feature"] for q in ranges if q["at_or_above_2pow53_integer_risk"]]
    if not flagged: return {"status": "no_stored_integer_candidates_at_or_above_2pow53", "features": [], "extra_source_passes": 0}
    result = {name: Counter() for name in flagged}; example_ids = {name: [] for name in flagged}; receipts = []
    for source in plan["sources"]:
        count = 0
        with L.open_source(root, source) as binary:
            before, h1 = source_check(root, source, binary)
            with c_reader(binary, flagged, dict.fromkeys(flagged, str)) as reader:
                for frame in reader:
                    for name in flagged:
                        for local, token in enumerate(frame[name]):
                            try: value = Decimal(str(token).strip())
                            except InvalidOperation as exc: raise ValueError("Invalid original decimal token") from exc
                            require(value.is_finite(), "Nonfinite original decimal token")
                            result[name]["tokens"] += 1
                            if value == value.to_integral_value():
                                result[name]["integer_tokens"] += 1
                                if abs(value) >= Decimal(2**53): result[name]["at_or_above_2pow53"] += 1
                                if Decimal.from_float(float(value)) != value:
                                    result[name]["integer_conversion_loss"] += 1
                                    if len(example_ids[name]) < 8: example_ids[name].append([source["source_id"], count + local])
                            else: result[name]["noninteger_tokens"] += 1
                    count += len(frame)
            require(count == source["rows"], "Token pass count differs")
            h2 = source_finish(root, source, binary, before)
        receipts.append({"source_id": source["source_id"], "sha256_before": h1, "sha256_after": h2})
    return {"status": "integer_conversion_loss_detected" if any(q["integer_conversion_loss"] for q in result.values()) else "flagged_tokens_checked_no_integer_loss",
            "features": [{"feature": k, **dict(v), "example_source_row_identities_only": example_ids[k]} for k, v in result.items()],
            "extra_source_passes": 14, "source_checks": receipts, "tokens_written": False}


def multiplicities(X, records, out):
    """Exact finite float64 vector equality, with signed zero canonicalized.

    Full bytes, not a numeric-vector hash, key the per-group vector dictionary.
    Python dictionary hash collisions are resolved by full bytes equality.
    """
    out = Path(out); keys = np.ascontiguousarray(records["group_sha256"])
    order = np.argsort(keys, kind="stable"); ordered_keys = keys[order]
    starts = np.r_[0, np.flatnonzero(ordered_keys[1:] != ordered_keys[:-1]) + 1, len(order)]
    totals = Counter(); histogram = Counter(); observer_hist = Counter(); role_totals = Counter()
    with (out / "per-key.csv").open("x", newline="") as kf, (out / "per-key-observer.csv").open("x", newline="") as of:
        kw = csv.writer(kf); ow = csv.writer(of)
        kw.writerow(["stored_key_sha256", "role_id", "rows", "observers", "distinct_numeric_vectors", "cross_observer_identical_record_pairs"])
        ow.writerow(["stored_key_sha256", "role_id", "observer_id", "rows", "distinct_numeric_vectors", "all_features_identical_within_key_observer"])
        for begin, end in zip(starts[:-1], starts[1:]):
            positions = order[begin:end]; n = len(positions); group = bytes(ordered_keys[begin]).decode("ascii")
            require(L.HEX.fullmatch(group), "Malformed stored key digest")
            roles = records["role_id"][positions]; require(bool((roles == roles[0]).all()), "Stored key spans global roles")
            rid = int(roles[0]); owners = records["observer_id"][positions]
            by_owner = Counter(int(v) for v in owners); vectors = {}
            for pos, owner in zip(positions, owners):
                row = X[pos]; require(bool(np.isfinite(row).all()), "Nonfinite vector during exact equality check")
                # Numeric equality identifies +0 and -0; all other finite f8 values have unique bits.
                if bool(((row == 0) & np.signbit(row)).any()):
                    row = row.copy(); row[row == 0] = 0.0
                token = row.tobytes(); counts = vectors.setdefault(token, Counter()); counts[int(owner)] += 1
            cross_pairs = 0; distinct_by_owner = Counter(); within_pairs = 0
            for counts in vectors.values():
                count = sum(counts.values()); cross_pairs += (count * count - sum(c * c for c in counts.values())) // 2
                within_pairs += sum(c * (c - 1) // 2 for c in counts.values())
                distinct_by_owner.update(counts.keys())
            kw.writerow([group, rid, n, len(by_owner), len(vectors), cross_pairs])
            for owner, count in sorted(by_owner.items()):
                ow.writerow([group, rid, owner, count, distinct_by_owner[owner], distinct_by_owner[owner] == 1])
                observer_hist[(owner, count)] += 1
                totals["key_observer_pairs"] += 1
                totals["key_observer_pairs_with_repeated_rows"] += count > 1
                totals["repeated_key_observer_pairs_with_feature_variation"] += count > 1 and distinct_by_owner[owner] > 1
            totals["keys"] += 1; totals["rows"] += n; totals["keys_with_repeated_rows"] += n > 1
            totals["repeated_keys_with_feature_variation"] += n > 1 and len(vectors) > 1
            totals["multi_observer_keys"] += len(by_owner) > 1
            totals["multi_observer_keys_all_features_identical"] += len(by_owner) > 1 and len(vectors) == 1
            totals["keys_with_any_cross_observer_exact_numeric_copy"] += cross_pairs > 0
            totals["cross_observer_identical_record_pairs"] += cross_pairs
            totals["within_observer_identical_record_pairs"] += within_pairs
            histogram[n] += 1; role_totals[rid] += n
    return {"totals": dict(totals), "rows_by_role_id": dict(role_totals),
            "key_row_multiplicity_histogram": [{"rows_per_key": n, "keys": count} for n, count in sorted(histogram.items())],
            "observer_key_multiplicity_histogram": [{"observer_id": o, "rows_per_key_observer": n, "keys": count}
                                                     for (o, n), count in sorted(observer_hist.items())],
            "equality": "all 73 finite stored float64 values exactly numerically equal; signed zeros equal; full vector bytes compared, no vector-hash-only inference",
            "unit_limit": "Stored unordered endpoint-pair/protocol key and numeric equality do not identify physical episodes or independence.",
            "records_deduplicated_or_reweighted": False}


def environment():
    hardware = {}
    for name in ("machdep.cpu.brand_string", "hw.memsize", "hw.physicalcpu", "hw.logicalcpu"):
        r = subprocess.run(["sysctl", "-n", name], capture_output=True, text=True)
        hardware[name] = r.stdout.strip() if r.returncode == 0 else "unavailable"
    return {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__,
            "os": platform.platform(), "machine": platform.machine(), "hardware": hardware,
            "python_workers": 1, "thread_environment": {k: os.environ.get(k) for k in
             ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS")},
            "actual_os_thread_count": "not measured", "energy": "not measured"}


def run(root, prepared_name, plan_path, plan_sha, output_name, contract, registry, contract_sha, registry_sha):
    root = Path(root).resolve(); prepared = directory(root, prepared_name); out = directory(root, output_name)
    out.mkdir(parents=True, exist_ok=False); start = time.monotonic(); phases = {}; progress = "controls"
    base = {"version": VERSION, "status": "running", "started_utc": now(), "pid": os.getpid(),
            "code": code_context(), "environment": environment(), "reserved_sources_opened_or_hashed": False,
            "model_fit_score_calibration_or_selection_performed": False, "scaler_fitted": False,
            "integer_conversion_policy": "audit only; no repairs", "plan_sha256": plan_sha}
    L.write_json(out / "run-state.json", base)
    def checkpoint():
        L.write_json(out / "run-state.json", base | {"phase": progress, "phase_seconds": phases, "elapsed_monotonic_seconds": time.monotonic() - start})
    try:
        require(L.sha(plan_path) == plan_sha, "Prespecified sample-plan hash differs")
        plan = L.read_json(plan_path)
        require(plan == make_plan(root, prepared_name, contract, registry, contract_sha, registry_sha), "Prespecified plan/control/code binding differs")
        phases[progress] = time.monotonic() - start
        t = time.monotonic(); progress = "sealed_view_open_and_identity_validation"; checkpoint()
        view = PurposeDataset(prepared, expected_features=tuple(plan["features"]), candidate_sha256=plan["input_pins"]["candidate"], assignment_sha256=plan["assignment_sha256"])
        phases[progress] = time.monotonic() - t
        t = time.monotonic(); progress = "independent_source_parse_and_sample_check"; checkpoint()
        samples = compare_samples(root, plan, view._X, view._records)
        L.write_json(out / "independent-samples.json", samples); phases[progress] = time.monotonic() - t
        t = time.monotonic(); progress = "full_feature_range_and_integrality"; checkpoint()
        ranges = feature_ranges(view._X, plan["features"])
        L.write_json(out / "feature-ranges.json", ranges); phases[progress] = time.monotonic() - t
        t = time.monotonic(); progress = "flagged_original_decimal_tokens"; checkpoint()
        tokens = inspect_integer_tokens(root, plan, ranges)
        L.write_json(out / "integer-token-audit.json", tokens); phases[progress] = time.monotonic() - t
        t = time.monotonic(); progress = "full_key_observer_exact_numeric_multiplicity"; checkpoint()
        multiplicity = multiplicities(view._X, view._records, out)
        require(multiplicity["totals"]["rows"] == plan["rows"] and multiplicity["totals"]["keys"] == plan["expected_groups"]
                and multiplicity["totals"]["multi_observer_keys"] == plan["expected_shared_observer_groups"], "Multiplicity row/key totals differ")
        require({name: multiplicity["rows_by_role_id"][rid] for name, rid in L.ROLE_IDS.items()} == plan["rows_by_role"], "Multiplicity roles differ")
        L.write_json(out / "multiplicity-summary.json", multiplicity); phases[progress] = time.monotonic() - t
        t = time.monotonic(); progress = "final_input_seal_and_control_verification"; checkpoint()
        # Recheck every sealed loader artifact after the audit; no mutation assumption is absolute.
        seal = L.read_json(prepared / "COMPLETE.json")
        require(L.sha(prepared / "COMPLETE.json") == plan["prepared_seal_sha256"], "Loader seal changed")
        for name, entry in seal["artifacts"].items():
            p = prepared / name
            require(p.resolve() == p and p.stat().st_size == entry["bytes"] and L.sha(p) == entry["sha256"], "Retained loader artifact changed")
        require(make_plan(root, prepared_name, contract, registry, contract_sha, registry_sha) == plan, "Control/code metadata changed")
        phases[progress] = time.monotonic() - t
        status = "complete_audit_with_integer_loss_finding" if tokens["status"] == "integer_conversion_loss_detected" else "complete_independent_engineering_audit"
        result = base | {"status": status, "finished_utc": now(), "elapsed_monotonic_seconds": time.monotonic() - start,
                 "phase_seconds": phases, "source_rows_parsed": samples["total_rows_parsed"],
                 "samples_checked": samples["sampled_rows_checked"], "source_count": 14,
                 "rows_by_role": plan["rows_by_role"], "assignment_sha256_unchanged": plan["assignment_sha256"],
                 "feature_range_count": len(ranges), "integer_token_status": tokens["status"],
                 "multiplicity_totals": multiplicity["totals"], "exclusions": plan["exclusions"],
                 "peak_process_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if platform.system() == "Darwin" else 1024),
                 "elapsed_boundary": "After new output directory creation through final retained-input seal/control checks; final output hashes and receipt/seal writes excluded.",
                 "limits": ["Independent numeric/timestamp comparison is sampled, not every source row.",
                            "Full feature integrality and multiplicity describe this stored development candidate, not physical units or episodes.",
                            "No weighting/deduplication, fitting, model selection, calibration or model scoring.",
                            "Hashes/fingerprints and read-only API are cooperative integrity controls, not absolute protection against a malicious local writer."]}
        L.write_json(out / "summary.json", result); L.write_json(out / "run-state.json", result)
        artifacts = {p.name: {"sha256": L.sha(p), "bytes": p.stat().st_size} for p in out.iterdir() if p.is_file()}
        L.write_json(out / "COMPLETE.json", {"version": VERSION, "status": status, "artifacts": artifacts})
        return result
    except Exception as exc:
        result = base | {"status": "failed_independent_audit", "finished_utc": now(), "elapsed_monotonic_seconds": time.monotonic() - start,
                         "phase_seconds": phases, "failed_phase": progress, "error_type": type(exc).__name__, "error": str(exc)}
        L.write_json(out / "FAILED.json", result); L.write_json(out / "run-state.json", result)
        raise


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument("phase", choices=["plan", "run"])
    for name in ("prepared", "contract", "registry", "contract-sha256", "registry-sha256", "plan"):
        p.add_argument("--" + name, required=True)
    p.add_argument("--plan-sha256"); p.add_argument("--output"); args = p.parse_args(); root = workspace_root()
    kw = dict(root=root, prepared_name=args.prepared, contract=args.contract, registry=args.registry,
              contract_sha=args.contract_sha256, registry_sha=args.registry_sha256)
    plan_path = L.control_path(root, args.plan)
    if args.phase == "plan":
        save_plan(plan_path, make_plan(**kw)); print(json.dumps({"plan_sha256": L.sha(plan_path), "feature_values_read": False}))
    else:
        require(args.plan_sha256 and args.output, "Run requires exact plan hash and new output")
        result = run(**kw, plan_path=plan_path, plan_sha=args.plan_sha256, output_name=args.output)
        print(json.dumps({k: result[k] for k in ("status", "source_count", "source_rows_parsed", "samples_checked", "integer_token_status", "peak_process_rss_bytes", "elapsed_monotonic_seconds")}))


if __name__ == "__main__": main()
