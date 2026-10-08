"""Independent arithmetic and membership verification of development predictions."""
import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

# Needed to resolve the locally generated joblib encoder class.
from preprocessing import PlanningEncoder, NUMERIC

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "reports/2026-10-07/model_dev_v1"
ARTIFACTS = ROOT / "data/processed/model_dev_v1"


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def id_hash(values):
    return hashlib.sha256("\n".join(sorted(map(str, values))).encode()).hexdigest()


def calculate(frame, labels):
    lookup = {label: i for i, label in enumerate(labels)}
    y = frame.target_tier.map(lookup).to_numpy(dtype=int)
    predicted = frame.predicted_tier.map(lookup).to_numpy(dtype=int)
    probabilities = frame[["p0", "p1", "p2"]].to_numpy()
    require(np.isfinite(probabilities).all() and (probabilities >= 0).all() and (probabilities <= 1).all(), "Invalid probabilities")
    require(np.allclose(probabilities.sum(axis=1), 1, atol=1e-10), "Probabilities do not sum to one")
    require(np.array_equal(predicted, probabilities.argmax(axis=1)), "Class predictions disagree with probabilities")
    cm = np.zeros((3, 3), dtype=np.int64)
    np.add.at(cm, (y, predicted), 1)
    tp = cm.diagonal()
    support, predicted_n = cm.sum(axis=1), cm.sum(axis=0)
    recall = np.divide(tp, support, out=np.zeros(3), where=support != 0)
    precision = np.divide(tp, predicted_n, out=np.zeros(3), where=predicted_n != 0)
    f1 = np.divide(2*tp, support+predicted_n, out=np.zeros(3), where=(support+predicted_n) != 0)
    onehot = np.eye(3)[y]
    clipped = np.clip(probabilities, np.finfo(float).eps, 1-np.finfo(float).eps)
    scores = {"macro_f1": float(f1.mean()), "balanced_accuracy": float(recall[support > 0].mean()),
              "accuracy": float(tp.sum()/len(frame)), "log_loss": float(-np.log(clipped[np.arange(len(frame)), y]).mean()),
              "brier": float(np.square(probabilities-onehot).sum(axis=1).mean())}
    return scores, cm, (precision, recall, f1, support)


