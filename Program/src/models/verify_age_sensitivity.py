"""Independent age eligibility, matched-OOF arithmetic, refit provenance and replay checks."""
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from preprocessing import NUMERIC, PlanningEncoder
from verify_development import calculate, digest, id_hash, require

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "reports/2026-10-11/model_age_v1"
ARTIFACTS = ROOT / "data/processed/model_age_v1"
METRICS = ("macro_f1", "balanced_accuracy", "accuracy", "log_loss", "brier")


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def row_for(table, **keys):
    mask = pd.Series(True, index=table.index)
    for column, value in keys.items():
        mask &= table[column].eq(value)
    found = table.loc[mask]
    require(len(found) == 1, f"Missing/duplicate table row: {keys}")
    return found.iloc[0]


def close(actual, expected, message):
    require(abs(float(actual) - float(expected)) < 1e-9, message)


def check_membership(frame, valid):
    require(not frame.app_id.duplicated().any() and set(frame.app_id) == set(valid.app_id), "Wrong validation membership")
    joined = frame.merge(valid[["app_id", "target_tier", "developer_group", "cv_fold"]], on="app_id",
                         suffixes=("", "_source"), validate="one_to_one")
    for column in ("target_tier", "developer_group", "cv_fold"):
        require(joined[column].eq(joined[column + "_source"]).all(), f"Wrong {column}")


def verify_model(model, fit, valid, spec, info, config, policy, labels, vocabulary_cache, cache_key):
    require(list(model.classes_) == labels, "Class order")
    if spec["family"] == "prior":
        require(type(model).__name__ == "DummyClassifier" and model.strategy == "prior", "Wrong prior estimator")
        require(np.allclose(model.class_prior_, fit.target_tier.value_counts(normalize=True).reindex(labels)), "Wrong age-fold class prior")
        return model.predict_proba(np.zeros((min(12, len(valid)), 1)))
    encoder, estimator = model.named_steps["encoder"], model.named_steps["model"]
    require(encoder.columns_ == policy[cache_key[0]][spec["features"]], "Predictor allowlist")
    for name in encoder.get_feature_names_out():
        require(json.loads(name)[1] in encoder.columns_, "Unexpected predictor")
    if cache_key not in vocabulary_cache:
        reference = PlanningEncoder(cache_key[0], spec["features"]).fit(fit)
        vocabulary_cache[cache_key] = reference.vectorizer_.vocabulary_
    require(encoder.vectorizer_.vocabulary_ == vocabulary_cache[cache_key], "Vocabulary includes non-fit-cohort tokens")
    for column in set(encoder.columns_) & NUMERIC:
        values = np.log1p(fit[column].to_numpy(dtype=float, na_value=np.nan))
        median = np.nanmedian(values) if np.isfinite(values).any() else 0.0
        values = np.where(np.isnan(values), median, values)
        expected = {"median": median, "mean": values.mean(), "std": values.std() if values.std() > 0 else 1.0}
        for stat, value in expected.items():
            close(value, encoder.numeric_stats_[column][stat], "Numeric statistics not age-fit-only")
            close(value, info["numeric_stats"][column][stat], "Wrong numeric audit")
    if spec["family"] == "forest":
        require(type(estimator).__name__ == "RandomForestClassifier", "Wrong forest family")
        settings = read(ROOT / config["forest_settings_from"])
        expected = {**settings["estimator"], "max_leaf_nodes": spec["max_leaf_nodes"],
                    "class_weight": spec["weight"], "random_state": config["seed"], "n_jobs": config["threads"]}
        require(len(estimator.estimators_) == settings["estimator"]["n_estimators"], "Wrong number of trees")
        require(all(t.get_depth() <= settings["estimator"]["max_depth"] and t.get_n_leaves() <= spec["max_leaf_nodes"]
                    for t in estimator.estimators_), "Tree complexity bounds")
    else:
        require(type(estimator).__name__ == "LogisticRegression", "Wrong linear family")
        settings = read(ROOT / config["linear_settings_from"])
        require(info["convergence_retries"] in (0, 1), "Unprescribed retry count")
        iterations = settings["max_iter"] if info["convergence_retries"] == 0 else settings["convergence_retry_max_iter"]
        expected = {"C": spec["C"], "class_weight": spec["weight"], "solver": settings["solver"],
                    "l1_ratio": settings["l1_ratio"], "tol": settings["tol"], "max_iter": iterations, "random_state": config["seed"]}
    for key, value in expected.items():
        require(estimator.get_params()[key] == value and info["estimator_params"][key] == value, f"Wrong estimator parameter: {key}")
    sample = valid.iloc[np.linspace(0, len(valid) - 1, min(12, len(valid)), dtype=int)]
    return model.predict_proba(sample)


