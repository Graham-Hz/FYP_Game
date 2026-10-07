"""Local, read-only historical comparison proof; no fitted model or held-out queries."""
import argparse
import hashlib
import json
import threading
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import duckdb

ROOT = Path(__file__).resolve().parents[2]
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
    def __init__(self, root=ROOT):
        self.lock = threading.Lock()
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
        if not isinstance(payload, dict) or set(payload) != {"platform", "a", "b"}:
            raise ValueError("Expected platform and two scenarios a/b.")
        platform = payload["platform"]
        if not isinstance(platform, str) or platform not in PLATFORMS:
            raise ValueError("Unknown platform.")
        result = {"demo_version": "historical_comparison_v1", "platform": platform,
                  "partition": "train", "analysis_manifest_sha256": EXPECTED_MANIFEST,
                  "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                  "metadata": self.options[platform], "small_sample_threshold": SMALL_SAMPLE,
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
            path = urlsplit(self.path).path
            if path == "/api/options":
                self.respond(200, {"platforms": store.options})
                return
            files = {"/": ("index.html", "text/html; charset=utf-8"),
                     "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                     "/style.css": ("style.css", "text/css; charset=utf-8")}
            if path not in files:
                self.respond(404, {"error": "Not found"})
                return
            file, mime = files[path]
            self.respond(200, (STATIC / file).read_bytes(), mime)

        def do_POST(self):
            if self.path != "/api/compare":
                self.respond(404, {"error": "Not found"})
                return
            # No cross-origin API use; no data or settings are written by this server.
            origin = self.headers.get("Origin")
            if origin and origin != f"http://127.0.0.1:{self.server.server_port}":
                self.respond(403, {"error": "Use the local demo page."})
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if size < 1 or size > 8192:
                    raise ValueError("Invalid request size.")
                payload = json.loads(self.rfile.read(size))
                self.respond(200, store.compare(payload))
            except (ValueError, UnicodeDecodeError) as exc:
                self.respond(400, {"error": str(exc)})

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
