"""Semantic mapping and separate exploration eligibility, without repository I/O."""
import csv
import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from imports import contracts, guided


def raw(rows, delimiter=","):
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=list(rows[0]), delimiter=delimiter)
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue().encode("utf-8-sig")


def metadata(platform="pc"):
    return {"platform": platform, "source_name": "Guided synthetic test fixture", "source_url": "",
            "snapshot_date": "2026-11-22", "data_kind": "synthetic",
            "outcome_definition": contracts.OUTCOMES[platform],
            "price_currency": "USD" if platform == "pc" else "per_row"}


def options(**changes):
    return {**guided.DEFAULT_OPTIONS, "confirmed_semantics": True, **changes}


def pc(**changes):
    return {"app_id": "42", "title": "Example game", "release_date": "2024-01-02", "observed_date": "",
            "genres": '["Action"]', "planning_categories": '["Single-player"]', "developers": '["Studio"]',
            "price_observed": "10", "owner_lower": "20000", "owner_upper": "50000", **changes}


def mobile(**changes):
    return {"app_id": "example.one", "title": "Mobile game", "release_date": "2024-01-02", "observed_date": "",
            "category": "Puzzle", "developer_id": "Studio", "free": "true", "ad_supported": "false",
            "in_app_purchases": "", "minimum_installs": "1000", "price": "0", "currency": "USD", **changes}


def identity(row):
    return {key: key for key in row}


class InspectTests(unittest.TestCase):
    def test_header_aliases_and_unmapped_extras_are_suggestions_only(self):
        data = raw([{"Game ID": "1", "Game Name": "Example", "Genre": "Action", "Price": "0", "Rating": "4.9"}])
        result = guided.inspect(data, "pc")
        self.assertEqual(result["suggestions"], {"app_id": "Game ID", "title": "Game Name", "genres": "Genre", "price_observed": "Price"})
        self.assertEqual(result["sample"][0]["Rating"], "4.9")
        self.assertEqual(len(result["fields"]), len(contracts.HEADERS["pc"]))

    def test_semantically_different_numbers_are_never_autoaliased(self):
        data = raw([{"Name": "Example", "Sales": "100", "Downloads": "100", "Revenue": "100", "Installs": "100"}])
        for platform in ("pc", "mobile"):
            self.assertEqual(guided.inspect(data, platform)["suggestions"], {"title": "Name"})

    def test_ambiguous_names_require_manual_choice(self):
        result = guided.inspect(raw([{"Name": "A", "Game Name": "B", "Genre": "Action"}]), "pc")
        self.assertNotIn("title", result["suggestions"])

    def test_delimiters_and_bom(self):
        for delimiter in (",", ";", "\t"):
            with self.subTest(delimiter=delimiter):
                result = guided.inspect(raw([{"Name": "A", "Price": "10"}], delimiter), "pc")
                self.assertEqual(result["delimiter"], delimiter)
                self.assertEqual(result["headers"], ["Name", "Price"])

    def test_invalid_csv_input_bounds(self):
        for data in (b"\xff", b"Name,Name\nA,B", b"Name,\nA,B", b"Name,Price\nA,\x00", b""):
            with self.subTest(data=data), self.assertRaises(ValueError):
                guided.inspect(data, "pc")
        for platform in ("console", {}, [], None, 123):
            with self.subTest(platform=platform), self.assertRaises(ValueError):
                guided.inspect(b"Name,Price\nA,1", platform)


