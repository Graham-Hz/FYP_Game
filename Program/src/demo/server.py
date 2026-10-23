"""Local historical comparison with independent, validated CSV snapshot versions."""
import argparse
import hashlib
import json
import copy
import secrets
import sys
import threading
import time
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

import duckdb

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from imports.contracts import MAX_BYTES, template, validate
from imports.repository import DEFAULT_VERSION, SnapshotRepository
from revenue import RevenueStore
STATIC = Path(__file__).parent / "static"
MANIFEST = "reports/2026-10-06/analysis_v1/manifest.json"
EXPECTED_MANIFEST = "5f3f341ed1c45fbca703995d95d4eca46d54d1af75e69677e15308d20aed12a6"
SMALL_SAMPLE = 30  # Display convention, not a claim of statistical adequacy.
PLATFORMS = {
    "pc": {
        "name": "Steam", "snapshot": "2025-03",
        "scope": "正價格、擁有者分級及開發者資料可用的遊戲；已排除僅軟件類型紀錄。只顯示訓練分區。",
        "outcome": "來源估算擁有者區間分級",
        "caveat": "價格為資料快照時的觀察值，並非已確認的發售價格。類型及功能可以重疊；兩組樣本也可能重疊。",
        "fields": {"genre": ("遊戲類型", "genres", "list"),
                   "capability": ("遊戲功能", "planning_categories", "list")},
        "tiers": [("O1_source_interval_up_to_20k", "來源區間上限 ≤ 20,000"),
                  ("O2_source_intervals_20k_to_100k", "來源區間 20,000–100,000"),
                  ("O3_source_intervals_100k_plus", "來源區間下限 ≥ 100,000")],
    },
    "mobile": {
        "name": "Android", "snapshot": "2021-06",
        "scope": "16 個明確遊戲類別，且發佈日期可用；不包含類型含糊的 Sports。只顯示訓練分區。",
        "outcome": "來源安裝量下限分級",
        "caveat": "免費狀態不明與付費分開處理。廣告及內購欄位是歷史快照，不能代表發售時的策略。",
        "fields": {"category": ("遊戲類別", "category", "string"),
                   "free": ("免費下載", "free", "bool"),
                   "ads": ("含廣告", "ad_supported", "bool"),
                   "iap": ("應用程式內購買", "in_app_purchases", "bool")},
        "tiers": [("M1_under_1k", "下限 < 1,000"),
                  ("M2_1k_to_under_100k", "1,000 ≤ 下限 < 100,000"),
                  ("M3_100k_plus", "下限 ≥ 100,000")],
    },
}


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


