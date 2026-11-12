"""Load a pinned FLNET development candidate without reassigning roles or fitting models.

Only recorded Normal/DDoS development CSVs are permitted. Outputs are private
engineering arrays, not a frozen scientific protocol or a deployment interface.
"""
from __future__ import annotations
from collections import Counter
from datetime import datetime, timezone
import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import re
import resource
import shutil
import subprocess
import sys
import time
import numpy as np
from flow_metadata import connection_key
import prepare_grouped_roles as roles
from research_workspace import workspace_root

VERSION = "flnet-grouped-candidate-loader-v1"
META = ("src_ip", "dst_ip", "src_port", "dst_port", "protocol", "timestamp", "label")
EXCLUDED_IAT = ("flow_iat_min", "fwd_iat_min", "bwd_iat_min")
LABEL_NAMES = tuple(roles.LABELS)
LABEL_IDS = {name: i for i, name in enumerate(LABEL_NAMES)}
ROLE_IDS = {name: i for i, name in enumerate(roles.ROLES)}
RECORD_DTYPE = np.dtype([("source_id", "u1"), ("source_row", "<u8"),
    ("observer_id", "u1"), ("role_id", "u1"), ("original_label_id", "u1"),
    ("binary_label", "u1"), ("group_sha256", "S64"), ("stored_timestamp", "S64")])
EXPECTED_PATHS = {*(f"datasets/flnet2023/extracted/Normal/Dataset-{i}.csv" for i in range(1, 11)),
    "datasets/flnet2023/extracted/DDoS/Dataset-1-BOT.csv",
    "datasets/flnet2023/extracted/DDoS/Dataset-5-STOMP.csv",
    "datasets/flnet2023/extracted/DDoS/Dataset-9-DYN.csv",
    "datasets/flnet2023/extracted/DDoS/Dataset-10-TCP.csv"}
SEAL_NAMES = {"RUNNING.json", "client-role-label-counts.csv", "destination-role-label-counts.csv",
    "observer-pair-shared-key-counts.csv", "date-role-label-counts.csv", "candidate-manifest.json"}
HEX = re.compile(r"[0-9a-f]{64}")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest_stream(stream):
    return hashlib.file_digest(stream, "sha256").hexdigest()


def sha(path):
    with Path(path).open("rb") as stream:
        return digest_stream(stream)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate JSON key")
        result[key] = value
    return result


def read_json(path):
    return json.loads(Path(path).read_text(), object_pairs_hook=unique_object)


def write_json(path, value):
    path = Path(path)
    temporary = path.with_name("." + path.name + ".tmp")
    try:
        with temporary.open("x") as stream:
            json.dump(value, stream, indent=2, allow_nan=False)
            stream.write("\n")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def control_path(root, name):
    """Control files must be config/reports JSON, never dataset paths or escapes."""
    p = Path(name)
    if p.is_absolute():
        try:
            p = p.relative_to(root)
        except ValueError as exc:
            raise ValueError("Control file outside workspace") from exc
    require(".." not in p.parts and "\\" not in str(p), "Invalid control path")
    require(p.parts and p.parts[0] in {"config", "reports"} and p.suffix == ".json", "Expected control JSON outside datasets")
    result = (root / p).resolve()
    require(result.is_relative_to(root) and result.relative_to(root).parts[0] in {"config", "reports"} and result.suffix == ".json" and "datasets" not in result.relative_to(root).parts, "Control path escaped permitted metadata")
    return result


def source_path(root, relative):
    """Check every path before a source descriptor, byte hash or parser is opened."""
    require(isinstance(relative, str) and relative in EXPECTED_PATHS, "Unauthorized development source")
    path = root / relative
    require(path.resolve() == path, "Source symlink or parent-directory escape")
    require(not any(p.casefold() in {"test", "03-11"} for p in path.parts), "Reserved source path")
    return path


