"""Integration checks against frozen artifacts; never train or evaluate a model."""
import json
import sys
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import duckdb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/demo"))
from server import ComparisonStore, make_server


class DemoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = ComparisonStore()
        cls.server = make_server(cls.store, 0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.store.db.close()

    def test_membership_and_baseline_counts(self):
        expected = {"pc": [38428, 8527, 4197], "mobile": [103908, 81403, 36495]}
        for platform, counts in expected.items():
            path = str(ROOT / f"data/processed/analysis_v1/{platform}_labels_splits.parquet")
            # Verify every loaded row is in train, not just that counts coincide.
            held_out = self.store.db.execute(f"SELECT count(*) FROM {platform} d JOIN read_parquet(?) l USING(app_id) WHERE l.split <> 'train'", [path]).fetchone()[0]
            self.assertEqual(held_out, 0)
            result = self.store.compare({"platform": platform, "a": {}, "b": {}})
            self.assertEqual(result["partition"], "train")
            self.assertEqual([t["count"] for t in result["scenarios"]["a"]["tiers"]], counts)
            self.assertEqual(result["overlap_count"], sum(counts))

    def test_filtered_counts_against_independent_query(self):
        cases = [("pc", {"genre": "Action", "capability": "Single-player"},
                  "list_contains(f.genres, 'Action') AND list_contains(f.planning_categories, 'Single-player')"),
                 ("mobile", {"category": "Puzzle", "free": "true", "ads": "false"},
                  "f.category = 'Puzzle' AND f.free IS TRUE AND f.ad_supported IS FALSE")]
        for platform, filters, where in cases:
            features = str(ROOT / f"data/processed/analysis_v1/{platform}_features.parquet")
            labels = str(ROOT / f"data/processed/analysis_v1/{platform}_labels_splits.parquet")
            with duckdb.connect() as db:
                expected = dict(db.execute(f"SELECT l.target_tier, count(*) FROM read_parquet(?) f JOIN read_parquet(?) l USING(app_id) WHERE l.split = 'train' AND {where} GROUP BY l.target_tier", [features, labels]).fetchall())
            result = self.store.compare({"platform": platform, "a": filters, "b": {}})
            scenario = result["scenarios"]["a"]
            self.assertEqual({t["id"]: t["count"] for t in scenario["tiers"]}, expected)
            self.assertEqual(result["overlap_count"], scenario["total"])
            self.assertAlmostEqual(sum(t["percent"] for t in scenario["tiers"]), 100, places=3)

    def test_unknown_is_not_paid_and_small_samples(self):
        result = self.store.compare({"platform": "mobile", "a": {"free": "unknown"}, "b": {"free": "false"}})
        self.assertEqual(result["scenarios"]["a"]["total"], 4)
        self.assertEqual(result["scenarios"]["a"]["status"], "small_sample")
        self.assertEqual(result["overlap_count"], 0)

    def test_no_matches_does_not_invent_percentages(self):
        result = self.store.compare({"platform": "mobile", "a": {"free": "unknown", "category": "Casino"}, "b": {}})
        self.assertEqual(result["scenarios"]["a"]["status"], "no_matches")
        self.assertTrue(all(t["percent"] is None for t in result["scenarios"]["a"]["tiers"]))

    def test_invalid_filters_and_split_requests_rejected(self):
        invalid = [{"platform": "test", "a": {}, "b": {}},
                   {"platform": [], "a": {}, "b": {}},
                   {"platform": "pc", "a": {"split": "test"}, "b": {}},
                   {"platform": "pc", "a": {"genre": "' OR 1=1 --"}, "b": {}},
                   {"platform": "mobile", "a": {"free": False}, "b": {}},
                   {"platform": "mobile", "a": [], "b": {}},
                   {"platform": "pc", "a": {}, "b": {}, "split": "test"}]
        for payload in invalid:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                self.store.compare(payload)

    def test_http_contract_and_static_allowlist(self):
        with urlopen(self.url + "/api/options") as response:
            options = json.load(response)
            self.assertEqual(options["platforms"]["mobile"]["train_count"], 221806)
        payload = json.dumps({"platform": "pc", "a": {"genre": "Action"}, "b": {}}).encode()
        with urlopen(Request(self.url + "/api/compare", data=payload, headers={"Content-Type": "application/json"})) as response:
            result = json.load(response)
        self.assertEqual(result["scenarios"]["b"]["total"], 51152)
        for path in ("/PROJECT_STATUS.md", "/../../config/analysis_v1.json"):
            with self.assertRaises(HTTPError) as error:
                urlopen(self.url + path)
            self.assertEqual(error.exception.code, 404)
            error.exception.close()
        with self.assertRaises(HTTPError) as error:
            urlopen(Request(self.url + "/api/compare", data=b"{}"))
        self.assertEqual(error.exception.code, 400)
        error.exception.close()


if __name__ == "__main__":
    unittest.main()
