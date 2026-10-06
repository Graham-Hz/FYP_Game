"""Independent SQL reconciliation of every cohort ID and label, plus artifact hashes."""
import json

from audit_common import ROOT, INTERIM, connection, lit, save_json, sha256


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    config_path = ROOT / "config/cleaning_candidate_v1.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    reports = ROOT / "reports" / config["report_date"] / config["version"]
    manifest_path = reports / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    (reports / "verification.json").unlink(missing_ok=True)
    require(manifest["generation_complete"], "Generation incomplete")
    require(sha256(config_path) == manifest["config_sha256"], "Configuration changed")
    for field in ["input_sha256", "output_sha256", "code_sha256"]:
        for relative, expected in manifest[field].items():
            require(sha256(ROOT / relative) == expected, f"Hash changed: {relative}")
    conn = connection()
    counts = {}
    for platform in ["pc", "mobile"]:
        source = INTERIM / config["inputs"][platform]["file"]
        out = INTERIM / config["version"]
        conn.execute(f"CREATE OR REPLACE VIEW src AS SELECT * FROM read_parquet({lit(source)})")
        conn.execute(f"CREATE OR REPLACE VIEW candidates AS SELECT * FROM read_parquet({lit(out / (platform + '_candidates.parquet'))})")
        conn.execute(f"CREATE OR REPLACE VIEW ledger AS SELECT * FROM read_parquet({lit(out / (platform + '_row_ledger.parquet'))})")
        require(conn.execute("SELECT count(*)=count(DISTINCT app_id) AND count(*)=count(app_id) FROM candidates").fetchone()[0], "Candidate IDs invalid")
        require(conn.execute("SELECT count(*)=count(DISTINCT app_id) AND count(*)=count(app_id) FROM ledger").fetchone()[0], "Ledger IDs invalid")
        require(conn.execute("SELECT count(*) FROM src FULL JOIN ledger USING(app_id) WHERE src.app_id IS NULL OR ledger.app_id IS NULL").fetchone()[0] == 0, "Ledger source coverage differs")
        if platform == "pc":
            # Assert parser premises before independently checking the current list representation.
            for column in ["genres", "categories", "supported_languages", "developers"]:
                require(conn.execute(f"SELECT count(*) FROM ledger WHERE flag_{column}_parse_error").fetchone()[0] == 0, f"Unresolved {column} parse errors")
            query = f"""
            WITH parsed AS (
              SELECT *, try_strptime(release_date,'%Y-%m-%d') AS released,
                DATE {lit(config['pc_reference_date_proxy'])} AS observed,
                try_cast(regexp_extract(estimated_owners,'^(\\d+)\\s*-\\s*(\\d+)$',1) AS BIGINT) AS lo,
                try_cast(regexp_extract(estimated_owners,'^(\\d+)\\s*-\\s*(\\d+)$',2) AS BIGINT) AS hi
              FROM src)
            SELECT app_id, coalesce(name IS NOT NULL AND trim(name)<>'' AND
              genres IS NOT NULL AND trim(genres) NOT IN ('','[]','{{}}') AND released<=observed AND
              NOT regexp_matches(lower(name),{lit(config['pc_demo_title_pattern'])}), false) AS eligible,
              CASE WHEN lo>=0 AND hi>0 AND lo<=hi THEN
                CASE WHEN hi<=20000 THEN 'O1_source_interval_up_to_20k'
                     WHEN lo>=100000 THEN 'O3_source_intervals_100k_plus'
                     WHEN lo>=20000 AND hi<=100000 THEN 'O2_source_intervals_20k_to_100k' END END AS target,
              date_diff('day',released,observed) AS age
            FROM parsed
            """
        else:
            query = """
            WITH parsed AS (
              SELECT *, try_strptime(released,'%b %d, %Y') AS release,
                cast(try_strptime(scraped_time,'%Y-%m-%d %H:%M:%S') AS DATE) AS observed,
                try_cast(minimum_installs AS DOUBLE) AS numeric_installs FROM src)
            SELECT app_id, coalesce(app_name IS NOT NULL AND trim(app_name)<>'' AND release<=observed,false) AS eligible,
              CASE WHEN numeric_installs>=0 AND isfinite(numeric_installs) AND numeric_installs=floor(numeric_installs) THEN
                CASE WHEN numeric_installs<1000 THEN 'M1_under_1k'
                     WHEN numeric_installs<100000 THEN 'M2_1k_to_under_100k'
                     ELSE 'M3_100k_plus' END END AS target,
              date_diff('day',release,observed) AS age
            FROM parsed
            """
        conn.execute("CREATE OR REPLACE TEMP TABLE expected AS " + query)
        require(conn.execute("SELECT count(*) FROM expected JOIN ledger USING(app_id) WHERE eligible IS DISTINCT FROM eligible_base OR (eligible AND target IS NOT NULL) IS DISTINCT FROM eligible_labelled").fetchone()[0] == 0, f"{platform} per-row eligibility differs from independent SQL")
        require(conn.execute("SELECT count(*) FROM (SELECT * FROM expected WHERE eligible) e FULL JOIN candidates c USING(app_id) WHERE e.app_id IS NULL OR c.app_id IS NULL OR e.target IS DISTINCT FROM c.target_tier OR e.age IS DISTINCT FROM c.age_days").fetchone()[0] == 0, f"{platform} candidate labels, ages or IDs differ")
        require(conn.execute("SELECT count(*) FROM ledger WHERE eligible_base IS DISTINCT FROM (first_exclusion_reason='retained')").fetchone()[0] == 0, "Exclusion reasons inconsistent")
        require(conn.execute("SELECT count(*) FROM candidates WHERE label_available IS DISTINCT FROM (target_tier IS NOT NULL) OR age_days<0").fetchone()[0] == 0, "Label availability or age invalid")
        if platform == "mobile":
            require(conn.execute("SELECT count(*) FROM candidates c JOIN src s USING(app_id) WHERE price_usd IS DISTINCT FROM CASE WHEN upper(trim(s.currency))='USD' AND try_cast(s.price AS DOUBLE)>=0 AND isfinite(try_cast(s.price AS DOUBLE)) THEN try_cast(s.price AS DOUBLE) END").fetchone()[0] == 0, "USD price isolation failed")
            require(conn.execute("SELECT count(*) FROM candidates WHERE app_id IN ('com.DN.None','com.Tomkii.NULl')").fetchone()[0] == 2, "Literal-title regression")
        actual = conn.execute("SELECT count(*), count(target_tier) FROM candidates").fetchone()
        recorded = manifest["platforms"][platform]
        require(actual == (recorded["base_candidate_rows"], recorded["labelled_candidate_rows"]), "Manifest count mismatch")
        counts[platform] = {"base_rows": actual[0], "labelled_rows": actual[1]}
    save_json(reports / "verification.json", {"status": "passed", "manifest_sha256": sha256(manifest_path),
        "verifier_sha256": sha256(ROOT / "src/data/verify_clean_candidates.py"), "counts": counts,
        "checks": ["all input/output/config/generator hashes", "unique IDs and complete ledger coverage", "independent SQL eligibility for every source row", "independent SQL labels and ages for every candidate", "unknown targets excluded from labelled eligibility", "USD-only Mobile prices", "literal Mobile titles retained"],
        "limitation": "Mechanical consistency, not validation of target meaning or supervisor approval."})
    print(json.dumps({"verification": "passed", "counts": counts}, indent=2))


if __name__ == "__main__":
    main()
