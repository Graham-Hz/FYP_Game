import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/data"))
import audit_common
from audit_revenue_sources import normalize_title, numeric_profile, overlap, profile, SOURCES


class RevenueAuditTests(unittest.TestCase):
    def test_name_candidates_preserve_identity_distinctions(self):
        self.assertEqual(normalize_title("  ＰＵＢＧ  Mobile "), "pubg mobile")
        self.assertNotEqual(normalize_title("A / B"), normalize_title("A"))
        self.assertNotEqual(normalize_title("Game 2"), normalize_title("Game"))

    def test_missing_and_nonfinite_are_not_zero(self):
        stats = numeric_profile(pd.Series(["", "oops", "inf", "0", "-2", "10"]))
        self.assertEqual(stats["invalid_or_missing"], 3)
        self.assertEqual(stats["zero"], 1)
        self.assertEqual(stats["negative"], 1)

    def test_overlap_counts_distinct_ids_not_rows(self):
        result = overlap(pd.DataFrame({"id": ["1", "1", "2", "3", ""]}), "id", {"1", "2"}, {"2"})
        self.assertEqual(result["matched_raw_steam_ids"], 2)
        self.assertEqual(result["matched_primary_cohort_ids"], 1)
        self.assertEqual(result["unmatched_raw_ids"], ["3"])

    def test_dates_duplicates_and_raw_file_preservation(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "mobile.csv"
            content = "Game,Revenue,Initial release\nA,100,2020-12-01\nA,100,2020-12-01\nB,,invalid\n"
            path.write_text(content, encoding="utf-8")
            _, _, report = profile(path, SOURCES["mobile_highest_grossing"])
            self.assertEqual(report["exact_duplicate_rows"], 1)
            self.assertEqual(report["rows_in_duplicate_keys"], 2)
            self.assertEqual(report["invalid_dates"], 1)
            self.assertEqual(report["numeric"]["Revenue"]["invalid_or_missing"], 1)
            self.assertEqual(path.read_text(encoding="utf-8"), content)

    def test_new_csv_folders_do_not_enter_original_audit(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            for name in ["Steam Games Dataset 2025", "Steam Revenue Top 1500 2024"]:
                (base / name).mkdir()
                (base / name / "sample.csv").write_text("appid\n1\n")
            (base / "sources_lock.json").write_text(json.dumps({"hf": {"FronkonGames/steam-games-dataset": {"revision": "pinned", "download": {"path": "mock.parquet"}}}}))
            with patch.object(audit_common, "DATA", base), patch.object(audit_common, "META", base):
                result = audit_common.sources()
                inventory = audit_common.original_source_files()
            self.assertIn("artem_sample", [r["key"] for r in result])
            self.assertEqual(len(result), 3)  # one legacy CSV, pinned HF, JSON
            self.assertEqual(inventory, [base / "Steam Games Dataset 2025/sample.csv"])


if __name__ == "__main__":
    unittest.main()
