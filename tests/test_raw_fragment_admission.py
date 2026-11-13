"""Discriminating fabricated fragment cases, independent of actual traffic."""
from pathlib import Path
from copy import deepcopy
import hashlib
import ipaddress
import json
import os
import struct
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import raw_fragment_admission as m
import raw_label_admission as b
from test_raw_label_admission import write_pcap

A=ipaddress.IPv4Address("192.0.2.1").packed
B=ipaddress.IPv4Address("198.51.100.2").packed


def udp(data=b"abcdefghijklmnopqrstuvwxyz012345",zero=False,bad=False):
    p=struct.pack("!HHHH",1234,80,len(data)+8,0)+data
    check=(~m.internet_sum(A+B+b"\0\x11"+struct.pack("!H",len(p))+p))&65535
    if not check:check=65535
    if zero:check=0
    if bad:check^=1
    return p[:6]+struct.pack("!H",check)+p[8:]


def make_frames(payload=None,ident=7,order=(0,1,2),base_ts=1000000,start=1):
    payload=udp() if payload is None else payload
    pieces=[(0,payload[:16],True),(16,payload[16:32],True),(32,payload[32:],False)]
    frames=[]
    for n,index in enumerate(order,start):
        offset,body,more=pieces[index];bits=offset//8+(0x2000 if more else 0)
        hdr=struct.pack("!BBHHHBBH4s4s",0x45,0,20+len(body),ident,bits,64,17,0,A,B)
        check=(~m.internet_sum(hdr))&65535;hdr=hdr[:10]+struct.pack("!H",check)+hdr[12:]
        data=b"\0"*12+b"\x08\x00"+hdr+body
        frames.append(b.Frame(n,base_ts+n-start,len(data),len(data),data))
    return frames


def parts(frames):return {f.ordinal:m.fragment(f) for f in frames}


def proposal(frames,payload=None):
    payload=udp() if payload is None else payload
    sport,dport,length,check=struct.unpack_from("!HHHH",payload)
    return {"completion_frame":max(f.ordinal for f in frames),"completion_ts":max(f.ts for f in frames),
            "members":[f.ordinal for f in frames],"tool_errors":[],"tool_length":len(payload),"tool_payload":payload,
            "tool_sport":sport,"tool_dport":dport,"tool_udp_length":length,"tool_udp_checksum_status":"3" if check==0 else "1"}


class Checksums(unittest.TestCase):
    def test_RFC1071_vector(self):self.assertEqual((~m.internet_sum(bytes.fromhex("0001f203f4f5f6f7")))&65535,0x220d)
    def test_even_odd_padding(self):self.assertEqual(m.internet_sum(b"a"),m.internet_sum(b"a\0"))
    def test_fold_carries(self):self.assertEqual(m.internet_sum(b"\xff\xff"*200),65535)
    def test_fragment_headers_valid(self):self.assertTrue(all(not f.errors for f in parts(make_frames()).values()))
    def test_udp_valid(self):
        p=udp();self.assertEqual(m.internet_sum(A+B+b"\0\x11"+struct.pack("!H",len(p))+p),65535)


