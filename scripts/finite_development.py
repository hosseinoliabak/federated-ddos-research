"""Finite development contracts, immutable CSV scorers and isolated selectors.

This is a new experiment version. The old fixed-pass runner/bundle is unchanged.
There is no calibration, final-source or arbitrary-role operation in this module.
"""
from dataclasses import dataclass, asdict
from pathlib import Path
import base64
import hashlib
import math
import os
import resource
import time
import numpy as np
import torch
from sklearn.metrics import roc_auc_score, average_precision_score
import afbkm_adapter_v2 as A
import frozen_model_bundle as B
import run_matched_workload as R
import workload_messages as M
import train_separability_diagnostic as D
from purpose_data_view import immutable, observer, UnlabeledBatch

VERSION = 'finite-development-v3'
SCORER_VERSION = 'finite-neural-csv-v3'
ANCHOR_SELECTION_VERSION = 'finite-development-v2'
ARCHITECTURES = ((16,), (64, 128, 64))
ARMS = ('independent_local', 'pooled_central', 'fedavg')


@dataclass(frozen=True)
class OptimizerSpec:
    name: str
    learning_rate: float

    def validate(self):
        B.require(self.name in {'SGD', 'Adam'} and type(self.learning_rate) is float
                  and math.isfinite(self.learning_rate) and self.learning_rate > 0, 'optimizer_spec')

    def configuration(self):
        self.validate()
        q = {'optimizer': self.name, 'learning_rate': self.learning_rate, 'weight_decay': 0,
             'foreach': False, 'fused': False, 'maximize': False, 'differentiable': False}
        return q | ({'momentum': 0, 'dampening': 0, 'nesterov': False} if self.name == 'SGD' else
                    {'betas': [0.9, 0.999], 'eps': 1e-8, 'amsgrad': False, 'capturable': False,
                     'decoupled_weight_decay': False})

    def make(self, model):
        self.validate()
        if self.name == 'SGD':
            return torch.optim.SGD(model.parameters(), lr=self.learning_rate, momentum=0,
                                   weight_decay=0, foreach=False, fused=False)
        return torch.optim.Adam(model.parameters(), lr=self.learning_rate, betas=(0.9, 0.999),
                                eps=1e-8, weight_decay=0, amsgrad=False, foreach=False,
                                fused=False, decoupled_weight_decay=False)


GRID = tuple(OptimizerSpec(name, rate) for name, rates in
             [('SGD', (0.001, 0.01, 0.1)), ('Adam', (0.0001, 0.001, 0.01))] for rate in rates)


class BudgetExceeded(RuntimeError):
    pass


class Budget:
    """Measured wall/application/storage ceilings; checks run at safe boundaries."""
    def __init__(self, seconds, parameter_bytes, raw_bytes=3 * 2**30, storage_bytes=20 * 2**30):
        B.require(all(type(v) is int and v >= 0 for v in (seconds, parameter_bytes, raw_bytes, storage_bytes)), 'budget_configuration')
        self.started = time.monotonic()
        self.seconds, self.parameter_cap, self.raw_cap, self.storage_cap = seconds, parameter_bytes, raw_bytes, storage_bytes
        self.parameter_bytes = self.raw_bytes = self.storage_bytes = 0

    def check(self):
        for ok, reason in ((time.monotonic() - self.started <= self.seconds, 'wall_time'),
                           (self.parameter_bytes <= self.parameter_cap, 'parameter_summary_bytes'),
                           (self.raw_bytes <= self.raw_cap, 'pooled_raw_bytes'),
                           (self.storage_bytes <= self.storage_cap, 'artifact_storage_bytes')):
            if not ok: raise BudgetExceeded(reason)

    def charge_message(self, n, *, raw=False):
        B.require(type(n) is int and n >= 0, 'message_byte_count')
        if raw: self.raw_bytes += n
        else: self.parameter_bytes += n
        self.check()

    def receipt(self):
        return {'elapsed_monotonic_seconds': time.monotonic() - self.started,
                'max_seconds': self.seconds, 'parameter_summary_bytes': self.parameter_bytes,
                'max_parameter_summary_bytes': self.parameter_cap, 'pooled_raw_bytes': self.raw_bytes,
                'max_pooled_raw_bytes': self.raw_cap, 'artifact_bytes_written': self.storage_bytes,
                'max_artifact_bytes': self.storage_cap,
                'overshoot_policy': 'stop at next completed batch/message/round or write boundary; no shortened tail counted complete'}

    def refresh_storage(self,root,*,enforce=True):
        self.storage_bytes=sum(p.stat().st_size for p in Path(root).rglob('*') if p.is_file())
        if enforce:self.check()


