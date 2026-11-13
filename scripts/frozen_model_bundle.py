"""CSV-only frozen inference/export. No raw-source path or calibration fitter.

Reuse the checked numerical/weight machinery. This trusted-code boundary does
not authenticate an unknown publisher or establish live metering equivalence.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import math
import os
import resource
import stat
import time
import numpy as np
import torch
import afbkm_adapter_v2 as A
import afbkm_wire_v2 as W
import workload_messages as M
import run_matched_workload as R
from purpose_data_view import PurposeDataset, PurposeView, UnlabeledBatch, immutable, observer

VERSION = 'frozen-csv-bundle-v1'
TRANSFORM_VERSION = 'train-transform-recovery-v1'
SCHEMA_VERSION = 'csv73-unverified-input-v1'
_LOAD_TOKEN = object()
MAX_JSON = 2 * 1024 * 1024
MAX_RUN_FILE = 512 * 1024 * 1024  # Parser bound, not a method resource allowance.
ARMS = {'independent_local', 'local_shared_moments', 'pooled_central', 'fedavg'}


def require(ok, reason):
    if not ok: raise ValueError(reason)


def sha(data): return hashlib.sha256(data).hexdigest()


def keys(obj, expected):
    require(type(obj) is dict and set(obj) == set(expected), 'bundle_keys')


def integer(value, minimum=0):
    require(type(value) is int and value >= minimum, 'bundle_integer')


def hex_id(value):
    require(type(value) is str and len(value) == 64 and all(c in '0123456789abcdef' for c in value), 'bundle_digest')


def loads(data):
    def unique(pairs):
        result = {}
        for k, v in pairs:
            require(k not in result, 'duplicate_json_key'); result[k] = v
        return result
    try:
        return json.loads(data, object_pairs_hook=unique,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite_json')))
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError('invalid_bundle_json') from exc


def root_path(directory, *, exists=True):
    p = Path(directory).absolute()
    # Artifact APIs never accept dataset or reserved-source directories.
    require(not any(s.casefold() in {'datasets', 'test', '03-11'} for s in p.parts), 'source_path_forbidden')
    require(p == p.resolve(strict=exists) and not p.is_symlink(), 'artifact_path_escape')
    if exists: require(p.is_dir(), 'artifact_directory')
    return p


def file_bytes(root, name, limit=MAX_JSON):
    require(type(name) is str and name not in {'.', '..'} and '/' not in name and '\\' not in name
            and name and not name.startswith('.'), 'artifact_name')
    p = root / name
    require(not p.is_symlink(), 'artifact_symlink')
    fd = os.open(p, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    with os.fdopen(fd, 'rb') as f:
        before = os.fstat(f.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_size <= limit, 'artifact_size_or_type')
        data = f.read(limit + 1); after = os.fstat(f.fileno())
        require(len(data) <= limit and (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
                == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), 'artifact_changed')
    return data


def put_json(path, value): path.write_bytes(A.canonical(value))


def seal(directory, names):
    files = {n: {'sha256': sha(file_bytes(directory, n, MAX_RUN_FILE)),
                 'bytes': (directory / n).stat().st_size} for n in names}
    payload = A.canonical({'version': VERSION, 'files': files})
    (directory / 'MANIFEST.json').write_bytes(payload)
    return sha(payload)


def open_seal(directory, expected, names=None):
    hex_id(expected); directory = root_path(directory)
    data = file_bytes(directory, 'MANIFEST.json'); require(sha(data) == expected, 'manifest_digest')
    obj = loads(data); keys(obj, {'version', 'files'})
    require(obj['version'] == VERSION and type(obj['files']) is dict, 'bundle_version')
    if names is not None: require(set(obj['files']) == set(names), 'manifest_files')
    else:
        supported = [
            {'scorer.json','input-schema.json','provenance.json','model.bin','preprocessing.json'},
            {'scorer.json','input-schema.json','provenance.json','af-state.json'},
            {'transforms.json','receipt.json'}]
        require(set(obj['files']) in supported, 'manifest_files')
    require(set(p.name for p in directory.iterdir()) == set(obj['files']) | {'MANIFEST.json'}, 'extra_artifact')
    result = {}
    for name, item in obj['files'].items():
        keys(item, {'sha256', 'bytes'}); hex_id(item['sha256']); integer(item['bytes'])
        value = file_bytes(directory, name, MAX_JSON)
        require(sha(value) == item['sha256'] and len(value) == item['bytes'], 'artifact_digest')
        result[name] = value
    return result


@dataclass(frozen=True)
class CompletedRun:
    directory: Path
    complete_sha256: str

    def read(self):
        root = root_path(self.directory); hex_id(self.complete_sha256)
        data = file_bytes(root, 'COMPLETE.json')
        require(sha(data) == self.complete_sha256, 'run_seal_digest')
        seal_obj = loads(data); keys(seal_obj, {'version', 'status', 'artifacts'})
        require(seal_obj['version'] == R.VERSION and seal_obj['status'] == 'complete_cost_pilot', 'incomplete_run')
        require(type(seal_obj['artifacts']) is dict and len(seal_obj['artifacts']) <= 200, 'run_artifacts')
        for name, item in seal_obj['artifacts'].items():
            keys(item, {'sha256', 'bytes'}); hex_id(item['sha256']); integer(item['bytes'])
            value = file_bytes(root, name, MAX_RUN_FILE)
            require(sha(value) == item['sha256'] and len(value) == item['bytes'], 'run_artifact_digest')
        summary = loads(file_bytes(root, 'summary.json', MAX_RUN_FILE))
        require(summary['status'] == 'complete_cost_pilot' and summary['version'] == R.VERSION, 'run_version')
        require(summary['features'] and len(summary['features']) == 73 and
                set(summary['arms']) == ARMS | {'statistical_complete'}, 'run_schema')
        return summary

    def checkpoint(self, name):
        self.read()  # Recheck completed evidence before an export.
        return file_bytes(root_path(self.directory), name)


def transform_payload(moments):
    moments.validate()
    return {'count': moments.count, 'mean': moments.mean.tolist(), 'M2': moments.M2.tolist(),
            'denominator': M.denominator(moments).tolist() if moments.count else None,
            'moment_id': A.digest([moments.mean.tolist(), moments.M2.tolist()])}


def validate_transform(obj, *, trained=True):
    keys(obj, {'count', 'mean', 'M2', 'denominator', 'moment_id'})
    integer(obj['count']); hex_id(obj['moment_id'])
    moments = M.Moments(obj['count'], np.asarray(obj['mean'], dtype='<f8'), np.asarray(obj['M2'], dtype='<f8'))
    expected = transform_payload(moments)
    require(A.canonical(expected) == A.canonical(obj), 'transform_values_or_digest')
    if trained: require(moments.count > 0, 'untrained_transform')
    return moments


def recover_train_transforms(dataset, completed, output):
    """Extra, charged TRAIN-only preprocessing pass. Does not fit/score a detector."""
    require(isinstance(dataset, PurposeDataset) and isinstance(completed, CompletedRun), 'sealed_dataset_and_run_required')
    out = root_path(output, exists=False); out.mkdir(parents=True, exist_ok=False)
    started = time.monotonic(); receipt = {'started_utc': datetime.now(timezone.utc).isoformat(), 'pid': os.getpid(),
        'python': os.sys.version, 'numpy': np.__version__, 'torch': torch.__version__,
        'torch_threads': torch.get_num_threads(), 'source_sha256': sha(Path(__file__).read_bytes()),
        'source_complete_sha256': completed.complete_sha256, 'status': 'running', 'rows': 0, 'attempted_rows': 0, 'owners': [],
        'boundary': 'extra recovery after output creation; includes run verification, TRAIN reads and transform writes, excludes prior dataset opening and original cost run',
        'held_out_model_operation': False, 'labels_read': False,
        'integrity_byte_reads': 'PurposeDataset seal opening may hash held-out prepared bytes; this fitter requests only unlabeled_train.'}
    try:
        run = completed.read()
        require(run['candidate_sha256'] == dataset.summary['input_sha256']['candidate'] and
                run['assignment_sha256'] == dataset.summary['assignment_sha256'] and
                run['features'] == list(dataset.features) and
                run['input_pins'] == dataset.summary['input_sha256'] and
                run['prepared_array_artifacts'] == dataset.summary['artifacts'], 'recovery_scope_mismatch')
        chunk = run['config']['batch_rows']; require(chunk == 256, 'unsupported_recovery_partition')
        union = M.empty_moments(); owners = {}
        for owner in R.OWNERS:
            tick = time.monotonic(); current = M.empty_moments()
            view = dataset.unlabeled_train(owner)
            require(type(view) is PurposeView and view.purpose == 'unlabeled_train' and
                    not view._excluded_anchor_indices, 'recovery_view')
            def identities():
                nonlocal current
                for batch in view.batches(chunk):
                    require(type(batch) is UnlabeledBatch, 'recovery_labels_forbidden')
                    require(all(r.observer_id == owner and r.role_id == 0 for r in batch.identities), 'recovery_ownership_or_role')
                    receipt['attempted_rows'] += len(batch.X)
                    current = M.merge_moments(current, M.fit_moments(batch.X, chunk))
                    receipt['rows'] += len(batch.X)
                    yield from batch.identities
            identity_sha = R.identity_digest(identities())
            obj = transform_payload(current)
            expected = run['arms']['independent_local']
            require(obj['moment_id'] == expected['local_moment_ids'][str(owner)] and
                    current.count == expected['clients'][owner - 1]['training_presentations'] and
                    expected['clients'][owner - 1]['owner'] == owner, 'recorded_local_transform_mismatch')
            owners[str(owner)] = obj
            union = M.merge_moments(union, current)
            receipt['owners'].append({'owner': owner, 'rows': current.count, 'identity_order_sha256': identity_sha,
                                      'seconds': time.monotonic() - tick})
        obj = transform_payload(union)
        require(union.count == run['rows_by_role']['train'] == receipt['rows'], 'recovery_count')
        require(all(obj['moment_id'] == run['arms'][arm]['global_moment_id'] for arm in
                    ('pooled_central', 'fedavg', 'local_shared_moments')), 'recorded_global_transform_mismatch')
        payload = {'version': TRANSFORM_VERSION, 'source_complete_sha256': completed.complete_sha256,
                   'candidate_sha256': run['candidate_sha256'], 'assignment_sha256': run['assignment_sha256'],
                   'features': run['features'], 'batch_rows': chunk, 'owners': owners, 'union': obj}
        put_json(out / 'transforms.json', payload)
        receipt.update(status='complete_train_transform_recovery', finished_utc=datetime.now(timezone.utc).isoformat(), elapsed_seconds=time.monotonic() - started,
                       peak_process_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss *
                          (1 if os.sys.platform == 'darwin' else 1024),
                       reconstruction_compute_not_original_training_time=True)
        put_json(out / 'receipt.json', receipt)
        return seal(out, ['transforms.json', 'receipt.json'])
    except BaseException as exc:
        receipt.update(status='failed_train_transform_recovery', finished_utc=datetime.now(timezone.utc).isoformat(), elapsed_seconds=time.monotonic() - started,
                       error_type=type(exc).__name__, error=str(exc))
        put_json(out / 'FAILED.json', receipt); raise


def csv_schema(features, registry_sha256):
    hex_id(registry_sha256)
    require(type(features) is tuple and len(features) == len(set(features)) == 73 and
            all(type(n) is str and 0 < len(n) <= 128 for n in features), 'input_features')
    return {'version': SCHEMA_VERSION, 'scope': 'stored_csv_only', 'live_eligible': False,
        'features': list(features), 'registry_sha256': registry_sha256, 'input_dtype': '<f8',
        'units': ['unverified_stored_release'] * 73, 'direction': 'unverified_provider_direction',
        'availability': 'unverified_original_release',
        'metering_policy': {'extractor': None, 'sampling': None, 'active_timeout': None, 'idle_timeout': None}}


def validate_schema(obj):
    keys(obj, {'version', 'scope', 'live_eligible', 'features', 'registry_sha256', 'input_dtype',
               'units', 'direction', 'availability', 'metering_policy'})
    expected = csv_schema(tuple(obj['features']), obj['registry_sha256'])
    require(A.canonical(expected) == A.canonical(obj), 'unsupported_input_semantics_or_live_schema')
    return A.digest(obj)


def decode_final_af(data, *, expected_state_id, expected_fixed_id, expected_round):
    obj = loads(data); keys(obj, W.STATE)
    require(obj['version'] == A.VERSION and A.canonical(obj) == data, 'af_version_or_encoding')
    keys(obj['parameters'], {'ridge', 'mad_k', 'blend', 'trust_k'})
    state = A.GlobalState(obj['model_id'], obj['round_id'], obj['scope_id'], obj['schema_id'],
        tuple(obj['features']), A.Parameters(**obj['parameters']),
        A.FrozenArray.of(obj['scaler_min']), A.FrozenArray.of(obj['scaler_denominator']),
        A.FrozenArray.of(obj['anchor_mean']), A.FrozenArray.of(obj['inverse_covariance']),
        A.FrozenArray.of(obj['mean']), obj['internal_threshold'], obj['anchor_id'])
    hex_id(expected_state_id); hex_id(expected_fixed_id); integer(expected_round)
    require(state.state_id == expected_state_id and state.fixed_id == expected_fixed_id and
            state.round_id == expected_round, 'af_final_state_or_round')
    return state


def scorer_identity(meta):
    return A.digest({k: meta[k] for k in ('family', 'arm', 'model_owner', 'recipients', 'input_id',
                                         'model_id', 'transform_id', 'source_complete_sha256', 'numeric_rule','training_scope_id','architecture')})


def export_bundle(completed, schema, output, *, arm, owner=0, transforms=None, transform_seal=None):
    """No fit or score. Neural transform recovery is a separate explicit operation."""
    require(isinstance(completed, CompletedRun), 'completed_run_required')
    input_id = validate_schema(schema); run = completed.read()
    require(schema['features'] == run['features'] and schema['registry_sha256'] == run['input_pins']['registry'], 'export_schema')
    require(arm in ARMS | {'statistical_complete'}, 'export_arm')
    local = arm in {'independent_local', 'local_shared_moments'}
    if local: observer(owner)
    else: require(type(owner) is int and owner == 0, 'global_model_owner')
    recipients = [owner] if local else list(R.OWNERS)
    meta = {'version': VERSION, 'use': 'csv_score_only', 'family': 'af' if arm == 'statistical_complete' else 'neural',
            'arm': arm, 'model_owner': owner, 'recipients': recipients, 'input_id': input_id,
            'source_complete_sha256': completed.complete_sha256, 'candidate_sha256': run['candidate_sha256'],
            'assignment_sha256': run['assignment_sha256'], 'customer_map': None, 'live_eligible': False,
            'feature_order_id': A.digest(run['features']), 'training_scope_id': A.TrainingScope(
                run['candidate_sha256'], run['assignment_sha256'], tuple(run['features']),
                tuple((q['source_id'], q['sha256']) for q in run['native_sources'])).scope_id}
    files = {'input-schema.json': A.canonical(schema)}
    if meta['family'] == 'neural':
        values = open_seal(transforms, transform_seal, {'transforms.json', 'receipt.json'})
        t = loads(values['transforms.json'])
        keys(t, {'version', 'source_complete_sha256', 'candidate_sha256', 'assignment_sha256', 'features', 'batch_rows', 'owners', 'union'})
        require(t['version'] == TRANSFORM_VERSION and t['source_complete_sha256'] == completed.complete_sha256 and
                t['features'] == run['features'] and t['candidate_sha256'] == run['candidate_sha256'] and
                t['assignment_sha256'] == run['assignment_sha256'] and t['batch_rows'] == 256, 'recovered_transform_scope')
        transform = t['owners'][str(owner)] if arm == 'independent_local' else t['union']
        validate_transform(transform)
        expected_count = (run['arms'][arm]['clients'][owner - 1]['training_presentations']
                          if arm == 'independent_local' else run['rows_by_role']['train'])
        require(transform['count'] == expected_count, 'export_transform_count')
        expected = (run['arms'][arm]['local_moment_ids'][str(owner)] if arm == 'independent_local'
                    else run['arms'][arm]['global_moment_id'])
        require(transform['moment_id'] == expected, 'export_transform_digest')
        name = f'{arm}-owner{owner}.bin' if local else f'{arm}-final.bin'
        payload = completed.checkpoint(name); kind, header, arrays = M.decode(payload)
        expected_model = (run['arms'][arm]['clients'][owner - 1]['final_state_id'] if local
                          else run['arms'][arm]['final_state_id'])
        require(kind == 'model' and header['arm'] == arm and header['owner'] == owner and
                header['round'] == 1 and header['schema'] == meta['feature_order_id'] and
                header['scope'] == meta['training_scope_id'] and header['parent'] == run['initial_neural_state_id'] and
                header['count'] == (run['arms'][arm]['clients'][owner - 1]['training_presentations'] if local else run['rows_by_role']['train']) and
                header['state'] == expected_model, 'export_model_scope')
        meta.update(model_id=M.model_digest(arrays), transform_id=A.digest(transform),
                    architecture='linear73_relu16_linear1', training_count=header['count'], initial_model_id=header['parent'], numeric_rule='float64_standardize_then_float32_logit_sigmoid')
        files.update({'model.bin': payload, 'preprocessing.json': A.canonical(transform)})
    else:
        require(transforms is None and transform_seal is None, 'af_external_transform_forbidden')
        af = run['arms'][arm]; payload = completed.checkpoint('statistical-complete-final.json')
        state = decode_final_af(payload, expected_state_id=af['final_state_id'], expected_fixed_id=af['fixed_state_id'], expected_round=len(af['rounds']))
        require(list(state.features) == run['features'] and state.scope_id == A.TrainingScope(
            run['candidate_sha256'], run['assignment_sha256'], tuple(run['features']),
            tuple((s['source_id'], s['sha256']) for s in run['native_sources'])).scope_id, 'af_scope')
        meta.update(model_id=state.state_id, transform_id=A.digest([state.scaler_min.values(), state.scaler_denominator.values()]),
                    fixed_id=state.fixed_id, final_round=state.round_id, architecture=A.VERSION,
                    numeric_rule='float64_fixed_anchor_minmax_mahalanobis', internal_threshold_use='training_provenance_only')
        files['af-state.json'] = payload
    meta['scorer_id'] = scorer_identity(meta)
    files['scorer.json'] = A.canonical(meta)
    files['provenance.json'] = A.canonical({'source_complete_sha256': completed.complete_sha256,
        'code': run['code'], 'framework': run['framework'], 'input_pins': run['input_pins'],
        'native_sources': run['native_sources'],
        'bundle_code': {'version':VERSION,'source_sha256':sha(Path(__file__).read_bytes()),
                        'numpy':np.__version__,'torch':torch.__version__},
        'preprocessing_role': 'train', 'customer_map': None,
        'transform_recovery_seal': transform_seal, 'extra_recovery_charged_separately': meta['family'] == 'neural'})
    out = root_path(output, exists=False); out.mkdir(parents=True, exist_ok=False)
    try:
        for name, data in files.items(): (out / name).write_bytes(data)
        bundle_id = seal(out, files)
        load_bundle(out, bundle_id)
        return bundle_id
    except BaseException as exc:
        put_json(out / 'FAILED.json', {'status': 'failed_export', 'error': str(exc)}); raise


class FrozenScorer:
    def __init__(self, metadata, schema, model_payload, transform=None, *, _token=None):
        require(_token is _LOAD_TOKEN, 'use_verified_bundle_loader')
        self._metadata = A.canonical(metadata); self._schema = A.canonical(schema)
        self._payload = bytes(model_payload); self._transform = None if transform is None else A.canonical(transform)

    @property
    def metadata(self): return loads(self._metadata)
    @property
    def scorer_id(self): return self.metadata['scorer_id']
    @property
    def input_id(self): return self.metadata['input_id']

    def score(self, predictors, *, feature_names, input_id, observer_id):
        observer(observer_id); meta = self.metadata
        require(observer_id in meta['recipients'], 'recipient_scope')
        require(type(feature_names) is tuple and list(feature_names) == loads(self._schema)['features']
                and input_id == meta['input_id'], 'scoring_schema')
        require(type(predictors) is np.ndarray and predictors.dtype == np.dtype('<f8') and
                predictors.ndim == 2 and predictors.shape[1] == 73 and 1 <= len(predictors) <= 10000 and
                bool(np.isfinite(predictors).all()), 'scoring_predictors')
        if meta['family'] == 'neural':
            _, _, arrays = M.decode(self._payload); transform = loads(self._transform)
            validate_transform(transform)
            x = M.standardize(predictors, np.asarray(transform['mean'], dtype='<f8'),
                              np.asarray(transform['denominator'], dtype='<f8'))
            with torch.random.fork_rng(devices=[]):
                model = R.clone_model(arrays).eval()
            with torch.inference_mode():
                logits = model(torch.from_numpy(x)).squeeze(1)
                require(bool(torch.isfinite(logits).all()), 'nonfinite_logit')
                scores = torch.sigmoid(logits).numpy()
        else:
            state = decode_final_af(self._payload, expected_state_id=meta['model_id'],
                                    expected_fixed_id=meta['fixed_id'], expected_round=meta['final_round'])
            scores = A.score(predictors, state)
        require(bool(np.isfinite(scores).all()) and scores.shape == (len(predictors),), 'nonfinite_or_missing_scores')
        return immutable(scores)

    def score_view(self, view, *, batch_rows=256):
        require(type(view) is PurposeView and view.purpose in {'frozen_validation_scoring', 'frozen_calibration_scoring'}
                and view.frozen_scorer_id == self.scorer_id, 'declared_unlabeled_scoring_view_required')
        require(view.observer_id in self.metadata['recipients'] and
                list(view.features) == loads(self._schema)['features'], 'scoring_view_owner_or_schema')
        require(view._dataset.summary['input_sha256']['candidate'] == self.metadata['candidate_sha256'] and
                view._dataset.summary['assignment_sha256'] == self.metadata['assignment_sha256'], 'scoring_data_scope')
        return ScoreStream(self, view, batch_rows)


def load_bundle(directory, expected_bundle_id):
    files = open_seal(directory, expected_bundle_id)
    meta = loads(files['scorer.json']); schema = loads(files['input-schema.json'])
    common = {'version', 'use', 'family', 'arm', 'model_owner', 'recipients', 'input_id', 'source_complete_sha256',
              'candidate_sha256', 'assignment_sha256', 'customer_map', 'live_eligible', 'feature_order_id',
              'model_id', 'transform_id', 'architecture', 'numeric_rule', 'scorer_id', 'training_scope_id'}
    require(meta.get('family') in {'neural', 'af'}, 'model_family')
    af = meta['family'] == 'af'
    keys(meta, common | ({'fixed_id', 'final_round', 'internal_threshold_use'} if af else {'training_count','initial_model_id'}))
    require(meta['version'] == VERSION and meta['use'] == 'csv_score_only' and meta['live_eligible'] is False and
            meta['customer_map'] is None, 'bundle_use')
    for key in ('input_id','source_complete_sha256','candidate_sha256','assignment_sha256','feature_order_id','model_id','transform_id','scorer_id','training_scope_id'): hex_id(meta[key])
    require(validate_schema(schema) == meta['input_id'] and A.digest(schema['features']) == meta['feature_order_id'], 'input_contract_digest')
    local = meta['arm'] in {'independent_local', 'local_shared_moments'}
    if local: observer(meta['model_owner'])
    else: require(type(meta['model_owner']) is int and meta['model_owner'] == 0, 'model_owner')
    require(meta['recipients'] == ([meta['model_owner']] if local else list(R.OWNERS)), 'recipient_scope')
    require(meta['scorer_id'] == scorer_identity(meta), 'scorer_digest')
    provenance = loads(files['provenance.json'])
    keys(provenance, {'source_complete_sha256','code','framework','input_pins','preprocessing_role',
                      'customer_map','transform_recovery_seal','extra_recovery_charged_separately','native_sources','bundle_code'})
    require(provenance['source_complete_sha256'] == meta['source_complete_sha256'] and
            provenance['preprocessing_role'] == 'train' and
            provenance['input_pins']['candidate'] == meta['candidate_sha256'] and
            provenance['input_pins']['registry'] == schema['registry_sha256'], 'provenance_scope')
    bundle_code=provenance['bundle_code'];keys(bundle_code,{'version','source_sha256','numpy','torch'})
    hex_id(bundle_code['source_sha256'])
    require(bundle_code['version']==VERSION and bundle_code['numpy']==np.__version__ and
            bundle_code['torch']==torch.__version__, 'unsupported_inference_runtime')
    native = provenance['native_sources']
    require(type(native) is list and len(native) == 14 and [v['source_id'] for v in native] == list(range(14)), 'native_source_inventory')
    for v in native: observer(v['client_id'])
    expected_scope = A.TrainingScope(meta['candidate_sha256'], meta['assignment_sha256'], tuple(schema['features']),
        tuple((v['source_id'],v['sha256']) for v in native)).scope_id
    require(expected_scope == meta['training_scope_id'], 'training_scope_binding')
    if not af:
        require(set(files) == {'scorer.json','input-schema.json','provenance.json','model.bin','preprocessing.json'}, 'bundle_files')
        require(meta['arm'] in ARMS and meta['architecture'] == 'linear73_relu16_linear1' and
                meta['numeric_rule'] == 'float64_standardize_then_float32_logit_sigmoid', 'neural_architecture')
        integer(meta['training_count'],1); hex_id(meta['initial_model_id'])
        kind, header, arrays = M.decode(files['model.bin']); t = loads(files['preprocessing.json']); validate_transform(t)
        require(kind == 'model' and header['arm'] == meta['arm'] and header['owner'] == meta['model_owner'] and
                header['round'] == 1 and header['schema'] == meta['feature_order_id'] and
                header['scope'] == meta['training_scope_id'] and header['count'] == meta['training_count'] and
                header['parent'] == meta['initial_model_id'] and
                (meta['arm'] != 'independent_local' or t['count'] == meta['training_count']) and
                M.model_digest(arrays) == meta['model_id'] and A.digest(t) == meta['transform_id'], 'model_or_transform_binding')
        return FrozenScorer(meta, schema, files['model.bin'], t, _token=_LOAD_TOKEN)
    require(set(files) == {'scorer.json','input-schema.json','provenance.json','af-state.json'} and
            meta['arm'] == 'statistical_complete' and meta['architecture'] == A.VERSION and
            meta['numeric_rule'] == 'float64_fixed_anchor_minmax_mahalanobis' and
            meta['internal_threshold_use'] == 'training_provenance_only', 'af_architecture')
    state = decode_final_af(files['af-state.json'], expected_state_id=meta['model_id'],
                           expected_fixed_id=meta['fixed_id'], expected_round=meta['final_round'])
    require(state.scope_id == meta['training_scope_id'] and list(state.features) == schema['features'] and A.digest([state.scaler_min.values(), state.scaler_denominator.values()]) == meta['transform_id'], 'af_transform_schema')
    return FrozenScorer(meta, schema, files['af-state.json'], _token=_LOAD_TOKEN)


class ScoreStream:
    """Partial outputs stay visible; failure counters are never benign decisions."""
    def __init__(self, scorer, view, rows):
        self.receipt = {'status': 'not_started', 'attempted_rows': 0, 'completed_rows': 0, 'completed_batches': 0}
        self.scorer, self.view, self.rows = scorer, view, rows

    def __iter__(self):
        require(self.receipt['status'] == 'not_started', 'score_stream_single_use')
        self.receipt['status'] = 'running'; started = time.monotonic()
        try:
            for batch in self.view.batches(self.rows):
                require(type(batch) is UnlabeledBatch, 'scorer_labels_forbidden')
                self.receipt['attempted_rows'] += len(batch.X)
                scores = self.scorer.score(batch.X, feature_names=self.view.features,
                    input_id=self.scorer.input_id, observer_id=self.view.observer_id)
                self.receipt['completed_rows'] += len(scores); self.receipt['completed_batches'] += 1
                yield batch.identities, scores
            self.receipt['status'] = 'complete_scoring'
        except BaseException as exc:
            self.receipt.update(status='failed_or_incomplete_scoring', error_type=type(exc).__name__, error=str(exc)); raise
        finally: self.receipt['elapsed_seconds'] = time.monotonic() - started


def validate_decision_policy(obj):
    keys(obj, {'version','scorer_id','input_id','role','comparison','rule','calibration_source_sha256','entries'})
    require(obj['version'] == VERSION and obj['role'] == 'calibration' and obj['comparison'] == '>' and
            obj['rule'] == 'benign_order_statistic_strict_ties', 'decision_policy')
    for k in ('scorer_id','input_id','calibration_source_sha256'): hex_id(obj[k])
    require(type(obj['entries']) is list and len(obj['entries']) <= 10, 'decision_entries')
    seen = set()
    for e in obj['entries']:
        keys(e, {'owner','threshold','n_benign','rank','alpha_numerator','alpha_denominator','membership_sha256'})
        observer(e['owner']); require(e['owner'] not in seen, 'duplicate_threshold_owner'); seen.add(e['owner'])
        integer(e['n_benign'], 1); integer(e['rank'],1); integer(e['alpha_numerator']); integer(e['alpha_denominator'],1)
        a,b,n = e['alpha_numerator'],e['alpha_denominator'],e['n_benign']
        require(a < b and e['rank'] == (n*(b-a)+b-1)//b, 'threshold_rank')
        require(type(e['threshold']) in (int,float) and math.isfinite(e['threshold']), 'threshold_finite')
        hex_id(e['membership_sha256'])
    return obj


def export_decision_policy(path, policy):
    validate_decision_policy(policy); path = Path(path)
    root = root_path(path.parent); require(not path.exists() and not path.is_symlink(), 'preserve_decision_artifact')
    require(path.name == 'reporting-thresholds.json', 'decision_artifact_name')
    data = A.canonical(policy)
    with path.open('xb') as f: f.write(data)
    return sha(data)


def decide(scorer, scores, *, owner, policy_directory, expected_policy_sha256):
    require(isinstance(scorer, FrozenScorer), 'frozen_scorer_required'); observer(owner); hex_id(expected_policy_sha256)
    raw = file_bytes(root_path(policy_directory), 'reporting-thresholds.json')
    require(sha(raw) == expected_policy_sha256, 'decision_artifact_digest')
    obj = validate_decision_policy(loads(raw)); meta = scorer.metadata
    require(obj['scorer_id'] == scorer.scorer_id and obj['input_id'] == scorer.input_id and
            owner in meta['recipients'] and all(e['owner'] in meta['recipients'] for e in obj['entries']), 'decision_scorer_scope')
    require(type(scores) is np.ndarray and scores.dtype in (np.dtype('float32'), np.dtype('float64')) and scores.ndim == 1 and 1 <= len(scores) <= 10000 and
            bool(np.isfinite(scores).all()), 'invalid_decision_scores')
    require(bool((scores >= 0).all()) and (meta['family'] != 'neural' or bool((scores <= 1).all())), 'score_range')
    entry = next((e for e in obj['entries'] if e['owner'] == owner), None)
    require(entry is not None, 'no_threshold_for_owner')
    threshold = entry['threshold']
    require(threshold >= 0 and (meta['family'] != 'neural' or threshold <= 1), 'threshold_range')
    return immutable(scores > threshold)