class Structural(unittest.TestCase):
    def check(self,frames,p=None):return m.validate_group(proposal(frames,p),parts(frames))
    def test_complete_exact(self):
        g,reasons=self.check(make_frames());self.assertFalse(reasons);self.assertEqual(g['ip_bytes'],60)
    def test_out_of_order(self):self.assertFalse(self.check(make_frames(order=(2,0,1)))[1])
    def test_reversed_fragment_order(self):self.assertFalse(self.check(make_frames(order=(2,1,0)))[1])
    def test_hole(self):
        f=make_frames(order=(0,2));self.assertIn('hole',self.check(f)[1])
    def test_missing_initial(self):self.assertIn('missing_or_multiple_initial',self.check(make_frames(order=(1,2)))[1])
    def test_missing_final(self):self.assertIn('missing_or_multiple_tail',self.check(make_frames(order=(0,1)))[1])
    def test_duplicate_payload_overlap(self):self.assertIn('overlap_or_duplicate',self.check(make_frames(order=(0,0,1,2)))[1])
    def test_duplicate_member_ordinal(self):
        f=make_frames();p=proposal(f);p['members'].append(1);self.assertIn('duplicate_or_too_few_members',m.validate_group(p,parts(f))[1])
    def test_unknown_member(self):
        f=make_frames();p=proposal(f);p['members'].append(99);self.assertIn('member_not_a_recognized_fragment',m.validate_group(p,parts(f))[1])
    def test_no_members(self):
        f=make_frames();p=proposal(f);p['members']=[];self.assertIsNone(m.validate_group(p,parts(f))[0])
    def test_mixed_ID(self):
        f=make_frames();q=parts(f);q[1].ident=8;self.assertIn('mixed_standard_keys',m.validate_group(proposal(f),q)[1])
    def test_mixed_VLAN(self):
        f=make_frames();q=parts(f);q[1].vlans=((0x8100,3),);self.assertIn('mixed_VLAN_context',m.validate_group(proposal(f),q)[1])
    def test_bad_header_checksum(self):
        f=make_frames();d=bytearray(f[0].data);d[22]^=1;f[0]=b.Frame(1,f[0].ts,len(d),len(d),bytes(d));self.assertIn('bad_ip_checksum',self.check(f)[1])
    def test_truncated(self):
        f=make_frames();a=f[0];f[0]=b.Frame(a.ordinal,a.ts,a.captured-1,a.wire,a.data[:-1]);self.assertIn('truncated_fragment',self.check(f)[1])
    def test_udp_bad_checksum(self):self.assertIn('bad_UDP_checksum',self.check(make_frames(payload=udp(bad=True)),udp(bad=True))[1])
    def test_udp_zero_permitted_not_verified(self):
        p=udp(zero=True);g,why=self.check(make_frames(payload=p),p);self.assertFalse(why);self.assertEqual(g['udp_checksum'],'not_present')
    def test_udp_length_mismatch(self):
        p=udp();p=p[:4]+struct.pack('!H',len(p)+1)+p[6:];self.assertIn('UDP_length_mismatch',self.check(make_frames(payload=p),p)[1])
    def test_tool_bytes_mismatch(self):
        f=make_frames();p=proposal(f);p['tool_payload']=b'x'*40;self.assertIn('tool_reassembled_bytes_or_length_disagreement',m.validate_group(p,parts(f))[1])
    def test_tool_checksum_disagreement(self):
        f=make_frames();p=proposal(f);p['tool_udp_checksum_status']='0';self.assertIn('tool_UDP_checksum_disagreement',m.validate_group(p,parts(f))[1])
    def test_tool_reported_overlap(self):
        f=make_frames();p=proposal(f);p['tool_errors']=['ip.fragment.overlap'];self.assertIn('ip.fragment.overlap',m.validate_group(p,parts(f))[1])
    def test_completion_timestamp_not_first(self):
        f=make_frames();g,why=self.check(f);self.assertEqual(g['last_ts'],1000002);self.assertEqual(g['initial_fragment_ts'],1000000)
    def test_completion_identity_mismatch(self):
        f=make_frames();p=proposal(f);p['completion_ts']-=1;self.assertIn('completion_identity_mismatch',m.validate_group(p,parts(f))[1])
    def test_within_group_timestamp_ties(self):
        f=[b.Frame(x.ordinal,1000000,x.captured,x.wire,x.data) for x in make_frames()];self.assertFalse(self.check(f)[1])
    def test_nonfinal_alignment_rejected(self):
        f=make_frames();q=parts(f);q[1].payload=q[1].payload[:-1];q[1].errors.append('nonfinal_payload_not_8byte_aligned')
        self.assertIn('nonfinal_payload_not_8byte_aligned',m.validate_group(proposal(f),q)[1])
    def test_fragment_TCP_not_silently_UDP(self):
        f=make_frames();q=parts(f);q[1].proto=6;q[1].errors.append('unsupported_fragment_protocol')
        self.assertIn('unsupported_fragment_protocol',m.validate_group(proposal(f),q)[1])
    def test_unsupported_options_remain_counted(self):
        f=make_frames();q=parts(f);q[1].errors.append('unsupported_ipv4_options')
        self.assertIn('unsupported_ipv4_options',m.validate_group(proposal(f),q)[1])
    def test_oversized_group_does_not_overflow_checksum_length(self):
        f=make_frames();q=parts(f);q[1].payload=b'x'*65536
        self.assertIn('UDP_payload_length_overflow',m.validate_group(proposal(f),q)[1])
    def test_mixed_direction_rejected(self):
        f=make_frames();q=parts(f);q[1].src,q[1].dst=q[1].dst,q[1].src
        self.assertIn('mixed_standard_keys',m.validate_group(proposal(f),q)[1])
    def test_lineage_preserves_exact_frame_hash(self):
        f=make_frames();q=parts(f);g,why=self.check(f);o=m.public_group(g,q);self.assertEqual(o['lineage'][0]['frame_sha256'],hashlib.sha256(f[0].data).hexdigest());self.assertNotIn('key',o)


