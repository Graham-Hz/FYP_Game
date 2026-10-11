"""Explicit adapters for the two audited Kaggle CSV layouts; no arbitrary CSV inference."""
import argparse
import ast
import csv
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from imports.contracts import GAME_CATEGORIES, HEADERS, OUTCOMES, iso_date, policies
from imports.repository import digest, encoded

SOURCE_FIELDS = {
    "pc": "appid,name,release_date,genres,categories,developers,price,estimated_owners".split(","),
    "mobile": "App Id,App Name,Category,Released,Scraped Time,Developer Id,Free,Ad Supported,In App Purchases,Minimum Installs,Price,Currency".split(","),
}


def source_list(value):
    if value.strip().lower() in {"", "nan", "none", "null"}:
        return []
    try:
        result = ast.literal_eval(value)
    except (ValueError, SyntaxError):
        raise ValueError("來源集合無法解析，請核對來源欄位。") from None
    if not isinstance(result, list) or any(not isinstance(x, str) for x in result):
        raise ValueError("來源集合不是字串陣列。")
    return result


def convert(platform, source, output, snapshot_date, source_name, source_url, research_train_only=False):
    iso_date(snapshot_date)
    if output.exists():
        raise ValueError("輸出資料夾已存在；請用新名稱，避免覆寫。")
    config, _ = policies()
    ids = None
    if research_train_only:
        import duckdb
        manifest_path = ROOT / "reports/2026-10-06/analysis_v1/manifest.json"
        if digest(manifest_path) != "5f3f341ed1c45fbca703995d95d4eca46d54d1af75e69677e15308d20aed12a6":
            raise ValueError("Research manifest changed")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        rel = f"data/processed/analysis_v1/{platform}_labels_splits.parquet"
        if digest(ROOT / rel) != manifest["outputs"][rel]:
            raise ValueError("Research split changed")
        with duckdb.connect() as db:
            ids = {v for v, in db.execute("SELECT app_id FROM read_parquet(?) WHERE split = 'train'", [str(ROOT / rel)]).fetchall()}
    source_hash = digest(source)
    output.mkdir(parents=True)
    counts = Counter()
    csv.field_size_limit(8 * 1024 * 1024)  # Source descriptions may be large; none are copied.
    try:
        with source.open(encoding="utf-8-sig", newline="") as f, (output / "snapshot.csv").open("x", encoding="utf-8-sig", newline="") as target:
            reader = csv.DictReader(f)
            if len(reader.fieldnames or []) != len(set(reader.fieldnames or [])) or not set(SOURCE_FIELDS[platform]) <= set(reader.fieldnames or []):
                raise ValueError("來源表頭不符合此 adapter 的已知格式。")
            writer = csv.DictWriter(target, fieldnames=HEADERS[platform]); writer.writeheader()
            for row in reader:
                counts["source_rows"] += 1
                app_id = row["appid" if platform == "pc" else "App Id"]
                if ids is not None and app_id not in ids:
                    counts["outside_research_train"] += 1
                    continue
                if platform == "mobile" and row["Category"] not in GAME_CATEGORIES:
                    counts["outside_game_categories"] += 1
                    continue
                if platform == "pc":
                    categories = source_list(row["categories"])
                    planning = [x for x in categories if x in config["pc_planning_categories"]]
                    counts["nonplanning_feature_tokens_omitted"] += len(categories) - len(planning)
                    owner = row["estimated_owners"].strip()
                    match = re.fullmatch(r"(\d+)\s*-\s*(\d+)", owner)
                    if owner and not match:
                        raise ValueError(f"來源紀錄 {counts['source_rows']} 的 owners 無法解析。")
                    result = dict(app_id=app_id, title=row["name"], release_date=row["release_date"], observed_date="",
                                  genres=json.dumps(source_list(row["genres"]), ensure_ascii=False),
                                  planning_categories=json.dumps(planning, ensure_ascii=False),
                                  developers=json.dumps(source_list(row["developers"]), ensure_ascii=False),
                                  price_observed=row["price"], owner_lower=match[1] if match else "", owner_upper=match[2] if match else "")
                else:
                    release = row["Released"].strip()
                    if release:
                        try: release = datetime.strptime(release, "%b %d, %Y").date().isoformat()
                        except ValueError: pass  # Validator reports unrecognized dates instead of inventing one.
                    scraped = row["Scraped Time"].strip()
                    if scraped:
                        try: scraped = datetime.strptime(scraped, "%Y-%m-%d %H:%M:%S").date().isoformat()
                        except ValueError: pass
                    result = dict(app_id=app_id, title=row["App Name"], release_date=release, observed_date=scraped,
                                  category=row["Category"], developer_id=row["Developer Id"], free=row["Free"],
                                  ad_supported=row["Ad Supported"], in_app_purchases=row["In App Purchases"],
                                  minimum_installs=row["Minimum Installs"], price=row["Price"], currency=row["Currency"])
                writer.writerow(result)
                counts["written_rows"] += 1
        if ids is not None and counts["written_rows"] != len(ids):
            raise ValueError("Source does not fully cover frozen train IDs")
        metadata = dict(platform=platform, source_name=source_name, source_url=source_url, snapshot_date=snapshot_date,
                        outcome_definition=OUTCOMES[platform], data_kind="historical", price_currency="unknown" if platform == "pc" else "per_row")
        (output / "metadata.json").write_bytes(encoded(metadata))
        (output / "conversion.json").write_bytes(encoded({"adapter": "audited_kaggle_v1", "platform": platform,
             "source_path": str(source.resolve()), "source_sha256": source_hash, "counts": dict(counts),
             "research_train_only": research_train_only, "snapshot_sha256": digest(output / "snapshot.csv"),
             "note": "Explicit conversion only; validate before import. PC observed_date left blank because snapshot date is a proxy."}))
        return dict(counts)
    except Exception:
        # Keep any partial output visibly marked, never claim successful conversion or import it.
        (output / "FAILED.txt").write_text("Conversion did not complete. Do not import this partial snapshot. Use a new output directory after fixing the source.\n", encoding="utf-8")
        raise


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--platform", choices=HEADERS, required=True)
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--snapshot-date", required=True)
    p.add_argument("--source-name", required=True)
    p.add_argument("--source-url", default="")
    p.add_argument("--research-train-only", action="store_true")
    args = p.parse_args()
    try: print(json.dumps(convert(args.platform, args.input, args.output_dir, args.snapshot_date, args.source_name, args.source_url, args.research_train_only)))
    except (OSError, ValueError, csv.Error) as exc: p.exit(2, f"{exc}\n")


if __name__ == "__main__": main()
