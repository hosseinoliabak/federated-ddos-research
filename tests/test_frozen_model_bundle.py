"""Fabricated-only bundle/role/serialization/numerical boundary regressions."""
from pathlib import Path
from unittest.mock import patch
import hashlib
import json
import shutil
import sys
import struct
import tempfile
import unittest
import numpy as np
import torch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import frozen_model_bundle as B
import run_matched_workload as R
import workload_messages as M
import afbkm_adapter_v2 as A
import afbkm_wire_v2 as W
from purpose_data_view import PurposeDataset, PurposeView, UnlabeledBatch
from synthetic_workload_fixture import prepared_fixture


def policy(scorer, owner=1, threshold=.5, n=10, rank=9):
    return {'version': B.VERSION, 'scorer_id': scorer.scorer_id, 'input_id': scorer.input_id,
            'role': 'calibration', 'comparison': '>', 'rule': 'benign_order_statistic_strict_ties',
            'calibration_source_sha256': 'a'*64, 'entries': [{'owner':owner,'threshold':threshold,
            'n_benign':n,'rank':rank,'alpha_numerator':1,'alpha_denominator':10,'membership_sha256':'b'*64}]}


class BundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='fabricated-frozen-bundles-')
        cls.root = Path(cls.tmp.name).resolve()
        cls.dataset = prepared_fixture(cls.root/'source',small=True)
        cls.run_dir=cls.root/'cost'; R.run(cls.dataset,R.PilotConfig(cpu_threads=1),cls.run_dir,synthetic_only=True)
        cls.completed=B.CompletedRun(cls.run_dir,hashlib.sha256((cls.run_dir/'COMPLETE.json').read_bytes()).hexdigest())
        cls.schema=B.csv_schema(cls.dataset.features,cls.dataset.summary['input_sha256']['registry'])
        cls.locals={};cls.messages={}
        for owner in R.OWNERS:
            out=cls.root/('local-recovery-'+str(owner));rid=B.recover_train_transforms(cls.dataset,cls.completed,out,owner=owner)
            cls.locals[owner]=(out,rid);cls.messages[owner]=B.local_moment_message(out,rid)
        cls.recovery=cls.root/'recovery';cls.recovery_id=B.merge_train_transforms(cls.completed,cls.messages,cls.recovery)
        cls.bundles={}
        for arm in ['independent_local','pooled_central','fedavg','local_shared_moments','statistical_complete']:
            out=cls.root/('bundle-'+arm);args={} if arm=='statistical_complete' else {'transforms':cls.recovery,'transform_seal':cls.recovery_id}
            if arm=='independent_local':args={'transforms':cls.locals[1][0],'transform_seal':cls.locals[1][1]}
            bid=B.export_bundle(cls.completed,cls.schema,out,arm=arm,
                owner=1 if arm in {'independent_local','local_shared_moments'} else 0,**args)
            cls.bundles[arm]=(out,bid)

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def setUp(self):
        self.case=Path(tempfile.mkdtemp(prefix='case-',dir=self.root))

    def scorer(self,arm='fedavg'):
        return B.load_bundle(*self.bundles[arm])

    def score(self,scorer,X=None,owner=1):
        X=np.zeros((3,73),dtype='<f8') if X is None else X
        return scorer.score(X,feature_names=self.dataset.features,input_id=scorer.input_id,observer_id=owner)

    def copied_bundle(self,arm='fedavg'):
        p=self.case/'bundle';shutil.copytree(self.bundles[arm][0],p);return p

    def reseal(self,p):
        return B.seal(p,[q.name for q in p.iterdir() if q.name!='MANIFEST.json'])

    def mutant_run(self,alter):
        p=self.case/'run';shutil.copytree(self.run_dir,p)
        s=B.loads((p/'summary.json').read_bytes());alter(s);B.put_json(p/'summary.json',s)
        seal=B.loads((p/'COMPLETE.json').read_bytes());data=(p/'summary.json').read_bytes()
        seal['artifacts']['summary.json']={'bytes':len(data),'sha256':B.sha(data)}
        B.put_json(p/'COMPLETE.json',seal)
        return B.CompletedRun(p,B.sha((p/'COMPLETE.json').read_bytes()))

    def test_all_five_self_contained_load_and_scores_without_dataset_or_run(self):
        with (patch.object(B.CompletedRun,'read',side_effect=AssertionError('no run access')),
              patch.object(PurposeDataset,'unlabeled_train',side_effect=AssertionError('no data fitting'))):
            for arm,(p,bid) in self.bundles.items():
                s=B.load_bundle(p,bid);scores=self.score(s)
                self.assertEqual(scores.shape,(3,));self.assertTrue(np.isfinite(scores).all())
                self.assertFalse(scores.flags.writeable)
                self.assertFalse(s.metadata['live_eligible']);self.assertIsNone(s.metadata['customer_map'])

    def test_neural_numpy_reference_and_torch_reload_declared_float_tolerance(self):
        for arm in ['independent_local','pooled_central','fedavg','local_shared_moments']:
            p,bid=self.bundles[arm];s=B.load_bundle(p,bid)
            _,_,w=M.decode((p/'model.bin').read_bytes());t=B.loads((p/'preprocessing.json').read_bytes())
            X=np.tile(np.asarray(t['mean'],dtype='<f8'),(3,1));X[1,0]+=t['denominator'][0];X[2,0]-=t['denominator'][0]
            z=((X-np.asarray(t['mean']))/np.asarray(t['denominator'])).astype('<f4')
            h=np.maximum(z@w['0.weight'].T+w['0.bias'],np.float32(0))
            logit=(h@w['2.weight'].T+w['2.bias']).reshape(-1)
            reference=(1/(1+np.exp(-logit.astype('<f8')))).astype('<f4')
            np.testing.assert_allclose(self.score(s,X),reference,rtol=2e-6,atol=2e-7)
            with torch.random.fork_rng(devices=[]),torch.inference_mode():
                model=R.clone_model(w).eval();expected=torch.sigmoid(model(torch.from_numpy(z)).squeeze(1)).numpy()
            np.testing.assert_array_equal(self.score(s,X),expected)

    def test_manual_three_point_logit_sigmoid_equations(self):
        p=self.copied_bundle();meta=B.loads((p/'scorer.json').read_bytes())
        _,header,w=M.decode((p/'model.bin').read_bytes());w={k:np.zeros_like(v) for k,v in w.items()}
        w['0.weight'][0,0]=1;w['0.bias'][0]=.5;w['2.weight'][0,0]=2;w['2.bias'][0]=-1
        header['state']=M.model_digest(w);(p/'model.bin').write_bytes(M.encode('model',header,w))
        meta['model_id']=header['state'];meta['scorer_id']=B.scorer_identity(meta);B.put_json(p/'scorer.json',meta)
        s=B.load_bundle(p,self.reseal(p));t=B.loads((p/'preprocessing.json').read_bytes())
        X=np.tile(np.asarray(t['mean']), (3,1));X[:,0]+=np.asarray([0.,1.,-2.])*t['denominator'][0]
        expected=np.asarray([.5,1/(1+np.exp(-2)),1/(1+np.exp(1))])
        np.testing.assert_allclose(self.score(s,X),expected,rtol=2e-6,atol=2e-7)

    def test_train_only_transform_recovery_labels_and_heldout_forbidden(self):
        with (patch.object(self.dataset,'_labels',side_effect=AssertionError('labels forbidden')),
              patch.object(self.dataset,'scoring',side_effect=AssertionError('heldout forbidden')),
              patch.object(self.dataset,'validation_selection',side_effect=AssertionError('selection forbidden')),
              patch.object(self.dataset,'trusted_benign_anchor',side_effect=AssertionError('anchor fitting forbidden'))):
            p=self.case/'recovered';bid=B.recover_train_transforms(self.dataset,self.completed,p,owner=1)
        values=B.open_seal(p,bid);t=B.loads(values['transforms.json']);receipt=B.loads(values['receipt.json'])
        original=B.loads((self.locals[1][0]/'transforms.json').read_bytes())
        self.assertEqual(t,original);self.assertEqual(receipt['rows'],original['owners']['1']['count'])
        for v in t['owners'].values():
            self.assertEqual(v['M2'][-1],0);self.assertEqual(v['denominator'][-1],1)
        self.assertTrue(receipt['reconstruction_compute_not_original_training_time'])

    def test_local_recovery_cannot_request_other_owner_predictors(self):
        original=self.dataset.unlabeled_train;requested=[]
        def own_only(owner,**kwargs):
            requested.append(owner)
            if owner!=1:raise AssertionError('other owner raw predictors forbidden')
            return original(owner,**kwargs)
        out=self.case/'own-only'
        with patch.object(self.dataset,'unlabeled_train',own_only):
            rid=B.recover_train_transforms(self.dataset,self.completed,out,owner=1)
        self.assertEqual(requested,[1]);t=B.loads((out/'transforms.json').read_bytes())
        self.assertEqual(set(t['owners']),{'1'});self.assertIsNone(t['union'])
        B.export_bundle(self.completed,self.schema,self.case/'local-bundle',arm='independent_local',owner=1,transforms=out,transform_seal=rid)
        with self.assertRaises(ValueError):B.export_bundle(self.completed,self.schema,self.case/'wrong-shared',arm='fedavg',transforms=out,transform_seal=rid)

    def test_summary_coordinator_has_no_predictor_access_and_rejects_raw_or_wrong_scope(self):
        out=self.case/'summary-merge'
        with patch.object(self.dataset,'unlabeled_train',side_effect=AssertionError('no predictor access')):
            rid=B.merge_train_transforms(self.completed,self.messages,out)
        receipt=B.loads((out/'receipt.json').read_bytes())
        self.assertEqual(receipt['predictor_rows_read'],0)
        self.assertEqual(receipt['summary_application_bytes'],sum(map(len,self.messages.values())))
        self.assertEqual(len(receipt['downlinks']),10)
        self.assertTrue(all(v['numeric_fields']==['mean','denominator'] for v in receipt['downlinks']))
        messages=dict(self.messages);kind,header,arrays=M.decode(messages[2]);header['scope']='f'*64
        messages[2]=M.encode(kind,header,arrays)
        with self.assertRaises(ValueError):B.merge_train_transforms(self.completed,messages,self.case/'bad-merge')
        failed=B.loads((self.case/'bad-merge/FAILED.json').read_bytes())
        self.assertEqual(len(failed['summaries']),1)
        run=self.completed.read();scope=A.TrainingScope(run['candidate_sha256'],run['assignment_sha256'],tuple(run['features']),
            tuple((q['source_id'],q['sha256']) for q in run['native_sources']))
        store=R.stage(self.dataset.supervised_train(1),256,[],'fabricated_raw_boundary')
        messages=dict(self.messages);n=min(256,len(store.X))
        messages[1]=M.encode('pooled_raw',R.meta(scope,'pooled_central',1,n),R.raw_arrays(store,0,n))
        with patch.object(M,'decode',side_effect=AssertionError('raw body decoder forbidden')):
            with self.assertRaisesRegex(ValueError,'forbidden_parameter_frame_kind'):
                B.merge_train_transforms(self.completed,messages,self.case/'raw-forbidden')

    def test_parameter_kind_gate_rejects_raw_before_body_decoder(self):
        raw=A.canonical({'version':M.VERSION,'kind':'pooled_raw','meta':{},'blocks':[]})
        frame=struct.pack('>Q',len(raw))+raw+b'fabricated raw body that must not be decoded'
        with patch.object(M,'decode',side_effect=AssertionError('body decoder forbidden')):
            for kind in ['moments','model']:
                with self.assertRaisesRegex(ValueError,'forbidden_parameter_frame_kind'):
                    B.decode_parameter_frame(frame,kind)

    def test_prepared_array_pins_and_runtime_version_must_match(self):
        run=self.mutant_run(lambda x:x['prepared_array_artifacts']['features.npy'].__setitem__('sha256','f'*64))
        with self.assertRaisesRegex(ValueError,'recovery_scope_mismatch'):
            B.recover_train_transforms(self.dataset,run,self.case/'bad-recovery',owner=1)
        p=self.copied_bundle();provenance=B.loads((p/'provenance.json').read_bytes())
        provenance['bundle_code']['torch']='unsupported-version';B.put_json(p/'provenance.json',provenance)
        with self.assertRaisesRegex(ValueError,'unsupported_inference_runtime'):B.load_bundle(p,self.reseal(p))

    def test_unequal_counts_owner_merge_full_tails_and_identity_accounting(self):
        t=B.loads((self.recovery/'transforms.json').read_bytes());r=B.loads((self.recovery/'receipt.json').read_bytes())
        counts=[B.loads((p/'transforms.json').read_bytes())['owners'][str(owner)]['count'] for owner,(p,_) in self.locals.items()]
        self.assertGreater(len(set(counts)),1);self.assertEqual(sum(counts),t['union']['count'])
        self.assertTrue(any(n%256 for n in counts));self.assertEqual([v['owner'] for v in r['summaries']],list(R.OWNERS))
        for p,_ in self.locals.values():
            local_receipt=B.loads((p/'receipt.json').read_bytes())
            self.assertTrue(all(len(v['identity_order_sha256'])==64 for v in local_receipt['owners']))

    def test_wrong_recorded_moment_count_and_partition_retains_failures(self):
        changes=[lambda x:x['arms']['independent_local']['local_moment_ids'].__setitem__('2','0'*64),
                 lambda x:x['arms']['independent_local']['clients'][1].__setitem__('training_presentations',1),
                 lambda x:x['config'].__setitem__('batch_rows',128)]
        for i,change in enumerate(changes):
            sub=self.case/str(i);sub.mkdir();original=self.case;self.case=sub
            run=self.mutant_run(change);out=sub/'recovery'
            with self.assertRaises(ValueError):B.recover_train_transforms(self.dataset,run,out,owner=2)
            f=B.loads((out/'FAILED.json').read_bytes());self.assertEqual(f['status'],'failed_train_transform_recovery')
            self.assertFalse((out/'MANIFEST.json').exists());self.case=original

    def test_nonfinite_recovery_and_partial_count_failure(self):
        original=PurposeView.batches
        def changed(view,rows):
            for batch in original(view,rows):
                if view.purpose=='unlabeled_train' and view.observer_id==2:
                    yield UnlabeledBatch(np.full(batch.X.shape,np.nan),batch.identities)
                else:yield batch
        out=self.case/'bad-recovery'
        with patch.object(PurposeView,'batches',changed),self.assertRaises(ValueError):
            B.recover_train_transforms(self.dataset,self.completed,out,owner=2)
        f=B.loads((out/'FAILED.json').read_bytes());self.assertEqual(f['rows'],0)
        self.assertGreater(f['attempted_rows'],0);self.assertEqual(len(f['owners']),0)

    def test_schema_owner_dtype_and_nonfinite_predictor_failures(self):
        s=self.scorer('independent_local');X=np.zeros((2,73),dtype='<f8')
        for owner in [0,2,11]:
            with self.assertRaises(ValueError):self.score(s,X,owner)
        for bad in [X[:,:72],X.astype('<f4'),np.full((2,73),np.nan),np.full((2,73),np.inf)]:
            with self.assertRaises(ValueError):self.score(s,bad)
        with self.assertRaises(ValueError):s.score(X,feature_names=tuple(reversed(self.dataset.features)),input_id=s.input_id,observer_id=1)
        with self.assertRaises(ValueError):s.score(X,feature_names=self.dataset.features,input_id='f'*64,observer_id=1)
        with self.assertRaises(TypeError):s.score(X,feature_names=self.dataset.features,input_id=s.input_id,observer_id=1,labels=np.zeros(2))

    def test_unknown_units_live_padding_and_different_schema_rejected(self):
        schema=dict(self.schema);schema['live_eligible']=True
        with self.assertRaises(ValueError):B.validate_schema(schema)
        schema=dict(self.schema);schema['units']=['seconds']*73
        with self.assertRaises(ValueError):B.validate_schema(schema)
        with self.assertRaises(ValueError):B.csv_schema(('duration','packets'), 'f'*64)
        bad=B.csv_schema(tuple(reversed(self.dataset.features)),self.schema['registry_sha256'])
        with self.assertRaises(ValueError):B.export_bundle(self.completed,bad,self.case/'bad',arm='fedavg',transforms=self.recovery,transform_seal=self.recovery_id)

    def test_manifest_hash_symlinks_reserved_paths_and_unknown_files(self):
        p=self.copied_bundle()
        with self.assertRaises(ValueError):B.load_bundle(p,'f'*64)
        (p/'model.bin').write_bytes(b'changed')
        with self.assertRaises(ValueError):B.load_bundle(p,self.bundles['fedavg'][1])
        p2=self.case/'sym';shutil.copytree(self.bundles['fedavg'][0],p2)
        (p2/'model.bin').unlink();(p2/'model.bin').symlink_to(self.bundles['fedavg'][0]/'model.bin')
        with self.assertRaises(ValueError):B.load_bundle(p2,self.bundles['fedavg'][1])
        with patch.object(B.os,'open',side_effect=AssertionError('must reject before open')):
            with self.assertRaisesRegex(ValueError,'source_path_forbidden'):B.load_bundle(self.case/'TEST','a'*64)
        p3=self.case/'extra';shutil.copytree(self.bundles['fedavg'][0],p3);(p3/'extra.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'extra_artifact'):B.load_bundle(p3,self.bundles['fedavg'][1])

    def test_metadata_scope_owner_version_round_and_transform_binding(self):
        mutations=[lambda x:x.__setitem__('model_owner',1),lambda x:x.__setitem__('training_scope_id','f'*64),
                   lambda x:x.__setitem__('version','unknown'),lambda x:x.__setitem__('initial_model_id','a'*64),
                   lambda x:x.__setitem__('training_count',1)]
        for i,change in enumerate(mutations):
            p=self.case/str(i);shutil.copytree(self.bundles['fedavg'][0],p)
            meta=B.loads((p/'scorer.json').read_bytes());change(meta);meta['scorer_id']=B.scorer_identity(meta)
            B.put_json(p/'scorer.json',meta)
            with self.assertRaises(ValueError):B.load_bundle(p,self.reseal(p))
        p=self.copied_bundle();t=B.loads((p/'preprocessing.json').read_bytes());t['mean'][0]+=1;B.put_json(p/'preprocessing.json',t)
        with self.assertRaises(ValueError):B.load_bundle(p,self.reseal(p))

    def test_malformed_weight_frame_shape_round_scope_version_and_nonfinite(self):
        changes=[lambda h:h['blocks'][0].__setitem__('shape',[1,1168]),
                 lambda h:h['meta'].__setitem__('round',0),
                 lambda h:h['meta'].__setitem__('scope','f'*64),
                 lambda h:h.__setitem__('version','unknown')]
        for i,change in enumerate(changes):
            p=self.case/str(i);shutil.copytree(self.bundles['fedavg'][0],p)
            data=(p/'model.bin').read_bytes();n=struct.unpack('>Q',data[:8])[0]
            header=B.loads(data[8:8+n]);change(header);encoded=A.canonical(header)
            (p/'model.bin').write_bytes(struct.pack('>Q',len(encoded))+encoded+data[8+n:])
            with self.assertRaises(ValueError):B.load_bundle(p,self.reseal(p))
        p=self.copied_bundle();data=bytearray((p/'model.bin').read_bytes());n=struct.unpack('>Q',data[:8])[0]
        data[8+n:12+n]=struct.pack('<f',float('nan'));(p/'model.bin').write_bytes(data)
        with self.assertRaises(ValueError):B.load_bundle(p,self.reseal(p))

    def test_shared_and_pooled_transform_bytes_match_and_local_scope_is_distinct(self):
        payloads=[(self.bundles[a][0]/'preprocessing.json').read_bytes() for a in
                  ['pooled_central','fedavg','local_shared_moments']]
        self.assertEqual(len(set(payloads)),1)
        local=B.loads((self.bundles['independent_local'][0]/'preprocessing.json').read_bytes())
        self.assertLess(local['count'],B.loads(payloads[0])['count'])

    def test_empty_transform_nonfinite_values_and_shape_failures(self):
        for transform in [B.transform_payload(M.empty_moments()),
                          {'count':1,'mean':[0.],'M2':[0.],'denominator':[1.],'moment_id':'a'*64}]:
            with self.assertRaises(ValueError):B.validate_transform(transform)
        t=B.loads((self.bundles['fedavg'][0]/'preprocessing.json').read_bytes());t['denominator'][0]=0
        with self.assertRaises(ValueError):B.validate_transform(t)

    def test_af_final_round_preserved_and_initial_decoder_is_not_a_final_decoder(self):
        p,bid=self.bundles['statistical_complete'];s=B.load_bundle(p,bid);m=s.metadata
        raw=(p/'af-state.json').read_bytes();obj=B.loads(raw)
        state=B.decode_final_af(raw,expected_state_id=m['model_id'],expected_fixed_id=m['fixed_id'],expected_round=m['final_round'])
        self.assertGreater(state.round_id,0)
        with self.assertRaises(ValueError):B.decode_final_af(raw,expected_state_id=m['model_id'],expected_fixed_id=m['fixed_id'],expected_round=0)
        initial=W.pack('initial_state',{'state':obj,'state_id':m['model_id']})
        with self.assertRaises(ValueError):W.decode_initial(initial)
        X=np.zeros((2,73),dtype='<f8');np.testing.assert_array_equal(self.score(s,X),A.score(X,state))
        obj['inverse_covariance'][0][0]=-1
        with self.assertRaises(ValueError):B.decode_final_af(A.canonical(obj),expected_state_id=m['model_id'],expected_fixed_id=m['fixed_id'],expected_round=m['final_round'])

    def test_overflow_does_not_become_benign(self):
        for arm in ['fedavg','statistical_complete']:
            with self.assertRaises(ValueError):self.score(self.scorer(arm),np.full((2,73),1e308,dtype='<f8'))

    def test_score_view_no_labels_wrong_roles_and_partial_failure_receipt(self):
        s=self.scorer();view=self.dataset.scoring('validation',1,declaration_id='synthetic',frozen_scorer_id=s.scorer_id)
        with patch.object(self.dataset,'_labels',side_effect=AssertionError('labels forbidden')):
            stream=s.score_view(view,batch_rows=2);output=list(stream)
        self.assertEqual(stream.receipt['status'],'complete_scoring');self.assertTrue(output)
        self.assertEqual(sum(len(q[1]) for q in output),stream.receipt['completed_rows'])
        for bad in [self.dataset.unlabeled_train(1),self.dataset.validation_selection(1,declaration_id='fixture')]:
            with self.assertRaises(ValueError):s.score_view(bad)
        wrong=self.dataset.scoring('calibration',1,declaration_id='bad',frozen_scorer_id='f'*64)
        with self.assertRaises(ValueError):s.score_view(wrong)
        original=PurposeView.batches
        def fail_after_first(v,n):
            for i,batch in enumerate(original(v,n)):
                if i:raise ValueError('fabricated_second_batch_failure')
                yield batch
        with patch.object(PurposeView,'batches',fail_after_first):
            stream=s.score_view(view,batch_rows=1);it=iter(stream);next(it)
            with self.assertRaisesRegex(ValueError,'fabricated_second_batch_failure'):next(it)
        self.assertEqual(stream.receipt['status'],'failed_or_incomplete_scoring')
        self.assertEqual(stream.receipt['completed_rows'],1)

    def test_strict_threshold_ties_endpoints_absent_support_and_scorer_binding(self):
        s=self.scorer();p=self.case/'decision';p.mkdir();obj=policy(s)
        bid=B.export_decision_policy(p/'reporting-thresholds.json',obj)
        scores=np.asarray([0.,.5,1.],dtype='<f4')
        np.testing.assert_array_equal(B.decide(s,scores,owner=1,policy_directory=p,expected_policy_sha256=bid),[False,False,True])
        with self.assertRaisesRegex(ValueError,'no_threshold_for_owner'):B.decide(s,scores,owner=2,policy_directory=p,expected_policy_sha256=bid)
        with self.assertRaises(ValueError):B.decide(self.scorer('independent_local'),scores,owner=1,policy_directory=p,expected_policy_sha256=bid)
        for value in [0.,1.]:
            obj=policy(s,threshold=value);B.validate_decision_policy(obj)
        for change in [lambda x:x.__setitem__('role','validation'),lambda x:x.__setitem__('comparison','>='),
                       lambda x:x['entries'][0].__setitem__('n_benign',0),lambda x:x['entries'][0].__setitem__('rank',1),
                       lambda x:x['entries'][0].__setitem__('threshold',float('nan'))]:
            obj=policy(s);change(obj)
            with self.assertRaises(ValueError):B.validate_decision_policy(obj)
        with self.assertRaises(ValueError):B.decide(s,np.asarray([np.nan]),owner=1,policy_directory=p,expected_policy_sha256=bid)

    def test_inference_and_public_metadata_are_immutable_and_rng_is_restored(self):
        s=self.scorer();before=(s._metadata,s._schema,s._payload,s._transform)
        rng=torch.random.get_rng_state().clone();first=self.score(s);second=self.score(s)
        self.assertTrue(torch.equal(rng,torch.random.get_rng_state()))
        self.assertEqual(before,(s._metadata,s._schema,s._payload,s._transform));np.testing.assert_array_equal(first,second)
        with self.assertRaises(ValueError):first[0]=0
        meta=s.metadata;meta['recipients']=[];self.assertNotEqual(meta,s.metadata)


if __name__=='__main__':unittest.main()
