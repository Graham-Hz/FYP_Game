"""Exercise the packaged local HTTP API with disposable application state.

Run this with the package's locked Python environment. This is an API smoke
check, not a browser test, a usability study or a second-computer certification.
No existing imported versions or research artifacts are modified.
"""
import argparse
import csv
import io
import json
import platform
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener


ROOT = Path(__file__).resolve().parents[2]
COUNTS = {"pc": 51152, "mobile": 221806, "revenue": 1500}
DEFAULT_VERSION = "research_train_v1"
STATIC_PATHS = (
    "/", "/market", "/revenue", "/planning", "/plan",
    "/app.js", "/style.css", "/market.js", "/market.css",
    "/charts.js", "/charts.css", "/revenue.js", "/revenue.css",
    "/planning.js", "/planning.css", "/fees.js", "/plan.js",
    "/workflow.js", "/workflow.css", "/budget_scenarios.js", "/budget_scenarios.css",
)


def require(condition, message):
    # Unlike assert, these checks still run with Python's -O flag.
    if not condition:
        raise RuntimeError(message)


def passed(report, name, **evidence):
    report["checks"].append({"name": name, "status": "passed", **evidence})
    print(f"PASS: {name}", flush=True)


class Client:
    def __init__(self, url):
        self.url = url
        self.token = None
        # Local verification should not depend on a machine's HTTP proxy setup.
        self.opener = build_opener(ProxyHandler({}))

    def request(self, path, payload=None, *, mutate=False, raw=False,
                expected_status=200):
        headers = {}
        body = None
        if payload is not None:
            body = json.dumps(payload, allow_nan=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if mutate:
            headers["X-GameScope-Token"] = self.token
            headers["Origin"] = self.url
        req = Request(self.url + path, data=body, headers=headers)
        try:
            response = self.opener.open(req, timeout=120)
        except HTTPError as exc:
            response = exc
        with response:
            data = response.read()
            require(response.status == expected_status,
                    f"{path}: expected HTTP {expected_status}, got "
                    f"{response.status}: {data[:300]!r}")
        return data if raw else json.loads(data)


def market_payload(source, version):
    return {"source": source, "version_id": version, "group": "",
            "year_from": None, "year_to": None, "top_n": 10,
            "rank_metric": "volume"}


def budget_example():
    return {
        "currency": "HKD", "months": 12,
        "team": [
            {"label": "Founder", "people": 1, "allocation": 1,
             "monthly_cash": 0, "monthly_unpaid": 12000},
            {"label": "Part-time developer", "people": 1, "allocation": .5,
             "monthly_cash": 16000, "monthly_unpaid": 0},
        ],
        "monthly_overhead": 2000, "outsourcing": 20000,
        "marketing": 15000, "other_one_off": 5000,
        "contingency_percent": 10, "available_funds": 200000,
        "net_unit_contribution": 40,
    }


def check_import(client, report):
    # The API provides the current contract header; the rows are artificial.
    template = client.request("/api/template?platform=mobile", raw=True)
    headers = next(csv.reader(io.StringIO(template.decode("utf-8-sig"))))
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=headers)
    writer.writeheader()
    for ident, installs in (("smoke.example.a", "1000"),
                            ("smoke.example.b", "100000")):
        writer.writerow({
            "app_id": ident, "title": "Synthetic portability example",
            "release_date": "2020-01-01", "observed_date": "2026-10-01",
            "category": "Puzzle", "developer_id": "Synthetic studio",
            "free": "true", "ad_supported": "false",
            "in_app_purchases": "", "minimum_installs": installs,
            "price": "0", "currency": "USD",
        })
    metadata = {"platform": "mobile", "source_name": "Synthetic smoke fixture",
                "source_url": "", "snapshot_date": "2026-10-01",
                "data_kind": "synthetic",
                "outcome_definition": "minimum_installs_lower_bound",
                "price_currency": "per_row"}
    client.request("/api/import/preview", {}, expected_status=403)
    preview = client.request("/api/import/preview",
                             {"metadata": metadata, "csv_text": stream.getvalue()},
                             mutate=True)
    require(preview["validation"]["can_import"] is True and
            preview["validation"]["eligible_rows"] == 2,
            "Synthetic CSV preview should accept exactly two records")
    saved = client.request("/api/import/commit",
                           {"preview_id": preview["preview_id"]}, mutate=True)
    ident = saved["version_id"]
    activated = client.request("/api/activate",
                               {"platform": "mobile", "version_id": ident},
                               mutate=True)
    require(activated["active"]["mobile"] == ident, "Import was not activated")
    imported = client.request("/api/market", market_payload("mobile", ident))
    require(imported["provenance"]["filtered_rows"] == 2 and
            imported["provenance"]["data_kind"] == "synthetic" and
            imported["provenance"]["partition"] == "application_snapshot",
            "Imported market analysis lost its synthetic snapshot provenance")
    require({row["app_id"] for row in imported["leaders"]["rows"]} ==
            {"smoke.example.a", "smoke.example.b"},
            "Imported market results contain unexpected records")
    restored = client.request("/api/activate",
                              {"platform": "mobile", "version_id": DEFAULT_VERSION},
                              mutate=True)
    require(restored["active"]["mobile"] == DEFAULT_VERSION,
            "Research version was not restored")
    comparison = client.request("/api/compare",
                                {"platform": "mobile", "a": {}, "b": {}})
    require(comparison["scenarios"]["a"]["total"] == COUNTS["mobile"],
            "Restored research row count differs")
    passed(report, "Synthetic CSV preview, commit, activation and rollback",
           eligible_rows=2, restored_rows=COUNTS["mobile"],
           uncredentialed_write_status=403)


