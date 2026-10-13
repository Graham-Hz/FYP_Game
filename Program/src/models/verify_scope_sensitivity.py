"""Independent reconstruction and NumPy arithmetic for scope/target experiments.

Does not import the scope builder, runner, probability collapse or sklearn metrics.
Reuses prior-run model-provenance checks, with separately reconstructed fitting rows.
"""
import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal
from verify_age_sensitivity import require, digest, id_hash, row_for, close, check_membership, verify_model

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / 'reports/2026-10-13/model_scope_v1'
ARTIFACTS = ROOT / 'data/processed/model_scope_v1'
METRICS = ('macro_f1', 'balanced_accuracy', 'accuracy', 'log_loss', 'brier')
THREE = ['M1_under_1k', 'M2_1k_to_under_100k', 'M3_100k_plus']
FOUR = ['M1_under_1k', 'M2_1k_to_under_100k', 'M3_100k_to_under_1m', 'M4_1m_plus']


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def calculate(frame, labels):
    k = len(labels)
    require(len(frame) > 0 and frame.target_tier.isin(labels).all() and frame.predicted_tier.isin(labels).all(), 'Unknown class/empty score')
    lookup = {label: i for i, label in enumerate(labels)}
    y = frame.target_tier.map(lookup).to_numpy(dtype=int)
    predicted = frame.predicted_tier.map(lookup).to_numpy(dtype=int)
    p = frame[[f'p{i}' for i in range(k)]].to_numpy()
    require(np.isfinite(p).all() and (p >= 0).all() and (p <= 1).all(), 'Invalid probabilities')
    require(np.allclose(p.sum(axis=1), 1, atol=1e-10), 'Probability sums')
    require(np.array_equal(predicted, p.argmax(axis=1)), 'Incorrect argmax')
    cm = np.zeros((k, k), dtype=np.int64)
    np.add.at(cm, (y, predicted), 1)
    tp, support, predicted_n = cm.diagonal(), cm.sum(axis=1), cm.sum(axis=0)
    recall = np.divide(tp, support, out=np.zeros(k), where=support != 0)
    precision = np.divide(tp, predicted_n, out=np.zeros(k), where=predicted_n != 0)
    f1 = np.divide(2*tp, support+predicted_n, out=np.zeros(k), where=(support+predicted_n) != 0)
    clipped = np.clip(p, np.finfo(float).eps, 1-np.finfo(float).eps)
    scores = {'macro_f1': float(f1.mean()), 'balanced_accuracy': float(recall[support > 0].mean()),
        'accuracy': float(tp.sum()/len(frame)), 'log_loss': float(-np.log(clipped[np.arange(len(frame)), y]).mean()),
        'brier': float(np.square(p-np.eye(k)[y]).sum(axis=1).mean())}
    return scores, cm, (precision, recall, f1, support)


