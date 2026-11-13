"""Fabricated integrity, reference-unit and diagnostic partition fixtures."""
from pathlib import Path
import json,struct,sys,tempfile,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import raw_label_admission as b
import raw_fragment_admission as m
import raw_reference_diagnostics as d
import test_raw_label_admission as old
import test_raw_fragment_admission as fragments

def complete(proto=17,payload=b'abc',tags=0):
    data=bytearray(old.ethernet(proto=proto,payload=payload,vlan=tags));offset=14+4*tags
    transport=offset+20;check_offset=6 if proto==17 else 16
    data[transport+check_offset:transport+check_offset+2]=b'\0\0'
    body=bytes(data[transport:]);pseudo=bytes(data[offset+12:offset+20])+struct.pack('!BBH',0,proto,len(body))
    checksum=(~m.internet_sum(pseudo+body))&65535
    if proto==17 and checksum==0:checksum=65535
    data[transport+check_offset:transport+check_offset+2]=struct.pack('!H',checksum)
    data[offset+10:offset+12]=b'\0\0';checksum=(~m.internet_sum(bytes(data[offset:offset+20])))&65535
    data[offset+10:offset+12]=struct.pack('!H',checksum)
    return b.Frame(1,1000000,len(data),len(data),bytes(data))

class Integrity(unittest.TestCase):
    def inspect(self,frame):return d.inspect_complete(frame,b.decode(frame).packet)
    def test_RFC1071_vector(self):self.assertEqual((~d.checksum_sum(bytes.fromhex('0001f203f4f5f6f7')))&65535,0x220d)
    def test_valid_odd_payload_udp_and_vlan(self):
        statuses,payload=self.inspect(complete(tags=2));self.assertEqual(statuses,{'ipv4_header':'valid','udp':'valid'});self.assertEqual(payload,3)
    def test_valid_tcp(self):self.assertEqual(self.inspect(complete(proto=6))[0],{'ipv4_header':'valid','tcp':'valid'})
    def test_bad_ipv4_does_not_become_a_silent_filter(self):
        frame=complete();data=bytearray(frame.data);data[22]^=1;frame=b.Frame(1,frame.ts,len(data),len(data),bytes(data))
        self.assertIsNotNone(b.decode(frame).packet);self.assertEqual(self.inspect(frame)[0]['ipv4_header'],'bad')
    def test_ipv4_zero_can_be_valid_but_is_never_an_absent_marker(self):
        frame=complete();data=bytearray(frame.data);data[18:20]=b'\0\0';data[24:26]=b'\0\0'
        data[18:20]=struct.pack('!H',(~m.internet_sum(bytes(data[14:34])))&65535)
        self.assertEqual(data[24:26],b'\0\0');frame=b.Frame(1,frame.ts,len(data),len(data),bytes(data))
        self.assertEqual(self.inspect(frame)[0]['ipv4_header'],'valid')
    def test_udp_zero_is_not_present(self):
        frame=complete();data=bytearray(frame.data);data[40:42]=b'\0\0';frame=b.Frame(1,frame.ts,len(data),len(data),bytes(data))
        self.assertEqual(self.inspect(frame)[0]['udp'],'not_present')
    def test_bad_tcp_and_udp_payloads_are_counted(self):
        for proto,name in [(6,'tcp'),(17,'udp')]:
            frame=complete(proto);data=bytearray(frame.data);data[-1]^=1;frame=b.Frame(1,frame.ts,len(data),len(data),bytes(data))
            self.assertEqual(self.inspect(frame)[0][name],'bad')
    def test_affected_admitted_rows_are_reported(self):
        frame=old.frame(old.ethernet(proto=17));packet=b.decode(frame).packet;audit=d.CompleteChecksumAudit();audit.observe(frame,packet)
        c=old.connection();report=audit.report({1:1},{1},{1:c})
        self.assertEqual(report['affected_rows']['ipv4_header:bad']['admitted_source_rows'],1)
        self.assertEqual(report['admission_action'],'AUDIT_ONLY_NO_NEW_CHECKSUM_FILTER')