def exercise(client, report):
    for path in STATIC_PATHS:
        require(bool(client.request(path, raw=True)), f"Empty static response: {path}")
    passed(report, "All application pages and static assets", paths=len(STATIC_PATHS))

    options = client.request("/api/options")
    client.token = options["mutation_token"]
    for source in ("pc", "mobile"):
        spec = options["platforms"][source]
        require(spec["version_id"] == DEFAULT_VERSION and
                spec["row_count"] == COUNTS[source],
                f"Unexpected initial {source} version or row count")
        comparison = client.request("/api/compare",
                                    {"platform": source, "a": {}, "b": {}})
        require(comparison["partition"] == "train" and
                comparison["scenarios"]["a"]["total"] == COUNTS[source] and
                comparison["overlap_count"] == COUNTS[source],
                f"Unexpected {source} comparison membership")
    passed(report, "Frozen Steam and Android comparison samples",
           pc_rows=COUNTS["pc"], mobile_rows=COUNTS["mobile"])

    sources = client.request("/api/market/options")["sources"]
    require({s["id"] for s in sources} == set(COUNTS), "Market source list differs")
    for source in sources:
        ident = source["id"]
        require(source["available"] is True, f"Market source unavailable: {ident}")
        result = client.request("/api/market", market_payload(ident, source["version_id"]))
        require(not result["empty"] and
                result["provenance"]["filtered_rows"] == COUNTS[ident],
                f"Unexpected {ident} market sample")
        require(len(result["charts"]) == 14 and
                len({c["id"] for c in result["charts"]}) == 14,
                f"Expected fourteen distinct charts for {ident}")
        require(bool(result["leaders"]["rows"]), f"Missing {ident} ranking")
        passed(report, f"{ident} market charts and ranking",
               rows=COUNTS[ident], charts=len(result["charts"]))

    gameplay_genres = {"Action", "Adventure", "Casual", "RPG", "Racing",
                       "Simulation", "Sports", "Strategy"}
    pc_genre = next(field for field in options["platforms"]["pc"]["fields"]
                    if field["key"] == "genre")
    pc_market = next(source for source in sources if source["id"] == "pc")
    require({choice["value"] for choice in pc_genre["choices"]} == gameplay_genres
            and set(pc_market["groups"]) == gameplay_genres,
            "Comparison and market options should expose the same eight gameplay genres")
    adventure_payload = market_payload("mobile", DEFAULT_VERSION)
    adventure_payload.update(group="Adventure", compare_group="")
    adventure = client.request("/api/market", adventure_payload)["comparison"]
    require(adventure["selected"]["n"] == 15795 and
            adventure["baseline"]["n"] == 206011 and
            adventure["overlap_count"] == 0,
            "Adventure and its disjoint remaining-sample baseline differ")
    records = client.request("/api/market/records", {
        "analysis": adventure_payload, "cohort": "selected",
        "tier": "M3_100k_plus", "q": "", "page": 1,
        "page_size": 20, "sort": "volume",
    })
    require(records["total"] == 2487 and len(records["rows"]) == 20 and
            records["context"]["version_id"] == DEFAULT_VERSION and
            records["context"]["cohort"] == "selected" and
            records["context"]["tier"] == "M3_100k_plus" and
            all(row["minimum_installs"] >= 100000 for row in records["rows"]),
            "Adventure highest-tier drill-down lost its count, bounds or version")
    passed(report, "Shared gameplay taxonomy, cohort comparison and record drill-down",
           gameplay_genres=8, selected_rows=15795, baseline_rows=206011,
           high_tier_rows=2487, records_returned=20, version_id=DEFAULT_VERSION)

    revenue = client.request("/api/revenue")
    require(revenue["summary"]["count"] == 1415, "Unexpected positive-price revenue sample")
    client.request("/api/revenue/metadata")
    references = client.request("/api/references",
                                {"genres": ["Action"], "price": 14.99,
                                 "limit": 10, "price_factor": 2})
    require(bool(references["rows"]), "No reference games returned")
    passed(report, "Revenue analysis and reference retrieval",
           positive_price_rows=1415, references=len(references["rows"]))

    cases = client.request("/api/planning/cases")
    fees = client.request("/api/planning/fees")
    require(cases["metadata"]["case_count"] == 10 and
            cases["metadata"]["observation_count"] == 37,
            "Unexpected development-case collection")
    require(fees["metadata"]["fee_count"] == 26 and
            fees["metadata"]["source_count"] == 16,
            "Unexpected fee catalogue")
    for name in ("cases", "observations", "sources"):
        require(bool(client.request("/api/planning/csv/" + name, raw=True)),
                f"Empty case CSV: {name}")
    for name in ("fees", "sources"):
        require(bool(client.request("/api/planning/fees/csv/" + name, raw=True)),
                f"Empty fee CSV: {name}")
    passed(report, "Cost cases, fee catalogue and five CSV downloads",
           cases=10, observations=37, fees=26, fee_sources=16)

    request = budget_example()
    manual = client.request("/api/planning/budget", request)
    require(manual["base"]["cash_budget"] == 176000 and
            manual["base"]["resource_budget"] == 320000 and
            manual["base"]["cash_break_even_units"] == 4400,
            "Artificial manual budget differs from hand-calculated example")
    request["fee_selection"] = {
        "revision": fees["metadata"]["revision"],
        "items": [{"fee_id": "F002", "quantity": 2, "fx_rate": 7.8,
                   "target_currency": "HKD", "eligibility_confirmed": True,
                   "billing_assumption": None}],
    }
    with_fees = client.request("/api/planning/budget", request)
    require(with_fees["base"]["cash_budget"] == 215639.6 and
            with_fees["delays"][1]["cash_budget"] == 288279.2,
            "Artificial selected-fee/renewal budget differs")
    passed(report, "Artificial manual and source-linked fee budgets",
           currency="HKD", manual_cash=176000, with_fees_cash=215639.6,
           delayed_with_fees_cash=288279.2)
    check_import(client, report)


