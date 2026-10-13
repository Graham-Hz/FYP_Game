"""Fixed-setting, train-only cohort/target sensitivity with resumable fold artifacts."""
import time
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal
from sklearn.metrics import confusion_matrix, precision_recall_fscore_support

from run_age_sensitivity import (ROOT, METRICS, atomic_json, check_hashes, digest, id_hash,
    identity as source_identity, read_json, source_directory, validate_candidates,
    fit_model, matched_reference, metrics)
from run_tree_development import validate_train
from scope_data_v1 import build, collapse, THREE, FOUR

CONFIG = ROOT / 'config/model_scope_v1.json'
REPORT = ROOT / 'reports/2026-10-13/model_scope_v1'
ARTIFACTS = ROOT / 'data/processed/model_scope_v1'
KEYS = ['platform', 'scenario', 'configuration', 'family', 'features']


def identity():
    base = source_identity()
    analysis = read_json(ROOT / 'reports/2026-10-06/analysis_v1/manifest.json')
    extra_inputs = {p: sha for p, sha in analysis['inputs'].items() if p.endswith('_candidates.parquet')}
    extra_inputs.update({p: sha for p, sha in analysis['outputs'].items() if p.endswith('_cohort_ledger.parquet')})
    check_hashes(ROOT, extra_inputs)
    extra = ['config/model_scope_v1.json', 'src/models/scope_data_v1.py',
             'src/models/run_scope_sensitivity.py', 'reports/planning/model_scope_v1_protocol.md']
    return {**base, 'inputs': {**base['inputs'], **extra_inputs},
            'dependencies': {**base['dependencies'], **{p: digest(ROOT / p) for p in extra}}}


def score(frame, labels):
    return metrics(frame.target_tier, frame[[f'p{i}' for i in range(len(labels))]].to_numpy(), labels)[0]


def evaluation_frames(platform, frame, original, primary):
    if platform == 'pc':
        common = frame.loc[frame.app_id.isin(primary.app_id)]
        reference = matched_reference(original, common)
        return {'scope_refit': frame, 'refit_common_primary': common, 'primary_common': reference}
    collapsed = collapse(frame)
    reference = matched_reference(original, collapsed)
    return {'four_tier_refit': frame, 'collapsed_three_refit': collapsed, 'primary_three': reference}


def labels_for(platform, mode, labels):
    return THREE if platform == 'mobile' and mode != 'four_tier_refit' else labels


def subgroup_records(frame, data, labels, prefix):
    columns = ['free'] if prefix['platform'] == 'mobile' else ['is_primary', 'exclude_software_only_heuristic']
    joined = frame.merge(data[['app_id'] + columns], on='app_id', validate='one_to_one')
    if prefix['platform'] == 'mobile':
        groups = [('free', joined.free.eq(True).fillna(False)), ('paid', joined.free.eq(False).fillna(False)),
                  ('unknown', joined.free.isna())]
    else:
        groups = [('original_primary', joined.is_primary), ('added_only', ~joined.is_primary),
                  ('software_only', joined.exclude_software_only_heuristic), ('other', ~joined.exclude_software_only_heuristic)]
    rows = []
    for name, mask in groups:
        part = joined.loc[mask]
        rows.append({**prefix, 'subgroup': name, 'n': len(part), 'class_count': len(labels),
                     'classes_present': part.target_tier.nunique(),
                     **{f'support_{i}': int(part.target_tier.eq(label).sum()) for i, label in enumerate(labels)},
                     **(score(part, labels) if len(part) else {metric: None for metric in METRICS})})
    return rows


def comparisons(summary):
    rows = []
    for values, group in summary.groupby(KEYS, sort=False):
        platform = values[0]
        refit_mode, primary_mode = ('refit_common_primary', 'primary_common') if platform == 'pc' else ('collapsed_three_refit', 'primary_three')
        refit, original = (group.loc[group.mode_name.eq(mode)].iloc[0] for mode in (refit_mode, primary_mode))
        if refit.n != original.n:
            raise ValueError('Unmatched comparison denominator')
        rows.append({**dict(zip(KEYS, values)), 'n': int(refit.n), 'refit_mode': refit_mode, 'primary_mode': primary_mode,
            **{f'{m}_{suffix}': row[f'{m}_mean'] for m in METRICS for suffix, row in [('refit', refit), ('primary', original)]},
            **{f'{m}_refit_minus_primary': refit[f'{m}_mean'] - original[f'{m}_mean'] for m in METRICS}})
    families = []
    for values, group in summary.groupby(['platform', 'scenario', 'features', 'mode_name'], sort=False):
        if set(group.family) != {'linear', 'forest'}:
            continue
        linear, forest = (group.loc[group.family.eq(f)].iloc[0] for f in ('linear', 'forest'))
        families.append({**dict(zip(['platform', 'scenario', 'features', 'mode_name'], values)),
            'linear_macro_f1': linear.macro_f1_mean, 'forest_macro_f1': forest.macro_f1_mean,
            'forest_minus_linear': forest.macro_f1_mean - linear.macro_f1_mean})
    return pd.DataFrame(rows), pd.DataFrame(families)


