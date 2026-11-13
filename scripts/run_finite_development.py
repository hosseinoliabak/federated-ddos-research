"""Bounded continuous neural trials and AF source-row-anchor sensitivity.

The public CLI accepts fabricated inputs only. Acquired-data use requires a
separate pinned controller/release. The original source and runs are unchanged.
"""
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
import argparse
import hashlib
import json
import os
import platform
import sys
import tempfile
import time
if __name__ == '__main__':
    for n in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','VECLIB_MAXIMUM_THREADS'): os.environ[n]='2'
import numpy as np
import torch
from threadpoolctl import threadpool_limits, threadpool_info
import finite_development as F
import afbkm_adapter_v2 as A
import afbkm_wire_v2 as AW
import frozen_model_bundle as B
import load_grouped_candidate as L
import run_matched_workload as R
import workload_messages as M
import train_separability_diagnostic as D
from purpose_data_view import PurposeDataset, PurposeView, immutable

now = lambda: datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class Plan:
    stage: str = 'fixed16-grid'
    seeds: tuple = (20261112, 20261113)
    grid: tuple = F.GRID
    checkpoints: tuple = (1, 2, 4)
    hidden: tuple = (16,)
    arms: tuple = F.ARMS
    batch_rows: int = 256
    cpu_threads: int = 2
    max_seconds: int = 10800
    max_parameter_bytes: int = 64 * 2**20
    max_raw_bytes: int = 3 * 2**30
    max_storage_bytes: int = 20 * 2**30

    def validate(self):
        B.require(self.stage in {'fixed16-grid','wider-capacity','shared-moment-ablation','fabricated'}, 'finite_stage')
        B.require(type(self.seeds) is tuple and len(set(self.seeds)) == len(self.seeds) and len(self.seeds) >= 1
                  and all(type(v) is int and v >= 0 for v in self.seeds), 'finite_seeds')
        B.require(type(self.grid) is tuple and 1 <= len(self.grid) <= 6 and len(set(self.grid)) == len(self.grid), 'finite_grid')
        for q in self.grid: q.validate()
        F.architecture(self.hidden)
        B.require(type(self.checkpoints) is tuple and self.checkpoints in {(1,), (1,2), (1,2,4)}, 'finite_checkpoints')
        B.require(type(self.arms) is tuple and len(set(self.arms)) == len(self.arms) and len(self.arms) >= 1
                  and set(self.arms) <= set(F.ARMS) | {'local_shared_moments'}, 'finite_arms')
        B.require(self.cpu_threads == 2 and type(self.batch_rows) is int and 1 <= self.batch_rows <= 256, 'finite_compute_configuration')
        for v in (self.max_seconds,self.max_parameter_bytes,self.max_raw_bytes,self.max_storage_bytes): B.integer(v)
        if self.stage != 'fabricated':
            B.require(self.seeds == (20261112,20261113) and self.checkpoints == (1,2,4) and self.batch_rows == 256, 'actual_fixed_schedule')
            B.require(self.max_raw_bytes==3*2**30 and self.max_storage_bytes==20*2**30 and
                      self.max_parameter_bytes==(16*2**20 if self.stage=='shared-moment-ablation' else 64*2**20),'actual_fixed_byte_caps')
            if self.stage == 'fixed16-grid': B.require(self.hidden == (16,) and self.grid == F.GRID and self.arms == F.ARMS and self.max_seconds == 10800, 'fixed16_schedule')
            if self.stage == 'wider-capacity': B.require(self.hidden == (64,128,64) and self.grid == (F.OptimizerSpec('SGD',.01),) and self.arms == F.ARMS and self.max_seconds == 5400, 'capacity_schedule')
            if self.stage == 'shared-moment-ablation': B.require(self.hidden == (16,) and self.grid == (F.OptimizerSpec('SGD',.01),) and self.arms == ('local_shared_moments',) and self.max_seconds == 1800, 'ablation_schedule')

    def payload(self):
        return asdict(self) | {'version': F.VERSION, 'optimizer_settings':[q.configuration() for q in self.grid],
            'score_representation':'sigmoid_float32; logits separately retained for BCE selection',
            'optimizer_state':'local/pooled continuous; client Adam reset each FL round; no server Adam',
            'selection_channels':'own-owner local BCE; pooled/FL union sum-count BCE; shared-moment local is collaboration condition',
            'ceiling_scope':'scheduling choice only; no operational bound, power guarantee or convergence claim'}


def stage_plan(stage):
    if stage == 'fixed16-grid': return Plan()
    if stage == 'wider-capacity': return Plan(stage=stage,hidden=(64,128,64),grid=(F.OptimizerSpec('SGD',.01),),max_seconds=5400)
    if stage == 'shared-moment-ablation': return Plan(stage=stage,grid=(F.OptimizerSpec('SGD',.01),),arms=('local_shared_moments',),max_seconds=1800,max_parameter_bytes=16*2**20)
    raise ValueError('unsupported_neural_stage')


class Ledger(R.Ledger):
    def __init__(self,out,budget):
        super().__init__(out); self.budget=budget

    def record(self,arm,kind,sender,recipient,payload,elapsed,**kwargs):
        before=self.path.stat().st_size
        super().record(arm,kind,sender,recipient,payload,elapsed,**kwargs)
        self.budget.storage_bytes+=self.path.stat().st_size-before
        self.budget.charge_message(len(payload),raw=kind=='pooled_raw')


