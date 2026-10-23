"""Metric boundaries, raw-data reconciliation and the revenue HTTP contract."""
import hashlib
import json
import math
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.request import urlopen

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src/demo"))
from analysis.revenue_metrics import analyze, price_band, summary
from revenue import RevenueStore
from server import make_server


def row(ident, revenue, price=10, genres=None):
    return {"steam_id": str(ident), "name": f"Game {ident}", "revenue": revenue,
            "price": price, "genres": genres or [], "genre_status": "matched" if genres else "unmatched",
            "publisher_class": "Indie", "price_band": price_band(price)}


class MetricTests(unittest.TestCase):
    def test_empty_results_do_not_claim_zero_revenue(self):
        result = analyze([row(1, 100)], {"q": "nonexistent"})
        self.assertIsNone(result["summary"]["total_revenue"])
        self.assertIsNone(result["summary"]["top_decile_share"])
        self.assertIsNone(result["summary"]["median_revenue"])

    def test_price_boundaries_and_zero_separation(self):
        prices = [0, .01, 9.99, 10, 19.99, 20, 29.99, 30]
        self.assertEqual([price_band(v) for v in prices], ["0", "0 < price < 10", "0 < price < 10", "10 <= price < 20", "10 <= price < 20", "20 <= price < 30", "20 <= price < 30", "price >= 30"])
        data = [row(1, 500, 0), row(2, 100, 10)]
        self.assertEqual(analyze(data)["summary"]["total_revenue"], 100)
        self.assertEqual(analyze(data, {"mode": "zero"})["summary"]["total_revenue"], 500)

    def test_concentration_ceiling_and_overlapping_genres(self):
        rows = [row(i, i, genres=["Action", "Adventure"]) for i in range(1, 12)]
        result = analyze(rows)
        self.assertEqual(result["summary"]["top_decile_count"], 2)
        self.assertAlmostEqual(result["summary"]["top_decile_share"], 21/66)
        self.assertEqual(result["summary"]["total_revenue"], 66)
        self.assertEqual([g["count"] for g in result["by_genre"]], [11, 11])
        self.assertEqual(summary([row(1, 100)])["q25"], 100)

    def test_invalid_query_is_rejected(self):
        for query in [{"split": "test"}, {"mode": "paid"}, {"genre": "invented"}, {"publisher": "unknown"}, {"q": "x" * 101}, {"q": 1}]:
            with self.subTest(query=query), self.assertRaises(ValueError):
                analyze([row(1, 100)], query)


class RevenueIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = RevenueStore(ROOT)
        cls.raw = pd.read_csv(ROOT.parent / "Dataset/Steam Revenue Top 1500 2024/Steam_2024_bestRevenue_1500.csv")
        cls.server = make_server(SimpleNamespace(root=ROOT), 0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join()

    def test_all_subsets_reconcile_directly_to_original_csv(self):
        for mode in ["positive", "zero", "all"]:
            raw = self.raw if mode == "all" else self.raw[self.raw.price.gt(0) if mode == "positive" else self.raw.price.eq(0)]
            result = self.store.query({"mode": [mode]})
            stats = result["summary"]
            self.assertEqual(stats["count"], len(raw))
            self.assertAlmostEqual(stats["total_revenue"], raw.revenue.sum(), places=3)
            self.assertEqual(stats["median_revenue"], raw.revenue.median())
            self.assertEqual(stats["q25"], raw.revenue.quantile(.25))
            self.assertEqual(stats["q75"], raw.revenue.quantile(.75))
            self.assertAlmostEqual(stats["top_decile_share"], raw.revenue.nlargest(math.ceil(len(raw)*.1)).sum()/raw.revenue.sum())
            self.assertEqual(sum(d["count"] for d in result["distribution"]), len(raw))
            self.assertEqual(sum(g["count"] for g in result["by_price"]), len(raw))
            self.assertEqual({r["steam_id"] for r in result["rows"]}, set(raw.steamId.astype(str)))

    def test_http_filters_and_unknown_parameters(self):
        with urlopen(self.url + "/api/revenue?mode=zero") as response:
            self.assertEqual(json.load(response)["summary"]["count"], 85)
        for query in ["mode=bad", "mode=zero&mode=all", "split=test", "genre=nonexistent"]:
            with self.subTest(query=query), self.assertRaises(HTTPError) as error:
                urlopen(self.url + "/api/revenue?" + query)
            self.assertEqual(error.exception.code, 400)
            error.exception.close()
        for path in ["/revenue", "/revenue.js", "/revenue.css"]:
            with urlopen(self.url + path) as response:
                self.assertEqual(response.status, 200)

    def test_artifact_tampering_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            manifest = base / "reports/2026-10-23/revenue_sources/analysis.json"
            artifact = base / "data/processed/revenue_v1/explorer.json"
            manifest.parent.mkdir(parents=True); artifact.parent.mkdir(parents=True)
            manifest.write_text(json.dumps({"artifact_sha256": hashlib.sha256(b"original").hexdigest()}))
            artifact.write_text("changed")
            with self.assertRaises(ValueError):
                RevenueStore(base)


if __name__ == "__main__":
    unittest.main()