class GuidedPreparationTests(unittest.TestCase):
    def test_minimal_renamed_csv_keeps_price_and_genres_without_research_fields(self):
        data = raw([{"ID": "a", "Game Name": "A", "Genre": "Action", "Price": "0", "Rating": "4.5"},
                    {"ID": "b", "Game Name": "B", "Genre": "Adventure", "Price": "5", "Rating": "4.1"}])
        mapping = {"app_id": "ID", "title": "Game Name", "genres": "Genre", "price_observed": "Price"}
        result = guided.prepare(data, metadata(), mapping, options(list_separator=";"))
        summary = result["summary"]
        self.assertTrue(summary["can_import"])
        self.assertEqual((summary["exploration_rows"], summary["eligible_rows"]), (2, 0))
        self.assertEqual(summary["unmapped_columns"], ["Rating"])
        self.assertEqual(result["exploration"]["price_observed"].to_pylist(), [0, 5])
        self.assertEqual(result["exploration"]["release_date"].to_pylist(), [None, None])
        self.assertEqual(summary["warnings"]["observation_uses_snapshot_proxy"], 2)
        ready = {item["id"]: item for item in summary["analysis_readiness"]}
        self.assertEqual(ready["genre_counts"]["usable_rows"], 2)
        self.assertEqual(ready["price_distribution"]["usable_rows"], 2)
        self.assertEqual(ready["release_cohorts"]["status"], "unavailable")

    def test_full_compatible_data_still_matches_legacy_comparison(self):
        row = pc()
        data = raw([row])
        result = guided.prepare(data, metadata(), identity(row), options())
        legacy = contracts.validate(data, metadata())
        self.assertTrue(result["summary"]["can_import"])
        self.assertEqual(result["comparison"].to_pylist(), legacy[1].to_pylist())
        self.assertEqual(result["ledger"].to_pylist()[0]["comparison_included"], True)
        self.assertEqual(result["exploration"]["target_tier"].to_pylist(), [contracts.PC_TIERS[1]])

    def test_missing_developer_and_cross_tier_interval_keep_exploration(self):
        rows = [pc(developers="", app_id="1"), pc(app_id="2", owner_lower="10000", owner_upper="30000")]
        result = guided.prepare(raw(rows), metadata(), identity(rows[0]), options())
        self.assertEqual(result["summary"]["exploration_rows"], 2)
        self.assertEqual(result["summary"]["eligible_rows"], 0)
        self.assertTrue(result["summary"]["can_import"])
        records = result["exploration"].to_pylist()
        self.assertEqual(records[0]["target_tier"], contracts.PC_TIERS[1])
        self.assertIsNone(records[1]["target_tier"])
        self.assertEqual((records[1]["owner_lower"], records[1]["owner_upper"]), (10000, 30000))

    def test_zero_owner_interval_is_unknown_not_known_zero(self):
        row = pc(owner_lower="0", owner_upper="0")
        result = guided.prepare(raw([row]), metadata(), identity(row), options())
        record = result["exploration"].to_pylist()[0]
        self.assertIsNone(record["owner_lower"])
        self.assertIsNone(record["owner_upper"])
        self.assertIsNone(record["target_tier"])
        self.assertEqual(result["summary"]["warnings"]["unknown_owners"], 1)

    def test_semantics_confirmation_is_explicit(self):
        row = pc()
        for confirmation in (False, None, "true", 1):
            with self.subTest(confirmation=confirmation), self.assertRaises(ValueError):
                guided.prepare(raw([row]), metadata(), identity(row), options(confirmed_semantics=confirmation))

    def test_unknown_options_and_unsafe_mapping_are_rejected(self):
        row = pc()
        for mapping in ({"title": "title"}, {"title": "missing", "price_observed": "price_observed"},
                        {"title": "title", "price_observed": "title"},
                        {**identity(row), "revenue": "price_observed"}):
            with self.subTest(mapping=mapping), self.assertRaises(ValueError):
                guided.prepare(raw([row]), metadata(), mapping, options())
        with self.assertRaises(ValueError):
            guided.prepare(raw([row]), metadata(), identity(row), options(guess_currency=True))

    def test_duplicate_id_blocks_even_with_usable_chart_fields(self):
        row = pc()
        result = guided.prepare(raw([row, row]), metadata(), identity(row), options())
        self.assertFalse(result["summary"]["can_import"])
        self.assertEqual(result["summary"]["invalid_rows"], 1)
        self.assertEqual(result["summary"]["errors_by_field"]["app_id"], 1)

    def test_row_identifiers_are_explicit_local_and_deterministic(self):
        rows = [{"Name": "Same name", "Price": "1"}, {"Name": "Same name", "Price": "2"}]
        data = raw(rows)
        mapping = {"title": "Name", "price_observed": "Price"}
        with self.assertRaises(ValueError):
            guided.prepare(data, metadata(), mapping, options())
        first = guided.prepare(data, metadata(), mapping, options(id_policy="row_number"))
        second = guided.prepare(data, metadata(), mapping, options(id_policy="row_number"))
        ids = first["exploration"]["app_id"].to_pylist()
        self.assertTrue(all(value.startswith("local-row-") for value in ids))
        self.assertEqual(len(set(ids)), 2)
        self.assertEqual(ids, second["exploration"]["app_id"].to_pylist())
        self.assertEqual(first["summary"]["identity_basis"], "local_row_id_not_platform_identity")
        self.assertEqual(first["summary"]["warnings"]["local_row_id_not_platform_identity"], 2)

    def test_date_format_does_not_guess_ambiguous_dates(self):
        row = pc(release_date="01/02/2025")
        data = raw([row])
        mapping = identity(row)
        rejected = guided.prepare(data, metadata(), mapping, options())
        self.assertFalse(rejected["summary"]["can_import"])
        dmy = guided.prepare(data, metadata(), mapping, options(date_format="dmy"))
        mdy = guided.prepare(data, metadata(), mapping, options(date_format="mdy"))
        self.assertEqual(dmy["exploration"]["release_date"].to_pylist(), ["2025-02-01"])
        self.assertEqual(mdy["exploration"]["release_date"].to_pylist(), ["2025-01-02"])

    def test_invalid_date_and_out_of_range_date_block(self):
        for value in ("2025-02-30", "1200-01-01", "2300-01-01"):
            row = pc(release_date=value)
            with self.subTest(value=value):
                self.assertFalse(guided.prepare(raw([row]), metadata(), identity(row), options())["summary"]["can_import"])

    def test_future_release_mask_does_not_lose_other_usable_fields(self):
        row = pc(release_date="2027-01-01")
        result = guided.prepare(raw([row]), metadata(), identity(row), options())
        self.assertTrue(result["summary"]["can_import"])
        self.assertEqual(result["summary"]["eligible_rows"], 0)
        self.assertIsNone(result["exploration"]["release_date"].to_pylist()[0])
        self.assertEqual(result["summary"]["warnings"]["release_after_observation_masked"], 1)
        self.assertIn(b"2027-01-01", result["normalized_csv"])

    def test_observation_after_snapshot_blocks(self):
        row = pc(observed_date="2026-12-01")
        result = guided.prepare(raw([row]), metadata(), identity(row), options())
        self.assertFalse(result["summary"]["can_import"])
        self.assertIn("observed_date", result["summary"]["errors_by_field"])

    def test_selected_numeric_normalization_and_unsupported_units(self):
        row = pc(owner_lower="20,000", owner_upper="50,000", price_observed="1,200.50")
        data = raw([row])
        self.assertFalse(guided.prepare(data, metadata(), identity(row), options())["summary"]["can_import"])
        result = guided.prepare(data, metadata(), identity(row), options(number_format="thousands_comma"))
        self.assertTrue(result["summary"]["can_import"])
        self.assertEqual(result["exploration"]["price_observed"].to_pylist(), [1200.5])
        for value in ("20k", "1000+", "1,00", "1.000,50", "HK$5", "NaN", "-1", "9007199254740992"):
            bad = pc(price_observed=value)
            with self.subTest(value=value):
                self.assertFalse(guided.prepare(raw([bad]), metadata(), identity(bad), options(number_format="thousands_comma"))["summary"]["can_import"])

    def test_owner_mapping_and_interval_constraints(self):
        row = pc()
        mapping = identity(row)
        del mapping["owner_upper"]
        with self.assertRaises(ValueError):
            guided.prepare(raw([row]), metadata(), mapping, options())
        for changes in ({"owner_upper": ""}, {"owner_lower": "50000", "owner_upper": "10000"}):
            row = pc(**changes)
            self.assertFalse(guided.prepare(raw([row]), metadata(), identity(row), options())["summary"]["can_import"])

    def test_list_format_is_explicit_and_software_only_excluded(self):
        row = pc(genres="Action|Adventure", developers="Studio", planning_categories="Single-player")
        result = guided.prepare(raw([row]), metadata(), identity(row), options(list_separator="|"))
        self.assertEqual(result["exploration"]["genres"].to_pylist(), [["Action", "Adventure"]])
        self.assertFalse(guided.prepare(raw([row]), metadata(), identity(row), options())["summary"]["can_import"])
        software = pc(genres='["Accounting"]')
        result = guided.prepare(raw([software]), metadata(), identity(software), options())
        self.assertFalse(result["summary"]["can_import"])
        self.assertEqual(result["summary"]["exclusions"]["software_only_heuristic"], 1)

    def test_exploration_warning_counts_exclude_removed_records(self):
        rows = [pc(app_id="1"), pc(app_id="2", genres='["Accounting"]')]
        result = guided.prepare(raw(rows), metadata(), identity(rows[0]), options())
        self.assertEqual(result["summary"]["warnings"]["observation_uses_snapshot_proxy"], 2)
        self.assertEqual(result["summary"]["exploration_warnings"]["observation_uses_snapshot_proxy"], 1)

    def test_invalid_rows_have_original_record_numbers_and_bounded_issues(self):
        rows = [pc(app_id=str(i), price_observed="USD 4") for i in range(120)]
        result = guided.prepare(raw(rows), metadata(), identity(rows[0]), options())
        summary = result["summary"]
        self.assertEqual(summary["invalid_rows"], 120)
        self.assertEqual(summary["error_count"], 120)
        self.assertEqual(len(summary["issues"]), contracts.MAX_ISSUES)
        self.assertTrue(summary["issues_truncated"])
        self.assertEqual(result["ledger"].num_rows, 120)
        self.assertEqual(summary["issues"][0]["row"], 2)

    def test_row_limit(self):
        rows = [pc(app_id="1"), pc(app_id="2")]
        with patch.object(contracts, "MAX_ROWS", 1), self.assertRaises(ValueError):
            guided.prepare(raw(rows), metadata(), identity(rows[0]), options())

    def test_mobile_missing_developer_still_keeps_installs_and_tier(self):
        row = mobile(developer_id="", release_date="")
        result = guided.prepare(raw([row]), metadata("mobile"), identity(row), options())
        self.assertTrue(result["summary"]["can_import"])
        self.assertEqual(result["summary"]["eligible_rows"], 0)
        self.assertEqual(result["exploration"]["target_tier"].to_pylist(), [contracts.MOBILE_TIERS[1]])
        self.assertEqual(result["exploration"].column_names, contracts.HEADERS["mobile"] + ["target_tier"])

    def test_mobile_boolean_formats_and_unknown_are_distinct(self):
        for fmt, yes, no in (("yes_no", "Yes", "NO"), ("one_zero", "1", "0")):
            row = mobile(free=yes, ad_supported=no)
            result = guided.prepare(raw([row]), metadata("mobile"), identity(row), options(boolean_format=fmt))
            record = result["exploration"].to_pylist()[0]
            self.assertTrue(record["free"])
            self.assertFalse(record["ad_supported"])
            self.assertIsNone(record["in_app_purchases"])
            self.assertFalse(guided.prepare(raw([row]), metadata("mobile"), identity(row), options())["summary"]["can_import"])

    def test_mobile_currency_and_unknown_category_do_not_corrupt_other_charts(self):
        rows = [mobile(app_id="1", category="Unsupported category", currency="HKD"),
                mobile(app_id="2", currency="usd", price="2", free="false")]
        result = guided.prepare(raw(rows), metadata("mobile"), identity(rows[0]), options())
        self.assertTrue(result["summary"]["can_import"])
        records = result["exploration"].to_pylist()
        self.assertIsNone(records[0]["category"])
        self.assertEqual(records[0]["currency"], "HKD")
        self.assertEqual(records[1]["currency"], "USD")
        ready = {item["id"]: item for item in result["summary"]["analysis_readiness"]}
        self.assertEqual(ready["price_distribution"]["usable_rows"], 1)
        self.assertEqual(ready["genre_counts"]["usable_rows"], 1)
        self.assertEqual(ready["age_installs"]["usable_rows"], 2)
        self.assertIn(b"Unsupported category", result["normalized_csv"])

    def test_mobile_free_price_conflict_masks_unknown(self):
        row = mobile(free="true", price="5")
        result = guided.prepare(raw([row]), metadata("mobile"), identity(row), options())
        self.assertIsNone(result["exploration"]["free"].to_pylist()[0])
        self.assertEqual(result["summary"]["warnings"]["free_price_conflict_masked"], 1)

    def test_empty_and_unusable_rows_cannot_save(self):
        result = guided.prepare(b"ID,Name,Price\n", metadata(), {"app_id": "ID", "title": "Name", "price_observed": "Price"}, options())
        self.assertFalse(result["summary"]["can_import"])
        data = raw([{"ID": "1", "Name": "A", "Price": ""}])
        result = guided.prepare(data, metadata(), {"app_id": "ID", "title": "Name", "price_observed": "Price"}, options())
        self.assertFalse(result["summary"]["can_import"])
        self.assertEqual(result["summary"]["exclusions"], {"no_usable_analysis_fields": 1})


if __name__ == "__main__":
    unittest.main()
