"""TRAIN-selected scalar control; acquired-data launch controller is not supplied.

Arp et al.2022 P4/P6 motivates an interpretable, simple control. Exact pair
counts implement this study's criterion, not an attribution of causation.
The CLI accepts only fabricated fixtures. No calibration/final API exists here.
"""
from dataclasses import dataclass
from pathlib import Path
import argparse
import hashlib
import json
import time
import numpy as np
from sklearn.metrics import roc_auc_score, average_precision_score
import afbkm_adapter_v2 as A
import frozen_model_bundle as B
import run_matched_workload as R
import workload_messages as M
from purpose_data_view import PurposeDataset, UnlabeledBatch

VERSION = 'train-scalar-control-v1'
MAX_INTEGER = 2**64 - 1


def pair_total(benign, attack):
    B.require(type(benign) is int and type(attack) is int and benign > 0 and attack > 0,
              'both_train_classes_required')
    result = 2 * benign * attack
    B.require(result <= MAX_INTEGER, 'pair_counter_range')
    return result


def labels(y, n):
    B.require(isinstance(y, np.ndarray) and y.shape == (n,) and y.dtype == np.dtype('u1')
              and bool(np.isin(y, [0, 1]).all()), 'scalar_labels')
    return int((y == 0).sum()), int((y == 1).sum())


def two_u(x, y):
    """Twice favorable benign/attack pair count, half-credit for exact ties.

    A positive pair contributes2 if x_attack>x_benign,1 at equality, otherwise0.
    Bounds are checked in Python integers before uint64 accumulation, whose
    total and individual nonnegative products cannot exceed2*n0*n1.
    """
    B.require(isinstance(x, np.ndarray) and x.ndim == 1 and x.dtype == np.dtype('<f8')
              and bool(np.isfinite(x).all()), 'scalar_feature')
    n0, n1 = labels(y, len(x)); total = pair_total(n0, n1)
    order = np.argsort(x, kind='stable'); sorted_x = x[order]
    starts = np.concatenate((np.asarray([0], dtype=np.int64),
                             np.flatnonzero(sorted_x[1:] != sorted_x[:-1]) + 1))
    ends = np.concatenate((starts[1:], np.asarray([len(x)], dtype=np.int64)))
    counts = (ends - starts).astype(np.uint64)
    attacks = np.add.reduceat(y[order], starts, dtype=np.uint64)
    benign = counts - attacks
    below = np.cumsum(benign, dtype=np.uint64) - benign
    value = int(np.sum(attacks * (2 * below + benign), dtype=np.uint64))
    B.require(0 <= value <= total, 'pair_count_invariant')
    return value, total


def select_feature(X, y):
    """Pure TRAIN computation; exact integer ties select the first field."""
    B.require(isinstance(X, np.ndarray) and X.ndim == 2 and X.shape[1] > 0
              and X.dtype == np.dtype('<f8') and bool(np.isfinite(X).all()), 'scalar_predictors')
    n0, n1 = labels(y, len(X))
    result = {'train_rows': len(X), 'benign': n0, 'attack': n1, 'criteria': []}
    if n0 == 0 or n1 == 0:
        return {**result, 'status': 'NA_train_class_support', 'selection': None}
    best = None
    for j in range(X.shape[1]):
        numerator, denominator = two_u(X[:, j], y)
        direction = 1 if 2 * numerator >= denominator else -1
        criterion = numerator if direction == 1 else denominator - numerator
        choice = {'feature_index': j, 'direction': direction, 'numerator': numerator,
                  'denominator': denominator, 'oriented_numerator': criterion}
        result['criteria'].append(choice)
        if best is None or criterion > best['oriented_numerator']: best = choice
    return {**result, 'status': 'selected_on_train', 'selection': best}


