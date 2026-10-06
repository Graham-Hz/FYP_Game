"""Versioned working cohorts plus row-level reasons; deliberately no model fitting."""
import json
from pathlib import Path

import pandas as pd

from audit_common import ROOT, INTERIM, GAME_CATEGORIES, save_csv, save_json, sha256
from cleaning_rules import boolean, collection, install_tiers, nonnegative, owner_interval, title_missing

CONFIG_PATH = ROOT / "config/cleaning_candidate_v1.json"
PC_FIELDS = "app_id name release_date genres categories supported_languages developers price windows mac linux estimated_owners".split()
MOBILE_FIELDS = "app_id app_name category released scraped_time developer_id price free currency ad_supported in_app_purchases content_rating minimum_installs".split()


def base(raw, name, release, observation):
    result = pd.DataFrame({"app_id": raw.app_id.astype("string"), "title": raw[name].astype("string")})
    result["release_date"] = release
    result["reference_date"] = observation
    result["age_days"] = (observation - release).dt.days.astype("Int64")
    flags = pd.DataFrame({"app_id": result.app_id})
    flags["exclude_title_missing"] = raw[name].map(title_missing)
    flags["exclude_release_unavailable"] = release.isna()
    flags["exclude_reference_unavailable"] = observation.isna()
    flags["exclude_release_after_reference"] = release.gt(observation)
    flags["flag_literal_null_like_title"] = raw[name].astype("string").str.strip().str.lower().isin(["none", "null", "nan", "n/a"])
    return result, flags


def pc_candidate(raw, config):
    release = pd.to_datetime(raw.release_date, format="%Y-%m-%d", errors="coerce")
    observation = pd.Series(pd.Timestamp(config["pc_reference_date_proxy"]), index=raw.index)
    result, flags = base(raw, "name", release, observation)
    for column in ["genres", "categories", "supported_languages", "developers"]:
        parsed = raw[column].map(collection)
        result[column] = parsed.map(lambda x: x[0])
        status = parsed.map(lambda x: x[1])
        flags[f"flag_{column}_unavailable"] = status.ne("valid")
        flags[f"flag_{column}_parse_error"] = status.eq("invalid")
    flags["exclude_genres_unavailable"] = flags.flag_genres_unavailable
    flags["exclude_demo_playtest_title_heuristic"] = raw.name.astype("string").str.lower().str.contains(config["pc_demo_title_pattern"].replace("(", "(?:"), regex=True, na=False)
    software = set(config["software_only_genres"])
    flags["flag_software_only_heuristic"] = result.genres.map(lambda xs: bool(xs) and set(xs) <= software)
    result["price_observed"] = nonnegative(raw.price)
    result["zero_observed_price"] = result.price_observed.eq(0)
    flags["flag_price_unavailable"] = result.price_observed.isna()
    for column in ["windows", "mac", "linux"]:
        result[column] = boolean(raw[column])
        flags[f"flag_{column}_unavailable"] = result[column].isna()
    intervals = pd.DataFrame(raw.estimated_owners.map(owner_interval).tolist(), columns=["owners_lower", "owners_upper", "target_tier", "target_status"], index=raw.index)
    for column in ["owners_lower", "owners_upper"]:
        intervals[column] = intervals[column].astype("Int64")
    result = pd.concat([result, intervals], axis=1)
    flags["flag_target_unavailable"] = result.target_tier.isna()
    result["software_only_heuristic"] = flags.flag_software_only_heuristic
    return result, flags


def mobile_candidate(raw, config):
    if not raw.category.isin(GAME_CATEGORIES).all():
        raise ValueError("Input includes categories outside the audited conservative game subset")
    release = pd.to_datetime(raw.released, format="%b %d, %Y", errors="coerce")
    # Date-level age; source clock time has no time-zone metadata.
    observation = pd.to_datetime(raw.scraped_time, format="%Y-%m-%d %H:%M:%S", errors="coerce").dt.normalize()
    result, flags = base(raw, "app_name", release, observation)
    for column in ["category", "content_rating", "developer_id", "currency"]:
        result[column] = raw[column].astype("string")
    flags["flag_developer_id_unavailable"] = raw.developer_id.map(title_missing)
    for column in ["free", "ad_supported", "in_app_purchases"]:
        result[column] = boolean(raw[column])
        flags[f"flag_{column}_unavailable"] = result[column].isna()
    price = nonnegative(raw.price)
    usd = raw.currency.astype("string").str.strip().str.upper().eq("USD").fillna(False)
    result["price_usd"] = price.where(usd)
    result["price_usd_unavailable"] = result.price_usd.isna()
    flags["flag_non_usd_or_unknown_currency"] = ~usd
    flags["flag_price_invalid_or_missing"] = price.isna()
    flags["flag_free_price_conflict"] = ((result.free.eq(True) & price.gt(0)) | (result.free.eq(False) & price.eq(0))).fillna(False)
    result["minimum_installs"] = nonnegative(raw.minimum_installs, integer=True)
    result["target_tier"] = install_tiers(result.minimum_installs)
    result["target_status"] = result.target_tier.notna().map({True: "labelled", False: "invalid_or_missing"})
    flags["flag_target_unavailable"] = result.target_tier.isna()
    return result, flags


