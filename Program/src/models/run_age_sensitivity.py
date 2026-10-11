"""Prespecified age-cohort refits, matched primary-fit comparisons and atomic checkpoints."""
import json
import os
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix, precision_recall_fscore_support
from sklearn.pipeline import Pipeline
from threadpoolctl import threadpool_limits

from preprocessing import PlanningEncoder
from run_development import ROOT, digest, id_hash, metrics
from run_tree_development import load_train, run_identity as tree_identity, subgroup_rows, validate_train

CONFIG = ROOT / "config/model_age_v1.json"
REPORT = ROOT / "reports/2026-10-11/model_age_v1"
ARTIFACTS = ROOT / "data/processed/model_age_v1"
SOURCES = {"linear": ROOT / "reports/2026-10-07/model_dev_v1", "forest": ROOT / "reports/2026-10-10/model_tree_v1"}
METRICS = ("macro_f1", "balanced_accuracy", "accuracy", "log_loss", "brier")
KEYS = ["platform", "minimum_age_days", "configuration", "family", "features"]


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_json(path, value):
    payload = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def check_hashes(base, records):
    for relative, expected in records.items():
        if digest(base / relative) != expected:
            raise ValueError(f"Changed recorded file: {relative}")


def identity():
    base = tree_identity()  # Also checks original analysis and all linear artifacts.
    tree = read_json(SOURCES["forest"] / "run_manifest.json")
    if tree["status"] != "complete" or tree["identity"] != base:
        raise ValueError("Changed/incomplete source forest run")
    check_hashes(SOURCES["forest"], tree["outputs"])
    check_hashes(ROOT, tree["artifacts"])
    for source in SOURCES.values():
        verification = read_json(source / "verification.json")
        if verification["status"] != "passed" or verification["run_manifest_sha256"] != digest(source / "run_manifest.json"):
            raise ValueError("Source verification does not match completed run")
    extra = ["config/model_age_v1.json", "src/models/run_age_sensitivity.py", "reports/planning/model_age_v1_protocol.md"]
    extra += [str((source / name).relative_to(ROOT)).replace("\\", "/") for source in SOURCES.values()
              for name in ("run_manifest.json", "verification.json")]
    return {**base, "dependencies": {**base["dependencies"], **{p: digest(ROOT / p) for p in extra}}}


def source_directory(spec):
    version = "model_tree_v1" if spec["family"] == "forest" else "model_dev_v1"
    return ROOT / "data/processed" / version


def validate_candidates(config):
    for platform, specs in config["candidates"].items():
        if len({s["source_configuration"] for s in specs}) != len(specs):
            raise ValueError("Duplicated candidate")
        for spec in specs:
            report = SOURCES["forest" if spec["family"] == "forest" else "linear"]
            choices = read_json(report / "development_choices.json")
            selected = [c for c in choices if c["platform"] == platform and c["features"] == spec["features"]]
            if len(selected) != 1 or selected[0]["configuration"] != spec["source_configuration"]:
                raise ValueError("Candidate was not the fixed original development choice")
            info = read_json(source_directory(spec) / f"{platform}__{spec['source_configuration']}__fold0.json")
            for field in ("C", "max_leaf_nodes"):
                if field in spec and spec[field] != info[field]:
                    raise ValueError(f"Changed selected {field}")
            if spec.get("weight") != (None if info["weight"] == "none" else info["weight"]):
                raise ValueError("Changed selected class weight")


def age_cohort(data, age, folds):
    validate_train(data, folds)
    if not isinstance(age, int) or age < 0:
        raise ValueError("Age cutoff must be a nonnegative integer")
    subset = data.loc[data.age_days.ge(age).fillna(False)].copy()
    validate_train(subset, folds)
    # Inherited assignments only; no recomputation after exclusions.
    if set(subset.target_tier) != set(data.target_tier):
        raise ValueError("Age cohort lost a target class")
    return subset


def matched_reference(reference, valid):
    if reference.app_id.duplicated().any() or valid.app_id.duplicated().any():
        raise ValueError("Duplicate comparison IDs")
    matched = reference.loc[reference.app_id.isin(valid.app_id)].copy()
    if len(matched) != len(valid) or set(matched.app_id) != set(valid.app_id):
        raise ValueError("Comparison validation IDs do not match")
    joined = matched.merge(valid[["app_id", "developer_group", "cv_fold", "target_tier"]], on="app_id",
                           suffixes=("", "_expected"), validate="one_to_one")
    for column in ("developer_group", "cv_fold", "target_tier"):
        if not joined[column].eq(joined[column + "_expected"]).all():
            raise ValueError(f"Mismatched reference {column}")
    return matched


