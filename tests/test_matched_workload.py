"""Paper fidelity and five-arm scientific boundaries, fabricated inputs only."""
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
import copy
import json
import struct
import sys
import tempfile
import unittest
import numpy as np
import torch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import afbkm_adapter as V1
import afbkm_adapter_v2 as A
import afbkm_wire as W1
import afbkm_wire_v2 as W2
import check_afbkm_adapter as C
import check_afbkm_v2 as F
import workload_messages as M
import run_matched_workload as R
from synthetic_workload_fixture import prepared_fixture
from purpose_data_view import RowIdentity


class FidelityTests(unittest.TestCase):
    def test_four_worker_numeric_counterexample_not_only_log_label(self):
        result = F.check()
        self.assertEqual(result["old_centroid"], [0.5])
        self.assertEqual(result["paper_v2_centroid"], [15 / 28])
        self.assertEqual(result["old_singleton_merge_status"], "trust_gate_rejected")
        self.assertEqual(result["paper_v2_singleton_gate_reason"], "finite_candidate_inside_exact_mad_gate")

    def state(self, points):
        scope = C.fake_scope(len(points[0])); batch = C.fake_batch(scope, 0, points)
        return scope, *A.initialize_anchor(batch, A.Parameters(.5, 3, .5, 3), "fidelity", trusted_benign=True)

    def test_skewed_distances_identify_mad_not_standard_deviation(self):
        scope, state, anchor = self.state([[0.], [1.]])
        state = replace(state, mean=A.FrozenArray.of([0.]), internal_threshold=10.)
        summary = A.summarize(C.fake_batch(scope, 1, [[0.], [0.], [0.], [10.]]), state)
        self.assertEqual(summary.accepted, 4); self.assertEqual(summary.dispersion, 0.)
        self.assertEqual(summary.threshold_candidate, 0.)
        self.assertEqual(np.std([0., 0., 0., 10.], ddof=1), 5.)

    def test_non_equidistant_three_row_anchor_has_positive_mad(self):
        scope, state, anchor = self.state([[0.], [1.], [4.]])
        distances = A.score([[0.], [1.], [4.]], state)
        expected, mad = A.mad_rule(distances, 3)
        self.assertGreater(mad, 0); self.assertGreater(state.internal_threshold, np.median(distances))
        self.assertEqual(state.internal_threshold, expected)

    def test_constant_anchor_feature_varies_in_worker_and_changes_distance(self):
        scope, state, anchor = self.state([[0., 5.], [1., 5.]])
        np.testing.assert_array_equal(state.scaler_denominator.array(), [1., 1.])
        np.testing.assert_array_equal(state.inverse_covariance.array(), [[1., 0.], [0., 2.]])
        self.assertEqual(A.score([[0., 6.]], state)[0], 1.5)
        summary = A.summarize(C.fake_batch(scope, 1, [[0., 6.], [1., 4.], [.5, 5.]]), state)
        self.assertEqual((summary.accepted, summary.rejected), (1, 2))
        self.assertEqual(summary.threshold_candidate, 0.)

    def test_two_rows_and_zero_mad_are_permitted_not_security_gates(self):
        scope, state, anchor = self.state([[1.], [1.]])
        self.assertEqual(state.internal_threshold, 0.)
        u = A.summarize(C.fake_batch(scope, 1, [[1.], [1.]]), state)
        # Valid self-reported mean can displace the detector: explicit source limit.
        forged = replace(u, mean=A.FrozenArray.of([1e6]))
        current, audit = A.merge(state, anchor, [forged], [u.permit])
        self.assertGreater(current.mean.array()[0], 1e5)
        self.assertTrue(np.isfinite(current.internal_threshold))

    def test_singleton_wire_version_is_not_silently_mixed(self):
        scope, state, anchor = self.state([[0.], [2.]])
        u = A.summarize(C.fake_batch(scope, 1, [[2.]]), state)
        payload = W2.encode_summary(u, 1)
        self.assertEqual(W2.decode_summary(payload, 1).threshold_candidate, .5)
        self.assertEqual(W2.encode_summary(W2.decode_summary(payload, 1), 1), payload)
        self.assertRaises(ValueError, W1.decode_summary, payload, 1)
        old, old_anchor = V1.initialize_anchor(C.fake_batch(scope, 0, [[0.], [2.]]), state.parameters, "old", trusted_benign=True)
        self.assertRaises(ValueError, W2.encode_initial, old)
        initial = W2.encode_initial(state); decoded = W2.decode_initial(initial)
        self.assertEqual(decoded.state_id, state.state_id)
        v, audit = A.merge(state, anchor, [u], [u.permit]); delta = W2.encode_delta(state, v)
        self.assertEqual(W2.apply_delta(decoded, delta).state_id, v.state_id)
        self.assertRaises(ValueError, W2.apply_delta, v, delta)

    def test_core_scope_is_caller_asserted_runner_requires_sealed_view(self):
        scope=C.fake_scope();altered=replace(scope,sources=tuple((sid,"f"*64) for sid,_ in scope.sources))
        # The numerical core has no file access: hashes are declarations here.
        batch=C.fake_batch(altered,1,[[1.],[1.]])
        self.assertEqual(batch.scope.scope_id,altered.scope_id)
        self.assertNotEqual(altered.scope_id,scope.scope_id)
        self.assertRaisesRegex(ValueError,"sealed_purpose_dataset_required",R.run,object(),R.PilotConfig(),Path("unused"))

    def test_outlier_reason_is_precise_for_active_finite_candidates(self):
        scope, state, anchor = self.state([[0.], [2.]])
        updates = [A.summarize(C.fake_batch(scope, owner, values), state) for owner, values in
                   [(1, [[1.], [1.]]), (2, [[1.]]), (3, [[0.], [0.]])]]
        _, audit = A.merge(state, anchor, updates, [u.permit for u in updates])
        self.assertEqual(audit["finite_candidate_count"], 3)
        self.assertEqual(audit["workers"][1]["gate_reason"], "finite_candidate_inside_exact_mad_gate")
        self.assertEqual(audit["workers"][2]["gate_reason"], "finite_candidate_outside_exact_mad_gate")


