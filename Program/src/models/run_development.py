"""Prespecified train-only, group-fold development evaluation; resumable by hashes."""
import hashlib
import importlib.metadata
import json
import platform as system_platform
import sys
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, confusion_matrix, f1_score, log_loss, precision_recall_fscore_support
from sklearn.pipeline import Pipeline
from threadpoolctl import threadpool_limits

from preprocessing import PlanningEncoder

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "reports/2026-10-07/model_dev_v1"
ARTIFACTS = ROOT / "data/processed/model_dev_v1"
CONFIG = ROOT / "config/model_dev_v1.json"


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def save_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def id_hash(values):
    return hashlib.sha256("\n".join(sorted(map(str, values))).encode()).hexdigest()


def configurations(platform, config):
    yield {"id": "class_prior", "features": "none", "C": None, "weight": None}
    for weight in config["class_weight_grid"]:
        yield {"id": f"age_only_C1_{weight or 'none'}", "features": "age_only", "C": config["age_only_C"], "weight": weight}
    for feature in config["feature_sets"][platform]:
        for C in config["C_grid"]:
            for weight in config["class_weight_grid"]:
                yield {"id": f"{feature.replace('+', '_plus_')}_C{C}_{weight or 'none'}", "features": feature, "C": C, "weight": weight}


def metrics(y, probabilities, labels):
    prediction = np.asarray(labels)[probabilities.argmax(axis=1)]
    onehot = np.array([[int(value == label) for label in labels] for value in y])
    return {"macro_f1": float(f1_score(y, prediction, labels=labels, average="macro", zero_division=0)),
            "balanced_accuracy": float(balanced_accuracy_score(y, prediction)),
            "accuracy": float(accuracy_score(y, prediction)), "log_loss": float(log_loss(y, probabilities, labels=labels)),
            "brier": float(np.mean(np.sum((probabilities-onehot)**2, axis=1)))}, prediction


def fingerprint(config):
    analysis_path = ROOT / "reports/2026-10-06/analysis_v1/manifest.json"
    if digest(analysis_path) != config["analysis_manifest_sha256"]:
        raise ValueError("Changed analysis manifest")
    analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
    for relative, expected in analysis["dependencies"].items():
        if digest(ROOT / relative) != expected:
            raise ValueError(f"Changed frozen dependency: {relative}")
    artifacts = {}
    for platform in ("pc", "mobile"):
        for kind in ("features", "labels_splits"):
            relative = f"data/processed/analysis_v1/{platform}_{kind}.parquet"
            actual = digest(ROOT / relative)
            if actual != analysis["outputs"][relative]:
                raise ValueError(f"Changed input: {relative}")
            artifacts[relative] = actual
    dependencies = {relative: digest(ROOT / relative) for relative in (
        "config/model_dev_v1.json", "src/models/preprocessing.py", "src/models/run_development.py",
        "experiments/model_dev_v1/pyproject.toml", "experiments/model_dev_v1/uv.lock",
        "config/feature_policy_v1.json", "src/features/feature_policy.py", "reports/planning/model_dev_v1_protocol.md")}
    return {"analysis_manifest_sha256": config["analysis_manifest_sha256"], "inputs": artifacts, "dependencies": dependencies,
            "python": system_platform.python_version(), "packages": {name: importlib.metadata.version(name) for name in ("scikit-learn", "numpy", "scipy", "pandas", "pyarrow", "joblib", "threadpoolctl")}}


