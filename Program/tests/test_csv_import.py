"""Import boundaries, immutable storage, rollback, restart and same-origin write checks."""
import csv
import io
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
from imports.contracts import HEADERS, OUTCOMES, validate, template
from imports.repository import SnapshotRepository, DEFAULT_VERSION
from server import ComparisonStore, make_server


def metadata(platform="mobile"):
    return dict(platform=platform, source_name="Synthetic test fixture", source_url="", snapshot_date="2026-10-01",
                data_kind="synthetic", outcome_definition=OUTCOMES[platform], price_currency="unknown" if platform == "pc" else "per_row")


def mobile(**changes):
    return dict(app_id="example.one", title="Example", release_date="2020-01-01", observed_date="2026-10-01",
                category="Puzzle", developer_id="Example studio", free="true", ad_supported="false",
                in_app_purchases="", minimum_installs="1000", price="0", currency="USD", **changes)


def pc():
    return dict(app_id="123", title="Example", release_date="2020-01-01", observed_date="2026-10-01",
                genres='["Action"]', planning_categories='["Single-player"]', developers='["Studio"]',
                price_observed="4.5", owner_lower="20000", owner_upper="50000")


def raw(rows, platform="mobile"):
    s = io.StringIO(newline="")
    w = csv.DictWriter(s, fieldnames=HEADERS[platform]); w.writeheader(); w.writerows(rows)
    return s.getvalue().encode("utf-8-sig")


class ContractTests(unittest.TestCase):
    def test_boundary_tiers_and_unknown_booleans(self):
        rows = []
        for i, value in enumerate(["0", "999", "1000", "99999", "100000", ""]):
            r = mobile(); r.update(app_id=str(i), minimum_installs=value, free="", price="")
            rows.append(r)
        report, table, ledger = validate(raw(rows), metadata())
        self.assertEqual((report["eligible_rows"], report["excluded_rows"]), (5, 1))
        self.assertEqual(list(report["tiers"].values()), [2, 2, 1])
        self.assertTrue(all(x is None for x in table["free"].to_pylist()))
        self.assertEqual(ledger.num_rows, 6)

    def test_pc_intervals_exclusions_and_literal_title(self):
        rows = []
        for i, (lo, hi) in enumerate([(0, 20000), (20000, 50000), (100000, 200000), (0, 0), (10000, 30000)]):
            r = pc(); r.update(app_id=str(i), title="None", owner_lower=str(lo), owner_upper=str(hi)); rows.append(r)
        report, table, _ = validate(raw(rows, "pc"), metadata("pc"))
        self.assertTrue(report["can_import"])
        self.assertEqual(table.num_rows, 3)
        self.assertEqual(report["exclusions"], {"unknown_owners": 1, "owner_interval_straddles_tiers": 1})

    def test_duplicate_invalid_values_and_empty_snapshot_block(self):
        a = mobile(); b = mobile(); b["free"] = "yes"
        report, _, _ = validate(raw([a, b]), metadata())
        self.assertFalse(report["can_import"])
        self.assertEqual(report["invalid_rows"], 1)
        self.assertIn("app_id", report["errors_by_field"])
        self.assertIn("free", report["errors_by_field"])
        report, _, _ = validate(template("mobile"), metadata())
        self.assertFalse(report["can_import"])
        for key, value in [("minimum_installs", "1.5"), ("price", "NaN"), ("release_date", "2026-02-30"), ("observed_date", "2026-10-02")]:
            with self.subTest(key=key):
                r = mobile(); r[key] = value
                self.assertFalse(validate(raw([r]), metadata())[0]["can_import"])

    def test_conflicts_are_masked_not_paid(self):
        r = mobile(); r.update(free="false", price="0", currency="")
        report, table, _ = validate(raw([r]), metadata())
        self.assertTrue(report["can_import"])
        self.assertIsNone(table["free"][0].as_py())
        self.assertEqual(report["warnings"]["free_price_conflict_masked"], 1)

    def test_invalid_headers_encoding_and_metadata(self):
        for data in [b"x,x\n1,2", b"\xff"]:
            with self.assertRaises(ValueError): validate(data, metadata())
        bad = metadata(); bad["outcome_definition"] = "revenue"
        with self.assertRaises(ValueError): validate(raw([mobile()]), bad)
        p = pc(); p["genres"] = "['Action']"
        self.assertFalse(validate(raw([p], "pc"), metadata("pc"))[0]["can_import"])

    def test_no_eligible_rows_and_date_proxy(self):
        r = mobile(); r.update(category="Sports", observed_date="")
        report, _, _ = validate(raw([r]), metadata())
        self.assertFalse(report["can_import"])
        self.assertEqual(report["warnings"]["observation_uses_snapshot_proxy"], 1)
        self.assertEqual(report["excluded_rows"], 1)


