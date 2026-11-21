"""Readiness reflects real fields/pairs and never replaces missingness with zero."""
import json
import sys
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/demo"))
sys.path.insert(0, str(ROOT / "src"))
from market import MarketStore, TIERS
from market_availability import annotate_charts
from market_cohorts import compare
from test_market_analytics import fixture


def analyze(frame, source="pc", comparison=None):
    frame = frame.copy()
    frame["source_tags"] = [[] for _ in range(len(frame))]
    frame["detail_available"] = True
    if source == "mobile":
        for field in ("free", "ad_supported", "in_app_purchases"):
            if field not in frame:
                frame[field] = True
        frame["target_tier"] = [TIERS["mobile"][i % 3][0] for i in range(len(frame))]
    data = {"source": {"id": source, "name": "Test source", "snapshot": "2026-01", "version_id": "test",
                       "group_label": "玩法類型", "limitations": []}, "unit": "proxy",
            "provenance": {"price_currency": "USD"}}
    filters = {"top_n": 10, "group": "", "tag": "", "year_from": None, "year_to": None, "rank_metric": "volume"}
    result = MarketStore._analyze(object(), data, frame, filters, comparison)
    json.dumps(result, allow_nan=False)
    return {chart["id"]: chart for chart in result["charts"]}


class ChartAvailabilityTests(unittest.TestCase):
    def test_every_source_chart_has_concrete_contract_and_original_values(self):
        for source in ("pc", "mobile", "revenue"):
            with self.subTest(source=source):
                charts = analyze(fixture(), source)
                self.assertEqual(len(charts), 14)
                for chart in charts.values():
                    readiness = chart["availability"]
                    self.assertIn(readiness["status"], {"available", "limited", "unavailable"})
                    self.assertTrue(readiness["reason"])
                    self.assertTrue(readiness["requirements"])
                    self.assertEqual(readiness["total_rows"], 60)
                    self.assertLessEqual(readiness["valid_rows"], 60)
                self.assertEqual(charts["group_count"]["rows"][0]["values"], [60])
                self.assertEqual(charts["group_volume_total"]["rows"][0]["values"][0], 1770000)

    def test_empty_filters_do_not_advertise_prebuilt_zero_bins_as_data(self):
        for source in ("pc", "mobile", "revenue"):
            charts = analyze(fixture(0), source)
            self.assertTrue(all(chart["availability"]["status"] == "unavailable" for chart in charts.values()))
            self.assertTrue(all(chart["availability"]["valid_rows"] == 0 for chart in charts.values()))
            if source != "revenue":
                self.assertEqual([r["values"] for r in charts["outcome_tiers"]["rows"]], [[0], [0], [0]])

    def test_missing_dates_disable_cohorts_and_android_scatter_only(self):
        frame = fixture()
        frame["release_date"] = pd.NaT
        charts = analyze(frame, "mobile")
        for ident in ("release_count", "release_volume_median", "price_outcome_scatter"):
            self.assertEqual(charts[ident]["availability"]["status"], "unavailable")
            self.assertTrue(charts[ident]["availability"]["action"])
        self.assertEqual(charts["top_games"]["availability"]["status"], "available")
        frame = fixture()
        self.assertEqual(analyze(frame)["release_count"]["availability"]["observed_periods"], 1)
        self.assertEqual(analyze(frame)["release_count"]["availability"]["status"], "limited")
        frame.loc[0, "release_date"] = pd.Timestamp("2019-01-01")
        self.assertEqual(analyze(frame)["release_count"]["availability"]["status"], "available")

    def test_missing_prices_do_not_become_zero_or_fake_scatter(self):
        frame = fixture()
        frame["price"] = float("nan")
        charts = analyze(frame)
        for ident in ("outcome_histogram", "genre_boxplot", "business_volume_median", "price_outcome_scatter"):
            self.assertEqual(charts[ident]["availability"]["status"], "unavailable")
        self.assertEqual(charts["business_count"]["availability"]["status"], "limited")
        self.assertEqual(charts["business_count"]["rows"][-1]["values"], [60])
        self.assertEqual(charts["business_count"]["rows"][0]["values"], [0])
        self.assertEqual(charts["top_games"]["availability"]["status"], "available")

    def test_scatter_single_pair_constant_axis_and_partial_pairs(self):
        frame = fixture(6)
        frame.loc[1:, "price"] = float("nan")
        chart = analyze(frame)["price_outcome_scatter"]
        self.assertEqual(chart["availability"]["status"], "limited")
        self.assertEqual(chart["availability"]["paired_rows"], 1)
        self.assertIsNone(chart["summary"]["spearman_rho"])
        frame["price"] = 0
        chart = analyze(frame)["price_outcome_scatter"]
        self.assertEqual(chart["availability"]["distinct_x_values"], 1)
        self.assertEqual(chart["availability"]["status"], "limited")
        self.assertEqual(chart["availability"]["valid_rows"], 6)
        self.assertTrue(all(point["x"] == 0 for point in chart["points"]))
        frame = fixture(6)
        frame.loc[0, "price"] = float("nan")
        chart = analyze(frame)["price_outcome_scatter"]
        self.assertEqual(chart["availability"]["status"], "limited")
        self.assertEqual(chart["availability"]["missing_rows"], 1)
        self.assertAlmostEqual(chart["summary"]["spearman_rho"], 1)

    def test_group_thresholds_use_unique_games_and_actual_known_values(self):
        frame = fixture(31)
        frame["groups"] = [["Action", "RPG"] for _ in range(len(frame))]
        frame.loc[0, "target_tier"] = None
        charts = analyze(frame)
        heat = charts["group_outcome_heatmap"]["availability"]
        self.assertEqual(heat["eligible_groups"], 2)
        self.assertEqual(heat["valid_rows"], 30)
        self.assertEqual(heat["status"], "limited")
        self.assertEqual(analyze(frame.head(29))["group_outcome_heatmap"]["availability"]["status"], "unavailable")
        self.assertEqual(analyze(frame.head(4))["genre_boxplot"]["availability"]["status"], "unavailable")
        self.assertEqual(analyze(frame.head(5))["genre_boxplot"]["availability"]["status"], "available")
        frame["target_tier"] = None
        self.assertEqual(analyze(frame)["group_high_tier_share"]["availability"]["status"], "unavailable")

    def test_missing_group_mapping_keeps_non_group_views(self):
        frame = fixture()
        frame["groups"] = [[] for _ in range(len(frame))]
        charts = analyze(frame)
        self.assertEqual(charts["group_count"]["availability"]["status"], "unavailable")
        self.assertEqual(charts["genre_boxplot"]["availability"]["status"], "unavailable")
        self.assertEqual(charts["outcome_histogram"]["availability"]["status"], "available")

    def test_zero_revenue_prevents_undefined_percentage_not_valid_zero_values(self):
        frame = fixture()
        frame["revenue"] = 0
        charts = analyze(frame, "revenue")
        self.assertEqual(charts["revenue_concentration"]["availability"]["status"], "unavailable")
        self.assertEqual(charts["revenue_concentration"]["availability"]["valid_rows"], 60)
        self.assertEqual(charts["outcome_histogram"]["availability"]["valid_rows"], 60)
        self.assertEqual(charts["outcome_histogram"]["rows"][0]["count"], 60)

    def test_empty_comparison_side_is_explained_and_preserves_known_side(self):
        frame = fixture(6)
        comparison = compare(frame, frame.head(0), "pc", "Action", "Other", "same sample", "test", TIERS["pc"])
        charts = analyze(frame, comparison=comparison)
        ready = comparison["chart"]["availability"]
        self.assertEqual(ready["status"], "limited")
        self.assertEqual(ready["selected_valid_rows"], 6)
        self.assertEqual(ready["baseline_valid_rows"], 0)
        self.assertEqual(ready["count_basis"], "sum_of_two_cohorts_including_any_overlap")
        self.assertEqual(charts["group_volume_median"]["availability"]["status"], "limited")
        self.assertTrue(all(value is None for value in comparison["chart"]["rows"][1]["values"]))
        empty = compare(frame.head(0), frame.head(0), "pc", "Action", "Other", "same sample", "test", TIERS["pc"])
        analyze(frame.head(0), comparison=empty)
        self.assertEqual(empty["chart"]["availability"]["status"], "unavailable")

    def test_partial_android_flags_are_disclosed(self):
        frame = fixture()
        frame["free"] = True
        frame["ad_supported"] = None
        frame["in_app_purchases"] = None
        ready = analyze(frame, "mobile")["business_count"]["availability"]
        self.assertEqual(ready["status"], "limited")
        self.assertEqual(ready["field_coverage"], {"free": 60, "ad_supported": 0, "in_app_purchases": 0})


if __name__ == "__main__":
    unittest.main()