class PartitionsAndTimers(unittest.TestCase):
    def test_pure_unknown_and_excluded_stay_distinct(self):
        self.assertEqual(b.propagated_label({'unknown'}),'unknown');self.assertEqual(b.propagated_label({'excluded'}),'excluded')
    def test_mixed_binary_with_unknown_keeps_unknown(self):
        self.assertEqual(b.propagated_label({'benign','ddos','unknown'}),'mixed:benign+ddos+unknown')
    def test_invalid_token_is_not_coerced(self):
        with self.assertRaises(ValueError):b.propagated_label({'other'})
    def test_active_first_mask_is_reported(self):
        packets=[old.packet(ts=0),old.packet(2,20000000)];policy=old.POLICY
        for active,idle,masked in [(1,1,True),(1,15,True),(10,15,True),(60,15,False)]:
            result=b.meter_diagnostic(packets,[old.connection()],{},set(),policy,active*1000000,idle*1000000,1)
            self.assertEqual(result['idle_branch_reachable_under_active_first_rule'],not masked)
            self.assertEqual(result['expiration_triggers'],{'active' if masked else 'idle':1,'eof':1})
    def test_source_histogram_retains_a_merged_record(self):
        c1=old.connection();c2=old.connection(row=2,ts=2000000,label='Benign / -',binary='benign')
        result=b.meter_diagnostic([old.packet(),old.packet(2,2000000)],[c1,c2],{1:1,2:2},{1,2},old.POLICY,60000000,15000000,1)
        self.assertEqual(result['cache_records_per_admitted_source_connection_histogram'],{'1':2})
        self.assertEqual(result['source_candidate_rows_per_record_histogram_by_record_label'],{'mixed_binary_label':{'2':1}})
        self.assertEqual(result['new_record_token_sets'],{'benign+ddos':1})

class ReferenceUnits(unittest.TestCase):
    def payload_case(self,expected='32'):
        frames=fragments.make_frames();ps=fragments.parts(frames);_,accepted,_,_=m.validate_all([fragments.proposal(frames)],ps)
        packet=m.datagram_packet(accepted[0],ps)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'conn.log';old.LogParsing().log(path);lines=path.read_text().splitlines()
            fields=next(line.split('\t')[1:] for line in lines if line.startswith('#fields\t'))
            values=lines[-1].split('\t');updates={'ts':'1.000002','proto':'udp','orig_ip_bytes':'60','orig_bytes':expected,'resp_bytes':'0'}
            for key,value in updates.items():values[fields.index(key)]=value
            lines[-1]='\t'.join(values);path.write_text('\n'.join(lines)+'\n')
            connections,_=b.read_connections(path,old.POLICY);unique,admitted,_,_,_=b.association([packet],connections,[])
            self.assertEqual(admitted,{1})
            report=d.udp_payload_comparison(connections,[packet],unique,admitted,{3},{3:32},path)
        return report
    def test_udp_payload_matches_distinct_ip_unit(self):
        report=self.payload_case();self.assertEqual(report['rows'][0]['observed_UDP_payload_bytes'],[32,0]);self.assertEqual(report['status_counts'],{'match':1})
    def test_udp_payload_mismatch_is_visible_not_a_new_hidden_veto(self):
        report=self.payload_case('33');self.assertEqual(report['status_counts'],{'mismatch':1});self.assertEqual(report['admission_action'],'DIAGNOSTIC_ONLY_NO_NEW_LABEL_OR_COUNTER_VETO')
    def test_unset_payload_counter_not_invented_as_zero(self):self.assertEqual(self.payload_case('-')['status_counts'],{'unavailable':1})
    def test_intra_datagram_gap_is_not_hidden_by_completion_only_time(self):
        frames=[b.Frame(f.ordinal,ts,f.captured,f.wire,f.data) for f,ts in zip(fragments.make_frames(),[0,1200000,1300000])]
        ps=fragments.parts(frames);_,accepted,_,_=m.validate_all([fragments.proposal(frames)],ps)
        c=old.connection(ts=1300000);report=d.datagram_wire_timing(accepted,ps,[],{3:1},{1},{1:c})
        self.assertEqual(report['datagram_member_span_us_by_source_label'][c.label]['max'],1300000)
        self.assertEqual(report['wire_profiles_for_source_rows_containing_datagrams'][0]['max_successive_wire_gap_us'],1200000)
        self.assertFalse(report['sampled_features_computed'])

if __name__=='__main__':unittest.main()
