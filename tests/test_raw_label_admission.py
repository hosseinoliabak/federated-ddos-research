"""Fabricated packet/label fixtures; documentation addresses, never real traffic."""

from pathlib import Path
import importlib.util
import ipaddress
import json
import shutil
import struct
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1]/"scripts"
sys.path.insert(0,str(SCRIPTS))
import raw_label_admission as m

POLICY = json.loads((SCRIPTS.parent/"docs/raw-label-policy-v1.json").read_text())
A = ipaddress.IPv4Address("192.0.2.1").packed
B = ipaddress.IPv4Address("198.51.100.2").packed


def ethernet(proto=6, src=A, dst=B, sport=1234, dport=80, payload=b"", ihl=5, vlan=0, frag=0, tcp_offset=5, udp_length=None):
    if proto == 6:
        transport = struct.pack("!HHIIBBHHH",sport,dport,1,0,tcp_offset<<4,2,1000,0,0)+payload
    elif proto == 17:
        transport = struct.pack("!HHHH",sport,dport,len(payload)+8 if udp_length is None else udp_length,0)+payload
    else:
        transport = payload
    ip = struct.pack("!BBHHHBBH4s4s",0x40|ihl,0,ihl*4+len(transport),1,frag,64,proto,0,src,dst)+b"\0"*(max(ihl,5)*4-20)
    prefix = b"\0"*12
    for _ in range(vlan):
        prefix += struct.pack("!HH",0x8100,10)
    return prefix+struct.pack("!H",0x0800)+ip+transport


def frame(data=None, ordinal=1, ts=1_000_000, wire=None):
    data = ethernet() if data is None else data
    return m.Frame(ordinal,ts,len(data),len(data) if wire is None else wire,data)


def packet(ordinal=1,ts=1_000_000,reverse=False,proto=6,ip_bytes=40):
    return m.Packet(ordinal,ts,B if reverse else A,80 if reverse else 1234,A if reverse else B,1234 if reverse else 80,proto,ip_bytes)


def connection(row=1,ts=1_000_000,duration=None,counts=(1,40,0,0),label="Malicious / DDoS",binary="ddos",**kwargs):
    return m.Connection(row,str(row),ts,duration,A,1234,B,80,6,counts,label,binary,kwargs.get("missed",0),kwargs.get("tunnel",False),"S0","S")


def write_pcap(path, frames, order="<", magic=None, snaplen=65535, linktype=1):
    magic = (b"\xd4\xc3\xb2\xa1" if order=="<" else b"\xa1\xb2\xc3\xd4") if magic is None else magic
    data = magic+struct.pack(order+"HHiiII",2,4,0,0,snaplen,linktype)
    for f in frames:
        sec,frac=divmod(f.ts,1_000_000)
        data += struct.pack(order+"IIII",sec,frac,f.captured,f.wire)+f.data
    path.write_bytes(data)


class Times(unittest.TestCase):
    def test_decimal_exact(self): self.assertEqual(m.microseconds("1545403816.870900"),1545403816870900)
    def test_microsecond_difference(self): self.assertEqual(m.microseconds("1.000001")-m.microseconds("1.000000"),1)
    def test_trailing_zero_precision(self): self.assertEqual(m.microseconds("1.0000000"),1_000_000)
    def test_submicrosecond_rejected(self):
        with self.assertRaises(ValueError): m.microseconds("1.0000001")
    def test_nonfinite_rejected(self):
        for text in ["NaN","Infinity","-1","bad"]:
            with self.subTest(text=text),self.assertRaises(ValueError): m.microseconds(text)
    def test_counter_strict(self):
        for text in ["-1","1.0","-"," 2"]:
            with self.subTest(text=text),self.assertRaises(ValueError): m.count(text)


