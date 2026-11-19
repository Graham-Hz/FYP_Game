"""Numerical semantics for distributions, sampling and categorical heatmaps."""
import hashlib
import json
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/demo"))
from market_analytics import analytical_charts, MAX_POINTS, SAFE_NUMBER


def fixture(n=60):
    return pd.DataFrame({
        "app_id": [str(i) for i in range(n)], "title": [f"Game {i}" for i in range(n)],
        "groups": [["Action"] for _ in range(n)], "price": np.arange(n, dtype=float),
        "volume_lower": np.arange(n, dtype=float) * 1000,
        "volume_upper": np.arange(n, dtype=float) * 1000 + 20000,
        "target_tier": ["O1_source_interval_up_to_20k", "O2_source_intervals_20k_to_100k", "O3_source_intervals_100k_plus"] * (n // 3) + ["O1_source_interval_up_to_20k"] * (n % 3),
        "revenue": np.arange(n, dtype=float) * 10000,
        "copies_sold": np.arange(n, dtype=float) * 100,
        "release_date": pd.to_datetime(["2020-01-01"] * n),
        "observed_date": pd.to_datetime(["2021-01-01"] * n),
    })


def configs(frame, source="pc"):
    return {c["id"]: c for c in analytical_charts(frame, source, "proxy", "unknown", "Test source")}


class MarketAnalyticsTests(unittest.TestCase):
    def test_histogram_counts_and_bounds_preserve_zero_and_missing(self):
        frame = fixture(9)
        frame["price"] = [0, 0, 1, 2, 10, 100, 1000, None, None]
        chart = configs(frame)["outcome_histogram"]
        self.assertEqual(sum(row["count"] for row in chart["rows"]), 7)
        self.assertEqual(chart["rows"][0]["lower"], 0)
        self.assertEqual(chart["rows"][-1]["upper"], 1000)
        self.assertEqual(chart["summary"]["missing_rows"], 2)
        self.assertTrue(chart["rows"][-1]["upper_inclusive"])
        known = frame.price.dropna()
        for row in chart["rows"]:
            actual = ((known >= row["lower"]) & ((known <= row["upper"]) if row["upper_inclusive"] else (known < row["upper"]))).sum()
            self.assertEqual(row["count"], actual)
        self.assertIn("幣別未核實", chart["xUnit"])

    def test_boxplot_uses_linear_quartiles_actual_whiskers_and_outlier(self):
        frame = fixture(10)
        frame["price"] = list(range(1, 10)) + [1000]
        row = configs(frame)["genre_boxplot"]["rows"][0]
        self.assertEqual(row["values"], [1, 3.25, 5.5, 7.75, 9])
        self.assertEqual(row["outlier_count"], 1)
        self.assertEqual(row["outliers"], [1000])
        self.assertEqual(row["n"], 10)
        self.assertFalse(configs(frame.head(4))["genre_boxplot"]["rows"])

    def test_scatter_sampling_is_deterministic_and_correlation_uses_all_pairs(self):
        frame = fixture(850)
        frame["volume_lower"] = 900 - frame.price
        chart = configs(frame)["price_outcome_scatter"]
        reverse = configs(frame.iloc[::-1])["price_outcome_scatter"]
        expected_ids = sorted(frame.app_id, key=lambda value: hashlib.sha256(f"pc:{value}".encode()).hexdigest())[:MAX_POINTS]
        self.assertEqual([p["id"] for p in chart["points"]], expected_ids)
        self.assertEqual(chart["points"], reverse["points"])
        self.assertEqual(chart["summary"]["paired_rows"], 850)
        self.assertEqual(chart["summary"]["displayed_rows"], MAX_POINTS)
        self.assertAlmostEqual(chart["summary"]["spearman_rho"], -1)
        self.assertTrue(all(point["y"] == 900 - point["x"] for point in chart["points"]))

    def test_scatter_missing_and_constant_do_not_fabricate_correlation(self):
        frame = fixture(6)
        frame["price"] = [1, 1, 1, None, None, None]
        chart = configs(frame)["price_outcome_scatter"]
        self.assertEqual(chart["summary"]["paired_rows"], 3)
        self.assertIsNone(chart["summary"]["spearman_rho"])
        frame["observed_date"] = pd.NaT
        mobile = configs(frame, "mobile")["price_outcome_scatter"]
        self.assertEqual(mobile["summary"]["paired_rows"], 0)
        self.assertFalse(mobile["points"])

    def test_heatmap_uses_known_denominator_and_exact_revenue_boundaries(self):
        frame = fixture(60)
        frame.loc[0, "target_tier"] = None
        row = configs(frame)["group_outcome_heatmap"]["rows"][0]
        self.assertEqual(row["counts"], [19, 20, 20])
        self.assertEqual(row["n"], 59)
        self.assertEqual(row["unknown_rows"], 1)
        self.assertAlmostEqual(sum(row["values"]), 100)
        frame["revenue"] = ([0, 9999, 10000, 99999, 100000, 999999, 1000000, None] * 8)[:60]
        row = configs(frame, "revenue")["group_outcome_heatmap"]["rows"][0]
        values = frame.revenue
        expected = [int(values.lt(10000).sum()), int((values.ge(10000) & values.lt(100000)).sum()),
                    int((values.ge(100000) & values.lt(1000000)).sum()), int(values.ge(1000000).sum())]
        self.assertEqual(row["counts"], expected)
        self.assertEqual(row["n"], int(values.notna().sum()))

    def test_empty_frames_and_constant_histograms_are_serializable(self):
        for source in ("pc", "mobile", "revenue"):
            chart_set = configs(fixture(0), source)
            self.assertEqual(len(chart_set), 4)
            self.assertTrue(all(not c["rows"] for c in chart_set.values()))
            json.dumps(chart_set, allow_nan=False)
        frame = fixture(5)
        frame["price"] = 0
        rows = configs(frame)["outcome_histogram"]["rows"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["count"], 5)

    def test_rejects_nonfinite_negative_or_unsafe_numeric_values(self):
        for value in (float("inf"), -1, SAFE_NUMBER + 1):
            frame = fixture(5)
            frame.loc[0, "price"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                configs(frame)


if __name__ == "__main__":
    unittest.main()
