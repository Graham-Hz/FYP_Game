"""Validate converted research-train CSVs against every frozen comparison row.

Requires the two explicitly converted CSVs documented in CSV_IMPORT_GUIDE.md.
Uses disposable snapshot storage; never changes the user's active versions.
"""
import hashlib
import json
import sys
import tempfile
import time
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src/demo"))
from imports.contracts import validate, rule_fingerprint
from imports.repository import SnapshotRepository, digest
from server import ComparisonStore


def main():
    result = {"date": "2026-10-10", "status": "passed", "rule_sha256": rule_fingerprint(), "platforms": {}}
    with tempfile.TemporaryDirectory() as temporary:
        repository = SnapshotRepository(Path(temporary))
        versions = {}
        for platform in ("pc", "mobile"):
            started = time.monotonic()
            source = ROOT / f"data/application/conversions/{platform}_train_v1"
            raw = (source / "snapshot.csv").read_bytes()
            meta = json.loads((source / "metadata.json").read_text(encoding="utf-8"))
            prepared = validate(raw, meta)
            summary, table, _ = prepared
            assert summary["can_import"] and summary["invalid_rows"] == 0 and summary["excluded_rows"] == 0, summary
            # Full membership, labels and comparison attributes, not only aggregate counts.
            with duckdb.connect() as db:
                db.register("imported", table)
                db.execute("CREATE TABLE expected AS SELECT f.*, l.target_tier FROM read_parquet(?) f JOIN read_parquet(?) l USING(app_id) WHERE l.split='train'",
                           [str(ROOT / f"data/processed/analysis_v1/{platform}_features.parquet"), str(ROOT / f"data/processed/analysis_v1/{platform}_labels_splits.parquet")])
                extra = (" OR list_sort(i.genres) IS DISTINCT FROM list_sort(e.genres) OR list_sort(i.planning_categories) IS DISTINCT FROM list_sort(e.planning_categories)"
                         if platform == "pc" else " OR i.category IS DISTINCT FROM e.category OR i.free IS DISTINCT FROM e.free OR i.ad_supported IS DISTINCT FROM e.ad_supported OR i.in_app_purchases IS DISTINCT FROM e.in_app_purchases")
                differences = db.execute("SELECT count(*) FROM imported i FULL OUTER JOIN expected e USING(app_id) WHERE i.app_id IS NULL OR e.app_id IS NULL OR i.target_tier IS DISTINCT FROM e.target_tier" + extra).fetchone()[0]
                assert differences == 0, (platform, differences)
            saved = repository.save(raw, meta, prepared)
            versions[platform] = saved["version_id"]
            result["platforms"][platform] = {"rows": summary["eligible_rows"], "csv_bytes": len(raw), "csv_sha256": hashlib.sha256(raw).hexdigest(),
                                           "all_row_comparison_differences": differences, "warnings": summary["warnings"],
                                           "tiers": summary["tiers"], "validation_and_save_seconds": round(time.monotonic() - started, 3)}
            print(platform, summary["eligible_rows"], "rows verified", flush=True)
        store = ComparisonStore(app_path=Path(temporary))
        try:
            for platform, ident in versions.items():
                store.activate(platform, ident)
                comparison = store.compare(dict(platform=platform, version_id=ident, a={}, b={}))
                assert comparison["scenarios"]["a"]["total"] == result["platforms"][platform]["rows"]
        finally:
            store.db.close()
        restarted = ComparisonStore(app_path=Path(temporary))
        try: assert restarted.active == versions
        finally: restarted.db.close()
    result["application_restart_verified"] = True
    result["research_manifest_sha256"] = digest(ROOT / "reports/2026-10-06/analysis_v1/manifest.json")
    result["validator_sha256"] = digest(ROOT / "src/imports/contracts.py")
    result["verifier_sha256"] = digest(Path(__file__))
    result["note"] = "Existing train rows only; no new training, calibration/test scoring, or independent external-data validity claim."
    output = ROOT / "reports/2026-10-10/csv_import_v1"
    output.mkdir(parents=True, exist_ok=True)
    (output / "real_data_verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__": main()