def write(path, obj, budget=None):
    data = A.canonical(obj)
    path = Path(path)
    previous = path.stat().st_size if path.exists() else 0
    path.write_bytes(data)
    if budget is not None:
        budget.storage_bytes += len(data) - previous
        budget.check()


def peak_rss_bytes(value=None, system=None):
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss if value is None else value
    system = os.sys.platform if system is None else system
    B.require(system in {'darwin', 'linux'}, 'rss_platform_not_supported')
    return int(value) * (1 if system == 'darwin' else 1024)


def architecture(hidden):
    B.require(type(hidden) is tuple and hidden in ARCHITECTURES, 'neural_architecture')
    return hidden


def template(hidden=(16,)):
    architecture(hidden)
    layers = []
    widths = (73,) + hidden + (1,)
    for i, (before, after) in enumerate(zip(widths, widths[1:])):
        layers.append(torch.nn.Linear(before, after, device='cpu', dtype=torch.float32))
        if i < len(widths) - 2: layers.append(torch.nn.ReLU())
    return torch.nn.Sequential(*layers)


def shapes(hidden):
    architecture(hidden)
    widths = (73,) + hidden + (1,)
    return {str(2 * i) + suffix: shape for i, (before, after) in enumerate(zip(widths, widths[1:]))
            for suffix, shape in (('.weight', (after, before)), ('.bias', (after,)))}


def state_id(state):
    h = hashlib.sha256()
    for key, value in state.items():
        h.update(A.canonical([key, value.dtype.str, list(value.shape)])); h.update(value.tobytes())
    return h.hexdigest()


def validate_state(state, hidden):
    expected = shapes(hidden)
    B.require(type(state) is dict and tuple(state) == tuple(expected), 'neural_state_blocks')
    B.require(all(type(v) is np.ndarray and v.shape == expected[k] and v.dtype == np.dtype('<f4')
                  and bool(np.isfinite(v).all()) for k, v in state.items()), 'neural_state_arrays')


def snapshot(model):
    return {k: immutable(v.detach().cpu().numpy()) for k, v in model.state_dict().items()}


def clone(state, hidden):
    validate_state(state, hidden)
    with torch.random.fork_rng(devices=[]): model = template(hidden)
    model.load_state_dict({k: torch.from_numpy(v.copy()) for k, v in state.items()}, strict=True)
    B.require(state_id(snapshot(model)) == state_id(state), 'clone_state_identity')
    return model


def packed_array(a,*,allow_nonfinite=False):
    B.require(isinstance(a, np.ndarray) and a.dtype.str in {'<f4', '<f8'}
              and a.ndim <= 2 and (allow_nonfinite or bool(np.isfinite(a).all())), 'checkpoint_array')
    return {'dtype': a.dtype.str, 'shape': list(a.shape), 'base64': base64.b64encode(a.tobytes()).decode('ascii')}


def unpacked_array(q):
    B.keys(q, {'dtype', 'shape', 'base64'})
    B.require(q['dtype'] in {'<f4', '<f8'} and type(q['shape']) is list and len(q['shape']) <= 2
              and all(type(n) is int and 0 <= n <= 100000 for n in q['shape'])
              and type(q['base64']) is str and len(q['base64']) < 4 * 2**20, 'checkpoint_array_header')
    raw = base64.b64decode(q['base64'], validate=True)
    B.require(len(raw) == math.prod(q['shape']) * np.dtype(q['dtype']).itemsize, 'checkpoint_array_size')
    a = np.frombuffer(raw, dtype=q['dtype']).reshape(q['shape'])
    B.require(bool(np.isfinite(a).all()), 'checkpoint_nonfinite')
    return a