class Reuse(unittest.TestCase):
    def setup_groups(self,second_ts=2000000):
        f=make_frames();q=make_frames(payload=udp(b'Z'*32),base_ts=second_ts,start=4);allparts=parts(f+q);return f,q,allparts
    def test_sequential_reused_ID(self):
        f,q,ps=self.setup_groups();g,a,u,r=m.validate_all([proposal(f),proposal(q,udp(b'Z'*32))],ps);self.assertEqual(len(a),2);self.assertFalse(u)
    def test_reuse_tie_rejected(self):
        f,q,ps=self.setup_groups(1000002);g,a,u,r=m.validate_all([proposal(f),proposal(q,udp(b'Z'*32))],ps);self.assertFalse(a)
    def test_reuse_interleaved_time_rejected(self):
        f,q,ps=self.setup_groups(1000001);g,a,u,r=m.validate_all([proposal(f),proposal(q,udp(b'Z'*32))],ps);self.assertFalse(a)
    def test_orphan_same_key_vetoes_complete_group(self):
        f=make_frames();extra=make_frames(base_ts=2000000,start=4,order=(1,));g,a,u,r=m.validate_all([proposal(f)],parts(f+extra));self.assertFalse(a);self.assertEqual(len(u),4)
    def test_rejected_group_same_key_veto(self):
        f,q,ps=self.setup_groups();p=proposal(q,udp(b'Z'*32));p['tool_errors']=['overlap'];g,a,u,r=m.validate_all([proposal(f),p],ps);self.assertFalse(a)
    def test_shared_membership_veto(self):
        f=make_frames();g,a,u,r=m.validate_all([proposal(f),proposal(f)],parts(f));self.assertFalse(a);self.assertEqual(r['shared_membership_frames'],3)
    def test_no_proposal_preserves_every_orphan(self):
        g,a,u,r=m.validate_all([],parts(make_frames()));self.assertFalse(a);self.assertEqual(u,{1,2,3});self.assertEqual(r['unproposed_fragments'],3)


class PinnedCLI(unittest.TestCase):
    def test_independent_official_CLI_complete_outoforder_reused_and_hole(self):
        exe=os.environ.get('RAW_ADMISSION_TSHARK')
        if not exe:self.skipTest('Official privateCLI not supplied for this environment')
        for name,frames,expected in [('ordered',make_frames(),1),('outoforder',make_frames(order=(2,0,1)),1),('reused',make_frames()+make_frames(payload=udp(b'Z'*32),base_ts=2000000,start=4),2),('hole',make_frames(order=(0,2)),0)]:
            with self.subTest(name=name),tempfile.TemporaryDirectory() as t:
                p=Path(t)/'fixture.pcap';write_pcap(p,frames);rows,receipt=m.proposals(exe,p,Path(t)/'config');g,a,u,r=m.validate_all(rows,parts(frames));self.assertEqual(len(a),expected,(name,rows,g));self.assertEqual(receipt['all_frame_rows'],len(frames))


if __name__=='__main__':unittest.main()
