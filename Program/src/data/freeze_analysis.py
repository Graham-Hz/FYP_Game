"""Prepare a versioned analytical cohort and group split; no learned preprocessing."""
import json
from pathlib import Path

import pandas as pd

from audit_common import ROOT, INTERIM, save_json, save_csv, sha256
from cleaning_rules import collection
from clean_candidates import PC_FIELDS, pc_candidate, finalize
from group_splits import pc_components, developer_tokens, mobile_group, partition, normalize_developer

CONFIG_PATH = ROOT / "config/analysis_v1.json"


def main():
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    cleaning = json.loads((ROOT / "config/cleaning_candidate_v1.json").read_text(encoding="utf-8"))
    policy_path = ROOT / config["feature_policy_file"]
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    previous_reports = ROOT / "reports/2026-10-06" / config["input_cleaning_version"]
    previous_path = previous_reports / "manifest.json"
    previous = json.loads(previous_path.read_text(encoding="utf-8"))
    verification = json.loads((previous_reports / "verification.json").read_text(encoding="utf-8"))
    if verification["status"] != "passed" or verification["manifest_sha256"] != sha256(previous_path):
        raise ValueError("Prior candidate verification does not match its manifest")
    inputs = {}
    for key, digest in previous["input_sha256"].items():
        path = ROOT / key
        if sha256(path) != digest:
            raise ValueError(f"Changed audited input: {key}")
        inputs[path.relative_to(ROOT).as_posix()] = digest
    candidates_dir = INTERIM / config["input_cleaning_version"]
    for platform in ["pc", "mobile"]:
        for suffix in ["candidates", "row_ledger"]:
            path = candidates_dir / f"{platform}_{suffix}.parquet"
            digest = sha256(path)
            if digest != previous["output_sha256"][str(path.relative_to(ROOT))]:
                raise ValueError(f"Changed candidate: {path}")
            inputs[path.relative_to(ROOT).as_posix()] = digest
    # Existing frozen version may only be deterministically reproduced with identical dependencies.
    reports = ROOT / "reports" / config["date"] / config["version"]
    out = ROOT / "data/processed" / config["version"]
    code_paths = [Path(__file__), ROOT / "src/data/group_splits.py", ROOT / "src/data/cleaning_rules.py", ROOT / "src/data/clean_candidates.py", ROOT / "src/features/feature_policy.py"]
    dependency_paths = [CONFIG_PATH, policy_path, ROOT / "config/cleaning_candidate_v1.json", previous_path, previous_reports / "verification.json", ROOT / "uv.lock"] + code_paths
    dependencies = {p.relative_to(ROOT).as_posix(): sha256(p) for p in dependency_paths}
    manifest_path = reports / "manifest.json"
    if manifest_path.exists():
        old = json.loads(manifest_path.read_text(encoding="utf-8"))
        if old["inputs"] != inputs or old["dependencies"] != dependencies:
            raise ValueError("Frozen version changed. Create a new version, do not overwrite its split.")
    reports.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    (reports / "verification.json").unlink(missing_ok=True)
    original = pd.read_parquet(INTERIM / cleaning["inputs"]["pc"]["file"], columns=PC_FIELDS)
    parsed_devs = original.developers.map(collection)
    if parsed_devs.map(lambda x: x[1] == "invalid").any():
        raise ValueError("Unparsed developer collection in full graph")
    records = list(zip(original.app_id, parsed_devs.map(lambda x: x[0])))
    groups, tokens = pc_components(records, config["developer_placeholder_tokens"])
    pc = pd.read_parquet(candidates_dir / "pc_candidates.parquet")
    # Reconstruct explicitly reviewed exceptions from unchanged source, not from a live API.
    exception_ids = set(config["pc_demo_exceptions"])
    exceptions = original[original.app_id.isin(exception_ids)].copy().reset_index(drop=True)
    if set(exceptions.app_id) != exception_ids or exception_ids.intersection(pc.app_id):
        raise ValueError("Unexpected demo exception IDs")
    extra, extra_flags = pc_candidate(exceptions, cleaning)
    if not extra_flags.exclude_demo_playtest_title_heuristic.all():
        raise ValueError("Exception no longer matches reviewed rule")
    extra_flags["exclude_demo_playtest_title_heuristic"] = False
    extra, _ = finalize(extra, extra_flags)
    if set(extra.app_id) != exception_ids:
        raise ValueError("Exception fails another base rule")
    pc = pd.concat([pc, extra], ignore_index=True).sort_values("app_id").reset_index(drop=True)
    pc["developer_group"] = pc.app_id.map(groups)
    mobile = pd.read_parquet(candidates_dir / "mobile_candidates.parquet")
    mob_ledger = pd.read_parquet(candidates_dir / "mobile_row_ledger.parquet").set_index("app_id")
    mobile["free_price_conflict"] = mobile.app_id.map(mob_ledger.flag_free_price_conflict)
    mobile.loc[mobile.free_price_conflict, "free"] = pd.NA
    mobile["developer_group"] = mobile.developer_id.map(lambda x: mobile_group(x, config["developer_placeholder_tokens"]) if pd.notna(x) else None)
    summary, outputs, rule_rows, class_rows = {}, {}, [], []
    def emit(frame, name):
        path = out / name
        frame.to_parquet(path, index=False)
        outputs[path.relative_to(ROOT).as_posix()] = sha256(path)
    # Full PC edges preserve evidence about bridge games excluded from analysis.
    edges = pd.DataFrame([(a, token, groups[a]) for a in sorted(tokens) for token in tokens[a]], columns=["app_id", "developer_token", "developer_group"])
    emit(edges, "pc_developer_edges.parquet")
    normalized = pd.DataFrame([(value, normalize_developer(value)) for _, values in records for value in values], columns=["original", "normalized"]).drop_duplicates()
    collisions = normalized.groupby("normalized").filter(lambda df: len(df)>1).sort_values(["normalized", "original"])
    save_csv(reports / "pc_developer_normalization_review.csv", collisions.to_dict("records"))
    for platform, frame in [("pc", pc), ("mobile", mobile)]:
        ledger = frame[["app_id", "developer_group", "target_tier"]].copy()
        ledger["exclude_unknown_target"] = frame.target_tier.isna()
        ledger["exclude_unknown_developer"] = frame.developer_group.isna()
        if platform == "pc":
            ledger["exclude_nonpositive_price"] = ~frame.price_observed.gt(0).fillna(False)
            ledger["exclude_software_only_heuristic"] = frame.software_only_heuristic
            ledger["reviewed_demo_exception"] = frame.app_id.isin(exception_ids)
        else:
            ledger["free_price_conflict_masked"] = frame.free_price_conflict
        excludes = [c for c in ledger if c.startswith("exclude_")]
        ledger["primary_eligible"] = ~ledger[excludes].any(axis=1)
        ledger["first_exclusion"] = "retained"
        for rule in excludes:
            ledger.loc[ledger.first_exclusion.eq("retained") & ledger[rule], "first_exclusion"] = rule
            rule_rows.append({"platform": platform, "rule": rule, "independent_rows": int(ledger[rule].sum()), "first_exclusion_rows": int(ledger.first_exclusion.eq(rule).sum())})
        parts = frame.developer_group.map(lambda group: partition(group, platform, config))
        ledger["assigned_split"] = parts.map(lambda x: x[0])
        ledger["assigned_cv_fold"] = parts.map(lambda x: x[1]).astype("Int64")
        emit(ledger.sort_values("app_id"), f"{platform}_cohort_ledger.parquet")
        keep = ledger.primary_eligible
        selected = frame.loc[keep].copy()
        split = ledger.loc[keep, ["app_id", "developer_group", "target_tier", "assigned_split", "assigned_cv_fold"]].rename(columns={"assigned_split": "split", "assigned_cv_fold": "cv_fold"}).sort_values("app_id").reset_index(drop=True)
        if platform == "pc":
            selected["planning_categories"] = selected.categories.map(lambda xs: [x for x in xs if x in config["pc_planning_categories"]])
            selected["categories_unavailable"] = selected.categories.map(len).eq(0)
            selected["languages_unavailable"] = selected.supported_languages.map(len).eq(0)
        else:
            selected["free_unavailable"] = selected.free.isna()
        feature_names = list(dict.fromkeys(c for cols in policy[platform].values() for c in cols))
        if set(feature_names).intersection(policy["forbidden_predictors"]):
            raise ValueError("Forbidden feature")
        features = selected[["app_id"] + feature_names].sort_values("app_id").reset_index(drop=True)
        emit(features, f"{platform}_features.parquet")
        emit(split, f"{platform}_labels_splits.parquet")
        for (part, target), count in split.groupby(["split", "target_tier"]).size().items():
            class_rows.append({"platform":platform,"partition":part,"target_tier":target,"rows":int(count)})
        for (fold,target), count in split[split.split.eq("train")].groupby(["cv_fold","target_tier"]).size().items():
            class_rows.append({"platform":platform,"partition":f"train_cv_{fold}","target_tier":target,"rows":int(count)})
        summary[platform] = {"base_rows_including_exceptions":len(frame),"primary_rows":len(split),"excluded_primary":int((~keep).sum()),
            "developer_groups":int(split.developer_group.nunique()),"largest_group_rows":int(split.developer_group.value_counts().max()),
            "split_rows":{k:int(v) for k,v in split.split.value_counts().items()},"train_cv_rows":{str(k):int(v) for k,v in split.cv_fold.value_counts().items()},
            "feature_columns_P":policy[platform]["P"],"feature_columns_P_plus_A":policy[platform]["P+A"]}
        if platform == "mobile":
            summary[platform]["free_price_conflicts_masked"] = int(selected.free_price_conflict.sum())
            summary[platform]["unavailable_USD_price"] = int(selected.price_usd_unavailable.sum())
    save_csv(reports / "cohort_flow.csv", rule_rows)
    save_csv(reports / "split_class_counts.csv", class_rows)
    for name in ["cohort_flow.csv", "split_class_counts.csv", "pc_developer_normalization_review.csv"]:
        path=reports/name
        if path.exists():outputs[path.relative_to(ROOT).as_posix()]=sha256(path)
    for path,digest in inputs.items():
        if sha256(ROOT/path)!=digest:raise ValueError("Input changed during generation")
    save_json(manifest_path, {"version":config["version"],"status":config["status"],"model_training":False,"inputs":inputs,"dependencies":dependencies,"outputs":outputs,"summary":summary,
        "split_target_use":"No labels used to assign groups, partitions or CV folds. Distribution counts are diagnostics only; no reroll.","verification":"pending independent verification"})
    print(json.dumps(summary,indent=2))


if __name__ == "__main__":
    main()