class Headers(unittest.TestCase):
    def test_tcp(self):
        d=m.decode(frame());self.assertEqual(d.reason,"supported");self.assertEqual(d.packet.proto,6);self.assertEqual(d.packet.ip_bytes,40)
    def test_udp(self):
        d=m.decode(frame(ethernet(proto=17,payload=b"abc")));self.assertEqual(d.packet.proto,17);self.assertEqual(d.packet.ip_bytes,31)
    def test_protocol_not_ethertype(self): self.assertNotEqual(m.decode(frame()).packet.proto,0x0800)
    def test_reverse_header(self): self.assertEqual(m.decode(frame(ethernet(src=B,dst=A,sport=80,dport=1234))).packet.src,B)
    def test_vlan(self):
        for n in [1,2,4]:
            with self.subTest(n=n): self.assertEqual(m.decode(frame(ethernet(vlan=n))).packet.vlans,n)
    def test_vlan_limit(self): self.assertEqual(m.decode(frame(ethernet(vlan=5))).reason,"too_many_vlan_tags")
    def test_ipv4_options(self): self.assertEqual(m.decode(frame(ethernet(ihl=6))).packet.ip_bytes,44)
    def test_first_fragment_rejected(self): self.assertEqual(m.decode(frame(ethernet(frag=0x2000))).reason,"ipv4_fragment")
    def test_later_fragment_rejected(self): self.assertEqual(m.decode(frame(ethernet(frag=1))).reason,"ipv4_fragment")
    def test_df_not_fragment(self): self.assertEqual(m.decode(frame(ethernet(frag=0x4000))).reason,"supported")
    def test_reserved_fragment_flag(self): self.assertEqual(m.decode(frame(ethernet(frag=0x8000))).reason,"reserved_ipv4_flag")
    def test_capture_truncation(self):
        f=frame();self.assertEqual(m.decode(frame(f.data,wire=f.wire+1)).reason,"captured_length_truncation")
    def test_ip_truncation(self): self.assertEqual(m.decode(frame(ethernet()[:-1])).reason,"ipv4_length_truncation")
    def test_invalid_ihl(self):
        f=bytearray(ethernet());f[14]=0x44;self.assertEqual(m.decode(frame(bytes(f))).reason,"invalid_ipv4_header")
    def test_invalid_tcp_offset(self): self.assertEqual(m.decode(frame(ethernet(tcp_offset=4))).reason,"invalid_tcp_header")
    def test_invalid_udp_length(self): self.assertEqual(m.decode(frame(ethernet(proto=17,udp_length=7))).reason,"invalid_udp_length")
    def test_unknown_ip_protocol(self): self.assertEqual(m.decode(frame(ethernet(proto=1))).reason,"unsupported_ipv4_protocol_1")
    def test_short_ethernet(self): self.assertEqual(m.decode(frame(b"\0"*10)).reason,"short_ethernet")
    def test_arp_outside_ipv4(self):
        data=b"\0"*12+struct.pack("!H",0x0806)+b"\0"*28;self.assertEqual(m.decode(frame(data)).reason,"unsupported_ethertype_0806")
    def test_ethernet_padding_not_ip_bytes(self): self.assertEqual(m.decode(frame(ethernet()+b"\0"*20)).packet.ip_bytes,40)


class Containers(unittest.TestCase):
    def helper(self,frames,**kwargs):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"a.pcap";write_pcap(p,frames,**kwargs);return list(m.pcap_frames(p))
    def test_little_endian(self): self.assertEqual(self.helper([frame()])[0].ts,1_000_000)
    def test_big_endian(self): self.assertEqual(self.helper([frame()],order=">")[0].data,ethernet())
    def test_timestamp_ties_preserved(self): self.assertEqual([f.ordinal for f in self.helper([frame(),frame(ordinal=2)])],[1,2])
    def test_timestamp_decrease_rejected(self):
        with self.assertRaises(ValueError): self.helper([frame(ts=2),frame(ts=1)])
    def test_nanosecond_policy_rejected(self):
        with self.assertRaises(ValueError): self.helper([],magic=b"\x4d\x3c\xb2\xa1")
    def test_linktype_rejected(self):
        with self.assertRaises(ValueError): self.helper([],linktype=101)
    def test_short_record_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"a.pcap";write_pcap(p,[]);p.write_bytes(p.read_bytes()+b"\0")
            with self.assertRaises(ValueError):list(m.pcap_frames(p))
    def test_short_data_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"a.pcap";write_pcap(p,[frame()]);p.write_bytes(p.read_bytes()[:-1])
            with self.assertRaises(ValueError):list(m.pcap_frames(p))