def main():
    run = json.loads((REPORT/"run_manifest.json").read_text(encoding="utf-8"))
    require(run["status"] == "complete" and run["partition"] == "train", "Not a completed training-only run")
    require(not run["calibration_evaluated"] and not run["test_evaluated"], "Unexpected holdout evaluation")
    for kind in ("inputs", "dependencies"):
        for relative, expected in run["identity"][kind].items():
            require(digest(ROOT/relative) == expected, f"Changed {kind}: {relative}")
    for name, expected in run["outputs"].items():
        require(digest(REPORT/name) == expected, f"Changed report {name}")
    for relative, expected in run["artifacts"].items():
        require(digest(ROOT/relative) == expected, f"Changed artifact {relative}")
    policy = json.loads((ROOT/"config/feature_policy_v1.json").read_text(encoding="utf-8"))
    summary = pd.read_csv(REPORT/"cv_summary.csv", keep_default_na=False)
    fold_table = pd.read_csv(REPORT/"fold_metrics.csv", keep_default_na=False)
    pooled = pd.read_csv(REPORT/"pooled_oof_metrics.csv", keep_default_na=False)
    class_table = pd.read_csv(REPORT/"per_class.csv", keep_default_na=False)
    cm_table = pd.read_csv(REPORT/"confusion_matrices.csv", keep_default_na=False)
    subgroup_table = pd.read_csv(REPORT/"mobile_subgroups.csv", keep_default_na=False)
    checked_rows, checked_folds, replay_rows = 0, 0, 0
    for platform in ("pc", "mobile"):
        labels_all = pd.read_parquet(ROOT/f"data/processed/analysis_v1/{platform}_labels_splits.parquet")
        labels_frame = labels_all.loc[labels_all.split.eq("train")].copy()
        features = pd.read_parquet(ROOT/f"data/processed/analysis_v1/{platform}_features.parquet")
        train = features.merge(labels_frame, on="app_id", validate="one_to_one").sort_values("app_id").reset_index(drop=True)
        labels = sorted(train.target_tier.unique().tolist())
        require(train.groupby("developer_group").cv_fold.nunique().max() == 1, "Group crossing folds")
        for row in summary.loc[summary.platform.eq(platform)].itertuples():
            candidate, predicted_frames, fold_scores = row.configuration, [], []
            for fold in (0, 1, 2):
                stem = f"{platform}__{candidate}__fold{fold}"
                info = json.loads((ARTIFACTS/f"{stem}.json").read_text(encoding="utf-8"))
                frame = pd.read_parquet(ARTIFACTS/f"{stem}.parquet")
                fit, valid = train.loc[train.cv_fold.ne(fold)], train.loc[train.cv_fold.eq(fold)]
                require(not frame.app_id.duplicated().any() and set(frame.app_id) == set(valid.app_id), "Wrong OOF membership")
                require(set(frame.app_id).isdisjoint(labels_all.loc[labels_all.split.ne("train"), "app_id"]), "Held-out row in predictions")
                joined = frame.merge(valid[["app_id", "target_tier", "developer_group", "cv_fold"]], on="app_id", suffixes=("", "_source"), validate="one_to_one")
                for column in ("target_tier", "developer_group", "cv_fold"):
                    require(joined[column].equals(joined[f"{column}_source"]), f"Wrong {column}")
                require(id_hash(fit.app_id) == info["fit_ids_sha256"] and id_hash(valid.app_id) == info["validation_ids_sha256"], "Wrong fitting IDs")
                require(set(fit.developer_group).isdisjoint(valid.developer_group), "Developer group leakage")
                score, _, _ = calculate(frame, labels)
                stored_fold = fold_table.loc[fold_table.platform.eq(platform) & fold_table.configuration.eq(candidate) & fold_table.fold.eq(fold)].iloc[0]
                for metric, actual in score.items():
                    require(abs(actual-info["scores"][metric]) < 1e-9 and abs(actual-stored_fold[metric]) < 1e-9, f"Wrong fold {metric}")
                model = joblib.load(ARTIFACTS/f"{stem}.joblib")  # Own artifacts verified against the run manifest above.
                sample = valid.head(12)
                if row.features == "none":
                    prior = fit.target_tier.value_counts(normalize=True).reindex(labels).to_numpy()
                    require(np.allclose(model.class_prior_, prior), "Prior not fitted from fit fold")
                    replay = model.predict_proba(np.zeros((len(sample), 1)))
                else:
                    encoder = model.named_steps["encoder"]
                    require(encoder.columns_ == policy[platform][row.features], "Wrong predictor allowlist")
                    for feature_name in encoder.get_feature_names_out():
                        require(json.loads(feature_name)[1] in encoder.columns_, "Unexpected encoded predictor")
                    for column in set(encoder.columns_) & NUMERIC:
                        x = np.log1p(fit[column].to_numpy(dtype=float, na_value=np.nan))
                        median = np.nanmedian(x) if np.isfinite(x).any() else 0.0
                        x = np.where(np.isnan(x), median, x)
                        expected_stats = {"median": median, "mean": x.mean(), "std": x.std() if x.std() > 0 else 1.0}
                        for stat, actual in expected_stats.items():
                            require(abs(actual-encoder.numeric_stats_[column][stat]) < 1e-10, "Numeric statistics not fit-fold-only")
                    replay = model.predict_proba(sample)
                saved = frame.set_index("app_id").loc[sample.app_id, ["p0", "p1", "p2"]].to_numpy()
                require(np.allclose(replay, saved, atol=1e-10), "Model replay mismatch")
                replay_rows += len(sample)
                checked_rows += len(frame)
                checked_folds += 1
                predicted_frames.append(frame)
                fold_scores.append(score)
            all_predictions = pd.concat(predicted_frames, ignore_index=True)
            require(not all_predictions.app_id.duplicated().any() and set(all_predictions.app_id) == set(train.app_id), "Incomplete OOF partition")
            for metric in ("macro_f1", "balanced_accuracy", "accuracy", "log_loss", "brier"):
                actual = np.mean([scores[metric] for scores in fold_scores])
                require(abs(actual-getattr(row, f"{metric}_mean")) < 1e-9, "Mean-fold aggregation mismatch")
            require(abs(np.std([s["macro_f1"] for s in fold_scores], ddof=1)-row.macro_f1_sd) < 1e-9, "Fold SD mismatch")
            scores, cm, class_values = calculate(all_predictions, labels)
            p_row = pooled.loc[pooled.platform.eq(platform) & pooled.configuration.eq(candidate)].iloc[0]
            for metric, value in scores.items():
                require(abs(value-p_row[metric]) < 1e-9, "Pooled score mismatch")
            for i, label in enumerate(labels):
                c_row = class_table.loc[class_table.platform.eq(platform) & class_table.configuration.eq(candidate) & class_table.tier.eq(label)].iloc[0]
                for metric, actual in zip(("precision", "recall", "f1", "support"), class_values):
                    require(abs(actual[i]-c_row[metric]) < 1e-9, "Per-class score mismatch")
                for j, predicted in enumerate(labels):
                    stored = cm_table.loc[cm_table.platform.eq(platform) & cm_table.configuration.eq(candidate) & cm_table.true_tier.eq(label) & cm_table.predicted_tier.eq(predicted), "count"].item()
                    require(cm[i,j] == stored, "Confusion matrix mismatch")
            if platform == "mobile":
                with_free = all_predictions.merge(train[["app_id", "free"]], on="app_id", validate="one_to_one")
                for subgroup, mask in (("free", with_free.free.eq(True).fillna(False)), ("paid", with_free.free.eq(False).fillna(False)), ("unknown", with_free.free.isna())):
                    part = with_free.loc[mask]
                    s_row = subgroup_table.loc[subgroup_table.configuration.eq(candidate) & subgroup_table.subgroup.eq(subgroup)].iloc[0]
                    s_scores, _, _ = calculate(part, labels)
                    require(len(part) == s_row.n and abs(s_scores["macro_f1"]-s_row.macro_f1_fixed_three_labels) < 1e-9 and abs(s_scores["accuracy"]-s_row.accuracy) < 1e-9, "Subgroup mismatch")
    require(checked_folds == run["fitted_folds"] == 78 and len(summary) == run["configurations"] == 26, "Incomplete experiment matrix")
    choices = json.loads((REPORT/"development_choices.json").read_text(encoding="utf-8"))
    for choice in choices:
        subset = summary.loc[summary.platform.eq(choice["platform"]) & summary.features.eq(choice["features"])]
        require(subset.set_index("configuration").loc[choice["configuration"], "macro_f1_mean"] >= subset.macro_f1_mean.max()-1e-6, "Invalid development choice")
    result = {"status": "passed", "configurations": len(summary), "folds_checked": checked_folds,
        "prediction_rows_checked": checked_rows, "model_replay_rows": replay_rows,
        "checks": ["artifact/input/code hashes", "train-only complete OOF membership", "fold group isolation", "numeric statistics fitted within fold",
                   "predictor allowlist", "independent confusion/precision/recall/F1/accuracy/log-loss/Brier", "fold mean and SD", "Mobile subgroups", "saved model replay", "development choices"],
        "calibration_evaluated": False, "test_evaluated": False,
        "run_manifest_sha256": digest(REPORT/"run_manifest.json"), "verifier_sha256": digest(Path(__file__))}
    (REPORT/"verification.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
