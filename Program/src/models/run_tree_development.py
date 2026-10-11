"""Resumable, prespecified train/group-CV forest comparison; preserves model_dev_v1."""
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_recall_fscore_support
from sklearn.pipeline import Pipeline
from threadpoolctl import threadpool_limits

from preprocessing import PlanningEncoder
from run_development import ROOT, digest, fingerprint, id_hash, metrics, save_json

REPORT = ROOT / "reports/2026-10-10/model_tree_v1"
ARTIFACTS = ROOT / "data/processed/model_tree_v1"
CONFIG = ROOT / "config/model_tree_v1.json"
LINEAR_REPORT = ROOT / "reports/2026-10-07/model_dev_v1"
LINEAR_ARTIFACTS = ROOT / "data/processed/model_dev_v1"
SCORES = ("macro_f1", "balanced_accuracy", "accuracy", "log_loss", "brier")


def configurations(platform, config):
    for features in config["feature_sets"][platform]:
        for leaves in config["max_leaf_nodes_grid"]:
            for weight in config["class_weight_grid"]:
                yield {"id": f"RF_{features.replace('+', '_plus_')}_leaves{leaves}_{weight or 'none'}",
                       "features": features, "max_leaf_nodes": leaves, "weight": weight}


def validate_train(data, folds):
    if data.empty or not data.split.eq("train").all() or set(data.cv_fold) != set(folds):
        raise ValueError("Only complete frozen train folds are permitted")
    if data.app_id.isna().any() or data.app_id.duplicated().any() or data.developer_group.isna().any():
        raise ValueError("Missing or duplicate identities")
    if data.groupby("developer_group").cv_fold.nunique().max() != 1:
        raise ValueError("Developer group crosses folds")


def choose(summary):
    choices = []
    for (platform, feature), group in summary.groupby(["platform", "features"]):
        if not group.folds.eq(3).all() or not np.isfinite(group.macro_f1_mean).all():
            raise ValueError("Incomplete/nonfinite candidate scores")
        tied = group.loc[group.macro_f1_mean >= group.macro_f1_mean.max() - 1e-6]
        best = tied.assign(weight_order=tied.weight.eq("balanced").astype(int)).sort_values(
            ["max_leaf_nodes", "weight_order"]).iloc[0]
        choices.append({"platform": platform, "features": feature, "configuration": best.configuration,
                        "mean_fold_macro_f1": float(best.macro_f1_mean), "fold_sd": float(best.macro_f1_sd)})
    return choices


def run_identity():
    original = json.loads((ROOT / "config/model_dev_v1.json").read_text(encoding="utf-8"))
    base = fingerprint(original)
    old_run = json.loads((LINEAR_REPORT / "run_manifest.json").read_text(encoding="utf-8"))
    if old_run["status"] != "complete" or old_run["identity"] != base:
        raise ValueError("Original completed model identity changed")
    # Historical outputs used in paired comparisons must still match their manifest.
    for relative, expected in old_run["outputs"].items():
        if digest(LINEAR_REPORT / relative) != expected:
            raise ValueError(f"Changed linear report: {relative}")
    for relative, expected in old_run["artifacts"].items():
        if digest(ROOT / relative) != expected:
            raise ValueError(f"Changed linear artifact: {relative}")
    return {**base, "dependencies": {**base["dependencies"], **{relative: digest(ROOT / relative) for relative in (
        "config/model_tree_v1.json", "src/models/run_tree_development.py",
        "reports/planning/model_tree_v1_protocol.md", "reports/2026-10-07/model_dev_v1/run_manifest.json")}}}


def load_train(platform, config):
    labels = pd.read_parquet(ROOT / f"data/processed/analysis_v1/{platform}_labels_splits.parquet",
                             filters=[("split", "==", "train")])
    data = pd.read_parquet(ROOT / f"data/processed/analysis_v1/{platform}_features.parquet").merge(
        labels, on="app_id", validate="one_to_one").sort_values("app_id").reset_index(drop=True)
    validate_train(data, config["folds"])
    return data


def read_oof(directory, platform, candidate):
    return pd.concat([pd.read_parquet(directory / f"{platform}__{candidate}__fold{fold}.parquet")
                      for fold in (0, 1, 2)], ignore_index=True)


def subgroup_rows(predictions, data, labels, prefix, age_thresholds=()):
    columns = ["app_id", "age_days"] + (["free"] if prefix["platform"] == "mobile" else [])
    joined = predictions.merge(data[columns], on="app_id", validate="one_to_one")
    masks = [(f"age_ge_{age}", joined.age_days.ge(age).fillna(False)) for age in age_thresholds]
    if "free" in joined:
        masks += [("free", joined.free.eq(True).fillna(False)), ("paid", joined.free.eq(False).fillna(False)),
                  ("unknown", joined.free.isna())]
    result = []
    for name, mask in masks:
        part = joined.loc[mask]
        result.append({**prefix, "subgroup": name, "n": len(part), "classes_present": part.target_tier.nunique(),
                       **{f"support_{i}": int(part.target_tier.eq(label).sum()) for i, label in enumerate(labels)},
                       "macro_f1_fixed_three_labels": float(f1_score(part.target_tier, part.predicted_tier,
                            labels=labels, average="macro", zero_division=0)) if len(part) else None,
                       "accuracy": float(accuracy_score(part.target_tier, part.predicted_tier)) if len(part) else None})
    return result