def pack_tree(value,*,allow_nonfinite=False):
    """JSON-only optimizer state; no pickle loader is introduced."""
    if isinstance(value, torch.Tensor): return {'tensor': packed_array(value.detach().cpu().numpy(),allow_nonfinite=allow_nonfinite)}
    if type(value) is dict: return {'mapping': [[k, pack_tree(v,allow_nonfinite=allow_nonfinite)] for k, v in value.items()]}
    if type(value) in {tuple, list}: return {'sequence': [pack_tree(v,allow_nonfinite=allow_nonfinite) for v in value]}
    B.require(value is None or type(value) in {str, int, float, bool}, 'optimizer_state_type')
    if type(value) is float: B.require(math.isfinite(value), 'optimizer_state_nonfinite')
    return {'scalar': value}


def unpack_tree(q):
    B.require(type(q) is dict and len(q) == 1, 'optimizer_state_encoding')
    if 'tensor' in q: return torch.from_numpy(unpacked_array(q['tensor']).copy())
    if 'mapping' in q:
        B.require(type(q['mapping']) is list and all(type(p) is list and len(p) == 2 for p in q['mapping']), 'optimizer_mapping')
        result = {}
        for k, v in q['mapping']:
            B.require(type(k) in {str, int} and k not in result, 'optimizer_mapping_key'); result[k] = unpack_tree(v)
        return result
    if 'sequence' in q: return [unpack_tree(v) for v in q['sequence']]
    B.keys(q, {'scalar'}); pack_tree(q['scalar']); return q['scalar']


def model_frame(state, hidden, meta):
    """Parameter-only general-architecture frame; no raw/label block accepted."""
    validate_state(state, hidden)
    B.keys(meta, {'scope', 'trial', 'owner', 'round', 'count', 'parent'})
    for k in ('scope', 'parent'): B.hex_id(meta[k])
    for k in ('trial', 'owner', 'round', 'count'): B.integer(meta[k])
    B.require(meta['owner'] <= 10, 'model_frame_owner')
    return A.canonical({'version': VERSION, 'kind': 'neural_parameter', 'hidden': list(hidden),
        'meta': meta, 'state_id': state_id(state), 'arrays': {k: packed_array(v) for k, v in state.items()}})


def decode_model(data, hidden, expected_meta):
    B.require(type(data) is bytes and len(data) <= 2 * 2**20, 'model_frame_size')
    q = B.loads(data)
    B.keys(q, {'version', 'kind', 'hidden', 'meta', 'state_id', 'arrays'})
    B.require(q['version'] == VERSION and q['kind'] == 'neural_parameter' and q['hidden'] == list(hidden)
              and q['meta'] == expected_meta, 'model_frame_binding')
    # Canonical JSON sorts keys; restore the prescribed model-block order.
    B.require(set(q['arrays']) == set(shapes(hidden)), 'model_frame_blocks')
    state = {k: unpacked_array(q['arrays'][k]) for k in shapes(hidden)}
    validate_state(state, hidden)
    B.require(state_id(state) == q['state_id'] and model_frame(state, hidden, expected_meta) == data, 'model_frame_identity')
    return state


