"""Train-only scope reconstruction; no learned transforms or new group assignment."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal

ROOT = Path(__file__).resolve().parents[2]
THREE = ['M1_under_1k', 'M2_1k_to_under_100k', 'M3_100k_plus']
FOUR = ['M1_under_1k', 'M2_1k_to_under_100k', 'M3_100k_to_under_1m', 'M4_1m_plus']


def pc_mask(ledger, scenario):
    known = ~ledger.exclude_unknown_target & ~ledger.exclude_unknown_developer
    if scenario == 'all_price':
        mask = known & ~ledger.exclude_software_only_heuristic
    elif scenario == 'include_software':
        mask = known & ~ledger.exclude_nonpositive_price
    elif scenario == 'no_demo_exception':
        mask = ledger.primary_eligible & ~ledger.reviewed_demo_exception
    else:
        raise ValueError('Unknown PC scope')
    return mask & ledger.assigned_split.eq('train')


def four_tiers(values):
    x = pd.to_numeric(values, errors='raise')
    if x.isna().any() or not np.isfinite(x).all() or (x < 0).any() or (x % 1 != 0).any():
        raise ValueError('Install lower bounds must be known nonnegative integers')
    return pd.Series(np.select([x < 1000, x < 100000, x < 1000000], FOUR[:3], default=FOUR[3]), index=values.index)


def collapse(frame):
    p = frame[[f'p{i}' for i in range(4)]].to_numpy()
    if not np.isfinite(p).all() or (p < 0).any() or (p > 1).any() or not np.allclose(p.sum(axis=1), 1):
        raise ValueError('Invalid four-class probabilities')
    result = frame.drop(columns='p3').copy()
    result['p2'] = p[:, 2] + p[:, 3]
    result['target_tier'] = result.target_tier.replace({FOUR[2]: THREE[2], FOUR[3]: THREE[2]})
    if not result.target_tier.isin(THREE).all():
        raise ValueError('Unexpected target')
    result['predicted_tier'] = np.asarray(THREE)[result[['p0','p1','p2']].to_numpy().argmax(axis=1)]
    return result


def build(platform, scenario):
    base = ROOT/'data/processed/analysis_v1'
    policy = json.loads((ROOT/'config/feature_policy_v1.json').read_text())
    rules = json.loads((ROOT/'config/analysis_v1.json').read_text())
    features = pd.read_parquet(base/f'{platform}_features.parquet')
    labels = pd.read_parquet(base/f'{platform}_labels_splits.parquet', filters=[('split','==','train')])
    primary = features.merge(labels, on='app_id', validate='one_to_one')
    ledger = pd.read_parquet(base/f'{platform}_cohort_ledger.parquet')
    candidates = pd.read_parquet(ROOT/f'data/interim/cleaning_candidate_v1/{platform}_candidates.parquet')
    if platform == 'mobile':
        if scenario != 'four_tiers':
            raise ValueError('Unknown Mobile scope')
        data = primary.merge(candidates[['app_id','minimum_installs']], on='app_id', validate='one_to_one')
        if len(data) != len(primary):
            raise ValueError('Missing install source')
        data['target_tier'] = four_tiers(data.minimum_installs)
        mapped = data.target_tier.replace({FOUR[2]:THREE[2], FOUR[3]:THREE[2]})
        if not np.array_equal(mapped, primary.set_index('app_id').loc[data.app_id, 'target_tier']):
            raise ValueError('Four-tier source disagrees with primary labels')
        data = data.drop(columns='minimum_installs')
        data['is_primary'] = True
    else:
        cols = list(dict.fromkeys(c for values in policy['pc'].values() for c in values))
        candidates['planning_categories'] = candidates.categories.map(lambda xs:[v for v in xs if v in rules['pc_planning_categories']])
        candidates['categories_unavailable'] = candidates.categories.map(len).eq(0)
        candidates['languages_unavailable'] = candidates.supported_languages.map(len).eq(0)
        # The reviewed exception was excluded by candidate cleaning; use its verified frozen features.
        exception = features.loc[features.app_id.isin(rules['pc_demo_exceptions'])]
        pool = pd.concat([candidates[['app_id']+cols], exception[['app_id']+cols]], ignore_index=True)
        overlap = pool.merge(primary[['app_id']], on='app_id', validate='one_to_one').sort_values('app_id').reset_index(drop=True)
        expected = primary[['app_id']+cols].sort_values('app_id').reset_index(drop=True)
        assert_frame_equal(overlap, expected, check_dtype=False)
        selected = ledger.loc[pc_mask(ledger, scenario)].copy()
        selected = selected.rename(columns={'assigned_split':'split','assigned_cv_fold':'cv_fold','primary_eligible':'is_primary'})
        fields = ['app_id','developer_group','target_tier','split','cv_fold','is_primary','exclude_software_only_heuristic','exclude_nonpositive_price']
        data = pool.merge(selected[fields], on='app_id', validate='one_to_one')
        if len(data) != len(selected):
            raise ValueError('Missing scenario feature rows')
        check = candidates[['app_id','target_tier']].merge(selected[['app_id','target_tier']], on='app_id', suffixes=('_candidate','_ledger'))
        if not check.target_tier_candidate.eq(check.target_tier_ledger).all():
            raise ValueError('Source label disagreement')
    if not data.split.eq('train').all() or data.app_id.duplicated().any() or data.groupby('developer_group').cv_fold.nunique().max() != 1:
        raise ValueError('Invalid train/group membership')
    return data.sort_values('app_id').reset_index(drop=True), primary.sort_values('app_id').reset_index(drop=True)
