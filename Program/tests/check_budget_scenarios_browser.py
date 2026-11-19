"""Saved budget alternatives: immutable snapshots, arithmetic context and exports."""
import json
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src/demo'))
from server import make_server


def main():
    output = ROOT / 'data/processed/budget_scenarios_qa'
    output.mkdir(parents=True, exist_ok=True)
    server = make_server(SimpleNamespace(root=ROOT), 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    checks, errors = [], []
    report = {'passed': False, 'checks': checks, 'page_errors': errors}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel='msedge', headless=True)
            try:
                page = browser.new_page(viewport={'width':1440,'height':1000}, accept_downloads=True)
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.on('dialog', lambda dialog: dialog.accept())
                page.goto(f'http://127.0.0.1:{server.server_port}/planning')
                expect(page.locator('#load-example')).to_be_enabled()
                expect(page.locator('#scenario-save-a')).to_be_disabled()
                page.locator('#load-example').click()
                page.locator('#calculate-budget').click()
                expect(page.locator('#budget-metrics')).to_contain_text('176,000')
                page.locator('#scenario-name-a').fill('Original 12 months')
                page.locator('#scenario-save-a').click()
                a = page.evaluate('PlanningFlow.budgetScenarios().slots.a')
                assert a['budget']['base']['cash_budget'] == 176000
                assert a['budget']['request']['months'] == 12
                assert page.evaluate('PlanningFlow.read()') is None
                page.locator('#budget-months').fill('9')
                expect(page.locator('#scenario-save-b')).to_be_disabled()
                assert page.evaluate('PlanningFlow.budgetScenarios().slots.a') == a
                page.locator('#monthly_overhead').fill('1000')
                page.locator('#available_funds').fill('')
                page.locator('#net_unit_contribution').fill('')
                page.locator('#calculate-budget').click()
                expect(page.locator('#budget-metrics')).to_contain_text('133,100')
                page.locator('#scenario-name-b').fill('Shorter scope')
                page.locator('#scenario-save-b').click()
                expect(page.locator('#scenario-export')).to_be_enabled()
                comparison = page.evaluate('BudgetScenarios.compare(PlanningFlow.budgetScenarios().slots)')
                by_key = {row['key']: row for row in comparison['metrics']}
                assert comparison['ready']
                assert by_key['cash_budget']['delta'] == -42900
                assert by_key['cash_break_even_units']['a'] == 4400
                assert by_key['cash_break_even_units']['b'] is None
                assert by_key['cash_break_even_units']['delta'] is None
                assert by_key['funding_balance']['b'] is None
                assert comparison['delays'][1] == {'key':'3','label':'延長 3 個月','unit':'HKD','a':209000,'b':162800,'delta':-46200,'a_months':15,'b_months':12}
                assert {row['key'] for row in comparison['inputs']} == {'months','monthly_overhead','available_funds','net_unit_contribution'}
                expect(page.locator('#budget-scenarios-view .scenario-chart svg')).to_have_count(2)
                page.locator('#budget-scenarios').screenshot(path=str(output/'alternatives-desktop.png'))
                with page.expect_download() as event:
                    page.locator('#scenario-export').click()
                event.value.save_as(str(output/'alternatives.json'))
                exported = json.loads((output/'alternatives.json').read_text(encoding='utf-8'))
                assert exported['slots']['a'] == a
                assert exported['comparison'] == comparison
                assert exported['slots']['b']['budget']['request']['net_unit_contribution'] is None
                with page.expect_download() as event:
                    page.locator('[data-scenario-chart="components"] .game-chart-actions button').click()
                event.value.save_as(str(output/'components.svg'))
                svg = (output/'components.svg').read_text(encoding='utf-8')
                assert 'Original 12 months' in svg and 'Shorter scope' in svg and '來源：兩個已保存的使用者預算' in svg
                checks.append('Standalone immutable A/B snapshots compare exact server outputs; null funds/contribution stay unknown, delay offsets retain actual durations, JSON/SVG preserve evidence.')

                # Optional fee references select v2 while manual A remains supported v1.
                page.locator('#load-example').click()
                page.locator('#fee-search').fill('Unity')
                page.locator('[data-add-fee="F002"]').click()
                selected = page.locator('.fee-selection[data-fee-id="F002"]')
                selected.locator('[data-fee-field="quantity"]').fill('2')
                selected.locator('[data-fee-field="fx_rate"]').fill('7.8')
                selected.locator('[data-fee-field="eligibility_confirmed"]').check()
                page.locator('#calculate-budget').click()
                expect(page.locator('#budget-metrics')).to_contain_text('215,639.6')
                page.locator('#scenario-name-b').fill('Two Unity Pro seats')
                page.locator('#scenario-save-b').click()
                expect(page.locator('#scenario-export')).to_be_enabled()
                with page.expect_download() as event:
                    page.locator('#scenario-export').click()
                event.value.save_as(str(output/'with-fees.json'))
                fee_export = json.loads((output/'with-fees.json').read_text(encoding='utf-8'))
                assert fee_export['comparison']['ready']
                assert {v['budget']['method_version'] for v in fee_export['slots'].values()} == {'budget_scenario_v1','budget_scenario_v2'}
                assert fee_export['slots']['b']['budget']['fee_reference']['selections'][0]['fx_rate'] == 7.8
                assert len(fee_export['slots']['b']['budget']['fee_reference']['sources']) == 2
                fee_rows = {r['key']:r for r in fee_export['comparison']['components']}
                assert fee_rows['reference_fees']['a'] == 0 and fee_rows['reference_fees']['b'] == 36036
                assert fee_export['comparison']['delays'][1]['b'] == 288279.2
                assert page.evaluate('PlanningFlow.budgetScenarios().slots.a') == a
                checks.append('Manual v1 and current optional-fee v2 budgets are compatible; saved fee selections, FX, sources and whole-term renewals are preserved.')

                page.route('**/api/planning/fees', lambda route:route.fulfill(status=503,content_type='application/json',body='{"error":"unavailable"}'))
                page.locator('#scenario-export').click()
                expect(page.locator('#budget-scenarios-status')).to_contain_text('未能匯出')
                expect(page.locator('#scenario-export')).to_be_disabled()
                expect(page.locator('#budget-scenarios-view .scenario-chart')).to_have_count(0)
                page.unroute('**/api/planning/fees')
                page.locator('#scenario-recheck').click()
                expect(page.locator('#scenario-export')).to_be_enabled()

                # Source metadata changes between rendering and export must block download.
                fee_data = page.request.get(f'http://127.0.0.1:{server.server_port}/api/planning/fees').json()
                fee_data['metadata']['revision'] = 'new-unreviewed-fee-revision'
                page.route('**/api/planning/fees', lambda route:route.fulfill(status=200,content_type='application/json',body=json.dumps(fee_data)))
                page.locator('#scenario-export').click()
                expect(page.locator('#budget-scenarios-status')).to_contain_text('未能匯出')
                expect(page.locator('#scenario-export')).to_be_disabled()
                expect(page.locator('#budget-scenarios-view')).to_contain_text('費用來源版本未能通過核對')
                expect(page.locator('#budget-scenarios-view .scenario-chart')).to_have_count(0)
                assert page.evaluate('PlanningFlow.budgetScenarios().slots.a') == a
                page.unroute('**/api/planning/fees')
                page.reload()
                expect(page.locator('#scenario-export')).to_be_enabled()
                expect(page.locator('#scenario-save-a')).to_be_disabled()
                checks.append('Unavailable or changed fee sources block numeric comparison/export without deleting snapshots; explicit retry or reload with matching sources restores the saved comparison.')

                # Different currencies must not be silently converted or subtracted.
                page.locator('#load-example').click()
                page.locator('#budget-currency').select_option('USD')
                page.locator('#calculate-budget').click()
                expect(page.locator('#budget-results')).to_be_visible()
                page.locator('#scenario-save-b').click()
                expect(page.locator('#scenario-export')).to_be_disabled()
                expect(page.locator('#budget-scenarios-view')).to_contain_text('兩個方案幣別不同')
                expect(page.locator('#budget-scenarios-view .scenario-chart')).to_have_count(0)
                checks.append('Different currencies show both saved contexts but suppress numeric differences, shared-axis charts and combined export.')

                # Unsupported saved methods cannot masquerade as current calculations.
                page.evaluate("""()=>{const key='gamescope.planning.workspace.v1',s=JSON.parse(sessionStorage.getItem(key));s.budget_scenarios.b.budget.currency='HKD';s.budget_scenarios.b.budget.request.currency='HKD';s.budget_scenarios.b.budget.method_version='unknown_future_method';sessionStorage.setItem(key,JSON.stringify(s));BudgetScenarios.refreshCurrent();}""")
                expect(page.locator('#budget-scenarios-view')).to_contain_text('計算方法不受目前版本支援')
                expect(page.locator('#scenario-export')).to_be_disabled()
                page.locator('#load-example').click();page.locator('#calculate-budget').click()
                expect(page.locator('#budget-results')).to_be_visible()
                page.locator('#scenario-name-b').fill('Manual recalculation')
                page.locator('#scenario-save-b').click()
                expect(page.locator('#scenario-export')).to_be_enabled()
                checks.append('Unsupported saved calculation methods are explicitly rejected until the user recalculates and updates that slot.')

                page.set_viewport_size({'width':390,'height':844})
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                page.locator('#budget-scenarios').screenshot(path=str(output/'alternatives-390px.png'))
                assert not errors, errors
                page.locator('#scenario-remove-b').click()
                expect(page.locator('#scenario-export')).to_be_disabled()
                assert page.evaluate('PlanningFlow.budgetScenarios().slots.a') == a
                assert page.evaluate('PlanningFlow.budgetScenarios().slots.b') is None
                checks.append('390px layout contains chart/table scrolling; removing B preserves A and no JavaScript errors occur.')
                report['passed'] = True
            finally:
                browser.close()
    except Exception as exc:
        report['error'] = f'{type(exc).__name__}: {exc}'
        raise
    finally:
        server.shutdown();server.server_close();thread.join()
        (output/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