def reconstruct(platform, scenario, policy):
    base = ROOT / 'data/processed/analysis_v1'
    all_labels = pd.read_parquet(base / f'{platform}_labels_splits.parquet')
    features = pd.read_parquet(base / f'{platform}_features.parquet')
    primary = features.merge(all_labels.loc[all_labels.split.eq('train')], on='app_id', validate='one_to_one')
    ledger = pd.read_parquet(base / f'{platform}_cohort_ledger.parquet')
    candidates = pd.read_parquet(ROOT / f'data/interim/cleaning_candidate_v1/{platform}_candidates.parquet')
    if platform == 'pc':
        eligible = ledger.assigned_split.eq('train')
        if scenario == 'no_demo_exception':
            eligible &= ledger.primary_eligible & ~ledger.reviewed_demo_exception
        else:
            eligible &= ~(ledger.exclude_unknown_target | ledger.exclude_unknown_developer)
            if scenario == 'all_price':
                eligible &= ~ledger.exclude_software_only_heuristic
            elif scenario == 'include_software':
                eligible &= ~ledger.exclude_nonpositive_price
            else:
                raise ValueError('Unexpected scenario')
        chosen = ledger.loc[eligible].rename(columns={'assigned_split':'split', 'assigned_cv_fold':'cv_fold', 'primary_eligible':'is_primary'})
        cols = list(dict.fromkeys(c for values in policy['pc'].values() for c in values))
        rules = read(ROOT / 'config/analysis_v1.json')
        candidates['planning_categories'] = [[c for c in categories if c in set(rules['pc_planning_categories'])] for categories in candidates.categories]
        candidates['categories_unavailable'] = [len(v) == 0 for v in candidates.categories]
        candidates['languages_unavailable'] = [len(v) == 0 for v in candidates.supported_languages]
        pool = pd.concat([candidates[['app_id']+cols], features.loc[features.app_id.isin(rules['pc_demo_exceptions']), ['app_id']+cols]], ignore_index=True)
        require(not pool.app_id.duplicated().any(), 'Duplicated source feature IDs')
        expected_primary = primary[['app_id']+cols].sort_values('app_id').reset_index(drop=True)
        actual_primary = pool.loc[pool.app_id.isin(primary.app_id)].sort_values('app_id').reset_index(drop=True)
        assert_frame_equal(actual_primary, expected_primary, check_dtype=False)
        fields = ['app_id','developer_group','target_tier','split','cv_fold','is_primary','exclude_software_only_heuristic','exclude_nonpositive_price']
        expected = pool.merge(chosen[fields], on='app_id', validate='one_to_one')
        require(len(expected) == len(chosen), 'Missing source features')
        source_labels = candidates.set_index('app_id').target_tier
        shared = expected.loc[expected.app_id.isin(source_labels.index)]
        require(np.array_equal(shared.target_tier, source_labels.loc[shared.app_id]), 'Source targets')
    else:
        require(scenario == 'four_tiers', 'Unexpected Mobile scenario')
        expected = primary.copy()
        installs = candidates.set_index('app_id').minimum_installs.loc[expected.app_id].to_numpy(dtype=float)
        require(np.isfinite(installs).all() and (installs >= 0).all() and (installs % 1 == 0).all(), 'Invalid install source')
        indices = np.searchsorted([1000,100000,1000000], installs, side='right')
        expected['target_tier'] = np.asarray(FOUR)[indices]
        require(np.array_equal(np.asarray(THREE)[np.minimum(indices,2)], primary.target_tier), 'Three-tier source mismatch')
        expected['is_primary'] = True
    expected = expected.sort_values('app_id').reset_index(drop=True)
    saved = pd.read_parquet(ARTIFACTS / f'{platform}__{scenario}__data.parquet')
    assert_frame_equal(saved, expected, check_dtype=False)
    require(expected.split.eq('train').all() and not expected.app_id.duplicated().any(), 'Nontrain/duplicate data')
    require(expected.groupby('developer_group').cv_fold.nunique().max() == 1, 'Group crosses folds')
    heldout = ledger.loc[ledger.assigned_split.ne('train')]
    require(set(expected.app_id).isdisjoint(heldout.app_id) and set(expected.developer_group).isdisjoint(heldout.developer_group), 'Heldout leakage')
    assigned = expected.merge(ledger[['app_id','developer_group','assigned_cv_fold','assigned_split']], on='app_id', suffixes=('','_ledger'), validate='one_to_one')
    require(assigned.developer_group.eq(assigned.developer_group_ledger).all() and assigned.cv_fold.eq(assigned.assigned_cv_fold).all() and assigned.assigned_split.eq('train').all(), 'Changed ledger assignment')
    return expected, primary, ledger.loc[ledger.assigned_split.eq('train')]


def independent_modes(platform, frame, original, primary, labels):
    if platform == 'pc':
        common = frame.loc[frame.app_id.isin(primary.app_id)]
        reference = original.loc[original.app_id.isin(common.app_id)]
        check_membership(reference, common)
        return {'scope_refit':(frame, labels), 'refit_common_primary':(common, labels), 'primary_common':(reference, labels)}
    collapsed = frame.drop(columns='p3').copy()
    collapsed['p2'] = frame[['p2','p3']].sum(axis=1)
    collapsed['target_tier'] = [THREE[min(FOUR.index(label),2)] for label in frame.target_tier]
    collapsed['predicted_tier'] = np.asarray(THREE)[collapsed[['p0','p1','p2']].to_numpy().argmax(axis=1)]
    check_membership(collapsed, primary.loc[primary.app_id.isin(frame.app_id)])
    check_membership(original, collapsed)
    return {'four_tier_refit':(frame, labels), 'collapsed_three_refit':(collapsed, THREE), 'primary_three':(original, THREE)}


