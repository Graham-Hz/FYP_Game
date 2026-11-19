"""Focused browser checks for cross-page labels and saved-reference method changes."""
import json
from pathlib import Path
import sys
import tempfile
import threading

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/demo"))
from server import ComparisonStore, make_server
from analysis.game_taxonomy import GAMEPLAY_GENRES


def main():
    output = ROOT / "data/processed/taxonomy_qa"
    output.mkdir(parents=True, exist_ok=True)
    errors, checks = [], []
    with tempfile.TemporaryDirectory(prefix="taxonomy-browser-") as state_directory:
        store = ComparisonStore(app_path=Path(state_directory))
        server = make_server(store, 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(channel="msedge", headless=True)
                context = browser.new_context(viewport={"width": 1440, "height": 1000})
                page = context.new_page()
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(base)
                expect(page.locator("#a-genre")).to_be_visible()
                genres = page.locator("#a-genre option").evaluate_all("nodes => nodes.map(n => n.value).filter(Boolean)")
                assert set(genres) == GAMEPLAY_GENRES, genres
                tags = page.locator("#a-source_tag option").evaluate_all("nodes => nodes.map(n => n.value).filter(Boolean)")
                assert "Indie" in tags and "Massively Multiplayer" in tags
                assert not (set(tags) & GAMEPLAY_GENRES)
                expect(page.locator('#a-source_tag optgroup[label="製作／發行標籤"] option[value="Indie"]')).to_have_count(1)
                page.locator("#a-genre").select_option("Action")
                page.locator("#a-source_tag").select_option("Indie")
                page.locator("#b-genre").select_option("RPG")
                page.locator("#compare").click()
                expect(page.locator("#results")).to_be_visible()
                expect(page.locator("#result-cards")).to_contain_text("其他來源標籤：Indie")
                page.screenshot(path=str(output / "comparison-taxonomy.png"), full_page=True)
                checks.append("Comparison offers eight gameplay genres separately from grouped source labels; Action AND Indie works.")

                page.locator('[data-plan-choice="a"]').click()
                expect(page).to_have_url(base + "/revenue#reference-panel")
                expect(page.locator("#r-results")).to_be_visible()
                references = page.locator("#ref-genres input").evaluate_all("nodes => nodes.map(n => n.value)")
                assert set(references) == GAMEPLAY_GENRES, references
                expect(page.locator('#r-genre optgroup[label="玩法類型"] option[value="Action"]')).to_have_count(1)
                expect(page.locator('#r-genre optgroup[label="製作／發行標籤"] option[value="Indie"]')).to_have_count(1)
                page.locator("#r-genre").select_option("Indie")
                page.locator("#r-apply").click()
                expect(page.locator("#r-context")).to_contain_text("正價格 · Indie")
                with page.expect_download() as event:
                    page.locator("#r-export").click()
                event.value.save_as(str(output / "source-indie-filter.json"))
                exported = json.loads((output / "source-indie-filter.json").read_text(encoding="utf-8"))
                assert exported["rows"] and all("Indie" in row["genres"] for row in exported["rows"])
                assert exported["filters"]["genre"] == "Indie"
                checks.append("Revenue source-label optgroups retain raw Indie filtering; reference selector uses exactly eight gameplay genres.")

                page.locator("#ref-price").fill("14.99")
                page.locator("#ref-submit").click()
                expect(page.locator("#ref-results")).to_be_visible()
                page.locator("[data-plan-game]").first.check()
                assert page.evaluate("PlanningFlow.read().references.evidence.method.version") == "genre_price_references_v2"
                page.locator("#ref-to-budget").click()
                expect(page.locator("#load-example")).to_be_enabled()
                page.locator("#load-example").click()
                page.locator("#calculate-budget").click()
                expect(page.locator("#budget-results")).to_be_visible()
                budget_before = page.evaluate("JSON.stringify(PlanningFlow.read().budget)")
                draft_before = page.evaluate("JSON.stringify(PlanningFlow.read().draft)")
                assert json.loads(budget_before)["base"]["cash_budget"] == 176000
                page.evaluate("PlanningFlow.mutate(s => {s.references.evidence.method.version = 'genre_price_references_v1';})")
                old_reference_state = page.evaluate("PlanningFlow.read()")
                page.goto(base + "/plan")
                expect(page.locator("#plan-checks")).to_contain_text("相近遊戲配對方法已更新")
                expect(page.locator("#plan-export")).to_be_disabled()
                assert page.evaluate("JSON.stringify(PlanningFlow.read().budget)") == budget_before
                checks.append("Summary rejects saved v1 reference evidence before marking a plan current or enabling export.")

                page.goto(base + "/revenue#reference-panel")
                expect(page.locator("#ref-status")).to_contain_text("舊參考選擇已清除")
                expect(page.locator("#ref-selection-status")).to_contain_text("已保存 0 / 5")
                expect(page.locator("#ref-results")).to_be_hidden()
                assert page.evaluate("PlanningFlow.read().references") is None
                assert page.evaluate("JSON.stringify(PlanningFlow.read().budget)") == budget_before
                assert page.evaluate("JSON.stringify(PlanningFlow.read().draft)") == draft_before
                expect(page.locator("#ref-price")).to_have_value("14.99")
                expect(page.locator('#ref-genres input[value="Action"]')).to_be_checked()
                page.locator("#reference-panel").screenshot(path=str(output / "stale-reference-method.png"))
                checks.append("Restoring old reference evidence clears only reference selections; manual draft, calculated budget and search inputs survive.")

                # An unavailable storage write must not make stale evidence look current.
                page.evaluate("state => sessionStorage.setItem('gamescope.planning.v1', JSON.stringify(state))", old_reference_state)
                page.evaluate("sessionStorage.setItem('taxonomy-qa-deny-write', '1')")
                page.add_init_script("""if (sessionStorage.getItem('taxonomy-qa-deny-write') === '1') {
                    window.taxonomyOriginalSetItem = Storage.prototype.setItem;
                    Storage.prototype.setItem = function(key, value) {
                        if (key === 'gamescope.planning.v1') throw new DOMException('QA denied write', 'QuotaExceededError');
                        return window.taxonomyOriginalSetItem.call(this, key, value);
                    };
                }""")
                page.reload()
                expect(page.locator("#ref-status")).to_contain_text("瀏覽器未能清除")
                expect(page.locator("#ref-selection-status")).to_contain_text("舊選擇已失效")
                expect(page.locator("#ref-results")).to_be_hidden()
                assert page.evaluate("JSON.stringify(PlanningFlow.read().budget)") == budget_before
                page.evaluate("Storage.prototype.setItem = window.taxonomyOriginalSetItem; sessionStorage.removeItem('taxonomy-qa-deny-write');")
                page.reload()
                expect(page.locator("#ref-selection-status")).to_contain_text("已保存 0 / 5")
                checks.append("Failed browser-storage writes leave stale reference evidence hidden and explicitly unavailable; restoration recovers once storage works.")

                page.evaluate("PlanningFlow.mutate(s => {s.comparison.scenarios.a.filters.genre = 'Indie';})")
                page.goto(base)
                expect(page.locator("#status")).to_contain_text("舊篩選條件")
                expect(page.locator("#workflow-panel")).to_contain_text("舊篩選條件")
                expect(page.locator("#results")).to_be_hidden()
                expect(page.locator("#a-genre")).to_have_value("")
                assert page.evaluate("PlanningFlow.read().comparison.scenarios.a.filters.genre") == "Indie"
                response = page.request.post(base + "/api/compare", data={"platform": "pc", "a": {"genre": "Indie"}, "b": {}})
                assert response.status == 400 and "source_tag" in response.json()["error"]
                page.goto(base + "/plan")
                expect(page.locator("#plan-checks")).to_contain_text("舊類型／標籤條件")
                expect(page.locator("#plan-export")).to_be_disabled()
                checks.append("Legacy genre=Indie is neither restored as a gameplay genre nor silently migrated; UI/API/summary require reselection.")

                page.set_viewport_size({"width": 390, "height": 844})
                page.goto(base)
                expect(page.locator("#a-source_tag")).to_be_visible()
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                page.screenshot(path=str(output / "taxonomy-mobile.png"), full_page=True)
                assert not errors, errors
                browser.close()
            (output / "verification.json").write_text(json.dumps({"checks": checks, "page_errors": errors,
                "note": "Automated local Edge checks; no human study or separate-computer validation."}, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"Taxonomy browser checks passed ({len(checks)} groups).")
        finally:
            server.shutdown(); server.server_close(); thread.join(); store.db.close()


if __name__ == "__main__":
    main()