def stage_view(view,batch_rows,access,arm,budget,progress):
    B.require(type(view) is PurposeView and view.role=='train' and view.purpose in
              {'supervised_train','unlabeled_train','anchor_train'},'training_view_required')
    tick=time.monotonic();parts=[];ys=[];ids=[];labelled=view.purpose=='supervised_train'
    rec={'owner':view.observer_id,'arm':arm,'purpose':view.purpose,'status':'running',
         'feature_rows_read':0,'label_rows_exposed':0};access.append(rec)
    try:
        budget.check()
        for batch in view.batches(batch_rows):
            parts.append(batch.X);ids.extend(batch.identities)
            if labelled:ys.append(batch.y);rec['label_rows_exposed']+=len(batch.X)
            else:B.require(not hasattr(batch,'y'),'af_worker_labels_forbidden')
            rec['feature_rows_read']+=len(batch.X);progress['source_access']=dict(rec);budget.check()
        store=R.Store(view.observer_id,immutable(np.concatenate(parts) if parts else np.empty((0,73),dtype='<f8')),tuple(ids),
            immutable(np.concatenate(ys) if ys else np.empty(0,dtype='u1')) if labelled else None)
        store.validate();rec.update(status='complete',identity_sha256=R.identity_digest(ids),seconds=time.monotonic()-tick)
        return store
    except BaseException as exc:
        rec.update(status='failed_or_incomplete',error_type=type(exc).__name__,error=str(exc),seconds=time.monotonic()-tick);raise


def owner_moment_message(store,scope,arm,batch_rows=256):
    """Local function returns only a whitelisted moment frame to coordinator."""
    store.validate(); moments=M.fit_moments(store.X,batch_rows)
    return M.encode('moments',R.meta(scope,arm,store.owner,len(store.X)),{'mean':moments.mean,'M2':moments.M2})


def merge_moment_messages(messages,scope,arm,counts):
    """No dataset, raw row, Store or label argument is accepted here."""
    B.require(set(messages)==set(counts)==set(R.OWNERS),'all_owner_moments')
    union=M.empty_moments()
    for owner in R.OWNERS:
        _,header,arrays=B.decode_parameter_frame(messages[owner],'moments')
        B.require(header==R.meta(scope,arm,owner,counts[owner]),'moment_scope_or_count')
        union=M.merge_moments(union,M.Moments(header['count'],arrays['mean'],arrays['M2']))
    B.require(union.count==sum(counts.values()),'moment_coverage')
    return union


def prepare(dataset,plan,scope,ledger,budget,access,progress):
    # Each Store belongs to its native simulated owner. The union cache is
    # reconstructed separately and is never an input to local/FL trainers.
    own={}; transforms={}; pooled={}; shared={}; local_moment_ids={}
    for owner in R.OWNERS:
        progress.update(phase='prepare_native_train',owner=owner); budget.check()
        store=stage_view(dataset.supervised_train(owner),plan.batch_rows,access,'finite_owner_cache',budget,progress)
        B.require(len(store.X)==sum(D.support(dataset,'train',owner).values()),'owner_train_coverage')
        own[owner]=store; moments=M.fit_moments(store.X,plan.batch_rows)
        transforms[owner]=(moments.mean,M.denominator(moments)) if moments.count else (np.zeros(73),np.ones(73))
        local_moment_ids[str(owner)]=A.digest([moments.mean.tolist(),moments.M2.tolist()]);budget.check()
    if set(plan.arms)&{'fedavg','local_shared_moments'}:
        arm='fedavg' if 'fedavg' in plan.arms else 'local_shared_moments'; messages={}
        for owner in R.OWNERS:
            budget.check();tick=time.monotonic();frame=owner_moment_message(own[owner],scope,arm,plan.batch_rows)
            ledger.record(arm,'moments',owner,0,frame,time.monotonic()-tick,fields=('mean','M2'));messages[owner]=frame
        union=merge_moment_messages(messages,scope,arm,{o:len(s.X) for o,s in own.items()})
        for owner in R.OWNERS:
            expected=R.meta(scope,arm,0,union.count)
            header,arrays=ledger.transfer('transform',expected,{'mean':union.mean,'denominator':M.denominator(union)},0,owner)
            B.require(header==expected,'transform_message_binding');shared[owner]=(arrays['mean'],arrays['denominator'])
    if 'pooled_central' in plan.arms:
        union=M.empty_moments()
        for owner in R.OWNERS:
            chunks=[];store=own[owner]
            for begin in range(0,len(store.X),plan.batch_rows):
                budget.check();end=min(begin+plan.batch_rows,len(store.X));meta=R.meta(scope,'pooled_central',owner,end-begin)
                header,arrays=ledger.transfer('pooled_raw',meta,R.raw_arrays(store,begin,end),owner,0)
                B.require(header==meta,'pooled_cache_binding');chunks.append(arrays)
            pooled[owner]=R.received_store(owner,chunks)
            B.require(pooled[owner].identities==store.identities and np.array_equal(pooled[owner].X,store.X)
                      and np.array_equal(pooled[owner].y,store.y),'pooled_cache_reconstruction')
            union=M.merge_moments(union,M.fit_moments(pooled[owner].X,plan.batch_rows));budget.check()
        global_transform=(union.mean,M.denominator(union))
        if shared:
            B.require(all(np.array_equal(a,b) for a,b in zip(global_transform,shared[1])),'pooled_shared_transform_mismatch')
    else: global_transform=None
    return own,transforms,pooled,global_transform,shared,local_moment_ids


def train_pass(model,optimizer,store,transform,order,batch_rows,budget,progress):
    store.validate();B.require(store.y is not None,'supervised_labels_required')
    tick=time.monotonic();rows=steps=0;loss_sum=0.;sizes=[]
    progress.update(owner=store.owner,planned_rows=len(order),rows=0,steps=0,attempted_rows=0,optimizer_steps_attempted=0)
    for begin in range(0,len(order),batch_rows):
        budget.check();positions=order[begin:begin+batch_rows]
        x=torch.from_numpy(M.standardize(store.X[positions],*transform));y=torch.from_numpy(store.y[positions].astype('<f4'))
        progress['attempted_rows']+=len(positions);optimizer.zero_grad(set_to_none=True)
        loss=torch.nn.functional.binary_cross_entropy_with_logits(model(x).squeeze(1),y)
        B.require(bool(torch.isfinite(loss)),'nonfinite_training_loss');loss.backward()
        B.require(all(p.grad is not None and bool(torch.isfinite(p.grad).all()) for p in model.parameters()),'nonfinite_gradient')
        progress['optimizer_steps_attempted']+=1;optimizer.step()
        B.require(all(bool(torch.isfinite(p).all()) for p in model.parameters()),'nonfinite_parameter')
        rows+=len(positions);steps+=1;sizes.append(len(positions));loss_sum+=float(loss.detach())*len(positions)
        progress.update(rows=rows,steps=steps);budget.check()
    B.require(rows==len(order),'training_tail_missing')
    return {'owner':store.owner,'rows':rows,'steps':steps,'batch_sizes':sizes,'tail_rows':sizes[-1] if sizes else 0,
            'online_training_bce_sum':loss_sum,'seconds':time.monotonic()-tick,
            'order_sha256':R.identity_digest(store.identities[i] for i in order)}


