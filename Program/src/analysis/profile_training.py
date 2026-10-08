"""Reproducible descriptive EDA of frozen training rows; no model fitting."""
import csv
import hashlib
import json
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports/2026-10-07/train_eda_v1"
MANIFEST = ROOT / "reports/2026-10-06/analysis_v1/manifest.json"
EXPECTED_MANIFEST = "5f3f341ed1c45fbca703995d95d4eca46d54d1af75e69677e15308d20aed12a6"
AGE_BAND = """CASE WHEN age_days IS NULL THEN 'unknown'
 WHEN age_days < 0 THEN 'invalid_negative'
 WHEN age_days < 180 THEN '0-179 days'
 WHEN age_days < 365 THEN '180-364 days'
 WHEN age_days < 1095 THEN '365-1094 days'
 ELSE '1095+ days' END"""


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def rows(db, sql, params=None):
    result = db.execute(sql, params or [])
    names = [d[0] for d in result.description]
    return [dict(zip(names, row)) for row in result.fetchall()]


def save_csv(name, records):
    with (OUT / name).open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)


def main():
    if digest(MANIFEST) != EXPECTED_MANIFEST:
        raise ValueError("Unexpected analysis manifest; review before rerunning.")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    db = duckdb.connect()
    inputs, distributions, missingness, ages, summary = {}, [], [], [], {}
    for platform in ("pc", "mobile"):
        paths = []
        for kind in ("features", "labels_splits"):
            relative = f"data/processed/analysis_v1/{platform}_{kind}.parquet"
            path = ROOT / relative
            actual = digest(path)
            if actual != manifest["outputs"][relative]:
                raise ValueError(f"Changed frozen artifact: {relative}")
            inputs[relative] = actual
            paths.append(str(path))
        db.execute(f"""CREATE TABLE {platform} AS SELECT f.*, l.target_tier
          FROM read_parquet(?) f JOIN read_parquet(?) l USING(app_id)
          WHERE l.split='train'""", paths)
        n, distinct_n, min_age = db.execute(f"SELECT count(*), count(DISTINCT app_id), min(age_days) FROM {platform}").fetchone()
        if n != distinct_n or n != manifest["summary"][platform]["split_rows"]["train"] or min_age < 0:
            raise ValueError(f"Invalid membership/count/age for {platform}")
        dimensions = {"overall": "'all'", "age_band": AGE_BAND}
        if platform == "pc":
            for key in ("genres", "planning_categories"):
                dimensions[key] = f"unnest(CASE WHEN {key} IS NULL OR len({key})=0 THEN ['<empty_or_missing>'] ELSE list_distinct({key}) END)"
        else:
            dimensions["category"] = "coalesce(category, '<unavailable>')"
            for key in ("free", "ad_supported", "in_app_purchases"):
                dimensions[key] = f"CASE WHEN {key} IS NULL THEN 'unknown' WHEN {key} THEN 'true' ELSE 'false' END"
        for dimension, expression in dimensions.items():
            records = rows(db, f"""WITH expanded AS (
                 SELECT app_id, target_tier, {expression} AS feature_value FROM {platform}),
                 groups AS (SELECT feature_value, count(*) AS group_n FROM expanded GROUP BY feature_value),
                 tiers AS (SELECT DISTINCT target_tier FROM {platform}),
                 counts AS (SELECT feature_value, target_tier, count(*) AS n FROM expanded GROUP BY ALL)
              SELECT groups.feature_value, tiers.target_tier, coalesce(counts.n,0) AS count,
                 groups.group_n, 100.0*coalesce(counts.n,0)/groups.group_n AS percent
              FROM groups CROSS JOIN tiers LEFT JOIN counts USING(feature_value,target_tier)
              ORDER BY groups.feature_value, tiers.target_tier""")
            for record in records:
                distributions.append({"platform": platform, "dimension": dimension, **record,
                                      "train_n": n, "small_sample": record["group_n"] < 30})
            totals = {}
            for record in records:
                entry = totals.setdefault(record["feature_value"], [0, record["group_n"]])
                entry[0] += record["count"]
            if any(count != total for count, total in totals.values()):
                raise ValueError("Outcome counts do not reconcile")
            if dimension not in ("genres", "planning_categories") and sum(total for _, total in totals.values()) != n:
                raise ValueError("Exclusive groups do not reconcile with train denominator")
        for column, kind, *_ in db.execute(f"DESCRIBE {platform}").fetchall():
            if column in ("app_id", "target_tier"):
                continue
            missing = f"{column} IS NULL OR len({column})=0" if kind.endswith("[]") else f"{column} IS NULL"
            m = db.execute(f"SELECT count(*) FROM {platform} WHERE {missing}").fetchone()[0]
            missingness.append({"platform": platform, "column": column, "missing_or_empty_n": m,
                                "train_n": n, "percent": 100.0*m/n})
        ages.extend({"platform": platform, **r} for r in rows(db, f"""SELECT target_tier, count(*) AS n,
          count(age_days) AS age_available_n, quantile_cont(age_days,0.25) AS age_days_p25,
          median(age_days) AS age_days_median, quantile_cont(age_days,0.75) AS age_days_p75
          FROM {platform} GROUP BY target_tier ORDER BY target_tier"""))
        summary[platform] = {"train_n": n, "tier_counts": rows(db, f"SELECT target_tier, count(*) AS n FROM {platform} GROUP BY target_tier ORDER BY target_tier")}
    OUT.mkdir(parents=True, exist_ok=True)
    save_csv("distributions.csv", distributions)
    save_csv("missingness.csv", missingness)
    save_csv("age_by_tier.csv", ages)
    report = ["# Training-only EDA v1", "", "Generated descriptive working notes, not submission prose. No model fitted; no holdout performance evaluated.", "",
              "Source scope: Steam March 2025 positive-observed-price primary cohort; Android June 2021 conservative game cohort. Rows below are TRAIN only.", "",
              "## Outcome balance", "", "| Platform | Train n | Tier | Count | Percent |", "|---|---:|---|---:|---:|"]
    for platform, data in summary.items():
        for r in data["tier_counts"]:
            report.append(f"| {platform} | {data['train_n']:,} | {r['target_tier']} | {r['n']:,} | {100*r['n']/data['train_n']:.2f}% |")
    report += ["", "## Age at observation by outcome tier", "", "| Platform | Tier | Median days | P25 | P75 |", "|---|---|---:|---:|---:|"]
    for r in ages:
        report.append(f"| {r['platform']} | {r['target_tier']} | {r['age_days_median']:.1f} | {r['age_days_p25']:.1f} | {r['age_days_p75']:.1f} |")
    report += ["", "## Interpretation and next experiments", "",
      "- Class counts motivate a majority/class-prior baseline and macro-F1 alongside class-specific results; these counts are not cross-validation scores.",
      "- Age summaries motivate the prespecified age-only and P versus P+A comparisons; they do not establish a causal effect or a fixed-horizon forecast.",
      "- `distributions.csv` covers all prespecified genres/functions or categories/monetization groups, rather than reporting only favorable examples. Within-group percentages have group_n as denominator. Multi-valued PC groups overlap; their totals do not sum to train_n.",
      "- The descriptive age bins (0-179, 180-364, 365-1094, 1095+ days) are display groupings, not newly chosen outcome cutoffs or changes to the frozen split.",
      "- Unknown free is separate from false; missing USD prices are not zero. Missing/empty feature counts are recorded in `missingness.csv`.",
      "- Empty planning_categories can mean no whitelisted planning feature, rather than missing source categories. The empty_or_missing bucket and missingness.csv count structural emptiness; consult categories_unavailable for source unavailability.",
      "- No cross-platform market ranking, significance test, confounder adjustment, revenue inference or causal claim is supported by these tables. Both cohorts have selection limitations; unknown outcomes excluded upstream are not represented here.",
      "- Before candidate fitting, finalize preprocessing and the small parameter grid. Use existing train group-CV, preserve calibration/test, and keep imported application snapshots separate from the research experiment.",
      "", "Reproduce: `uv run --locked python.exe src/analysis/profile_training.py`", ""]
    (OUT / "eda_notes.md").write_text("\n".join(report), encoding="utf-8")
    record = {"version": "train_eda_v1", "partition": "train", "model_training": False,
              "analysis_manifest_sha256": EXPECTED_MANIFEST, "inputs": inputs,
              "script_sha256": digest(Path(__file__)), "summary": summary,
              "outputs": {name: digest(OUT/name) for name in ("distributions.csv", "missingness.csv", "age_by_tier.csv", "eda_notes.md")}}
    (OUT / "manifest.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    db.close()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
