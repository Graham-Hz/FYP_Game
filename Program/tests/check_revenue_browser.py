"""Headless Edge checks of revenue filters, export, stale results and layout."""
import json
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/demo"))
from server import make_server


def main():
    output = ROOT / "data/processed/revenue_qa"
    output.mkdir(parents=True, exist_ok=True)
    server = make_server(SimpleNamespace(root=ROOT), 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    errors = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel="msedge", headless=True)
            page = browser.new_page(viewport={"width": 1365, "height": 1000})
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(f"http://127.0.0.1:{server.server_port}/revenue")
            expect(page.locator("#r-results")).to_be_visible()
            expect(page.locator("#r-metrics")).to_contain_text("1,415")
            expect(page.locator("#r-metrics")).to_contain_text("$105,087")
            page.screenshot(path=str(output / "desktop.png"), full_page=True)
            page.locator("#r-next").click()
            expect(page.locator("#r-page")).to_contain_text("2 / 57")
            page.locator("#r-sort").select_option("price")
            expect(page.locator("#r-page")).to_contain_text("1 / 57")
            page.locator("#r-mode").select_option("zero")
            expect(page.locator("#r-results")).to_be_hidden()
            page.locator("#r-apply").click()
            expect(page.locator("#r-metrics")).to_contain_text("85")
            with page.expect_download() as event:
                page.locator("#r-export").click()
            event.value.save_as(str(output / "export.json"))
            export = json.loads((output / "export.json").read_text(encoding="utf-8"))
            assert export["summary"]["count"] == 85 and export["filters"]["mode"] == "zero"
            assert all(r["price"] == 0 for r in export["rows"])
            assert export["metadata"]["source_sha256"]
            page.locator("#r-search").fill("zzzz-no-game-match-zzzz")
            page.locator("#r-apply").click()
            expect(page.locator("#r-warning")).to_contain_text("沒有符合")
            expect(page.locator(".revenue-value").nth(1)).to_have_text("—")
            page.locator("#r-reset").click()
            expect(page.locator("#r-metrics")).to_contain_text("1,415")
            page.locator("#r-genre").select_option("Action")
            page.locator("#r-publisher").select_option("Indie")
            page.locator("#r-apply").click()
            expect(page.locator("#r-context")).to_contain_text("Action · Indie")
            page.locator("#reference-panel summary").click()
            page.locator("#ref-submit").click()
            expect(page.locator("#ref-results")).to_be_visible()
            expect(page.locator("#ref-table tbody tr")).to_have_count(10)
            with page.expect_download() as reference_event:
                page.locator("#ref-export").click()
            reference_event.value.save_as(str(output / "references-export.json"))
            references = json.loads((output / "references-export.json").read_text(encoding="utf-8"))
            assert references["request"]["genres"] == ["Action"]
            assert references["returned_count"] == 10
            assert references["method"]["ranking_inputs"] == ["gameplay genres", "observed price", "Steam ID for ties"]
            assert all("Action" in r["match"]["shared_genres"] for r in references["rows"])
            page.locator("#reference-panel").screenshot(path=str(output / "references-desktop.png"))
            page.locator("#ref-price").fill("0")
            expect(page.locator("#ref-results")).to_be_hidden()
            expect(page.locator("#ref-factor")).to_be_disabled()
            page.locator("#ref-submit").click()
            expect(page.locator("#ref-context")).to_contain_text("只比較零價格作品")
            page.locator("#ref-price").fill("1000")
            page.locator("#ref-submit").click()
            expect(page.locator("#ref-warning")).to_contain_text("沒有符合")
            page.locator('#ref-genres input[value="Action"]').uncheck()
            page.locator("#ref-submit").click()
            expect(page.locator("#ref-status")).to_contain_text("至少選擇")
            page.locator('#ref-genres input[value="Action"]').check()
            page.locator("#ref-price").fill("14.99")
            page.locator("#ref-submit").click()
            expect(page.locator("#ref-table tbody tr")).to_have_count(10)
            page.set_viewport_size({"width": 390, "height": 844})
            page.locator("#reference-panel").screenshot(path=str(output / "references-mobile.png"))
            page.screenshot(path=str(output / "mobile.png"), full_page=True)
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            ref_held = []
            page.route("**/api/references", lambda route: ref_held.append(route))
            page.locator("#ref-submit").click()
            page.wait_for_timeout(150)
            assert ref_held
            page.locator("#ref-price").fill("20")
            ref_held[0].fulfill(status=200, content_type="application/json", body=json.dumps(references))
            page.wait_for_timeout(150)
            expect(page.locator("#ref-results")).to_be_hidden()
            expect(page.locator("#r-context")).to_contain_text("Action · Indie")
            # A response arriving after filters changed must not reveal stale results.
            held = []
            page.route("**/api/revenue?*", lambda route: held.append(route))
            page.locator("#r-apply").click()
            page.wait_for_timeout(150)
            assert held
            page.locator("#r-mode").select_option("zero")
            held[0].fulfill(status=200, content_type="application/json", body=json.dumps(export))
            page.wait_for_timeout(150)
            expect(page.locator("#r-results")).to_be_hidden()
            assert not errors, errors
            browser.close()
    finally:
        server.shutdown(); server.server_close(); thread.join()
    (output / "verification.json").write_text(json.dumps({"status": "passed", "checks": ["default metrics", "pagination and sorting", "price/genre/publisher filters", "export provenance and rows", "empty results", "reset", "reference selection and method export", "zero-price reference separation", "empty reference results", "missing genre feedback", "independent analysis and reference filters", "390px overflow", "stale reference and analysis responses", "no JS errors"]}, indent=2))
    print("Revenue browser checks passed")


if __name__ == "__main__":
    main()
