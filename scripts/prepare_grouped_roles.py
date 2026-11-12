"""Prepare a reproducible FLNET development-role candidate, never a frozen test split."""

from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
from itertools import combinations
import argparse
import csv
import hashlib
import json
import os
import platform
import re
import resource
import subprocess
import time

from flow_metadata import connection_key
from research_workspace import contained_path, workspace_root

VERSION = "flnet-grouped-role-candidate-v1"
ROLES = ("train", "validation", "calibration")
FIELDS = ("src_ip", "dst_ip", "src_port", "dst_port", "protocol", "timestamp", "label")
LABELS = {"Normal": 0, "DDoS-bot": 1, "DDoS-tcp": 1, "DDoS-stomp": 1, "DDoS-dyn": 1}
GROUP_DEFINITION = "stored_unordered_address_port_pair_and_protocol_v1"


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def code_context():
    repo = Path(__file__).resolve().parents[1]
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True)
    status = subprocess.run(["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True)
    return {"commit_context": result.stdout.strip() if result.returncode == 0 else None,
            "worktree_dirty": bool(status.stdout.strip()) if status.returncode == 0 else None,
            "lock_sha256": sha(repo / "uv.lock") if (repo / "uv.lock").is_file() else None}


def validate_policy(policy):
    expected = {"version", "candidate_id", "dataset", "claim_scope", "group_definition",
                "role_seed", "role_weights", "minimum_rows_per_client_role"}
    if not isinstance(policy, dict) or set(policy) != expected:
        raise ValueError("Use the exact documented candidate-policy fields")
    if policy["version"] != VERSION or policy["dataset"] != "flnet2023":
        raise ValueError("This version supports FLNET development sources only")
    if policy["claim_scope"] != "within_release_grouped_holdout":
        raise ValueError("This program does not implement a temporal or new-site protocol")
    if policy["group_definition"] != GROUP_DEFINITION:
        raise ValueError("Unknown grouping definition")
    for name in ["candidate_id", "role_seed"]:
        if not isinstance(policy[name], str) or not policy[name].strip() or len(policy[name]) > 128:
            raise ValueError("Candidate ID and seed must be nonblank strings up to 128 characters")
    weights = policy["role_weights"]
    if not isinstance(weights, dict) or set(weights) != set(ROLES):
        raise ValueError("Specify train, validation and calibration weights")
    if any(type(weights[k]) is not int or weights[k] <= 0 for k in ROLES):
        raise ValueError("Role weights must be positive integers")
    if sum(weights.values()) > 10000:
        raise ValueError("Role-weight total must not exceed 10000")
    if type(policy["minimum_rows_per_client_role"]) is not int or policy["minimum_rows_per_client_role"] < 1:
        raise ValueError("Minimum role support must be a positive integer")
    return policy


def assign_role(key, policy):
    """Assign a stored key globally; observer, label and date cannot change its role."""
    material = json.dumps([VERSION, policy["role_seed"], key], separators=(",", ":")).encode()
    bucket = int.from_bytes(hashlib.sha256(material).digest()[:8], "big") % sum(policy["role_weights"].values())
    for role in ROLES:
        weight = policy["role_weights"][role]
        if bucket < weight:
            return role
        bucket -= weight
    raise RuntimeError("Role allocation failed")


def development_sources(root, proposal):
    """Check every selected path before opening any dataset file, including symlinks."""
    if not isinstance(proposal, dict) or not isinstance(proposal.get("files"), list):
        raise ValueError("Proposal must contain a file list")
    mapping = proposal.get("observed_development_label_mapping", {}).get("flnet2023")
    if mapping != LABELS:
        raise ValueError("The original FLNET binary label mapping must be preserved")
    if proposal.get("unmapped_development_labels", {}).get("flnet2023"):
        raise ValueError("Unmapped FLNET labels require review")
    sources, seen = [], set()
    base = (root / "datasets/flnet2023/extracted").resolve()
    for item in proposal["files"]:
        if not isinstance(item, dict) or item.get("dataset") != "flnet2023":
            continue
        role = item.get("source_role")
        if role == "reserved_test":
            continue  # Never hash, open or decode a reserved source.
        if role != "development":
            raise ValueError("Unknown FLNET source role")
        relative = item.get("path")
        if not isinstance(relative, str):
            raise ValueError("Source paths must be strings")
        path = contained_path(root, relative)
        parts = tuple(part.casefold() for part in Path(relative).parts)
        resolved_parts = tuple(part.casefold() for part in path.parts)
        if "test" in parts or "03-11" in parts or "test" in resolved_parts or "03-11" in resolved_parts:
            raise ValueError("Reserved path cannot be used as development")
        if not path.is_relative_to(base) or path.parent.name not in ("Normal", "DDoS"):
            raise ValueError("Expected a documented FLNET Normal or DDoS source")
        match = re.fullmatch(r"Dataset-(\d+)(?:-[A-Za-z]+)?\.csv", path.name)
        client = item.get("client_id")
        if not match or type(client) is not int or client != int(match.group(1)) or not 1 <= client <= 10:
            raise ValueError("Source observer ID disagrees with the published filename")
        if path in seen:
            raise ValueError("Duplicate source path or symlink alias")
        seen.add(path)
        if not isinstance(item.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"]):
            raise ValueError("Each source needs its recorded SHA-256")
        sources.append({"path": relative, "resolved": path, "sha256": item["sha256"], "client_id": client})
    if not sources:
        raise ValueError("No FLNET development sources")
    return sorted(sources, key=lambda item: item["path"])


def write_table(path, columns, rows):
    with path.open("x", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(columns)
        writer.writerows(rows)


def prepare(root, proposal_path, policy_path, output):
    root = Path(root).resolve()
    proposal_path = contained_path(root, proposal_path)
    policy_path = contained_path(root, policy_path)
    output = contained_path(root, output)
    if not output.is_relative_to(root / "reports/development-preparation"):
        raise ValueError("Candidate outputs belong under reports/development-preparation")
    if output.exists():
        raise FileExistsError("Preserve the existing candidate or failed run; use a new output path")
    policy_bytes = policy_path.read_bytes()
    proposal_bytes = proposal_path.read_bytes()
    policy = validate_policy(json.loads(policy_bytes))
    proposal = json.loads(proposal_bytes)
    sources = development_sources(root, proposal)
    output.mkdir(parents=True, exist_ok=False)
    started, tick = datetime.now(timezone.utc).isoformat(), time.monotonic()
    base = {"version": VERSION, "candidate_id": policy["candidate_id"], "started_utc": started,
            "status": "preparation_running", "policy": policy, "policy_sha256": hashlib.sha256(policy_bytes).hexdigest(),
            "proposal_sha256": hashlib.sha256(proposal_bytes).hexdigest(), "code_context": code_context(), "reserved_test_opened": False,
            "model_fitted": False, "predictor_values_analyzed": False, "source_files_written": False,
            "source_code_sha256": {p.name: sha(p) for p in [Path(__file__), Path(__file__).with_name("flow_metadata.py"), Path(__file__).with_name("research_workspace.py")]}}
    dump(output / "RUNNING.json", base)
    try:
        counts, date_counts, destinations = Counter(), Counter(), Counter()
        groups = {}  # digest -> [role, observer bitmask, original-label bitmask, row count]
        labels = {name: 1 << i for i, name in enumerate(sorted(LABELS))}
        assignment_digest = hashlib.sha256()
        observed, total = [], 0
        hash_seconds, parsing_seconds = 0.0, 0.0
        for item in sources:
            path, client = item["resolved"], item["client_id"]
            before = path.stat()
            source_tick = time.monotonic()
            actual_sha = sha(path)
            source_hash_seconds = time.monotonic() - source_tick
            hash_seconds += source_hash_seconds
            if actual_sha != item["sha256"]:
                raise ValueError("Development source hash mismatch: " + item["path"])
            local_rows = 0
            source_tick = time.monotonic()
            with path.open(newline="", encoding="utf-8-sig") as stream:
                reader = csv.reader(stream)
                header = next(reader, None)
                if header is None:
                    raise ValueError("Empty source: " + item["path"])
                normalized = [s.strip() for s in header]
                if any(normalized.count(name) != 1 for name in FIELDS):
                    raise ValueError("Required metadata header missing or ambiguous")
                indices = [normalized.index(name) for name in FIELDS]
                for row_number, row in enumerate(reader):
                    if len(row) != len(header):
                        raise ValueError("Malformed source row in " + item["path"])
                    src, dst, sport, dport, protocol, timestamp, label = [row[i].strip() for i in indices]
                    if any(not value for value in [src, dst, sport, dport, protocol, timestamp, label]):
                        raise ValueError("Missing metadata in " + item["path"])
                    if label not in LABELS:
                        raise ValueError("Unmapped original FLNET label in " + item["path"])
                    stored_date = datetime.fromisoformat(timestamp).date().isoformat()
                    key = connection_key(src, dst, sport, dport, protocol)
                    group = hashlib.sha256(key.encode()).digest()
                    if group not in groups:
                        groups[group] = [assign_role(key, policy), 0, 0, 0]
                    state = groups[group]
                    role = state[0]
                    state[1] |= 1 << (client - 1)
                    state[2] |= labels[label]
                    state[3] += 1
                    counts[(client, role, label)] += 1
                    date_counts[(stored_date, role, label)] += 1
                    destination = hashlib.sha256(dst.encode()).hexdigest()
                    destinations[(destination, role, label)] += 1
                    assignment_digest.update(json.dumps([item["path"], row_number, client, group.hex(), role, label], separators=(",", ":")).encode() + b"\n")
                    local_rows += 1
            source_parsing_seconds = time.monotonic() - source_tick
            parsing_seconds += source_parsing_seconds
            after = path.stat()
            if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
                raise ValueError("Source changed during preparation")
            observed.append({k: item[k] for k in ["path", "sha256", "client_id"]} | {"rows": local_rows, "hash_seconds": source_hash_seconds, "parsing_seconds": source_parsing_seconds})
            total += local_rows
        if not total:
            raise ValueError("No development records")
        group_counts, pair_counts = Counter(), Counter()
        role_groups = Counter()
        for role, clients, label_mask, nrows in groups.values():
            role_groups[role] += 1
            ids = [client for client in range(1, 11) if clients & (1 << (client - 1))]
            for client in ids:
                group_counts[(client, role)] += 1
            for a, b in combinations(ids, 2):
                pair_counts[(a, b, role)] += 1
        clients = sorted({item["client_id"] for item in observed})
        support_issues = [{"client_id": c, "role": role, "rows": sum(counts[(c, role, label)] for label in LABELS)}
                          for c in clients for role in ROLES
                          if sum(counts[(c, role, label)] for label in LABELS) < policy["minimum_rows_per_client_role"]]
        write_table(output / "client-role-label-counts.csv", ["observer_id", "role", "original_label", "rows"],
                    [(*key, n) for key, n in sorted(counts.items())])
        write_table(output / "date-role-label-counts.csv", ["stored_date", "role", "original_label", "rows"],
                    [(*key, n) for key, n in sorted(date_counts.items())])
        write_table(output / "destination-role-label-counts.csv", ["stored_destination_digest", "role", "original_label", "rows"],
                    [(*key, n) for key, n in sorted(destinations.items())])
        write_table(output / "observer-pair-shared-key-counts.csv", ["observer_a", "observer_b", "role", "candidate_keys"],
                    [(*key, n) for key, n in sorted(pair_counts.items())])
        rows_by_role = {role: sum(n for (c, r, label), n in counts.items() if r == role) for role in ROLES}
        result = base | {"status": "candidate_not_frozen", "finished_utc": datetime.now(timezone.utc).isoformat(),
                  "elapsed_seconds": time.monotonic() - tick, "rows": total, "sources": observed,
                  "assignment_sha256": assignment_digest.hexdigest(), "candidate_groups": len(groups),
                  "rows_by_role": rows_by_role, "groups_by_role": dict(role_groups),
                  "groups_seen_at_multiple_observers": sum(state[1].bit_count() > 1 for state in groups.values()),
                  "groups_with_multiple_original_labels": sum(state[2].bit_count() > 1 for state in groups.values()),
                  "client_role_group_counts": [{"client_id": c, "role": r, "groups": group_counts[(c, r)]} for c in clients for r in ROLES],
                  "support_checks": {"minimum_rows_per_client_role": policy["minimum_rows_per_client_role"], "total_row_minimum_passed": not support_issues, "issues": support_issues,
                      "binary_class_counts": [{"client_id": c, "role": r,
                          "benign": counts[(c, r, "Normal")],
                          "attack": sum(counts[(c, r, label)] for label in LABELS if label != "Normal")}
                          for c in clients for r in ROLES],
                      "note": "A row-count minimum is not a check of calibration sufficiency or both-class metric support."},
                  "timing": {"source_hash_seconds": hash_seconds, "csv_parsing_and_role_accounting_seconds": parsing_seconds,
                      "elapsed_boundary": "After configuration validation and output-directory creation through manifest assembly; final serialization excluded"},
                  "source_verification": "SHA-256 before parsing; size, modification time and inode unchanged after parsing",
                  "environment": {"python": platform.python_version(), "platform": platform.platform(), "logical_cpus": os.cpu_count(), "preparation_threads": 1,
                                  "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if platform.system() == "Darwin" else 1024)},
                  "limits": ["Candidate grouping does not prove independent sessions, captures or sites.",
                             "Original observer IDs are preserved; this program does not establish operational PoPs or customer identities.",
                             "Destination digests group stored addresses; they are not customer mappings or a privacy guarantee.",
                             "Hash allocation mixes stored dates; it does not implement a future-traffic evaluation.",
                             "No predictor semantics, calibration sufficiency, final test eligibility or protocol freeze is established."]}
        if sum(rows_by_role.values()) != total or sum(role_groups.values()) != len(groups):
            raise RuntimeError("Role accounting mismatch")
        dump(output / "candidate-manifest.json", result)
        artifacts = {p.name: sha(p) for p in output.iterdir() if p.is_file()}
        dump(output / "COMPLETE.json", {"version": VERSION, "scope": "candidate_preparation_only", "artifacts": artifacts,
                                       "reserved_test_opened": False, "model_fitted": False})
        return result
    except Exception as exc:
        dump(output / "FAILED.json", base | {"status": "preparation_failed", "finished_utc": datetime.now(timezone.utc).isoformat(),
                                            "elapsed_seconds": time.monotonic() - tick, "error_type": type(exc).__name__, "error": str(exc)})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proposal", default="config/split-proposal.json")
    parser.add_argument("--policy", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = prepare(workspace_root(), args.proposal, args.policy, args.output)
    print(json.dumps({k: result[k] for k in ["status", "rows", "rows_by_role", "candidate_groups", "groups_by_role", "support_checks", "elapsed_seconds"]}))


if __name__ == "__main__":
    main()
