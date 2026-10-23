"""Audit supplementary revenue CSVs without modifying sources or model cohorts.

Only identifiers are read from frozen analysis tables. No reserved outcomes are
inspected. Name matches are candidates for manual review, never automatic joins.
"""
import argparse
import hashlib
import json
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SOURCES = {
    "steam_revenue_2024": {
        "file": "Steam Revenue Top 1500 2024/Steam_2024_bestRevenue_1500.csv",
        "url": "https://www.kaggle.com/datasets/alicemtopcu/top-1500-games-on-steam-by-revenue-09-09-2024",
        "key": "steamId", "title": "name", "date": "releaseDate", "format": "%d-%m-%Y",
        "numeric": ["copiesSold", "price", "revenue", "avgPlaytime", "reviewScore"],
        "interpretation": "Gamalytic-derived estimated gross revenue; top-1500 selection, not a representative Steam cohort. Author describes releases from 2024-01-01 to 2024-09-09; check actual dates below. Not profit or verified developer receipts.",
    },
    "mobile_highest_grossing": {
        "file": "Highest Grossing Mobile Games/mobile-games.csv",
        "url": "https://www.kaggle.com/datasets/mattop/highest-grossing-mobile-games",
        "key": "Game", "title": "Game", "date": "Initial release", "format": "%Y-%m-%d",
        "numeric": ["Revenue"],
        "interpretation": "Cumulative high-grossing mobile-game revenue compilation; not Android-only. Per-title revenue cutoff, platform coverage and revenue components are not supplied in the CSV. Release date is not a revenue observation date.",
    },
    "steam_launch_panel_2026": {
        "file": "Steam Launch Lever Panel 2026/steam-launch-lever-panel-2026.csv",
        "url": "https://huggingface.co/datasets/steamforecast/steam-launch-lever-panel-2026",
        "key": "appid", "title": "name", "date": "release_date", "format": "%Y-%m-%d",
        "numeric": ["y_week1_cents", "y_log_week1", "recommendations_total"],
        "interpretation": "First-week gross revenue proxy in USD cents, derived from owners/reviews, price and assumed first-week shares. Not observed first-week sales; selected paid-game sample. Review/price predictors can reproduce the target construction.",
    },
}


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def normalize_title(value):
    # Preserve punctuation and combined titles to avoid speculative matching.
    return " ".join(unicodedata.normalize("NFKC", str(value)).casefold().split())


def numeric_profile(values):
    parsed = pd.to_numeric(values, errors="coerce")
    finite = parsed.notna() & np.isfinite(parsed)
    clean = parsed[finite]
    return {
        "invalid_or_missing": int((~finite).sum()),
        "negative": int((clean < 0).sum()), "zero": int((clean == 0).sum()),
        "minimum": float(clean.min()) if len(clean) else None,
        "median": float(clean.median()) if len(clean) else None,
        "maximum": float(clean.max()) if len(clean) else None,
    }


def profile(path, spec):
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    required = {spec["key"], spec["title"], spec["date"], *spec["numeric"]}
    if missing := required - set(frame.columns):
        raise ValueError(f"{path.name}: missing columns {sorted(missing)}")
    dates = pd.to_datetime(frame[spec["date"]], format=spec["format"], errors="coerce")
    valid_dates = dates.dropna()
    key_counts = frame.loc[frame[spec["key"]].str.strip().ne(""), spec["key"]].value_counts()
    result = {
        "file": str(path), "sha256": sha256(path), "bytes": path.stat().st_size,
        "source_url": spec["url"], "interpretation": spec["interpretation"],
        "rows": len(frame), "columns": list(frame.columns),
        "missing_by_column": {c: int(frame[c].str.strip().eq("").sum()) for c in frame},
        "exact_duplicate_rows": int(frame.duplicated().sum()),
        "duplicate_nonblank_keys": int((key_counts > 1).sum()),
        "rows_in_duplicate_keys": int(key_counts[key_counts > 1].sum()),
        "invalid_dates": int(dates.isna().sum()),
        "release_date_min": valid_dates.min().date().isoformat() if len(valid_dates) else None,
        "release_date_max": valid_dates.max().date().isoformat() if len(valid_dates) else None,
        "release_year_counts": {str(int(k)): int(v) for k, v in valid_dates.dt.year.value_counts().sort_index().items()},
        "numeric": {c: numeric_profile(frame[c]) for c in spec["numeric"]},
    }
    return frame, dates, result


def overlap(frame, key, raw_ids, cohort_ids):
    ids = set(frame[key]) - {""}
    return {
        "unique_source_ids": len(ids), "matched_raw_steam_ids": len(ids & raw_ids),
        "matched_primary_cohort_ids": len(ids & cohort_ids),
        "raw_match_percent": round(100 * len(ids & raw_ids) / len(ids), 2) if ids else None,
        "unmatched_raw_ids": sorted(ids - raw_ids),
    }


