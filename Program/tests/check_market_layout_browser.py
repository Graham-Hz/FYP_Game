"""Compact market pages retain shared scope, chart access and honest status.

Run: uv run --offline --locked --with playwright python -B tests/check_market_layout_browser.py
Uses the actual historical API with an isolated registry. A single explicit
500-response fixture checks recovery; research data and saved versions stay intact.
"""
import json
from pathlib import Path
import sys
import tempfile
import threading
import xml.etree.ElementTree as ET

from playwright.sync_api import expect, sync_playwright
from market_browser_controls import market_control

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/demo"))
from server import ComparisonStore, make_server


def main():
    output = ROOT / "data/processed/market_layout_qa"
    output.mkdir(parents=True, exist_ok=True)
    checks, errors, geometry = [], [], {}
    report = {"passed": False, "checks": checks, "page_errors": errors, "geometry": geometry}
    with tempfile.TemporaryDirectory(prefix="market-layout-") as folder:
        store = ComparisonStore(app_path=Path(folder))
        server = make_server(store, 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(channel="msedge", headless=True)
                try:
                    context = browser.new_context(viewport={"width": 1365, "height": 1000}, accept_downloads=True)
                    page = context.new_page()
                    page.set_default_timeout(45000)
                    expect.set_options(timeout=45000)
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    requests = []
                    page.on("request", lambda request: requests.append(request.post_data_json)
                            if request.url == base + "/api/market" and request.method == "POST" else None)
                    page.goto(base + "/market", wait_until="networkidle")
                    expect(page.locator("#market-results")).to_be_visible()
                    assert not page.locator("#market-filter-panel").evaluate("node => node.open")
                    expect(page.locator("#market-form")).to_be_hidden()
                    expect(page.locator("#market-result-context")).to_be_visible()
                    expect(page.locator("#market-result-context")).to_contain_text("51,152")
                    expect(page.locator("#market-scope-source")).to_contain_text("2025-03")
                    page.locator("#market-filter-toggle").focus()
                    page.locator("#market-filter-toggle").press("Enter")
                    expect(page.locator("#market-form")).to_be_visible()
                    page.locator("#market-filter-toggle").press("Enter")
                    expect(page.locator("#market-form")).to_be_hidden()
                    initial_requests = len(requests)
                    titles = []
                    for section in ["overview", "distribution", "relationships", "cohorts", "rankings"]:
                        page.locator(f'a[data-market-section="{section}"]').click()
                        expect(page.locator(f'a[data-market-section="{section}"]')).to_have_attribute("aria-current", "page")
                        expect(page.locator("h1#market-section-title")).to_be_visible()
                        titles.append(page.locator("h1#market-section-title").inner_text())
                        expect(page.locator("#market-filter-panel")).not_to_have_attribute("open", "")
                        if section == "overview":
                            expect(page.locator("#market-summary")).to_be_visible()
                        else:
                            expect(page.locator("#market-summary")).to_be_hidden()
                        expect(page.locator("#market-export-json")).to_be_visible()
                        expect(page.locator("#market-export-csv")).to_be_visible()
                        page.evaluate("window.scrollTo(0, 0)")
                        first_chart = page.locator("#market-charts > article").first
                        expect(first_chart).to_be_visible()
                        box = first_chart.bounding_box()
                        svg_top = first_chart.locator("svg").bounding_box()["y"]
                        geometry[section] = {"first_chart_top": box["y"], "first_svg_top": svg_top, "height": box["height"]}
                        assert box["y"] < (640 if section == "overview" else 520), geometry
                        assert svg_top < 800, geometry
                        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                        page.screenshot(path=str(output / f"{section}-desktop.png"), animations="disabled")
                    assert len(set(titles)) == 5, titles
                    assert not any("探索遊戲市場資料" in title for title in titles)
                    assert len(requests) == initial_requests, "Section changes unexpectedly re-ran the same analysis"
                    checks.append("Five section-specific headings replace the shared hero; only overview shows KPI cards; collapsed filters retain visible source/date/sample scope and all plots start in the first desktop viewport without re-querying data.")

                    # Compact warnings still disclose the complete limitation and
                    # preserve it in the portable SVG, even while collapsed.
                    limited = page.locator("#market-charts details.game-chart-readiness-compact").first
                    expect(limited).not_to_have_attribute("open", "")
                    expect(limited.locator(":scope > summary")).to_contain_text("資料有局限")
                    expect(limited.locator(":scope > p").first).to_be_hidden()
                    limited.locator(":scope > summary").focus()
                    limited.locator(":scope > summary").press("Enter")
                    expect(limited.locator(":scope > p").first).to_be_visible()
                    limited.locator(":scope > details > summary").click()
                    expect(limited.locator("ul")).to_be_visible()
                    reason = limited.locator(":scope > p").first.inner_text()
                    limited.locator(":scope > summary").click()
                    with page.expect_download() as event:
                        page.locator("#market-charts .game-chart-actions button").first.click()
                    svg_path = output / "compact-limited-chart.svg"
                    event.value.save_as(str(svg_path))
                    svg = ET.fromstring(svg_path.read_bytes())
                    metadata = json.loads(svg.find("{http://www.w3.org/2000/svg}metadata").text)
                    assert metadata["availability"]["reason"] == reason
                    svg_text = "".join("".join(svg.itertext()).split())
                    assert "".join(reason.split()) in svg_text
                    assert "".join(metadata["availability"]["action"].split()) in svg_text
                    checks.append("Keyboard-operable filter and limited-data disclosures retain readable reasons/requirements; the collapsed chart's SVG still contains the exact reason, action and metadata.")

                    # Direct entry and browser history select the correct section title.
                    page.goto(base + "/market#relationships", wait_until="networkidle")
                    expect(page.locator("#market-section-title")).to_contain_text("關聯")
                    page.locator('a[data-market-section="cohorts"]').click()
                    expect(page.locator("#market-section-title")).to_contain_text("發售")
                    page.go_back()
                    expect(page.locator("#market-section-title")).to_contain_text("關聯")
                    page.go_forward()
                    expect(page.locator("#market-section-title")).to_contain_text("發售")
                    checks.append("Direct section URLs and back/forward show the matching heading and selected sidebar entry.")

                    # Shared controls remain usable without any programmatic opening.
                    market_control(page, "#market-source").select_option("mobile")
                    expect(page.locator("#market-results")).to_be_visible()
                    market_control(page, "#market-group").select_option("Adventure")
                    market_control(page, "#market-year-from").fill("2018")
                    market_control(page, "#market-year-to").fill("2019")
                    market_control(page, "#market-apply").click()
                    expect(page.locator("#market-results")).to_be_visible()
                    expect(page.locator("#market-filter-panel")).to_have_attribute("open", "")
                    page.locator("#market-filter-toggle").click()
                    expect(page.locator("#market-form")).to_be_hidden()
                    expect(page.locator("#market-result-context")).to_contain_text("Adventure")
                    expect(page.locator("#market-result-context")).to_contain_text("2018")
                    expect(page.locator("#market-result-context")).to_contain_text("2019")
                    expect(page.locator("#market-scope-source")).to_contain_text("Android")
                    applied = requests[-1].copy()
                    count_requests = len(requests)
                    page.locator('a[data-market-section="rankings"]').click()
                    page.locator('a[data-market-section="distribution"]').click()
                    assert len(requests) == count_requests
                    expect(page.locator("#market-source")).to_have_value("mobile")
                    expect(page.locator("#market-group")).to_have_value("Adventure")
                    expect(page.locator("#market-year-from")).to_have_value("2018")
                    expect(page.locator("#market-year-to")).to_have_value("2019")
                    expect(page.locator("#market-form")).to_be_hidden()
                    page.evaluate("window.scrollTo(0, 0)")
                    page.screenshot(path=str(output / "filtered-distribution-desktop.png"), animations="disabled")
                    with page.expect_download() as event:
                        page.locator("#market-export-json").click()
                    export_path = output / "filtered-analysis.json"
                    event.value.save_as(str(export_path))
                    exported = json.loads(export_path.read_text(encoding="utf-8"))
                    assert exported["filters"]["group"] == applied["group"]
                    assert exported["filters"]["year_from"] == 2018 and exported["filters"]["year_to"] == 2019
                    page.locator("#market-view-records").click()
                    expect(page.locator("#market-records-table")).to_be_visible()
                    expect(page.locator("#market-records-context")).to_contain_text("Android")
                    page.locator("#market-records-close").click()
                    checks.append("User-opened filters stay open during edits; closing preserves Android/Adventure/year scope across sections, and visible export/record actions use those exact applied filters.")

                    # A hidden filter drawer must not hide a pending or failed analysis.
                    market_control(page, "#market-group").select_option("Puzzle")
                    page.locator("#market-filter-toggle").click()
                    expect(page.locator("#market-results")).to_be_hidden()
                    expect(page.locator("#market-status")).to_be_visible()
                    expect(page.locator("#market-status")).to_contain_text("條件已更改")
                    expect(page.locator("#market-export-json")).to_be_disabled()
                    page.screenshot(path=str(output / "pending-closed-filters.png"), animations="disabled")
                    page.route("**/api/market", lambda route: route.fulfill(status=500, json={"error": "Layout QA simulated failure"}))
                    market_control(page, "#market-apply").click()
                    expect(page.locator("#market-status")).to_contain_text("Layout QA simulated failure")
                    page.locator("#market-filter-toggle").click()
                    expect(page.locator("#market-status")).to_be_visible()
                    expect(page.locator("#market-results")).to_be_hidden()
                    page.unroute("**/api/market")
                    market_control(page, "#market-apply").click()
                    expect(page.locator("#market-results")).to_be_visible()
                    page.locator("#market-filter-toggle").click()
                    checks.append("Pending conditions and an explicit simulated server error remain visible while controls are collapsed; stale results/exports stay unavailable, and a real retry recovers.")

                    page.set_viewport_size({"width": 390, "height": 844})
                    page.evaluate("window.scrollTo(0, 0)")
                    expect(page.locator("#market-filter-toggle")).to_be_visible()
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                    page.screenshot(path=str(output / "distribution-mobile.png"), animations="disabled")
                    page.locator(".app-menu-toggle").click()
                    page.locator('a[data-market-section="rankings"]').click()
                    expect(page.locator(".app-menu-toggle")).to_have_attribute("aria-expanded", "false")
                    expect(page.locator("#market-summary")).to_be_hidden()
                    market_control(page, "#market-group")
                    expect(page.locator("#market-group")).to_be_visible()
                    expect(page.locator("#market-group")).to_have_value("Puzzle")
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                    page.locator("#market-filter-toggle").click()
                    page.evaluate("window.scrollTo(0, 0)")
                    page.screenshot(path=str(output / "rankings-mobile.png"), animations="disabled")
                    checks.append("390px layout keeps scope and controls readable without horizontal overflow; sidebar navigation and expanding/collapsing filters preserve the selected data.")
                    assert not errors, errors
                    report["passed"] = True
                finally:
                    browser.close()
        except Exception as exc:
            report["error"] = f"{type(exc).__name__}: {exc}"
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()
            store.db.close()
    (output / "verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
