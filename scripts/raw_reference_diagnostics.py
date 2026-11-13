"""Full-trace reference diagnostics, never a sampled/live feature extractor.

Complete-packet checksum status is audited without changing the historical
counter-join admission. It is not proof of wire integrity or offload policy.
"""
from collections import Counter, defaultdict
from pathlib import Path
import struct
import raw_label_admission as base


def checksum_sum(data):
    if len(data) % 2:data += b"\0"
    value=sum(struct.unpack("!"+"H"*(len(data)//2),data))
    while value >> 16:value=(value & 65535)+(value >> 16)
    return value


def inspect_complete(frame,packet):
    """Read only bytes already accepted by the base complete-packet decoder."""
    offset=14+4*packet.vlans;ihl=(frame.data[offset] & 15)*4
    header=frame.data[offset:offset+ihl]
    payload=frame.data[offset+ihl:offset+packet.ip_bytes]
    if len(header)!=ihl or len(payload)!=packet.ip_bytes-ihl:
        raise ValueError("Complete audit requires complete decoded bytes")
    statuses={"ipv4_header":"valid" if checksum_sum(header)==65535 else "bad"}
    pseudo=packet.src+packet.dst+struct.pack("!BBH",0,packet.proto,len(payload))
    if packet.proto==17:
        transmitted=struct.unpack_from("!H",payload,6)[0]
        statuses["udp"]="not_present" if transmitted==0 else "valid" if checksum_sum(pseudo+payload)==65535 else "bad"
        udp_payload=len(payload)-8
    elif packet.proto==6:
        statuses["tcp"]="valid" if checksum_sum(pseudo+payload)==65535 else "bad"
        udp_payload=None
    else:raise ValueError("Only decoded IPv4 TCP/UDP is supported")
    return statuses,udp_payload


class CompleteChecksumAudit:
    def __init__(self):
        self.counts=defaultdict(Counter);self.flagged=defaultdict(set)
    def observe(self,frame,packet):
        statuses,payload=inspect_complete(frame,packet)
        for name,status in statuses.items():
            self.counts[name][status]+=1
            if status!="valid":self.flagged[name+":"+status].add(packet.ordinal)
        return payload
    def report(self,unique,admitted,by_row):
        affected={}
        for name,ordinals in self.flagged.items():
            rows={unique[n] for n in ordinals if n in unique}
            accepted=rows & admitted
            affected[name]={"complete_packets":len(ordinals),"unique_candidate_source_rows":len(rows),
                            "admitted_source_rows":len(accepted),
                            "admitted_source_labels":dict(Counter(by_row[row].label for row in accepted))}
        return {"scope":"Complete nonfragment decoded packets only; original fragment checksum validation remains separate",
                "counts":{name:dict(values) for name,values in self.counts.items()},"affected_rows":affected,
                "admission_action":"AUDIT_ONLY_NO_NEW_CHECKSUM_FILTER", "historical_checksum_or_offload_policy":"UNVERIFIED",
                "meaning":"Bad does not establish its cause. UDP not_present is not checksum validation; IPv4 zero is checked arithmetically, never treated as absent."}


def read_source_payload_counts(path,wanted_rows):
    """Stream optional UDP payload counters, retaining only requested source rows."""
    fields=None;row=0;answer={}
    with Path(path).open(encoding="utf-8") as stream:
        for line in stream:
            if line.startswith("#fields\t"):fields=line.rstrip("\n").split("\t")[1:]
            elif line.startswith("#"):continue
            elif line.strip():
                row+=1
                if row in wanted_rows:
                    if fields is None:raise ValueError("Missing source fields")
                    values=line.rstrip("\n").split("\t")
                    if len(values)!=len(fields):raise ValueError("Source payload field count mismatch")
                    d=dict(zip(fields,values))
                    answer[row]=tuple(None if d.get(key) in (None,"-") else base.count(d[key]) for key in ("orig_bytes","resp_bytes"))
    if set(answer)!=set(wanted_rows):raise ValueError("Requested source payload row missing")
    return answer


def udp_payload_comparison(connections,packets,unique,admitted,datagram_ordinals,payload_bytes,labels):
    by_row={c.row:c for c in connections}
    wanted={unique[n] for n in datagram_ordinals if n in unique and unique[n] in admitted}
    expected=read_source_payload_counts(labels,wanted)
    totals={row:[0,0] for row in wanted};unavailable=set()
    for packet in packets:
        row=unique.get(packet.ordinal)
        if row not in wanted:continue
        if packet.proto!=17 or packet.ordinal not in payload_bytes:unavailable.add(row);continue
        direction=by_row[row].direction(packet)
        if direction is None:unavailable.add(row)
        else:totals[row][direction]+=payload_bytes[packet.ordinal]
    rows=[]
    for row in sorted(wanted):
        status="unavailable" if row in unavailable or None in expected[row] else "match" if list(expected[row])==totals[row] else "mismatch"
        rows.append({"source_row":row,"source_label":by_row[row].label,"source_connection_counter_reconciled":True,
                     "expected_source_payload_bytes":list(expected[row]),"observed_UDP_payload_bytes":totals[row],"status":status})
    return {"scope":"UDP source rows containing validated datagrams; sum all joined UDP payloads in that source row",
            "unit":"UDP length minus its eight-byte header, distinct from IPv4 total length and wire bytes",
            "admission_action":"DIAGNOSTIC_ONLY_NO_NEW_LABEL_OR_COUNTER_VETO", "rows":rows,
            "status_counts":dict(Counter(r["status"] for r in rows)),"historical_analyzer_identity":"UNVERIFIED"}


def datagram_wire_timing(accepted,fragments,complete,unique,admitted,by_row):
    """Describe full-reference member spans and new-row wire gaps; no selected features."""
    spans=defaultdict(list);inside=defaultdict(list);wire=defaultdict(list)
    target_rows=set();group_counts=Counter()
    for group in accepted:
        row=unique.get(group["completion_frame"])
        label=by_row[row].label if row in admitted else "UNRECONCILED"
        members=sorted((fragments[n].ts,n) for n in group["members"])
        spans[label].append(members[-1][0]-members[0][0])
        inside[label].append(max((b[0]-a[0] for a,b in zip(members,members[1:])),default=0))
        if row in admitted:
            target_rows.add(row);group_counts[row]+=1;wire[row].extend(members)
    for packet in complete:
        row=unique.get(packet.ordinal)
        if row in target_rows:wire[row].append((packet.ts,packet.ordinal))
    rows=[]
    for row in sorted(target_rows):
        ordered=sorted(wire[row]);gaps=[b[0]-a[0] for a,b in zip(ordered,ordered[1:])]
        rows.append({"source_row":row,"source_label":by_row[row].label,"validated_datagrams":group_counts[row],
                     "original_wire_frames":len(ordered),"max_successive_wire_gap_us":max(gaps,default=None),
                     "wire_gap_at_least_us":{str(t):sum(g>=t for g in gaps) for t in [1000000,15000000]}})
    return {"scope":"Full-trace admitted datagram reference; timing is recorded capture time, not onset truth, cache readiness or a sampled-feature result",
            "datagram_member_span_us_by_source_label":{label:base.distribution(values) for label,values in spans.items()},
            "largest_internal_fragment_gap_us_by_source_label":{label:base.distribution(values) for label,values in inside.items()},
            "wire_profiles_for_source_rows_containing_datagrams":rows,"sampled_features_computed":False}