def fit_model(fit, valid, platform, spec, config):
    messages, retries = [], 0
    if spec["family"] == "prior":
        model = DummyClassifier(strategy="prior").fit(np.zeros((len(fit), 1)), fit.target_tier)
        probabilities = model.predict_proba(np.zeros((len(valid), 1)))
        return model, probabilities, {"n_features": 0, "numeric_stats": {}, "coverage": {},
                                     "convergence_retries": 0, "warnings": [], "estimator_params": model.get_params()}
    encoder = PlanningEncoder(platform, spec["features"])
    with threadpool_limits(limits=config["threads"]):
        xfit, xvalid = encoder.fit_transform(fit), encoder.transform(valid)
        if spec["family"] == "forest":
            settings = read_json(ROOT / config["forest_settings_from"])
            estimator = RandomForestClassifier(**settings["estimator"], max_leaf_nodes=spec["max_leaf_nodes"],
                class_weight=spec["weight"], n_jobs=config["threads"], random_state=config["seed"])
            estimator.fit(xfit, fit.target_tier)
        else:
            settings = read_json(ROOT / config["linear_settings_from"])
            for attempt, iterations in enumerate((settings["max_iter"], settings["convergence_retry_max_iter"])):
                estimator = LogisticRegression(C=spec["C"], class_weight=spec["weight"], solver=settings["solver"],
                    l1_ratio=settings["l1_ratio"], max_iter=iterations, tol=settings["tol"], random_state=config["seed"])
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter("always")
                    estimator.fit(xfit, fit.target_tier)
                messages += [str(w.message) for w in caught]
                retries = attempt
                if not any(issubclass(w.category, ConvergenceWarning) for w in caught):
                    break
            else:
                raise RuntimeError("Age refit failed convergence after prespecified retry")
        probabilities = estimator.predict_proba(xvalid)
    return Pipeline([("encoder", encoder), ("model", estimator)]), probabilities, {
        "n_features": xfit.shape[1], "numeric_stats": encoder.numeric_stats_, "coverage": encoder.coverage(valid),
        "convergence_retries": retries, "warnings": messages, "estimator_params": estimator.get_params()}


def completed_run_matches(run, current_identity):
    if run["identity"] != current_identity:
        raise ValueError("Changed experiment identity; create a new version")
    if run["status"] != "complete":
        return False
    check_hashes(REPORT, run["outputs"])
    check_hashes(ROOT, run["artifacts"])
    return True


def aggregate_comparisons(summary):
    refit = summary.loc[summary.mode_name.eq("age_refit")].drop(columns="mode_name")
    primary = summary.loc[summary.mode_name.eq("primary_fit_same_rows")].drop(columns="mode_name")
    matched = refit.merge(primary, on=KEYS, suffixes=("_refit", "_primary"), validate="one_to_one")
    for metric in METRICS:
        matched[f"{metric}_refit_minus_primary"] = matched[f"{metric}_mean_refit"] - matched[f"{metric}_mean_primary"]
    family_rows = []
    for (platform, age, features), group in matched.groupby(["platform", "minimum_age_days", "features"]):
        if set(group.family) != {"linear", "forest"}:
            continue
        linear, forest = (group.loc[group.family.eq(f)].iloc[0] for f in ("linear", "forest"))
        row = {"platform": platform, "minimum_age_days": age, "features": features}
        for mode in ("primary", "refit"):
            row[f"linear_macro_f1_{mode}"] = linear[f"macro_f1_mean_{mode}"]
            row[f"forest_macro_f1_{mode}"] = forest[f"macro_f1_mean_{mode}"]
            row[f"forest_minus_linear_{mode}"] = row[f"forest_macro_f1_{mode}"] - row[f"linear_macro_f1_{mode}"]
        family_rows.append(row)
    return matched, pd.DataFrame(family_rows)


