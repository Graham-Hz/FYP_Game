"""Optional UI smoke test using a separate, headless system Edge session.

Run on Windows: uv run --locked --with playwright python.exe tests/check_demo_browser.py
Screenshots and downloaded aggregates go to the ignored data/processed/demo_qa directory.
"""
import json
import sys
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/demo"))
from server import ComparisonStore, make_server


def main():
    output = ROOT / "data/processed/demo_qa"
    output.mkdir(parents=True, exist_ok=True)
    store = ComparisonStore()
    server = make_server(store, 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    errors, checks = [], []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel="msedge", headless=True)
            page = browser.new_page(viewport={"width": 1365, "height": 1000}, device_scale_factor=1)
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(f"http://127.0.0.1:{server.server_port}/")
            expect(page.locator("#denominator")).to_have_text("51,152 筆訓練樣本")
            page.locator("#a-genre").select_option("Action")
            page.locator("#b-genre").select_option("Adventure")
            page.locator("#compare").click()
            expect(page.locator("#results")).to_be_visible()
            expected = store.compare({"platform": "pc", "a": {"genre": "Action"}, "b": {"genre": "Adventure"}})
            for index, key in enumerate(("a", "b")):
                expect(page.locator(".metric").nth(index)).to_contain_text(f"{expected['scenarios'][key]['total']:,}")
            page.screenshot(path=str(output / "steam-desktop.png"), full_page=True)
            checks.append("Steam scenario results equal independent server invocation")
            with page.expect_download() as download_event:
                page.locator("#export").click()
            download_event.value.save_as(str(output / "export.json"))
            exported = json.loads((output / "export.json").read_text(encoding="utf-8"))
            assert exported["scenarios"] == expected["scenarios"]
            assert exported["partition"] == "train"
            assert exported["analysis_manifest_sha256"] == expected["analysis_manifest_sha256"]
            checks.append("Downloaded aggregate counts, filters and provenance match displayed query")
            page.locator("#a-genre").select_option("Indie")
            expect(page.locator("#results")).to_be_hidden()
            checks.append("Changing a filter hides stale results and export")
            page.locator('[data-platform="mobile"]').click()
            expect(page.locator("#denominator")).to_have_text("221,806 筆訓練樣本")
            page.locator("#a-free").select_option("unknown")
            page.locator("#b-free").select_option("false")
            page.locator("#compare").click()
            expect(page.locator(".sample-warning")).to_contain_text("小樣本")
            expect(page.locator("#overlap")).to_contain_text("共有 0 筆")
            checks.append("Android unknown Free remains distinct from false, with small-sample warning")
            page.locator("#a-category").select_option("Casino")
            page.locator("#compare").click()
            expect(page.locator(".sample-warning")).to_contain_text("沒有符合")
            expect(page.locator(".result-card").first.locator(".tier-heading strong").first).to_have_text("—")
            checks.append("No matches show no percentages")
            page.locator('[data-reset="a"]').click()
            expect(page.locator("#results")).to_be_hidden()
            expect(page.locator("#a-free")).to_have_value("")
            page.locator("#a-category").select_option("Puzzle")
            page.locator("#b-category").select_option("Action")
            page.locator("#b-free").select_option("true")
            page.locator("#compare").click()
            expect(page.locator("#results")).to_be_visible()
            page.screenshot(path=str(output / "android-desktop.png"), full_page=True)
            page.set_viewport_size({"width": 390, "height": 844})
            page.screenshot(path=str(output / "android-mobile.png"), full_page=True)
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            checks.append("390px layout has no horizontal overflow")
            # A delayed request from the old platform must never replace the new view.
            held = []
            page.route("**/api/compare", lambda route: held.append(route))
            page.locator("#compare").click()
            page.wait_for_timeout(100)
            assert held
            page.locator('[data-platform="pc"]').click()
            held[0].fulfill(status=200, content_type="application/json", body=json.dumps(expected))
            page.wait_for_timeout(100)
            expect(page.locator("#results")).to_be_hidden()
            expect(page.locator("#denominator")).to_have_text("51,152 筆訓練樣本")
            checks.append("Late responses after a platform switch do not display stale results")
            assert not errors, errors
            checks.append("No uncaught browser JavaScript errors")
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
        store.db.close()
    (output / "browser_checks.json").write_text(json.dumps({"status": "passed", "checks": checks}, indent=2), encoding="utf-8")
    print(json.dumps({"status": "passed", "checks": checks}, indent=2))


if __name__ == "__main__":
    main()