def source_inventory(root, proposal, manifest):
    require(proposal.get("observed_development_label_mapping", {}).get("flnet2023") == roles.LABELS, "Original label mapping differs")
    require(not proposal.get("unmapped_development_labels", {}).get("flnet2023"), "Unmapped labels in proposal")
    require(isinstance(proposal.get("files"), list), "Missing inventory")
    selected, excluded, seen = [], [], set()
    for i, item in enumerate(proposal["files"]):
        require(isinstance(item, dict), "Malformed inventory entry")
        dataset, role, relative = item.get("dataset"), item.get("source_role"), item.get("path")
        require(dataset in {"flnet2023", "cicddos2019"} and role in {"development", "reserved_test"}, "Unknown inventory dataset or role")
        require(isinstance(relative, str) and not Path(relative).is_absolute() and ".." not in Path(relative).parts and "\\" not in relative, "Invalid inventory path")
        if role == "reserved_test" or dataset != "flnet2023":
            # Do not resolve, stat, open or hash excluded dataset paths.
            excluded.append({"inventory_position": i, "path": relative, "dataset": dataset,
                "source_role": role, "reason": "reserved_no_access" if role == "reserved_test" else "other_dataset"})
            continue
        path = source_path(root, relative)
        match = re.fullmatch(r"Dataset-(\d+)(?:-[A-Za-z]+)?\.csv", path.name)
        client = item.get("client_id")
        require(match and type(client) is int and client == int(match.group(1)) and 1 <= client <= 10, "Observer identity differs")
        require(relative not in seen, "Duplicate source")
        require(isinstance(item.get("sha256"), str) and HEX.fullmatch(item["sha256"]), "Invalid source digest")
        seen.add(relative)
        selected.append({"path": relative, "sha256": item["sha256"], "client_id": client})
    require(seen == EXPECTED_PATHS and len(selected) == 14, "Expected exactly fourteen development sources")
    expected = {q["path"]: (q["sha256"], q["client_id"]) for q in manifest["sources"]}
    observed = {q["path"]: (q["sha256"], q["client_id"]) for q in selected}
    require(len(manifest["sources"]) == 14 and expected == observed, "Candidate source inventory differs")
    return sorted(selected, key=lambda q: q["path"]), excluded


def verify_controls(root, contract_name, registry_name, contract_sha, registry_sha):
    contract_path, registry_path = [control_path(root, p) for p in [contract_name, registry_name]]
    require(HEX.fullmatch(contract_sha) and HEX.fullmatch(registry_sha), "Expected explicit frozen-control SHA-256 pins")
    require(sha(contract_path) == contract_sha and sha(registry_path) == registry_sha, "Contract or registry hash mismatch")
    contract, registry = read_json(contract_path), read_json(registry_path)
    pin = contract["candidate"]
    paths = {k: control_path(root, pin[name]) for k, name in [("candidate", "path"), ("proposal", "proposal_path"), ("policy", "policy_path"), ("seal", "seal_path")]}
    for k, key in [("candidate", "sha256"), ("proposal", "proposal_sha256"), ("policy", "policy_sha256"), ("seal", "seal_sha256")]:
        require(sha(paths[k]) == pin[key], "Pinned " + k + " changed")
    manifest, proposal, policy, seal = [read_json(paths[k]) for k in ["candidate", "proposal", "policy", "seal"]]
    roles.validate_policy(policy)
    require(manifest["status"] == "candidate_not_frozen" and manifest["policy"] == policy and manifest["policy_sha256"] == pin["policy_sha256"] and manifest["proposal_sha256"] == pin["proposal_sha256"], "Candidate policy/status binding differs")
    require(manifest["assignment_sha256"] == pin["assignment_sha256"] and manifest["reserved_test_opened"] is False and manifest["model_fitted"] is False, "Candidate scope/digest differs")
    require(manifest["source_code_sha256"] == pin["executed_role_source_sha256"] and manifest["code_context"]["commit_context"] == pin["executed_role_code_commit"], "Candidate executed-code binding differs")
    require(paths["seal"].parent == paths["candidate"].parent and set(seal["artifacts"]) == SEAL_NAMES and seal["reserved_test_opened"] is False and seal["model_fitted"] is False, "Candidate seal scope differs")
    for name, digest in seal["artifacts"].items():
        artifact = paths["candidate"].parent / name
        require(artifact.resolve() == artifact, "Candidate sealed artifact symlink escape")
        require(sha(artifact) == digest, "Candidate sealed artifact changed")
    script_dir = Path(__file__).resolve().parent
    for name, digest in pin["executed_role_source_sha256"].items():
        require(Path(name).name == name and sha(script_dir / name) == digest, "Pinned role implementation changed")
    require(set(pin["executed_role_source_sha256"]) == {"prepare_grouped_roles.py", "flow_metadata.py", "research_workspace.py"}, "Incomplete role implementation pins")
    header = [q["name"] for q in registry["fields"]]
    features = registry["historical_csv73_ordered_inputs"]
    require(len(header) == 83 and len(set(header)) == 83 and set(META + EXCLUDED_IAT) <= set(header), "Expected exact stored schema")
    require(features == [q for q in header if q not in META + EXCLUDED_IAT] == contract["input"]["features"] and len(features) == 73, "Ordered predictor contract differs")
    sources, exclusions = source_inventory(root, proposal, manifest)
    require(type(manifest["rows"]) is int and manifest["rows"] > 0 and sum(q["rows"] for q in manifest["sources"]) == manifest["rows"], "Invalid candidate row count")
    return manifest, policy, header, features, sources, exclusions, {"contract": contract_sha, "registry": registry_sha, **{k: sha(p) for k, p in paths.items()}}


