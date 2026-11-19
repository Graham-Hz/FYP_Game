"""End-to-end planning tasks using the real local APIs and fixed research data."""
import json
import sys
import tempfile
import threading
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src/demo'))
from server import ComparisonStore, make_server


def main():
    output = ROOT / 'data/processed/workflow_qa'
    output.mkdir(parents=True, exist_ok=True)
    isolated = tempfile.TemporaryDirectory(prefix='planning-workflow-browser-')
    store = ComparisonStore(app_path=Path(isolated.name))
    server = make_server(store, 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f'http://127.0.0.1:{server.server_port}'
    errors = []
    checks = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel='msedge', headless=True)
            context = browser.new_context(viewport={'width': 1440, 'height': 1000})
            page = context.new_page()
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(base)
            expect(page.locator('#a-genre')).to_be_visible()
            page.locator('#a-genre').select_option('Action')
            page.locator('#b-genre').select_option('RPG')
            page.locator('#compare').click()
            expect(page.locator('#results')).to_be_visible()
            page.locator('[data-plan-choice="a"]').click()
            expect(page).to_have_url(base + '/revenue#reference-panel')
            expect(page.locator('#ref-flow-note')).to_contain_text('Action')
            expect(page.locator('#ref-genres input[value="Action"]')).to_be_checked()
            expect(page.locator('#ref-price')).to_have_value('')
            page.locator('#ref-price').fill('14.99')
            page.locator('#ref-submit').click()
            expect(page.locator('#ref-results')).to_be_visible()
            boxes = page.locator('[data-plan-game]')
            assert boxes.count() >= 6
            for i in range(6): boxes.nth(i).click()
            assert page.locator('[data-plan-game]:checked').count() == 5
            expect(page.locator('#ref-selection-status')).to_contain_text('最多')
            for i in range(1, 5): boxes.nth(i).uncheck()
            chosen = boxes.first.get_attribute('data-plan-game')
            page.reload()
            expect(page.locator(f'[data-plan-game="{chosen}"]')).to_be_checked()
            expect(page.locator('#ref-price')).to_have_value('14.99')
            page.locator('#reference-panel').screenshot(path=str(output/'references-desktop.png'))
            page.locator('#ref-to-budget').click()
            expect(page.locator('#load-example')).to_be_enabled()
            expect(page.locator('#case-platform')).to_have_value('PC')
            # Comparison and reference prices must never be treated as contribution.
            expect(page.locator('#net_unit_contribution')).to_have_value('')
            page.locator('#load-example').click()
            expect(page.locator('#fee-count')).to_contain_text('26')
            page.locator('[data-add-fee="F002"]').click()
            fee = page.locator('.fee-selection[data-fee-id="F002"]')
            fee.locator('[data-fee-field="quantity"]').fill('2')
            fee.locator('[data-fee-field="fx_rate"]').fill('7.8')
            fee.locator('[data-fee-field="eligibility_confirmed"]').check()
            page.locator('#calculate-budget').click()
            expect(page.locator('#budget-metrics')).to_contain_text('215,639.6')
            page.locator('#budget-to-summary').click()
            expect(page.locator('#plan-export')).to_be_enabled()
            expect(page.locator('#plan-market')).to_contain_text('Action')
            expect(page.locator('#plan-references .plan-games li')).to_have_count(1)
            expect(page.locator('#plan-budget')).to_contain_text('215,639.6')
            expect(page.locator('#plan-budget')).to_contain_text('288,279.2')
            page.locator('#plan-name').fill('Action concept')
            page.locator('#plan-notes').fill('Compare a small scope; validate labour assumptions with a developer.')
            with page.expect_download() as event: page.locator('#plan-export').click()
            event.value.save_as(str(output/'steam-plan.json'))
            steam = json.loads((output/'steam-plan.json').read_text(encoding='utf-8'))
            assert steam['completion']['complete']
            assert steam['comparable_games']['selection_count'] == 1
            assert str(steam['comparable_games']['rows'][0]['steam_id']) == chosen
            assert steam['historical_comparison']['analysis_manifest_sha256']
            assert steam['budget']['fee_reference']['metadata']['sha256']
            assert steam['budget']['base']['cash_budget'] == 215639.6
            assert steam['budget']['delays'][1]['cash_budget'] == 288279.2
            assert steam['budget']['request']['net_unit_contribution'] == 40
            assert steam['name'] == 'Action concept'
            # Independent reference and fee sources must each be checked.
            def changed_revenue(route):
                response=route.fetch(); data=response.json(); data['metadata']['qa_revision']='changed'
                route.fulfill(response=response,json=data)
            page.route('**/api/revenue/metadata',changed_revenue)
            page.locator('#plan-refresh').click()
            expect(page.locator('#plan-checks')).to_contain_text('相近遊戲資料已更新')
            expect(page.locator('#plan-export')).to_be_disabled()
            page.unroute('**/api/revenue/metadata')
            def changed_fees(route):
                response=route.fetch(); data=response.json(); data['metadata']['revision']='qa_changed'
                route.fulfill(response=response,json=data)
            page.route('**/api/planning/fees',changed_fees)
            page.locator('#plan-refresh').click()
            expect(page.locator('#plan-checks')).to_contain_text('工具費用資料已更新')
            expect(page.locator('#plan-export')).to_be_disabled()
            page.unroute('**/api/planning/fees')
            page.locator('#plan-refresh').click()
            expect(page.locator('#plan-export')).to_be_enabled()
            page.screenshot(path=str(output/'summary-desktop.png'), full_page=True)
            page.set_viewport_size({'width':390,'height':844})
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.screenshot(path=str(output/'summary-mobile.png'), full_page=True)
            checks.append('Steam comparison -> explicit reference selection -> fee budget -> source-linked summary export')
            # Draft and computed result survive navigation and reload.
            page.goto(base + '/planning#budget-section')
            expect(page.locator('#budget-results')).to_be_visible()
            expect(page.locator('#budget-months')).to_have_value('12')
            expect(page.locator('.fee-selection [data-fee-field="quantity"]')).to_have_value('2')
            expect(page.locator('.fee-selection [data-fee-field="fx_rate"]')).to_have_value('7.8')
            page.locator('#budget-months').fill('15')
            expect(page.locator('#budget-results')).to_be_hidden()
            page.goto(base + '/plan')
            expect(page.locator('#plan-budget')).to_contain_text('重新計算')
            expect(page.locator('#plan-completion')).to_contain_text('未完成')
            page.goto(base + '/planning')
            expect(page.locator('#calculate-budget')).to_be_enabled()
            expect(page.locator('#budget-months')).to_have_value('15')
            page.locator('#calculate-budget').click()
            expect(page.locator('#budget-metrics')).to_contain_text('288,279.2')
            # Clearing a numeric field must stay blank, not become zero on restore.
            page.locator('#monthly_overhead').fill('')
            page.reload()
            expect(page.locator('#calculate-budget')).to_be_enabled()
            expect(page.locator('#monthly_overhead')).to_have_value('')
            assert not page.locator('#budget-form').evaluate('f => f.checkValidity()')
            page.locator('#monthly_overhead').fill('2000')
            page.locator('#calculate-budget').click()
            expect(page.locator('#budget-results')).to_be_visible()
            checks.append('Draft/fee/FX persistence, missing-versus-zero preservation, edited-input result invalidation')
            # Reopening the same comparison should not erase downstream work.
            page.goto(base)
            expect(page.locator('#a-genre')).to_have_value('Action')
            expect(page.locator('#b-genre')).to_have_value('RPG')
            page.locator('[data-plan-choice="a"]').click()
            expect(page.locator(f'[data-plan-game="{chosen}"]')).to_be_checked()
            assert page.evaluate('PlanningFlow.read().budget.base.cash_budget') == 288279.2
            page.locator('#ref-price').fill('999')
            assert page.evaluate('PlanningFlow.read().references') is None
            page.locator('#ref-factor').select_option('1.5')
            page.locator('#ref-submit').click()
            expect(page.locator('#ref-results')).to_be_visible()
            expect(page.locator('#ref-warning')).to_contain_text('沒有符合')
            page.locator('#ref-skip').is_visible()  # The disclosure remains user-controlled.
            page.locator('#ref-flow-actions details summary').click()
            page.locator('#ref-skip-reason').fill('No suitable candidates in this selected sample.')
            page.locator('#ref-skip').click()
            expect(page).to_have_url(base + '/planning#budget-section')
            page.goto(base + '/plan')
            expect(page.locator('#plan-references')).to_contain_text('No suitable candidates')
            checks.append('Same comparison preservation, changed reference invalidation, honest no-match/skip path')
            # Source version changes must prevent unqualified export; no real versions are mutated.
            def outdated_options(route):
                response = route.fetch(); data = response.json()
                data['platforms']['pc']['version_id'] = 'different_test_version'
                route.fulfill(response=response, json=data)
            page.route('**/api/options', outdated_options)
            page.locator('#plan-refresh').click()
            expect(page.locator('#plan-checks')).to_contain_text('版本已切換')
            expect(page.locator('#plan-export')).to_be_disabled()
            page.unroute('**/api/options')
            page.locator('#plan-refresh').click()
            expect(page.locator('#plan-export')).to_be_enabled()
            # A missing catalogue must not silently drop already selected costs.
            page.route('**/api/planning/fees', lambda route: route.fulfill(status=503, json={'error':'QA unavailable'}))
            page.goto(base + '/planning')
            expect(page.locator('#discard-saved-fees')).to_be_visible()
            expect(page.locator('#calculate-budget')).to_be_disabled()
            page.locator('#monthly_overhead').fill('2100')
            page.reload()
            expect(page.locator('#discard-saved-fees')).to_be_visible()
            expect(page.locator('#monthly_overhead')).to_have_value('2100')
            page.locator('#discard-saved-fees').click()
            expect(page.locator('#calculate-budget')).to_be_enabled()
            page.locator('#calculate-budget').click()
            expect(page.locator('#budget-results')).to_be_visible()
            assert page.evaluate('PlanningFlow.read().budget.fee_reference') is None
            assert page.evaluate('PlanningFlow.read().budget.base.cash_budget') == 210650
            page.unroute('**/api/planning/fees')
            checks.append('Source mismatch blocks export; missing catalogue requires explicit removal of saved fees')
            # Android must not inherit Steam references or silently select PC cases.
            page.set_viewport_size({'width':1440,'height':1000})
            page.goto(base)
            expect(page.locator('#a-genre')).to_be_visible()
            page.locator('[data-platform="mobile"]').click()
            page.locator('#a-category').select_option('Action')
            page.locator('#compare').click()
            expect(page.locator('#results')).to_be_visible()
            page.locator('[data-plan-choice="a"]').click()
            expect(page).to_have_url(base + '/planning#budget-section')
            expect(page.locator('#case-platform')).to_have_value('Android')
            expect(page.locator('#calculate-budget')).to_be_enabled()
            assert page.evaluate('PlanningFlow.read().references') is None
            assert page.evaluate('PlanningFlow.read().budget') is None
            page.locator('#calculate-budget').click()
            expect(page.locator('#budget-results')).to_be_visible()
            page.goto(base + '/plan')
            expect(page.locator('#plan-references')).to_contain_text('未提供 Android')
            expect(page.locator('#plan-export')).to_be_enabled()
            with page.expect_download() as event: page.locator('#plan-export').click()
            event.value.save_as(str(output/'android-plan.json'))
            android=json.loads((output/'android-plan.json').read_text(encoding='utf-8'))
            assert android['reference_status']=='not_available_for_android'
            assert android['comparable_games'] is None
            assert android['historical_comparison']['platform']=='mobile'
            assert android['completion']['complete']
            checks.append('Android direct budget route and explicitly unavailable references')
            # Corrupt browser state and explicit clearing remain recoverable.
            page.evaluate("sessionStorage.setItem('gamescope.planning.v1','invalid json')")
            page.reload()
            expect(page.locator('#workflow-panel')).to_contain_text('無法讀取')
            expect(page.locator('#plan-export')).to_be_disabled()
            page.once('dialog',lambda d:d.accept())
            page.locator('#plan-clear').click()
            expect(page.locator('#plan-status')).to_contain_text('尚未有規劃')
            assert page.evaluate('PlanningFlow.read()') is None
            checks.append('Corrupt-state recovery and explicit reset')
            page.add_init_script("""const original=Storage.prototype.setItem;
              Storage.prototype.setItem=function(k,v){if(k==='gamescope.planning.v1')throw new DOMException('QA storage unavailable','QuotaExceededError');return original.call(this,k,v);};""")
            page.goto(base)
            expect(page.locator('#a-genre')).to_be_visible()
            page.locator('#compare').click()
            expect(page.locator('#results')).to_be_visible()
            page.locator('[data-plan-choice="a"]').click()
            expect(page).to_have_url(base + '/')
            expect(page.locator('#workflow-panel')).to_contain_text('無法保存')
            expect(page.locator('#results')).to_be_visible()
            checks.append('Storage failure preserves standalone comparison and blocks an unsaved handoff')
            assert not errors,errors
            browser.close()
        (output/'verification.json').write_text(json.dumps({'checks':checks,'page_errors':errors,'note':'Automated task-path checks, not a human usability study.'},ensure_ascii=False,indent=2),encoding='utf-8')
        print(f'Planning workflow browser checks passed ({len(checks)} groups).')
    finally:
        server.shutdown();server.server_close();thread.join();store.db.close();isolated.cleanup()


if __name__=='__main__':main()