def main():
    run = read(REPORT / "run_manifest.json")
    require(run["status"] == "complete" and run["partition"] == "train" and
            not run["calibration_evaluated"] and not run["test_evaluated"], "Not a complete train-only experiment")
    analysis_path = ROOT / "reports/2026-10-06/analysis_v1/manifest.json"
    require(digest(analysis_path) == run["identity"]["analysis_manifest_sha256"], "Changed analysis manifest")
    for mapping in (run["identity"]["inputs"], run["identity"]["dependencies"], read(analysis_path)["dependencies"], run["artifacts"]):
        for relative, sha in mapping.items():
            require(digest(ROOT / relative) == sha, f"Changed input/code/artifact: {relative}")
    for name, sha in run["outputs"].items():
        require(digest(REPORT / name) == sha, f"Changed report: {name}")
    config = read(ROOT / "config/model_age_v1.json")
    require(not config["retune"] and config["minimum_age_days"] == [180, 365] and config["folds"] == [0, 1, 2], "Design changed")
    policy = read(ROOT / "config/feature_policy_v1.json")
    tables = {name: pd.read_csv(REPORT / f"{name}.csv", keep_default_na=False) for name in (
        "cohort_counts", "cohort_class_support", "fold_metrics", "cv_summary", "matched_comparison", "family_comparison",
        "pooled_oof_metrics", "per_class", "confusion_matrices", "mobile_subgroups")}
    expected_lengths = {"cohort_counts": 4, "cohort_class_support": 36, "fold_metrics": 168, "cv_summary": 56,
                        "matched_comparison": 28, "family_comparison": 10, "pooled_oof_metrics": 56, "per_class": 168,
                        "confusion_matrices": 504, "mobile_subgroups": 72}
    for table, n in expected_lengths.items():
        require(len(tables[table]) == n, f"Wrong {table} row count")
    audit = read(REPORT / "preprocessing_audit.json")
    require(len(audit) == 84 and len(run["artifacts"]) == 252, "Incomplete checkpoint matrix")
    checked, matched_checked, replayed, folds_checked, subgroup_checked = 0, 0, 0, 0, 0
    vocabulary_cache = {}
    for platform, specs in config["candidates"].items():
        all_labels = pd.read_parquet(ROOT / f"data/processed/analysis_v1/{platform}_labels_splits.parquet")
        train_labels = all_labels.loc[all_labels.split.eq("train")]
        data = pd.read_parquet(ROOT / f"data/processed/analysis_v1/{platform}_features.parquet").merge(
            train_labels, on="app_id", validate="one_to_one").sort_values("app_id").reset_index(drop=True)
        labels = sorted(data.target_tier.unique().tolist())
        require(data.groupby("developer_group").cv_fold.nunique().max() == 1, "Source group crosses folds")
        heldout_ids = set(all_labels.loc[~all_labels.split.eq("train"), "app_id"])
        for cutoff in config["minimum_age_days"]:
            subset = data.loc[data.age_days.notna() & (data.age_days >= cutoff)]
            c_row = row_for(tables["cohort_counts"], platform=platform, minimum_age_days=cutoff)
            expected = {"primary_train_n": len(data), "eligible_n": len(subset), "excluded_n": len(data) - len(subset),
                        "missing_age_n": data.age_days.isna().sum(), "below_cutoff_n": data.age_days.lt(cutoff).sum(),
                        "eligible_groups": subset.developer_group.nunique()}
            for key, value in expected.items():
                require(c_row[key] == value, f"Wrong cohort {key}")
            for fold in config["folds"]:
                for label in labels:
                    r = row_for(tables["cohort_class_support"], platform=platform, minimum_age_days=cutoff, fold=fold, tier=label)
                    require(r.n == (subset.cv_fold.eq(fold) & subset.target_tier.eq(label)).sum(), "Wrong cohort class support")
            for spec in specs:
                prefix = {"platform": platform, "minimum_age_days": cutoff, "configuration": spec["source_configuration"],
                          "family": spec["family"], "features": spec["features"]}
                modes = {"age_refit": [], "primary_fit_same_rows": []}
                scores_by_mode = {key: [] for key in modes}
                source_version = "model_tree_v1" if spec["family"] == "forest" else "model_dev_v1"
                source_date = "2026-10-10" if spec["family"] == "forest" else "2026-10-07"
                source_report = ROOT / f"reports/{source_date}/{source_version}"
                source_manifest = read(source_report / "run_manifest.json")
                choices = read(source_report / "development_choices.json")
                require(any(c["platform"] == platform and c["features"] == spec["features"] and
                            c["configuration"] == spec["source_configuration"] for c in choices), "Retuned candidate")
                for fold in config["folds"]:
                    fit, valid = subset.loc[subset.cv_fold.ne(fold)], subset.loc[subset.cv_fold.eq(fold)]
                    stem = f"{platform}__age{cutoff}__{spec['source_configuration']}__fold{fold}"
                    info = read(ARTIFACTS / f"{stem}.json")
                    require(info["spec"] == spec and info["minimum_age_days"] == cutoff and info["fold"] == fold and
                            info["platform"] == platform and info["labels"] == labels, "Wrong fold identity")
                    require(info["fit_ids_sha256"] == id_hash(fit.app_id) and info["validation_ids_sha256"] == id_hash(valid.app_id), "Wrong age-fit IDs")
                    require(info["fit_n"] == len(fit) and info["validation_n"] == len(valid) and
                            info["fit_groups"] == fit.developer_group.nunique() and info["validation_groups"] == valid.developer_group.nunique(), "Wrong fold support")
                    require(set(fit.developer_group).isdisjoint(valid.developer_group) and set(fit.app_id).isdisjoint(valid.app_id), "Fit/validation leakage")
                    require(set(fit.app_id).isdisjoint(heldout_ids) and set(valid.app_id).isdisjoint(heldout_ids), "Holdout used")
                    pred_path, model_path = ARTIFACTS / f"{stem}.parquet", ARTIFACTS / f"{stem}.joblib"
                    require(info["prediction_sha256"] == digest(pred_path) and info["model_sha256"] == digest(model_path), "Checkpoint hashes")
                    frame = pd.read_parquet(pred_path)
                    check_membership(frame, valid)
                    source_path = ROOT / f"data/processed/{source_version}/{platform}__{spec['source_configuration']}__fold{fold}.parquet"
                    source_info_path = source_path.with_suffix(".json")
                    require(digest(source_info_path) == source_manifest["artifacts"][source_info_path.relative_to(ROOT).as_posix()], "Changed source metadata")
                    source_info = read(source_info_path)
                    require(source_info["features"] == spec["features"] and
                            source_info["weight"] == (spec.get("weight") or "none"), "Changed source feature/weight setting")
                    for parameter in ("C", "max_leaf_nodes"):
                        if parameter in spec:
                            require(source_info[parameter] == spec[parameter], "Changed source hyperparameter")
                    require(digest(source_path) == source_manifest["artifacts"][source_path.relative_to(ROOT).as_posix()] == info["source_prediction_sha256"], "Changed reference predictions")
                    original = pd.read_parquet(source_path)
                    require(not original.app_id.duplicated().any(), "Duplicate original IDs")
                    original = original.loc[original.app_id.isin(valid.app_id)]
                    check_membership(original, valid)
                    for mode, part, metadata_key in (("age_refit", frame, "scores"), ("primary_fit_same_rows", original, "reference_scores")):
                        scores, _, _ = calculate(part, labels)
                        stored = row_for(tables["fold_metrics"], **prefix, mode_name=mode, fold=fold)
                        require(stored.validation_n == len(part), "Wrong validation denominator")
                        for metric, value in scores.items():
                            close(value, stored[metric], "Fold arithmetic")
                            close(value, info[metadata_key][metric], "Fold metadata arithmetic")
                        modes[mode].append(part)
                        scores_by_mode[mode].append(scores)
                    # Load only this run's own, hash-verified local artifacts.
                    model = joblib.load(model_path)
                    replay = verify_model(model, fit, valid, spec, info, config, policy, labels, vocabulary_cache,
                                          (platform, cutoff, spec["features"], fold))
                    sample = valid.iloc[np.linspace(0, len(valid) - 1, min(12, len(valid)), dtype=int)]
                    saved = frame.set_index("app_id").loc[sample.app_id, ["p0", "p1", "p2"]].to_numpy()
                    require(np.allclose(replay, saved, atol=1e-10, rtol=1e-10), "Saved pipeline replay mismatch")
                    matching_audit = [r for r in audit if all(r[k] == v for k, v in prefix.items()) and r["fold"] == fold]
                    require(len(matching_audit) == 1 and matching_audit[0] == info, "Preprocessing audit mismatch")
                    checked += len(frame)
                    matched_checked += len(original)
                    replayed += len(sample)
                    folds_checked += 1
                for mode, frames in modes.items():
                    joined = pd.concat(frames, ignore_index=True)
                    check_membership(joined, subset)
                    key = {**prefix, "mode_name": mode}
                    summary = row_for(tables["cv_summary"], **key)
                    require(summary.folds == 3 and summary.n == len(joined), "Summary support")
                    for metric in METRICS:
                        close(np.mean([s[metric] for s in scores_by_mode[mode]]), summary[f"{metric}_mean"], "Mean-fold arithmetic")
                    close(np.std([s["macro_f1"] for s in scores_by_mode[mode]], ddof=1), summary.macro_f1_sd, "Fold SD arithmetic")
                    pooled, cm, class_values = calculate(joined, labels)
                    stored = row_for(tables["pooled_oof_metrics"], **key)
                    require(stored.n == len(joined), "Wrong pooled denominator")
                    for metric, value in pooled.items():
                        close(value, stored[metric], "Pooled arithmetic")
                    for i, label in enumerate(labels):
                        stored = row_for(tables["per_class"], **key, tier=label)
                        for metric, values in zip(("precision", "recall", "f1", "support"), class_values):
                            close(values[i], stored[metric], "Per-class arithmetic")
                        for j, predicted in enumerate(labels):
                            stored = row_for(tables["confusion_matrices"], **key, true_tier=label, predicted_tier=predicted)
                            require(stored["count"] == cm[i, j], "Confusion matrix")
                    if platform == "mobile":
                        with_free = joined.merge(subset[["app_id", "free"]], on="app_id", validate="one_to_one")
                        for name, mask in (("free", with_free.free.eq(True).fillna(False)), ("paid", with_free.free.eq(False).fillna(False)), ("unknown", with_free.free.isna())):
                            part = with_free.loc[mask]
                            stored = row_for(tables["mobile_subgroups"], **key, subgroup=name)
                            require(stored.n == len(part) and stored.classes_present == part.target_tier.nunique(), "Subgroup support")
                            for i, label in enumerate(labels):
                                require(stored[f"support_{i}"] == part.target_tier.eq(label).sum(), "Subgroup class support")
                            if len(part):
                                scores, _, _ = calculate(part, labels)
                                close(scores["macro_f1"], stored.macro_f1_fixed_three_labels, "Subgroup F1")
                                close(scores["accuracy"], stored.accuracy, "Subgroup accuracy")
                            else:
                                require(stored.macro_f1_fixed_three_labels == "" and stored.accuracy == "", "Empty subgroup scored")
                            subgroup_checked += 1
                comparison = row_for(tables["matched_comparison"], **prefix)
                for mode, suffix in (("age_refit", "refit"), ("primary_fit_same_rows", "primary")):
                    summary = row_for(tables["cv_summary"], **prefix, mode_name=mode)
                    for field in ("folds", "n", "macro_f1_sd", *[f"{m}_mean" for m in METRICS]):
                        close(summary[field], comparison[f"{field}_{suffix}"], "Matched summary")
                for metric in METRICS:
                    close(comparison[f"{metric}_mean_refit"] - comparison[f"{metric}_mean_primary"],
                          comparison[f"{metric}_refit_minus_primary"], "Matched difference")
                print(f"Verified {platform} age >= {cutoff}: {spec['source_configuration']}", flush=True)
    for r in tables["family_comparison"].itertuples():
        for mode, suffix in (("age_refit", "refit"), ("primary_fit_same_rows", "primary")):
            values = {}
            for family in ("linear", "forest"):
                source = row_for(tables["cv_summary"], platform=r.platform, minimum_age_days=r.minimum_age_days,
                                 features=r.features, family=family, mode_name=mode)
                values[family] = source.macro_f1_mean
                close(values[family], getattr(r, f"{family}_macro_f1_{suffix}"), "Family score")
            close(values["forest"] - values["linear"], getattr(r, f"forest_minus_linear_{suffix}"), "Family difference")
    require(folds_checked == run["fitted_folds"] == 84 and run["configurations"] == 28 and subgroup_checked == 72, "Incomplete verification")
    result = {"status": "passed", "configurations": 28, "folds_checked": folds_checked,
        "refit_prediction_rows_checked": checked, "matched_primary_rows_checked": matched_checked,
        "model_replay_rows": replayed, "mobile_subgroup_rows_checked": subgroup_checked,
        "checks": ["frozen hashes", "age eligibility and unchanged fold assignments", "age-fit-only numeric statistics/vocabulary/priors",
                   "original selected configurations and fixed estimator settings", "train-only group isolation", "matched validation membership",
                   "independent fold/pooled/class/confusion/subgroup metric arithmetic", "matched and family deltas", "saved-model replay"],
        "calibration_evaluated": False, "test_evaluated": False, "run_manifest_sha256": digest(REPORT / "run_manifest.json"),
        "verifier_sha256": digest(Path(__file__)), "arithmetic_helper_sha256": digest(ROOT / "src/models/verify_development.py")}
    (REPORT / "verification.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
