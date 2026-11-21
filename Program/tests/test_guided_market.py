"""Guided exploration uses chart fields, independently of comparison eligibility."""
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace

import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src/demo"))
from imports.contracts import FIELDS
from market import MarketStore, TIERS


PC_SCHEMA = pa.schema([
    ("app_id", pa.string()), ("title", pa.string()), ("release_date", pa.string()),
    ("observed_date", pa.string()), ("genres", pa.list_(pa.string())),
    ("planning_categories", pa.list_(pa.string())), ("developers", pa.list_(pa.string())),
    ("price_observed", pa.float64()), ("owner_lower", pa.int64()), ("owner_upper", pa.int64()),
    ("target_tier", pa.string()),
])
MOBILE_SCHEMA = pa.schema([
    ("app_id", pa.string()), ("title", pa.string()), ("release_date", pa.string()),
    ("observed_date", pa.string()), ("category", pa.string()), ("developer_id", pa.string()),
    ("free", pa.bool_()), ("ad_supported", pa.bool_()), ("in_app_purchases", pa.bool_()),
    ("minimum_installs", pa.int64()), ("price", pa.float64()), ("currency", pa.string()),
    ("target_tier", pa.string()),
])


def pc_row(i, **changes):
    return dict(app_id=str(i), title=f"Game {i}", release_date=None, observed_date="2025-01-01",
                genres=["Action"], planning_categories=[], developers=[], price_observed=0,
                owner_lower=None, owner_upper=None, target_tier=None) | changes


def mobile_row(i, **changes):
    return dict(app_id=f"app.{i}", title=f"Game {i}", release_date=None, observed_date="2025-01-01",
                category="Puzzle", developer_id=None, free=None, ad_supported=None,
                in_app_purchases=None, minimum_installs=None, price=None, currency=None,
                target_tier=None) | changes


def chart(result, ident):
    return next(item for item in result["charts"] if item["id"] == ident)


class GuidedMarketTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.folder = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def market(self, rows, platform="pc", comparison_count=0):
        schema = PC_SCHEMA if platform == "pc" else MOBILE_SCHEMA
        pq.write_table(pa.Table.from_pylist(rows, schema=schema), self.folder / "exploration.parquet")
        pq.write_table(pa.Table.from_pylist([], schema=FIELDS[platform]), self.folder / "data.parquet")
        validation = {"mapping": {"title": "Game Name"}, "options": {"confirmed_semantics": True},
                      "unmapped_columns": ["Review text"], "warnings": {"observation_uses_snapshot_proxy": len(rows)}}
        (self.folder / "validation.json").write_text(json.dumps(validation), encoding="utf-8")
        metadata = dict(source_name="Synthetic guided upload", source_url="", snapshot_date="2025-01-01",
                        data_kind="synthetic", price_currency="unknown" if platform == "pc" else "per_row")
        manifest = dict(contract_version="application_guided_csv_v1", exploration_rows=len(rows),
                        eligible_rows=comparison_count, metadata=metadata, files={"exploration.parquet": "test"})
        repository = SimpleNamespace(load=lambda source, version: (manifest, self.folder / "data.parquet"))
        spec = dict(name="Steam" if platform == "pc" else "Android", row_count=comparison_count,
                    exploration_rows=len(rows), snapshot="2025-01-01", partition="application_snapshot", data_kind="synthetic")
        comparison = SimpleNamespace(root=ROOT, db=None, repository=repository, options={platform: spec},
                                     active={platform: "guided-fixture"}, lock=threading.RLock())
        return MarketStore(comparison)

    def query(self, market, platform="pc", **changes):
        result = market.query(dict(source=platform, version_id="guided-fixture", group="", tag="",
                                   year_from=None, year_to=None, top_n=10, rank_metric="volume") | changes)
        json.dumps(result, allow_nan=False)
        return result

    def test_price_and_genres_survive_zero_comparison_eligibility(self):
        market = self.market([pc_row(i, price_observed=i * 5) for i in range(6)])
        result = self.query(market)
        self.assertEqual(result["summary"][0]["value"], 6)
        self.assertEqual(chart(result, "group_count")["rows"][0]["values"], [6])
        self.assertEqual(chart(result, "outcome_histogram")["availability"]["valid_rows"], 6)
        self.assertEqual(chart(result, "genre_boxplot")["availability"]["valid_rows"], 6)
        self.assertEqual(chart(result, "release_count")["availability"]["status"], "unavailable")
        self.assertEqual(chart(result, "price_outcome_scatter")["availability"]["status"], "unavailable")
        self.assertEqual(chart(result, "top_games")["availability"]["status"], "unavailable")
        self.assertEqual(result["leaders"]["rows"], [])
        self.assertIsNone(result["summary"][2]["value"])
        self.assertEqual(result["provenance"]["guided_import"]["comparison_eligible_rows"], 0)
        self.assertEqual(result["provenance"]["observation_date_proxy_rows"], 6)
        self.assertIn("Synthetic guided upload", result["source"]["name"])
        self.assertEqual(result["provenance"]["guided_import"]["unmapped_columns"], ["Review text"])

    def test_straddling_interval_is_numeric_but_not_a_low_tier(self):
        result = self.query(self.market([pc_row(1, owner_lower=10000, owner_upper=30000, price_observed=5)]))
        self.assertEqual(chart(result, "group_volume_total")["rows"][0]["values"], [10000, 30000])
        self.assertEqual(chart(result, "price_outcome_scatter")["summary"]["paired_rows"], 1)
        tiers = chart(result, "outcome_tiers")["rows"]
        self.assertEqual([item["values"] for item in tiers], [[0], [0], [0], [1]])
        self.assertEqual(tiers[-1]["filter"], {"tier": "unknown"})
        self.assertEqual(chart(result, "outcome_tiers")["availability"]["status"], "limited")
        self.assertTrue(chart(result, "outcome_tiers")["availability"]["action"])
        self.assertEqual(result["leaders"]["rows"][0]["volume_upper"], 30000)

    def test_high_tier_share_uses_known_denominator_and_threshold(self):
        rows = [pc_row(i, target_tier=TIERS["pc"][2][0], owner_lower=100000, owner_upper=200000) for i in range(30)]
        rows += [pc_row(i) for i in range(30, 60)]
        result = self.query(self.market(rows))
        high = chart(result, "group_high_tier_share")
        self.assertEqual(high["rows"][0]["values"], [100])
        self.assertEqual(high["availability"]["valid_rows"], 30)
        self.assertEqual(high["availability"]["missing_rows"], 30)
        self.assertEqual(high["percentage_denominator"], "known_outcome_rows_within_each_group")
        result = self.query(self.market(rows[1:]))
        self.assertEqual(chart(result, "group_high_tier_share")["rows"], [])
        self.assertEqual(chart(result, "group_high_tier_share")["availability"]["status"], "unavailable")

    def test_mobile_price_chart_keeps_only_explicit_usd(self):
        rows = [mobile_row(1, price=0, currency="USD"), mobile_row(2, price=5, currency="USD"),
                mobile_row(3, price=100, currency="HKD"), mobile_row(4, price=10)]
        result = self.query(self.market(rows, "mobile"), "mobile")
        histogram = chart(result, "price_histogram")
        self.assertEqual(histogram["availability"]["valid_rows"], 2)
        self.assertEqual(histogram["availability"]["status"], "limited")
        self.assertEqual(sum(item["count"] for item in histogram["rows"]), 2)
        self.assertEqual(histogram["xUnit"], "USD")
        self.assertEqual(chart(result, "outcome_histogram")["availability"]["status"], "unavailable")
        self.assertEqual(chart(result, "group_count")["rows"][0]["values"], [4])
        no_usd = self.query(self.market([mobile_row(1, price=100, currency="HKD")], "mobile"), "mobile")
        self.assertEqual(chart(no_usd, "price_histogram")["availability"]["status"], "unavailable")

    def test_missing_category_does_not_become_a_literal_none_group(self):
        result = self.query(self.market([mobile_row(1, category=None, minimum_installs=1000,
                                                      target_tier=TIERS["mobile"][1][0])], "mobile"), "mobile")
        self.assertEqual(result["source"]["groups"], [])
        self.assertEqual(chart(result, "group_count")["availability"]["status"], "unavailable")
        self.assertEqual(chart(result, "top_games")["availability"]["status"], "available")

    def test_records_and_cohort_comparison_retain_unknowns(self):
        market = self.market([pc_row(1), pc_row(2, genres=["RPG"], owner_lower=10000, owner_upper=30000)])
        result = self.query(market, group="Action")
        self.assertEqual(result["comparison"]["selected"]["unknown_outcome_rows"], 1)
        self.assertEqual(result["comparison"]["baseline"]["unknown_outcome_rows"], 1)
        self.assertEqual(result["comparison"]["selected"]["tiers"][-1]["percent"], 100)
        records = market.records(dict(analysis=result["filters"], cohort="selected", tier="unknown",
                                      q="", page=1, page_size=20, sort="title"))
        self.assertEqual(records["total"], 1)
        self.assertIsNone(records["rows"][0]["volume_lower"])
        self.assertIsNone(records["rows"][0]["release_date"])
        json.dumps(records, allow_nan=False)

    def test_date_only_price_only_and_unclassified_labels_remain_browsable(self):
        rows = [pc_row(1, genres=[], price_observed=None, release_date="2020-01-01"),
                pc_row(2, genres=[], price_observed=5),
                pc_row(3, genres=["Future label"], price_observed=None)]
        market = self.market(rows)
        result = self.query(market)
        self.assertEqual(result["source"]["groups"], [])
        self.assertEqual(chart(result, "group_count")["availability"]["status"], "unavailable")
        self.assertEqual(chart(result, "release_count")["availability"]["valid_rows"], 1)
        self.assertEqual(chart(result, "outcome_histogram")["availability"]["valid_rows"], 1)
        self.assertEqual(chart(result, "top_games")["availability"]["status"], "unavailable")
        records = market.records(dict(analysis=result["filters"], cohort="selected", tier="",
                                      q="", page=1, page_size=20, sort="title"))
        self.assertEqual(records["total"], 3)
        self.assertEqual({record["app_id"] for record in records["rows"]}, {"1", "2", "3"})
        self.assertEqual(records["rows"][2]["source_tags"], ["Future label"])
        selected = self.query(market, tag="Future label")
        self.assertEqual(selected["summary"][0]["value"], 1)
        json.dumps(records, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