def main():
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    identity = fingerprint(config)
    REPORT.mkdir(parents=True, exist_ok=True)
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    run_path = REPORT / "run_manifest.json"
    if run_path.exists():
        old = json.loads(run_path.read_text(encoding="utf-8"))
        if old["identity"] != identity:
            raise ValueError("Existing run identity changed; use a new experiment version, not overwrite.")
    else:
        save_json(run_path, {"status": "running", "started_utc": datetime.now(timezone.utc).isoformat(), "identity": identity,
                             "partition": "train", "calibration_evaluated": False, "test_evaluated": False})
    folds, pooled, classes, matrices, subgroups, preprocessing = [], [], [], [], [], []
    for platform in ("pc", "mobile"):
        feature_path = ROOT / f"data/processed/analysis_v1/{platform}_features.parquet"
        label_path = ROOT / f"data/processed/analysis_v1/{platform}_labels_splits.parquet"
        labels_frame = pd.read_parquet(label_path, filters=[("split", "==", "train")])
        data = pd.read_parquet(feature_path).merge(labels_frame, on="app_id", validate="one_to_one").sort_values("app_id").reset_index(drop=True)
        if not data.split.eq("train").all() or set(data.cv_fold) != set(config["folds"]):
            raise ValueError("Only frozen train folds are permitted")
        if data.groupby("developer_group").cv_fold.nunique().max() != 1:
            raise ValueError("Developer group crosses folds")
        labels = sorted(data.target_tier.unique().tolist())
        for spec in configurations(platform, config):
            candidate = spec["id"]
            prefix = {"platform": platform, "configuration": candidate, "features": spec["features"], "C": spec["C"], "weight": spec["weight"] or "none"}
            predictions = []
            for fold in config["folds"]:
                stem = f"{platform}__{candidate}__fold{fold}"
                info_path, pred_path, model_path = (ARTIFACTS/f"{stem}.{ext}" for ext in ("json", "parquet", "joblib"))
                fit = data.loc[data.cv_fold.ne(fold)].copy()
                valid = data.loc[data.cv_fold.eq(fold)].copy()
                if set(fit.developer_group) & set(valid.developer_group) or set(fit.app_id) & set(valid.app_id):
                    raise ValueError("Fold leakage")
                if info_path.exists():
                    info = json.loads(info_path.read_text(encoding="utf-8"))
                    if digest(pred_path) != info["prediction_sha256"] or digest(model_path) != info["model_sha256"]:
                        raise ValueError("Changed checkpoint")
                    prediction_frame = pd.read_parquet(pred_path)
                    print(f"Resume {stem}", flush=True)
                else:
                    started = time.perf_counter()
                    if spec["features"] == "none":
                        model = DummyClassifier(strategy="prior")
                        model.fit(np.zeros((len(fit), 1)), fit.target_tier)
                        probabilities = model.predict_proba(np.zeros((len(valid), 1)))
                        coverage, numeric, n_features, retries, warning_messages = {}, {}, 0, 0, []
                    else:
                        encoder = PlanningEncoder(platform, spec["features"])
                        with threadpool_limits(limits=config["threads"]):
                            xfit = encoder.fit_transform(fit)
                            xvalid = encoder.transform(valid)
                            retries, warning_messages = 0, []
                            for iterations in (config["max_iter"], config["convergence_retry_max_iter"]):
                                estimator = LogisticRegression(C=spec["C"], class_weight=spec["weight"], solver=config["solver"],
                                    l1_ratio=config["l1_ratio"], max_iter=iterations, tol=config["tol"], random_state=config["seed"])
                                with warnings.catch_warnings(record=True) as caught:
                                    warnings.simplefilter("always")
                                    estimator.fit(xfit, fit.target_tier)
                                warning_messages += [str(w.message) for w in caught]
                                converged = not any(issubclass(w.category, ConvergenceWarning) for w in caught)
                                if converged:
                                    break
                                retries += 1
                            if not converged:
                                save_json(REPORT/f"{stem}_failure.json", {"status": "not_converged", "warnings": warning_messages})
                                raise RuntimeError(f"Prespecified retry exhausted: {stem}; no candidate silently omitted")
                            probabilities = estimator.predict_proba(xvalid)
                        model = Pipeline([("encoder", encoder), ("model", estimator)])
                        coverage = encoder.coverage(valid)
                        numeric, n_features = encoder.numeric_stats_, xfit.shape[1]
                    if list(model.classes_) != labels:
                        raise ValueError("Class probability columns misaligned")
                    scores, predicted = metrics(valid.target_tier, probabilities, labels)
                    prediction_frame = valid[["app_id", "developer_group", "cv_fold", "target_tier"]].copy()
                    prediction_frame["predicted_tier"] = predicted
                    for i in range(3):
                        prediction_frame[f"p{i}"] = probabilities[:, i]
                    prediction_frame.to_parquet(pred_path, index=False)
                    joblib.dump(model, model_path)
                    info = {**prefix, "fold": fold, "fit_n": len(fit), "validation_n": len(valid), "group_overlap": 0,
                            "fit_ids_sha256": id_hash(fit.app_id), "validation_ids_sha256": id_hash(valid.app_id),
                            "fit_groups": fit.developer_group.nunique(), "validation_groups": valid.developer_group.nunique(),
                            "labels": labels, "scores": scores, "seconds": time.perf_counter()-started,
                            "n_features": n_features, "coverage": coverage, "numeric_stats": numeric,
                            "convergence_retries": retries, "warnings": warning_messages,
                            "prediction_sha256": digest(pred_path), "model_sha256": digest(model_path)}
                    save_json(info_path, info)
                    print(f"{stem}: macro-F1={scores['macro_f1']:.4f}, balanced_accuracy={scores['balanced_accuracy']:.4f}, {info['seconds']:.1f}s", flush=True)
                folds.append({**prefix, "fold": fold, **info["scores"], "fit_n": info["fit_n"], "validation_n": info["validation_n"],
                              "seconds": info["seconds"], "n_features": info["n_features"], "convergence_retries": info["convergence_retries"]})
                preprocessing.append(info)
                predictions.append(prediction_frame)
            joined = pd.concat(predictions, ignore_index=True).sort_values("app_id")
            if joined.app_id.duplicated().any() or set(joined.app_id) != set(data.app_id):
                raise ValueError("Incomplete OOF coverage")
            probabilities = joined[["p0", "p1", "p2"]].to_numpy()
            scores, predicted = metrics(joined.target_tier, probabilities, labels)
            pooled.append({**prefix, "n": len(joined), **scores})
            p, r, f, support = precision_recall_fscore_support(joined.target_tier, predicted, labels=labels, zero_division=0)
            cm = confusion_matrix(joined.target_tier, predicted, labels=labels)
            for i, label in enumerate(labels):
                classes.append({**prefix, "tier": label, "precision": p[i], "recall": r[i], "f1": f[i], "support": int(support[i])})
                for j, predicted_label in enumerate(labels):
                    matrices.append({**prefix, "true_tier": label, "predicted_tier": predicted_label, "count": int(cm[i,j])})
            if platform == "mobile":
                with_free = joined.merge(data[["app_id", "free"]], on="app_id", validate="one_to_one")
                for name, mask in (("free", with_free.free.eq(True).fillna(False)), ("paid", with_free.free.eq(False).fillna(False)), ("unknown", with_free.free.isna())):
                    subset = with_free.loc[mask]
                    if len(subset):
                        # Balanced accuracy for absent classes is not comparable: omit here; fixed-label macro-F1 retained with support.
                        prob = subset[["p0", "p1", "p2"]].to_numpy()
                        pred = np.asarray(labels)[prob.argmax(axis=1)]
                        subgroups.append({**prefix, "subgroup": name, "n": len(subset), "classes_present": subset.target_tier.nunique(),
                            "macro_f1_fixed_three_labels": f1_score(subset.target_tier, pred, labels=labels, average="macro", zero_division=0),
                            "accuracy": accuracy_score(subset.target_tier, pred)})
    fold_table = pd.DataFrame(folds)
    summary = fold_table.groupby(["platform", "configuration", "features", "weight"], sort=False).agg(
        folds=("fold", "count"), macro_f1_mean=("macro_f1", "mean"), macro_f1_sd=("macro_f1", "std"),
        balanced_accuracy_mean=("balanced_accuracy", "mean"), accuracy_mean=("accuracy", "mean"),
        log_loss_mean=("log_loss", "mean"), brier_mean=("brier", "mean"), seconds=("seconds", "sum")).reset_index()
    summary = summary.merge(fold_table[["platform", "configuration", "C"]].drop_duplicates(), on=["platform", "configuration"], validate="one_to_one")
    if not summary.folds.eq(3).all():
        raise ValueError("Candidate missing fold")
    chosen = []
    for (platform, feature), group in summary.groupby(["platform", "features"]):
        tied = group.loc[group.macro_f1_mean >= group.macro_f1_mean.max()-1e-6]
        best = tied.assign(weight_order=tied.weight.eq("balanced").astype(int)).sort_values(["C", "weight_order"], na_position="last").iloc[0]
        chosen.append({"platform": platform, "features": feature, "configuration": best.configuration,
                       "mean_fold_macro_f1": best.macro_f1_mean, "fold_sd": best.macro_f1_sd})
    outputs = {"fold_metrics.csv": fold_table, "cv_summary.csv": summary, "pooled_oof_metrics.csv": pd.DataFrame(pooled),
               "per_class.csv": pd.DataFrame(classes), "confusion_matrices.csv": pd.DataFrame(matrices), "mobile_subgroups.csv": pd.DataFrame(subgroups)}
    for name, table in outputs.items():
        table.to_csv(REPORT/name, index=False, encoding="utf-8-sig")
    save_json(REPORT/"preprocessing_audit.json", preprocessing)
    save_json(REPORT/"development_choices.json", chosen)
    run = json.loads(run_path.read_text(encoding="utf-8"))
    run.update(status="complete", completed_utc=datetime.now(timezone.utc).isoformat(), configurations=len(summary), fitted_folds=len(folds),
               outputs={name: digest(REPORT/name) for name in [*outputs, "preprocessing_audit.json", "development_choices.json"]},
               artifacts={str(path.relative_to(ROOT)).replace("\\", "/"): digest(path) for path in ARTIFACTS.iterdir() if path.is_file()})
    save_json(run_path, run)
    print(f"Completed {len(summary)} configurations / {len(folds)} fold fits. Calibration/test not evaluated.", flush=True)


if __name__ == "__main__":
    main()
