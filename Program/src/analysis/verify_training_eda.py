"""Independently reproduce EDA counts and quantiles with pandas, not SQL."""
import hashlib
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports/2026-10-07/train_eda_v1"


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    record = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
    for relative, expected in record["inputs"].items():
        require(digest(ROOT / relative) == expected, f"Changed input {relative}")
    for name, expected in record["outputs"].items():
        require(digest(OUT / name) == expected, f"Changed output {name}")
    require(digest(ROOT / "src/analysis/profile_training.py") == record["script_sha256"], "Changed generator")
    dist = pd.read_csv(OUT / "distributions.csv", keep_default_na=False)
    ages = pd.read_csv(OUT / "age_by_tier.csv")
    missing = pd.read_csv(OUT / "missingness.csv")
    checks = []
    for platform in ("pc", "mobile"):
        f = pd.read_parquet(ROOT / f"data/processed/analysis_v1/{platform}_features.parquet")
        labels = pd.read_parquet(ROOT / f"data/processed/analysis_v1/{platform}_labels_splits.parquet")
        train = labels.loc[labels.split.eq("train"), ["app_id", "target_tier"]]
        data = f.merge(train, on="app_id", validate="one_to_one")
        expected_age = data.groupby("target_tier").age_days.quantile([.25, .5, .75])
        for r in ages.loc[ages.platform.eq(platform)].itertuples():
            for q, actual in ((.25, r.age_days_p25), (.5, r.age_days_median), (.75, r.age_days_p75)):
                require(expected_age.loc[r.target_tier, q] == actual, "Age quantile mismatch")
        for r in missing.loc[missing.platform.eq(platform)].itertuples():
            values = data[r.column]
            if r.column in ("genres", "planning_categories", "supported_languages"):
                expected = values.map(lambda v: v is None or len(v) == 0).sum()
            else:
                expected = values.isna().sum()
            require(r.missing_or_empty_n == expected and r.train_n == len(data), "Missing count mismatch")
            require(abs(r.percent - 100 * expected / len(data)) < 1e-8, "Missing percent mismatch")
        for dimension, subset in dist.loc[dist.platform.eq(platform)].groupby("dimension"):
            if dimension == "overall":
                expanded = data.assign(feature_value="all")
            elif dimension == "age_band":
                bands = pd.cut(data.age_days, [-1, 179, 364, 1094, float("inf")],
                               labels=["0-179 days", "180-364 days", "365-1094 days", "1095+ days"])
                expanded = data.assign(feature_value=bands.astype("string").fillna("unknown"))
            elif dimension in ("genres", "planning_categories"):
                expanded = data.assign(feature_value=data[dimension].map(
                    lambda v: list(set(v)) if v is not None and len(v) else ["<empty_or_missing>"])).explode("feature_value")
            elif dimension == "category":
                expanded = data.assign(feature_value=data.category.fillna("<unavailable>"))
            else:
                expanded = data.assign(feature_value=data[dimension].map(
                    lambda v: "unknown" if pd.isna(v) else "true" if v else "false"))
            counts = expanded.groupby(["feature_value", "target_tier"]).size()
            totals = expanded.groupby("feature_value").size()
            require(set(subset.feature_value) == set(totals.index), "Missing feature groups")
            require(len(subset) == 3 * len(totals) and not subset.duplicated(["feature_value", "target_tier"]).any(), "Incomplete or repeated tiers")
            for r in subset.itertuples():
                require(r.count == counts.get((r.feature_value, r.target_tier), 0), "Distribution count mismatch")
                require(r.group_n == totals.loc[r.feature_value] and r.train_n == len(data), "Denominator mismatch")
                require(abs(r.percent - 100 * r.count / r.group_n) < 1e-8, "Percent mismatch")
                require(bool(r.small_sample) == (r.group_n < 30), "Sample flag mismatch")
            checks.append({"platform": platform, "dimension": dimension, "checked_rows": len(subset)})
    result = {"status": "passed", "independent_engine": "pandas", "distribution_rows_checked": len(dist),
              "age_quantiles_checked": len(ages) * 3, "missingness_rows_checked": len(missing), "checks": checks,
              "manifest_sha256": digest(OUT / "manifest.json"), "verifier_sha256": digest(Path(__file__))}
    (OUT / "verification.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
