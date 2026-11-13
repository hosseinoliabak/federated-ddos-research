"""Scalar-control invariants; fabricated arrays/source fixtures only."""
from pathlib import Path
from unittest.mock import patch
import json
import sys
import tempfile
import unittest
import numpy as np
from sklearn.metrics import roc_auc_score
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import train_separability_diagnostic as D
import afbkm_adapter_v2 as A
import frozen_model_bundle as B
import run_matched_workload as R
from purpose_data_view import PurposeView, UnlabeledBatch, immutable
from synthetic_workload_fixture import prepared_fixture


class PairCriterionTests(unittest.TestCase):
    def test_hand_computable_tied_pairs(self):
        x=np.array([0,1,1,3],dtype='<f8');y=np.array([0,1,0,1],dtype='u1')
        self.assertEqual(D.two_u(x,y),(7,8))
        r=D.select_feature(x[:,None],y)['selection'];self.assertEqual(r['direction'],1)
        self.assertEqual(r['oriented_numerator'],7)

    def test_reverse_orientation_same_exact_criterion(self):
        x=np.array([0,1,1,3],dtype='<f8');y=np.array([0,1,0,1],dtype='u1')
        self.assertEqual(D.two_u(-x,y),(1,8))
        r=D.select_feature(np.stack([-x,x],axis=1),y)['selection']
        self.assertEqual((r['feature_index'],r['direction'],r['oriented_numerator']),(0,-1,7))

    def test_all_ties_choose_first_positive_at_chance(self):
        X=np.zeros((5,4),dtype='<f8');y=np.array([0,1,0,1,0],dtype='u1')
        r=D.select_feature(X,y)['selection']
        self.assertEqual(r,{'feature_index':0,'direction':1,'numerator':6,'denominator':12,'oriented_numerator':6})

    def test_pair_count_matches_independent_brute_and_sklearn(self):
        rng=np.random.default_rng(117)
        for n in (3,8,19,35):
            for trial in range(8):
                x=rng.integers(-3,4,size=n).astype('<f8');y=rng.integers(0,2,size=n,dtype='u1');y[0]=0;y[1]=1
                favorable=sum(2*int(a>b)+int(a==b) for a in x[y==1] for b in x[y==0])
                numerator,total=D.two_u(x,y)
                self.assertEqual(numerator,favorable)
                self.assertAlmostEqual(numerator/total,roc_auc_score(y,x),places=14)

    def test_uint64_boundary_before_reduction(self):
        self.assertEqual(D.pair_total(2**31,1),2**32)
        self.assertRaisesRegex(ValueError,'pair_counter_range',D.pair_total,2**32,2**32)
        self.assertRaises(ValueError,D.pair_total,True,1)

    def test_single_class_and_empty_do_not_invent_scorer(self):
        for y in [np.zeros(4,dtype='u1'),np.ones(4,dtype='u1'),np.empty(0,dtype='u1')]:
            r=D.select_feature(np.zeros((len(y),73),dtype='<f8'),y)
            self.assertEqual(r['status'],'NA_train_class_support');self.assertIsNone(r['selection'])
            self.assertEqual(r['criteria'],[])

    def test_invalid_feature_label_dtype_shape_finiteness(self):
        good=np.arange(4,dtype='<f8');y=np.array([0,1,0,1],dtype='u1')
        for x in (good.astype('f4'),np.array([0,np.nan,1,2]),np.array([0,np.inf,1,2]),good[:,None]):
            self.assertRaises(ValueError,D.two_u,x,y)
        for bad in (y.astype('f8'),np.array([0,2,0,1],dtype='u1'),y[:2]):
            self.assertRaises(ValueError,D.two_u,good,bad)


class PurposeScalarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(prefix='fabricated-scalar-tests-');cls.root=Path(cls.tmp.name).resolve()
        cls.ds=prepared_fixture(cls.root/'source',small=True)
        cls.local,cls.lr=D.fit_local(cls.ds,1);cls.pooled,cls.pr=D.fit_pooled(cls.ds)

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def altered(self,mutate):
        payload=self.local.validate();mutate(payload);data=A.canonical(payload)
        return D.FrozenScalar(data,B.sha(data))

    def score(self,scorer=None,X=None,owner=1):
        s=scorer or self.local;q=s.validate()
        X=np.zeros((3,73),dtype='<f8') if X is None else X
        return s.score(X,feature_names=self.ds.features,input_id=q['input_id'],observer_id=owner)

    def test_local_never_requests_other_owners_or_heldout(self):
        original=self.ds.supervised_train;requested=[]
        def own(owner):
            self.assertEqual(owner,1);requested.append(owner);return original(owner)
        with (patch.object(self.ds,'supervised_train',own),
              patch.object(self.ds,'scoring',side_effect=AssertionError('heldout forbidden')),
              patch.object(self.ds,'validation_selection',side_effect=AssertionError('selection forbidden')),
              patch.object(self.ds,'trusted_benign_anchor',side_effect=AssertionError('anchor forbidden')),
              patch.object(self.ds,'unlabeled_train',side_effect=AssertionError('unnecessary transform forbidden'))):
            s,r=D.fit_local(self.ds,1)
        self.assertEqual(requested,[1]);self.assertEqual(s.data,self.local.data)
        self.assertEqual(r['serialized_application_bytes'],0)

    def test_pooled_full_owner_raw_roundtrips_and_tails(self):
        self.assertEqual([a['owner'] for a in self.pr['access']],list(R.OWNERS))
        self.assertEqual(self.pr['train_rows'],self.ds.summary['rows_by_role']['train'])
        self.assertGreater(self.pr['serialized_application_bytes'],self.pr['train_rows']*73*8)
        self.assertEqual(self.pr['serialized_messages'],10)
        self.assertEqual(self.pooled.validate()['owner'],0)

    def test_single_class_owner_has_na_without_global_fallback(self):
        original=self.ds.supervised_train;requested=[]
        def own(owner):self.assertEqual(owner,2);requested.append(owner);return original(owner)
        with patch.object(self.ds,'supervised_train',own):s,r=D.fit_local(self.ds,2)
        self.assertIsNone(s);self.assertEqual(r['status'],'NA_train_class_support');self.assertEqual(requested,[2])

    def test_validation_view_cannot_be_substituted_for_training(self):
        bad=self.ds.validation_selection(1,declaration_id='fabricated-wrong-role')
        with patch.object(self.ds,'supervised_train',return_value=bad),patch.object(PurposeView,'batches',side_effect=AssertionError('must reject before read')):
            self.assertRaisesRegex(ValueError,'non_training_stage',D.fit_local,self.ds,1)

    def test_exact_serialization_hash_and_train_choice_bounds(self):
        clone=D.FrozenScalar(self.local.data,self.local.scorer_id);self.assertEqual(clone.data,self.local.data)
        self.assertRaisesRegex(ValueError,'scalar_hash',D.FrozenScalar,self.local.data,b'0'.hex()*32)
        for f in [lambda p:p['selection'].update(feature_index=73),lambda p:p.update(owner=True),
                  lambda p:p['selection'].update(direction=0),lambda p:p.update(train_rows=999)]:
            self.assertRaises(ValueError,self.altered,f)

    def test_unknown_or_live_schema_rejected(self):
        self.assertRaises(ValueError,self.altered,lambda p:p['schema'].update(live_eligible=True))
        self.assertRaises(ValueError,self.altered,lambda p:p.update(extra=True))
        self.assertRaises(ValueError,self.altered,lambda p:p.update(version='different'))

    def test_predictor_only_signed_value_not_scaling(self):
        q=self.local.validate();j=q['selection']['feature_index'];direction=q['selection']['direction']
        X=np.zeros((3,73),dtype='<f8');X[:,j]=[-3,0,7]
        scores=self.score(X=X);np.testing.assert_array_equal(scores,direction*np.array([-3,0,7]))
        self.assertFalse(scores.flags.writeable)
        self.assertRaises(TypeError,self.local.score,X,feature_names=self.ds.features,input_id=q['input_id'],observer_id=1,y=np.zeros(3))

    def test_wrong_owner_order_input_and_nonfinite_fail(self):
        self.assertRaises(ValueError,self.score,owner=2)
        q=self.local.validate();X=np.zeros((3,73),dtype='<f8')
        for kwargs in [{'feature_names':tuple(reversed(self.ds.features)),'input_id':q['input_id'],'observer_id':1},
                       {'feature_names':self.ds.features,'input_id':'0'*64,'observer_id':1}]:
            self.assertRaises(ValueError,self.local.score,X,**kwargs)
        X[0,0]=np.nan;self.assertRaises(ValueError,self.score,X=X)
        self.assertRaises(ValueError,self.score,X=np.zeros((2,72)))

    def test_owner_mismatch_rejected_before_validation_read(self):
        with patch.object(self.ds,'scoring',side_effect=AssertionError('unauthorized view requested')):
            self.assertRaisesRegex(ValueError,'scalar_recipient',D.evaluate_validation,self.ds,self.local,2)

    def test_validation_complete_without_fitting_selection_calibration(self):
        with (patch.object(self.ds,'supervised_train',side_effect=AssertionError('fit forbidden')),
              patch.object(self.ds,'unlabeled_train',side_effect=AssertionError('transform forbidden')),
              patch.object(self.ds,'validation_selection',side_effect=AssertionError('selection forbidden')),
              patch.object(D,'select_feature',side_effect=AssertionError('reselect forbidden'))):
            r=D.evaluate_validation(self.ds,self.local,1,batch_rows=3)
        self.assertEqual(r['status'],'complete_fixed_validation');self.assertEqual(r['missing_scores'],0)
        self.assertEqual(r['valid_scores'],r['expected_rows']);self.assertIsNone(r['recall']);self.assertIsNone(r['fpr'])

    def test_no_attack_validation_rank_na_support_and_coverage(self):
        r=D.evaluate_validation(self.ds,self.pooled,2,batch_rows=3)
        self.assertEqual(r['rank_status'],'NA_class_support');self.assertEqual(r['attack'],0)
        self.assertIsNone(r['auroc']);self.assertIsNone(r['average_precision']);self.assertEqual(r['missing_scores'],0)

    def test_partial_score_failure_retains_exact_missing_without_benign(self):
        original=D.FrozenScalar.score;calls=[0]
        def fail(s,*args,**kwargs):
            calls[0]+=1
            if calls[0]>1:raise ValueError('fabricated-later-failure')
            return original(s,*args,**kwargs)
        with patch.object(D.FrozenScalar,'score',fail):
            with self.assertRaises(D.DiagnosticFailure) as cm:D.evaluate_validation(self.ds,self.local,1,batch_rows=1)
        r=cm.exception.receipt;self.assertEqual(r['valid_scores'],1)
        self.assertEqual(r['missing_scores'],r['expected_rows']-1);self.assertEqual(r['status'],'failed_or_incomplete_validation')
        self.assertNotIn('confusion',r)

    def test_invalid_returned_score_fails_without_imputation(self):
        with patch.object(D.FrozenScalar,'score',return_value=np.array([np.nan])):
            with self.assertRaises(D.DiagnosticFailure) as cm:D.evaluate_validation(self.ds,self.local,1,batch_rows=1)
        self.assertEqual(cm.exception.receipt['invalid_returned_scores'],1)
        self.assertEqual(cm.exception.receipt['valid_scores'],0)

    def test_wrong_dataset_scope_is_rejected(self):
        s=self.altered(lambda q:q.update(scope_id='f'*64))
        self.assertRaisesRegex(ValueError,'scalar_dataset_scope',D.evaluate_validation,self.ds,s,1)

    def test_sealed_source_arrays_remain_immutable(self):
        before=B.sha(self.ds._X.tobytes());records=B.sha(self.ds._records.tobytes())
        D.evaluate_validation(self.ds,self.pooled,10,batch_rows=3)
        self.assertEqual(before,B.sha(self.ds._X.tobytes()));self.assertEqual(records,B.sha(self.ds._records.tobytes()))
        self.assertFalse(self.ds._X.flags.writeable);self.assertFalse(self.ds._records.flags.writeable)


if __name__=='__main__':unittest.main()