def open_source(root, item):
    path = source_path(root, item["path"])
    directory_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in Path(item["path"]).parts[:-1]:
            child_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory_fd)
            os.close(directory_fd)
            directory_fd = child_fd
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory_fd)
    finally:
        os.close(directory_fd)
    try:
        return os.fdopen(fd, "rb")
    except Exception:
        os.close(fd)
        raise


def fingerprint(stat):
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns


def code_context():
    repo = Path(__file__).resolve().parents[1]
    def git(*args):
        r = subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True)
        return r.stdout.strip() if r.returncode == 0 else None
    return {"commit": git("rev-parse", "HEAD"), "worktree_dirty": git("status", "--porcelain") != "",
        "source_sha256": {name: sha(repo / "scripts" / name) for name in ["load_grouped_candidate.py", "prepare_grouped_roles.py", "flow_metadata.py", "research_workspace.py"]}, "lock_sha256": sha(repo / "uv.lock")}


def prepare(root, contract_name, registry_name, output_name, contract_sha, registry_sha, chunk_rows=10000):
    root = Path(root).resolve()
    require(type(chunk_rows) is int and 1 <= chunk_rows <= 100000, "Invalid chunk bound")
    output = root / output_name
    require(not Path(output_name).is_absolute() and ".." not in Path(output_name).parts and "\\" not in output_name, "Use a new relative output")
    require(output.resolve() == output and output.is_relative_to(root / "reports/development-preparation"), "Output must remain in development reports without symlinks")
    output.mkdir(parents=True, exist_ok=False)
    tick, started = time.monotonic(), datetime.now(timezone.utc).isoformat()
    timing = Counter()
    base = {"version": VERSION, "purpose": "candidate_engineering_loader_not_protocol_freeze", "status": "running", "started_utc": started,
        "code": code_context(), "chunk_rows": chunk_rows, "reserved_test_opened_or_hashed": False, "model_fitted": False,
        "calibration_or_model_scoring_performed": False, "learned_preprocessing_fitted": False}
    write_json(output / "run-state.json", base)
    X = records = None
    progress = {"source_id": None, "source_path": None, "source_row": None, "stored_rows": 0}
    try:
        t = time.monotonic()
        manifest, policy, header, features, sources, exclusions, pins = verify_controls(root, contract_name, registry_name, contract_sha, registry_sha)
        timing["control_verification_seconds"] = time.monotonic() - t
        n = manifest["rows"]
        feature_indices = [header.index(name) for name in features]
        numeric_indices = [header.index(name) for name in header if name not in META]
        selected_from_numeric = [i for i, index in enumerate(numeric_indices) if index in feature_indices]
        # Preserve feature order even if the registry puts excluded numeric fields among predictors.
        require([numeric_indices[i] for i in selected_from_numeric] == feature_indices, "Numeric projection order differs")
        t = time.monotonic()
        required_bytes = n * (len(features) * 8 + RECORD_DTYPE.itemsize) + 8192
        require(shutil.disk_usage(output).free >= required_bytes, "Insufficient free space for declared arrays")
        X = np.lib.format.open_memmap(output / "features.npy", mode="w+", dtype="<f8", shape=(n, len(features)), fortran_order=False, version=(2, 0))
        records = np.lib.format.open_memmap(output / "records.npy", mode="w+", dtype=RECORD_DTYPE, shape=(n,), fortran_order=False, version=(2, 0))
        timing["array_allocation_seconds"] = time.monotonic() - t
        schema = {"version": VERSION, "rows": n, "features": features, "feature_dtype": X.dtype.str, "feature_shape": list(X.shape),
            "record_dtype": records.dtype.descr, "record_itemsize": records.dtype.itemsize, "array_order": "C", "npy_format": [2, 0],
            "source_row_origin": "zero-based parsed CSV data row, excluding header", "roles": ROLE_IDS, "original_labels": LABEL_IDS,
            "binary_labels": roles.LABELS, "feature_policy": "unscaled float64; no unit conversion, imputation, clipping, normalization or fitting",
            "excluded_numeric_policy": "minimum IAT fields validated as finite then excluded; finite negative values retained in source only",
            "timestamp_policy": "stripped stored ISO text up to64 ASCII bytes, no clock/timezone conversion", "role_policy": policy}
        write_json(output / "schema.json", schema)
        write_json(output / "source-map.json", sources)
        assignment, x_payload, r_payload = [hashlib.sha256() for _ in range(3)]
        groups, counts, date_counts, observed, offset = {}, Counter(), Counter(), [], 0
        def flush(numeric_rows, record_rows):
            nonlocal offset
            if not numeric_rows:
                return
            require(offset + len(numeric_rows) <= n, "Observed rows exceed candidate")
            try:
                values = np.asarray(numeric_rows, dtype="<f8")
            except (ValueError, OverflowError) as exc:
                raise ValueError("Invalid or missing numeric stored field") from exc
            require(np.isfinite(values).all(), "Nonfinite stored numeric field")
            values = np.ascontiguousarray(values[:, selected_from_numeric], dtype="<f8")
            provenance = np.asarray(record_rows, dtype=RECORD_DTYPE)
            X[offset:offset + len(values)] = values
            records[offset:offset + len(values)] = provenance
            x_payload.update(values.tobytes(order="C")); r_payload.update(provenance.tobytes(order="C"))
            offset += len(values)
            progress["stored_rows"] = offset
        source_rows = {q["path"]: q["rows"] for q in manifest["sources"]}
        for sid, item in enumerate(sources):
            t = time.monotonic(); local_rows = 0
            progress.update(source_id=sid, source_path=item["path"], source_row=None)
            with open_source(root, item) as binary:
                before = os.fstat(binary.fileno())
                require(digest_stream(binary) == item["sha256"], "Development source hash mismatch before parsing")
                timing["source_hash_before_seconds"] += time.monotonic() - t
                binary.seek(0)
                text = io.TextIOWrapper(binary, encoding="utf-8-sig", newline="")
                t = time.monotonic()
                try:
                    reader = csv.reader(text)
                    require(next(reader, None) == header, "Missing, duplicate or reordered stored columns")
                    numeric_rows, record_rows = [], []
                    for row_number, row in enumerate(reader):
                        progress["source_row"] = row_number
                        require(len(row) == len(header), "Malformed CSV row width")
                        src, dst, sport, dport, protocol, stamp, label = [row[header.index(name)].strip() for name in META]
                        require(all([src, dst, sport, dport, protocol, stamp, label]), "Missing metadata")
                        require(label in roles.LABELS, "Unknown original label")
                        date = datetime.fromisoformat(stamp).date().isoformat()
                        stamp_bytes = stamp.encode("ascii")
                        require(len(stamp_bytes) <= 64, "Stored timestamp exceeds declared bound")
                        key = connection_key(src, dst, sport, dport, protocol)
                        group = hashlib.sha256(key.encode()).digest()
                        if group not in groups:
                            groups[group] = [roles.assign_role(key, policy), 0, 0]
                        state = groups[group]; role = state[0]
                        state[1] |= 1 << (item["client_id"] - 1); state[2] |= 1 << LABEL_IDS[label]
                        counts[(item["client_id"], role, label)] += 1
                        date_counts[(date, role, label)] += 1
                        digest_hex = group.hex()
                        assignment.update(json.dumps([item["path"], row_number, item["client_id"], digest_hex, role, label], separators=(",", ":")).encode() + b"\n")
                        numeric_rows.append([row[index] for index in numeric_indices])
                        record_rows.append((sid, row_number, item["client_id"], ROLE_IDS[role], LABEL_IDS[label], roles.LABELS[label], digest_hex.encode(), stamp_bytes))
                        local_rows += 1
                        if len(numeric_rows) == chunk_rows:
                            flush(numeric_rows, record_rows); numeric_rows, record_rows = [], []
                    flush(numeric_rows, record_rows)
                finally:
                    text.detach()
                timing["csv_numeric_role_and_array_write_seconds"] += time.monotonic() - t
                require(local_rows == source_rows[item["path"]], "Per-source row count differs")
                t = time.monotonic(); binary.seek(0)
                require(digest_stream(binary) == item["sha256"], "Development source hash mismatch after parsing")
                after = os.fstat(binary.fileno())
                path_after = source_path(root, item["path"]).stat()
                require(fingerprint(before) == fingerprint(after) == fingerprint(path_after), "Source changed during loading")
                timing["source_hash_after_seconds"] += time.monotonic() - t
            observed.append(item | {"source_id": sid, "rows": local_rows})
        t = time.monotonic()
        require(offset == n and assignment.hexdigest() == manifest["assignment_sha256"], "Total row count or assignment digest differs")
        row_totals = {r: sum(v for (c, role, lab), v in counts.items() if role == r) for r in roles.ROLES}
        group_totals = Counter(state[0] for state in groups.values())
        client_groups = Counter((c, state[0]) for state in groups.values() for c in range(1, 11) if state[1] & (1 << (c - 1)))
        support = [{"client_id": c, "role": r, "benign": counts[(c, r, "Normal")], "attack": sum(counts[(c, r, lab)] for lab in roles.LABELS if lab != "Normal")} for c in range(1, 11) for r in roles.ROLES]
        require(row_totals == manifest["rows_by_role"] and dict(group_totals) == manifest["groups_by_role"] and len(groups) == manifest["candidate_groups"], "Global row/key accounting differs")
        require(support == manifest["support_checks"]["binary_class_counts"], "Observer role class support differs")
        require([{"client_id": c, "role": r, "groups": client_groups[(c, r)]} for c in range(1, 11) for r in roles.ROLES] == manifest["client_role_group_counts"], "Observer key support differs")
        shared = sum(q[1].bit_count() > 1 for q in groups.values()); multi_label = sum(q[2].bit_count() > 1 for q in groups.values())
        require(shared == manifest["groups_seen_at_multiple_observers"] and multi_label == manifest["groups_with_multiple_original_labels"], "Shared-key accounting differs")
        timing["accounting_verification_seconds"] = time.monotonic() - t
        t = time.monotonic(); X.flush(); records.flush(); del X, records; X = records = None
        timing["array_flush_seconds"] = time.monotonic() - t
        t = time.monotonic()
        actual_x, actual_r = [hashlib.sha256() for _ in range(2)]
        saved_x = np.load(output / "features.npy", mmap_mode="r", allow_pickle=False)
        saved_r = np.load(output / "records.npy", mmap_mode="r", allow_pickle=False)
        require(saved_x.shape == (n, 73) and saved_x.dtype == np.dtype("<f8") and saved_r.shape == (n,) and saved_r.dtype == RECORD_DTYPE, "Saved array schema differs")
        for begin in range(0, n, chunk_rows):
            actual_x.update(saved_x[begin:begin + chunk_rows].tobytes(order="C"))
            actual_r.update(saved_r[begin:begin + chunk_rows].tobytes(order="C"))
        require(actual_x.digest() == x_payload.digest() and actual_r.digest() == r_payload.digest(), "Saved payload differs or tail rows lost")
        del saved_x, saved_r
        timing["saved_payload_readback_seconds"] = time.monotonic() - t
        write_json(output / "row-support.json", {"binary_support": support, "original_label_counts": [{"observer_id": c, "role": r, "original_label": lab, "rows": count} for (c, r, lab), count in sorted(counts.items())], "stored_date_counts": [{"stored_date": d, "role": r, "original_label": lab, "rows": count} for (d, r, lab), count in sorted(date_counts.items())]})
        t = time.monotonic()
        payloads = {name: {"sha256": sha(output / name), "bytes": (output / name).stat().st_size} for name in ["features.npy", "records.npy", "schema.json", "source-map.json", "row-support.json"]}
        timing["artifact_hash_seconds"] = time.monotonic() - t
        result = base | {"status": "complete_engineering_loader", "input_sha256": pins, "candidate_code_context": manifest["code_context"], "candidate_status_unchanged": manifest["status"], "assignment_sha256": assignment.hexdigest(), "rows": n, "sources": observed, "exclusions": exclusions,
            "rows_by_role": row_totals, "groups_by_role": dict(group_totals), "candidate_groups": len(groups), "groups_seen_at_multiple_observers": shared,
            "groups_with_multiple_original_labels": multi_label, "binary_support": support, "schema": schema, "payload_sha256": {"features": x_payload.hexdigest(), "records": r_payload.hexdigest()},
            "artifacts": payloads, "timing": dict(timing), "environment": {"python": platform.python_version(), "numpy": np.__version__, "platform": platform.platform(), "machine": platform.machine(), "logical_cpus": os.cpu_count(), "preparation_python_workers": 1, "numpy_thread_setting": "library_default; no BLAS fitting/scoring operations used", "peak_process_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if platform.system() == "Darwin" else 1024)},
            "limits": ["No physical feature semantics or original common observation policy verified.", "Stored grouping does not establish independent episodes, customers or PoPs.", "No learned transforms, model training, calibration or model scoring performed.", "Per-process peak RSS includes mappings/runtime; no energy or distributed latency measured."]}
        result["finished_utc"] = datetime.now(timezone.utc).isoformat(); result["elapsed_monotonic_seconds"] = time.monotonic() - tick
        result["elapsed_boundary"] = "After new output-directory creation through source/control checks, allocation, parsing, row/key accounting, flush/readback and artifact hashes; final receipt writes excluded."
        write_json(output / "summary.json", result); write_json(output / "run-state.json", result)
        write_json(output / "COMPLETE.json", {"version": VERSION, "status": "complete_engineering_loader", "artifacts": payloads | {name: {"sha256": sha(output / name), "bytes": (output / name).stat().st_size} for name in ["summary.json", "run-state.json"]}})
        return result
    except Exception as exc:
        failed = base | {"status": "failed_engineering_loader", "finished_utc": datetime.now(timezone.utc).isoformat(), "elapsed_monotonic_seconds": time.monotonic() - tick, "timing": dict(timing), "progress": progress, "error_type": type(exc).__name__, "error": str(exc)}
        write_json(output / "FAILED.json", failed); write_json(output / "run-state.json", failed)
        raise
    finally:
        for mapping in [X, records]:
            if mapping is not None:
                try:
                    mapping.flush()
                except OSError:
                    pass  # A failed run remains failed; preserve the original error.


def open_arrays(directory):
    """Read trusted prepared arrays immutably after checking every sealed artifact."""
    directory = Path(directory).resolve()
    require(not any(p.casefold() in {"test", "03-11"} for p in directory.parts), "Reserved directory cannot be a loader output")
    require(not (directory / "COMPLETE.json").is_symlink(), "Completion seal symlink is not permitted")
    seal = read_json(directory / "COMPLETE.json")
    require(seal.get("version") == VERSION and seal.get("status") == "complete_engineering_loader", "Incomplete or unsupported loader output")
    expected = {"features.npy", "records.npy", "schema.json", "source-map.json", "row-support.json", "summary.json", "run-state.json"}
    require(set(seal["artifacts"]) == expected, "Unexpected artifact inventory")
    for name, entry in seal["artifacts"].items():
        p = directory / name
        require(not p.is_symlink() and p.is_file() and p.stat().st_size == entry["bytes"] and sha(p) == entry["sha256"], "Prepared artifact integrity mismatch")
    schema = read_json(directory / "schema.json")
    X = np.load(directory / "features.npy", mmap_mode="r", allow_pickle=False)
    records = np.load(directory / "records.npy", mmap_mode="r", allow_pickle=False)
    require(X.shape == (schema["rows"], 73) and X.dtype == np.dtype("<f8") and records.shape == (schema["rows"],) and records.dtype == RECORD_DTYPE, "Prepared array schema mismatch")
    return schema, X, records


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--contract", required=True); p.add_argument("--registry", required=True)
    p.add_argument("--contract-sha256", required=True); p.add_argument("--registry-sha256", required=True)
    p.add_argument("--output", required=True); p.add_argument("--chunk-rows", type=int, default=10000)
    args = p.parse_args()
    result = prepare(workspace_root(), args.contract, args.registry, args.output, args.contract_sha256, args.registry_sha256, args.chunk_rows)
    print(json.dumps({k: result[k] for k in ["status", "rows", "rows_by_role", "assignment_sha256", "elapsed_monotonic_seconds"]}))

if __name__ == "__main__":
    main()
