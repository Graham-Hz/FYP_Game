"""Independent table/selection checks, using saved OOF rows and direct arithmetic."""
import json

import numpy as np
import pandas as pd

from verify_development import calculate, digest, require


def verify_diagnostics(root, report, artifacts, summary, choices):
    config = json.loads((root / "config/model_tree_v1.json").read_text(encoding="utf-8"))
    expected = {(platform, f"RF_{features.replace('+', '_plus_')}_leaves{leaves}_{weight or 'none'}")
        for platform, features_list in config["feature_sets"].items() for features in features_list
        for leaves in config["max_leaf_nodes_grid"] for weight in config["class_weight_grid"]}
    require(len(summary) == len(expected) and set(zip(summary.platform, summary.configuration)) == expected,
            "Wrong prespecified configuration matrix")
    require(len(choices) == sum(map(len, config["feature_sets"].values())), "Missing development choice")
    for choice in choices:
        candidates = summary.loc[summary.platform.eq(choice["platform"]) & summary.features.eq(choice["features"])]
        maximum = candidates.macro_f1_mean.max()
        tied = [r for r in candidates.itertuples() if r.macro_f1_mean >= maximum - 1e-6]
        winner = min(tied, key=lambda r: (r.max_leaf_nodes, r.weight == "balanced"))
        require(winner.configuration == choice["configuration"], "Incorrect selection/tie handling")
        require(abs(winner.macro_f1_mean - choice["mean_fold_macro_f1"]) < 1e-12 and
                abs(winner.macro_f1_sd - choice["fold_sd"]) < 1e-12, "Choice metric mismatch")
    old_report = root / "reports/2026-10-07/model_dev_v1"
    old = json.loads((old_report / "run_manifest.json").read_text(encoding="utf-8"))
    for name, sha in old["outputs"].items():
        require(digest(old_report / name) == sha, "Changed linear table")
    old_choices = json.loads((old_report / "development_choices.json").read_text(encoding="utf-8"))
    comparison = pd.read_csv(report / "linear_tree_comparison.csv", keep_default_na=False)
    diagnostic = pd.read_csv(report / "selected_oof_subgroups.csv", keep_default_na=False)
    require(len(comparison) == len(choices), "Wrong comparison count")
    checked = 0
    for platform in ("pc", "mobile"):
        train_labels = pd.read_parquet(root / f"data/processed/analysis_v1/{platform}_labels_splits.parquet",
                                      filters=[("split", "==", "train")])
        columns = ["app_id", "age_days"] + (["free"] if platform == "mobile" else [])
        data = pd.read_parquet(root / f"data/processed/analysis_v1/{platform}_features.parquet", columns=columns).merge(
            train_labels, on="app_id", validate="one_to_one")
        labels = sorted(data.target_tier.unique())
        for tree in [c for c in choices if c["platform"] == platform]:
            linear = next(c for c in old_choices if c["platform"] == platform and c["features"] == tree["features"])
            matching = comparison.loc[comparison.platform.eq(platform) & comparison.features.eq(tree["features"])]
            require(len(matching) == 1, "Comparison duplicated or missing")
            row = matching.iloc[0]
            require(row.linear_configuration == linear["configuration"] and row.tree_configuration == tree["configuration"],
                    "Wrong compared configuration")
            for family, choice in [("linear", linear), ("tree", tree)]:
                require(abs(row[f"{family}_macro_f1_mean"] - choice["mean_fold_macro_f1"]) < 1e-12, "Comparison score")
                require(abs(row[f"{family}_fold_sd"] - choice["fold_sd"]) < 1e-12, "Comparison SD")
            require(abs(row.tree_minus_linear - (tree["mean_fold_macro_f1"] - linear["mean_fold_macro_f1"])) < 1e-12,
                    "Comparison delta")
            for family, choice, directory in [("linear", linear, root / "data/processed/model_dev_v1"), ("forest", tree, artifacts)]:
                frames = []
                for fold in (0, 1, 2):
                    path = directory / f"{platform}__{choice['configuration']}__fold{fold}.parquet"
                    if family == "linear":
                        require(digest(path) == old["artifacts"][path.relative_to(root).as_posix()], "Changed linear OOF")
                    frames.append(pd.read_parquet(path))
                frame = pd.concat(frames, ignore_index=True)
                require(set(frame.app_id) == set(data.app_id) and not frame.app_id.duplicated().any(), "Diagnostic membership")
                frame = frame.merge(data[columns], on="app_id", validate="one_to_one")
                masks = {f"age_ge_{age}": frame.age_days.ge(age).fillna(False) for age in config["diagnostics"]["age_minimum_days"]}
                if platform == "mobile":
                    masks.update(free=frame.free.eq(True).fillna(False), paid=frame.free.eq(False).fillna(False), unknown=frame.free.isna())
                for subgroup, mask in masks.items():
                    stored = diagnostic.loc[diagnostic.platform.eq(platform) & diagnostic.family.eq(family) &
                        diagnostic.configuration.eq(choice["configuration"]) & diagnostic.subgroup.eq(subgroup)]
                    require(len(stored) == 1, "Missing/duplicated subgroup")
                    record, part = stored.iloc[0], frame.loc[mask]
                    require(record.n == len(part) and record.classes_present == part.target_tier.nunique(), "Wrong subgroup support")
                    for i, label in enumerate(labels):
                        require(record[f"support_{i}"] == part.target_tier.eq(label).sum(), "Wrong subgroup class support")
                    if len(part):
                        scores, _, _ = calculate(part, labels)
                        require(abs(record.macro_f1_fixed_three_labels - scores["macro_f1"]) < 1e-12 and
                                abs(record.accuracy - scores["accuracy"]) < 1e-12, "Wrong subgroup metric")
                    checked += 1
    require(checked == len(diagnostic), "Unexpected diagnostic rows")
    return {"comparison_rows": len(comparison), "subgroup_rows": checked, "selection_tie_rules": "passed",
            "age_restricted_refitting": False}