class Joins(unittest.TestCase):
    def test_unset_single_point(self):
        unique,admitted,rows,_,_=m.association([packet()],[connection()],[])
        self.assertEqual(unique,{1:1});self.assertEqual(admitted,{1})
    def test_unset_single_not_later(self): self.assertFalse(m.association([packet(ts=1_000_001)],[connection()],[])[1])
    def test_unset_multi_not_invented(self):
        c=connection(counts=(2,80,0,0));result=m.association([packet()],[c],[])
        self.assertFalse(result[1]);self.assertIn("unset_multi_packet_duration",result[2][1]["reasons"])
    def test_unset_zero_not_multi_or_absent_packet_proof(self):
        c=connection(counts=(0,0,0,0));result=m.association([packet()],[c],[])
        self.assertFalse(result[1]);self.assertIn("unset_zero_packet_duration",result[2][1]["reasons"])
        self.assertNotIn("unset_multi_packet_duration",result[2][1]["reasons"])
    def test_zero_packet_profile_not_three_to_nine(self):
        c=connection(counts=(0,0,0,0));result=m.association([packet()],[c],[])
        p=m.connection_profiles([c],result[2])[c.label]
        self.assertEqual(p["packet_count_histogram"],{"0":1})
        self.assertEqual(p["unset_zero_packet_counters"],1)
        self.assertEqual(p["unset_multi_packet"],0)
    def test_reverse_first_keeps_log_orientation(self):
        c=connection(counts=(0,0,1,40));self.assertEqual(m.association([packet(reverse=True)],[c],[])[1],{1})
    def test_known_two_direction_interval(self):
        c=connection(duration=1,counts=(1,40,1,40));p=[packet(),packet(2,1_000_001,reverse=True)]
        self.assertEqual(m.association(p,[c],[])[1],{1})
    def test_counter_mismatch_not_eligible(self): self.assertFalse(m.association([packet()],[connection(counts=(2,80,0,0),duration=0)],[])[1])
    def test_ip_bytes_mismatch_not_eligible(self): self.assertFalse(m.association([packet()],[connection(counts=(1,41,0,0))],[])[1])
    def test_start_boundary_exact(self): self.assertFalse(m.association([packet(ts=999999)],[connection(duration=1)],[])[1])
    def test_end_boundary_exact(self): self.assertFalse(m.association([packet(ts=1_000_002)],[connection(duration=1)],[])[1])
    def test_no_nearest_clock_adjustment(self): self.assertFalse(m.association([packet(ts=1_000_001)],[connection()],[])[1])
    def test_reused_tuple_nonoverlap(self):
        c=[connection(),connection(row=2,ts=2_000_000)]
        result=m.association([packet(),packet(2,2_000_000)],c,[])
        self.assertEqual(result[1],{1,2});self.assertEqual(result[0],{1:1,2:2})
    def test_overlapping_same_label_ambiguous(self):
        result=m.association([packet()],[connection(),connection(row=2)],[])
        self.assertFalse(result[1]);self.assertEqual(result[4],{1:"same_label"})
    def test_overlapping_mixed_label_ambiguous(self):
        c=connection(row=2,label="Benign / -",binary="benign")
        self.assertEqual(m.association([packet()],[connection(),c],[])[4],{1:"mixed_label"})
    def test_unknown_multi_competitor_veto(self):
        c=connection(row=2,counts=(2,80,0,0))
        self.assertFalse(m.association([packet()],[connection(),c],[])[1])
    def test_timestamp_ties_not_first_match(self):
        self.assertFalse(m.association([packet(),packet(2)],[connection()],[])[1])
    def test_fragments_veto_family(self):
        self.assertFalse(m.association([packet()],[connection()],[(1_000_000,packet().family)])[1])
    def test_unsupported_other_time_not_veto(self): self.assertEqual(m.association([packet()],[connection()],[(2_000_000,packet().family)])[1],{1})
    def test_missed_bytes_veto(self): self.assertFalse(m.association([packet()],[connection(missed=1)],[])[1])
    def test_tunnel_veto(self): self.assertFalse(m.association([packet()],[connection(tunnel=True)],[])[1])
    def test_trailing_ack_no_interval_extension(self):
        p=[packet(),packet(2,1_000_001,True),packet(3,1_000_002)]
        c=connection(duration=1,counts=(2,80,1,40))
        self.assertFalse(m.association(p,[c],[])[1])


class Propagation(unittest.TestCase):
    def test_same_binary_label(self): self.assertEqual(m.propagated_label({"ddos"}),"ddos")
    def test_mixed_label(self): self.assertEqual(m.propagated_label({"ddos","benign"}),"mixed_binary_label")
    def test_cc_outside_binary(self): self.assertEqual(m.propagated_label({"benign","excluded"}),"unknown_or_excluded")
    def test_unknown_veto(self): self.assertEqual(m.propagated_label({"ddos","unknown"}),"unknown_or_excluded")
    def test_never_drop_unknown_before_meter(self):
        c=[connection()];p=[packet(),packet(2,1_000_001)]
        d=m.meter_diagnostic(p,c,{1:1},{1},POLICY,60_000_000,15_000_000,1)
        self.assertEqual(d["selected_supported_packets"],2);self.assertEqual(d["new_record_labels"],{"unknown_or_excluded":1})
    def test_timeout_reuse_propagates_underlying_connections(self):
        c=[connection(),connection(row=2,ts=2_000_000,label="Benign / -",binary="benign")]
        p=[packet(),packet(2,2_000_000)]
        d=m.meter_diagnostic(p,c,{1:1,2:2},{1,2},POLICY,60_000_000,15_000_000,1)
        self.assertEqual(d["new_record_labels"],{"mixed_binary_label":1})
    def test_active_equality_expires(self):
        c=[connection()];p=[packet(),packet(2,2_000_000)]
        d=m.meter_diagnostic(p,c,{1:1,2:1},{1},POLICY,1_000_000,10_000_000,1)
        self.assertEqual(d["new_records"],2);self.assertEqual(d["expiration_triggers"].get("active"),1)
    def test_idle_equality_expires(self):
        d=m.meter_diagnostic([packet(),packet(2,2_000_000)],[connection()],{1:1,2:1},{1},POLICY,60_000_000,1_000_000,1)
        self.assertEqual(d["expiration_triggers"].get("idle"),1)
    def test_ties_remain_one_flow(self):
        d=m.meter_diagnostic([packet(),packet(2)],[connection()],{1:1,2:1},{1},POLICY,1,1,1)
        self.assertEqual(d["new_records"],1)
    def test_sampling_nested_and_deterministic(self):
        for i in range(1,100):
            if m.selected(i,10,"seed"): self.assertTrue(m.selected(i,2,"seed"))
            self.assertTrue(m.selected(i,1,"seed"));self.assertEqual(m.selected(i,2,"seed"),m.selected(i,2,"seed"))
    def test_diagnostic_reread_not_model(self): self.assertEqual(len(POLICY["diagnostic_grid"]["active_seconds"])*len(POLICY["diagnostic_grid"]["idle_seconds"])*len(POLICY["diagnostic_grid"]["sampling_denominators"]),18)