def comparison_tables(choices, summary, config):
    linear = json.loads((LINEAR_REPORT / "development_choices.json").read_text(encoding="utf-8"))
    comparisons, diagnostics = [], []
    for platform in config["feature_sets"]:
        data = load_train(platform, config)
        labels = sorted(data.target_tier.unique())
        for choice in [c for c in choices if c["platform"] == platform]:
            old = next(c for c in linear if c["platform"] == platform and c["features"] == choice["features"])
            comparisons.append({"platform": platform, "features": choice["features"],
                "linear_configuration": old["configuration"], "tree_configuration": choice["configuration"],
                "linear_macro_f1_mean": old["mean_fold_macro_f1"], "tree_macro_f1_mean": choice["mean_fold_macro_f1"],
                "tree_minus_linear": choice["mean_fold_macro_f1"] - old["mean_fold_macro_f1"],
                "linear_fold_sd": old["fold_sd"], "tree_fold_sd": choice["fold_sd"]})
            for family, item, directory in (("linear", old, LINEAR_ARTIFACTS), ("forest", choice, ARTIFACTS)):
                frame = read_oof(directory, platform, item["configuration"])
                diagnostics += subgroup_rows(frame, data, labels, {"platform": platform, "features": choice["features"],
                    "family": family, "configuration": item["configuration"]}, config["diagnostics"]["age_minimum_days"])
    return pd.DataFrame(comparisons), pd.DataFrame(diagnostics)


