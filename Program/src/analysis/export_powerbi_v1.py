"""Export frozen train-only data for the student's Power BI Desktop exercise.

CSV interchange tables, not new cohorts, models or application versions.
Run from Program: uv run --locked python.exe -B -m src.analysis.export_powerbi_v1
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/processed/powerbi_v1"
REPORT = ROOT / "reports/2026-10-11/lecture_review"
MANIFEST = ROOT / "reports/2026-10-06/analysis_v1/manifest.json"
EXPECTED = "5f3f341ed1c45fbca703995d95d4eca46d54d1af75e69677e15308d20aed12a6"


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def records(db, sql, params=None):
    result = db.execute(sql, params or [])
    return [dict(zip([d[0] for d in result.description], row)) for row in result.fetchall()]


def main():
    if sha(MANIFEST) != EXPECTED:
        raise ValueError("Unexpected frozen analysis manifest")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    db = duckdb.connect()
    inputs, outputs, checks = {}, {}, {}
    OUT.mkdir(parents=True, exist_ok=True)
    for platform in ("pc", "mobile"):
        paths = []
        for kind in ("features", "labels_splits"):
            relative = f"data/processed/analysis_v1/{platform}_{kind}.parquet"
            path = ROOT / relative
            actual = sha(path)
            if actual != manifest["outputs"][relative]:
                raise ValueError(f"Changed frozen input: {relative}")
            inputs[relative] = actual
            paths.append(str(path))
        db.execute(f"""CREATE TABLE {platform}_source AS
            SELECT f.*, l.target_tier FROM read_parquet(?) f
            JOIN read_parquet(?) l USING(app_id) WHERE l.split='train'""", paths)
        # Display labels keep the original tier rule: never infer numeric sales.
        common = """app_id, target_tier,
            CAST(substr(target_tier, 2, 1) AS INTEGER) AS tier_order,
            age_days,
            CASE WHEN age_days IS NULL THEN 'Unknown'
                 WHEN age_days < 180 THEN '0-179 days'
                 WHEN age_days < 365 THEN '180-364 days'
                 WHEN age_days < 1095 THEN '365-1094 days'
                 ELSE '1095+ days' END AS age_band,
            CASE WHEN age_days IS NULL THEN 5 WHEN age_days < 180 THEN 1
                 WHEN age_days < 365 THEN 2 WHEN age_days < 1095 THEN 3
                 ELSE 4 END AS age_band_order"""
        bools = ("windows", "mac", "linux", "categories_unavailable", "languages_unavailable") if platform == "pc" else (
            "free", "ad_supported", "in_app_purchases", "price_usd_unavailable", "free_unavailable")
        extra = ", price_observed" if platform == "pc" else ", category, content_rating, price_usd"
        for column in bools:
            extra += f", CASE WHEN {column} IS NULL THEN 'Unknown' WHEN {column} THEN 'Yes' ELSE 'No' END AS {column}"
        db.execute(f"CREATE TABLE {platform}_games AS SELECT {common}{extra} FROM {platform}_source ORDER BY app_id")
        n, distinct_n = db.execute(f"SELECT count(*), count(DISTINCT app_id) FROM {platform}_games").fetchone()
        if n != distinct_n or n != manifest["summary"][platform]["split_rows"]["train"]:
            raise ValueError("Invalid train membership")
        checks[platform] = {
            "rows": n,
            "tiers": records(db, f"SELECT target_tier, count(*) AS n FROM {platform}_games GROUP BY 1 ORDER BY 1"),
            "age_bands": records(db, f"SELECT age_band, count(*) AS n FROM {platform}_games GROUP BY 1 ORDER BY 1"),
        }
    db.execute("""CREATE TABLE pc_genres AS SELECT app_id,
        unnest(CASE WHEN genres IS NULL OR len(genres)=0 THEN ['<empty_or_missing>']
               ELSE list_sort(list_distinct(genres)) END) AS genre
        FROM pc_source ORDER BY app_id, genre""")
    db.execute("CREATE TABLE genre AS SELECT DISTINCT genre FROM pc_genres ORDER BY genre")
    if db.execute("SELECT count(*) FROM (SELECT app_id,genre FROM pc_genres GROUP BY ALL HAVING count(*)<>1)").fetchone()[0]:
        raise ValueError("Duplicate bridge pair")
    if db.execute("SELECT count(DISTINCT app_id) FROM pc_genres").fetchone()[0] != checks['pc']['rows']:
        raise ValueError("Incomplete genre bridge")
    checks['pc']['genre_union_action_indie'] = records(db, """SELECT target_tier, count(*) AS n FROM pc_games
        WHERE app_id IN (SELECT app_id FROM pc_genres WHERE genre IN ('Action','Indie')) GROUP BY 1 ORDER BY 1""")
    checks['pc']['action_age_365_plus'] = records(db, """SELECT target_tier, count(*) AS n FROM pc_games
        WHERE age_days>=365 AND app_id IN (SELECT app_id FROM pc_genres WHERE genre='Action') GROUP BY 1 ORDER BY 1""")
    checks['mobile']['free'] = records(db, "SELECT free, count(*) AS n FROM mobile_games GROUP BY 1 ORDER BY 1")
    checks['mobile']['paid_age_365_plus'] = records(db, """SELECT target_tier, count(*) AS n
        FROM mobile_games WHERE free='No' AND age_days>=365 GROUP BY 1 ORDER BY 1""")
    checks['mobile']['category_puzzle'] = records(db, """SELECT target_tier, count(*) AS n
        FROM mobile_games WHERE category='Puzzle' GROUP BY 1 ORDER BY 1""")
    for name in ('pc_games', 'mobile_games', 'pc_genres', 'genre'):
        target = OUT / f"{name}.csv"
        result = db.execute(f"SELECT * FROM {name}")
        columns = [d[0] for d in result.description]
        with target.open('w', encoding='utf-8-sig', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(columns)
            writer.writerows(result.fetchall())
        # Read with the intended Power Query column types, preserving IDs and missing values.
        schema = db.execute(f"DESCRIBE {name}").fetchall()
        types = {row[0]: row[1] for row in schema}
        db.read_csv(str(target), header=True, dtype=types).create_view('roundtrip')
        mismatches = db.execute(f"""SELECT count(*) FROM (
            (SELECT * FROM {name} EXCEPT ALL SELECT * FROM roundtrip)
            UNION ALL (SELECT * FROM roundtrip EXCEPT ALL SELECT * FROM {name}))""").fetchone()[0]
        if mismatches:
            raise ValueError(f"CSV round trip differs for {name}")
        db.execute('DROP VIEW roundtrip')
        outputs[target.relative_to(ROOT).as_posix()] = {'sha256': sha(target), 'rows': db.execute(f'SELECT count(*) FROM {name}').fetchone()[0], 'columns': types}
    record = {
        'version': 'powerbi_v1', 'partition': 'train', 'analysis_manifest_sha256': EXPECTED,
        'inputs': inputs, 'outputs': outputs, 'script_sha256': sha(Path(__file__)),
        'checks': checks, 'csv_roundtrip_differences': 0,
        'power_bi_ui_tested': False,
        'scope': 'Research-train descriptive export only; no application snapshot refresh or held-out evaluation.',
    }
    REPORT.mkdir(parents=True, exist_ok=True)
    (REPORT/'powerbi_export_verification.json').write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'rows': {k:v['rows'] for k,v in outputs.items()}, 'checks':checks}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
