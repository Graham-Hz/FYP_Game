"""Negative-path checks for distribution diagnostics, independent of large datasets."""
import json
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src/demo"))
import preflight


class DemoPreflightTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="demo package 測試 ")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "Program"
        for relative in preflight.REQUIRED_FILES:
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"{}" if path.suffix == ".json" else b"fixture data\n")
        manifest = {
            "outputs": {name: preflight.digest(self.root / name) for name in preflight.ANALYSIS_ARTIFACTS},
            "inputs": {name: preflight.digest(self.root / name) for name in preflight.CANDIDATE_ARTIFACTS},
        }
        path = self.root / preflight.ANALYSIS_MANIFEST
        path.write_text(json.dumps(manifest), encoding="utf-8")
        self.frozen = patch.object(preflight, "EXPECTED_MANIFEST", preflight.digest(path))
        self.frozen.start()
        self.addCleanup(self.frozen.stop)
        (self.root / preflight.REVENUE_MANIFEST).write_text(json.dumps({
            "artifact_sha256": preflight.digest(self.root / preflight.REVENUE_ARTIFACT)
        }), encoding="utf-8")

    def failures(self):
        return [message for ok, message in preflight.data_checks(self.root) if not ok]

    def package_manifest(self, files):
        path = self.root.parent / "DEMO_PACKAGE_MANIFEST.json"
        path.write_text(json.dumps({"schema_version": 1, "files": files}), encoding="utf-8")

    def test_complete_fixture_and_source_checkout(self):
        self.assertEqual(self.failures(), [])
        self.assertTrue(all(ok for ok, _ in preflight.package_checks(self.root)))

    def test_missing_data_explains_github_zip(self):
        (self.root / preflight.ANALYSIS_ARTIFACTS[0]).unlink()
        failures = self.failures()
        self.assertTrue(any("Missing required file" in item for item in failures))
        self.assertTrue(any("GitHub Download ZIP" in item for item in failures))

    def test_corrupt_core_candidate_and_revenue_are_each_rejected(self):
        for relative in (preflight.ANALYSIS_ARTIFACTS[0], preflight.CANDIDATE_ARTIFACTS[0], preflight.REVENUE_ARTIFACT):
            with self.subTest(relative=relative):
                path = self.root / relative
                original = path.read_bytes()
                path.write_bytes(b"damaged")
                self.assertTrue(any("checksum mismatch" in item.lower() for item in self.failures()))
                path.write_bytes(original)

    def test_changed_frozen_manifest_is_rejected(self):
        with (self.root / preflight.ANALYSIS_MANIFEST).open("ab") as stream:
            stream.write(b" ")
        self.assertTrue(any("Frozen analysis manifest checksum" in item for item in self.failures()))

    def test_missing_reference_and_static_files_are_rejected(self):
        for relative in ("../Dataset/Development Fee References/fees.csv", "src/demo/static/market.js"):
            (self.root / relative).unlink()
            self.assertTrue(any(relative in item for item in self.failures()))

    def test_package_hashes_detect_changed_and_missing_file(self):
        path = self.root / "src/demo/static/market.js"
        self.package_manifest([{"path": "Program/src/demo/static/market.js",
                                "sha256": preflight.digest(path), "size_bytes": path.stat().st_size}])
        self.assertTrue(all(ok for ok, _ in preflight.package_checks(self.root)))
        path.write_bytes(b"changed data")
        self.assertTrue(any(not ok and "changed" in text for ok, text in preflight.package_checks(self.root)))
        path.unlink()
        self.assertTrue(any(not ok and "missing" in text for ok, text in preflight.package_checks(self.root)))

    def test_package_rejects_escape_and_duplicate_paths(self):
        for relative in ("../outside.txt", "C:/outside.txt", "/outside.txt", "Program\\src\\demo\\server.py"):
            with self.subTest(relative=relative):
                self.package_manifest([{"path": relative, "sha256": "0" * 64, "size_bytes": 0}])
                self.assertTrue(any(not ok and "manifest check failed" in text for ok, text in preflight.package_checks(self.root)))
        item = {"path": "Program/src/demo/server.py", "sha256": "0" * 64, "size_bytes": 0}
        self.package_manifest([item, item])
        self.assertTrue(any(not ok and "duplicate" in text for ok, text in preflight.package_checks(self.root)))

    def test_write_probe_cleans_up_and_reports_permission_denied(self):
        self.assertTrue(preflight.writable_check(self.root)[0])
        self.assertFalse((self.root / "data/application").exists())
        with patch.object(preflight.tempfile, "TemporaryFile", side_effect=PermissionError("read-only test")):
            ok, message = preflight.writable_check(self.root)
        self.assertFalse(ok)
        self.assertIn("writable folder", message)
        self.assertFalse((self.root / "data/application").exists())

    def test_existing_import_state_survives_write_probe(self):
        path = self.root / "data/application/v1/active.json"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"existing state")
        self.assertTrue(preflight.writable_check(self.root)[0])
        self.assertEqual(path.read_bytes(), b"existing state")

    def test_busy_port_has_actionable_message(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            sock.listen(1)
            ok, message = preflight.port_check(sock.getsockname()[1])
        self.assertFalse(ok)
        self.assertIn("--port", message)


if __name__ == "__main__":
    unittest.main()