def run(report, temporary_parent=None):
    sys.path.insert(0, str(ROOT / "src"))
    sys.path.insert(0, str(ROOT / "src/demo"))
    from server import ComparisonStore, make_server

    # Only this newly created temporary directory may receive import writes.
    with tempfile.TemporaryDirectory(prefix="fyp-smoke-", dir=temporary_parent) as temporary:
        app_path = Path(temporary).resolve() / "application"
        store = ComparisonStore(root=ROOT, app_path=app_path)
        server = None
        thread = None
        try:
            server = make_server(store, 0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            exercise(Client(f"http://127.0.0.1:{server.server_port}"), report)
        finally:
            if server is not None:
                if thread is not None:
                    server.shutdown()
                server.server_close()
            if thread is not None:
                thread.join(timeout=10)
            store.db.close()
        restarted = ComparisonStore(root=ROOT, app_path=app_path)
        try:
            require(restarted.active == {"pc": DEFAULT_VERSION, "mobile": DEFAULT_VERSION},
                    "Restored versions did not persist across store restart")
            passed(report, "Restored research selection survives restart")
        finally:
            restarted.db.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Optional JSON verification report")
    args = parser.parse_args()
    output = args.output.resolve() if args.output else None
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "kind": "packaged_demo_http_smoke", "passed": False,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "program_root": str(ROOT), "python_executable": sys.executable,
        "python_version": platform.python_version(), "python_prefix": sys.prefix,
        "os": platform.platform(), "architecture": platform.machine(),
        "fresh_machine": False, "browser_ui_test": False,
        "environment_creation_verified_by_this_script": False,
        "application_state": "Disposable temporary directory; existing imports are not used",
        "limitations": [
            "This verifies local HTTP behaviour only, not browser layout or user benefit.",
            "This does not establish another physical computer or clean OS installation.",
            "Environment installation/download checks must be recorded separately.",
        ],
        "checks": [],
    }
    started = time.monotonic()
    try:
        run(report, output.parent if output else None)
        report["passed"] = True
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
        print("FAIL: " + report["error"], file=sys.stderr, flush=True)
    report["elapsed_seconds"] = round(time.monotonic() - started, 2)
    report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    if output:
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                          encoding="utf-8")
        print(f"Verification report: {output}", flush=True)
    print(f"{'PASS' if report['passed'] else 'FAIL'}: {len(report['checks'])} completed check groups. "
          "This is not a second-computer or browser certification.", flush=True)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