@dataclass(frozen=True)
class FrozenNeural:
    data: bytes
    scorer_id: str

    def __post_init__(self): self.validate()

    def validate(self):
        B.require(type(self.data) is bytes and len(self.data) <= 2 * 2**20 and B.sha(self.data) == self.scorer_id, 'finite_scorer_hash')
        q = B.loads(self.data)
        B.keys(q, {'version', 'schema', 'input_id', 'scope', 'hidden', 'owner', 'recipients', 'state_id', 'state', 'transform'})
        B.require(q['version'] == SCORER_VERSION and A.canonical(q) == self.data, 'finite_scorer_version')
        B.require(B.validate_schema(q['schema']) == q['input_id'], 'finite_scorer_schema')
        B.hex_id(q['scope']); B.integer(q['owner'])
        B.require(q['owner'] <= 10 and q['recipients'] == ([q['owner']] if q['owner'] else list(R.OWNERS)), 'finite_scorer_recipient')
        hidden = tuple(q['hidden']); architecture(hidden)
        B.require(set(q['state']) == set(shapes(hidden)), 'finite_scorer_blocks')
        state = {k: unpacked_array(q['state'][k]) for k in shapes(hidden)}; validate_state(state, hidden)
        B.require(state_id(state) == q['state_id'], 'finite_scorer_state')
        t = q['transform']; B.keys(t, {'mean', 'denominator'})
        mean, denominator = (unpacked_array(t[k]) for k in ('mean', 'denominator'))
        B.require(mean.dtype == denominator.dtype == np.dtype('<f8') and mean.shape == denominator.shape == (73,)
                  and bool((denominator > 0).all()), 'finite_scorer_transform')
        return q, state, mean, denominator

    def predict(self, X, *, feature_names, input_id, observer_id):
        q, state, mean, denominator = self.validate()
        B.require(type(observer_id) is int and observer_id in q['recipients'], 'finite_scorer_owner')
        B.require(type(feature_names) is tuple and list(feature_names) == q['schema']['features'] and input_id == q['input_id'], 'finite_scorer_input')
        B.require(type(X) is np.ndarray and X.dtype == np.dtype('<f8') and X.ndim == 2 and X.shape[1] == 73
                  and bool(np.isfinite(X).all()), 'finite_scorer_predictors')
        model = clone(state, tuple(q['hidden'])).eval()
        with torch.inference_mode():
            z = model(torch.from_numpy(M.standardize(X, mean, denominator))).squeeze(1)
            B.require(bool(torch.isfinite(z).all()), 'nonfinite_logit')
            return immutable(torch.sigmoid(z).numpy()), immutable(z.numpy())


def freeze(dataset, state, hidden, owner, mean, denominator):
    validate_state(state, hidden)
    schema = B.csv_schema(dataset.features, dataset.summary['input_sha256']['registry'])
    q = {'version': SCORER_VERSION, 'schema': schema, 'input_id': B.validate_schema(schema),
         'scope': D.training_scope(dataset).scope_id, 'hidden': list(hidden), 'owner': owner,
         'recipients': [owner] if owner else list(R.OWNERS), 'state_id': state_id(state),
         'state': {k: packed_array(v) for k, v in state.items()},
         'transform': {'mean': packed_array(mean), 'denominator': packed_array(denominator)}}
    data = A.canonical(q); return FrozenNeural(data, B.sha(data))


def scorer_delivery(scorer,meta):
    """Explicit parameter/transform/input-contract delivery to one client."""
    B.require(type(scorer) is FrozenNeural,'checkpoint_scorer_required');q=scorer.validate()[0]
    B.keys(meta,{'scope','trial','seed','grid','checkpoint','arm','recipient'})
    B.require(meta['scope']==q['scope'] and meta['arm'] in {'pooled_central','fedavg'} and
              type(meta['recipient']) is int and meta['recipient'] in q['recipients'],'scorer_delivery_scope')
    for k in ('trial','seed','grid','checkpoint'):B.integer(meta[k])
    return A.canonical({'version':VERSION,'kind':'checkpoint_scorer','meta':meta,'scorer_id':scorer.scorer_id,'payload':q})


def receive_scorer(data,expected_meta):
    """Client receives only the serialized scorer, never the coordinator object."""
    B.require(type(data) is bytes and len(data)<=3*2**20,'scorer_delivery_size')
    q=B.loads(data);B.keys(q,{'version','kind','meta','scorer_id','payload'})
    B.require(q['version']==VERSION and q['kind']=='checkpoint_scorer' and q['meta']==expected_meta,'scorer_delivery_binding')
    scorer=FrozenNeural(A.canonical(q['payload']),q['scorer_id'])
    B.require(scorer_delivery(scorer,expected_meta)==data,'scorer_delivery_encoding')
    return scorer