class ComparisonStore:
    def __init__(self, root=ROOT, app_path=None):
        self.lock = threading.RLock()
        self.import_lock = threading.Lock()
        self.pending = None
        self.root = root
        self.repository = SnapshotRepository(app_path if app_path is not None else root / "data/application/v1")
        self.active = {"pc": DEFAULT_VERSION, "mobile": DEFAULT_VERSION}
        manifest_path = root / MANIFEST
        if sha256(manifest_path) != EXPECTED_MANIFEST:
            raise ValueError("Frozen analysis manifest changed; review it before running this demo.")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.db = duckdb.connect(":memory:")
        self.options = {}
        for platform, spec in PLATFORMS.items():
            paths = []
            for kind in ("features", "labels_splits"):
                relative = f"data/processed/analysis_v1/{platform}_{kind}.parquet"
                path = root / relative
                if sha256(path) != manifest["outputs"][relative]:
                    raise ValueError(f"Frozen artifact changed: {relative}")
                paths.append(str(path))
            # Materialize TRAIN rows only. The API has no selectable split parameter.
            self.db.execute(f"""CREATE TABLE {platform} AS
                SELECT f.*, l.target_tier FROM read_parquet(?) f
                JOIN read_parquet(?) l USING(app_id) WHERE l.split = 'train'""", paths)
            count, unique = self.db.execute(f"SELECT count(*), count(DISTINCT app_id) FROM {platform}").fetchone()
            if count != unique or count != manifest["summary"][platform]["split_rows"]["train"]:
                raise ValueError(f"Unexpected train membership: {platform}")
            actual_tiers = {r[0] for r in self.db.execute(f"SELECT DISTINCT target_tier FROM {platform}").fetchall()}
            if actual_tiers != {t[0] for t in spec["tiers"]}:
                raise ValueError(f"Unexpected target tiers: {platform}")
            fields = []
            for key, (label, column, kind) in spec["fields"].items():
                if kind == "bool":
                    choices = [{"value": "true", "label": "是"}, {"value": "false", "label": "否"},
                               {"value": "unknown", "label": "資料不明"}]
                else:
                    expression = f"unnest({column})" if kind == "list" else column
                    values = self.db.execute(f"SELECT DISTINCT v FROM (SELECT {expression} v FROM {platform}) WHERE v IS NOT NULL ORDER BY v").fetchall()
                    choices = [{"value": v, "label": v} for (v,) in values]
                fields.append({"key": key, "label": label, "choices": choices})
            self.options[platform] = {k: spec[k] for k in ("name", "snapshot", "scope", "outcome", "caveat")}
            self.options[platform].update(train_count=count, fields=fields)
            self.options[platform].update(row_count=count, sample_label="訓練樣本", version_id=DEFAULT_VERSION,
                                          partition="train", data_kind="historical", source_name="固定研究 train 資料")
        self.research_options = copy.deepcopy(self.options)
        for platform, ident in self.repository.active().items():
            if ident != DEFAULT_VERSION:
                self.activate(platform, ident, persist=False)

    def options_snapshot(self):
        with self.lock:
            return copy.deepcopy(self.options)

    def versions(self):
        with self.lock:
            return {"active": dict(self.active), "versions": self.repository.list_versions(), "default_version": DEFAULT_VERSION}

    def preview(self, payload):
        if not isinstance(payload, dict) or set(payload) != {"metadata", "csv_text"} or not isinstance(payload["csv_text"], str):
            raise ValueError("請提供 metadata 和 csv_text。")
        with self.import_lock:
            self.pending = None
            raw = payload["csv_text"].encode("utf-8")
            prepared = validate(raw, payload["metadata"])
            token = secrets.token_urlsafe(24) if prepared[0]["can_import"] else None
            if token:
                self.pending = (token, time.monotonic(), raw, prepared)
            return {"preview_id": token, "validation": prepared[0], "expires_in_seconds": 900 if token else 0}

    def commit_preview(self, payload):
        if not isinstance(payload, dict) or set(payload) != {"preview_id"}:
            raise ValueError("請提供 preview_id。")
        with self.import_lock:
            if not self.pending or payload["preview_id"] != self.pending[0] or time.monotonic() - self.pending[1] > 900:
                self.pending = None
                raise ValueError("預覽已過期或被新的預覽取代，請重新驗證。")
            _, _, raw, prepared = self.pending
            with self.lock:
                result = self.repository.save(raw, prepared[0]["metadata"], prepared)
            self.pending = None
            return result

    def activate(self, platform, ident, persist=True):
        self.repository.check_id(platform, ident)
        with self.lock:
            old_active = dict(self.active)
            if ident == DEFAULT_VERSION:
                manifest = json.loads((self.root / MANIFEST).read_text(encoding="utf-8"))
                if sha256(self.root / MANIFEST) != EXPECTED_MANIFEST:
                    raise ValueError("Research manifest changed")
                paths = []
                for kind in ("features", "labels_splits"):
                    rel = f"data/processed/analysis_v1/{platform}_{kind}.parquet"
                    if sha256(self.root / rel) != manifest["outputs"][rel]:
                        raise ValueError("Research artifact changed")
                    paths.append(str(self.root / rel))
                query = f"CREATE OR REPLACE TABLE {platform} AS SELECT f.*, l.target_tier FROM read_parquet(?) f JOIN read_parquet(?) l USING(app_id) WHERE l.split = 'train'"
                spec = copy.deepcopy(self.research_options[platform])
            else:
                manifest, parquet = self.repository.load(platform, ident)
                paths = [str(parquet)]
                query = f"CREATE OR REPLACE TABLE {platform} AS SELECT * FROM read_parquet(?)"
                meta = manifest["metadata"]
                spec = copy.deepcopy(self.research_options[platform])
                spec.pop("train_count", None)
                spec.update(snapshot=meta["snapshot_date"], version_id=ident, partition="application_snapshot",
                            data_kind=meta["data_kind"], source_name=meta["source_name"], source_url=meta["source_url"],
                            contract_version=manifest["contract_version"], rule_sha256=manifest["rule_sha256"],
                            input_sha256=manifest["files"]["source.csv"], price_currency=meta["price_currency"],
                            row_count=manifest["eligible_rows"], sample_label="合資格樣本",
                            scope=("人工示例資料；不可解讀為市場證據。" if meta["data_kind"] == "synthetic" else "匯入的歷史快照；未經獨立來源核實。") +
                                  ("僅納入正觀察價格、owners 分級及開發者可用的遊戲；排除軟件及 demo/playtest 啟發式命中。" if platform == "pc" else "僅納入 16 個遊戲類別、發佈日期、安裝量下界及開發者可用的紀錄。") +
                                  "此版本沒有研究 train/test 切分，也不會更新模型。")
            self.db.execute("BEGIN TRANSACTION")
            wrote_active = False
            try:
                self.db.execute(query, paths)
                count, unique = self.db.execute(f"SELECT count(*), count(DISTINCT app_id) FROM {platform}").fetchone()
                if count != unique or count != spec["row_count"]:
                    raise ValueError("Version row counts are inconsistent")
                for field in spec["fields"]:
                    _, column, kind = PLATFORMS[platform]["fields"][field["key"]]
                    if kind != "bool":
                        expression = f"unnest({column})" if kind == "list" else column
                        values = self.db.execute(f"SELECT DISTINCT v FROM (SELECT {expression} v FROM {platform}) WHERE v IS NOT NULL ORDER BY v").fetchall()
                        field["choices"] = [{"value": v, "label": v} for v, in values]
                next_active = {**old_active, platform: ident}
                if persist:
                    self.repository.set_active(next_active)
                    wrote_active = True
                self.db.execute("COMMIT")
            except Exception:
                self.db.execute("ROLLBACK")
                if wrote_active:
                    self.repository.set_active(old_active)
                raise
            self.options[platform] = spec
            self.active = next_active
            return {"active": dict(self.active), "platforms": copy.deepcopy(self.options)}

    def _where(self, platform, filters):
        if not isinstance(filters, dict) or set(filters) - set(PLATFORMS[platform]["fields"]):
            raise ValueError("Unknown comparison filter.")
        conditions, params, normalized = [], [], {}
        for field in self.options[platform]["fields"]:
            key = field["key"]
            value = filters.get(key, "")
            if not isinstance(value, str):
                raise ValueError("Filter values must be strings.")
            if value == "":
                continue
            if value not in {c["value"] for c in field["choices"]}:
                raise ValueError(f"Invalid value for {key}.")
            _, column, kind = PLATFORMS[platform]["fields"][key]
            normalized[key] = value
            if kind == "bool" and value == "unknown":
                conditions.append(f"{column} IS NULL")
            elif kind == "bool":
                conditions.append(f"{column} = ?")
                params.append(value == "true")
            else:
                conditions.append(f"list_contains({column}, ?)" if kind == "list" else f"{column} = ?")
                params.append(value)
        return " AND ".join(conditions) or "TRUE", params, normalized

    def compare(self, payload):
        if not isinstance(payload, dict) or set(payload) not in ({"platform", "a", "b"}, {"platform", "a", "b", "version_id"}):
            raise ValueError("Expected platform and two scenarios a/b.")
        platform = payload["platform"]
        if not isinstance(platform, str) or platform not in PLATFORMS:
            raise ValueError("Unknown platform.")
        with self.lock:
            return self._compare_locked(platform, payload)

    def _compare_locked(self, platform, payload):
        if "version_id" in payload and payload["version_id"] != self.active[platform]:
            raise ValueError("資料版本已改變，請重新整理頁面後比較。")
        spec = copy.deepcopy(self.options[platform])
        result = {"demo_version": "historical_comparison_v2", "platform": platform,
                  "version_id": self.active[platform], "partition": spec["partition"],
                  "analysis_manifest_sha256": EXPECTED_MANIFEST if spec["partition"] == "train" else None,
                  "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                  "metadata": spec, "small_sample_threshold": SMALL_SAMPLE,
                  "interpretation": "Historical associations only; not forecasts, causal effects, revenue or current market coverage.",
                  "scenarios": {}}
        with self.lock:
            predicates = {}
            for name in ("a", "b"):
                where, params, normalized = self._where(platform, payload[name])
                predicates[name] = (where, params)
                counts = dict(self.db.execute(f"SELECT target_tier, count(*) FROM {platform} WHERE {where} GROUP BY target_tier", params).fetchall())
                total = sum(counts.values())
                tiers = [{"id": tier, "label": label, "count": counts.get(tier, 0),
                          "percent": round(100 * counts.get(tier, 0) / total, 4) if total else None}
                         for tier, label in PLATFORMS[platform]["tiers"]]
                result["scenarios"][name] = {"filters": normalized, "total": total, "tiers": tiers,
                    "status": "no_matches" if total == 0 else "small_sample" if total < SMALL_SAMPLE else "available"}
            wa, pa = predicates["a"]
            wb, pb = predicates["b"]
            result["overlap_count"] = self.db.execute(f"SELECT count(*) FROM {platform} WHERE ({wa}) AND ({wb})", pa + pb).fetchone()[0]
        return result


