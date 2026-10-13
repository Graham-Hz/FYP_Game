"""Meaningful boundary, group-preservation and compatible-comparison checks."""
import importlib.util
from pathlib import Path
import sys
import unittest

if importlib.util.find_spec('sklearn') is None:
    raise unittest.SkipTest('Requires frozen model environment')
import numpy as np
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src/models'))
from scope_data_v1 import FOUR, THREE, four_tiers, collapse, pc_mask
from run_scope_sensitivity import evaluation_frames
from verify_scope_sensitivity import calculate


class ScopeTests(unittest.TestCase):
    def test_four_class_arithmetic_keeps_absent_class(self):
        y, predicted = [0,0,1,3], [0,1,1,2]
        probabilities = np.eye(4)[predicted]
        frame = pd.DataFrame({'target_tier':np.asarray(FOUR)[y], 'predicted_tier':np.asarray(FOUR)[predicted],
                              **{f'p{i}':probabilities[:,i] for i in range(4)}})
        scores, matrix, per_class = calculate(frame, FOUR)
        self.assertAlmostEqual(scores['macro_f1'], 1/3)
        self.assertAlmostEqual(scores['balanced_accuracy'], .5)
        self.assertEqual(scores['accuracy'], .5)
        self.assertEqual(matrix.shape, (4,4))
        self.assertEqual(per_class[3].tolist(), [2,1,0,1])

    def test_install_boundaries(self):
        values = pd.Series([0, 999, 1000, 99999, 100000, 999999, 1000000, 2000000000], index=range(10,18))
        result = four_tiers(values)
        self.assertEqual(result.tolist(), [x for x in FOUR for _ in range(2)])
        self.assertEqual(result.index.tolist(), values.index.tolist())

    def test_invalid_install_bounds(self):
        for invalid in (-1, 1.5, np.nan, np.inf, 'unknown'):
            with self.subTest(invalid=invalid), self.assertRaises((ValueError, TypeError)):
                four_tiers(pd.Series([invalid]))

    def test_collapse_recomputes_winner(self):
        frame = pd.DataFrame({'target_tier': [FOUR[3]], 'predicted_tier': [FOUR[0]],
                              'p0': [.35], 'p1': [.15], 'p2': [.3], 'p3': [.2]})
        result = collapse(frame)
        self.assertEqual(result.target_tier.iloc[0], THREE[2])
        self.assertEqual(result.predicted_tier.iloc[0], THREE[2])
        self.assertEqual(result.p2.iloc[0], .5)
        self.assertIn('p3', frame)  # no input mutation
        for column, value in [('p0', np.nan), ('p1', -.1), ('p2', .9), ('target_tier', 'invalid')]:
            with self.subTest(column=column), self.assertRaises(ValueError):
                collapse(frame.assign(**{column: value}))

    def test_pc_scope_filters_and_inherited_folds(self):
        ledger = pd.DataFrame({'exclude_unknown_target': [False]*6+[True],
            'exclude_unknown_developer': [False]*5+[True,False],
            'exclude_software_only_heuristic': [False,False,True,False,False,False,False],
            'exclude_nonpositive_price': [False,True,False,False,False,False,False],
            'primary_eligible': [True,False,False,True,True,False,False],
            'reviewed_demo_exception': [False,False,False,True,False,False,False],
            'assigned_split': ['train']*4+['test','train','train'], 'assigned_cv_fold': [0,1,1,2,-1,0,1]})
        for scenario, ids in [('all_price',[0,1,3]), ('include_software',[0,2,3]), ('no_demo_exception',[0])]:
            self.assertEqual(ledger.index[pc_mask(ledger, scenario)].tolist(), ids)
        self.assertEqual(ledger.assigned_cv_fold.tolist(), [0,1,1,2,-1,0,1])
        with self.assertRaises(ValueError):
            pc_mask(ledger, 'invalid')

    def test_pc_comparison_uses_exact_intersection(self):
        frame = pd.DataFrame({'app_id':['a','b'], 'developer_group':['g1','g2'], 'cv_fold':[0,0],
            'target_tier':['x','y'], 'predicted_tier':['x','y'], 'p0':[.7,.1], 'p1':[.2,.8], 'p2':[.1,.1]})
        original = frame.iloc[:1].copy()
        result = evaluation_frames('pc', frame, original, original[['app_id']])
        self.assertEqual(len(result['scope_refit']), 2)
        self.assertEqual(result['refit_common_primary'].app_id.tolist(), ['a'])
        self.assertEqual(result['primary_common'].app_id.tolist(), ['a'])
        with self.assertRaises(ValueError):
            evaluation_frames('pc', frame, original.assign(developer_group='wrong'), original[['app_id']])


if __name__ == '__main__':
    unittest.main()
