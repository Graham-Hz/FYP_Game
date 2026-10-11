"""Headless Edge end-to-end import QA in a disposable application repository."""
import json
import sys
import tempfile
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/demo"))
sys.path.insert(0, str(ROOT / "tests"))
from server import ComparisonStore, make_server
from test_csv_import import mobile, raw


def main():
    output = ROOT / "data/application/qa"
    output.mkdir(parents=True, exist_ok=True)
    errors, checks = [], []
    with tempfile.TemporaryDirectory() as folder:
        store = ComparisonStore(app_path=Path(folder))
        server = make_server(store, 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(channel="msedge", headless=True)
                page = browser.new_page(viewport={"width": 1365, "height": 1000}, device_scale_factor=1)
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(f"http://127.0.0.1:{server.server_port}/")
                page.locator('[data-platform="mobile"]').click()
                expect(page.locator("#denominator")).to_have_text("221,806 筆訓練樣本")
                page.locator("#data-manager summary").click()
                page.locator("#source-name").fill("Synthetic QA fixture")
                page.locator("#snapshot-date").fill("2026-10-01")
                page.locator("#data-kind").select_option("synthetic")
                page.locator("#csv-file").set_input_files({"name": "invalid.csv", "mimeType": "text/csv", "buffer": raw([mobile(), mobile()])})
                page.locator("#preview-import").click()
                expect(page.locator("#import-status")).to_contain_text("不能儲存")
                expect(page.locator("#save-import")).to_be_disabled()
                expect(page.locator("#denominator")).to_have_text("221,806 筆訓練樣本")
                checks.append("Duplicate upload blocked; active research data unchanged")
                second = mobile(); second.update(app_id="example.two", minimum_installs="100000", free="false", price="5")
                page.locator("#csv-file").set_input_files({"name": "synthetic.csv", "mimeType": "text/csv", "buffer": raw([mobile(), second])})
                page.locator("#preview-import").click()
                expect(page.locator("#import-status")).to_contain_text("驗證通過")
                expect(page.locator("#validation-summary")).to_contain_text("合資格 2")
                page.screenshot(path=str(output / "import-desktop.png"), full_page=True)
                page.locator("#save-import").click()
                expect(page.locator("#import-status")).to_contain_text("尚未啟用")
                expect(page.locator("#denominator")).to_have_text("221,806 筆訓練樣本")
                page.locator("#activate-version").click()
                expect(page.locator("#denominator")).to_have_text("2 筆合資格樣本")
                expect(page.locator("#scope")).to_contain_text("人工示例")
                page.locator("#a-free").select_option("true")
                page.locator("#compare").click()
                expect(page.locator("#results")).to_be_visible()
                expect(page.locator(".metric").first).to_contain_text("1")
                with page.expect_download() as event:
                    page.locator("#export").click()
                event.value.save_as(str(output / "import-comparison.json"))
                result = json.loads((output / "import-comparison.json").read_text(encoding="utf-8"))
                assert result["partition"] == "application_snapshot"
                assert result["metadata"]["data_kind"] == "synthetic"
                assert result["scenarios"]["a"]["total"] == 1
                assert result["scenarios"]["b"]["total"] == 2
                assert result["version_id"] == store.active["mobile"]
                checks.append("Preview/save/activate/filter/export use the imported version and correct denominators")
                page.reload()
                page.locator('[data-platform="mobile"]').click()
                expect(page.locator("#denominator")).to_have_text("2 筆合資格樣本")
                page.locator("#data-manager summary").click()
                page.locator("#version-select").select_option("research_train_v1")
                page.locator("#activate-version").click()
                expect(page.locator("#denominator")).to_have_text("221,806 筆訓練樣本")
                expect(page.locator("#results")).to_be_hidden()
                checks.append("Reload preserves selection; rollback restores research counts and invalidates stale output")
                page.set_viewport_size({"width": 390, "height": 844})
                page.screenshot(path=str(output / "import-mobile.png"), full_page=True)
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                assert not errors, errors
                checks.append("390px view has no horizontal overflow; no page JavaScript errors")
                browser.close()
        finally:
            server.shutdown(); server.server_close(); thread.join(); store.db.close()
    (output / "browser_verification.json").write_text(json.dumps({"status": "passed", "checks": checks, "page_errors": errors}, indent=2), encoding="utf-8")
    print(json.dumps({"status": "passed", "checks": checks}))


if __name__ == "__main__": main()