def checkpoint(out,models,optimizers,transforms,hidden,meta,budget=None):
    partial=meta.get('partial',False)
    states={str(o):{k:F.packed_array(v,allow_nonfinite=partial) for k,v in F.snapshot(model).items()} for o,model in models.items()}
    q={'version':F.VERSION,'meta':meta,'hidden':list(hidden),'models':states,
       'model_ids':{str(o):F.state_id(F.snapshot(m)) for o,m in models.items()},
       'optimizer_state':{str(o):F.pack_tree(opt.state_dict(),allow_nonfinite=partial) for o,opt in optimizers.items()},
       'transforms':{str(o):{'mean':F.packed_array(t[0]),'denominator':F.packed_array(t[1])} for o,t in transforms.items()},
       'resume_policy':'archival state only; actual resume would require a separately reviewed finite amendment',
       'partial_archive_ineligible_for_scoring':bool(partial),
       'nonfinite_model_values':{str(o):sum(int((~np.isfinite(v)).sum()) for v in F.snapshot(m).values()) for o,m in models.items()}}
    F.write(out,q,budget);return B.sha(out.read_bytes())


def aggregate_models(states,counts,hidden):
    B.require(set(states)==set(counts)==set(R.OWNERS) and sum(counts.values())>0,'full_participation_counts')
    for s in states.values():F.validate_state(s,hidden)
    result={}
    with np.errstate(over='raise',invalid='raise',divide='raise'):
        for key in F.shapes(hidden):
            a=sum(states[o][key].astype('<f8')*(counts[o]/sum(counts.values())) for o in R.OWNERS).astype('<f4')
            B.require(bool(np.isfinite(a).all()),'aggregate_nonfinite');result[key]=immutable(a)
    return result


