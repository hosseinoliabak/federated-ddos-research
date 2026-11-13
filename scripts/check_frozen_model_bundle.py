"""Fabricated end-to-end frozen bundle check; no acquired-data input option."""
from pathlib import Path
import hashlib
import json
import tempfile
import numpy as np
import frozen_model_bundle as B
from synthetic_workload_fixture import prepared_fixture
import run_matched_workload as R


def check():
    with tempfile.TemporaryDirectory(prefix='fabricated-bundle-e2e-') as tmp:
        root=Path(tmp).resolve();ds=prepared_fixture(root/'source',small=True)
        run_dir=root/'cost';R.run(ds,R.PilotConfig(cpu_threads=1),run_dir,synthetic_only=True)
        completed=B.CompletedRun(run_dir,hashlib.sha256((run_dir/'COMPLETE.json').read_bytes()).hexdigest())
        locals={};messages={}
        for owner in R.OWNERS:
            out=root/('local-recovery-'+str(owner));seal=B.recover_train_transforms(ds,completed,out,owner=owner)
            locals[owner]=(out,seal);messages[owner]=B.local_moment_message(out,seal)
        recovery=root/'recovery';rid=B.merge_train_transforms(completed,messages,recovery)
        schema=B.csv_schema(ds.features,ds.summary['input_sha256']['registry']);results=[]
        for arm in ['independent_local','pooled_central','fedavg','local_shared_moments','statistical_complete']:
            local=arm in {'independent_local','local_shared_moments'}
            options={} if arm=='statistical_complete' else {'transforms':recovery,'transform_seal':rid}
            if arm=='independent_local':options={'transforms':locals[1][0],'transform_seal':locals[1][1]}
            out=root/arm;bid=B.export_bundle(completed,schema,out,arm=arm,owner=1 if local else 0,**options)
            scorer=B.load_bundle(out,bid)
            view=ds.scoring('validation',1,declaration_id='fabricated-bundle-check',frozen_scorer_id=scorer.scorer_id)
            stream=scorer.score_view(view,batch_rows=3);rows=sum(len(scores) for _,scores in stream)
            B.require(stream.receipt['status']=='complete_scoring' and rows>0,'fabricated_scoring_incomplete')
            results.append({'arm':arm,'bundle_id':bid,'scorer_id':scorer.scorer_id,
                            'fabricated_scored_rows':rows,'live_eligible':False})
        return {'status':'complete_frozen_bundle_synthetic_check','synthetic_only':True,
                'actual_data_fit_recovery_export_scoring_calibration':False,
                'features':73,'arms':results,'recovered_train_rows':ds.summary['rows_by_role']['train'],
                'labels_given_to_scorer':False,'external_calibration_performed':False}


def main():
    print(json.dumps(check(),indent=2,allow_nan=False))
    return 0

if __name__=='__main__':raise SystemExit(main())
