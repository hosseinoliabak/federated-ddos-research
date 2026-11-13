"""Fabricated regressions for finite development isolation and continuous state."""
from pathlib import Path
from dataclasses import replace
from unittest.mock import patch
import copy
import json
import sys
import tempfile
import unittest
import numpy as np
import torch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import finite_development as F
import run_finite_development as S
import afbkm_adapter_v2 as A
import frozen_model_bundle as B
import run_matched_workload as R
import workload_messages as M
import train_separability_diagnostic as D
from purpose_data_view import immutable, PurposeDataset, PurposeView
from synthetic_workload_fixture import prepared_fixture


class ContractTests(unittest.TestCase):
    def test_frozen_reference_grid_and_caps(self):
        plan=S.stage_plan('fixed16-grid');plan.validate()
        self.assertEqual(len(S.slots(plan)),36)
        self.assertEqual([g.name for g in plan.grid],['SGD']*3+['Adam']*3)
        self.assertEqual(len(S.slots(S.stage_plan('wider-capacity'))),6)
        self.assertEqual(len(S.slots(S.stage_plan('shared-moment-ablation'))),2)
        for wrong in [replace(plan,seeds=(1,)),replace(plan,hidden=(64,128,64)),replace(plan,checkpoints=(1,2))]:
            self.assertRaises(ValueError,wrong.validate)

    def test_invalid_architectures_and_optimizer_specs(self):
        for hidden in [(17,),[16],(64,)]:self.assertRaises(ValueError,F.template,hidden)
        for spec in [F.OptimizerSpec('Adam',float('nan')),F.OptimizerSpec('Adam',1),F.OptimizerSpec('AdamW',.1)]:
            self.assertRaises(ValueError,spec.validate)

    def test_optimizer_tree_does_not_alias_checkpoint(self):
        with torch.random.fork_rng(devices=[]):torch.manual_seed(2);model=F.template()
        opt=F.OptimizerSpec('Adam',.001).make(model)
        opt.zero_grad();model(torch.ones((2,73))).sum().backward();opt.step()
        packed=F.pack_tree(opt.state_dict());before=A.canonical(packed)
        opt.zero_grad();model(torch.ones((2,73))).sum().backward();opt.step()
        self.assertEqual(A.canonical(packed),before)
        clone=F.clone(F.snapshot(model),(16,));other=F.OptimizerSpec('Adam',.001).make(clone)
        other.load_state_dict(F.unpack_tree(packed))
        self.assertEqual(A.canonical(F.pack_tree(other.state_dict())),before)

    def test_general_model_frame_exact_roundtrip_and_raw_refusal(self):
        meta={'scope':'a'*64,'trial':1,'owner':2,'round':1,'count':20,'parent':'b'*64}
        for hidden in F.ARCHITECTURES:
            state=F.snapshot(F.template(hidden));frame=F.model_frame(state,hidden,meta)
            clone=F.decode_model(frame,hidden,meta)
            self.assertEqual(F.state_id(clone),F.state_id(state))
            self.assertFalse(next(iter(clone.values())).flags.writeable)
            bad=B.loads(frame);bad['kind']='pooled_raw'
            with patch.object(F,'unpacked_array',side_effect=AssertionError('must reject before array decode')):
                self.assertRaisesRegex(ValueError,'model_frame_binding',F.decode_model,A.canonical(bad),hidden,meta)
        self.assertRaises(ValueError,F.decode_model,frame,hidden,meta|{'scope':'c'*64})

    def test_rss_units_are_platform_explicit(self):
        self.assertEqual(F.peak_rss_bytes(1234,'darwin'),1234)
        self.assertEqual(F.peak_rss_bytes(1234,'linux'),1263616)
        self.assertRaises(ValueError,F.peak_rss_bytes,1234,'unknown')

    def test_constant_and_majority_tie_metrics_remain_valid(self):
        y=np.asarray([0,0,1,1],dtype='u1')
        for value in (0.,.5,1.):
            q=F.rank_metrics(y,np.full(4,value));self.assertEqual(q['rank_status'],'complete')
            self.assertEqual(q['auroc'],.5);self.assertEqual(q['average_precision'],.5);self.assertTrue(q['constant_scores'])
        q=F.rank_metrics(np.array([0,0,1,1,1,1]),np.array([.1,.1,1.,1.,1.,1.]))
        self.assertTrue(q['majority_tie']);self.assertEqual(q['auroc'],1.)
        self.assertEqual(F.rank_metrics(np.zeros(4),np.ones(4))['rank_status'],'NA_class_support')

    def record(self,owner,seed,grid=0,checkpoint=1,loss=.5):
        return {'owner':owner,'seed':seed,'grid':grid,'checkpoint':checkpoint,'loss_sum':loss*4,'loss_count':4,
                'missing_scores':0,'status':'complete_validation','trial_complete':True}

    def test_local_selector_rejects_other_owner_feedback(self):
        self.assertRaisesRegex(ValueError,'selection_owner_isolation',F.choose,[self.record(1,1),self.record(2,2)],(1,2),1,(1,),owner=1)

    def test_missing_or_duplicate_seed_is_never_eligible(self):
        for rows in [[self.record(1,1)],[self.record(1,1),self.record(1,1)]]:
            self.assertEqual(F.choose(rows,(1,2),1,(1,),owner=1)['status'],'no_eligible_candidate')

    def test_incomplete_trial_cannot_select_early_checkpoint(self):
        records=[self.record(1,1),self.record(1,2)];records[1]['trial_complete']=False
        self.assertIsNone(F.choose(records,(1,2),1,(1,),owner=1)['selection'])

    def test_selection_tie_prefers_shorter_checkpoint_then_grid(self):
        records=[self.record(1,s,g,c) for s in (1,2) for g in (0,1) for c in (1,2)]
        q=F.choose(records,(1,2),2,(1,2),owner=1)
        self.assertEqual((q['selection']['grid'],q['selection']['checkpoint']),(0,1))

    def test_validation_loss_summary_binding_and_no_extra_labels(self):
        r={'owner':1,'expected_rows':3,'loss_count':3,'loss_sum':2.,'status':'complete_validation','missing_scores':0,
           'scorer_id':'a'*64,'identity_sha256':'b'*64}
        args={'scope':'c'*64,'seed':1,'grid':0,'checkpoint':1,'arm':'fedavg'}
        data=F.loss_message(r,**args);expected=args|{'owner':1,'expected_rows':3}
        q=F.admit_loss_message(data,**expected);self.assertEqual(q['count'],3)
        q['y']=[0,1,0];self.assertRaises(ValueError,F.admit_loss_message,A.canonical(q),**expected)
        self.assertRaises(ValueError,F.admit_loss_message,data,**(expected|{'owner':2}))
        self.assertRaises(ValueError,F.loss_message,r|{'missing_scores':1},**args)

    def test_budget_categories_are_separate_and_charged_before_failure(self):
        b=F.Budget(20,10,raw_bytes=15);b.charge_message(15,raw=True);b.charge_message(10)
        with self.assertRaisesRegex(F.BudgetExceeded,'parameter_summary_bytes'):b.charge_message(1)
        self.assertEqual((b.raw_bytes,b.parameter_bytes),(15,11))

    def test_nonfinite_partial_archive_preserves_bytes_but_cannot_score(self):
        model=F.template()
        with torch.no_grad():next(model.parameters()).view(-1)[0]=float('nan')
        with tempfile.TemporaryDirectory(prefix='fabricated-nonfinite-archive-') as tmp:
            p=Path(tmp)/'partial.json'
            S.checkpoint(p,{1:model},{},{1:(np.zeros(73),np.ones(73))},(16,),{'partial':True})
            q=json.loads(p.read_text());self.assertEqual(q['nonfinite_model_values']['1'],1)
            self.assertTrue(q['partial_archive_ineligible_for_scoring'])
            self.assertRaises(ValueError,F.unpacked_array,q['models']['1']['0.weight'])

    def test_terminal_seal_bytes_are_checked_before_success_publication(self):
        with tempfile.TemporaryDirectory(prefix='fabricated-seal-budget-') as tmp:
            root=Path(tmp).resolve();(root/'artifact.txt').write_text('fabricated')
            budget=F.Budget(20,1000,storage_bytes=20)
            self.assertRaises(F.BudgetExceeded,S.seal,root,'fabricated_complete',budget)
            self.assertFalse((root/'COMPLETE.json').exists());self.assertTrue((root/'PENDING-COMPLETE.json').exists())


class SyntheticTrialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(prefix='fabricated-finite-tests-');cls.root=Path(cls.tmp.name).resolve()
        cls.ds=prepared_fixture(cls.root/'source',small=True)
        cls.plan=S.Plan(stage='fabricated',seeds=(11,12),grid=(F.OptimizerSpec('Adam',.001),),checkpoints=(1,2),max_seconds=120)
        cls.result=S.run_neural(cls.ds,cls.plan,cls.root/'neural',synthetic_only=True)
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def read(self,name):return json.loads((self.root/'neural'/name).read_text())

    def test_complete_neural_matrix_and_exact_tail_presentations(self):
        r=self.result;n=self.ds.summary['rows_by_role']['train'];v=self.ds.summary['rows_by_role']['validation']
        self.assertEqual(r['status'],'complete_finite_neural_stage');self.assertEqual(len(r['trials']),6)
        self.assertEqual(r['validation_valid_scores'],12*v);self.assertEqual(r['validation_missing_scores'],0)
        for q in r['trials']:
            self.assertEqual(q['train_rows'],2*n);self.assertEqual(q['completed_presentations'],2)
            for p in q['passes']:
                if 'rows' in p:self.assertEqual(sum(p['batch_sizes']),p['rows'])
        self.assertTrue((self.root/'neural/COMPLETE.json').exists())

    def test_local_adam_step_survives_second_presentation(self):
        path=next(q for q in (self.root/'neural').glob('trial-*') if json.loads((q/'TRIAL.json').read_text())['arm']=='independent_local')
        first=json.loads((path/'checkpoint-1.json').read_text());second=json.loads((path/'checkpoint-2.json').read_text())
        for owner in range(1,11):
            a=F.unpack_tree(first['optimizer_state'][str(owner)]);b=F.unpack_tree(second['optimizer_state'][str(owner)])
            for key in a['state']:self.assertEqual(float(b['state'][key]['step']),2*float(a['state'][key]['step']))

    def test_pooled_adam_retains_state_across_owner_blocks(self):
        q=next(q for q in self.result['trials'] if q['arm']=='pooled_central')
        path=self.root/'neural'/f"trial-{q['trial']:03}"/'checkpoint-2.json'
        ck=json.loads(path.read_text());state=F.unpack_tree(ck['optimizer_state']['0'])
        self.assertTrue(all(int(s['step'])==q['optimizer_steps'] for s in state['state'].values()))

    def test_archived_model_optimizer_exactly_continue_to_next_checkpoint(self):
        trial=next(q for q in self.result['trials'] if q['arm']=='independent_local')
        path=self.root/'neural'/f"trial-{trial['trial']:03}"
        first=json.loads((path/'checkpoint-1.json').read_text());second=json.loads((path/'checkpoint-2.json').read_text())
        arrays={k:F.unpacked_array(first['models']['1'][k]) for k in F.shapes((16,))}
        model=F.clone(arrays,(16,));opt=F.OptimizerSpec('Adam',.001).make(model)
        opt.load_state_dict(F.unpack_tree(first['optimizer_state']['1']))
        transform=tuple(F.unpacked_array(first['transforms']['1'][k]) for k in ('mean','denominator'))
        store=R.stage(self.ds.supervised_train(1),256,[],'fabricated')
        S.train_pass(model,opt,store,transform,R.order_for(store,trial['seed']),256,F.Budget(20,1000),{})
        self.assertEqual(F.state_id(F.snapshot(model)),second['model_ids']['1'])

    def test_new_one_round_sgd_matches_original_frozen_engineering_update(self):
        plan=replace(self.plan,seeds=(77,),grid=(F.OptimizerSpec('SGD',.01),),checkpoints=(1,),arms=('fedavg',))
        r=S.run_neural(self.ds,plan,self.root/'one-sgd',synthetic_only=True)
        old=self.root/'old-sgd';old.mkdir();ledger=R.Ledger(old)
        with torch.random.fork_rng(devices=[]):torch.manual_seed(77);initial=R.snapshot(R.template_model())
        result=R.neural_arm(self.ds,D.training_scope(self.ds),'fedavg',initial,R.PilotConfig(seed=77),[],ledger,old,{})
        ck=json.loads((self.root/'one-sgd/trial-000/checkpoint-1.json').read_text())
        self.assertEqual(ck['model_ids']['0'],result['final_state_id'])

    def test_wider_new_codec_and_trial_have_complete_validation(self):
        plan=replace(self.plan,seeds=(81,),hidden=(64,128,64),grid=(F.OptimizerSpec('SGD',.01),),checkpoints=(1,),arms=('independent_local',))
        r=S.run_neural(self.ds,plan,self.root/'wide',synthetic_only=True)
        self.assertEqual(r['status'],'complete_finite_neural_stage')
        self.assertEqual(r['trials'][0]['validation_valid_scores'],self.ds.summary['rows_by_role']['validation'])
        data=(self.root/'wide/trial-000/scorer-1-owner1.json').read_bytes()
        self.assertEqual(F.FrozenNeural(data,B.sha(data)).validate()[0]['hidden'],[64,128,64])

    def test_federated_rounds_have_full_participation_and_reset_adam(self):
        q=next(q for q in self.result['trials'] if q['arm']=='fedavg')
        rounds=[p for p in q['passes'] if 'participants' in p]
        self.assertEqual(len(rounds),2)
        self.assertTrue(all(r['participants']==list(range(1,11)) for r in rounds))
        ck=json.loads((self.root/'neural'/f"trial-{q['trial']:03}"/'checkpoint-2.json').read_text())
        self.assertEqual(ck['optimizer_state'],{})
        self.assertEqual(q['optimizer_state_policy'],'reset_client_each_round_no_server_optimizer')

    def test_local_selection_is_ten_distinct_own_records(self):
        qs=self.result['selections']['independent_local']
        self.assertEqual([q['owner'] for q in qs],list(range(1,11)))
        self.assertTrue(all(q['status']=='selected' for q in qs))
        self.assertEqual(self.result['selections']['fedavg']['owner'],0)

    def test_same_initial_weights_and_order_across_arms(self):
        for seed in self.plan.seeds:
            rs=[q for q in self.result['trials'] if q['seed']==seed]
            self.assertEqual(len({q['initial_id'] for q in rs}),1)
            for owner in range(1,11):
                ids={p['order_sha256'] for q in rs for p in q['passes'] if p.get('owner')==owner}
                self.assertEqual(len(ids),1)

    def test_moment_coordinator_rejects_raw_frame_before_array_decode(self):
        scope=D.training_scope(self.ds);access=[];store=R.stage(self.ds.supervised_train(1),256,access,'fabricated')
        raw=M.encode('pooled_raw',R.meta(scope,'pooled_central',1,len(store.X)),R.raw_arrays(store,0,len(store.X)))
        with patch.object(M,'decode',side_effect=AssertionError('raw body must not decode')):
            self.assertRaises(ValueError,S.merge_moment_messages,{o:raw for o in R.OWNERS},scope,'fedavg',{o:len(store.X) for o in R.OWNERS})

    def test_preparation_rejects_validation_view_before_read(self):
        view=self.ds.validation_selection(1,declaration_id='fabricated-wrong-role')
        with patch.object(PurposeView,'batches',side_effect=AssertionError('wrong role read')):
            self.assertRaisesRegex(ValueError,'training_view_required',S.stage_view,view,256,[],'bad',F.Budget(20,100),{})

    def scorer(self):
        q=next(q for q in self.result['trials'] if q['arm']=='independent_local')
        p=self.root/'neural'/f"trial-{q['trial']:03}"/'scorer-1-owner1.json';data=p.read_bytes()
        return F.FrozenNeural(data,B.sha(data))

    def test_immutable_predictor_only_neural_and_schema(self):
        scorer=self.scorer();q=scorer.validate()[0];X=np.zeros((2,73),dtype='<f8')
        args={'feature_names':self.ds.features,'input_id':q['input_id'],'observer_id':1}
        scores,z=scorer.predict(X,**args);self.assertFalse(scores.flags.writeable);self.assertFalse(z.flags.writeable)
        self.assertRaises(TypeError,scorer.predict,X,**args,y=np.zeros(2))
        self.assertRaises(ValueError,scorer.predict,X,**(args|{'observer_id':2}))
        before=torch.get_rng_state().clone();scorer.predict(X,**args);self.assertTrue(torch.equal(before,torch.get_rng_state()))
        bad=B.loads(scorer.data);bad['schema']['live_eligible']=True;data=A.canonical(bad)
        self.assertRaises(ValueError,F.FrozenNeural,data,B.sha(data))

    def test_scorer_delivery_rejects_endpoint_and_corrupted_payload(self):
        scorer=self.scorer();q=scorer.validate()[0]
        meta={'scope':q['scope'],'trial':1,'seed':1,'grid':0,'checkpoint':1,'arm':'fedavg','recipient':1}
        data=F.scorer_delivery(scorer,meta);received=F.receive_scorer(data,meta)
        self.assertEqual(received.data,scorer.data);self.assertIsNot(received,scorer)
        with patch.object(F,'FrozenNeural',side_effect=AssertionError('wrong endpoint must reject before scorer decode')):
            self.assertRaisesRegex(ValueError,'scorer_delivery_binding',F.receive_scorer,data,meta|{'recipient':2})
        corrupt=B.loads(data);corrupt['payload']['state_id']='f'*64
        self.assertRaises(ValueError,F.receive_scorer,A.canonical(corrupt),meta)

    def test_collective_validation_uses_only_decoded_delivered_scorers(self):
        coordinator=[];delivered=[];evaluated=[]
        freeze=F.freeze;receive=F.receive_scorer;evaluate=F.evaluate_owner
        def sender(*args,**kwargs):
            q=freeze(*args,**kwargs);coordinator.append(q);return q
        def recipient(*args,**kwargs):
            q=receive(*args,**kwargs);delivered.append(q);return q
        def owner(ds,scorer,*args,**kwargs):
            self.assertTrue(any(scorer is x for x in delivered));self.assertFalse(any(scorer is x for x in coordinator))
            evaluated.append(scorer);return evaluate(ds,scorer,*args,**kwargs)
        plan=replace(self.plan,seeds=(54,),checkpoints=(1,),arms=('pooled_central','fedavg'))
        with patch.object(F,'freeze',sender),patch.object(F,'receive_scorer',recipient),patch.object(F,'evaluate_owner',owner):
            r=S.run_neural(self.ds,plan,self.root/'delivered',synthetic_only=True)
        self.assertEqual(r['status'],'complete_finite_neural_stage');self.assertEqual(len(evaluated),20)
        records=[json.loads(line) for line in (self.root/'delivered/messages.jsonl').read_text().splitlines()]
        deliveries=[q for q in records if q['kind']=='checkpoint_scorer_delivery']
        self.assertEqual(len(deliveries),20);self.assertTrue(all(q['sender']==0 and q['recipient'] in R.OWNERS and q['bytes']>0 for q in deliveries))

    def test_fixed_and_wider_parameter_envelopes_include_scorer_distribution(self):
        # ASCII128 bounds this study's frozen ASCII schema, not all possible
        # Unicode names accepted by the generic scorer schema validator.
        maxds=object.__new__(PurposeDataset);maxds.features=tuple(str(i).zfill(3)+'x'*125 for i in range(73));maxds.summary=self.ds.summary
        observations=[]
        for hidden,fl_trials,collective_trials in [((16,),12,24),((64,128,64),2,4)]:
            state=F.snapshot(F.template(hidden));scope=D.training_scope(maxds)
            scorer=F.freeze(maxds,state,hidden,0,np.zeros(73),np.ones(73))
            delivery=F.scorer_delivery(scorer,{'scope':scope.scope_id,'trial':35,'seed':20261113,'grid':5,'checkpoint':4,'arm':'pooled_central','recipient':10})
            model=F.model_frame(state,hidden,{'scope':scope.scope_id,'trial':35,'owner':10,'round':4,'count':2**64-1,'parent':'f'*64})
            moments=M.encode('moments',R.meta(scope,'fedavg',10,2**64-1),{'mean':np.zeros(73),'M2':np.zeros(73)})
            transform=M.encode('transform',R.meta(scope,'fedavg',0,2**64-1),{'mean':np.zeros(73),'denominator':np.ones(73)})
            maximum=fl_trials*90*len(model)+collective_trials*3*10*(len(delivery)+4096)+10*(len(moments)+len(transform))
            self.assertLess(maximum,64*2**20)
            observations.append({'hidden':hidden,'delivery_bytes_ascii128':len(delivery),'model_frame_bytes':len(model),
                'parameter_and_summary_upper_bound_bytes':maximum,'cap_bytes':64*2**20,
                'includes':'FLinitial+4roundupdates/downlinks,allcheckpointscorerdeliveries,max4096BCEsummaries,coldmoment/transformfanout',
                'excludes':'separately charged pooled rawTRAIN,artifact storage; no universal Unicode schema bound'})
        print(json.dumps({'fabricated_conservative_parameter_envelopes':observations},sort_keys=True))

    def test_validation_never_calls_fit_or_calibration(self):
        original=self.ds.scoring
        def validation(role,*args,**kwargs):self.assertEqual(role,'validation');return original(role,*args,**kwargs)
        with (patch.object(self.ds,'scoring',validation),patch.object(self.ds,'supervised_train',side_effect=AssertionError('fit')),
              patch.object(self.ds,'validation_selection',side_effect=AssertionError('labels through reporting only'))):
            r=F.evaluate_owner(self.ds,self.scorer(),1,F.Budget(20,1000))
        self.assertEqual(r['missing_scores'],0);self.assertIsNone(r['classification_threshold'])

    def test_validation_partial_failure_tracks_generated_shortfall(self):
        original=F.FrozenNeural.predict;calls=[0]
        def fail(s,*args,**kwargs):
            calls[0]+=1
            if calls[0]>1:raise ValueError('fabricated_failure')
            return original(s,*args,**kwargs)
        with patch.object(F.FrozenNeural,'predict',fail):
            with self.assertRaises(F.ValidationFailure) as cm:F.evaluate_owner(self.ds,self.scorer(),1,F.Budget(20,1000),batch_rows=1)
        r=cm.exception.receipt;self.assertEqual(r['valid_scores'],1);self.assertEqual(r['missing_scores'],r['expected_rows']-1)

    def test_budget_failure_is_retained_no_complete_seal(self):
        plan=replace(self.plan,max_seconds=0)
        with self.assertRaises(F.BudgetExceeded):S.run_neural(self.ds,plan,self.root/'budget',synthetic_only=True)
        r=json.loads((self.root/'budget/FAILED.json').read_text());self.assertEqual(r['status'],'budget_limited')
        self.assertEqual(r['validation_missing_scores'],r['validation_expected_scores'])
        self.assertFalse((self.root/'budget/COMPLETE.json').exists())

    def test_failed_slot_is_not_retried_or_removed(self):
        original=S.train_pass;calls=[0]
        def fail(*args,**kwargs):
            calls[0]+=1
            if calls[0]==1:raise ValueError('fabricated_first_slot_failure')
            return original(*args,**kwargs)
        with patch.object(S,'train_pass',fail):
            r=S.run_neural(self.ds,replace(self.plan,seeds=(19,),checkpoints=(1,)),self.root/'failed-slot',synthetic_only=True)
        self.assertEqual(len(r['trials']),3);self.assertEqual(r['trials'][0]['status'],'failed_or_incomplete_trial')
        self.assertEqual(r['status'],'finite_stage_with_failed_trials');self.assertGreater(r['validation_missing_scores'],0)
        self.assertTrue((self.root/'failed-slot/trial-000/PARTIAL-CHECKPOINT.json').exists())

    def test_initialization_failure_consumes_slots_without_retry(self):
        with patch.object(F,'template',side_effect=RuntimeError('fabricated_init_failure')):
            r=S.run_neural(self.ds,replace(self.plan,seeds=(18,),checkpoints=(1,)),self.root/'init-fail',synthetic_only=True)
        self.assertEqual(len(r['trials']),3)
        self.assertTrue(all(q['status']=='failed_trial_initialization' for q in r['trials']))
        self.assertEqual(r['validation_missing_scores'],r['validation_expected_scores'])

    def test_partial_validation_failure_accounts_for_entire_universe(self):
        original=F.FrozenNeural.predict;calls=[0]
        def fail(s,*args,**kwargs):
            calls[0]+=1
            if calls[0]==2:raise ValueError('fabricated_one_later_batch_failure')
            return original(s,*args,**kwargs)
        plan=replace(self.plan,seeds=(71,),checkpoints=(1,),batch_rows=1)
        with patch.object(F.FrozenNeural,'predict',fail):
            r=S.run_neural(self.ds,plan,self.root/'validation-fail',synthetic_only=True)
        v=self.ds.summary['rows_by_role']['validation']
        self.assertEqual(r['validation_expected_scores'],3*v)
        self.assertEqual(r['validation_generated_scores_including_active'],2*v+1)
        self.assertEqual(r['validation_missing_scores'],v-1)
        self.assertFalse((self.root/'validation-fail/COMPLETE.json').exists())

    def test_no_source_array_or_role_changes(self):
        before=(B.sha(self.ds._X.tobytes()),B.sha(self.ds._records.tobytes()))
        F.evaluate_owner(self.ds,self.scorer(),1,F.Budget(20,1000))
        self.assertEqual(before,(B.sha(self.ds._X.tobytes()),B.sha(self.ds._records.tobytes())))
        self.assertFalse(self.ds._X.flags.writeable);self.assertFalse(self.ds._records.flags.writeable)

    def test_anchor_hash_selection_ignores_predictor_values(self):
        store=R.stage(self.ds.supervised_train(1),256,[],'fabricated');ids=S.select_anchor(store,5,13)
        changed=R.Store(store.owner,immutable(store.X+100),store.identities,store.y)
        self.assertEqual(ids,S.select_anchor(changed,5,13));self.assertEqual(len(ids),5)
        self.assertTrue(all(store.y[store.identities.index(i)]==0 for i in ids))
        self.assertRaises(ValueError,S.select_anchor,store,10000,13)

    def test_anchor_identity_namespace_is_preserved_across_delivery_amendment(self):
        import hashlib
        store=R.stage(self.ds.supervised_train(1),256,[],'fabricated')
        eligible=[r for r,y in zip(store.identities,store.y) if y==0]
        def old_key(r):return hashlib.sha256(A.canonical(['finite-development-v2',13,r.source_id,r.source_row,r.observer_id,r.role_id])).digest(),r.source_id,r.source_row
        self.assertEqual(S.select_anchor(store,5,13),tuple(sorted(eligible,key=old_key)[:5]))

    def test_af_round_zero_is_rejected_by_new_scorer_contract(self):
        store=R.stage(self.ds.supervised_train(1),256,[],'fabricated');ids=S.select_anchor(store,5,13)
        view=self.ds.trusted_benign_anchor(1,ids,approval_id='fabricated-positive-final-round')
        anchor=R.stage(view,256,[],'fabricated')
        batch=R.adapt(anchor,np.arange(len(anchor.X)),D.training_scope(self.ds))
        initial,_=A.initialize_anchor(batch,A.Parameters(.001,3.,.5,3.),'fabricated-initial-state',trusted_benign=True)
        self.assertEqual(initial.round_id,0)
        self.assertRaisesRegex(ValueError,'positive_final_af_round_required',F.freeze_af,self.ds,initial)

    def test_af_full_worker_coverage_exact_anchor_exclusion_and_reference(self):
        original=A.summarize
        def no_labels(batch,state):self.assertFalse(hasattr(batch,'y'));return original(batch,state)
        with patch.object(A,'summarize',no_labels):
            r=S.run_af(self.ds,self.root/'af',synthetic_only=True,anchor_count=5,seeds=(31,),max_seconds=120)
        self.assertEqual(r['status'],'complete_finite_af_stage');self.assertEqual(len(r['fits']),3)
        n=self.ds.summary['rows_by_role']['train'];v=self.ds.summary['rows_by_role']['validation']
        for q in r['fits']:
            self.assertEqual(q['rows_completed'],n-5);self.assertEqual(q['validation_valid_scores'],v)
            logs=self.root/'af'/f"fit-{r['fits'].index(q):02}"/'rounds.jsonl'
            audits=[json.loads(line) for line in logs.read_text().splitlines()]
            self.assertEqual(q['postinitial_anchor_visits'],sum(a['anchor_rows_rescored'] for a in audits))
            self.assertLessEqual(q['postinitial_anchor_visits'],q['rounds']*5)
            self.assertEqual(q['covariance_updates_after_initialization'],0)
        self.assertEqual([q['source_reference'] for q in r['fits']],[True,False,False])
        self.assertNotIn('best_ridge',r)

    def test_af_budget_failure_retains_whole_score_universe(self):
        r=S.run_af(self.ds,self.root/'af-budget',synthetic_only=True,anchor_count=5,seeds=(99,),max_seconds=0)
        self.assertEqual(r['status'],'budget_limited');self.assertEqual(len(r['fits']),3)
        self.assertEqual(r['validation_expected_scores'],3*self.ds.summary['rows_by_role']['validation'])
        self.assertEqual(r['validation_missing_scores'],r['validation_expected_scores'])
        self.assertEqual(r['validation_generated_scores_including_active'],0)
        self.assertFalse((self.root/'af-budget/COMPLETE.json').exists())

    def test_af_terminal_storage_cap_withholds_complete_after_finished_fits(self):
        target=self.root/'af-terminal-budget';original=F.Budget.refresh_storage;observed=[]
        def terminal(budget,root,**kwargs):
            if Path(root)==target:
                observed.append(True);budget.storage_cap=max(0,sum(p.stat().st_size for p in target.rglob('*') if p.is_file())-1)
            return original(budget,root,**kwargs)
        with patch.object(F.Budget,'refresh_storage',terminal):
            self.assertRaises(F.BudgetExceeded,S.run_af,self.ds,target,synthetic_only=True,anchor_count=5,seeds=(35,),max_seconds=120)
        self.assertTrue(observed);self.assertFalse((target/'COMPLETE.json').exists())
        r=json.loads((target/'FAILED.json').read_text());self.assertEqual(r['status'],'budget_limited')
        self.assertEqual(len(r['fits']),3);self.assertTrue(all(q['status']=='complete_af_sensitivity_fit' for q in r['fits']))


if __name__=='__main__':unittest.main()
