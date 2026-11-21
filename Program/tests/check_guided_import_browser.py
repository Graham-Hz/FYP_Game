"""Guided import user workflow in a disposable repository, using real local APIs."""
import json
import sys
import tempfile
import threading
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/demo"))
from server import ComparisonStore, make_server


def main():
    output = ROOT / "data/application/qa/guided_import"
    output.mkdir(parents=True, exist_ok=True)
    errors, checks = [], []
    # Missing developers/dates/owners intentionally: exploration should remain usable.
    csv = b"Game ID,Game Name,Genre,Price,My Notes\nlocal-a,Alpha,Action,0,free sample\nlocal-b,Beta,RPG,12.5,paid sample\n"
    with tempfile.TemporaryDirectory() as folder:
        store = ComparisonStore(app_path=Path(folder))
        server = make_server(store, 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(channel="msedge", headless=True)
                page = browser.new_page(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
                page.on("pageerror", lambda error: errors.append(str(error)))
                base = f"http://127.0.0.1:{server.server_port}"
                page.goto(base + "/import")
                expect(page.locator('[data-shell-link="import"]')).to_have_attribute("aria-current", "page")
                page.locator("#guided-file").set_input_files({"name": "renamed_partial.csv", "mimeType": "text/csv", "buffer": csv})
                page.locator("#guided-source").fill("Synthetic guided browser fixture")
                page.locator("#guided-date").fill("2026-11-22")
                page.locator("#guided-kind").select_option("synthetic")
                page.locator("#guided-currency").fill("USD")
                page.locator("#inspect-csv").click()
                expect(page.locator("#mapping-fields")).to_be_visible()
                # Explicit choices also verify the complete mapping UI independently of aliases.
                for field, source in {"app_id": "Game ID", "title": "Game Name", "genres": "Genre", "price_observed": "Price"}.items():
                    page.locator(f"#map-{field}").select_option(source)
                page.locator("#format-list").select_option(";")
                expect(page.locator("#unmapped-columns")).to_contain_text("My Notes")
                page.locator("#save-profile").click()
                expect(page.locator("#profile-status")).to_contain_text("已保存在此瀏覽器")
                page.locator("#map-price_observed").select_option("")
                page.locator("#reuse-profile").click()
                expect(page.locator("#map-price_observed")).to_have_value("Price")
                expect(page.locator("#confirm-semantics")).not_to_be_checked()
                checks.append("Renamed fields and extras mapped explicitly; saved profile reuses mappings without confirming semantics")
                page.locator("#confirm-semantics").check()
                page.locator("#preview-guided").click()
                expect(page.locator("#guided-status")).to_contain_text("驗證通過", timeout=30000)
                expect(page.locator("#preview-counts")).to_contain_text("可用於市場探索")
                counts = page.locator(".import-count strong").all_text_contents()
                assert counts == ["2", "2", "0"], counts
                expect(page.locator("#readiness-table")).to_contain_text("資料不足")
                page.evaluate("window.scrollTo(0, 0)")
                page.screenshot(path=str(output / "guided-import-desktop.png"), full_page=True)
                page.set_viewport_size({"width": 390, "height": 844})
                expect(page.locator('.app-sidebar')).to_have_css('transform', 'matrix(1, 0, 0, 1, -303, 0)')
                page.evaluate("window.scrollTo(0, 0)")
                page.screenshot(path=str(output / "guided-import-mobile.png"), full_page=True)
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), "Mobile mapping overflow"
                page.set_viewport_size({"width": 1440, "height": 1000})
                page.locator("#guided-source").fill("Synthetic guided browser fixture edited")
                expect(page.locator("#save-guided")).to_be_disabled()
                expect(page.locator("#guided-preview")).to_be_hidden()
                expect(page.locator("#confirm-semantics")).not_to_be_checked()
                page.locator("#confirm-semantics").check()
                page.locator("#preview-guided").click()
                expect(page.locator("#guided-status")).to_contain_text("驗證通過", timeout=30000)
                checks.append("Partial records give 2 exploration / 0 comparison rows; metadata change invalidates preview and confirmation")
                with page.expect_download() as download:
                    page.locator("#download-validation").click()
                report_path = output / "validation.json"
                download.value.save_as(str(report_path))
                report = json.loads(report_path.read_text(encoding="utf-8"))
                assert report["exploration_rows"] == 2 and report["eligible_rows"] == 0
                page.locator("#save-guided").click()
                expect(page.locator("#guided-status")).to_contain_text("尚未啟用", timeout=30000)
                assert store.active["pc"] == "research_train_v1"
                page.locator("#activate-guided").click()
                expect(page.locator("#activation-status")).to_contain_text("已啟用", timeout=30000)
                assert store.active["pc"] != "research_train_v1"
                # Exercise actual chart rendering from the activated broad snapshot,
                # including missing-data states. No intercepted responses or fixtures.
                page.goto(base + "/market")
                expect(page.locator("#market-results")).to_be_visible(timeout=30000)
                expect(page.locator("#market-summary article strong").first).to_have_text("2")
                genre_chart = page.locator('article[data-chart-id="group_count"]')
                expect(genre_chart.locator("svg")).to_be_visible()
                expect(genre_chart.locator("svg")).to_contain_text("Action")
                expect(genre_chart.locator("svg")).to_contain_text("RPG")
                page.evaluate("window.scrollTo(0, 0)")
                page.screenshot(path=str(output / "guided-partial-market-overview.png"), full_page=True)
                page.locator('[data-market-section="distribution"]').click()
                page.locator("#market-chart-select").select_option("outcome_histogram")
                histogram = page.locator('article[data-chart-id="outcome_histogram"]')
                expect(histogram.locator("svg")).to_be_visible()
                expect(histogram).to_contain_text("觀測價格")
                expect(histogram).to_contain_text("USD")
                page.locator("#market-analysis-panel").screenshot(path=str(output / "guided-partial-market-prices.png"))
                page.locator('[data-market-section="cohorts"]').click()
                expect(page.locator('[data-market-section="cohorts"]')).to_have_attribute("data-availability", "unavailable")
                expect(page.locator("#market-charts .game-chart-readiness")).to_contain_text("發售日期")
                expect(page.locator("#market-charts svg")).to_have_count(0)
                page.locator("#market-analysis-panel").screenshot(path=str(output / "guided-partial-market-missing-dates.png"))
                page.locator("#market-view-records").click()
                expect(page.locator("#market-records-table")).to_be_visible()
                expect(page.locator("#market-records-table")).to_contain_text("Alpha")
                expect(page.locator("#market-records-table")).to_contain_text("Beta")
                expect(page.locator("#market-records-table tbody tr")).to_have_count(2)
                checks.append("Activated partial CSV renders real genre and price charts, marks missing-date charts unavailable, and retains both game records")
                page.locator('[data-shell-link="import"]').click()
                page.reload()
                expect(page.locator("#guided-active")).to_contain_text("Synthetic guided browser fixture edited")
                page.locator("#guided-version").select_option("research_train_v1")
                page.locator("#activate-guided").click()
                expect(page.locator("#activation-status")).to_contain_text("已啟用", timeout=30000)
                assert store.active["pc"] == "research_train_v1"
                checks.append("Export, save without activation, activation, reload and rollback succeed")
                page.locator("#guided-file").set_input_files({"name": "invalid_utf8.csv", "mimeType": "text/csv", "buffer": b"name\n\xff\n"})
                page.locator("#inspect-csv").click()
                expect(page.locator("#guided-status")).to_contain_text("不是有效 UTF-8")
                expect(page.locator("#mapping-fields")).to_be_hidden()
                checks.append("Invalid UTF-8 fails before inspection; previous preview cannot be reused")
                page.set_viewport_size({"width": 390, "height": 844})
                expect(page.locator('.app-sidebar')).to_have_css('transform', 'matrix(1, 0, 0, 1, -303, 0)')
                page.evaluate("window.scrollTo(0, 0)")
                page.screenshot(path=str(output / "guided-import-error-mobile.png"), full_page=True)
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), "Mobile overflow"
                assert not errors, errors
                checks.append("390px layout has no horizontal overflow and no browser JavaScript errors")
                browser.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
            store.db.close()
    report = {"status": "passed", "checks": checks, "page_errors": errors}
    (output / "browser_verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