class IndependentTooling(unittest.TestCase):
    def test_libpcap_and_tcpdump_fabricated_frames(self):
        executable=shutil.which("tcpdump")
        if not executable or not m.ctypes.util.find_library("pcap"):
            self.skipTest("Installed independent packet tooling unavailable")
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"fixture.pcap"
            frames=[frame(),frame(ethernet(src=B,dst=A,sport=80,dport=1234),2,1_000_001),frame(ethernet(proto=17,vlan=1),3,1_000_002)]
            write_pcap(p,frames)
            lib=m.libpcap_control(p);h=m.hashlib.sha256()
            for f in frames:m.raw_identity(f,h)
            self.assertEqual(lib["record_stream_sha256"],h.hexdigest())
            packets=[m.decode(f).packet for f in frames]
            result=m.tcpdump_control(p,packets,executable)
            self.assertEqual(result["all_packet_records"],3);self.assertEqual(result["supported_tuples_compared"],3)
            self.assertEqual(result["tuple_or_timestamp_mismatches"],0)
            self.assertEqual(result["supported_tuples_unparsed"],0)


class LogParsing(unittest.TestCase):
    def log(self,path,duration="-",orig_pkts="1",uid="fixture",extra="",separator=r"\x09"):
        fields="ts uid id.orig_h id.orig_p id.resp_h id.resp_p proto service duration orig_bytes resp_bytes conn_state local_orig local_resp missed_bytes history orig_pkts orig_ip_bytes resp_pkts resp_ip_bytes tunnel_parents label det_label".split()
        types="time string addr port addr port enum string interval count count string bool bool count string count count count count set[string] string string".split()
        values=["1.000000",uid,"192.0.2.1","1234","198.51.100.2","80","tcp","-",duration,"-","-","S0","-","-","0","S",orig_pkts,"40","0","0","-","Malicious","DDoS"]
        data="#separator "+separator+"\n#unset_field\t-\n#fields\t"+"\t".join(fields)+"\n#types\t"+"\t".join(types)+"\n"+"\t".join(values)+"\n"+extra
        path.write_text(data)
        return "\t".join(values)+"\n"
    def test_unset_marker_preserved(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"conn.log";self.log(p)
            rows,headers=m.read_connections(p,POLICY)
            self.assertIsNone(rows[0].duration);self.assertEqual(rows[0].binary,"ddos");self.assertEqual(headers["unset_field"],"-")
    def test_zero_duration_not_unset(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"conn.log";self.log(p,duration="0.000000")
            self.assertEqual(m.read_connections(p,POLICY)[0][0].duration,0)
    def test_invalid_counter_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"conn.log";self.log(p,orig_pkts="-")
            with self.assertRaises(ValueError):m.read_connections(p,POLICY)
    def test_duplicate_uid_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"conn.log";row=self.log(p);self.log(p,extra=row)
            with self.assertRaises(ValueError):m.read_connections(p,POLICY)
    def test_wrong_separator_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"conn.log";self.log(p,separator=r"\x20")
            with self.assertRaises(ValueError):m.read_connections(p,POLICY)
    def test_cc_not_benign(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"conn.log";self.log(p);p.write_text(p.read_text().replace("Malicious\tDDoS","Malicious\tC&C"))
            self.assertIsNone(m.read_connections(p,POLICY)[0][0].binary)
    def test_field_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"conn.log";self.log(p);p.write_text(p.read_text()+"bad\trow\n")
            with self.assertRaises(ValueError):m.read_connections(p,POLICY)


if __name__ == "__main__": unittest.main()
