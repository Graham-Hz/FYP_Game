"""Immutable application snapshots with atomic activation; never touch analysis_v1."""
import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pyarrow.parquet as pq

from imports.contracts import VERSION, metadata_check, rule_fingerprint, validate

DEFAULT_VERSION = "research_train_v1"


def digest(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False).encode("utf-8")


def version_id(summary):
    identity = {k: summary[k] for k in ("input_sha256", "metadata", "contract_version", "rule_sha256")}
    return summary["metadata"]["platform"] + "-" + hashlib.sha256(encoded(identity)).hexdigest()[:24]


class SnapshotRepository:
    def __init__(self, path):
        self.path = Path(path)

    def active(self):
        path = self.path / "active.json"
        if not path.exists():
            return {"pc": DEFAULT_VERSION, "mobile": DEFAULT_VERSION}
        try:
            result = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(result, dict) or set(result) != {"pc", "mobile"}:
                raise ValueError("Invalid activation registry")
            for platform, ident in result.items():
                self.check_id(platform, ident)
            return result
        except (ValueError, TypeError) as exc:
            raise ValueError("資料版本設定無效。請保留檔案並按 CSV_IMPORT_GUIDE.md 修復。") from exc

    @staticmethod
    def check_id(platform, ident):
        if platform not in {"pc", "mobile"} or not isinstance(ident, str):
            raise ValueError("Invalid platform/version")
        if ident != DEFAULT_VERSION and not re.fullmatch(platform + r"-[0-9a-f]{24}", ident):
            raise ValueError("Invalid version ID")

    def set_active(self, active):
        if set(active) != {"pc", "mobile"}:
            raise ValueError("Invalid activation registry")
        for p, ident in active.items():
            self.check_id(p, ident)
        self.path.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=".active-", suffix=".tmp", dir=self.path)
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(encoded(active))
                f.flush()
                os.fsync(f.fileno())
            os.replace(temporary, self.path / "active.json")
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def save(self, raw, metadata, prepared=None):
        summary, table, ledger = prepared if prepared is not None else validate(raw, metadata)
        if summary["input_sha256"] != hashlib.sha256(raw).hexdigest() or summary["metadata"] != metadata_check(metadata):
            raise ValueError("預覽與來源資料不一致，請重新驗證。")
        if summary["rule_sha256"] != rule_fingerprint() or not summary["can_import"]:
            raise ValueError("驗證未通過或規則已改變，不能儲存。")
        ident = version_id(summary)
        versions = self.path / "versions"
        destination = versions / ident
        if destination.exists():
            self.load(summary["metadata"]["platform"], ident)
            return {"version_id": ident, "already_exists": True, "validation": summary}
        versions.mkdir(parents=True, exist_ok=True)
        # A failed write never appears in versions and cannot alter active.json.
        with tempfile.TemporaryDirectory(prefix=".import-", dir=self.path) as temporary:
            folder = Path(temporary)
            (folder / "source.csv").write_bytes(raw)
            (folder / "validation.json").write_bytes(encoded(summary))
            pq.write_table(table, folder / "data.parquet", compression="zstd")
            pq.write_table(ledger, folder / "ledger.parquet", compression="zstd")
            manifest = {"version_id": ident, "created_at_utc": datetime.now(timezone.utc).isoformat(),
                        "contract_version": VERSION, "rule_sha256": summary["rule_sha256"], "metadata": summary["metadata"],
                        "eligible_rows": summary["eligible_rows"], "total_rows": summary["total_rows"],
                        "files": {name: digest(folder / name) for name in ("source.csv", "validation.json", "data.parquet", "ledger.parquet")}}
            (folder / "manifest.json").write_bytes(encoded(manifest))
            # Move just the completed artifact directory, then let TemporaryDirectory clean its empty parent.
            completed = folder / "completed"
            completed.mkdir()
            for file in list(folder.iterdir()):
                if file != completed:
                    file.rename(completed / file.name)
            completed.rename(destination)
        return {"version_id": ident, "already_exists": False, "validation": summary}

    def load(self, platform, ident):
        self.check_id(platform, ident)
        if ident == DEFAULT_VERSION:
            raise ValueError("Research data is loaded separately")
        folder = self.path / "versions" / ident
        try:
            manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
            meta = metadata_check(manifest["metadata"])
            if manifest["version_id"] != ident or meta["platform"] != platform:
                raise ValueError("Version/platform mismatch")
            if manifest["contract_version"] != VERSION or manifest["rule_sha256"] != rule_fingerprint():
                raise ValueError("Validation rules changed; reimport the saved source with current rules")
            expected = {"source.csv", "validation.json", "data.parquet", "ledger.parquet"}
            if set(manifest["files"]) != expected:
                raise ValueError("Invalid version contents")
            for name, fingerprint in manifest["files"].items():
                if digest(folder / name) != fingerprint:
                    raise ValueError(f"Version checksum mismatch: {name}")
            summary = json.loads((folder / "validation.json").read_text(encoding="utf-8"))
            if version_id(summary) != ident or not summary["can_import"] or summary["metadata"] != meta:
                raise ValueError("Version identity mismatch")
            return manifest, folder / "data.parquet"
        except (OSError, KeyError, TypeError) as exc:
            raise ValueError("版本資料不完整，無法啟用。") from exc

    def list_versions(self):
        result = []
        for path in sorted((self.path / "versions").glob("*/manifest.json")):
            try:
                m = json.loads(path.read_text(encoding="utf-8"))
                self.check_id(m["metadata"]["platform"], m["version_id"])
                if path.parent.name != m["version_id"]:
                    continue
                result.append({k: m[k] for k in ("version_id", "metadata", "eligible_rows", "total_rows", "created_at_utc")})
            except (OSError, KeyError, TypeError, ValueError):
                continue  # Never activate malformed entries; active corruption fails on startup.
        return result