@dataclass(frozen=True)
class FrozenScalar:
    """Immutable self-contained CSV scalar definition; no labels at inference."""
    data: bytes
    expected_id: str

    def __post_init__(self): self.validate()

    @property
    def scorer_id(self): return self.expected_id

    def validate(self):
        B.require(type(self.data) is bytes and len(self.data) <= B.MAX_JSON, 'scalar_payload')
        B.hex_id(self.expected_id); B.require(B.sha(self.data) == self.expected_id, 'scalar_hash')
        q = B.loads(self.data)
        B.keys(q, {'version','schema','input_id','candidate_sha256','assignment_sha256','scope_id',
                   'owner','recipients','training_identity_sha256','train_rows','benign','attack','selection'})
        B.require(q['version'] == VERSION and A.canonical(q) == self.data, 'scalar_encoding_or_version')
        B.require(B.validate_schema(q['schema']) == q['input_id'], 'scalar_schema_identity')
        for k in ('candidate_sha256','assignment_sha256','scope_id','training_identity_sha256'): B.hex_id(q[k])
        B.integer(q['owner']); B.require(q['owner'] in range(11), 'scalar_owner')
        B.require(q['recipients'] == ([q['owner']] if q['owner'] else list(R.OWNERS)), 'scalar_recipients')
        for k in ('train_rows','benign','attack'): B.integer(q[k])
        total = pair_total(q['benign'],q['attack'])
        B.require(q['train_rows'] == q['benign'] + q['attack'], 'scalar_support')
        s = q['selection']; B.keys(s, {'feature_index','direction','numerator','denominator','oriented_numerator'})
        B.integer(s['feature_index']); B.integer(s['numerator']); B.integer(s['denominator']); B.integer(s['oriented_numerator'])
        B.require(s['feature_index'] < 73 and type(s['direction']) is int and s['direction'] in (-1,1)
                  and s['denominator'] == total and 0 <= s['numerator'] <= total, 'scalar_selection')
        direction = 1 if 2*s['numerator'] >= total else -1
        criterion = s['numerator'] if direction == 1 else total - s['numerator']
        B.require(s['direction'] == direction and s['oriented_numerator'] == criterion, 'scalar_direction')
        return q

    def score(self, X, *, feature_names, input_id, observer_id):
        q = self.validate()
        B.require(type(observer_id) is int and observer_id in q['recipients'], 'scalar_recipient')
        B.require(type(feature_names) is tuple and list(feature_names) == q['schema']['features']
                  and input_id == q['input_id'], 'scalar_input_schema')
        B.require(isinstance(X, np.ndarray) and X.ndim == 2 and X.shape[1] == 73
                  and X.dtype == np.dtype('<f8') and bool(np.isfinite(X).all()), 'scalar_predictors')
        scores = q['selection']['direction'] * X[:, q['selection']['feature_index']]
        B.require(bool(np.isfinite(scores).all()), 'scalar_nonfinite_score')
        return np.frombuffer(scores.tobytes(), dtype='<f8')


def training_scope(dataset):
    B.require(isinstance(dataset, PurposeDataset), 'sealed_purpose_dataset_required')
    return A.TrainingScope(dataset.summary['input_sha256']['candidate'], dataset.summary['assignment_sha256'],
        dataset.features, tuple((q['source_id'],q['sha256']) for q in dataset.summary['sources']))


def support(dataset, role, owner):
    selected = [q for q in dataset.summary['binary_support'] if q['role'] == role
                and (owner == 0 or q['client_id'] == owner)]
    return {c:sum(q[c] for q in selected) for c in ('benign','attack')}


def finish_fit(dataset, scope, owner, X, y, identities, receipt):
    expected = support(dataset,'train',owner)
    B.require(labels(y,len(X)) == (expected['benign'],expected['attack']), 'scalar_train_support')
    B.require(len(identities) == len(X) and len({R.row_key(r) for r in identities}) == len(X)
              and all(r.role_id == 0 and (owner == 0 or r.observer_id == owner) for r in identities), 'scalar_train_coverage')
    result = select_feature(X,y); receipt.update(result)
    receipt.update(training_identity_sha256=R.identity_digest(identities), predictor_transform='none_stored_values',
                   held_out_feature_or_label_selection=False, calibration_or_threshold=False)
    if result['selection'] is None: return None, receipt
    schema = B.csv_schema(dataset.features,dataset.summary['input_sha256']['registry'])
    payload = {'version':VERSION,'schema':schema,'input_id':B.validate_schema(schema),
        'candidate_sha256':scope.candidate_sha256,'assignment_sha256':scope.assignment_sha256,'scope_id':scope.scope_id,
        'owner':owner,'recipients':[owner] if owner else list(R.OWNERS),
        'training_identity_sha256':receipt['training_identity_sha256'],
        **{k:result[k] for k in ('train_rows','benign','attack','selection')}}
    data=A.canonical(payload); return FrozenScalar(data,B.sha(data)),receipt


def fit_local(dataset, owner):
    """Only this owner's supervised TRAIN view; no shared selector feedback."""
    from purpose_data_view import observer
    observer(owner); scope=training_scope(dataset); access=[]; tick=time.monotonic()
    store=R.stage(dataset.supervised_train(owner),256,access,'scalar_local')
    model,receipt=finish_fit(dataset,scope,owner,store.X,store.y,store.identities,
        {'scope':'independent_local','owner':owner,'access':access,'serialized_application_bytes':0})
    receipt['elapsed_seconds']=time.monotonic()-tick; return model,receipt


def fit_pooled(dataset):
    """Declared central raw TRAIN union; exact existing application roundtrips."""
    scope=training_scope(dataset); access=[]; received=[]; tick=time.monotonic(); moved=0; messages=0
    for owner in R.OWNERS:
        local=R.stage(dataset.supervised_train(owner),256,access,'scalar_permitted_pooled');chunks=[]
        for begin in range(0,len(local.X),256):
            end=min(begin+256,len(local.X));meta=R.meta(scope,'pooled_central',owner,end-begin)
            payload=M.encode('pooled_raw',meta,R.raw_arrays(local,begin,end))
            kind,header,arrays=M.decode(payload)
            B.require(kind=='pooled_raw' and header==meta and M.encode(kind,header,arrays)==payload,'scalar_raw_roundtrip')
            moved+=len(payload);messages+=1;chunks.append(arrays)
        central=R.received_store(owner,chunks)
        B.require(central.identities==local.identities and np.array_equal(central.X,local.X)
                  and np.array_equal(central.y,local.y),'scalar_pool_reconstruction')
        received.append(central)
    X=np.concatenate([s.X for s in received]);y=np.concatenate([s.y for s in received])
    identities=tuple(r for s in received for r in s.identities)
    model,receipt=finish_fit(dataset,scope,0,X,y,identities,
        {'scope':'permitted_pooled_raw_union','owner':0,'access':access,
         'serialized_application_bytes':moved,'serialized_messages':messages,
         'movement_boundary':'actual pooled_raw encode/decode bytes; no network packets/latency'})
    receipt['elapsed_seconds']=time.monotonic()-tick; return model,receipt


