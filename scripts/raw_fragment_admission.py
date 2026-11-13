"""TShark-proposed IPv4UDP reassembly with independent byte/lineage validation.

Offline label reconciliation only. The forwarding and sampled-feature paths are
not configured by this script. Runtime input/tool paths belong in private data.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
import argparse
import csv
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import resource
import struct
import subprocess
import sys
import time

import raw_label_admission as base

FIELDS = ["frame.number", "frame.time_epoch", "ip.fragment", "ip.fragment.count",
          "ip.fragment.overlap", "ip.fragment.overlap.conflict", "ip.fragment.multipletails",
          "ip.fragment.toolongfragment", "ip.fragment.error", "ip.reassembled.length",
          "ip.reassembled.data", "udp.srcport", "udp.dstport", "udp.length", "udp.checksum.status"]


def internet_sum(data):
    if len(data) & 1:
        data += b"\0"
    total = sum(struct.unpack("!"+"H"*(len(data)//2),data))
    while total >> 16:
        total = (total & 65535)+(total >> 16)
    return total


@dataclass
class Fragment:
    ordinal: int
    ts: int
    src: bytes
    dst: bytes
    proto: int
    ident: int
    offset: int
    more: bool
    header: bytes
    payload: bytes
    vlans: tuple
    captured: int
    wire: int
    frame_sha256: str
    errors: list[str]

    @property
    def key(self): return (self.src,self.dst,self.proto,self.ident)
    @property
    def family(self): return base.family(self.src,self.dst,self.proto)
    @property
    def end(self): return self.offset+len(self.payload)


def fragment(frame):
    """Recognize fragment headers even when their captured body is truncated."""
    data=frame.data
    if len(data)<14: return None
    eth=struct.unpack_from("!H",data,12)[0];off=14;tags=[]
    while eth in (0x8100,0x88a8):
        if len(tags)>=4 or len(data)<off+4: return None
        tci,following=struct.unpack_from("!HH",data,off);tags.append((eth,tci));eth=following;off+=4
    if eth!=0x0800 or len(data)<off+20: return None
    bits=struct.unpack_from("!H",data,off+6)[0]
    if not bits & 0x3fff: return None
    ihl=(data[off]&15)*4;total=struct.unpack_from("!H",data,off+2)[0]
    proto=data[off+9];src=data[off+12:off+16];dst=data[off+16:off+20]
    errors=[]
    if data[off]>>4!=4 or ihl<20 or ihl>60 or total<ihl:errors.append("invalid_ipv4_header")
    if ihl!=20:errors.append("unsupported_ipv4_options")
    if frame.captured<frame.wire or len(data)<off+total:errors.append("truncated_fragment")
    header=data[off:off+ihl]
    if len(header)!=ihl or internet_sum(header)!=65535:errors.append("bad_ip_checksum")
    if bits & 0xc000:errors.append("DF_or_reserved_fragment_flag")
    offset=(bits&0x1fff)*8;more=bool(bits&0x2000)
    payload=data[off+ihl:off+total]
    if not payload:errors.append("empty_fragment_payload")
    if more and len(payload)%8:errors.append("nonfinal_payload_not_8byte_aligned")
    if offset+len(payload)+20>65535:errors.append("reassembled_length_overflow")
    if proto!=17:errors.append("unsupported_fragment_protocol")
    return Fragment(frame.ordinal,frame.ts,src,dst,proto,struct.unpack_from("!H",data,off+4)[0],offset,more,header,payload,tuple(tags),frame.captured,frame.wire,hashlib.sha256(data).hexdigest(),errors)


def tshark_command(executable,capture):
    # -r is mandatory. Never invoke a default capture path.
    args=[str(executable),"-n","-2","-r",str(capture),"--disable-protocol","ALL",
          "--enable-protocol","eth,vlan,ip,udp,data","-o","ip.defragment:TRUE",
          "-o","ip.check_checksum:TRUE","-o","udp.check_checksum:TRUE",
          "-T","fields","-E","separator=\t","-E","occurrence=a","-E","aggregator=,"]
    for name in FIELDS:args.extend(["-e",name])
    return args


def proposals(executable,capture,config):
    config.mkdir(parents=True,exist_ok=False)
    plugins=config/"empty-plugins";plugins.mkdir()
    env=os.environ.copy();env["WIRESHARK_CONFIG_DIR"]=str(config);env["WIRESHARK_PLUGIN_DIR"]=str(plugins);env["WIRESHARK_EXTCAP_DIR"]=str(plugins)
    cmd=tshark_command(executable,capture);start=time.monotonic()
    measured=["/usr/bin/time","-l",*cmd] if sys.platform=="darwin" else cmd
    p=subprocess.run(measured,env=env,capture_output=True,timeout=180)
    if p.returncode: raise RuntimeError("Pinned offline TShark failed: "+p.stderr.decode(errors="replace")[:1500])
    rows=[];frame_count=0
    for line in p.stdout.decode("utf-8").splitlines():
        values=line.split("\t")
        if len(values)!=len(FIELDS):raise ValueError("Unexpected TShark field count")
        d=dict(zip(FIELDS,values));frame_count+=1
        if int(d["frame.number"])!=frame_count:raise ValueError("TShark frame sequence differs")
        if not d["ip.fragment"]:continue
        members=[int(v) for v in d["ip.fragment"].split(",")]
        errors=[name for name in FIELDS[4:9] if d[name] and d[name] not in ("0","False","false")]
        rows.append({"completion_frame":int(d["frame.number"]),"completion_ts":base.microseconds(d["frame.time_epoch"]),
                     "members":members,"tool_errors":errors,"tool_length":int(d["ip.reassembled.length"] or 0),
                     "tool_payload":bytes.fromhex(d["ip.reassembled.data"].replace(":","")),
                     "tool_sport":int(d["udp.srcport"]) if d["udp.srcport"] else None,
                     "tool_dport":int(d["udp.dstport"]) if d["udp.dstport"] else None,
                     "tool_udp_length":int(d["udp.length"]) if d["udp.length"] else None,
                     "tool_udp_checksum_status":d["udp.checksum.status"]})
    import re
    match=re.search(rb"(\d+)\s+maximum resident set size",p.stderr) if sys.platform=="darwin" else None
    return rows,{"command":cmd,"measured_command":measured,"exit_code":p.returncode,"elapsed_monotonic_seconds":time.monotonic()-start,
                 "TShark_peak_RSS_bytes":int(match.group(1)) if match else None,
                 "all_frame_rows":frame_count,"proposed_groups":len(rows),"stdout_sha256":hashlib.sha256(p.stdout).hexdigest(),
                 "stderr_sha256":hashlib.sha256(p.stderr).hexdigest(),"raw_tshark_text_retained":False,
                 "config_isolated":True,"nonrequired_application_protocols_disabled":True,"DNS_or_live_capture":False}


def validate_group(proposal,fragments):
    reasons=list(proposal["tool_errors"]);ids=proposal["members"]
    if len(ids)<2 or len(set(ids))!=len(ids):reasons.append("duplicate_or_too_few_members")
    if not ids:return None,reasons
    if any(n not in fragments for n in ids):return None,[*reasons,"member_not_a_recognized_fragment"]
    parts=[fragments[n] for n in ids];keys={f.key for f in parts}
    if len(keys)!=1:reasons.append("mixed_standard_keys")
    if len({f.vlans for f in parts})!=1:reasons.append("mixed_VLAN_context")
    for f in parts:reasons.extend(f.errors)
    starts=[f for f in parts if f.offset==0];tails=[f for f in parts if not f.more]
    if len(starts)!=1:reasons.append("missing_or_multiple_initial")
    if len(tails)!=1:reasons.append("missing_or_multiple_tail")
    sorted_parts=sorted(parts,key=lambda f:(f.offset,f.ordinal));end=0
    for f in sorted_parts:
        if f.offset<end:reasons.append("overlap_or_duplicate")
        if f.offset>end:reasons.append("hole")
        end=max(end,f.end)
    if tails and any(f.end!=end for f in tails):reasons.append("tail_length_conflict")
    if end+20>65535:reasons.append("reassembled_length_overflow")
    if proposal["completion_frame"]!=max(ids) or proposal["completion_ts"]!=max(f.ts for f in parts):reasons.append("completion_identity_mismatch")
    payload=b"".join(f.payload for f in sorted_parts)
    checksum="unsupported"
    sport=dport=None
    if len(payload)>65535:reasons.append("UDP_payload_length_overflow")
    elif len(payload)<8:reasons.append("short_reassembled_udp")
    else:
        sport,dport,length,check=struct.unpack_from("!HHHH",payload)
        if length!=len(payload) or length<8:reasons.append("UDP_length_mismatch")
        pseudo=parts[0].src+parts[0].dst+b"\0\x11"+struct.pack("!H",len(payload))
        checksum="not_present" if check==0 else "valid" if internet_sum(pseudo+payload)==65535 else "bad"
        if checksum=="bad":reasons.append("bad_UDP_checksum")
        expected_status="3" if checksum=="not_present" else "1"
        if proposal["tool_udp_checksum_status"]!=expected_status:reasons.append("tool_UDP_checksum_disagreement")
        if (sport,dport,length)!=(proposal["tool_sport"],proposal["tool_dport"],proposal["tool_udp_length"]):reasons.append("tool_transport_disagreement")
    if payload!=proposal["tool_payload"] or len(payload)!=proposal["tool_length"]:reasons.append("tool_reassembled_bytes_or_length_disagreement")
    record={"completion_frame":proposal["completion_frame"],"members":ids,"key":parts[0].key,
            "first_ts":min(f.ts for f in parts),"last_ts":max(f.ts for f in parts),
            "first_ordinal":min(ids),"last_ordinal":max(ids),"initial_fragment_ts":starts[0].ts if len(starts)==1 else None,
            "payload_sha256":hashlib.sha256(payload).hexdigest(),"ip_bytes":20+len(payload),
            "udp_checksum":checksum,"sport":sport,"dport":dport,"reasons":sorted(set(reasons))}
    return record,record["reasons"]


def validate_all(proposed,fragments):
    groups=[];owners=defaultdict(list);by_key=defaultdict(list)
    for proposal in proposed:
        record,reasons=validate_group(proposal,fragments)
        if record is None:
            groups.append({"completion_frame":proposal["completion_frame"],"members":proposal["members"],"reasons":reasons,"admitted":False})
            continue
        groups.append(record);by_key[record["key"]].append(record)
        for member in record["members"]:owners[member].append(record)
    unresolved=set(fragments)-set(owners)
    unresolved_keys={fragments[n].key for n in unresolved}
    shared_keys={fragments[n].key for n,o in owners.items() if len(o)>1}
    for key,records in by_key.items():
        veto=[]
        if key in unresolved_keys:veto.append("same_key_unresolved_fragment")
        if key in shared_keys:veto.append("shared_fragment_membership")
        if any(r["reasons"] for r in records):veto.append("same_key_rejected_group")
        ordered=sorted(records,key=lambda r:(r["first_ts"],r["first_ordinal"]))
        for a,b in zip(ordered,ordered[1:]):
            if a["last_ts"]>=b["first_ts"] or a["last_ordinal"]>=b["first_ordinal"]:
                veto.append("ID_reuse_interleaving_or_timestamp_tie")
        for record in records:
            record["reasons"]=sorted(set(record["reasons"]+veto));record["admitted"]=not record["reasons"]
    accepted=[g for g in groups if g.get("admitted")]
    accepted_members={n for g in accepted for n in g["members"]}
    return groups,accepted,set(fragments)-accepted_members,{"unproposed_fragments":len(unresolved),"shared_membership_frames":sum(len(v)>1 for v in owners.values()),"standard_keys":len({f.key for f in fragments.values()}),"keys_with_multiple_proposals":sum(len(v)>1 for v in by_key.values())}


def public_group(g,fragments):
    result={k:v for k,v in g.items() if k not in ("key","sport","dport")}
    if "key" in g:
        key=g["key"];result["standard_key_sha256"]=hashlib.sha256(key[0]+key[1]+struct.pack("!BH",key[2],key[3])).hexdigest()
    result["lineage"]=[{"ordinal":f.ordinal,"timestamp_us":f.ts,"offset":f.offset,"payload_length":len(f.payload),
                        "more":f.more,"captured_bytes":f.captured,"wire_bytes":f.wire,"frame_sha256":f.frame_sha256,
                        "header_sha256":hashlib.sha256(f.header).hexdigest(),"payload_sha256":hashlib.sha256(f.payload).hexdigest()}
                       for n in g["members"] if (f:=fragments.get(n))]
    return result


def admitted_profiles(connections,results,packets,unique,admitted):
    times=defaultdict(list)
    for p in packets:
        row=unique.get(p.ordinal)
        if row in admitted:times[row].append(p.ts)
    profiles={}
    for label in sorted({c.label for c in connections}):
        selected=[c for c in connections if c.label==label and c.row in admitted];d=[c.duration for c in selected if c.duration is not None]
        gaps=[max(b-a for a,b in zip(t,t[1:])) for c in selected if len(t:=sorted(times[c.row]))>1]
        profiles[label]={"connections":len(selected),"protocols":dict(Counter(c.proto for c in selected)),
                         "known_duration_us":base.distribution(d),"largest_internal_gap_us":base.distribution(gaps),
                         "duration_at_least_us":{str(x):sum(v>=x for v in d) for x in [1000000,10000000,15000000,60000000]},
                         "gap_at_least_us":{str(x):sum(v>=x for v in gaps) for x in [1000000,15000000]},
                         "source_domain_packets":sum(c.counts[0]+c.counts[2] for c in selected)}
    return profiles


def run(contract_path,expected_hash,output):
    started=time.monotonic();utc=datetime.now(timezone.utc).isoformat();root=Path(__file__).resolve().parents[1]
    workspace=Path(os.environ["FDDOS_WORKSPACE"]).resolve();contract_path=contract_path.resolve();output=output.resolve()
    if not contract_path.is_relative_to(workspace) or not output.is_relative_to(workspace) or base.digest(contract_path)!=expected_hash:raise ValueError("Runtime contract/path mismatch")
    contract=json.loads(contract_path.read_text());commit=subprocess.check_output(["git","-C",str(root),"rev-parse","HEAD"],text=True).strip()
    if commit!=contract["code_commit"] or subprocess.check_output(["git","-C",str(root),"status","--porcelain"],text=True).strip():raise ValueError("Require frozen clean code commit")
    for name,sha in contract["source_sha256"].items():
        if base.digest(root/name)!=sha:raise ValueError("Source seal mismatch")
    if base.digest(root/"uv.lock")!=contract["uv_lock_sha256"]:raise ValueError("Lock seal mismatch")
    capture=Path(contract["capture"]["path"]).resolve();labels=Path(contract["labels"]["path"]).resolve();tool=Path(contract["tshark"]["path"]).resolve()
    if any(not p.is_relative_to(workspace) for p in [capture,labels,tool]) or output.exists():raise ValueError("Unsafe runtime path/output")
    before=[base.seal(p) for p in [capture,labels]]
    if any(s["sha256"]!=contract[k]["sha256"] or s["mode"]!="0o444" for k,s in zip(["capture","labels"],before)):raise ValueError("Original hash or0444 mode differs")
    if base.digest(tool)!=contract["tshark"]["sha256"]:raise ValueError("Pinned CLI binary differs")
    output.mkdir(parents=True);phases={};phase=time.monotonic()
    fragments={};complete=[];unsupported=[];decode_counts=Counter();raw_count=0
    for frame in base.pcap_frames(capture):
        raw_count+=1;part=fragment(frame);d=base.decode(frame);decode_counts[d.reason]+=1
        if part:fragments[frame.ordinal]=part
        elif d.packet:complete.append(d.packet)
        elif d.family:unsupported.append((frame.ts,d.family))
    phases["raw_decode_and_lineage"]=time.monotonic()-phase;phase=time.monotonic()
    proposed,tool_record=proposals(tool,capture,output/"isolated-tshark-config")
    if tool_record["all_frame_rows"]!=raw_count:raise ValueError("Tool frame count differs")
    phases["pinned_TShark_reassembly_proposal"]=time.monotonic()-phase;phase=time.monotonic()
    groups,accepted,unresolved,reuse=validate_all(proposed,fragments)
    packets=list(complete)
    for g in accepted:
        first=fragments[g["members"][0]]
        packets.append(base.Packet(g["completion_frame"],g["last_ts"],first.src,g["sport"],first.dst,g["dport"],17,g["ip_bytes"]))
    packets.sort(key=lambda p:(p.ts,p.ordinal))
    for ordinal in unresolved:
        f=fragments[ordinal];unsupported.append((f.ts,f.family))
    policy=json.loads((root/"docs/raw-label-policy-v1.json").read_text());connections,headers=base.read_connections(labels,policy)
    unique,admitted,results,statuses,ambiguity=base.association(packets,connections,unsupported)
    phases["byte_validation_and_original_connection_reconciliation"]=time.monotonic()-phase;phase=time.monotonic()
    profiles=admitted_profiles(connections,results,packets,unique,admitted);by_row={c.row:c for c in connections}
    datagram_labels=Counter();wire_labels=Counter();lineage_output=[]
    for g in accepted:
        row=unique.get(g["completion_frame"]);category=by_row[row].label if row in admitted else "UNRECONCILED"
        datagram_labels[category]+=1;wire_labels[category]+=len(g["members"])
        line=public_group(g,fragments);line.update(source_row=row,source_connection_reconciled=row in admitted,source_label=category);lineage_output.append(line)
    sampling=[]
    for denominator in [1,2,10]:
        full=partial=none=after=0;selected_members=0
        for g in accepted:
            k=sum(base.selected(n,denominator,policy["sampling_seed"]) for n in g["members"]);selected_members+=k
            full+=k==len(g["members"]);partial+=0<k<len(g["members"]);none+=k==0
            after+=base.selected(g["completion_frame"],denominator,policy["sampling_seed"])
        sampling.append({"denominator":denominator,"wire_selected_members":selected_members,"wire_before_reassembly_complete_groups":full,"wire_before_reassembly_partial_groups":partial,"wire_before_reassembly_zero_groups":none,"after_full_reassembly_selected_datagrams":after,"sampled_features_computed":False,"note":"Full-trace lineage is label reference only; no unsampled bytes or ports passed into a feature pipeline"})
    diagnostics=[]
    for active in [1,10,60]:
        for idle in [1,15]:diagnostics.append(base.meter_diagnostic(packets,connections,unique,admitted,policy,active*1000000,idle*1000000,1))
    phases["source_profiles_and_boundary_diagnostics"]=time.monotonic()-phase
    base.write_json(output/"datagram-lineage.json",lineage_output)
    base.write_json(output/"group-status.json",[public_group(g,fragments) for g in groups])
    base.write_json(output/"unresolved-fragment-lineage.json",[public_group({"members":[n],"admitted":False,"reasons":fragments[n].errors or ["unresolved_or_rejected_group"]},fragments) for n in sorted(unresolved)])
    base.write_json(output/"connection-reconciliation.json",list(results.values()))
    base.write_json(output/"admitted-source-profiles.json",profiles)
    base.write_json(output/"datagram-domain-timeout-diagnostics.json",diagnostics)
    base.write_json(output/"sampling-position-diagnostic.json",sampling)
    base.write_json(output/"tool-receipt.json",tool_record)
    after=[base.seal(p) for p in [capture,labels]]
    if before!=after or base.digest(contract_path)!=expected_hash:raise ValueError("Originals/contract changed")
    peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss;peak=peak if sys.platform=="darwin" else peak*1024
    summary={"version":"raw-fragment-admission-v1","status":"completed_development_reconstruction_diagnostic","started_utc":utc,"finished_utc":datetime.now(timezone.utc).isoformat(),
             "elapsed_monotonic_seconds":time.monotonic()-started,"phase_seconds":phases,"peak_wrapper_RSS_bytes":peak,"TShark_child_peak_RSS_bytes":tool_record["TShark_peak_RSS_bytes"], "python":sys.version,"pid":os.getpid(),"workers":1,
             "code_commit":commit,"input_contract_sha256":expected_hash,"source_sha256":contract["source_sha256"],"tool_binary_sha256":contract["tshark"]["sha256"],"originals_before":before,"originals_after":after,"originals_unchanged":True,
             "raw_frame_count":raw_count,"decode_statuses":dict(decode_counts),"fragment_frames":len(fragments),"tool_proposed_groups":len(proposed),"validated_groups":len(accepted),"validated_fragment_members":sum(len(g["members"]) for g in accepted),"unresolved_fragment_frames":len(unresolved),
             "rejected_proposed_groups":sum(not g.get("admitted") for g in groups),"rejection_reasons_nonexclusive":dict(Counter(x for g in groups for x in g.get("reasons",[]))),"ID_reuse":reuse,"UDP_checksum_statuses":dict(Counter(g["udp_checksum"] for g in accepted)),
             "source_domain_packet_or_datagram_candidates":len(packets),"source_association_statuses":dict(statuses),"admitted_source_connections":len(admitted),"reconstructed_datagram_source_labels":dict(datagram_labels),"reconstructed_wire_fragment_source_labels":dict(wire_labels),"admitted_source_profiles":profiles,
             "model_fit_score_calibration_selection":False,"replay_or_live_capture":False,"forwarding_or_lab_change":False,"live_policy_committed":False,"benchmark_or_episode_or_customer_adoption":False,
             "limits":["Tool proposals plus strict local byte/checksum/lineage validation, not proof of unobserved in-flight ID uniqueness or historical analyzer/config identity.","Reassembly is offline label reconciliation. Datagram-domain timeout diagnostics do not define a forwarding-path or live detector operation.","Wire-before-reassembly and after-reassembly sampling differ. No sampled feature was built from full-trace/unsampled data.","Original analyst labels and source zero-counter histories are unchanged; C&C/scan remain outside binary task.","One development scenario; future final captures remain unopened; source/license/member provenance unresolved."]}
    base.write_json(output/"summary.json",summary);base.write_json(output/"COMPLETE.json",{"code_commit":commit,"contract_sha256":expected_hash,"artifacts":{p.name:base.digest(p) for p in output.iterdir() if p.is_file()}})
    print(json.dumps({"status":summary["status"],"validated_datagrams":len(accepted),"unresolved_fragments":len(unresolved),"datagram_labels":dict(datagram_labels),"wire_labels":dict(wire_labels),"elapsed_seconds":summary["elapsed_monotonic_seconds"],"wrapper_RSS_bytes":peak}))


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--contract",type=Path,required=True);p.add_argument("--contract-sha256",required=True);p.add_argument("--output",type=Path,required=True);a=p.parse_args();run(a.contract,a.contract_sha256,a.output)
