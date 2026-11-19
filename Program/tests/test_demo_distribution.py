"""Distribution boundaries: include runtime files without copying private state."""
import hashlib
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src/distribution"))
from build_demo import FIXED_FILES, RENAMED_FILES, build_archive, selected_files, document_bytes


class DistributionTests(unittest.TestCase):
    def test_allowlist_and_exact_archive_inventory(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for rel in (*FIXED_FILES, *RENAMED_FILES.values(),
                        "Program/src/demo/server.py", "Program/src/demo/static/market.js"):
                path = root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes((rel + "\n").encode())
            excluded = [".env", ".git/config", "Program/.venv/pyvenv.cfg",
                        "Program/data/application/v1/active.json", "Program/src/demo/__pycache__/x.pyc",
                        "Program/reports/private.docx", "Dataset/original.csv",
                        "Program/src/demo/static/secret.env"]
            for rel in excluded:
                path = root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("never ship")
            entries = selected_files(root)
            self.assertFalse(set(excluded) & entries.keys())
            self.assertEqual(entries["README.md"], root / RENAMED_FILES["README.md"])
            archive_path = root / "out/Demo.zip"
            result = build_archive(entries, archive_path, "Demo")
            with zipfile.ZipFile(archive_path) as archive:
                manifest = json.loads(archive.read("Demo/DEMO_PACKAGE_MANIFEST.json"))
                self.assertEqual(len(archive.namelist()), len(entries) + 1)
                for entry in manifest["files"]:
                    content = archive.read("Demo/" + entry["path"])
                    self.assertEqual(len(content), entry["size_bytes"])
                    self.assertEqual(hashlib.sha256(content).hexdigest(), entry["sha256"])
            self.assertEqual(result["sha256"], hashlib.sha256(archive_path.read_bytes()).hexdigest())
            with self.assertRaisesRegex(ValueError, "already exists"):
                build_archive(entries, archive_path, "Demo")

    def test_missing_input_does_not_make_archive(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, "missing"):
                selected_files(Path(folder))

    def test_document_links_distinguish_runtime_and_omitted_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "guide.md"
            path.write_text("[local](README.md) [research](README.md#audit-supplementary-revenue-data) "
                            "[evidence](reports/verification.md) [external](https://example.com/)", encoding="utf-8")
            text = document_bytes("Program/DEMO_GUIDE.md", path, {"Program/README.md": path}).decode()
            self.assertIn("[local](README.md)", text)
            self.assertIn("blob/main/Program/README.md#audit-supplementary-revenue-data", text)
            self.assertIn("blob/main/Program/reports/verification.md", text)
            self.assertIn("[external](https://example.com/)", text)

    def test_bad_member_does_not_leave_deliverable(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "input.txt"
            source.write_text("test")
            for member in ("../escape", "/absolute", "C:/outside", "a\\b"):
                output = root / "Demo.zip"
                with self.subTest(member=member), self.assertRaises(ValueError):
                    build_archive({member: source}, output, "Demo")
                self.assertFalse(output.exists())
                self.assertFalse(list(root.glob(".demo-*")))


if __name__ == "__main__":
    unittest.main()