def rank_metrics(y, scores):
    B.require(type(y) is np.ndarray and type(scores) is np.ndarray and y.ndim == scores.ndim == 1
              and len(y) == len(scores) and bool(np.isin(y, [0, 1]).all()) and bool(np.isfinite(scores).all()), 'rank_inputs')
    n = len(y); p = int((y == 1).sum()); unique, counts = np.unique(scores, return_counts=True)
    largest = int(counts.max()) if n else 0
    return {'rows': n, 'benign': n - p, 'attack': p, 'rank_status': 'complete' if p and n-p else 'NA_class_support',
            'auroc': float(roc_auc_score(y, scores)) if p and n-p else None,
            'average_precision': float(average_precision_score(y, scores)) if p and n-p else None,
            'unique_scores': len(unique), 'largest_tie_group': largest,
            'tie_fraction': largest/n if n else None, 'constant_scores': bool(n and len(unique) == 1),
            'majority_tie': bool(n and largest/n > .5), 'exact_zero_scores': int((scores == 0).sum()),
            'exact_one_scores': int((scores == 1).sum()),
            'warning_scope': 'descriptive ties/endpoints; neither proof of numerical saturation nor exclusion from valid AUC/AP',
            'classification_threshold': None, 'recall': None, 'fpr': None}


@dataclass(frozen=True)
class FrozenAF:
    data: bytes
    scorer_id: str

    def __post_init__(self): self.validate()

    def validate(self):
        B.require(type(self.data) is bytes and len(self.data)<=2*2**20 and B.sha(self.data)==self.scorer_id,'af_scorer_hash')
        q=B.loads(self.data);B.keys(q,{'version','schema','input_id','scope','state','state_id','fixed_id','round','recipients'})
        B.require(q['version']=='finite-af-csv-v3' and A.canonical(q)==self.data and
                  B.validate_schema(q['schema'])==q['input_id'] and q['recipients']==list(R.OWNERS),'af_scorer_metadata')
        B.require(type(q['round']) is int and q['round']>0,'positive_final_af_round_required')
        state=B.decode_final_af(A.canonical(q['state']),expected_state_id=q['state_id'],expected_fixed_id=q['fixed_id'],expected_round=q['round'])
        B.require(state.scope_id==q['scope'],'af_scorer_scope');return q,state

    def score(self,X,*,feature_names,input_id,observer_id):
        q,state=self.validate();observer(observer_id)
        B.require(observer_id in q['recipients'] and type(feature_names) is tuple and list(feature_names)==q['schema']['features']
                  and input_id==q['input_id'],'af_scorer_input')
        B.require(type(X) is np.ndarray and X.dtype==np.dtype('<f8') and X.ndim==2 and X.shape[1]==73
                  and bool(np.isfinite(X).all()),'af_scorer_predictors')
        scores=A.score(X,state)
        B.require(scores.shape==(len(X),) and bool(np.isfinite(scores).all()) and bool((scores>=0).all()),'af_score_invalid')
        return immutable(scores)


def freeze_af(dataset,state):
    state.validate();schema=B.csv_schema(dataset.features,dataset.summary['input_sha256']['registry'])
    q={'version':'finite-af-csv-v3','schema':schema,'input_id':B.validate_schema(schema),'scope':D.training_scope(dataset).scope_id,
       'state':state.payload(),'state_id':state.state_id,'fixed_id':state.fixed_id,'round':state.round_id,'recipients':list(R.OWNERS)}
    data=A.canonical(q);return FrozenAF(data,B.sha(data))


class ValidationFailure(RuntimeError):
    def __init__(self, receipt, cause):
        self.receipt = receipt; super().__init__(str(cause))


