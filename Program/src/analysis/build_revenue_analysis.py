"""Prepare a separate, reproducible Steam revenue exploration snapshot."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src/data"))
from audit_revenue_sources import sha256, SOURCES
from cleaning_rules import collection
from revenue_metrics import analyze, price_band


def build(root=ROOT):
    source = root.parent / "Dataset" / SOURCES["steam_revenue_2024"]["file"]
    audit = root / "reports/2026-10-23/revenue_sources/audit.json"
    expected = json.loads(audit.read_text(encoding="utf-8"))["sources"]["steam_revenue_2024"]["sha256"]
    if sha256(source) != expected:
        raise ValueError("Revenue source changed; run and review its audit before rebuilding")
    frame = pd.read_csv(source, dtype={"steamId": str}, keep_default_na=False)
    if frame["steamId"].duplicated().any() or not frame["steamId"].str.fullmatch(r"[1-9]\d*").all():
        raise ValueError("Steam IDs must be unique positive integers")
    for column in ["price", "revenue", "copiesSold"]:
        frame[column] = pd.to_numeric(frame[column], errors="raise")
        if not (np.isfinite(frame[column]) & frame[column].ge(0)).all():
            raise ValueError(f"Invalid {column}; review source instead of imputing")
    if (frame["copiesSold"] % 1 != 0).any():
        raise ValueError("Noninteger copies sold")
    dates = pd.to_datetime(frame["releaseDate"], format="%d-%m-%Y", errors="raise")
    if not dates.between("2024-01-01", "2024-09-09").all():
        raise ValueError("Release date outside declared source cohort")
    frame["releaseDate"] = dates.dt.strftime("%Y-%m-%d")
    metadata_source = root.parent / "Dataset/Steam Games Dataset 2025/games_march2025_full.csv"
    metadata_hash = sha256(metadata_source)
    wanted = set(frame["steamId"])
    genres = {}
    for chunk in pd.read_csv(metadata_source, usecols=["appid", "genres"], dtype=str, keep_default_na=False, chunksize=10000):
        for app_id, value in chunk.loc[chunk["appid"].isin(wanted)].itertuples(index=False, name=None):
            if app_id in genres:
                raise ValueError("Duplicate metadata ID; refusing many-to-many join")
            parsed, status = collection(value)
            genres[app_id] = (parsed, "matched" if status == "valid" else "missing_or_invalid")
    records = []
    for row in frame.to_dict("records"):
        labels, status = genres.get(row["steamId"], ([], "unmatched"))
        records.append({"steam_id": row["steamId"], "name": row["name"], "release_date": row["releaseDate"],
                        "price": float(row["price"]), "revenue": float(row["revenue"]),
                        "copies_sold": int(row["copiesSold"]), "publisher_class": row["publisherClass"] or "Unknown",
                        "genres": labels, "genre_status": status, "price_band": price_band(row["price"])})
    if sha256(source) != expected or sha256(metadata_source) != metadata_hash:
        raise ValueError("Inputs changed during processing")
    metadata = {
        "version": "steam_revenue_v1", "created_utc": datetime.now(timezone.utc).isoformat(),
        "source_url": SOURCES["steam_revenue_2024"]["url"], "source_sha256": expected,
        "source_rows": len(records), "source_snapshot": "2024-09-09 (dataset title; per-row capture times unavailable)",
        "metadata_snapshot": "2025-03", "metadata_sha256": metadata_hash,
        "currency": "USD", "currency_basis": "Interpreted using Gamalytic provider conventions; the CSV has no explicit currency column.",
        "methodology_url": "https://gamalytic.com/about",
        "api_definitions_url": "https://api.gamalytic.com/reference/",
        "definitions_checked": "2026-10-23",
        "definition_version_limit": "Current provider definitions checked in 2026; exact 2024 methodology version is not archived in this download.",
        "scope": "Selected top-revenue 2024 releases, not all Steam games. No existing research outcomes or partitions are used.",
        "limitations": [
            "Estimated cumulative gross revenue, not profit or verified developer receipts; does not describe a common first-week window.",
            "Provider release dates can mean full release after Early Access. A 2024 release-date label does not establish that all revenue was earned in 2024.",
            "Current provider documentation separates paid base-game receipts from broader free-to-play revenue; zero observed price does not prove launch-time F2P status.",
            "Default subset is positive observed price; zero-price games remain available separately. No revenue values are imputed or reconstructed from price times copies.",
            "Publisher classes use provider revenue thresholds; Indie does not establish independent ownership or a small studio. These classes are not causal predictors.",
            "Genres come from later March 2025 metadata. Multi-genre groups overlap, unmatched genres are not imputed, and comparisons are descriptive rather than launch-time prediction.",
            "Revenue selection, observation-age differences and estimation error prevent market success probabilities or causal pricing advice.",
        ],
    }
    artifact = root / "data/processed/revenue_v1/explorer.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps({"metadata": metadata, "rows": records}, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    report = {"metadata": metadata, "artifact": "data/processed/revenue_v1/explorer.json", "artifact_sha256": sha256(artifact),
              "preparation": {"rows_retained": len(records), "metadata_id_matches": len(genres),
                              "valid_genre_rows": sum(r["genre_status"] == "matched" for r in records),
                              "excluded_rows": 0, "imputed_revenue_values": 0}, "subsets": {}}
    for mode in ["positive", "zero", "all"]:
        result = analyze(records, {"mode": mode})
        report["subsets"][mode] = {k: v for k, v in result.items() if k != "rows"}
    output = root / "reports/2026-10-23/revenue_sources/analysis.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"preparation": report["preparation"], "positive_price": report["subsets"]["positive"]["summary"]}, indent=2))
    return report


if __name__ == "__main__":
    build()