def neural_trial(dataset,scope,plan,seed,grid,arm,trial_id,resources,out,ledger,budget,progress):
    own,local,pooled,global_transform,shared,_=resources
    spec=plan.grid[grid];tick=time.monotonic();out.mkdir();models={};opts={};metrics=[];summaries=[];passes=[]
    with torch.random.fork_rng(devices=[]):torch.manual_seed(seed);initial=F.snapshot(F.template(plan.hidden))
    initial_id=F.state_id(initial);orders={o:R.order_for(own[o],seed) for o in R.OWNERS}
    transforms=local if arm=='independent_local' else shared if arm in {'fedavg','local_shared_moments'} else {o:global_transform for o in R.OWNERS}
    if arm=='pooled_central':models[0]=F.clone(initial,plan.hidden);opts[0]=spec.make(models[0])
    elif arm!='fedavg':
        for o in R.OWNERS:models[o]=F.clone(initial,plan.hidden);opts[o]=spec.make(models[o])
    current=initial;replicas={o:initial for o in R.OWNERS};counts={o:len(own[o].X) for o in R.OWNERS}
    r={'status':'running','arm':arm,'seed':seed,'grid':grid,'trial':trial_id,'initial_id':initial_id,'started_utc':now(),
       'optimizer':spec.configuration(),'planned_horizon':max(plan.checkpoints),'completed_presentations':0,
       'train_rows':0,'optimizer_steps':0,'validation_valid_scores':0,'validation_expected_scores':
           len(plan.checkpoints)*dataset.summary['rows_by_role']['validation'],'checkpoints':[], 'passes':passes,
       'optimizer_state_policy':'reset_client_each_round_no_server_optimizer' if arm=='fedavg' else 'retain_continuous_across_owner_blocks_and_presentations',
       'training_permutation':'same seed/owner permutation repeated each complete presentation; pooled owner blocks1..10',
       'selection_channel':'own_validation_only' if arm=='independent_local' else 'collaboration_shared_moments_own_validation' if arm=='local_shared_moments' else 'union_loss_summary'}
    def save():F.write(out/'TRIAL.json',r)
    def transfer(state,owner,round_id,parent,sender,recipient,kind):
        meta={'scope':scope.scope_id,'trial':trial_id,'owner':owner,'round':round_id,'count':counts.get(owner,sum(counts.values())),'parent':parent}
        t=time.monotonic();frame=F.model_frame(state,plan.hidden,meta);decoded=F.decode_model(frame,plan.hidden,meta)
        ledger.record(arm,kind,sender,recipient,frame,time.monotonic()-t,round_id=round_id,fields=tuple(state));return decoded
    save()
    try:
        if arm=='fedavg':
            for o in R.OWNERS:replicas[o]=transfer(current,0,0,initial_id,0,o,'model_initial')
        for epoch in range(1,max(plan.checkpoints)+1):
            states={};epoch_records=[]
            for owner in R.OWNERS:
                progress.update(phase='neural_train',trial=trial_id,arm=arm,presentation=epoch,owner=owner,training={})
                budget.check()
                if arm=='fedavg':
                    models[owner]=F.clone(replicas[owner],plan.hidden);opts[owner]=spec.make(models[owner])
                key=0 if arm=='pooled_central' else owner
                store=pooled[owner] if arm=='pooled_central' else own[owner]
                item=train_pass(models[key],opts[key],store,transforms[owner],orders[owner],plan.batch_rows,budget,progress['training'])
                item.update(presentation=epoch,optimizer_state_digest=A.digest(F.pack_tree(opts[key].state_dict())))
                epoch_records.append(item);r['train_rows']+=item['rows'];r['optimizer_steps']+=item['steps']
                if arm=='fedavg':states[owner]=transfer(F.snapshot(models[owner]),owner,epoch,F.state_id(current),owner,0,'model_update')
                save()
            if arm=='fedavg':
                tick_merge=time.monotonic();previous_id=F.state_id(current);current=aggregate_models(states,counts,plan.hidden)
                for owner in R.OWNERS:replicas[owner]=transfer(current,0,epoch,previous_id,0,owner,'model_final')
                epoch_records.append({'aggregation_seconds':time.monotonic()-tick_merge,'participants':list(R.OWNERS),
                     'native_train_counts':counts,'global_state_id':F.state_id(current),
                     'discarded_client_optimizer_state':{str(o):A.digest(F.pack_tree(opt.state_dict())) for o,opt in opts.items()}})
                models={0:F.clone(current,plan.hidden)};opts={}
            passes.extend(epoch_records);r['completed_presentations']=epoch
            B.require(sum(q['rows'] for q in epoch_records if 'rows' in q)==dataset.summary['rows_by_role']['train'],'full_epoch_coverage')
            if epoch in plan.checkpoints:
                progress.update(phase='checkpoint',trial=trial_id,presentation=epoch)
                checkpoint_models=models;checkpoint_transforms=({0:global_transform} if arm=='pooled_central' else {0:shared[1]} if arm=='fedavg' else transforms)
                ck=out/f'checkpoint-{epoch}.json'
                checkpoint_id=checkpoint(ck,checkpoint_models,opts,checkpoint_transforms,plan.hidden,
                   {'scope':scope.scope_id,'seed':seed,'grid':grid,'arm':arm,'presentation':epoch,'trial':trial_id,
                    'optimizer_configuration':spec.configuration(),'train_rows':r['train_rows'],'optimizer_steps':r['optimizer_steps'],
                    'completed_presentations':epoch,'optimizer_state_policy':r['optimizer_state_policy']},budget)
                scores=[];messages=[]
                for owner in R.OWNERS:
                    progress.update(phase='validation',trial=trial_id,presentation=epoch,owner=owner)
                    key=0 if arm in {'pooled_central','fedavg'} else owner
                    coordinator_scorer=F.freeze(dataset,F.snapshot(models[key]),plan.hidden,key,*transforms[owner])
                    delivery=None
                    if arm in {'pooled_central','fedavg'}:
                        expected_delivery={'scope':scope.scope_id,'trial':trial_id,'seed':seed,'grid':grid,
                             'checkpoint':epoch,'arm':arm,'recipient':owner}
                        t=time.monotonic();frame=F.scorer_delivery(coordinator_scorer,expected_delivery)
                        ledger.record(arm,'checkpoint_scorer_delivery',0,owner,frame,time.monotonic()-t,
                                      round_id=epoch,fields=('model','transform','input_schema','scorer_id'))
                        scorer=F.receive_scorer(frame,expected_delivery)
                        B.require(scorer.scorer_id==coordinator_scorer.scorer_id,'delivered_scorer_identity')
                        delivery={'bytes':len(frame),'sha256':B.sha(frame),'sender':0,'recipient':owner,
                                  'policy':'full explicit checkpoint scorer for both collective arms; FedAvg duplicates its existing model/transform delivery'}
                    else:scorer=coordinator_scorer
                    F.write(out/f'scorer-{epoch}-owner{key}.json',B.loads(scorer.data),budget)
                    record=F.evaluate_owner(dataset,scorer,owner,budget,batch_rows=plan.batch_rows)
                    record.update(seed=seed,grid=grid,checkpoint=epoch,arm=arm,trial=trial_id,trial_complete=False)
                    record['scorer_delivery']=delivery
                    record['validation_model_access']='decoded_serialized_checkpoint_scorer' if delivery else 'own_resident_local_checkpoint'
                    r['validation_valid_scores']+=record['valid_scores'];scores.append(record);metrics.append(record)
                    F.write(out/f'validation-{epoch}-owner{owner}.json',record,budget)
                    if arm in {'pooled_central','fedavg'}:
                        raw=F.loss_message(record,scope=scope.scope_id,seed=seed,grid=grid,checkpoint=epoch,arm=arm)
                        admitted=F.admit_loss_message(raw,scope=scope.scope_id,seed=seed,grid=grid,checkpoint=epoch,arm=arm,
                           owner=owner,expected_rows=sum(D.support(dataset,'validation',owner).values()))
                        ledger.record(arm,'validation_loss_sum_count',owner,0,raw,0.,round_id=epoch,fields=('loss_sum','count','identity_sha256','scorer_id'))
                        messages.append(admitted)
                    save()
                if arm in {'pooled_central','fedavg'}:
                    B.require(len(messages)==10 and {q['owner'] for q in messages}==set(R.OWNERS),'all_owner_validation_summaries')
                    summaries.append({'owner':0,'seed':seed,'grid':grid,'checkpoint':epoch,'arm':arm,'trial_complete':False,
                        'status':'complete_validation','loss_sum':sum(q['loss_sum'] for q in messages),
                        'loss_count':sum(q['count'] for q in messages),'missing_scores':0,
                        'coordinator_input':'only bound per-owner loss_sum/count messages, no raw validation labels/predictors'})
                r['checkpoints'].append({'presentation':epoch,'sha256':checkpoint_id,'validation_valid_scores':sum(q['valid_scores'] for q in scores)})
                budget.refresh_storage(out.parent)
            budget.check();save()
        B.require(r['train_rows']==max(plan.checkpoints)*dataset.summary['rows_by_role']['train'],'trial_train_coverage')
        r.update(status='complete_continuous_trial',finished_utc=now(),elapsed_seconds=time.monotonic()-tick,
                 validation_missing_scores=r['validation_expected_scores']-r['validation_valid_scores'])
        B.require(r['validation_missing_scores']==0,'trial_validation_coverage')
        for q in metrics+summaries:q['trial_complete']=True
        F.write(out/'METRICS.json',{'owner_metrics':metrics,'collective_selection_records':summaries},budget);save()
        return r,metrics,summaries
    except BaseException as exc:
        r.update(status='budget_limited' if isinstance(exc,F.BudgetExceeded) else 'failed_or_incomplete_trial',
           finished_utc=now(),elapsed_seconds=time.monotonic()-tick,error_type=type(exc).__name__,error=str(exc),partial_progress=dict(progress),
           validation_missing_scores=r['validation_expected_scores']-r['validation_valid_scores'])
        if isinstance(exc,F.ValidationFailure):
            r['active_validation']=exc.receipt;r['validation_generated_scores_including_active']=r['validation_valid_scores']+exc.receipt['valid_scores']
            r['validation_missing_scores']=r['validation_expected_scores']-r['validation_generated_scores_including_active']
            if exc.receipt['error_type']=='BudgetExceeded':r['status']='budget_limited'
        if progress.get('phase')=='neural_train':
            work=progress.get('training',{})
            r['training_rows_completed_including_active']=r['train_rows']+work.get('rows',0)
            r['optimizer_steps_completed_including_active']=r['optimizer_steps']+work.get('steps',0)
        try:checkpoint(out/'PARTIAL-CHECKPOINT.json',models,opts,({0:global_transform} if arm=='pooled_central' else transforms),plan.hidden,
                       {'scope':scope.scope_id,'arm':arm,'seed':seed,'grid':grid,'partial':True,'work':r['partial_progress']})
        except BaseException as archive_exc:r['partial_archive_failure']={'type':type(archive_exc).__name__,'error':str(archive_exc)}
        F.write(out/'FAILED.json',r);save()
        if not isinstance(exc,Exception):raise
        return r,metrics,summaries