def main():
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    identity = run_identity()
    REPORT.mkdir(parents=True, exist_ok=True)
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    run_path = REPORT / "run_manifest.json"
    if run_path.exists():
        if json.loads(run_path.read_text(encoding="utf-8"))["identity"] != identity:
            raise ValueError("Run identity changed; use a new version")
    else:
        save_json(run_path, {"status": "running", "started_utc": datetime.now(timezone.utc).isoformat(),
            "identity": identity, "partition": "train", "calibration_evaluated": False, "test_evaluated": False})
    folds, pooled, classes, matrices, subgroups, audit = [], [], [], [], [], []
    for platform in config["feature_sets"]:
        data = load_train(platform, config)
        labels = sorted(data.target_tier.unique().tolist())
        for spec in configurations(platform, config):
            prefix = {"platform": platform, "configuration": spec["id"], "features": spec["features"],
                      "max_leaf_nodes": spec["max_leaf_nodes"], "weight": spec["weight"] or "none"}
            predictions = []
            for fold in config["folds"]:
                stem = f"{platform}__{spec['id']}__fold{fold}"
                info_path, pred_path, model_path = [ARTIFACTS / f"{stem}.{ext}" for ext in ("json", "parquet", "joblib")]
                fit, valid = data.loc[data.cv_fold.ne(fold)], data.loc[data.cv_fold.eq(fold)]
                if set(fit.developer_group) & set(valid.developer_group) or set(fit.app_id) & set(valid.app_id):
                    raise ValueError("Fold leakage")
                if info_path.exists():
                    info = json.loads(info_path.read_text(encoding="utf-8"))
                    if (digest(pred_path) != info["prediction_sha256"] or digest(model_path) != info["model_sha256"]
                            or info["fit_ids_sha256"] != id_hash(fit.app_id) or info["validation_ids_sha256"] != id_hash(valid.app_id)):
                        raise ValueError("Changed checkpoint")
                    prediction_frame = pd.read_parquet(pred_path)
                    print(f"Resume {stem}", flush=True)
                else:
                    started = time.perf_counter()
                    print(f"Fitting {stem} ({len(fit)} fit / {len(valid)} validation rows)", flush=True)
                    encoder = PlanningEncoder(platform, spec["features"])
                    with threadpool_limits(limits=config["threads"]):
                        xfit, xvalid = encoder.fit_transform(fit), encoder.transform(valid)
                        estimator = RandomForestClassifier(**config["estimator"], max_leaf_nodes=spec["max_leaf_nodes"],
                            class_weight=spec["weight"], n_jobs=config["threads"], random_state=config["seed"])
                        estimator.fit(xfit, fit.target_tier)
                        probabilities = estimator.predict_proba(xvalid)
                    model = Pipeline([("encoder", encoder), ("model", estimator)])
                    if list(model.classes_) != labels:
                        raise ValueError("Class probability order mismatch")
                    scores, predicted = metrics(valid.target_tier, probabilities, labels)
                    prediction_frame = valid[["app_id", "developer_group", "cv_fold", "target_tier"]].copy()
                    prediction_frame["predicted_tier"] = predicted
                    for i in range(3):
                        prediction_frame[f"p{i}"] = probabilities[:, i]
                    prediction_frame.to_parquet(pred_path, index=False)
                    joblib.dump(model, model_path, compress=1)
                    info = {**prefix, "fold": fold, "fit_n": len(fit), "validation_n": len(valid), "group_overlap": 0,
                        "fit_ids_sha256": id_hash(fit.app_id), "validation_ids_sha256": id_hash(valid.app_id),
                        "fit_groups": fit.developer_group.nunique(), "validation_groups": valid.developer_group.nunique(),
                        "labels": labels, "scores": scores, "seconds": time.perf_counter() - started,
                        "n_features": xfit.shape[1], "coverage": encoder.coverage(valid), "numeric_stats": encoder.numeric_stats_,
                        "estimator_params": estimator.get_params(), "tree_nodes": sum(t.tree_.node_count for t in estimator.estimators_),
                        "prediction_sha256": digest(pred_path), "model_sha256": digest(model_path)}
                    save_json(info_path, info)
                    print(f"{stem}: macro-F1={scores['macro_f1']:.4f}, {info['seconds']:.1f}s", flush=True)
                folds.append({**prefix, "fold": fold, **info["scores"], "fit_n": info["fit_n"],
                    "validation_n": info["validation_n"], "seconds": info["seconds"], "n_features": info["n_features"], "tree_nodes": info["tree_nodes"]})
                audit.append(info)
                predictions.append(prediction_frame)
            joined = pd.concat(predictions, ignore_index=True)
            if joined.app_id.duplicated().any() or set(joined.app_id) != set(data.app_id):
                raise ValueError("Incomplete OOF coverage")
            scores, predicted = metrics(joined.target_tier, joined[["p0", "p1", "p2"]].to_numpy(), labels)
            pooled.append({**prefix, "n": len(joined), **scores})
            p, r, f, support = precision_recall_fscore_support(joined.target_tier, predicted, labels=labels, zero_division=0)
            cm = confusion_matrix(joined.target_tier, predicted, labels=labels)
            for i, label in enumerate(labels):
                classes.append({**prefix, "tier": label, "precision": p[i], "recall": r[i], "f1": f[i], "support": int(support[i])})
                for j, predicted_label in enumerate(labels):
                    matrices.append({**prefix, "true_tier": label, "predicted_tier": predicted_label, "count": int(cm[i, j])})
            if platform == "mobile":
                subgroups += subgroup_rows(joined, data, labels, prefix)
    table = pd.DataFrame(folds)
    summary = table.groupby(["platform", "configuration", "features", "weight", "max_leaf_nodes"], sort=False).agg(
        folds=("fold", "count"), macro_f1_mean=("macro_f1", "mean"), macro_f1_sd=("macro_f1", "std"),
        balanced_accuracy_mean=("balanced_accuracy", "mean"), accuracy_mean=("accuracy", "mean"),
        log_loss_mean=("log_loss", "mean"), brier_mean=("brier", "mean"), seconds=("seconds", "sum")).reset_index()
    choices = choose(summary)
    comparison, diagnostics = comparison_tables(choices, summary, config)
    outputs = {"fold_metrics.csv": table, "cv_summary.csv": summary, "pooled_oof_metrics.csv": pd.DataFrame(pooled),
        "per_class.csv": pd.DataFrame(classes), "confusion_matrices.csv": pd.DataFrame(matrices),
        "mobile_subgroups.csv": pd.DataFrame(subgroups), "linear_tree_comparison.csv": comparison,
        "selected_oof_subgroups.csv": diagnostics}
    for name, frame in outputs.items():
        frame.to_csv(REPORT / name, index=False, encoding="utf-8-sig")
    save_json(REPORT / "preprocessing_audit.json", audit)
    save_json(REPORT / "development_choices.json", choices)
    run = json.loads(run_path.read_text(encoding="utf-8"))
    run.update(status="complete", completed_utc=datetime.now(timezone.utc).isoformat(), configurations=len(summary),
        fitted_folds=len(folds), outputs={name: digest(REPORT / name) for name in [*outputs, "preprocessing_audit.json", "development_choices.json"]},
        artifacts={str(path.relative_to(ROOT)).replace("\\", "/"): digest(path) for path in ARTIFACTS.iterdir() if path.is_file()})
    save_json(run_path, run)
    print(f"Completed {len(summary)} configurations / {len(folds)} folds. Calibration/test not evaluated.", flush=True)


if __name__ == "__main__":
    main()
