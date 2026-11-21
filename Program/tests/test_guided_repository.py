"""Guided snapshots remain separate, traceable, restartable and reversible."""
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src/demo"))
from imports.guided import prepare
from imports.repository import SnapshotRepository, DEFAULT_VERSION
from server import ComparisonStore, make_server
from test_csv_import import metadata

CSV = "Game Name,Genre,Price,Other Price,Notes\nExample A,Action,0,5,original extra column\nExample B,Adventure,10,20,keep this too\n"
MAPPING = {"title": "Game Name", "genres": "Genre", "price_observed": "Price"}
OPTIONS = {"delimiter": ",", "date_format": "iso", "list_separator": ";",
           "boolean_format": "true_false", "number_format": "plain",
           "confirmed_semantics": True, "id_policy": "row_number"}


class GuidedRepositoryTests(unittest.TestCase):
    def prepared(self, mapping=None):
        return prepare(CSV.encode(), metadata("pc"), mapping or MAPPING, OPTIONS)

    def test_original_mapping_normalized_and_broad_data_saved(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = SnapshotRepository(folder)
            prepared = self.prepared()
            self.assertEqual(prepared["summary"]["eligible_rows"], 0)
            self.assertEqual(prepared["summary"]["exploration_rows"], 2)
            one = repo.save(CSV.encode(), metadata("pc"), prepared)
            two = repo.save(CSV.encode(), metadata("pc"), prepared)
            self.assertTrue(two["already_exists"])
            self.assertEqual(one["version_id"], two["version_id"])
            manifest, path = repo.load("pc", one["version_id"])
            self.assertEqual((path.parent / "source.csv").read_bytes(), CSV.encode())
            self.assertEqual(manifest["exploration_rows"], 2)
            self.assertEqual(set(manifest["files"]), {"source.csv", "validation.json", "data.parquet", "ledger.parquet", "normalized.csv", "mapping.json", "exploration.parquet"})
            changed = self.prepared({**MAPPING, "price_observed": "Other Price"})
            three = repo.save(CSV.encode(), metadata("pc"), changed)
            self.assertNotEqual(one["version_id"], three["version_id"])
            self.assertEqual(repo.active()["pc"], DEFAULT_VERSION)
            (path.parent / "exploration.parquet").write_bytes(b"broken")
            with self.assertRaises(ValueError):
                repo.load("pc", one["version_id"])

    def test_failed_write_does_not_publish(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = SnapshotRepository(folder)
            prepared = self.prepared()
            with patch("imports.repository.pq.write_table", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    repo.save(CSV.encode(), metadata("pc"), prepared)
            self.assertFalse(repo.list_versions())
            self.assertEqual(repo.active()["pc"], DEFAULT_VERSION)

    def test_http_preview_activate_restart_and_rollback(self):
        with tempfile.TemporaryDirectory() as folder:
            store = ComparisonStore(app_path=Path(folder))
            server = make_server(store, 0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            url = f"http://127.0.0.1:{server.server_port}"
            def request(path, payload, token=None):
                headers = {"Content-Type": "application/json"}
                if token: headers["X-GameScope-Token"] = token
                with urlopen(Request(url + path, json.dumps(payload).encode(), headers), timeout=30) as response:
                    return json.load(response)
            try:
                with urlopen(url + "/api/options") as response:
                    token = json.load(response)["mutation_token"]
                upload = {"platform": "pc", "csv_text": CSV}
                with self.assertRaises(HTTPError) as error:
                    request("/api/import/inspect", upload)
                self.assertEqual(error.exception.code, 403)
                error.exception.close()
                inspected = request("/api/import/inspect", upload, token)
                self.assertIn("Notes", inspected["headers"])
                preview_payload = {"csv_text": CSV, "metadata": metadata("pc"), "mapping": MAPPING, "options": OPTIONS}
                preview = request("/api/import/guided-preview", preview_payload, token)
                self.assertTrue(preview["validation"]["can_import"])
                # Inspecting another upload invalidates a previously approved preview.
                request("/api/import/inspect", upload, token)
                with self.assertRaises(HTTPError) as expired:
                    request("/api/import/commit", {"preview_id": preview["preview_id"]}, token)
                self.assertEqual(expired.exception.code, 400)
                expired.exception.close()
                preview = request("/api/import/guided-preview", preview_payload, token)
                saved = request("/api/import/commit", {"preview_id": preview["preview_id"]}, token)
                ident = saved["version_id"]
                self.assertEqual(store.active["pc"], DEFAULT_VERSION)
                request("/api/activate", {"platform": "pc", "version_id": ident}, token)
                result = request("/api/compare", {"platform": "pc", "a": {}, "b": {}, "version_id": ident})
                self.assertEqual(result["scenarios"]["a"]["total"], 0)
                self.assertEqual(result["metadata"]["exploration_rows"], 2)
                restarted = ComparisonStore(app_path=Path(folder))
                try:
                    self.assertEqual(restarted.active["pc"], ident)
                    self.assertEqual(restarted.options["pc"]["row_count"], 0)
                finally:
                    restarted.db.close()
                request("/api/activate", {"platform": "pc", "version_id": DEFAULT_VERSION}, token)
                self.assertEqual(store.options["pc"]["row_count"], 51152)
                self.assertEqual(store.options["mobile"]["row_count"], 221806)
            finally:
                server.shutdown(); server.server_close(); thread.join(); store.db.close()


if __name__ == "__main__":
    unittest.main()
