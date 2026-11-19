"""Cross-page label separation preserves source rows and comparison eligibility."""
import csv
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src/demo"))
from analysis.game_taxonomy import GAMEPLAY_GENRES, gameplay, other_labels
import market_taxonomy
from imports.contracts import HEADERS, OUTCOMES, validate
from imports.repository import DEFAULT_VERSION
from server import ComparisonStore, MarketStore, make_server


class TaxonomyWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.store = ComparisonStore(app_path=Path(cls.directory.name))

    @classmethod
    def tearDownClass(cls):
        cls.store.db.close()
        cls.directory.cleanup()

    def fields(self):
        return {field["key"]: field for field in self.store.options["pc"]["fields"]}

    def test_shared_mapping_separates_all_labels_without_loss(self):
        self.assertIs(market_taxonomy.GAMEPLAY_GENRES, GAMEPLAY_GENRES)
        raw = {value for value, in self.store.db.execute("SELECT DISTINCT unnest(genres) FROM pc").fetchall()}
        fields = self.fields()
        genres = {c["value"] for c in fields["genre"]["choices"]}
        tags = {c["value"] for c in fields["source_tag"]["choices"]}
        self.assertEqual(genres, raw & GAMEPLAY_GENRES)
        self.assertEqual(tags, raw - GAMEPLAY_GENRES)
        self.assertEqual(genres | tags, raw)
        self.assertFalse(genres & tags)
        grouped = {value for group in fields["source_tag"]["groups"] for value in group["values"]}
        self.assertEqual(grouped, tags)
        self.assertIn("Indie", tags)
        self.assertIn("Massively Multiplayer", tags)
        self.assertEqual(self.store.options["pc"]["row_count"], 51152)
        self.assertNotIn("source_tag", {f["key"] for f in self.store.options["mobile"]["fields"]})

    def test_source_tag_and_gameplay_use_original_columns_with_and(self):
        result = self.store.compare({"platform": "pc", "a": {"genre": "Action", "source_tag": "Indie"},
                                     "b": {"source_tag": "Indie"}})
        expected = self.store.db.execute("SELECT count(*) FROM pc WHERE list_contains(genres, 'Action') AND list_contains(genres, 'Indie')").fetchone()[0]
        self.assertEqual(result["scenarios"]["a"]["total"], expected)
        self.assertEqual(result["overlap_count"], expected)
        self.assertEqual(result["metadata"]["label_taxonomy"]["gameplay_genres"], sorted(GAMEPLAY_GENRES))
        self.assertEqual(result["scenarios"]["a"]["filters"], {"genre": "Action", "source_tag": "Indie"})

    def test_old_genre_labels_are_rejected_without_reinterpretation(self):
        for value in ("Indie", "Sexual Content", "Massively Multiplayer"):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "source_tag"):
                self.store.compare({"platform": "pc", "a": {"genre": value}, "b": {}})
        with self.assertRaises(ValueError):
            self.store.compare({"platform": "pc", "a": {"source_tag": "Action"}, "b": {}})

    def test_imported_options_preserve_unknown_tags_and_existing_eligibility(self):
        labels = [["Action", "Indie", "Unmapped label"], ["RPG", "Sexual Content", "Massively Multiplayer"], ["Indie"], ["Utilities"]]
        rows = [dict(app_id=str(900+i), title=f"Fixture {i}", release_date="2020-01-01", observed_date="2026-10-01",
                     genres=json.dumps(values), planning_categories='["Single-player"]', developers='["Studio"]',
                     price_observed="4.5", owner_lower="20000", owner_upper="50000") for i, values in enumerate(labels)]
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=HEADERS["pc"])
        writer.writeheader(); writer.writerows(rows)
        raw = stream.getvalue().encode("utf-8")
        meta = dict(platform="pc", source_name="Synthetic taxonomy test", source_url="", snapshot_date="2026-10-01",
                    data_kind="synthetic", outcome_definition=OUTCOMES["pc"], price_currency="unknown")
        prepared = validate(raw, meta)
        self.assertEqual(prepared[0]["eligible_rows"], 3)
        self.assertEqual(prepared[0]["exclusions"], {"software_only_heuristic": 1})
        saved = self.store.repository.save(raw, meta, prepared)
        try:
            self.store.activate("pc", saved["version_id"])
            fields = self.fields()
            self.assertEqual([c["value"] for c in fields["genre"]["choices"]], ["Action", "RPG"])
            self.assertIn("Unmapped label", fields["source_tag"]["groups"][-1]["values"])
            self.assertEqual(fields["source_tag"]["groups"][-1]["id"], "other")
            result = self.store.compare({"platform": "pc", "a": {"source_tag": "Indie"}, "b": {}})
            self.assertEqual(result["scenarios"]["a"]["total"], 2)
            self.assertEqual(result["scenarios"]["b"]["total"], 3)
            actual = self.store.db.execute("SELECT app_id, genres FROM pc ORDER BY app_id").fetchall()
            self.assertEqual(actual, [(str(900+i), values) for i, values in enumerate(labels[:3])])
        finally:
            self.store.activate("pc", DEFAULT_VERSION)
        self.assertEqual(self.store.options["pc"]["row_count"], 51152)


class MarketRecordsRouteTests(unittest.TestCase):
    def setUp(self):
        self.entered, self.release = threading.Event(), threading.Event()
        def compare(payload):
            self.entered.set()
            self.release.wait(5)
            return {"comparison": "done"}
        self.server = make_server(SimpleNamespace(root=ROOT, compare=compare), 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.release.set()
        self.server.shutdown(); self.server.server_close(); self.thread.join()

    def post(self, path, payload, headers=None):
        request = Request(self.base + path, data=json.dumps(payload).encode(),
                          headers={"Content-Type": "application/json", **(headers or {})})
        with urlopen(request, timeout=3) as response:
            return json.load(response)

    def test_read_only_records_route_bypasses_upload_gate_and_needs_no_token(self):
        comparison_results = []
        worker = threading.Thread(target=lambda: comparison_results.append(self.post("/api/compare", {})), daemon=True)
        worker.start()
        try:
            self.assertTrue(self.entered.wait(2))
            with patch.object(MarketStore, "records", return_value={"rows": [], "total": 0}, create=True) as records:
                payload = {"source": "pc"}
                self.assertEqual(self.post("/api/market/records", payload), {"rows": [], "total": 0})
                records.assert_called_once_with(payload)
        finally:
            self.release.set(); worker.join(4)
        self.assertEqual(comparison_results, [{"comparison": "done"}])

    def test_records_route_keeps_origin_size_and_value_checks(self):
        with patch.object(MarketStore, "records", side_effect=ValueError("invalid record query"), create=True):
            for payload, headers, status in [({}, {}, 400), ({}, {"Origin": "https://example.com"}, 403),
                                              ({"padding": "x" * 8192}, {}, 400)]:
                with self.subTest(status=status), self.assertRaises(HTTPError) as error:
                    self.post("/api/market/records", payload, headers)
                self.assertEqual(error.exception.code, status)
                error.exception.close()


if __name__ == "__main__":
    unittest.main()