def evaluate_af_owner(dataset,scorer,owner,budget,*,batch_rows=256):
    observer(owner);q,_=scorer.validate()
    B.require(q['scope']==D.training_scope(dataset).scope_id,'af_validation_scope')
    expected=D.support(dataset,'validation',owner);n=sum(expected.values());ids=[];parts=[]
    r={'owner':owner,'expected_rows':n,'valid_scores':0,'missing_scores':n,'invalid_returned_scores':0,
       'scorer_id':scorer.scorer_id,'live_eligible':False,'reporting_axis':'native_client_not_customer'}
    tick=time.monotonic()
    try:
        view=dataset.scoring('validation',owner,declaration_id='finite-af-development-v2',frozen_scorer_id=scorer.scorer_id)
        for batch in view.batches(batch_rows):
            budget.check();B.require(type(batch) is UnlabeledBatch,'af_inference_labels_forbidden')
            values=scorer.score(batch.X,feature_names=view.features,input_id=q['input_id'],observer_id=owner)
            bad=~np.isfinite(values)
            if bool(bad.any()):r['invalid_returned_scores']+=int(bad.sum());raise ValueError('nonfinite_af_score')
            B.require(values.shape==(len(batch.identities),) and bool((values>=0).all()),'af_score_shape_range')
            parts.append(values);ids.extend(batch.identities);r['valid_scores']+=len(values);r['missing_scores']=n-r['valid_scores'];budget.check()
        B.require(len(ids)==n and len({R.row_key(i) for i in ids})==n and all(i.observer_id==owner and i.role_id==1 for i in ids),'af_validation_coverage')
        y=view.reporting_labels(ids);B.require(D.labels(y,n)==(expected['benign'],expected['attack']),'af_validation_support')
        scores=np.concatenate(parts) if n else np.empty(0,dtype='<f8')
        r.update(rank_metrics(y,scores),status='complete_validation',identity_sha256=R.identity_digest(ids),
             score_sha256=B.sha(scores.tobytes()),ranking_representation='mahalanobis_float64',label_rows_examined=n,elapsed_seconds=time.monotonic()-tick,
             selection='none; source reference ridge remains designated')
        return r
    except BaseException as exc:
        r.update(status='failed_or_incomplete_validation',error_type=type(exc).__name__,error=str(exc),elapsed_seconds=time.monotonic()-tick)
        raise ValidationFailure(r,exc) from exc


def evaluate_owner(dataset, scorer, owner, budget, *, batch_rows=256):
    """Predictor-only scorer first; labels join only after full paired coverage."""
    observer(owner); q = scorer.validate()[0]
    B.require(owner in q['recipients'] and q['scope'] == D.training_scope(dataset).scope_id, 'validation_scope')
    expected = D.support(dataset, 'validation', owner); n = sum(expected.values()); ids = []; parts = []; logits = []
    r = {'owner': owner, 'expected_rows': n, 'valid_scores': 0, 'missing_scores': n, 'invalid_returned_scores': 0,
         'scorer_id': scorer.scorer_id, 'live_eligible': False, 'reporting_axis': 'native_client_not_customer'}
    tick = time.monotonic()
    try:
        view = dataset.scoring('validation', owner, declaration_id='finite-development-v2', frozen_scorer_id=scorer.scorer_id)
        for batch in view.batches(batch_rows):
            budget.check(); B.require(type(batch) is UnlabeledBatch, 'inference_labels_forbidden')
            scores, z = scorer.predict(batch.X, feature_names=view.features, input_id=q['input_id'], observer_id=owner)
            B.require(scores.shape == z.shape == (len(batch.identities),), 'score_shape')
            bad = ~(np.isfinite(scores) & np.isfinite(z))
            if bool(bad.any()): r['invalid_returned_scores'] += int(bad.sum()); raise ValueError('nonfinite_returned_score')
            B.require(bool(((scores >= 0) & (scores <= 1)).all()), 'sigmoid_score_range')
            parts.append(scores); logits.append(z); ids.extend(batch.identities)
            r['valid_scores'] += len(scores); r['missing_scores'] = n - r['valid_scores']; budget.check()
        B.require(len(ids) == n and len({R.row_key(i) for i in ids}) == n
                  and all(i.observer_id == owner and i.role_id == 1 for i in ids), 'validation_identity_coverage')
        y = view.reporting_labels(ids); B.require(D.labels(y, n) == (expected['benign'], expected['attack']), 'validation_support')
        scores = np.concatenate(parts) if n else np.empty(0, dtype='<f4')
        z = np.concatenate(logits) if n else np.empty(0, dtype='<f4')
        loss = torch.nn.functional.binary_cross_entropy_with_logits(torch.from_numpy(z.astype('<f8')),
                    torch.from_numpy(y.astype('<f8')), reduction='sum').item() if n else 0.0
        B.require(math.isfinite(loss) and loss >= 0, 'validation_loss_nonfinite')
        r.update(rank_metrics(y, scores), status='complete_validation', identity_sha256=R.identity_digest(ids),
                 loss_sum=loss, loss_count=n, mean_bce=loss/n if n else None,label_rows_examined=n,
                 score_sha256=B.sha(scores.tobytes()), logits_sha256=B.sha(z.tobytes()),
                 ranking_representation='sigmoid_float32', selection_representation='float32_logits_stable_BCE_float64_sum',
                 elapsed_seconds=time.monotonic()-tick)
        return r
    except BaseException as exc:
        r.update(status='failed_or_incomplete_validation', error_type=type(exc).__name__, error=str(exc), elapsed_seconds=time.monotonic()-tick)
        raise ValidationFailure(r, exc) from exc