class DiagnosticFailure(ValueError):
    def __init__(self,receipt,cause):
        self.receipt=receipt;super().__init__('scalar_validation_failed: '+str(cause))


def evaluate_validation(dataset, scorer, owner, *, batch_rows=256):
    """Fixed selected scorer only; labels join outside inference after coverage."""
    B.require(isinstance(scorer,FrozenScalar),'frozen_scalar_required');q=scorer.validate()
    scope=training_scope(dataset)
    B.require(type(owner) is int and owner in q['recipients'],'scalar_recipient')
    B.require(q['scope_id']==scope.scope_id,'scalar_dataset_scope')
    expected=support(dataset,'validation',owner);n=sum(expected.values())
    view=dataset.scoring('validation',owner,declaration_id='frozen-scalar-diagnostic',frozen_scorer_id=scorer.scorer_id)
    receipt={'status':'running','owner':owner,'expected_rows':n,'valid_scores':0,'missing_scores':n,
             'invalid_returned_scores':0,'classification_threshold':None,'calibration':False,
             'score_representation':'signed_stored_float64','live_eligible':False}
    start=time.monotonic();ids=[];chunks=[]
    try:
        for batch in view.batches(batch_rows):
            B.require(isinstance(batch,UnlabeledBatch) and not hasattr(batch,'y'),'scalar_scoring_labels')
            scores=scorer.score(batch.X,feature_names=view.features,input_id=q['input_id'],observer_id=owner)
            B.require(scores.shape==(len(batch.identities),),'scalar_score_shape')
            if not bool(np.isfinite(scores).all()):
                receipt['invalid_returned_scores']+=int((~np.isfinite(scores)).sum());raise ValueError('scalar_invalid_returned_scores')
            chunks.append(scores);ids.extend(batch.identities);receipt['valid_scores']+=len(scores)
            receipt['missing_scores']=n-receipt['valid_scores']
        B.require(len(ids)==n and len({R.row_key(r) for r in ids})==n,'scalar_validation_coverage')
        y=view.reporting_labels(ids);B.require(labels(y,n)==(expected['benign'],expected['attack']),'scalar_validation_support')
        scores=np.concatenate(chunks) if chunks else np.empty(0,dtype='<f8')
        both=expected['benign']>0 and expected['attack']>0
        unique,counts=np.unique(scores,return_counts=True)
        receipt.update(status='complete_fixed_validation',**expected,identity_order_sha256=R.identity_digest(ids),
            auroc=float(roc_auc_score(y,scores)) if both else None,
            average_precision=float(average_precision_score(y,scores)) if both else None,
            rank_status='complete' if both else 'NA_class_support',score_unique_count=len(unique),
            largest_tie_group=int(counts.max()) if len(counts) else 0,
            recall=None,fpr=None,elapsed_seconds=time.monotonic()-start,
            boundary='after bundle/view setup through validation reads, predictor scoring, label join and ranking; no fit/threshold/selection')
        return receipt
    except BaseException as exc:
        receipt.update(status='failed_or_incomplete_validation',error_type=type(exc).__name__,error=str(exc),elapsed_seconds=time.monotonic()-start)
        raise DiagnosticFailure(receipt,exc) from exc


def synthetic_check():
    import tempfile
    from synthetic_workload_fixture import prepared_fixture
    with tempfile.TemporaryDirectory(prefix='fabricated-scalar-control-') as tmp:
        dataset=prepared_fixture(Path(tmp).resolve()/'source',small=True)
        local,lr=fit_local(dataset,1);pooled,pr=fit_pooled(dataset)
        B.require(local is not None and pooled is not None,'fabricated_missing_scorer')
        lv=evaluate_validation(dataset,local,1,batch_rows=3)
        pv=[evaluate_validation(dataset,pooled,owner,batch_rows=3) for owner in R.OWNERS]
        B.require(sum(q['valid_scores'] for q in pv)==dataset.summary['rows_by_role']['validation'],'fabricated_missing_tail')
        return {'status':'passed_fabricated_only','version':VERSION,'local_train_rows':lr['train_rows'],
                'pooled_train_rows':pr['train_rows'],'pooled_validation_rows':sum(q['valid_scores'] for q in pv),
                'pooled_serialized_application_bytes':pr['serialized_application_bytes'],'local_validation_rows':lv['valid_scores']}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--synthetic',action='store_true',required=True)
    parser.parse_args();print(json.dumps(synthetic_check(),sort_keys=True))
