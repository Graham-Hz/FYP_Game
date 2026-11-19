"""Independent market analysis UI checks using real data and an isolated registry.

Run: uv run --locked --with playwright python -B tests/check_market_browser.py
Captures and exports are written to ignored data/processed/market_qa/.
Failure cases are browser-response fixtures, not changes to research data.
"""
import copy
import csv
import io
import json
import sys
import tempfile
import threading
import xml.etree.ElementTree as ET
from pathlib import Path

from playwright.sync_api import expect, sync_playwright
expect.set_options(timeout=15000)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/demo"))
from server import ComparisonStore, make_server


def main():
    output = ROOT / "data/processed/market_qa"
    output.mkdir(parents=True, exist_ok=True)
    checks, errors = [], []
    with tempfile.TemporaryDirectory(prefix="gamescope-market-qa-") as folder:
        store = ComparisonStore(app_path=Path(folder))
        server = make_server(store, 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(channel="msedge", headless=True)
                context = browser.new_context(viewport={"width": 1365, "height": 1000})
                page = context.new_page()
                page.set_default_timeout(45000)
                page.on("pageerror", lambda error: errors.append(str(error)))

                def options():
                    response = context.request.get(base + "/api/market/options")
                    assert response.ok, response.text()
                    return response.json()

                source_options = options()
                by_source = {source["id"]: source for source in source_options["sources"]}

                def query(source_id, **filters):
                    source = by_source[source_id]
                    payload = {
                        "source": source_id, "version_id": source["version_id"],
                        "group": "", "tag": "", "year_from": None, "year_to": None,
                        "top_n": 10, "rank_metric": source["rank_metrics"][0]["id"],
                        **filters,
                    }
                    response = context.request.post(base + "/api/market", data=payload)
                    assert response.ok, response.text()
                    return response.json()

                expected_pc = query("pc")
                assert len(expected_pc["charts"]) == 14
                page.goto(base + "/market")
                expect(page.locator("#market-results")).to_be_visible()
                expect(page.locator("#market-charts > article")).to_have_count(2)
                expect(page.locator("#market-source")).to_have_value("pc")
                count = store.db.execute("SELECT count(*) FROM pc").fetchone()[0]
                expect(page.locator("#market-summary")).to_contain_text(f"{count:,}")
                assert page.evaluate("sessionStorage.length") == 0
                assert page.locator("#market-source-links a").count() > 0
                assert not page.locator('#market-group option[value="Sexual Content"]').count()
                assert not page.locator('#market-group option[value="Indie"]').count()
                assert not page.locator('#market-group option[value="Accounting"]').count()
                assert page.locator('#market-tag optgroup[label="內容描述"] option[value="Sexual Content"]').count() == 1
                page.screenshot(path=str(output / "steam-desktop-top.png"), full_page=True)
                page.locator("#market-analysis-panel").screenshot(path=str(output / "steam-desktop-overview.png"))
                def show_chart(chart):
                    page.locator(f'#market-tab-{chart["section"]}').click()
                    actual = page.locator(f'article[data-chart-id="{chart["id"]}"]')
                    if not actual.count():
                        page.locator("#market-chart-select").select_option(chart["id"])
                    return page.locator(f'article[data-chart-id="{chart["id"]}"]')
                for chart in expected_pc["charts"]:
                    actual = show_chart(chart)
                    expect(actual.locator("figcaption")).to_have_text(chart["title"])
                    assert page.locator("#market-charts > article").count() <= 2
                    if chart["type"] in {"histogram", "boxplot", "scatter", "heatmap"}:
                        expect(actual.locator("svg")).to_be_visible()
                        actual.screenshot(path=str(output / f'steam-desktop-{chart["type"]}.png'))
                    if chart["id"] == "release_count":
                        actual.screenshot(path=str(output / "steam-desktop-cohorts.png"))
                first_chart = expected_pc["charts"][0]
                show_chart(first_chart)
                assert page.locator("#market-charts .game-chart-viewport").first.evaluate("node => node.scrollWidth <= node.clientWidth")
                page.locator("#market-charts > article").first.screenshot(path=str(output / "steam-desktop-chart.png"))
                checks.append("Fourteen real chart configurations are accessible through five tabs, with only one or two plots shown and gameplay separated from other tags")

                with page.expect_download() as event:
                    page.locator("#market-export-json").click()
                event.value.save_as(str(output / "steam-analysis.json"))
                exported = json.loads((output / "steam-analysis.json").read_text(encoding="utf-8"))
                for key in ("charts", "summary", "filters", "source", "provenance"):
                    assert exported[key] == expected_pc[key], key
                assert exported["provenance"]
                with page.expect_download() as event:
                    page.locator("#market-export-csv").click()
                event.value.save_as(str(output / "steam-chart-data.csv"))
                csv_bytes = (output / "steam-chart-data.csv").read_bytes()
                assert csv_bytes.startswith(b"\xef\xbb\xbf")
                records = list(csv.DictReader(io.StringIO(csv_bytes.decode("utf-8-sig"))))
                assert records[0]["record_type"] == "analysis_metadata"
                assert records[0]["source_version"] == expected_pc["source"]["version_id"]
                assert json.loads(records[0]["provenance_json"]) == expected_pc["provenance"]
                assert sum(record["record_type"] == "chart_metadata" for record in records) == 14
                first_record = next(record for record in records if record["record_type"] == "chart_value" and record["chart_id"] == first_chart["id"])
                assert first_record["chart_id"] == first_chart["id"]
                assert first_record["group"] == first_chart["rows"][0]["label"]
                assert float(first_record["value"]) == first_chart["rows"][0]["values"][0]
                scatter = next(chart for chart in expected_pc["charts"] if chart["type"] == "scatter")
                points = [record for record in records if record["record_type"] == "scatter_point"]
                assert len(points) == len(scatter["points"])
                assert float(points[0]["x"]) == scatter["points"][0]["x"]
                assert float(points[0]["y"]) == scatter["points"][0]["y"]
                histogram = next(chart for chart in expected_pc["charts"] if chart["type"] == "histogram")
                bins = [record for record in records if record["record_type"] == "histogram_bin"]
                assert len(bins) == len(histogram["rows"])
                assert float(bins[0]["lower"]) == histogram["rows"][0]["lower"]
                boxplot = next(chart for chart in expected_pc["charts"] if chart["type"] == "boxplot")
                assert sum(record["record_type"] == "box_summary" for record in records) == 5 * len(boxplot["rows"])
                with page.expect_download() as event:
                    page.locator("#market-charts .game-chart-actions button").first.click()
                event.value.save_as(str(output / "steam-chart.svg"))
                svg = ET.fromstring((output / "steam-chart.svg").read_bytes())
                assert svg.tag == "{http://www.w3.org/2000/svg}svg"
                assert svg.find("{http://www.w3.org/2000/svg}title").text == first_chart["title"]
                svg_text = " ".join(svg.itertext())
                assert expected_pc["source"]["snapshot"] in svg_text
                assert not any(node.tag.endswith("image") or node.tag.endswith("script") for node in svg.iter())
                checks.append("Whole-analysis JSON and typed BOM CSV preserve all charts including raw scatter coordinates, bins, box statistics and source evidence; SVG is self-contained")

                # A content description is its own filter, never a gameplay genre.
                page.locator("#market-tag").select_option("Sexual Content")
                page.locator("#market-apply").click()
                expect(page.locator("#market-results")).to_be_visible()
                sexual = query("pc", tag="Sexual Content")
                assert sexual["summary"][0]["value"] == 61
                expect(page.locator("#market-summary")).to_contain_text("61")
                page.locator("#market-analysis-panel").screenshot(path=str(output / "sexual-content-tag-desktop.png"))
                assert all(row["label"] in by_source["pc"]["groups"] for row in sexual["charts"][0]["rows"])
                page.locator("#market-group").select_option("Action")
                page.locator("#market-apply").click()
                expect(page.locator("#market-results")).to_be_visible()
                combined = query("pc", tag="Sexual Content", group="Action")
                expect(page.locator("#market-summary")).to_contain_text(f'{combined["summary"][0]["value"]:,}')
                expect(page.locator("#market-result-context")).to_contain_text("Sexual Content")
                page.locator("#market-reset").click()
                expect(page.locator("#market-results")).to_be_visible()
                drill = page.locator('article[data-chart-id="group_count"] rect[role="button"]').first
                label = first_chart["rows"][0]["filter"]["group"]
                drill.click()
                expect(page.locator("#market-group")).to_have_value(label)
                expect(page.locator("#market-results")).to_be_visible()
                page.locator("#market-reset").click()
                expect(page.locator("#market-results")).to_be_visible()
                checks.append("Sexual Content filters 61 records separately from gameplay; genre and tag combine with AND, and genre bars support exact-filter drill-down")

                chart = show_chart(scatter)
                expect(chart.locator('.game-chart-statistics')).to_contain_text(f"{scatter['summary']['spearman_rho']:.4f}")
                chart.locator('circle[role="button"]').first.focus()
                chart.locator('circle[role="button"]').first.press("Enter")
                expect(page.locator("#market-point-detail")).to_be_visible()
                expect(page.locator("#market-point-detail")).to_contain_text(scatter["points"][0]["label"])
                chart.locator('.game-chart-scale select').select_option("linear")
                expect(chart.locator('.game-chart-scale select')).to_have_value("linear")
                page.locator("#market-analysis-panel").screenshot(path=str(output / "scatter-selection-linear.png"))
                checks.append("Scatter marks expose original records and scale switching changes the drawing without changing raw values")
                show_chart(first_chart)

                page.locator("#market-group").select_option("Action")
                expect(page.locator("#market-results")).to_be_hidden()
                expect(page.locator("#market-export-json")).to_be_disabled()
                page.locator("#market-advanced-filters > summary").click()
                page.locator("#market-year-from").fill("2020")
                page.locator("#market-year-to").fill("2024")
                page.locator("#market-apply").click()
                expect(page.locator("#market-results")).to_be_visible()
                filtered = query("pc", group="Action", year_from=2020, year_to=2024)
                expect(page.locator("#market-result-context")).to_contain_text("2020–2024")
                for metric in filtered["summary"]:
                    if isinstance(metric["value"], int):
                        expect(page.locator("#market-summary")).to_contain_text(f'{metric["value"]:,}')
                checks.append("Type/year filters hide stale results and recompute the matching cohort")

                page.locator("#market-source").select_option("mobile")
                expect(page.locator("#market-results")).to_be_visible()
                expect(page.locator("#market-result-context")).to_contain_text(by_source["mobile"]["name"])
                mobile_count = store.db.execute("SELECT count(*) FROM mobile").fetchone()[0]
                expect(page.locator("#market-summary")).to_contain_text(f"{mobile_count:,}")
                expect(page.locator("#market-group")).to_have_value("")
                expect(page.locator("#market-tag-label")).to_be_hidden()
                page.locator("#market-source").select_option("revenue")
                expect(page.locator("#market-result-context")).to_contain_text(by_source["revenue"]["name"])
                expect(page.locator("#market-source-snapshot")).to_contain_text("2024")
                page.locator("#market-rank").select_option("revenue")
                expect(page.locator("#market-results")).to_be_hidden()
                page.locator("#market-apply").click()
                expect(page.locator("#market-results")).to_be_visible()
                revenue = query("revenue", rank_metric="revenue")
                page.locator("#market-tab-rankings").click()
                expect(page.locator("#market-leaders-title")).to_have_text(revenue["leaders"]["title"])
                checks.append("Android and separate revenue sources switch with their own dates, metrics and denominators")

                # These requests really reach the server, unlike the delayed-response fixture below.
                page.locator("#market-source").select_option("mobile")
                page.locator("#market-source").select_option("revenue")
                page.locator("#market-source").select_option("pc")
                expect(page.locator("#market-results")).to_be_visible()
                expect(page.locator("#market-result-context")).to_contain_text(by_source["pc"]["name"])
                expect(page.locator("#market-summary")).to_contain_text(f"{count:,}")
                checks.append("Rapid real source changes settle on the final selection without upload-gate errors or stale rendering")

                # A deterministic response fixture exercises empty rendering without changing data.
                empty = copy.deepcopy(expected_pc)
                empty.update(empty=True, charts=[], summary=[], leaders={"title": "No matches", "columns": [], "rows": []})
                page.route("**/api/market", lambda route: route.fulfill(json=empty))
                page.locator("#market-apply").click()
                expect(page.locator("#market-empty")).to_be_visible()
                expect(page.locator("#market-charts > article")).to_have_count(0)
                expect(page.locator("#market-export-csv")).to_be_disabled()
                page.unroute("**/api/market")
                page.locator("#market-reset").click()
                expect(page.locator("#market-charts > article")).to_have_count(2)
                checks.append("Empty response is explained without fabricated zero charts")

                held = []
                def delayed(route):
                    if route.request.post_data_json["source"] == "pc":
                        held.append(route)
                    else:
                        route.continue_()
                page.route("**/api/market", delayed)
                page.locator("#market-apply").click()
                page.wait_for_timeout(100)
                assert held
                page.locator("#market-source").select_option("mobile")
                held[0].fulfill(json=expected_pc)
                expect(page.locator("#market-results")).to_be_visible()
                expect(page.locator("#market-result-context")).to_contain_text(by_source["mobile"]["name"])
                expect(page.locator("#market-summary")).to_contain_text(f"{mobile_count:,}")
                page.unroute("**/api/market")
                checks.append("Delayed response from a previously selected source cannot overwrite the new view")

                page.route("**/api/market", lambda route: route.fulfill(status=400, json={"error": "資料版本已改變，請重新讀取資料版本。"}))
                page.locator("#market-apply").click()
                expect(page.locator("#market-status")).to_contain_text("資料版本已改變")
                expect(page.locator("#market-results")).to_be_hidden()
                expect(page.locator("#market-export-json")).to_be_disabled()
                page.unroute("**/api/market")
                bad_version = copy.deepcopy(expected_pc)
                bad_version["source"]["version_id"] = "qa-mismatched-version"
                page.route("**/api/market", lambda route: route.fulfill(json=bad_version))
                page.locator("#market-source").select_option("pc")
                expect(page.locator("#market-status")).to_contain_text("資料版本已改變")
                expect(page.locator("#market-results")).to_be_hidden()
                page.unroute("**/api/market")
                checks.append("API version errors and mismatched successful payloads block stale results and export")

                unavailable = copy.deepcopy(source_options)
                next(item for item in unavailable["sources"] if item["id"] == "revenue").update(available=False, description="QA unavailable source")
                page.route("**/api/market/options", lambda route: route.fulfill(json=unavailable))
                page.locator("#market-refresh").click()
                expect(page.locator("#market-results")).to_be_visible()
                page.locator("#market-source").select_option("revenue")
                expect(page.locator("#market-status")).to_contain_text("QA unavailable source")
                expect(page.locator("#market-apply")).to_be_disabled()
                expect(page.locator("#market-results")).to_be_hidden()
                page.locator("#market-source").select_option("pc")
                expect(page.locator("#market-results")).to_be_visible()
                page.unroute("**/api/market/options")
                checks.append("Unavailable source remains explicit while independent sources still work")

                synthetic = copy.deepcopy(source_options)
                next(item for item in synthetic["sources"] if item["id"] == "pc")["data_kind"] = "synthetic"
                page.route("**/api/market/options", lambda route: route.fulfill(json=synthetic))
                page.locator("#market-refresh").click()
                expect(page.locator("#market-data-kind")).to_be_visible()
                expect(page.locator("#market-data-kind")).to_contain_text("不代表市場")
                page.unroute("**/api/market/options")
                page.locator("#market-refresh").click()
                expect(page.locator("#market-data-kind")).to_be_hidden()
                checks.append("Synthetic source metadata is prominently labelled rather than silently presented as market evidence")

                page.set_viewport_size({"width": 390, "height": 844})
                page.locator("#market-reset").click()
                expect(page.locator("#market-results")).to_be_visible()
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                page.evaluate("scrollTo(0,0)")
                page.screenshot(path=str(output / "steam-mobile-top.png"), full_page=True)
                page.locator("#market-charts > article").first.screenshot(path=str(output / "steam-mobile-chart.png"))
                show_chart(histogram).screenshot(path=str(output / "steam-mobile-histogram.png"))
                show_chart(scatter).screenshot(path=str(output / "steam-mobile-scatter.png"))
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                assert not errors, errors
                checks.append("390px page has no horizontal overflow; chart scrolling is contained and no JavaScript errors occur")
                browser.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
            store.db.close()
    record = {"status": "passed", "checks": checks, "page_errors": errors,
              "note": "Automated UI/data checks; not a human usability evaluation."}
    (output / "verification.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