def finalize(result, flags):
    exclusions = [c for c in flags if c.startswith("exclude_")]
    flags["eligible_base"] = ~flags[exclusions].any(axis=1)
    flags["eligible_labelled"] = flags.eligible_base & ~flags.flag_target_unavailable
    # Save every independent flag as well as the first failing rule for additive counts.
    first = pd.Series("retained", index=flags.index)
    for rule in exclusions:
        first.loc[first.eq("retained") & flags[rule]] = rule
    flags["first_exclusion_reason"] = first
    result["label_available"] = ~flags.flag_target_unavailable
    return result.loc[flags.eligible_base].sort_values("app_id").reset_index(drop=True), flags.sort_values("app_id").reset_index(drop=True)


def main():
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    out = INTERIM / config["version"]
    reports = ROOT / "reports" / config["report_date"] / config["version"]
    out.mkdir(parents=True, exist_ok=True)
    reports.mkdir(parents=True, exist_ok=True)
    # Remove only the generated success marker before any rewrite, never source data.
    manifest_path = reports / "manifest.json"
    manifest_path.unlink(missing_ok=True)
    (reports / "verification.json").unlink(missing_ok=True)
    manifest = {"version": config["version"], "status": config["status"], "model_training": False, "split_created": False,
                "config_sha256": sha256(CONFIG_PATH), "input_sha256": {}, "output_sha256": {}, "platforms": {}}
    rules, balance, titles = [], [], []
    for platform, builder, fields in [("pc", pc_candidate, PC_FIELDS), ("mobile", mobile_candidate, MOBILE_FIELDS)]:
        source = INTERIM / config["inputs"][platform]["file"]
        digest = sha256(source)
        if digest != config["inputs"][platform]["sha256"]:
            raise ValueError(f"Input hash changed: {source}; audit and version the rules before proceeding")
        manifest["input_sha256"][str(source.relative_to(ROOT))] = digest
        raw = pd.read_parquet(source, columns=fields)
        if raw.app_id.isna().any() or raw.app_id.str.strip().eq("").any() or not raw.app_id.is_unique:
            raise ValueError("Missing or duplicate source IDs; never silently drop duplicates")
        result, flags = builder(raw, config)
        candidates, ledger = finalize(result, flags)
        for suffix, frame in [("candidates", candidates), ("row_ledger", ledger)]:
            path = out / f"{platform}_{suffix}.parquet"
            frame.to_parquet(path, index=False)
            manifest["output_sha256"][str(path.relative_to(ROOT))] = sha256(path)
        for rule in [c for c in ledger if c.startswith(("exclude_", "flag_"))]:
            rules.append({"platform": platform, "rule": rule, "affected_all_input_rows": int(ledger[rule].sum()),
                          "first_exclusion_rows": int(ledger.first_exclusion_reason.eq(rule).sum()),
                          "affected_retained_rows": int((ledger[rule] & ledger.eligible_base).sum())})
        for label, count in candidates.target_tier.fillna("UNLABELLED").value_counts().sort_index().items():
            balance.append({"platform": platform, "target_tier": label, "rows": int(count)})
        title_ids = flags.loc[flags.flag_literal_null_like_title, "app_id"]
        title_review = result.loc[result.app_id.isin(title_ids), ["app_id", "title"]].merge(flags[["app_id", "eligible_base", "eligible_labelled", "first_exclusion_reason"]], on="app_id", validate="one_to_one")
        title_review.insert(0, "platform", platform)
        titles.extend(title_review.to_dict("records"))
        if platform == "mobile":
            conflict_ids = flags.loc[flags.eligible_base & flags.flag_free_price_conflict, "app_id"]
            review_path = reports / "mobile_free_price_review.csv"
            raw.loc[raw.app_id.isin(conflict_ids), ["app_id", "app_name", "free", "price", "currency"]].sort_values("app_id").to_csv(review_path, index=False, encoding="utf-8-sig")
            manifest["output_sha256"][str(review_path.relative_to(ROOT))] = sha256(review_path)
        manifest["platforms"][platform] = {"input_rows": len(raw), "base_candidate_rows": len(candidates),
            "labelled_candidate_rows": int(candidates.label_available.sum()), "unlabelled_candidate_rows": int((~candidates.label_available).sum()),
            "excluded_rows": int((~ledger.eligible_base).sum())}
        # Rehash read-only input after work as well as before.
        assert sha256(source) == digest
    save_csv(reports / "rule_counts.csv", rules)
    save_csv(reports / "target_balance.csv", balance)
    save_csv(reports / "literal_title_review.csv", titles)
    for name in ["rule_counts.csv", "target_balance.csv", "literal_title_review.csv"]:
        path = reports / name
        manifest["output_sha256"][str(path.relative_to(ROOT))] = sha256(path)
    manifest["code_sha256"] = {str(p.relative_to(ROOT)): sha256(p) for p in [Path(__file__), Path(__file__).with_name("cleaning_rules.py")]}
    manifest["generation_complete"] = True
    manifest["independent_verification"] = "pending; run verify_clean_candidates.py"
    save_json(manifest_path, manifest)
    print(json.dumps(manifest["platforms"], indent=2))


if __name__ == "__main__":
    main()