def verify_subgroups(table, joined, data, labels, key):
    if key['platform'] == 'mobile':
        joined = joined.merge(data[['app_id','free']], on='app_id', validate='one_to_one')
        masks = {'free':joined.free.eq(True).fillna(False), 'paid':joined.free.eq(False).fillna(False), 'unknown':joined.free.isna()}
    else:
        joined = joined.merge(data[['app_id','is_primary','exclude_software_only_heuristic']], on='app_id', validate='one_to_one')
        masks = {'original_primary':joined.is_primary, 'added_only':~joined.is_primary,
                 'software_only':joined.exclude_software_only_heuristic, 'other':~joined.exclude_software_only_heuristic}
    for name, mask in masks.items():
        part = joined.loc[mask]
        row = row_for(table, **key, subgroup=name)
        require(row.n == len(part) and row.class_count == len(labels) and row.classes_present == part.target_tier.nunique(), 'Subgroup denominator')
        for i, label in enumerate(labels):
            close(row[f'support_{i}'], part.target_tier.eq(label).sum(), 'Subgroup support')
        if len(part):
            scores, _, _ = calculate(part, labels)
            for m, value in scores.items():
                close(value, row[m], 'Subgroup arithmetic')
        else:
            require(all(row[m] == '' for m in METRICS), 'Empty subgroup was scored')
    return len(masks)


