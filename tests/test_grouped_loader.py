"""Scientific-boundary regressions on fabricated CSVs, never real datasets."""
from pathlib import Path
from unittest.mock import patch
import copy, csv, json, sys, tempfile, unittest
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import load_grouped_candidate as L
import prepare_grouped_roles as R

class LoaderTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();(self.root/"config").mkdir()
        self.features=[f"num{i:02}" for i in range(73)]
        self.header=list(L.META[:-1])+["num00"]+list(L.EXCLUDED_IAT)+self.features[1:]+["label"]
        self.expected={};self.proposal={"files":[],"observed_development_label_mapping":{"flnet2023":R.LABELS},"unmapped_development_labels":{"flnet2023":[]}}
        source1=sorted(L.EXPECTED_PATHS).index("datasets/flnet2023/extracted/Normal/Dataset-1.csv")
        for sid,relative in enumerate(sorted(L.EXPECTED_PATHS)):
            client=int(Path(relative).stem.split("-")[1]);label="Normal" if "/Normal/" in relative else {1:"DDoS-bot",5:"DDoS-stomp",9:"DDoS-dyn",10:"DDoS-tcp"}[client]
            rows=[]
            for row_id in range(5+sid%2):
                fields={"src_ip":f"192.0.2.{client}","dst_ip":"198.51.100.1","src_port":str(2000+sid*100+row_id),"dst_port":"443","protocol":"2048","timestamp":"2023-05-13 15:00:00","label":label,**{name:str(-j-1) for j,name in enumerate(L.EXCLUDED_IAT)},**{name:str((sid*10+row_id)*100+k) for k,name in enumerate(self.features)}}
                if relative.endswith("Normal/Dataset-2.csv") and row_id==0:fields.update(src_ip="192.0.2.1",src_port=str(2000+source1*100))
                rows.append([fields[q] for q in self.header]);self.expected[sid,row_id]=(client,label,[float(fields[q]) for q in self.features])
            self.write(relative,rows)
            self.proposal["files"].append({"dataset":"flnet2023","source_role":"development","path":relative,"client_id":client,"sha256":L.sha(self.root/relative)})
        for ds,role,rel in [("flnet2023","reserved_test","datasets/flnet2023/extracted/TEST/poison.csv"),("cicddos2019","reserved_test","datasets/cicddos2019/extracted/03-11/poison.csv"),("cicddos2019","development","datasets/cicddos2019/extracted/01-12/poison.csv")]:
            p=self.root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b"\xff\x00invalid")
            self.proposal["files"].append({"dataset":ds,"source_role":role,"path":rel})
        self.pp=self.root/"config/proposal.json";self.pp.write_text(json.dumps(self.proposal))
        self.pol=self.root/"config/policy.json";self.pol.write_text(json.dumps({"version":R.VERSION,"candidate_id":"synthetic-loader","dataset":"flnet2023","claim_scope":"within_release_grouped_holdout","group_definition":R.GROUP_DEFINITION,"role_seed":"synthetic-loader-only","role_weights":{"train":8,"validation":1,"calibration":1},"minimum_rows_per_client_role":1}))
        self.manifest=R.prepare(self.root,"config/proposal.json","config/policy.json","reports/development-preparation/candidate")
        self.mp=self.root/"reports/development-preparation/candidate/candidate-manifest.json";self.sp=self.mp.with_name("COMPLETE.json")
        self.cp=self.root/"config/contract.json";self.rp=self.root/"config/registry.json"
        self.registry={"fields":[{"name":q} for q in self.header],"historical_csv73_ordered_inputs":self.features.copy()};self.refresh()

    def write(self,relative,rows,header=None):
        p=self.root/relative;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open("w",newline="") as f:w=csv.writer(f);w.writerow(header or self.header);w.writerows(rows)

    def refresh(self):
        self.pp.write_text(json.dumps(self.proposal));self.manifest["proposal_sha256"]=L.sha(self.pp);self.mp.write_text(json.dumps(self.manifest))
        seal=json.loads(self.sp.read_text());seal["artifacts"]["candidate-manifest.json"]=L.sha(self.mp);self.sp.write_text(json.dumps(seal))
        pin={"path":str(self.mp),"sha256":L.sha(self.mp),"proposal_path":str(self.pp),"proposal_sha256":L.sha(self.pp),"policy_path":str(self.pol),"policy_sha256":L.sha(self.pol),"seal_path":str(self.sp),"seal_sha256":L.sha(self.sp),"assignment_sha256":self.manifest["assignment_sha256"],"executed_role_source_sha256":self.manifest["source_code_sha256"],"executed_role_code_commit":self.manifest["code_context"]["commit_context"]}
        self.cp.write_text(json.dumps({"candidate":pin,"input":{"features":self.registry["historical_csv73_ordered_inputs"]}}));self.rp.write_text(json.dumps(self.registry))

    def edit(self,name,value,header=None):
        item=self.proposal["files"][0];p=self.root/item["path"]
        with p.open(newline="") as f:rows=list(csv.reader(f))
        rows[1][self.header.index(name)]=value;self.write(item["path"],rows[1:],header)
        item["sha256"]=L.sha(p)
        for q in self.manifest["sources"]:
            if q["path"]==item["path"]:q["sha256"]=item["sha256"]
        self.refresh()

    def run_loader(self,name="loaded"):
        return L.prepare(self.root,"config/contract.json","config/registry.json","reports/development-preparation/"+name,L.sha(self.cp),L.sha(self.rp),4)

    def failed(self,name="loaded"):
        p=self.root/"reports/development-preparation"/name
        self.assertTrue((p/"FAILED.json").is_file());self.assertFalse((p/"COMPLETE.json").exists())
        self.assertEqual(json.loads((p/"run-state.json").read_text())["status"],"failed_engineering_loader")

    def test_exact_digest_feature_order_source_rows_ownership_and_tail(self):
        result=self.run_loader();self.assertEqual(result["assignment_sha256"],self.manifest["assignment_sha256"])
        self.assertEqual(result["rows"],len(self.expected));self.assertEqual(result["rows_by_role"],self.manifest["rows_by_role"])
        self.assertEqual(result["groups_seen_at_multiple_observers"],self.manifest["groups_seen_at_multiple_observers"]);self.assertGreater(result["groups_seen_at_multiple_observers"],0)
        schema,X,records=L.open_arrays(self.root/"reports/development-preparation/loaded");seen=set()
        for i,r in enumerate(records):
            key=int(r["source_id"]),int(r["source_row"]);seen.add(key);client,label,values=self.expected[key]
            np.testing.assert_array_equal(X[i],values);self.assertEqual(r["observer_id"],client);self.assertEqual(r["original_label_id"],L.LABEL_IDS[label]);self.assertEqual(r["binary_label"],R.LABELS[label]);self.assertEqual(r["stored_timestamp"],b"2023-05-13 15:00:00")
        self.assertEqual(seen,set(self.expected));self.assertEqual(schema["features"],self.features)
        self.assertFalse(X.flags.writeable);self.assertFalse(records.flags.writeable);self.assertFalse(X.dtype.hasobject);self.assertFalse(records.dtype.hasobject);self.assertFalse(result["model_fitted"])

    def test_excluded_sources_never_reach_open(self):
        actual=L.open_source;opened=[]
        def checked(root,item):
            self.assertIn(item["path"],L.EXPECTED_PATHS);opened.append(item["path"]);return actual(root,item)
        with patch.object(L,"open_source",side_effect=checked):result=self.run_loader()
        self.assertEqual(set(opened),L.EXPECTED_PATHS);self.assertEqual(len(result["exclusions"]),3)

    def test_missing_nonfinite_and_invalid_numeric_fields(self):
        for i,(name,value) in enumerate([("num00","NaN"),("num00","inf"),("num00",""),("num00","words"),("flow_iat_min","-inf")]):
            self.edit(name,value)
            with self.assertRaises(ValueError):self.run_loader("bad"+str(i))
            self.failed("bad"+str(i));self.edit(name,"1")

    def test_unknown_original_label(self):
        self.edit("label","Unexpected")
        with self.assertRaisesRegex(ValueError,"Unknown original label"):self.run_loader()
        self.failed()

    def test_missing_metadata_and_invalid_timestamp(self):
        for i,(name,value) in enumerate([("src_ip",""),("timestamp","not-iso")]):
            self.edit(name,value)
            with self.assertRaises(ValueError):self.run_loader("meta"+str(i))
            self.failed("meta"+str(i));self.edit(name,"192.0.2.1" if name=="src_ip" else "2023-05-13 15:00:00")

    def test_reordered_or_duplicate_columns(self):
        for i,header in enumerate([self.header[:6]+["num01"]+self.header[7:],list(reversed(self.header))]):
            self.edit("num00","1",header)
            with self.assertRaisesRegex(ValueError,"stored columns"):self.run_loader("header"+str(i))
            self.failed("header"+str(i))

    def test_reserved_forgery_rejected_before_any_source_open(self):
        self.proposal["files"][0]["path"]="datasets/flnet2023/extracted/TEST/poison.csv";self.refresh()
        with patch.object(L,"open_source",side_effect=AssertionError("source opened")):
            with self.assertRaisesRegex(ValueError,"Unauthorized"):self.run_loader()
        self.failed()

    def test_symlink_escape_rejected_before_open(self):
        p=self.root/self.proposal["files"][0]["path"];target=self.root/"datasets/flnet2023/extracted/TEST/escaped.csv";p.rename(target);p.symlink_to(target)
        with patch.object(L,"open_source",side_effect=AssertionError("source opened")):
            with self.assertRaisesRegex(ValueError,"symlink"):self.run_loader()
        self.failed()

    def test_malformed_unknown_duplicate_missing_inventory_before_open(self):
        before=copy.deepcopy(self.proposal["files"])
        for i,entries in enumerate([before+[None],before+[{"dataset":"other","source_role":"development","path":"x"}],before+[copy.deepcopy(before[0])],before[1:]]):
            self.proposal["files"]=copy.deepcopy(entries);self.refresh()
            with patch.object(L,"open_source",side_effect=AssertionError("source opened")):
                with self.assertRaises(ValueError):self.run_loader("inv"+str(i))
            self.failed("inv"+str(i))

    def test_source_hash_mismatch(self):
        p=self.root/self.proposal["files"][0]["path"];p.write_text(p.read_text()+"changed\n")
        with self.assertRaisesRegex(ValueError,"hash mismatch before"):self.run_loader()
        self.failed()

    def test_assignment_digest_mismatch(self):
        self.manifest["assignment_sha256"]="0"*64;self.refresh()
        with self.assertRaisesRegex(ValueError,"assignment digest differs"):self.run_loader()
        self.failed()

    def test_source_count_mismatch(self):
        self.manifest["sources"][0]["rows"]+=1;self.manifest["rows"]+=1;self.refresh()
        with self.assertRaisesRegex(ValueError,"Per-source row count"):self.run_loader()
        self.failed()

    def test_pinned_contract_and_feature_order(self):
        with self.assertRaisesRegex(ValueError,"Contract or registry"):L.prepare(self.root,"config/contract.json","config/registry.json","reports/development-preparation/pin","0"*64,L.sha(self.rp))
        self.registry["historical_csv73_ordered_inputs"].reverse();self.refresh()
        with self.assertRaisesRegex(ValueError,"Ordered predictor"):self.run_loader()
        self.failed()

    def test_duplicate_json_key(self):
        self.cp.write_text('{"candidate":{},"candidate":{}}')
        with self.assertRaisesRegex(ValueError,"Duplicate JSON"):self.run_loader()
        self.failed()

    def test_overwrite_refusal(self):
        self.run_loader();p=self.root/"reports/development-preparation/loaded/COMPLETE.json";before=p.read_bytes()
        with self.assertRaises(FileExistsError):self.run_loader()
        self.assertEqual(p.read_bytes(),before)

    def test_corrupted_output_rejected(self):
        self.run_loader();out=self.root/"reports/development-preparation/loaded"
        with (out/"features.npy").open("r+b") as f:f.seek(-1,2);v=f.read(1);f.seek(-1,2);f.write(bytes([v[0]^1]))
        with self.assertRaisesRegex(ValueError,"integrity mismatch"):L.open_arrays(out)

    def test_sealed_metadata_symlink_cannot_hash_reserved_target(self):
        source=self.mp.with_name("client-role-label-counts.csv")
        target=self.root/"datasets/flnet2023/extracted/TEST/aggregate.csv"
        source.rename(target);source.symlink_to(target)
        real_sha=L.sha
        def checked(path):
            self.assertNotIn("datasets",Path(path).resolve().parts)
            return real_sha(path)
        with patch.object(L,"sha",side_effect=checked),patch.object(L,"open_source",side_effect=AssertionError("source opened")):
            with self.assertRaisesRegex(ValueError,"sealed artifact symlink"):self.run_loader()
        self.failed()

    def test_source_changed_during_parsing_is_not_completed(self):
        real_digest=L.digest_stream;changed=[]
        def mutating(stream):
            result=real_digest(stream)
            if isinstance(stream.name,int) and not changed:
                p=self.root/self.proposal["files"][0]["path"]
                with p.open(newline="") as f:rows=list(csv.reader(f))
                rows[1][self.header.index("num00")]="99999"
                self.write(self.proposal["files"][0]["path"],rows[1:]);changed.append(True)
            return result
        with patch.object(L,"digest_stream",side_effect=mutating):
            with self.assertRaisesRegex(ValueError,"hash mismatch after"):self.run_loader()
        self.assertTrue(changed);self.failed()

    def test_parent_symlink_swap_after_path_check_cannot_open_target(self):
        item=self.proposal["files"][0];actual=L.source_path;changed=[]
        def swap(root,relative):
            path=actual(root,relative)
            if not changed:
                path.parent.rename(root/"moved-source-directory")
                path.parent.symlink_to(root/"datasets/flnet2023/extracted/TEST",target_is_directory=True)
                (root/"datasets/flnet2023/extracted/TEST"/path.name).write_bytes(b"poison")
                changed.append(True)
            return path
        with patch.object(L,"source_path",side_effect=swap):
            with self.assertRaises(OSError):L.open_source(self.root,item)
        self.assertTrue(changed)

    def test_completion_seal_symlink_rejected_without_reading_target(self):
        self.run_loader();out=self.root/"reports/development-preparation/loaded"
        seal=out/"COMPLETE.json";target=self.root/"datasets/flnet2023/extracted/TEST/hidden.json"
        seal.rename(target);seal.symlink_to(target)
        with self.assertRaisesRegex(ValueError,"Completion seal symlink"):L.open_arrays(out)

    def test_output_and_control_paths(self):
        with self.assertRaises(ValueError):L.prepare(self.root,"config/contract.json","config/registry.json","../escape",L.sha(self.cp),L.sha(self.rp))
        with self.assertRaisesRegex(ValueError,"control JSON"):L.prepare(self.root,"datasets/flnet2023/extracted/TEST/poison.csv","config/registry.json","reports/development-preparation/control",L.sha(self.cp),L.sha(self.rp))

if __name__=="__main__":unittest.main()