def loss_message(record, *, scope, seed, grid, checkpoint, arm):
    B.require(record['status'] == 'complete_validation' and record['missing_scores'] == 0, 'incomplete_loss_message')
    q = {'version': VERSION, 'kind': 'validation_loss_sum_count', 'scope': scope, 'seed': seed,
         'grid': grid, 'checkpoint': checkpoint, 'arm': arm, 'owner': record['owner'],
         'count': record['loss_count'], 'expected_rows': record['expected_rows'], 'loss_sum': record['loss_sum'],
         'scorer_id': record['scorer_id'], 'identity_sha256': record['identity_sha256']}
    data = A.canonical(q); return data


def admit_loss_message(data, *, scope, seed, grid, checkpoint, arm, owner, expected_rows):
    B.require(type(data) is bytes and len(data) <= 4096, 'loss_message_size')
    q = B.loads(data)
    B.keys(q, {'version','kind','scope','seed','grid','checkpoint','arm','owner','count','expected_rows','loss_sum','scorer_id','identity_sha256'})
    B.require(q['version'] == VERSION and q['kind'] == 'validation_loss_sum_count' and A.canonical(q) == data
              and (q['scope'], q['seed'], q['grid'], q['checkpoint'], q['arm'], q['owner'], q['expected_rows']) ==
                  (scope, seed, grid, checkpoint, arm, owner, expected_rows), 'loss_message_binding')
    B.require(type(q['count']) is int and q['count'] == expected_rows and type(q['loss_sum']) in {float,int}
              and math.isfinite(q['loss_sum']) and q['loss_sum'] >= 0, 'loss_message_coverage')
    for k in ('scope','scorer_id','identity_sha256'): B.hex_id(q[k])
    return q


def choose(records, seeds, grids, checkpoints, *, owner):
    """A local selector is given exactly one owner's records, no shared fallback.

    Collective records have owner0 and contain only admitted sum/count messages.
    A candidate is eligible only when both continuous horizon trials completed.
    """
    B.require(type(owner) is int and 0 <= owner <= 10 and all(q['owner'] == owner for q in records), 'selection_owner_isolation')
    candidates = []
    for grid in range(grids):
        for checkpoint in checkpoints:
            selected = [r for r in records if r['grid'] == grid and r['checkpoint'] == checkpoint]
            eligible = len(selected) == len(seeds) and {r['seed'] for r in selected} == set(seeds) and all(
                r['status'] == 'complete_validation' and r['trial_complete'] and r['loss_count'] > 0
                and math.isfinite(r['loss_sum']) and r['missing_scores'] == 0 for r in selected)
            mean = sum(r['loss_sum']/r['loss_count'] for r in selected)/len(seeds) if eligible else None
            candidates.append({'grid': grid, 'checkpoint': checkpoint, 'eligible': eligible, 'mean_seed_bce': mean})
    eligible = [r for r in candidates if r['eligible']]
    best = min(eligible, key=lambda r: (r['mean_seed_bce'], r['checkpoint'], r['grid'])) if eligible else None
    return {'owner': owner, 'status': 'selected' if best else 'no_eligible_candidate', 'selection': best, 'candidates': candidates,
            'criterion': 'minimum mean own-validation BCE across seeds' if owner else 'minimum mean permitted union-validation BCE across seeds',
            'horizon_limit': 'checkpoint4 selection indicates tested horizon boundary, not demonstrated convergence',
            'no_threshold_calibration_or_final_operation': True}