def make_server(store, port=8765):
    mutation_token = secrets.token_urlsafe(32)
    upload_gate = threading.BoundedSemaphore(1)
    try:
        revenue_store = RevenueStore(store.root)
    except (OSError, ValueError, KeyError):
        revenue_store = None
    class Handler(BaseHTTPRequestHandler):
        def respond(self, status, data, content_type="application/json; charset=utf-8"):
            body = json.dumps(data, ensure_ascii=False, allow_nan=False).encode("utf-8") if isinstance(data, dict) else data
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if not self.local_host():
                self.respond(403, {"error": "Use the local demo address."})
                return
            path = urlsplit(self.path).path
            if path == "/api/revenue":
                if revenue_store is None:
                    self.respond(503, {"error": "營收分析資料尚未準備好或版本核對失敗。請先執行 build_revenue_analysis.py，再重新啟動網站。"})
                    return
                try:
                    params = parse_qs(urlsplit(self.path).query, keep_blank_values=True, max_num_fields=8)
                    self.respond(200, revenue_store.query(params))
                except ValueError as exc:
                    self.respond(400, {"error": str(exc)})
                return
            if path == "/api/options":
                self.respond(200, {"platforms": store.options_snapshot(), "mutation_token": mutation_token})
                return
            if path == "/api/versions":
                self.respond(200, store.versions())
                return
            if path == "/api/template":
                platform = parse_qs(urlsplit(self.path).query).get("platform", [""])[0]
                try:
                    self.respond(200, template(platform), "text/csv; charset=utf-8")
                except ValueError as exc:
                    self.respond(400, {"error": str(exc)})
                return
            files = {"/": ("index.html", "text/html; charset=utf-8"),
                     "/revenue": ("revenue.html", "text/html; charset=utf-8"),
                     "/revenue.js": ("revenue.js", "text/javascript; charset=utf-8"),
                     "/revenue.css": ("revenue.css", "text/css; charset=utf-8"),
                     "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                     "/style.css": ("style.css", "text/css; charset=utf-8")}
            if path not in files:
                self.respond(404, {"error": "Not found"})
                return
            file, mime = files[path]
            self.respond(200, (STATIC / file).read_bytes(), mime)

        def do_POST(self):
            if self.path not in {"/api/compare", "/api/references", "/api/import/preview", "/api/import/commit", "/api/activate"}:
                self.respond(404, {"error": "Not found"})
                return
            origin = self.headers.get("Origin")
            if not self.local_host() or (origin and origin != f"http://127.0.0.1:{self.server.server_port}"):
                self.respond(403, {"error": "Use the local demo page."})
                return
            mutation = self.path not in {"/api/compare", "/api/references"}
            if mutation and (self.headers.get("X-GameScope-Token") != mutation_token or self.headers.get_content_type() != "application/json"):
                self.respond(403, {"error": "請從本機頁面操作資料版本。"})
                return
            if not upload_gate.acquire(blocking=False):
                self.respond(409, {"error": "目前有其他請求，請稍後重試。"})
                return
            try:
                self.connection.settimeout(30)
                size = int(self.headers.get("Content-Length", "0"))
                if size < 1 or size > (MAX_BYTES * 2 + 8192 if self.path == "/api/import/preview" else 8192):
                    raise ValueError("Invalid request size.")
                payload = json.loads(self.rfile.read(size))
                if self.path == "/api/references":
                    if revenue_store is None:
                        self.respond(503, {"error": "參考作品資料尚未準備好；請建立營收分析資料後重新啟動。"})
                        return
                    result = revenue_store.references(payload)
                elif self.path == "/api/compare":
                    result = store.compare(payload)
                elif self.path == "/api/import/preview":
                    result = store.preview(payload)
                elif self.path == "/api/import/commit":
                    result = store.commit_preview(payload)
                else:
                    if not isinstance(payload, dict) or set(payload) != {"platform", "version_id"}:
                        raise ValueError("Expected platform and version_id")
                    result = store.activate(payload["platform"], payload["version_id"])
                self.respond(200, result)
            except (ValueError, UnicodeDecodeError, RecursionError) as exc:
                self.respond(400, {"error": str(exc)})
            except (OSError, duckdb.Error) as exc:
                self.log_error("Data operation failed: %s", exc)
                self.respond(500, {"error": "資料操作未完成；請查看啟動視窗，保留原有資料後重試。"})
            finally:
                upload_gate.release()

        def local_host(self):
            return self.headers.get("Host") == f"127.0.0.1:{self.server.server_port}"

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--open", action="store_true", help="Open the local page after verifying inputs")
    args = parser.parse_args()
    print("Verifying frozen data and loading training rows...", flush=True)
    try:
        store = ComparisonStore()
        server = make_server(store, args.port)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Demo could not start: {exc}\nSee DEMO_GUIDE.md.\n")
    url = f"http://127.0.0.1:{server.server_port}/"
    print(f"Demo ready: {url}\nClose this window or press Ctrl+C to stop.", flush=True)
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        store.db.close()


if __name__ == "__main__":
    main()