class RepositoryTests(unittest.TestCase):
    def test_duplicate_import_and_tampering(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = SnapshotRepository(Path(folder))
            one = repo.save(raw([mobile()]), metadata())
            two = repo.save(raw([mobile()]), metadata())
            self.assertEqual(one["version_id"], two["version_id"])
            self.assertTrue(two["already_exists"])
            self.assertEqual(repo.active()["mobile"], DEFAULT_VERSION)
            manifest, data = repo.load("mobile", one["version_id"])
            data.write_bytes(b"broken")
            with self.assertRaises(ValueError): repo.load("mobile", one["version_id"])
            self.assertEqual(len(repo.list_versions()), 1)

    def test_failed_write_and_invalid_data_leave_no_version(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = SnapshotRepository(Path(folder))
            with patch("imports.repository.pq.write_table", side_effect=OSError("disk full")):
                with self.assertRaises(OSError): repo.save(raw([mobile()]), metadata())
            self.assertEqual(repo.list_versions(), [])
            self.assertEqual(list(Path(folder).glob(".import-*")), [])
            with self.assertRaises(ValueError): repo.save(raw([mobile(), mobile()]), metadata())
            self.assertFalse((Path(folder) / "active.json").exists())


class ApplicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory()
        cls.store = ComparisonStore(app_path=Path(cls.folder.name))

    @classmethod
    def tearDownClass(cls):
        cls.store.db.close(); cls.folder.cleanup()

    def setUp(self):
        self.store.activate("mobile", DEFAULT_VERSION)
        self.store.activate("pc", DEFAULT_VERSION)

    def import_one(self):
        data = self.store.preview({"metadata": metadata(), "csv_text": raw([mobile()]).decode("utf-8")})
        return self.store.commit_preview({"preview_id": data["preview_id"]})["version_id"]

    def test_activation_restart_stale_requests_and_rollback(self):
        ident = self.import_one()
        self.assertEqual(self.store.active["mobile"], DEFAULT_VERSION)
        self.store.activate("mobile", ident)
        payload = dict(platform="mobile", a={}, b={}, version_id=ident)
        result = self.store.compare(payload)
        self.assertEqual(result["partition"], "application_snapshot")
        self.assertEqual(result["scenarios"]["a"]["total"], 1)
        self.assertIsNone(result["analysis_manifest_sha256"])
        self.assertNotIn("train_count", result["metadata"])
        with self.assertRaises(ValueError): self.store.compare({**payload, "version_id": DEFAULT_VERSION})
        restarted = ComparisonStore(app_path=Path(self.folder.name))
        try: self.assertEqual(restarted.active["mobile"], ident)
        finally: restarted.db.close()
        with patch.object(self.store.repository, "set_active", side_effect=OSError("disk full")):
            with self.assertRaises(OSError): self.store.activate("mobile", DEFAULT_VERSION)
        self.assertEqual(self.store.compare(payload)["scenarios"]["a"]["total"], 1)
        self.assertEqual(self.store.repository.active()["mobile"], ident)
        self.store.activate("mobile", DEFAULT_VERSION)
        self.assertEqual(self.store.compare(dict(platform="mobile", a={}, b={}))["scenarios"]["a"]["total"], 221806)

    def test_invalid_preview_expiry_and_version_paths(self):
        result = self.store.preview({"metadata": metadata(), "csv_text": raw([mobile(), mobile()]).decode("utf-8")})
        self.assertIsNone(result["preview_id"])
        with self.assertRaises(ValueError): self.store.commit_preview({"preview_id": "fake"})
        preview = self.store.preview({"metadata": metadata(), "csv_text": raw([mobile()]).decode("utf-8")})
        pending = self.store.pending
        self.store.pending = (pending[0], pending[1] - 901, *pending[2:])
        with self.assertRaises(ValueError): self.store.commit_preview({"preview_id": preview["preview_id"]})
        for ident in ["../../analysis_v1", "pc-" + "0" * 24, None]:
            with self.assertRaises(ValueError): self.store.activate("mobile", ident)

    def test_http_write_token_origin_and_actual_upload(self):
        server = make_server(self.store, 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        url = f"http://127.0.0.1:{server.server_port}"
        def request(path, payload, headers=None):
            return urlopen(Request(url + path, json.dumps(payload).encode(), {"Content-Type": "application/json", **(headers or {})}), timeout=10)
        try:
            options = json.load(urlopen(url + "/api/options"))
            token = {"X-GameScope-Token": options["mutation_token"]}
            payload = {"metadata": metadata(), "csv_text": raw([mobile()]).decode("utf-8")}
            with self.assertRaises(HTTPError) as error: request("/api/import/preview", payload)
            self.assertEqual(error.exception.code, 403)
            error.exception.close()
            with self.assertRaises(HTTPError) as error: request("/api/import/preview", payload, {**token, "Origin": "https://example.com"})
            self.assertEqual(error.exception.code, 403)
            error.exception.close()
            preview = json.load(request("/api/import/preview", payload, token))
            saved = json.load(request("/api/import/commit", {"preview_id": preview["preview_id"]}, token))
            json.load(request("/api/activate", {"platform": "mobile", "version_id": saved["version_id"]}, token))
            result = json.load(request("/api/compare", dict(platform="mobile", a={}, b={}, version_id=saved["version_id"])))
            self.assertEqual(result["scenarios"]["a"]["total"], 1)
            self.assertEqual(urlopen(url + "/api/template?platform=pc").read(), template("pc"))
        finally:
            server.shutdown(); server.server_close(); thread.join()


if __name__ == "__main__": unittest.main()