def run(workspace, output):
    dataset = workspace / "Dataset"
    program = workspace / "Program"
    frames, summaries = {}, {}
    for name, spec in SOURCES.items():
        frame, dates, summary = profile(dataset / spec["file"], spec)
        frames[name] = frame
        if name == "steam_revenue_2024":
            outside = dates.notna() & ~dates.between("2024-01-01", "2024-09-09")
            summary["outside_author_release_window"] = int(outside.sum())
            summary["outside_window_examples"] = frame.loc[outside, ["steamId", "name", "releaseDate"]].head(10).to_dict("records")
            summary["publisher_class_counts"] = frame["publisherClass"].value_counts().to_dict()
            for c in ["steamId", "copiesSold"]:
                n = pd.to_numeric(frame[c], errors="coerce")
                summary[c + "_invalid_integer"] = int((n.isna() | ~np.isfinite(n) | (n % 1 != 0) | (n < (1 if c == "steamId" else 0))).sum())
            scores = pd.to_numeric(frame["reviewScore"], errors="coerce")
            summary["review_scores_outside_0_100"] = int((~scores.between(0, 100)).sum())
            prices = pd.to_numeric(frame["price"], errors="coerce")
            revenue = pd.to_numeric(frame["revenue"], errors="coerce")
            zero_price_revenue = prices.eq(0) & revenue.gt(0)
            summary["zero_price_positive_revenue_rows"] = int(zero_price_revenue.sum())
            summary["zero_price_positive_revenue_examples"] = frame.loc[zero_price_revenue, ["steamId", "name", "price", "revenue"]].head(10).to_dict("records")
            summary["interpretation_flags"] = [
                "Zero price with positive revenue requires source-method verification; do not impute revenue as price times copies or treat these as errors automatically.",
                "publisherClass is a provider label, not a verified measure of independent ownership or studio size.",
                "September 2024 outcomes joined to March 2025 metadata support descriptive comparisons only; later metadata is not evidence of launch-time features.",
                "Review score zero is preserved; its missing/unrated semantics need verification before score analysis.",
            ]
        if name == "steam_launch_panel_2026":
            cents = pd.to_numeric(frame["y_week1_cents"], errors="coerce")
            logs = pd.to_numeric(frame["y_log_week1"], errors="coerce")
            valid = (cents > 0) & np.isfinite(cents) & np.isfinite(logs)
            summary["log_check"] = {
                "valid_rows": int(valid.sum()), "tolerance": 0.00001,
                "rows_matching_ln_cents": int(np.isclose(logs[valid], np.log(cents[valid]), atol=0.00001, rtol=0).sum()),
                "rows_matching_log10_cents": int(np.isclose(logs[valid], np.log10(cents[valid]), atol=0.00001, rtol=0).sum()),
                "note": "Dataset card says log10; compare actual values before using this field.",
            }
            summary["source_quality_counts"] = frame["source_quality"].value_counts().to_dict()
            summary["estimated_week1_usd"] = numeric_profile(cents / 100)
        summaries[name] = summary

    raw_ids = set()
    steam_raw = dataset / "Steam Games Dataset 2025/games_march2025_full.csv"
    for chunk in pd.read_csv(steam_raw, usecols=["appid"], dtype=str, chunksize=10000):
        raw_ids.update(chunk["appid"].dropna())
    cohort_path = program / "data/processed/analysis_v1/pc_features.parquet"
    cohort_ids = set(pd.read_parquet(cohort_path, columns=["app_id"])["app_id"].astype(str))
    for name in ["steam_revenue_2024", "steam_launch_panel_2026"]:
        summaries[name]["id_overlap"] = overlap(frames[name], SOURCES[name]["key"], raw_ids, cohort_ids)

    # Count conservative name candidates only; do not infer Android revenue from
    # a title match, or merge iOS/Android/combined-game revenue into app rows.
    mobile = frames["mobile_highest_grossing"]
    wanted = {normalize_title(t) for t in mobile["Game"]}
    candidates = {title: set() for title in wanted}
    mobile_raw = dataset / "Google Play Store Apps/Google-Playstore.csv"
    for chunk in pd.read_csv(mobile_raw, usecols=["App Name", "App Id"], dtype=str, keep_default_na=False, chunksize=100000):
        normalized = chunk["App Name"].map(normalize_title)
        for title, app_id in zip(normalized[normalized.isin(wanted)], chunk.loc[normalized.isin(wanted), "App Id"]):
            if app_id:
                candidates[title].add(app_id)
    counts = Counter(len(candidates[normalize_title(t)]) for t in mobile["Game"])
    summaries["mobile_highest_grossing"]["name_match_review"] = {
        "method": "Unicode NFKC + casefold + whitespace; punctuation preserved, no fuzzy or combined-title matching.",
        "unmatched_source_rows": counts[0], "single_candidate_source_rows": counts[1],
        "ambiguous_source_rows": sum(v for k, v in counts.items() if k > 1),
        "candidates": [{"title": title, "app_ids": sorted(candidates[normalize_title(title)])} for title in mobile["Game"] if candidates[normalize_title(title)]],
        "status": "Candidates only. Identity, publisher, platform and observation-period verification required; no automatic join.",
    }
    for name, spec in SOURCES.items():
        if sha256(dataset / spec["file"]) != summaries[name]["sha256"]:
            raise RuntimeError("Source changed during audit")
    report = {
        "audit_version": 1, "generated_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Supplementary source quality and identifier overlap only. No cleaning, model fitting, outcome inspection or activation.",
        "reference_inputs": {
            "steam_raw": {"file": str(steam_raw), "bytes": steam_raw.stat().st_size, "mtime_ns": steam_raw.stat().st_mtime_ns, "unique_ids": len(raw_ids)},
            "steam_cohort": {"file": str(cohort_path), "sha256": sha256(cohort_path), "unique_ids": len(cohort_ids)},
            "mobile_raw": {"file": str(mobile_raw), "bytes": mobile_raw.stat().st_size, "mtime_ns": mobile_raw.stat().st_mtime_ns},
        },
        "sources": summaries,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    for name, s in summaries.items():
        print(name, json.dumps({k: s[k] for k in ["rows", "exact_duplicate_rows", "release_date_min", "release_date_max"]}))
        if "id_overlap" in s:
            print("ID overlap:", json.dumps({k: v for k, v in s["id_overlap"].items() if k != "unmatched_raw_ids"}))
    print("Report:", output)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=ROOT.parent)
    parser.add_argument("--output", type=Path, default=ROOT / "reports/2026-10-23/revenue_sources/audit.json")
    args = parser.parse_args()
    run(args.workspace, args.output)