def main():
    config = read_json(CONFIG)
    current = identity()
    validate_candidates(config)
    REPORT.mkdir(parents=True, exist_ok=True)
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    run_path = REPORT / 'run_manifest.json'
    if run_path.exists():
        old = read_json(run_path)
        if old['identity'] != current:
            raise ValueError('Changed run identity; use a new version')
        if old['status'] == 'complete':
            check_hashes(REPORT, old['outputs'])
            check_hashes(ROOT, old['artifacts'])
            print(f"Verified completed run: skipped {old['fitted_folds']} fits; no files rewritten.", flush=True)
            return
    else:
        atomic_json(run_path, {'status': 'running', 'started_utc': datetime.now(timezone.utc).isoformat(),
            'identity': current, 'partition': 'train', 'calibration_evaluated': False, 'test_evaluated': False})
    folds, pooled, classes, matrices, subgroups, audit, cohorts, support, coverage = [], [], [], [], [], [], [], [], []
    for platform, scenarios in config['scenarios'].items():
        for scenario in scenarios:
            data, primary = build(platform, scenario)
            validate_train(data, config['folds'])
            labels = sorted(data.target_tier.unique().tolist())
            if platform == 'mobile' and labels != FOUR:
                raise ValueError('Incorrect four-tier ordering')
            data_path = ARTIFACTS / f'{platform}__{scenario}__data.parquet'
            if data_path.exists():
                assert_frame_equal(pd.read_parquet(data_path), data)
            else:
                tmp = data_path.with_suffix('.parquet.tmp')
                data.to_parquet(tmp, index=False)
                tmp.replace(data_path)
            ledger = pd.read_parquet(ROOT / f'data/processed/analysis_v1/{platform}_cohort_ledger.parquet')
            ledger = ledger.loc[ledger.assigned_split.eq('train')]
            cohorts.append({'platform': platform, 'scenario': scenario, 'ledger_train_n': len(ledger),
                'ledger_unknown_target_n': int(ledger.exclude_unknown_target.sum()),
                'ledger_unknown_developer_n': int(ledger.exclude_unknown_developer.sum()),
                'primary_train_n': len(primary), 'eligible_n': len(data), 'eligible_groups': data.developer_group.nunique(),
                'common_n': int(data.app_id.isin(primary.app_id).sum()), 'added_n': int((~data.app_id.isin(primary.app_id)).sum()),
                'removed_n': int((~primary.app_id.isin(data.app_id)).sum()), 'class_count': len(labels)})
            for column in read_json(ROOT / 'config/feature_policy_v1.json')[platform]['P+A']:
                coverage.append({'platform': platform, 'scenario': scenario, 'column': column,
                                 'n': len(data), 'null_n': int(data[column].isna().sum())})
            for fold in config['folds']:
                for label in labels:
                    support.append({'platform': platform, 'scenario': scenario, 'fold': fold, 'tier': label,
                                    'n': int((data.cv_fold.eq(fold) & data.target_tier.eq(label)).sum())})
            for spec in config['candidates'][platform]:
                prefix = dict(platform=platform, scenario=scenario, configuration=spec['source_configuration'],
                              family=spec['family'], features=spec['features'])
                predictions = {}
                for fold in config['folds']:
                    fit, valid = data.loc[data.cv_fold.ne(fold)], data.loc[data.cv_fold.eq(fold)]
                    if set(fit.developer_group) & set(valid.developer_group) or set(fit.target_tier) != set(labels) or set(valid.target_tier) != set(labels):
                        raise ValueError('Invalid group/class support')
                    stem = f"{platform}__{scenario}__{spec['source_configuration']}__fold{fold}"
                    info_path, pred_path, model_path = [ARTIFACTS / f'{stem}.{ext}' for ext in ('json', 'parquet', 'joblib')]
                    source_path = source_directory(spec) / f"{platform}__{spec['source_configuration']}__fold{fold}.parquet"
                    original = pd.read_parquet(source_path)
                    if info_path.exists():
                        info = read_json(info_path)
                        expected = {**prefix, 'spec': spec, 'fold': fold, 'labels': labels, 'data_sha256': digest(data_path),
                            'fit_ids_sha256': id_hash(fit.app_id), 'validation_ids_sha256': id_hash(valid.app_id),
                            'prediction_sha256': digest(pred_path), 'model_sha256': digest(model_path),
                            'source_prediction_sha256': digest(source_path)}
                        if any(info[k] != v for k, v in expected.items()):
                            raise ValueError('Changed scope checkpoint')
                        frame = pd.read_parquet(pred_path)
                        print(f'Resume {stem}', flush=True)
                    else:
                        print(f'Fitting {stem}: {len(fit)} fit / {len(valid)} validation rows', flush=True)
                        started = time.perf_counter()
                        model, probabilities, extra = fit_model(fit, valid, platform, spec, config)
                        if list(model.classes_) != labels:
                            raise ValueError('Class order mismatch')
                        scores, predicted = metrics(valid.target_tier, probabilities, labels)
                        frame = valid[['app_id', 'developer_group', 'cv_fold', 'target_tier']].copy()
                        frame['predicted_tier'] = predicted
                        for i in range(len(labels)):
                            frame[f'p{i}'] = probabilities[:, i]
                        tmp = pred_path.with_suffix('.parquet.tmp')
                        frame.to_parquet(tmp, index=False)
                        tmp.replace(pred_path)
                        tmp = model_path.with_suffix('.joblib.tmp')
                        joblib.dump(model, tmp, compress=1)
                        tmp.replace(model_path)
                        info = {**prefix, 'spec': spec, 'fold': fold, 'fit_n': len(fit), 'validation_n': len(valid),
                            'fit_groups': fit.developer_group.nunique(), 'validation_groups': valid.developer_group.nunique(),
                            'fit_ids_sha256': id_hash(fit.app_id), 'validation_ids_sha256': id_hash(valid.app_id),
                            'labels': labels, 'scores': scores, 'seconds': time.perf_counter() - started, **extra,
                            'data_sha256': digest(data_path), 'prediction_sha256': digest(pred_path),
                            'model_sha256': digest(model_path), 'source_prediction_sha256': digest(source_path)}
                        atomic_json(info_path, info)
                        print(f"{stem}: macro-F1={scores['macro_f1']:.4f}; {info['seconds']:.1f}s", flush=True)
                    audit.append(info)
                    for mode, part in evaluation_frames(platform, frame, original, primary).items():
                        active_labels = labels_for(platform, mode, labels)
                        predictions.setdefault(mode, []).append(part)
                        folds.append({**prefix, 'mode_name': mode, 'class_count': len(active_labels), 'fold': fold,
                                      'validation_n': len(part), **score(part, active_labels)})
                for mode, frames in predictions.items():
                    joined = pd.concat(frames, ignore_index=True)
                    expected_ids = data.app_id if platform == 'mobile' or mode == 'scope_refit' else data.loc[data.is_primary, 'app_id']
                    if joined.app_id.duplicated().any() or set(joined.app_id) != set(expected_ids):
                        raise ValueError('Incomplete OOF coverage')
                    active_labels = labels_for(platform, mode, labels)
                    record = {**prefix, 'mode_name': mode, 'class_count': len(active_labels)}
                    pooled.append({**record, 'n': len(joined), **score(joined, active_labels)})
                    p, r, f, n = precision_recall_fscore_support(joined.target_tier, joined.predicted_tier, labels=active_labels, zero_division=0)
                    cm = confusion_matrix(joined.target_tier, joined.predicted_tier, labels=active_labels)
                    for i, label in enumerate(active_labels):
                        classes.append({**record, 'tier': label, 'precision': p[i], 'recall': r[i], 'f1': f[i], 'support': int(n[i])})
                        for j, predicted_label in enumerate(active_labels):
                            matrices.append({**record, 'true_tier': label, 'predicted_tier': predicted_label, 'count': int(cm[i, j])})
                    subgroups += subgroup_records(joined, data, active_labels, record)
    fold_table = pd.DataFrame(folds)
    summary = fold_table.groupby(KEYS + ['mode_name', 'class_count'], sort=False).agg(
        folds=('fold', 'count'), n=('validation_n', 'sum'), macro_f1_sd=('macro_f1', 'std'),
        **{f'{m}_mean': (m, 'mean') for m in METRICS}).reset_index()
    if len(audit) != config['expected_fits'] or len(summary) != 90 or not summary.folds.eq(3).all():
        raise ValueError('Incomplete experiment matrix')
    matched, families = comparisons(summary)
    outputs = {'cohort_counts': pd.DataFrame(cohorts), 'cohort_class_support': pd.DataFrame(support),
        'metadata_coverage': pd.DataFrame(coverage), 'fold_metrics': fold_table, 'cv_summary': summary,
        'matched_comparison': matched, 'family_comparison': families, 'pooled_oof_metrics': pd.DataFrame(pooled),
        'per_class': pd.DataFrame(classes), 'confusion_matrices': pd.DataFrame(matrices), 'subgroups': pd.DataFrame(subgroups)}
    for name, table in outputs.items():
        tmp = REPORT / f'{name}.csv.tmp'
        table.to_csv(tmp, index=False, encoding='utf-8-sig')
        tmp.replace(REPORT / f'{name}.csv')
    atomic_json(REPORT / 'preprocessing_audit.json', audit)
    run = read_json(run_path)
    run.update(status='complete', completed_utc=datetime.now(timezone.utc).isoformat(), configurations=30,
        fitted_folds=len(audit), outputs={name: digest(REPORT / name) for name in [*[f'{n}.csv' for n in outputs], 'preprocessing_audit.json']},
        artifacts={p.relative_to(ROOT).as_posix(): digest(p) for p in ARTIFACTS.iterdir() if p.suffix in ('.json', '.parquet', '.joblib')})
    atomic_json(run_path, run)
    print('Completed 30 scope/model combinations / 90 fits. Calibration/test not evaluated.', flush=True)


if __name__ == '__main__':
    main()
