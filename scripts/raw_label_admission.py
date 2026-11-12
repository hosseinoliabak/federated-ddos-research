"""Offline conservative packet/Zeek-label admission. No model fitting or live I/O.

The checked policy is explicit data, committed before an actual audit. Public
code contains no capture paths, packet addresses, source rows or credentials.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import ctypes
import ctypes.util
import csv
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import platform
import re
import resource
import struct
import subprocess
import sys
import time


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def microseconds(text: str) -> int:
    try:
        value = Decimal(text) * 1_000_000
        if not value.is_finite() or value < 0 or value != value.to_integral_value():
            raise ValueError("Not exact nonnegative integer microseconds")
        return int(value)
    except InvalidOperation as e:
        raise ValueError("Invalid decimal time") from e


def count(text: str) -> int:
    if not re.fullmatch(r"[0-9]+", text):
        raise ValueError("Invalid nonnegative integer counter")
    return int(text)


def canonical(src, sport, dst, dport, proto):
    return (tuple(sorted(((src, sport), (dst, dport)))), proto)


def family(src, dst, proto):
    return (tuple(sorted((src, dst))), proto)


@dataclass(frozen=True)
class Frame:
    ordinal: int
    ts: int
    captured: int
    wire: int
    data: bytes


@dataclass(frozen=True)
class Packet:
    ordinal: int
    ts: int
    src: bytes
    sport: int
    dst: bytes
    dport: int
    proto: int
    ip_bytes: int
    vlans: int = 0

    @property
    def key(self):
        return canonical(self.src, self.sport, self.dst, self.dport, self.proto)

    @property
    def family(self):
        return family(self.src, self.dst, self.proto)


@dataclass
class Decode:
    reason: str
    packet: Packet | None = None
    family: tuple | None = None


def pcap_frames(path: Path):
    """Read a classic PCAP strictly; no oversized reads on corrupt lengths."""
    with path.open("rb") as f:
        header = f.read(24)
        if len(header) != 24:
            raise ValueError("Incomplete PCAP global header")
        byte_orders = {b"\xd4\xc3\xb2\xa1": "<", b"\xa1\xb2\xc3\xd4": ">"}
        if header[:4] not in byte_orders:
            raise ValueError("Policy supports classic microsecond PCAP only")
        order = byte_orders[header[:4]]
        major, minor, zone, sigfig, snaplen, linktype = struct.unpack(order + "HHiiII", header[4:])
        if (major, minor) != (2, 4) or linktype != 1 or not (0 < snaplen <= 16_777_216):
            raise ValueError("Unsupported PCAP version, link type or snapshot length")
        ordinal, previous = 0, -1
        while True:
            record = f.read(16)
            if not record:
                break
            if len(record) != 16:
                raise ValueError("Incomplete PCAP record header")
            sec, frac, captured, wire = struct.unpack(order + "IIII", record)
            if frac >= 1_000_000 or captured > snaplen or captured > wire:
                raise ValueError("Invalid PCAP timestamp or lengths")
            data = f.read(captured)
            if len(data) != captured:
                raise ValueError("Incomplete PCAP packet data")
            ts = sec * 1_000_000 + frac
            if ts < previous:
                raise ValueError("Timestamp order decreases; no sorting repair")
            previous = ts
            ordinal += 1
            yield Frame(ordinal, ts, captured, wire, data)


def decode(frame: Frame) -> Decode:
    data = frame.data
    if len(data) < 14:
        return Decode("short_ethernet")
    ethertype = struct.unpack_from("!H", data, 12)[0]
    offset, vlans = 14, 0
    while ethertype in (0x8100, 0x88A8):
        if vlans == 4:
            return Decode("too_many_vlan_tags")
        if len(data) < offset + 4:
            return Decode("short_vlan")
        ethertype = struct.unpack_from("!H", data, offset + 2)[0]
        offset += 4
        vlans += 1
    if ethertype != 0x0800:
        return Decode(f"unsupported_ethertype_{ethertype:04x}")
    if len(data) < offset + 20:
        return Decode("short_ipv4")
    version, ihl = data[offset] >> 4, (data[offset] & 15) * 4
    total = struct.unpack_from("!H", data, offset + 2)[0]
    frag = struct.unpack_from("!H", data, offset + 6)[0]
    proto = data[offset + 9]
    src, dst = data[offset + 12:offset + 16], data[offset + 16:offset + 20]
    fam = family(src, dst, proto) if proto in (6, 17) else None
    if version != 4 or ihl < 20 or ihl > 60 or total < ihl:
        return Decode("invalid_ipv4_header", family=fam)
    if frame.captured < frame.wire:
        return Decode("captured_length_truncation", family=fam)
    if len(data) < offset + ihl or len(data) < offset + total:
        return Decode("ipv4_length_truncation", family=fam)
    if frag & 0x3FFF:  # MF or fragment offset; never treat a first fragment as complete.
        return Decode("ipv4_fragment", family=fam)
    if frag & 0x8000:
        return Decode("reserved_ipv4_flag", family=fam)
    if proto not in (6, 17):
        return Decode(f"unsupported_ipv4_protocol_{proto}")
    transport, available = offset + ihl, total - ihl
    if proto == 6:
        if available < 20:
            return Decode("short_tcp", family=fam)
        tcp_header = (data[transport + 12] >> 4) * 4
        if tcp_header < 20 or tcp_header > available:
            return Decode("invalid_tcp_header", family=fam)
    else:
        if available < 8:
            return Decode("short_udp", family=fam)
        udp_length = struct.unpack_from("!H", data, transport + 4)[0]
        if udp_length < 8 or udp_length != available:
            return Decode("invalid_udp_length", family=fam)
    sport, dport = struct.unpack_from("!HH", data, transport)
    packet = Packet(frame.ordinal, frame.ts, src, sport, dst, dport, proto, total, vlans)
    return Decode("supported", packet, fam)


@dataclass
class Connection:
    row: int
    uid: str
    ts: int
    duration: int | None
    src: bytes
    sport: int
    dst: bytes
    dport: int
    proto: int
    counts: tuple[int, int, int, int]
    label: str
    binary: str | None
    missed: int
    tunnel: bool
    state: str
    history: str

    @property
    def key(self):
        return canonical(self.src, self.sport, self.dst, self.dport, self.proto)

    @property
    def family(self):
        return family(self.src, self.dst, self.proto)

    @property
    def end(self):
        if self.duration is not None:
            return self.ts + self.duration
        if self.counts[0] + self.counts[2] == 1:
            return self.ts
        return None

    def temporal_candidate(self, ts):
        return ts >= self.ts and (self.end is None or ts <= self.end)

    def direction(self, packet):
        forward = (packet.src, packet.sport, packet.dst, packet.dport) == (self.src, self.sport, self.dst, self.dport)
        reverse = (packet.dst, packet.dport, packet.src, packet.sport) == (self.src, self.sport, self.dst, self.dport)
        if forward == reverse:
            return None
        return 0 if forward else 1


def read_connections(path: Path, policy: dict):
    metadata, rows, uids = {}, [], set()
    fields = None
    with path.open(encoding="utf-8", newline="") as f:
        for lineno, line in enumerate(f, 1):
            line = line.rstrip("\r\n")
            if line.startswith("#"):
                key, _, value = line.partition("\t")
                if line.startswith("#separator "):
                    metadata["separator"] = line[len("#separator "):]
                elif key == "#fields":
                    fields = value.split("\t")
                    if len(fields) != len(set(fields)):
                        raise ValueError("Duplicate log field")
                    metadata["fields"] = fields
                elif key == "#types":
                    metadata["types"] = value.split("\t")
                else:
                    metadata[key.lstrip("#")] = value
                continue
            if fields is None or not line:
                raise ValueError(f"Missing fields or blank row at line {lineno}")
            values = line.split("\t")
            if len(values) != len(fields):
                raise ValueError(f"Field count mismatch at line {lineno}")
            d = dict(zip(fields, values))
            uid = d["uid"]
            if uid in uids:
                raise ValueError("Duplicate source UID; no deduplication repair")
            uids.add(uid)
            if d["proto"] not in ("tcp", "udp"):
                raise ValueError("Unsupported source transport; no coercion")
            src, dst = ipaddress.ip_address(d["id.orig_h"]), ipaddress.ip_address(d["id.resp_h"])
            if src.version != 4 or dst.version != 4:
                raise ValueError("Unsupported source address family")
            sport, dport = count(d["id.orig_p"]), count(d["id.resp_p"])
            if max(sport, dport) > 65535:
                raise ValueError("Invalid source port")
            label = d["label"] + " / " + d["det_label"]
            rows.append(Connection(
                len(rows) + 1, uid, microseconds(d["ts"]),
                None if d["duration"] == "-" else microseconds(d["duration"]),
                src.packed, sport, dst.packed, dport, 6 if d["proto"] == "tcp" else 17,
                tuple(count(d[k]) for k in ["orig_pkts", "orig_ip_bytes", "resp_pkts", "resp_ip_bytes"]),
                label, policy["binary_labels"].get(label), count(d["missed_bytes"]),
                d["tunnel_parents"] not in ("-", "(empty)"), d["conn_state"], d["history"],
            ))
    if metadata.get("separator") != r"\x09" or metadata.get("unset_field") != "-":
        raise ValueError("Unsupported source log separator or unset marker")
    if len(metadata.get("types", [])) != len(metadata.get("fields", [])):
        raise ValueError("Log type/field mismatch")
    return rows, metadata


def association(packets: list[Packet], connections: list[Connection], unsupported):
    """Never break tuple/time ties, including same-label ties."""
    by_key, by_family = defaultdict(list), defaultdict(list)
    for c in connections:
        by_key[c.key].append(c)
        by_family[c.family].append(c)
    unique, packets_by_conn, ambiguity, ambiguous_connections, vetoes = {}, defaultdict(list), {}, set(), set()
    statuses = Counter()
    for packet in packets:
        candidates = [c for c in by_key.get(packet.key, []) if c.temporal_candidate(packet.ts)]
        if not candidates:
            statuses["unmatched"] += 1
        elif len(candidates) > 1:
            statuses["ambiguous"] += 1
            ambiguous_connections.update(c.row for c in candidates)
            ambiguity[packet.ordinal] = "mixed_label" if len({c.label for c in candidates}) > 1 else "same_label"
        else:
            c = candidates[0]
            if c.end is None or c.direction(packet) is None:
                statuses["unsupported_connection"] += 1
                vetoes.add(c.row)
            else:
                statuses["unique_candidate"] += 1
                unique[packet.ordinal] = c.row
                packets_by_conn[c.row].append(packet)
    for ts, fam in unsupported:
        for c in by_family.get(fam, []):
            if c.temporal_candidate(ts):
                vetoes.add(c.row)
    results, admitted = {}, set()
    for c in connections:
        assigned = packets_by_conn[c.row]
        totals = [0, 0, 0, 0]
        for p in assigned:
            direction = c.direction(p)
            totals[direction * 2] += 1
            totals[direction * 2 + 1] += p.ip_bytes
        reasons = []
        if c.end is None:
            reasons.append("unset_zero_packet_duration" if c.counts[0]+c.counts[2] == 0 else "unset_multi_packet_duration")
        if c.row in ambiguous_connections:
            reasons.append("competing_tuple_time_candidate")
        if c.row in vetoes:
            reasons.append("unsupported_packet_or_connection")
        if tuple(totals) != c.counts:
            reasons.append("directional_count_or_ip_byte_mismatch")
        if not assigned:
            reasons.append("no_unique_packets")
        else:
            if min(p.ts for p in assigned) != c.ts:
                reasons.append("first_timestamp_mismatch")
            if max(p.ts for p in assigned) != c.end:
                reasons.append("last_timestamp_mismatch")
        if c.missed:
            reasons.append("source_missed_bytes")
        if c.tunnel:
            reasons.append("source_tunnel")
        if not reasons:
            admitted.add(c.row)
        results[c.row] = {"row": c.row, "label": c.label, "binary": c.binary,
                          "source_duration_us": c.duration, "expected": list(c.counts),
                          "unique_candidate_observed": totals, "admitted": not reasons,
                          "reasons": reasons}
    return unique, admitted, results, statuses, ambiguity


def distribution(values):
    values = sorted(values)
    if not values:
        return {"count": 0, "min": None, "p50": None, "p90": None, "p99": None, "max": None}
    return {"count": len(values), "min": values[0], "p50": values[(len(values)-1)//2],
            "p90": values[((len(values)-1)*90)//100], "p99": values[((len(values)-1)*99)//100], "max": values[-1]}


def connection_profiles(connections, results):
    output = {}
    for label in sorted({c.label for c in connections}):
        selected = [c for c in connections if c.label == label]
        durations = [c.duration for c in selected if c.duration is not None]
        totals = [c.counts[0]+c.counts[2] for c in selected]
        output[label] = {
            "rows": len(selected), "protocols": dict(Counter(c.proto for c in selected)),
            "states": dict(Counter(c.state for c in selected)),
            "duration_unset": sum(c.duration is None for c in selected),
            "unset_zero_packet_counters": sum(c.duration is None and c.counts[0]+c.counts[2] == 0 for c in selected),
            "unset_single_packet": sum(c.duration is None and c.counts[0]+c.counts[2] == 1 for c in selected),
            "unset_multi_packet": sum(c.duration is None and c.counts[0]+c.counts[2] > 1 for c in selected),
            "known_duration_us": distribution(durations), "source_packet_counts": distribution(totals),
            "packet_count_histogram": dict(Counter("0" if n == 0 else "1" if n == 1 else "2" if n == 2 else "3-9" if n < 10 else "10+" for n in totals)),
            "sum_source_packets": sum(totals),
            "admitted_connections": sum(results[c.row]["admitted"] for c in selected),
            "admitted_source_packets": sum(c.counts[0]+c.counts[2] for c in selected if results[c.row]["admitted"]),
            "rejection_reasons_nonexclusive": dict(Counter(r for c in selected for r in results[c.row]["reasons"])),
            "positive_durations_at_least_us": {str(t): sum(x >= t for x in durations) for t in [1_000_000,10_000_000,60_000_000]},
        }
    return output


def selected(ordinal, denominator, seed):
    if denominator == 1:
        return True
    h = hashlib.sha256((seed + ":" + str(ordinal)).encode()).digest()
    return int.from_bytes(h, "big") < (1 << 256) // denominator


def propagated_label(tokens):
    """Unknown/excluded packets are never silently dropped from a new record."""
    binary = {t for t in tokens if t in ("benign", "ddos")}
    if len(binary) > 1:
        return "mixed_binary_label"
    if any(t not in ("benign", "ddos") for t in tokens):
        return "unknown_or_excluded"
    return next(iter(binary)) if binary else "unknown_or_excluded"


def meter_diagnostic(packets, connections, unique, admitted, policy, active_us, idle_us, denominator):
    by_row = {c.row: c for c in connections}
    cache, output, labels, expiration = {}, [], Counter(), Counter()
    eligible_packet_counts, source_spans = Counter(), Counter()
    selected_packets, unknown_packets, excluded_packets = 0, 0, 0

    def close(key, reason):
        f = cache.pop(key)
        label = propagated_label(f["tokens"])
        labels[label] += 1
        expiration[reason] += 1
        if label in ("benign", "ddos"):
            eligible_packet_counts[label] += f["count"]
        source_spans[str(len(f["connections"]))] += 1
        output.append((label, f["count"], f["last"]-f["first"]))

    for p in packets:
        if not selected(p.ordinal, denominator, policy["sampling_seed"]):
            continue
        selected_packets += 1
        source_row = unique.get(p.ordinal)
        if source_row not in admitted:
            token = "unknown"
            unknown_packets += 1
        elif by_row[source_row].binary is None:
            token = "excluded"
            excluded_packets += 1
        else:
            token = by_row[source_row].binary
        f = cache.get(p.key)
        if f and p.ts-f["first"] >= active_us:
            close(p.key, "active")
        elif f and p.ts-f["last"] >= idle_us:
            close(p.key, "idle")
        if p.key not in cache:
            cache[p.key] = {"first": p.ts, "last": p.ts, "count": 0, "tokens": set(), "connections": set()}
        f = cache[p.key]
        f["last"] = p.ts
        f["count"] += 1
        f["tokens"].add(token)
        if source_row is not None:
            f["connections"].add(source_row)
    for key in list(cache):
        close(key, "eof")
    return {"active_us": active_us, "idle_us": idle_us, "sampling_denominator": denominator,
            "selected_supported_packets": selected_packets, "unknown_packets": unknown_packets,
            "excluded_category_packets": excluded_packets, "new_records": len(output),
            "new_record_labels": dict(labels), "expiration_triggers": dict(expiration),
            "binary_eligible_packet_counts": dict(eligible_packet_counts),
            "source_connections_per_record_histogram": dict(source_spans),
            "binary_eligible_record_packet_counts": {label: distribution([n for l,n,d in output if l == label]) for label in ["benign","ddos"]},
            "binary_eligible_record_duration_us": {label: distribution([d for l,n,d in output if l == label]) for label in ["benign","ddos"]}}


def raw_identity(frame, h):
    h.update(struct.pack("!qII", frame.ts, frame.captured, frame.wire))
    h.update(frame.data)


def libpcap_control(path):
    """Independent installed libpcap container reader; not a second flow labeler."""
    class Timeval(ctypes.Structure):
        _fields_ = [("tv_sec", ctypes.c_long), ("tv_usec", ctypes.c_long)]

    class Header(ctypes.Structure):
        _fields_ = [("ts", Timeval), ("caplen", ctypes.c_uint32), ("length", ctypes.c_uint32)]

    libpath = ctypes.util.find_library("pcap")
    if not libpath:
        raise RuntimeError("Installed libpcap not located")
    lib = ctypes.CDLL(libpath)
    lib.pcap_open_offline.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
    lib.pcap_open_offline.restype = ctypes.c_void_p
    lib.pcap_next_ex.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.POINTER(Header)), ctypes.POINTER(ctypes.POINTER(ctypes.c_ubyte))]
    lib.pcap_next_ex.restype = ctypes.c_int
    lib.pcap_close.argtypes = [ctypes.c_void_p]
    lib.pcap_datalink.argtypes = [ctypes.c_void_p]
    lib.pcap_datalink.restype = ctypes.c_int
    lib.pcap_lib_version.restype = ctypes.c_char_p
    error = ctypes.create_string_buffer(256)
    handle = lib.pcap_open_offline(os.fsencode(path), error)
    if not handle:
        raise RuntimeError("libpcap offline open failed")
    h, n, first, last = hashlib.sha256(), 0, None, None
    try:
        if lib.pcap_datalink(handle) != 1:
            raise ValueError("Independent reader link type differs")
        header, data = ctypes.POINTER(Header)(), ctypes.POINTER(ctypes.c_ubyte)()
        while True:
            status = lib.pcap_next_ex(handle, ctypes.byref(header), ctypes.byref(data))
            if status == -2:
                break
            if status != 1:
                raise RuntimeError("libpcap offline record failed")
            d = header.contents
            ts = int(d.ts.tv_sec)*1_000_000 + int(d.ts.tv_usec)
            if not 0 <= d.ts.tv_usec < 1_000_000 or d.caplen > 16_777_216:
                raise ValueError("Invalid independent record")
            h.update(struct.pack("!qII", ts, d.caplen, d.length))
            h.update(ctypes.string_at(data, d.caplen))
            n += 1
            first = ts if first is None else first
            last = ts
        return {"library": libpath, "version": lib.pcap_lib_version().decode(), "records": n,
                "first_ts_us": first, "last_ts_us": last, "record_stream_sha256": h.hexdigest()}
    finally:
        lib.pcap_close(handle)


TCPDUMP_LINE = re.compile(r"^(\d+\.\d+)\s+IP\s+(\d+\.\d+\.\d+\.\d+)\.(\d+)\s+>\s+(\d+\.\d+\.\d+\.\d+)\.(\d+):\s+(tcp|UDP)\b", re.IGNORECASE)


def tcpdump_control(path, packets, executable):
    expected = {p.ordinal: p for p in packets}
    command = [str(executable), "-nn", "-tt", "-q", "-r", str(path)]
    start = time.monotonic()
    result = subprocess.run(command, capture_output=True, timeout=180)
    if result.returncode:
        raise RuntimeError("Offline tcpdump failed")
    n, compared, unparsed_supported, mismatch, parsed_unsupported = 0, 0, 0, 0, 0
    first, last = None, None
    for line in result.stdout.decode("utf-8", errors="replace").splitlines():
        prefix = re.match(r"^(\d+\.\d+)\s", line)
        if not prefix:
            continue
        n += 1
        ts = microseconds(prefix.group(1))
        first = ts if first is None else first
        last = ts
        match = TCPDUMP_LINE.match(line)
        p = expected.get(n)
        if p is None:
            parsed_unsupported += int(match is not None)
            continue
        if not match:
            unparsed_supported += 1
            continue
        t,src,sport,dst,dport,proto = match.groups()
        observed = (microseconds(t),ipaddress.IPv4Address(src).packed,int(sport),ipaddress.IPv4Address(dst).packed,int(dport),6 if proto.lower()=="tcp" else 17)
        compared += 1
        mismatch += observed != (p.ts,p.src,p.sport,p.dst,p.dport,p.proto)
    return {"command": command, "exit_code": result.returncode, "elapsed_seconds": time.monotonic()-start,
            "all_packet_records": n, "first_ts_us": first, "last_ts_us": last,
            "supported_tuples_compared": compared, "supported_tuples_unparsed": unparsed_supported,
            "tuple_or_timestamp_mismatches": mismatch, "tool_parsed_policy_unsupported": parsed_unsupported,
            "stdout_sha256": hashlib.sha256(result.stdout).hexdigest(),
            "stderr_sha256": hashlib.sha256(result.stderr).hexdigest(), "packet_text_retained": False,
            "scope": "Offline numeric timestamp/directional IPv4 TCP/UDP tuple decoding; not historical Zeek reconstruction or independent label truth"}


def seal(path):
    stat = path.stat()
    return {"path": str(path), "bytes": stat.st_size, "mode": oct(stat.st_mode & 0o777),
            "mtime_ns": stat.st_mtime_ns, "sha256": digest(path)}


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")


def run(contract_path, expected_contract_sha, output):
    started_utc, started = datetime.now(timezone.utc).isoformat(), time.monotonic()
    code_root = Path(__file__).resolve().parents[1]
    workspace = Path(os.environ["FDDOS_WORKSPACE"]).resolve()
    contract_path = contract_path.resolve()
    output = output.resolve()
    if not contract_path.is_relative_to(workspace) or not output.is_relative_to(workspace):
        raise ValueError("Runtime paths must stay in FDDOS_WORKSPACE")
    if digest(contract_path) != expected_contract_sha:
        raise ValueError("Input contract seal mismatch")
    contract = json.loads(contract_path.read_text())
    if contract["version"] != "raw-label-admission-input-v1":
        raise ValueError("Unexpected input contract")
    commit = subprocess.check_output(["git","-C",str(code_root),"rev-parse","HEAD"],text=True).strip()
    if commit != contract["code_commit"] or subprocess.check_output(["git","-C",str(code_root),"status","--porcelain"],text=True).strip():
        raise ValueError("Audit requires the frozen clean code commit")
    for relative, expected in contract["source_sha256"].items():
        if digest(code_root/relative) != expected:
            raise ValueError("Frozen source hash mismatch")
    if digest(code_root/"uv.lock") != contract["uv_lock_sha256"]:
        raise ValueError("Dependency lock mismatch")
    policy_path = code_root/"docs/raw-label-policy-v1.json"
    if digest(policy_path) != contract["policy_sha256"]:
        raise ValueError("Policy mismatch")
    policy = json.loads(policy_path.read_text())
    input_paths = [Path(contract[k]["path"]).resolve() for k in ("capture","labels")]
    if any(not p.is_relative_to(workspace) for p in input_paths):
        raise ValueError("Input path escapes workspace")
    if output.exists() or any(output == p or output in p.parents or p in output.parents for p in input_paths):
        raise ValueError("Output must be a new independent directory")
    before = [seal(p) for p in input_paths]
    for key, entry in zip(("capture","labels"),before):
        if entry["sha256"] != contract[key]["sha256"] or entry["mode"] != "0o444":
            raise ValueError("Original input hash/read-only mode mismatch")
    output.mkdir(parents=True)
    phases, phase = {}, time.monotonic()
    connections, headers = read_connections(input_paths[1],policy)
    phases["source_log_parse"] = time.monotonic()-phase
    phase = time.monotonic()
    packets, unsupported, decoded_counts = [], [], Counter()
    record_hash, frame_count, total_captured, total_wire = hashlib.sha256(), 0, 0, 0
    first, last = None, None
    for frame in pcap_frames(input_paths[0]):
        raw_identity(frame,record_hash)
        frame_count += 1
        total_captured += frame.captured
        total_wire += frame.wire
        first = frame.ts if first is None else first
        last = frame.ts
        decoded = decode(frame)
        decoded_counts[decoded.reason] += 1
        if decoded.packet:
            packets.append(decoded.packet)
        elif decoded.family:
            unsupported.append((frame.ts,decoded.family))
    phases["pcap_decode"] = time.monotonic()-phase
    phase = time.monotonic()
    unique, admitted, results, statuses, ambiguity = association(packets,connections,unsupported)
    phases["strict_source_association"] = time.monotonic()-phase
    phase = time.monotonic()
    independent_lib = libpcap_control(input_paths[0])
    if independent_lib["records"] != frame_count or independent_lib["record_stream_sha256"] != record_hash.hexdigest():
        raise ValueError("Independent libpcap record stream disagrees")
    independent_tcpdump = tcpdump_control(input_paths[0],packets,contract["tcpdump"])
    if independent_tcpdump["all_packet_records"] != frame_count or independent_tcpdump["tuple_or_timestamp_mismatches"] or independent_tcpdump["supported_tuples_unparsed"]:
        raise ValueError("Independent tcpdump packet decoding disagrees or is incomplete")
    phases["independent_installed_readers"] = time.monotonic()-phase
    phase = time.monotonic()
    diagnostics = []
    for active in policy["diagnostic_grid"]["active_seconds"]:
        for idle in policy["diagnostic_grid"]["idle_seconds"]:
            for denominator in policy["diagnostic_grid"]["sampling_denominators"]:
                diagnostics.append(meter_diagnostic(packets,connections,unique,admitted,policy,active*1_000_000,idle*1_000_000,denominator))
    phases["diagnostic_sampling_and_timeout_coverage"] = time.monotonic()-phase
    profiles = connection_profiles(connections,results)
    by_row = {c.row:c for c in connections}
    transferred = Counter(by_row[row].label for ordinal,row in unique.items() if row in admitted)
    binary_transferred = Counter(by_row[row].binary for ordinal,row in unique.items() if row in admitted and by_row[row].binary)
    known_duration_packets = sum(1 for ordinal,row in unique.items() if row in admitted and by_row[row].duration is not None)
    with (output/"packet-association.tsv").open("w",encoding="utf-8",newline="") as f:
        writer = csv.writer(f,delimiter="\t")
        writer.writerow(["packet_ordinal","source_row_ordinal","association_status","binary_label"])
        for packet in packets:
            row = unique.get(packet.ordinal)
            writer.writerow([packet.ordinal,row or "", "admitted" if row in admitted else "unique_unreconciled" if row else "ambiguous" if packet.ordinal in ambiguity else "unassigned", by_row[row].binary if row in admitted else ""])
    write_json(output/"connection-reconciliation.json",list(results.values()))
    write_json(output/"source-label-profiles.json",profiles)
    write_json(output/"diagnostic-grid.json",diagnostics)
    write_json(output/"independent-readers.json",{"libpcap":independent_lib,"tcpdump":independent_tcpdump})
    after = [seal(p) for p in input_paths]
    if before != after or digest(contract_path) != expected_contract_sha:
        raise ValueError("Original input or contract changed during audit")
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    rss_bytes = peak if sys.platform == "darwin" else peak*1024
    summary = {
        "version":"raw-label-admission-v1", "status":"completed_conservative_engineering_admission_audit",
        "started_utc":started_utc,"finished_utc":datetime.now(timezone.utc).isoformat(),
        "elapsed_monotonic_seconds":time.monotonic()-started,"phase_seconds":phases,
        "timing_boundary":"Process main through final input reseal; final summary/COMPLETE serialization excluded",
        "peak_process_rss_bytes":rss_bytes,"python":sys.version,"platform":platform.platform(),
        "pid":os.getpid(),"workers":1,"device":"CPU","random_seed":policy["sampling_seed"],
        "thread_environment":{k:os.environ.get(k) for k in ["OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS","VECLIB_MAXIMUM_THREADS"]},
        "actual_os_threads":"not recorded","energy":"not recorded","code_commit":commit,
        "contract_sha256":expected_contract_sha,"policy_sha256":digest(policy_path),
        "source_sha256":contract["source_sha256"],"uv_lock_sha256":contract["uv_lock_sha256"],
        "original_inputs_before":before,"original_inputs_after":after,"originals_unchanged":True,
        "source_log_header":headers,"source_connections":len(connections),"capture_records":frame_count,
        "captured_bytes":total_captured,"wire_length_sum":total_wire,"first_ts_us":first,"last_ts_us":last,
        "decode_statuses":dict(decoded_counts),"supported_packet_association_statuses":dict(statuses),
        "ambiguous_packet_labels":dict(Counter(ambiguity.values())),"admitted_source_connections":len(admitted),
        "admitted_packet_labels":dict(transferred),"binary_admitted_packet_labels":dict(binary_transferred),
        "admitted_known_duration_packets":known_duration_packets,
        "admitted_unset_single_point_packets":sum(transferred.values())-known_duration_packets,
        "source_label_profiles":profiles,"diagnostic_configurations":len(diagnostics),
        "actual_model_fit_score_calibration_selection":False,"packet_replay_or_live_capture":False,
        "DNS_or_network_traffic":False,"split_roles_assigned":False,
        "limits":["Source analyst connection labels, not independently established packet-level attack onset/end truth.",
                  "Exact conservative core intervals can leave trailing TCP packets or precision disagreements unassigned; no tolerance or interval repair.",
                  "No IPv6, fragmentation reassembly, tunnel decoding, checksum validation or historical Zeek/config replication.",
                  "UIDs and timeout records are not independent physical episodes; one source scenario cannot establish scenario-level generalization.",
                  "Diagnostic grid is one deterministic thinning realization and custom cache, not a live-router input contract or tuned model result.",
                  "Historical authorization notice, declared CC-BY release grant and unverified archive-member byte provenance remain as acquired."]}
    write_json(output/"summary.json",summary)
    artifacts = {p.name:digest(p) for p in output.iterdir() if p.is_file()}
    write_json(output/"COMPLETE.json",{"status":"completed","code_commit":commit,"policy_sha256":digest(policy_path),"contract_sha256":expected_contract_sha,"artifacts":artifacts})
    print(json.dumps({"status":summary["status"],"output":str(output),"capture_records":frame_count,"admitted_connections":len(admitted),"binary_packet_counts":dict(binary_transferred),"elapsed_seconds":summary["elapsed_monotonic_seconds"],"peak_rss_bytes":rss_bytes}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract",type=Path,required=True)
    parser.add_argument("--contract-sha256",required=True)
    parser.add_argument("--output",type=Path,required=True)
    args = parser.parse_args()
    run(args.contract,args.contract_sha256,args.output)


if __name__ == "__main__":
    main()