def slots(plan):
    result=[]
    for seed in plan.seeds:
        for grid in range(len(plan.grid)):
            offset=(len(result)//len(plan.arms))%len(plan.arms)
            for arm in plan.arms[offset:]+plan.arms[:offset]:result.append((seed,grid,arm))
    return result


def seal(out,status,budget=None):
    files={str(p.relative_to(out)):{'sha256':L.sha(p),'bytes':p.stat().st_size} for p in out.rglob('*') if p.is_file() and p.name!='COMPLETE.json'}
    pending=out/'PENDING-COMPLETE.json'
    F.write(pending,{'version':F.VERSION,'status':status,'artifacts':files})
    # Include terminal manifest bytes/hash/write time before publishing COMPLETE.
    # A failure preserves PENDING-COMPLETE and never publishes a success seal.
    if budget is not None:budget.refresh_storage(out)
    pending.rename(out/'COMPLETE.json')


def run_neural(dataset,plan,output,*,synthetic_only=False):
    B.require(type(dataset) is PurposeDataset,'sealed_dataset_required');plan.validate()
    B.require(not sys.flags.optimize,'optimized_python_forbidden')
    out=B.root_path(output,exists=False);out.mkdir(parents=True,exist_ok=False)
    budget=F.Budget(plan.max_seconds,plan.max_parameter_bytes,plan.max_raw_bytes,plan.max_storage_bytes)
    ledger=Ledger(out,budget);scope=D.training_scope(dataset);access=[];progress={};results=[];metrics=[];summaries=[]
    schedule=slots(plan);r={'version':F.VERSION,'status':'running','started_utc':now(),'plan':plan.payload(),
        'scope':scope.scope_id,'candidate_sha256':scope.candidate_sha256,'assignment_sha256':scope.assignment_sha256,
        'features':list(dataset.features),'input_pins':dataset.summary['input_sha256'],'prepared_artifacts':dataset.summary['artifacts'],
        'source':L.code_context(),'runner_sources':{p.name:L.sha(p) for p in Path(__file__).parent.glob('*.py')},
        'lock_sha256':L.sha(Path(__file__).parents[1]/'uv.lock'),'synthetic_only':synthetic_only,
        'planned_slots':[{'seed':s,'grid':g,'arm':a} for s,g,a in schedule],'trials':results,
        'classification_threshold':None,'calibration_or_final_operation':False,'live_eligible':False,
        'source_access':access,'cache_policy':'native owner TRAIN stores and own transforms reused once bound to candidate/assignment/ordered identities; separately reconstructed pooled cache never supplied to local/FL',
        'cache_cost':'all cold preparation/movement charged once; per-trial marginal time excludes shared preparation; stage includes it',
        'single_process_simulation':True,'network_latency_energy_or_privacy_guarantee':False,
        'hardware':{'platform':platform.platform(),'machine':platform.machine(),'processor':platform.processor()},
        'framework':{'python':platform.python_version(),'numpy':np.__version__,'torch':torch.__version__},
        'timing_boundary':'output creation through preparation,all trials,validation,selection and stage receipt serialization; excludes terminal seal hashing/writes and caller seal opening/outer source hashing, recorded by outer controller'}
    def save():r.update(active=progress,budget=budget.receipt(),message_counts=dict(ledger.counts),application_bytes=dict(ledger.bytes));F.write(out/'STAGE.json',r)
    save()
    try:
        torch.set_num_threads(plan.cpu_threads);torch.use_deterministic_algorithms(True)
        with threadpool_limits(limits=plan.cpu_threads):
            r['thread_control']={'torch':torch.get_num_threads(),'pools':threadpool_info(),
               'environment':{n:os.environ.get(n) for n in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','VECLIB_MAXIMUM_THREADS')},
               'limit':'supported pools; Accelerate OS thread count not measured'}
            resources=prepare(dataset,plan,scope,ledger,budget,access,progress)
            r['preprocessing_complete_seconds']=time.monotonic()-budget.started
            r['owner_cache_identity_sha256']={str(o):R.identity_digest(s.identities) for o,s in resources[0].items()}
            r['owner_moment_ids']=resources[-1];save()
            stop=False
            for trial_id,(seed,grid,arm) in enumerate(schedule):
                if stop:
                    results.append({'trial':trial_id,'seed':seed,'grid':grid,'arm':arm,'status':'not_started_stage_budget_exhausted'});continue
                try:trial,tm,ts=neural_trial(dataset,scope,plan,seed,grid,arm,trial_id,resources,out/f'trial-{trial_id:03}',ledger,budget,progress)
                except Exception as exc:
                    # Setup failures before the trial's internal handler still
                    # consume one named slot and retain an explicit receipt.
                    trial={'trial':trial_id,'seed':seed,'grid':grid,'arm':arm,
                        'status':'budget_limited' if isinstance(exc,F.BudgetExceeded) else 'failed_trial_initialization',
                        'error_type':type(exc).__name__,'error':str(exc),'validation_valid_scores':0,
                        'validation_expected_scores':len(plan.checkpoints)*dataset.summary['rows_by_role']['validation']}
                    folder=out/f'trial-{trial_id:03}';folder.mkdir(exist_ok=True);F.write(folder/'FAILED.json',trial);tm=[];ts=[]
                results.append(trial);metrics.extend(tm);summaries.extend(ts);save()
                stop=trial['status']=='budget_limited'
            selections={}
            for arm in plan.arms:
                if arm in {'independent_local','local_shared_moments'}:
                    selections[arm]=[F.choose([q for q in metrics if q['arm']==arm and q['owner']==owner],plan.seeds,len(plan.grid),plan.checkpoints,owner=owner) for owner in R.OWNERS]
                else:selections[arm]=F.choose([q for q in summaries if q['arm']==arm],plan.seeds,len(plan.grid),plan.checkpoints,owner=0)
            F.write(out/'SELECTION.json',{'selections':selections,'all_outcomes_retained':True,'final_or_calibration_access':False})
        status='complete_finite_neural_stage' if all(q['status']=='complete_continuous_trial' for q in results) else 'budget_limited' if stop else 'finite_stage_with_failed_trials'
        r.update(status=status,finished_utc=now(),selections=selections,peak_process_rss_bytes=F.peak_rss_bytes(),
            validation_expected_scores=len(schedule)*len(plan.checkpoints)*dataset.summary['rows_by_role']['validation'],
            validation_valid_scores=sum(q.get('validation_valid_scores',0) for q in results),
            validation_generated_scores_including_active=sum(q.get('validation_generated_scores_including_active',q.get('validation_valid_scores',0)) for q in results))
        r['validation_missing_scores']=r['validation_expected_scores']-r['validation_generated_scores_including_active'];progress.clear();save()
        try:budget.refresh_storage(out)
        except F.BudgetExceeded as exc:r.update(status='budget_limited',terminal_budget_reason=str(exc));status='budget_limited'
        r['budget']=budget.receipt();F.write(out/'STAGE.json',r)
        if status=='complete_finite_neural_stage':seal(out,status,budget)
        else:F.write(out/'INCOMPLETE.json',{'status':status,'trials':[{k:q[k] for k in ('trial','arm','seed','grid','status')} for q in results], 'validation_missing_scores':r['validation_missing_scores']})
        return r
    except BaseException as exc:
        r.update(status='budget_limited' if isinstance(exc,F.BudgetExceeded) else 'failed_finite_stage',finished_utc=now(),error_type=type(exc).__name__,error=str(exc),
            validation_expected_scores=len(schedule)*len(plan.checkpoints)*dataset.summary['rows_by_role']['validation'],
            validation_generated_scores_including_active=sum(q.get('validation_generated_scores_including_active',q.get('validation_valid_scores',0)) for q in results),
            unstarted_slots=[{'seed':s,'grid':g,'arm':a} for s,g,a in schedule[len(results):]])
        r['validation_missing_scores']=r['validation_expected_scores']-r['validation_generated_scores_including_active'];F.write(out/'FAILED.json',r);save();raise


def select_anchor(store,count,seed):
    """Only identity hash ranks eligible Normal TRAIN rows; never predictor values."""
    store.validate();B.require(store.y is not None and type(count) is int and count>=2,'anchor_selector')
    eligible=[i for i,y in enumerate(store.y) if y==0]
    B.require(len(eligible)>=count,'insufficient_trusted_anchor_rows')
    def key(i):
        r=store.identities[i]
        return hashlib.sha256(A.canonical([F.ANCHOR_SELECTION_VERSION,seed,r.source_id,r.source_row,r.observer_id,r.role_id])).digest(),r.source_id,r.source_row
    selected=sorted(eligible,key=key)[:count]
    return tuple(store.identities[i] for i in selected)


def run_af_trial(dataset,seed,ridge,anchor_count,out,budget,ledger,progress):
    scope=D.training_scope(dataset);out.mkdir();access=[];tick=time.monotonic();state=None;rounds=0;worker_rows=0;worker_windows=0;visits=0
    r={'status':'running','seed':seed,'ridge':ridge,'source_reference':ridge==.001,'sensitivity_not_label_selected':True,
        'anchor_count':anchor_count,'anchor_owner':1,'started_utc':now(),'rows_completed':0,'rounds':0,'source_access':access,
        'internal_threshold_use':'training_provenance_only_not_external_reporting','selection':'identity hash of eligible Normal TRAIN owner1; original full-anchor fit unchanged',
        'anchor_semantics':'storedCSVrows, not verified physical packets','covariance_updates_after_initialization':0}
    def save():F.write(out/'TRIAL.json',r)
    save()
    try:
        progress.update(phase='af_anchor_eligibility');budget.check()
        selector=stage_view(dataset.supervised_train(1),256,access,'af_anchor_eligibility',budget,progress)
        ids=select_anchor(selector,anchor_count,seed)
        view=dataset.trusted_benign_anchor(1,ids,approval_id='finite-development-v2-identity-anchor')
        anchor=stage_view(view,256,access,'statistical_complete',budget,progress);anchor_batch=R.adapt(anchor,np.arange(len(anchor.X)),scope)
        state,context=A.initialize_anchor(anchor_batch,A.Parameters(ridge,3.,.5,3.),'finite-af2000-seed'+str(seed)+'-ridge'+str(ridge),trusted_benign=True)
        r.update(anchor_identity_sha256=R.identity_digest(ids),anchor_label_rows_examined=len(selector.X),trusted_anchor_admission_label_rechecks=anchor_count,initial_state_id=state.state_id,
                 fixed_state_id=state.fixed_id,initial_anchor_rows_scored=anchor_count)
        F.write(out/'INITIAL-STATE.json',state.payload(),budget)
        stores={};orders={};cursors={};replicas={};seen={R.row_key(i) for i in ids}
        for owner in R.OWNERS:
            budget.check();stores[owner]=stage_view(dataset.unlabeled_train(owner,exclude_anchor=view if owner==1 else None),256,access,'statistical_complete',budget,progress)
            orders[owner]=R.order_for(stores[owner],seed,selector.identities if owner==1 else None);cursors[owner]=0
            t=time.monotonic();frame=AW.encode_initial(state);replicas[owner]=AW.decode_initial(frame)
            ledger.record('statistical_complete','af_initial_fixed_state',0,owner,frame,time.monotonic()-t,fields=('mean','internal_threshold','inverse_covariance','scaler_min','scaler_denominator'))
        expected=sum(len(s.X) for s in stores.values())
        r.update(expected_worker_rows=expected,expected_worker_windows=sum((len(s.X)+255)//256 for s in stores.values()),
                 expected_rounds=max((len(s.X)+255)//256 for s in stores.values()),
                 worker_rows_by_owner={str(o):len(s.X) for o,s in stores.items()},
                 worker_order_sha256={str(o):R.identity_digest(stores[o].identities[i] for i in orders[o]) for o in R.OWNERS})
        logs=out/'rounds.jsonl'
        with logs.open('x') as stream:
            while any(cursors[o]<len(orders[o]) for o in R.OWNERS):
                budget.check();progress.update(phase='af_round',round=state.round_id,worker_rows=worker_rows,rounds=rounds)
                t_round=time.monotonic();updates=[];permits=[];statuses=[]
                for owner in R.OWNERS:
                    budget.check();begin=cursors[owner];end=min(begin+256,len(orders[owner]));indices=orders[owner][begin:end]
                    if begin==end:statuses.append({'owner':owner,'status':'exhausted' if len(orders[owner]) else 'empty_worker','rows':0});continue
                    batch=R.adapt(stores[owner],indices,scope)
                    for ref in batch.refs:
                        key=ref.source_id,ref.source_row;B.require(key not in seen,'af_anchor_worker_overlap');seen.add(key)
                    progress.update(owner=owner,active_rows_attempted=len(indices));permit=A.authorize(batch,state);summary=A.summarize(batch,replicas[owner])
                    t=time.monotonic();frame=AW.encode_summary(summary,73);rebuilt=AW.decode_summary(frame,73)
                    B.require(AW.encode_summary(rebuilt,73)==frame,'af_summary_roundtrip')
                    ledger.record('statistical_complete','af_summary',owner,0,frame,time.monotonic()-t,round_id=state.round_id,
                        fields=('accepted_mean','accepted_count','dispersion_mad','threshold_candidate','permit'))
                    permits.append(permit);updates.append(rebuilt);cursors[owner]=end;worker_rows+=len(indices);worker_windows+=1
                    statuses.append({'owner':owner,'status':summary.status,'rows':len(indices)})
                budget.check();current,audit=A.merge(state,context,updates,permits);visits+=audit['anchor_rows_rescored']
                for owner in R.OWNERS:
                    t=time.monotonic();frame=AW.encode_delta(state,current);replicas[owner]=AW.apply_delta(replicas[owner],frame)
                    ledger.record('statistical_complete','af_later_state',0,owner,frame,time.monotonic()-t,round_id=current.round_id,fields=('mean','internal_threshold','identity'))
                rounds+=1;state=current;audit.update(seconds=time.monotonic()-t_round,schedule_statuses=statuses)
                line=json.dumps(audit,sort_keys=True)+'\n';stream.write(line);stream.flush();budget.storage_bytes+=len(line.encode());budget.check()
                r.update(rows_completed=worker_rows,rounds=rounds,worker_windows=worker_windows,postinitial_anchor_visits=visits)
                if rounds%64==0:save()
                if rounds%64==0:budget.refresh_storage(out.parent)
        B.require(worker_rows==expected and worker_windows==r['expected_worker_windows'] and rounds==r['expected_rounds']
                  and len(seen)==dataset.summary['rows_by_role']['train']==expected+anchor_count,'af_full_train_coverage')
        F.write(out/'FINAL-STATE.json',state.payload(),budget)
        # No attack-label choice: the source-reference ridge remains designated.
        scorer=F.freeze_af(dataset,state);F.write(out/'SCORER.json',B.loads(scorer.data),budget)
        reports=[]
        r.update(training_status='complete',validation_expected_scores=dataset.summary['rows_by_role']['validation'],validation_valid_scores=0)
        for owner in R.OWNERS:
            progress.update(phase='af_fixed_validation',owner=owner)
            record=F.evaluate_af_owner(dataset,scorer,owner,budget)
            reports.append(record);r['validation_valid_scores']+=record['valid_scores']
            F.write(out/f'validation-owner{owner}.json',record,budget);save()
        F.write(out/'METRICS.json',{'owner_metrics':reports,'source_reference_ridge':.001,'best_of_sensitivity_selection':False},budget)
        r['validation_missing_scores']=r['validation_expected_scores']-r['validation_valid_scores']
        B.require(r['validation_missing_scores']==0,'af_validation_coverage')
        r.update(status='complete_af_sensitivity_fit',finished_utc=now(),elapsed_seconds=time.monotonic()-tick,
                 final_state_id=state.state_id,validation_status='complete_fixed_validation',calibration_or_final_operation=False)
        save();return r
    except BaseException as exc:
        r.update(status='budget_limited' if isinstance(exc,F.BudgetExceeded) else 'failed_af_fit',finished_utc=now(),elapsed_seconds=time.monotonic()-tick,
            error_type=type(exc).__name__,error=str(exc),rows_completed=worker_rows,rounds=rounds,worker_windows=worker_windows,
            postinitial_anchor_visits=visits,partial_progress=dict(progress))
        if state is not None:F.write(out/'PARTIAL-STATE.json',state.payload())
        if isinstance(exc,F.ValidationFailure):
            r['active_validation']=exc.receipt
            r['validation_missing_scores']=r['validation_expected_scores']-r['validation_valid_scores']-exc.receipt['valid_scores']
            if exc.receipt['error_type']=='BudgetExceeded':r['status']='budget_limited'
        F.write(out/'FAILED.json',r);save()
        if not isinstance(exc,Exception):raise
        return r


def run_af(dataset,output,*,synthetic_only=False,anchor_count=2000,seeds=(20261112,20261113),ridges=(.001,.0001,.01),max_seconds=5400):
    B.require(type(dataset) is PurposeDataset and not sys.flags.optimize,'sealed_dataset_and_checked_python_required')
    if not synthetic_only:B.require(anchor_count==2000 and seeds==(20261112,20261113) and ridges==(.001,.0001,.01) and max_seconds==5400,'af_fixed_schedule')
    out=B.root_path(output,exists=False);out.mkdir(parents=True,exist_ok=False)
    budget=F.Budget(max_seconds,2**30);ledger=Ledger(out,budget);progress={};fits=[];stop=False
    r={'version':F.VERSION,'status':'running','started_utc':now(),'anchor_count':anchor_count,'seeds':seeds,'ridges':ridges,'fits':fits,
       'synthetic_only':synthetic_only,'scope':D.training_scope(dataset).scope_id,'source':L.code_context(),
       'input_pins':dataset.summary['input_sha256'],'assignment_sha256':dataset.summary['assignment_sha256'],
       'prepared_artifacts':dataset.summary['artifacts'],'features':list(dataset.features),
       'runner_sources':{p.name:L.sha(p) for p in Path(__file__).parent.glob('*.py')},'lock_sha256':L.sha(Path(__file__).parents[1]/'uv.lock'),
       'hardware':{'platform':platform.platform(),'machine':platform.machine()},
       'framework':{'python':platform.python_version(),'numpy':np.__version__,'torch':torch.__version__},
       'timing_boundary':'stage output creation through cold fit preparation,full worker traversal,validation and stored trial receipts; terminal seal hashing/writes and caller source-hash/seal-opening costs recorded outside',
       'source_reference_ridge':.001,'sensitivity_selection':'none; never best-of-six attack-label optimum','calibration_or_final_operation':False}
    def coverage():
        r['validation_expected_scores']=len(seeds)*len(ridges)*dataset.summary['rows_by_role']['validation']
        r['validation_valid_scores']=sum(q.get('validation_valid_scores',0) for q in fits)
        r['validation_generated_scores_including_active']=sum(q.get('validation_valid_scores',0)+q.get('active_validation',{}).get('valid_scores',0) for q in fits)
        r['validation_missing_scores']=r['validation_expected_scores']-r['validation_generated_scores_including_active']
    coverage()
    try:
        torch.set_num_threads(2)
        with threadpool_limits(limits=2):
            r['thread_control']={'torch':torch.get_num_threads(),'pools':threadpool_info(),
              'environment':{n:os.environ.get(n) for n in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','VECLIB_MAXIMUM_THREADS')}}
            for seed in seeds:
                for ridge in ridges:
                    if stop:fits.append({'seed':seed,'ridge':ridge,'status':'not_started_stage_budget_exhausted'});continue
                    trial=run_af_trial(dataset,seed,ridge,anchor_count,out/f'fit-{len(fits):02}',budget,ledger,progress)
                    fits.append(trial);stop=trial['status']=='budget_limited';coverage();F.write(out/'STAGE.json',r|{'budget':budget.receipt(),'active':progress})
        coverage()
        r.update(status='complete_finite_af_stage' if all(q['status']=='complete_af_sensitivity_fit' for q in fits) else 'budget_limited' if stop else 'af_stage_with_failed_fits',
           finished_utc=now(),budget=budget.receipt(),peak_process_rss_bytes=F.peak_rss_bytes(),message_counts=dict(ledger.counts),application_bytes=dict(ledger.bytes))
        F.write(out/'STAGE.json',r)
        budget.refresh_storage(out,enforce=r['status']=='complete_finite_af_stage')
        r['budget']=budget.receipt();F.write(out/'STAGE.json',r)
        if r['status']=='complete_finite_af_stage':seal(out,r['status'],budget)
        else:F.write(out/'INCOMPLETE.json',r)
        return r
    except BaseException as exc:
        coverage()
        r.update(status='budget_limited' if isinstance(exc,F.BudgetExceeded) else 'failed_finite_af_stage',error_type=type(exc).__name__,error=str(exc),budget=budget.receipt(),active=progress)
        F.write(out/'FAILED.json',r);raise


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--synthetic',action='store_true',required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    from synthetic_workload_fixture import prepared_fixture
    with tempfile.TemporaryDirectory(prefix='fabricated-finite-development-') as tmp:
        ds=prepared_fixture(Path(tmp).resolve()/'source',small=True)
        plan=Plan(stage='fabricated',grid=(F.OptimizerSpec('Adam',.001),),seeds=(41,42),checkpoints=(1,2),max_seconds=120)
        r=run_neural(ds,plan,args.output,synthetic_only=True)
    print(json.dumps({'status':r['status'],'trials':len(r['trials']),'actual_sources_opened':False}))


if __name__=='__main__':main()