class MomentMessageTests(unittest.TestCase):
    def header(self, owner=1, count=3, arm="fedavg"):
        return {"arm":arm,"owner":owner,"count":count,"scope":"a"*64,"schema":"b"*64,
                "role":"train","round":0,"parent":"0"*64,"state":"0"*64}

    def test_hand_computable_merge_population_variance_and_constant_columns(self):
        X = np.zeros((3,73)); X[:,0] = [1.,2.,3.]
        Y = np.zeros((2,73)); Y[:,0] = [5.,9.]
        a=M.fit_moments(X,2);b=M.fit_moments(Y,2);m=M.merge_moments(a,b)
        self.assertEqual(m.count,5);self.assertEqual(m.mean[0],4.)
        self.assertEqual(m.M2[0],40.); self.assertEqual(M.denominator(m)[1],1.)
        self.assertEqual(m.M2[0]/m.count,8.)
        np.testing.assert_allclose(m.mean,np.concatenate([X,Y]).mean(axis=0),rtol=0,atol=1e-15)
        np.testing.assert_allclose(m.M2/5,np.concatenate([X,Y]).var(axis=0),rtol=0,atol=1e-15)
        self.assertRaises(ValueError,m.mean.setflags,write=True)

    def test_large_offset_merge_avoids_raw_second_moment_subtraction(self):
        X=np.full((6,73),1e12);X[:,0]+=[0,1,2,3,4,5]
        m=M.merge_moments(M.fit_moments(X[:3],3),M.fit_moments(X[3:],3))
        self.assertEqual(m.mean[0],1e12+2.5);self.assertEqual(m.M2[0],17.5)
        self.assertEqual(M.merge_moments(M.empty_moments(),m).count,6)
        self.assertRaises(ValueError,M.denominator,M.empty_moments())
        self.assertRaises(ValueError,M.fit_moments,np.full((1,73),np.inf),1)
        self.assertRaises(ValueError,M.standardize,np.full((1,73),1e308),np.zeros(73),np.full(73,1e-300))

    def test_exact_message_reconstruction_size_and_forbidden_fields(self):
        m=M.fit_moments(np.arange(219,dtype=float).reshape(3,73),2)
        payload=M.encode("moments",self.header(),{"mean":m.mean,"M2":m.M2})
        kind,meta,arrays=M.decode(payload)
        self.assertEqual(payload,M.encode(kind,meta,arrays));self.assertFalse(arrays["mean"].flags.writeable)
        n=struct.unpack(">Q",payload[:8])[0]
        self.assertEqual(len(payload),8+n+2*73*8)
        self.assertNotIn(b"label",payload[:8+n])
        for field in ["labels","raw_rows","inverse_covariance"]:
            self.assertRaises(ValueError,M.encode,"moments",self.header(),{"mean":m.mean,"M2":m.M2,field:np.ones(73)})
        bad=self.header();bad["role"]="validation"
        self.assertRaises(ValueError,M.encode,"moments",bad,{"mean":m.mean,"M2":m.M2})
        for damaged in [payload+b"x",payload[:-1],b"\xff"*10,b"x"*(M.MAX_FRAME+1)]:self.assertRaises(ValueError,M.decode,damaged)

    def test_raw_data_message_is_restricted_to_pooled_and_train_owner(self):
        ids=tuple(RowIdentity(1,i,1,0,"a"*64) for i in range(2))
        store=R.Store(1,np.ones((2,73)),ids,np.array([0,1],dtype="u1"))
        arrays=R.raw_arrays(store,0,2)
        self.assertRaises(ValueError,M.encode,"pooled_raw",self.header(count=2),arrays)
        data=M.encode("pooled_raw",self.header(count=2,arm="pooled_central"),arrays)
        _,_,received=M.decode(data);rebuilt=R.received_store(1,[received])
        self.assertEqual(rebuilt.identities,ids);np.testing.assert_array_equal(rebuilt.X,store.X)
        altered=arrays.copy();packed=np.frombuffer(arrays["identities"].tobytes(),dtype=M.IDENTITY_DTYPE).copy();packed["role_id"]=2
        altered["identities"]=np.frombuffer(packed.tobytes(),dtype="u1").reshape(2,-1)
        self.assertRaises(ValueError,M.encode,"pooled_raw",self.header(count=2,arm="pooled_central"),altered)

    def test_clone_and_count_weighted_neural_aggregate(self):
        torch.manual_seed(19);initial=R.snapshot(R.template_model());a=R.clone_model(initial);b=R.clone_model(initial)
        self.assertEqual(M.model_digest(R.snapshot(a)),M.model_digest(R.snapshot(b)))
        first={k:np.full_like(v,2.) for k,v in initial.items()};second={k:np.full_like(v,6.) for k,v in initial.items()}
        merged=R.weighted_models([first,second],[1,3])
        for values in merged.values():np.testing.assert_array_equal(values,np.full_like(values,5.))
        self.assertRaises(ValueError,R.weighted_models,[first],[0])
        meta=self.header(owner=1,count=3);meta["state"]=M.model_digest(initial)
        frame=M.encode("model",meta,initial);_,_,decoded=M.decode(frame)
        self.assertEqual(M.model_digest(decoded),M.model_digest(initial))
        bad=meta.copy();bad["state"]="0"*64
        self.assertRaises(ValueError,M.encode,"model",bad,initial)
        arrays=initial.copy();arrays["0.bias"]=np.full(16,np.nan,dtype="<f4")
        self.assertRaises(ValueError,M.encode,"model",meta,arrays)

    def test_empty_single_class_clients_and_nonfinite_training_failure(self):
        config=R.PilotConfig(batch_rows=3);torch.set_num_threads(2);torch.manual_seed(3)
        initial=R.snapshot(R.template_model());empty=R.Store(2,np.empty((0,73)),(),np.empty(0,dtype="u1"))
        result=R.train(R.clone_model(initial),empty,np.zeros(73),np.ones(73),np.empty(0,dtype=np.int64),config)
        self.assertEqual(result["optimizer_steps"],0);self.assertEqual(result["status"],"empty_worker_untrained")
        ids=tuple(RowIdentity(1,i,2,0,"a"*64) for i in range(5));single=R.Store(2,np.ones((5,73)),ids,np.zeros(5,dtype="u1"))
        result=R.train(R.clone_model(initial),single,np.ones(73),np.ones(73),np.arange(5),config)
        self.assertEqual(result["batch_sizes"],[3,2]);self.assertEqual(result["attack_rows"],0)
        with patch.object(M,"standardize",return_value=np.full((3,73),np.nan,dtype="<f4")):
            self.assertRaises(ValueError,R.train,R.clone_model(initial),single,np.zeros(73),np.ones(73),np.arange(5),config)

    def test_seeded_subset_order_is_filter_of_same_full_owner_permutation(self):
        ids=tuple(RowIdentity(1,i,1,0,"a"*64) for i in range(11));full=R.Store(1,np.zeros((11,73)),ids)
        order=R.order_for(full,20261112);self.assertEqual(set(order),set(range(11)))
        subset_ids=tuple(r for r in ids if r.source_row%3);subset=R.Store(1,np.zeros((len(subset_ids),73)),subset_ids)
        filtered=[ids[i] for i in order if ids[i] in subset_ids]
        actual=[subset_ids[i] for i in R.order_for(subset,20261112,ids)]
        self.assertEqual(filtered,actual);self.assertNotEqual(list(order),list(R.order_for(full,9)))
        self.assertRaises(ValueError,R.order_for,subset,20261112,tuple(replace(r,observer_id=2) for r in ids))


class FiveArmTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.root=Path(cls.temp.name).resolve()
        cls.dataset=prepared_fixture(cls.root/"fixture",small=True)
        cls.config=R.PilotConfig(batch_rows=8)
        cls.result=R.run(cls.dataset,cls.config,cls.root/"complete",synthetic_only=True)

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def test_all_five_arms_full_counts_tails_matched_streams_and_moments(self):
        result=self.result;expected=self.dataset.summary["rows_by_role"]["train"]
        self.assertEqual(set(result["arms"]),{"independent_local","pooled_central","fedavg","statistical_complete","local_shared_moments"})
        neural=[result["arms"][a] for a in ["independent_local","pooled_central","fedavg","local_shared_moments"]]
        self.assertTrue(all(a["total_presentations"]==expected for a in neural))
        self.assertEqual(len({a["total_optimizer_steps"] for a in neural}),1)
        for owner in range(1,11):
            self.assertEqual(len({a["clients"][owner-1]["order_sha256"] for a in neural}),1)
            self.assertTrue(all(sum(a["clients"][owner-1]["batch_sizes"])==a["clients"][owner-1]["training_presentations"] for a in neural))
        self.assertGreater(len({c["training_presentations"] for c in neural[0]["clients"]}),1)
        self.assertTrue(any(0<c["tail_rows"]<8 for c in neural[0]["clients"]))
        self.assertEqual(len({result["arms"][a]["global_moment_id"] for a in ["pooled_central","fedavg","local_shared_moments"]}),1)
        self.assertGreater(len(set(neural[0]["local_moment_ids"].values())),1)
        af=result["arms"]["statistical_complete"]
        self.assertEqual(af["total_presentations_including_anchor_once"],expected)
        self.assertEqual(sum(af["worker_rows_by_owner"].values())+af["anchor_rows"],expected)
        self.assertEqual(sum(sum(s["rows"] for s in r["schedule_statuses"]) for r in af["rounds"]),af["worker_rows"])
        self.assertTrue(any(s["status"]=="exhausted" for r in af["rounds"] for s in r["schedule_statuses"]))
        self.assertFalse(af["external_reporting_calibration_performed"])
        self.assertEqual(af["covariance_updates_after_initialization"],0)

    def test_same_initial_neural_state_and_pooled_continuation_recorded(self):
        for arm in ["independent_local","fedavg","local_shared_moments"]:
            for client in self.result["arms"][arm]["clients"]:
                self.assertEqual(client["client_start_state_id"],self.result["initial_neural_state_id"])
        pooled=self.result["arms"]["pooled_central"]["clients"]
        self.assertEqual(pooled[0]["client_start_state_id"],self.result["initial_neural_state_id"])
        self.assertEqual(pooled[1]["client_start_state_id"],pooled[0]["final_state_id"])

    def test_local_moments_are_own_only_and_fed_local_models_equal_shared_ablation(self):
        for owner in range(1,11):
            batches=list(self.dataset.unlabeled_train(owner).batches(8))
            X=np.concatenate([b.X for b in batches]);moments=M.fit_moments(X,8)
            expected=A.digest([moments.mean.tolist(),moments.M2.tolist()])
            self.assertEqual(expected,self.result["arms"]["independent_local"]["local_moment_ids"][str(owner)])
            self.assertEqual(self.result["arms"]["fedavg"]["clients"][owner-1]["final_state_id"],
                             self.result["arms"]["local_shared_moments"]["clients"][owner-1]["final_state_id"])

    def test_actual_journal_bytes_and_fixed_initial_downlink_are_separate(self):
        rows=[json.loads(l) for l in (self.root/"complete/messages.jsonl").read_text().splitlines()]
        counts={};sizes={}
        for row in rows:
            key=row["arm"]+":"+row["kind"];counts[key]=counts.get(key,0)+1;sizes[key]=sizes.get(key,0)+row["bytes"]
            if row["kind"] in ["af_summary","af_later_state"]:
                self.assertNotIn("inverse_covariance",row["logical_fields"])
            if row["kind"]=="pooled_raw":self.assertEqual(row["arm"],"pooled_central")
        self.assertEqual(sizes,self.result["application_bytes"]);self.assertEqual(counts,self.result["message_counts"])
        self.assertEqual(counts["statistical_complete:af_initial_fixed_state"],10)
        self.assertEqual(counts["fedavg:model_initial"],10);self.assertEqual(counts["fedavg:model_update"],10)
        self.assertEqual(counts["fedavg:model_final"],10)
        self.assertFalse(any(key.startswith("independent_local:") for key in sizes))
        self.assertFalse(any(key.startswith("local_shared_moments:model") for key in sizes))
        self.assertTrue((self.root/"complete/COMPLETE.json").is_file())

    def test_seed_determinism_and_no_heldout_interface_called(self):
        with patch.object(self.dataset,"validation_selection",side_effect=AssertionError("heldout selection")),patch.object(self.dataset,"scoring",side_effect=AssertionError("heldout scoring")):
            again=R.run(self.dataset,self.config,self.root/"repeat",synthetic_only=True)
        for arm,first in self.result["arms"].items():
            self.assertEqual(first.get("final_state_id"),again["arms"][arm].get("final_state_id"))
            if "clients" in first:self.assertEqual([c["final_state_id"] for c in first["clients"]],[c["final_state_id"] for c in again["arms"][arm]["clients"]])
        self.assertEqual(self.result["application_bytes"],again["application_bytes"])
        self.assertTrue(all(p["purpose"] in {"supervised_train","unlabeled_train","anchor_train"} for p in again["source_access_passes"]))

    def test_af_worker_interface_receives_no_labels(self):
        original=A.summarize;seen=[]
        def checked(batch,state):
            self.assertFalse(hasattr(batch,"y"));seen.append(len(batch.refs));return original(batch,state)
        with patch.object(A,"summarize",side_effect=checked):
            R.run(self.dataset,self.config,self.root/"label-guard",synthetic_only=True)
        self.assertGreater(sum(seen),0)
        ids=tuple(RowIdentity(1,i,1,0,"a"*64) for i in range(2));bad=R.Store(1,np.zeros((2,73)),ids,np.zeros(2,dtype="u1"))
        scope=A.TrainingScope("a"*64,"b"*64,tuple("x"+str(i) for i in range(73)),((1,"c"*64),))
        self.assertRaises(ValueError,R.adapt,bad,np.arange(2),scope)

    def test_stale_final_model_round_fails_before_acceptance(self):
        original=R.Ledger.transfer
        def corrupt(ledger,kind,meta,arrays,sender,recipient):
            header,values=original(ledger,kind,meta,arrays,sender,recipient)
            if kind=="model" and meta["owner"]==0 and meta["round"]==1:header={**header,"round":0}
            return header,values
        with patch.object(R.Ledger,"transfer",corrupt):
            with self.assertRaisesRegex(ValueError,"final_model_admission_mismatch"):
                R.run(self.dataset,self.config,self.root/"stale-final",synthetic_only=True)
        self.assertTrue((self.root/"stale-final/FAILED.json").is_file())
        self.assertFalse((self.root/"stale-final/COMPLETE.json").exists())

    def test_missing_or_wrong_scope_message_is_explicit_failed_run(self):
        original=R.Ledger.transfer
        def corrupt(ledger,kind,meta,arrays,sender,recipient):
            header,values=original(ledger,kind,meta,arrays,sender,recipient)
            if kind=="moments":header={**header,"scope":"f"*64}
            return header,values
        with patch.object(R.Ledger,"transfer",corrupt):
            with self.assertRaisesRegex(ValueError,"moment_admission_mismatch"):
                R.run(self.dataset,self.config,self.root/"wrong-scope",synthetic_only=True)
        failed=json.loads((self.root/"wrong-scope/FAILED.json").read_text())
        self.assertEqual(failed["status"],"failed_cost_pilot");self.assertEqual(failed["failed_phase"],"fedavg")
        self.assertFalse((self.root/"wrong-scope/COMPLETE.json").exists())
        self.assertRaises(FileExistsError,R.run,self.dataset,self.config,self.root/"complete",synthetic_only=True)


if __name__=="__main__":unittest.main()