def main():
    run = read(REPORT / 'run_manifest.json')
    require(run['status'] == 'complete' and run['partition'] == 'train' and not run['calibration_evaluated'] and not run['test_evaluated'], 'Not complete/train-only')
    analysis_path = ROOT / 'reports/2026-10-06/analysis_v1/manifest.json'
    analysis = read(analysis_path)
    require(digest(analysis_path) == run['identity']['analysis_manifest_sha256'], 'Changed analysis')
    for mapping in (run['identity']['inputs'], run['identity']['dependencies'], analysis['dependencies'], run['artifacts']):
        for relative, sha in mapping.items():
            require(digest(ROOT / relative) == sha, f'Changed file {relative}')
    for name, sha in run['outputs'].items():
        require(digest(REPORT / name) == sha, f'Changed table {name}')
    config = read(ROOT / 'config/model_scope_v1.json')
    require(not config['retune'] and config['folds'] == [0,1,2] and config['expected_fits'] == 90, 'Design mismatch')
    require(config['scenarios'] == {'pc':['all_price','include_software','no_demo_exception'], 'mobile':['four_tiers']}, 'Scenario mismatch')
    policy = read(ROOT / 'config/feature_policy_v1.json')
    tables = {name[:-4]:pd.read_csv(REPORT / name, keep_default_na=False) for name in run['outputs'] if name.endswith('.csv')}
    lengths = {'cohort_counts':4, 'cohort_class_support':39, 'metadata_coverage':39, 'fold_metrics':270, 'cv_summary':90,
        'matched_comparison':30, 'family_comparison':33, 'pooled_oof_metrics':90, 'per_class':276, 'confusion_matrices':852, 'subgroups':342}
    for name, n in lengths.items():
        require(len(tables[name]) == n, f'Wrong {name} count: {len(tables[name])} vs {n}')
    audit = read(REPORT / 'preprocessing_audit.json')
    require(len(audit) == 90 and len(run['artifacts']) == 274, 'Incomplete artifacts/audit')
    checked = matched_checked = replayed = fold_count = subgroup_count = data_cells = 0
    cache = {}
    for platform, scenarios in config['scenarios'].items():
        for scenario in scenarios:
            data, primary, ledger = reconstruct(platform, scenario, policy)
            labels = sorted(data.target_tier.unique().tolist())
            data_cells += data.size
            c = row_for(tables['cohort_counts'], platform=platform, scenario=scenario)
            expected = {'ledger_train_n':len(ledger), 'ledger_unknown_target_n':int(ledger.exclude_unknown_target.sum()),
                'ledger_unknown_developer_n':int(ledger.exclude_unknown_developer.sum()), 'primary_train_n':len(primary),
                'eligible_n':len(data), 'eligible_groups':data.developer_group.nunique(), 'common_n':int(data.app_id.isin(primary.app_id).sum()),
                'added_n':int((~data.app_id.isin(primary.app_id)).sum()), 'removed_n':int((~primary.app_id.isin(data.app_id)).sum()), 'class_count':len(labels)}
            for field, value in expected.items():
                require(c[field] == value, f'Cohort {field}')
            for column in policy[platform]['P+A']:
                row = row_for(tables['metadata_coverage'], platform=platform, scenario=scenario, column=column)
                require(row.n == len(data) and row.null_n == data[column].isna().sum(), 'Metadata coverage')
            for fold in config['folds']:
                for label in labels:
                    row = row_for(tables['cohort_class_support'], platform=platform, scenario=scenario, fold=fold, tier=label)
                    require(row.n == (data.cv_fold.eq(fold) & data.target_tier.eq(label)).sum(), 'Class/fold support')
            for spec in config['candidates'][platform]:
                prefix = dict(platform=platform, scenario=scenario, configuration=spec['source_configuration'], family=spec['family'], features=spec['features'])
                source_version, source_date = ('model_tree_v1','2026-10-10') if spec['family'] == 'forest' else ('model_dev_v1','2026-10-07')
                source_report = ROOT / f'reports/{source_date}/{source_version}'
                source_manifest = read(source_report / 'run_manifest.json')
                choices = read(source_report / 'development_choices.json')
                require(any(c['platform'] == platform and c['features'] == spec['features'] and c['configuration'] == spec['source_configuration'] for c in choices), 'Retuned candidate')
                modes, fold_scores = {}, {}
                for fold in config['folds']:
                    fit, valid = data.loc[data.cv_fold.ne(fold)], data.loc[data.cv_fold.eq(fold)]
                    stem = f"{platform}__{scenario}__{spec['source_configuration']}__fold{fold}"
                    info = read(ARTIFACTS / f'{stem}.json')
                    for k, v in {**prefix, 'spec':spec, 'fold':fold, 'labels':labels, 'fit_n':len(fit), 'validation_n':len(valid),
                        'fit_groups':fit.developer_group.nunique(), 'validation_groups':valid.developer_group.nunique(),
                        'fit_ids_sha256':id_hash(fit.app_id), 'validation_ids_sha256':id_hash(valid.app_id),
                        'data_sha256':digest(ARTIFACTS / f'{platform}__{scenario}__data.parquet')}.items():
                        require(info[k] == v, f'Checkpoint {k}')
                    require(set(fit.app_id).isdisjoint(valid.app_id) and set(fit.developer_group).isdisjoint(valid.developer_group), 'Fold leakage')
                    pred_path, model_path = ARTIFACTS / f'{stem}.parquet', ARTIFACTS / f'{stem}.joblib'
                    require(info['prediction_sha256'] == digest(pred_path) and info['model_sha256'] == digest(model_path), 'Checkpoint hashes')
                    frame = pd.read_parquet(pred_path)
                    check_membership(frame, valid)
                    source_path = ROOT / f"data/processed/{source_version}/{platform}__{spec['source_configuration']}__fold{fold}.parquet"
                    source_info_path = source_path.with_suffix('.json')
                    require(digest(source_path) == source_manifest['artifacts'][source_path.relative_to(ROOT).as_posix()] == info['source_prediction_sha256'], 'Source predictions hash')
                    require(digest(source_info_path) == source_manifest['artifacts'][source_info_path.relative_to(ROOT).as_posix()], 'Source metadata hash')
                    source_info = read(source_info_path)
                    require(source_info['features'] == spec['features'] and source_info['weight'] == (spec.get('weight') or 'none'), 'Source features/weight')
                    for parameter in ('C','max_leaf_nodes'):
                        if parameter in spec:
                            require(source_info[parameter] == spec[parameter], 'Changed hyperparameter')
                    original = pd.read_parquet(source_path)
                    if platform == 'pc' and scenario == 'no_demo_exception' and fold == 0:
                        require(info['fit_ids_sha256'] == source_info['fit_ids_sha256'], 'Unchanged-fit control membership')
                        old_common = original.set_index('app_id').loc[frame.app_id, ['p0','p1','p2']].to_numpy()
                        require(np.allclose(frame[['p0','p1','p2']].to_numpy(), old_common, atol=1e-10, rtol=1e-10), 'Unchanged-fit control predictions')
                    parts = independent_modes(platform, frame, original, primary, labels)
                    for mode, (part, active_labels) in parts.items():
                        scores, _, _ = calculate(part, active_labels)
                        stored = row_for(tables['fold_metrics'], **prefix, mode_name=mode, fold=fold)
                        require(stored.validation_n == len(part) and stored.class_count == len(active_labels), 'Fold denominator/classes')
                        for m, value in scores.items():
                            close(value, stored[m], 'Fold arithmetic')
                            if mode in ('scope_refit','four_tier_refit'):
                                close(value, info['scores'][m], 'Checkpoint score')
                        modes.setdefault(mode, []).append(part)
                        fold_scores.setdefault(mode, []).append(scores)
                    model = joblib.load(model_path)
                    replay = verify_model(model, fit, valid, spec, info, config, policy, labels, cache, (platform, scenario, spec['features'], fold))
                    sample = valid.iloc[np.linspace(0,len(valid)-1,min(12,len(valid)),dtype=int)]
                    saved = frame.set_index('app_id').loc[sample.app_id, [f'p{i}' for i in range(len(labels))]].to_numpy()
                    require(np.allclose(replay, saved, atol=1e-10, rtol=1e-10), 'Saved model replay')
                    require([r for r in audit if all(r[k] == v for k,v in prefix.items()) and r['fold'] == fold] == [info], 'Audit mismatch')
                    checked += len(frame)
                    matched_checked += len(parts['primary_common' if platform == 'pc' else 'primary_three'][0])
                    replayed += len(sample)
                    fold_count += 1
                for mode, frames in modes.items():
                    joined = pd.concat(frames, ignore_index=True)
                    active_labels = THREE if platform == 'mobile' and mode != 'four_tier_refit' else labels
                    membership = data if platform == 'mobile' or mode == 'scope_refit' else data.loc[data.is_primary]
                    if platform == 'mobile' and mode != 'four_tier_refit':
                        membership = primary
                    check_membership(joined, membership)
                    key = {**prefix, 'mode_name':mode}
                    summary = row_for(tables['cv_summary'], **key)
                    require(summary.folds == 3 and summary.n == len(joined) and summary.class_count == len(active_labels), 'Summary support')
                    for m in METRICS:
                        close(np.mean([s[m] for s in fold_scores[mode]]), summary[f'{m}_mean'], 'Mean-fold arithmetic')
                    close(np.std([s['macro_f1'] for s in fold_scores[mode]], ddof=1), summary.macro_f1_sd, 'Fold SD')
                    scores, cm, class_values = calculate(joined, active_labels)
                    pooled = row_for(tables['pooled_oof_metrics'], **key)
                    require(pooled.n == len(joined), 'Pooled denominator')
                    for m, value in scores.items():
                        close(value, pooled[m], 'Pooled arithmetic')
                    for i, label in enumerate(active_labels):
                        row = row_for(tables['per_class'], **key, tier=label)
                        for name, values in zip(('precision','recall','f1','support'), class_values):
                            close(values[i], row[name], 'Per-class arithmetic')
                        for j, predicted in enumerate(active_labels):
                            row = row_for(tables['confusion_matrices'], **key, true_tier=label, predicted_tier=predicted)
                            require(row['count'] == cm[i,j], 'Confusion arithmetic')
                    subgroup_count += verify_subgroups(tables['subgroups'], joined, data, active_labels, key)
                comparison = row_for(tables['matched_comparison'], **prefix)
                for suffix, mode in [('refit','refit_common_primary' if platform == 'pc' else 'collapsed_three_refit'),
                                     ('primary','primary_common' if platform == 'pc' else 'primary_three')]:
                    row = row_for(tables['cv_summary'], **prefix, mode_name=mode)
                    require(comparison.n == row.n and comparison[f'{suffix}_mode'] == mode, 'Comparison denominator/mode')
                    for m in METRICS:
                        close(row[f'{m}_mean'], comparison[f'{m}_{suffix}'], 'Comparison summary')
                for m in METRICS:
                    close(comparison[f'{m}_refit'] - comparison[f'{m}_primary'], comparison[f'{m}_refit_minus_primary'], 'Matched delta')
                print(f"Verified {platform} {scenario}: {spec['source_configuration']}", flush=True)
    for r in tables['family_comparison'].itertuples():
        values = {}
        for family in ('linear','forest'):
            row = row_for(tables['cv_summary'], platform=r.platform, scenario=r.scenario, features=r.features, mode_name=r.mode_name, family=family)
            values[family] = row.macro_f1_mean
            close(values[family], getattr(r, f'{family}_macro_f1'), 'Family score')
        close(values['forest']-values['linear'], r.forest_minus_linear, 'Family difference')
    require(fold_count == run['fitted_folds'] == 90 and run['configurations'] == 30 and subgroup_count == 342, 'Incomplete verification')
    result = {'status':'passed', 'configurations':30, 'folds_checked':fold_count, 'reconstructed_data_cells':data_cells,
        'refit_prediction_rows_checked':checked, 'matched_primary_rows_checked':matched_checked,
        'model_replay_rows':replayed, 'subgroup_rows_checked':subgroup_count,
        'checks':['frozen source/dependency/artifact hashes', 'independent complete cohort/feature/target reconstruction',
            'inherited train/group/fold membership and no heldout leakage', 'fixed selected hyperparameters and fit-only preprocessing',
            'independent NumPy fold/pooled/class/confusion/subgroup arithmetic', 'matched PC and collapsed Mobile comparisons',
            'family deltas, unchanged-fit control and saved pipeline replay'], 'calibration_evaluated':False, 'test_evaluated':False,
        'run_manifest_sha256':digest(REPORT / 'run_manifest.json'), 'verifier_sha256':digest(Path(__file__)),
        'model_check_helper_sha256':digest(ROOT / 'src/models/verify_age_sensitivity.py')}
    (REPORT / 'verification.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    main()