def main():
    config = read_json(CONFIG)
    current_identity = identity()
    validate_candidates(config)
    REPORT.mkdir(parents=True, exist_ok=True)
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    run_path = REPORT / "run_manifest.json"
    if run_path.exists():
        old = read_json(run_path)
        if completed_run_matches(old, current_identity):
            print(f"Verified completed run: skipped {old['fitted_folds']} fits; no files rewritten.", flush=True)
            return
    else:
        atomic_json(run_path, {"status": "running", "started_utc": datetime.now(timezone.utc).isoformat(),
            "identity": current_identity, "partition": "train", "calibration_evaluated": False, "test_evaluated": False})
    folds, pooled, classes, matrices, subgroups, audit, cohort_rows, support_rows = [], [], [], [], [], [], [], []
    for platform, specs in config["candidates"].items():
        data = load_train(platform, config)
        labels = sorted(data.target_tier.unique().tolist())
        for age in config["minimum_age_days"]:
            subset = age_cohort(data, age, config["folds"])
            cohort_rows.append({"platform": platform, "minimum_age_days": age, "primary_train_n": len(data),
                "eligible_n": len(subset), "excluded_n": len(data) - len(subset), "missing_age_n": int(data.age_days.isna().sum()),
                "below_cutoff_n": int(data.age_days.lt(age).fillna(False).sum()), "eligible_groups": subset.developer_group.nunique()})
            for fold in config["folds"]:
                for label in labels:
                    support_rows.append({"platform": platform, "minimum_age_days": age, "fold": fold, "tier": label,
                        "n": int((subset.cv_fold.eq(fold) & subset.target_tier.eq(label)).sum())})
            for spec in specs:
                prefix = {"platform": platform, "minimum_age_days": age, "configuration": spec["source_configuration"],
                          "family": spec["family"], "features": spec["features"]}
                predictions = {"age_refit": [], "primary_fit_same_rows": []}
                for fold in config["folds"]:
                    fit, valid = subset.loc[subset.cv_fold.ne(fold)], subset.loc[subset.cv_fold.eq(fold)]
                    if set(fit.developer_group) & set(valid.developer_group) or set(fit.target_tier) != set(labels) or set(valid.target_tier) != set(labels):
                        raise ValueError("Invalid group/class support in age fold")
                    stem = f"{platform}__age{age}__{spec['source_configuration']}__fold{fold}"
                    info_path, pred_path, model_path = [ARTIFACTS / f"{stem}.{ext}" for ext in ("json", "parquet", "joblib")]
                    source_path = source_directory(spec) / f"{platform}__{spec['source_configuration']}__fold{fold}.parquet"
                    original = matched_reference(pd.read_parquet(source_path), valid)
                    original_scores, _ = metrics(original.target_tier, original[["p0", "p1", "p2"]].to_numpy(), labels)
                    if info_path.exists():
                        info = read_json(info_path)
                        if (info["spec"] != spec or info["minimum_age_days"] != age or info["fold"] != fold or
                            info["fit_ids_sha256"] != id_hash(fit.app_id) or info["validation_ids_sha256"] != id_hash(valid.app_id) or
                            info["prediction_sha256"] != digest(pred_path) or info["model_sha256"] != digest(model_path) or
                            info["source_prediction_sha256"] != digest(source_path)):
                            raise ValueError("Changed or mismatched age checkpoint")
                        predicted_frame = pd.read_parquet(pred_path)
                        print(f"Resume {stem}", flush=True)
                    else:
                        print(f"Fitting {stem}: {len(fit)} fit / {len(valid)} validation rows", flush=True)
                        started = time.perf_counter()
                        model, probabilities, extra = fit_model(fit, valid, platform, spec, config)
                        if list(model.classes_) != labels:
                            raise ValueError("Probability class order mismatch")
                        scores, predicted = metrics(valid.target_tier, probabilities, labels)
                        predicted_frame = valid[["app_id", "developer_group", "cv_fold", "target_tier"]].copy()
                        predicted_frame["predicted_tier"] = predicted
                        for i in range(3):
                            predicted_frame[f"p{i}"] = probabilities[:, i]
                        temporary = pred_path.with_name(pred_path.name + ".tmp")
                        predicted_frame.to_parquet(temporary, index=False)
                        temporary.replace(pred_path)
                        temporary = model_path.with_name(model_path.name + ".tmp")
                        joblib.dump(model, temporary, compress=1)
                        temporary.replace(model_path)
                        info = {**prefix, "spec": spec, "fold": fold, "fit_n": len(fit), "validation_n": len(valid),
                            "fit_groups": fit.developer_group.nunique(), "validation_groups": valid.developer_group.nunique(),
                            "fit_ids_sha256": id_hash(fit.app_id), "validation_ids_sha256": id_hash(valid.app_id),
                            "labels": labels, "scores": scores, "reference_scores": original_scores,
                            "seconds": time.perf_counter() - started, **extra, "prediction_sha256": digest(pred_path),
                            "model_sha256": digest(model_path), "source_prediction_sha256": digest(source_path)}
                        atomic_json(info_path, info)  # Completion marker is written last.
                        print(f"{stem}: refit macro-F1={scores['macro_f1']:.4f}; matched primary={original_scores['macro_f1']:.4f}; {info['seconds']:.1f}s", flush=True)
                    audit.append(info)
                    for mode, frame, scores in (("age_refit", predicted_frame, info["scores"]),
                                                ("primary_fit_same_rows", original, original_scores)):
                        predictions[mode].append(frame)
                        folds.append({**prefix, "mode_name": mode, "fold": fold, "validation_n": len(valid), **scores})
                for mode, frames in predictions.items():
                    joined = pd.concat(frames, ignore_index=True)
                    if joined.app_id.duplicated().any() or set(joined.app_id) != set(subset.app_id):
                        raise ValueError("Incomplete age OOF coverage")
                    scores, predicted = metrics(joined.target_tier, joined[["p0", "p1", "p2"]].to_numpy(), labels)
                    record = {**prefix, "mode_name": mode}
                    pooled.append({**record, "n": len(joined), **scores})
                    p, r, f, support = precision_recall_fscore_support(joined.target_tier, predicted, labels=labels, zero_division=0)
                    cm = confusion_matrix(joined.target_tier, predicted, labels=labels)
                    for i, label in enumerate(labels):
                        classes.append({**record, "tier": label, "precision": p[i], "recall": r[i], "f1": f[i], "support": int(support[i])})
                        for j, predicted_label in enumerate(labels):
                            matrices.append({**record, "true_tier": label, "predicted_tier": predicted_label, "count": int(cm[i, j])})
                    if platform == "mobile":
                        subgroups += subgroup_rows(joined, subset, labels, record)
    fold_table = pd.DataFrame(folds)
    summary = fold_table.groupby(KEYS + ["mode_name"], sort=False).agg(
        folds=("fold", "count"), n=("validation_n", "sum"), macro_f1_sd=("macro_f1", "std"),
        **{f"{metric}_mean": (metric, "mean") for metric in METRICS}).reset_index()
    if len(audit) != 84 or len(summary) != 56 or not summary.folds.eq(3).all():
        raise ValueError("Incomplete age experiment matrix")
    matched, family = aggregate_comparisons(summary)
    outputs = {"cohort_counts.csv": pd.DataFrame(cohort_rows), "cohort_class_support.csv": pd.DataFrame(support_rows),
        "fold_metrics.csv": fold_table, "cv_summary.csv": summary, "matched_comparison.csv": matched,
        "family_comparison.csv": family, "pooled_oof_metrics.csv": pd.DataFrame(pooled), "per_class.csv": pd.DataFrame(classes),
        "confusion_matrices.csv": pd.DataFrame(matrices), "mobile_subgroups.csv": pd.DataFrame(subgroups)}
    for name, frame in outputs.items():
        frame.to_csv(REPORT / name, index=False, encoding="utf-8-sig")
    atomic_json(REPORT / "preprocessing_audit.json", audit)
    run = read_json(run_path)
    run.update(status="complete", completed_utc=datetime.now(timezone.utc).isoformat(), configurations=28, fitted_folds=len(audit),
        outputs={name: digest(REPORT / name) for name in [*outputs, "preprocessing_audit.json"]},
        artifacts={p.relative_to(ROOT).as_posix(): digest(p) for p in ARTIFACTS.iterdir() if p.suffix in (".json", ".parquet", ".joblib")})
    atomic_json(run_path, run)
    print("Completed 28 age/model combinations / 84 fits. Calibration/test not evaluated.", flush=True)


if __name__ == "__main__":
    main()
