"""Restore saved cost assumptions atomically, then explicitly recalculate them."""
import copy
import json
import sys
import tempfile
import threading
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src/demo'))
from server import ComparisonStore, make_server


def main():
    output = ROOT / 'data/processed/budget_restore_qa'
    output.mkdir(parents=True, exist_ok=True)
    isolated = tempfile.TemporaryDirectory(prefix='budget-restore-qa-')
    server = make_server(ComparisonStore(app_path=Path(isolated.name)), 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f'http://127.0.0.1:{server.server_port}'
    checks, errors, dialogs = [], [], []
    report = {'passed': False, 'checks': checks, 'page_errors': errors}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel='msedge', headless=True)
            try:
                page = browser.new_page(viewport={'width':1440,'height':1000})
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.on('dialog', lambda dialog: (dialogs.append(dialog.message), dialog.accept()))
                page.goto(base+'/planning')
                expect(page.locator('#load-example')).to_be_enabled()

                def calculate(expected=None):
                    page.locator('#calculate-budget').click()
                    expect(page.locator('#budget-results')).to_be_visible()
                    if expected:
                        expect(page.locator('#budget-metrics')).to_contain_text(expected)

                def load(slot):
                    page.locator(f'#scenario-load-{slot}').click()
                    expect(page.locator('#budget-scenarios-status')).to_contain_text('已載入方案')
                    expect(page.locator('#budget-results')).to_be_hidden()

                def current():
                    return page.evaluate('({draft:captureDraft(),result,legacy:PlanningFlow.read()})')

                page.locator('#load-example').click()
                calculate('176,000')
                page.locator('#scenario-save-a').click()
                a = page.evaluate('PlanningFlow.budgetScenarios().slots.a')
                page.locator('#budget-months').fill('9')
                page.locator('#available_funds').fill('')
                page.locator('#net_unit_contribution').fill('0')
                calculate()
                page.locator('#scenario-save-b').click()
                b = page.evaluate('PlanningFlow.budgetScenarios().slots.b')
                load('a')
                assert page.evaluate('captureDraft()') == a['draft']
                assert page.evaluate('PlanningFlow.read()') is None
                expect(page.locator('#scenario-form-match')).to_contain_text('方案 A')
                expect(page.locator('#scenario-form-match')).to_contain_text('尚需')
                calculate('176,000')
                assert page.evaluate('BudgetScenarios.matchingSlots(result,PlanningFlow.budgetScenarios().slots)') == ['a']
                load('b')
                expect(page.locator('#available_funds')).to_have_value('')
                expect(page.locator('#net_unit_contribution')).to_have_value('0')
                assert page.evaluate('captureDraft()') == b['draft']
                assert page.evaluate('PlanningFlow.budgetScenarios().slots') == {'a':a,'b':b}
                page.reload()
                expect(page.locator('#scenario-load-a')).to_be_enabled()
                load('a')
                assert page.evaluate('captureDraft()') == a['draft']
                checks.append('Standalone A/B inputs survive navigation through immutable snapshots; restoration preserves team, blanks and explicit zeros, clears results and requires Calculate.')

                page.locator('#fee-search').fill('Unity')
                page.locator('[data-add-fee="F002"]').click()
                selected = page.locator('.fee-selection[data-fee-id="F002"]')
                selected.locator('[data-fee-field="quantity"]').fill('2')
                selected.locator('[data-fee-field="fx_rate"]').fill('7.8')
                selected.locator('[data-fee-field="eligibility_confirmed"]').check()
                calculate('215,639.6')
                page.locator('#scenario-save-b').click()
                fee_b = page.evaluate('PlanningFlow.budgetScenarios().slots.b')
                load('a')
                expect(page.locator('.fee-selection')).to_have_count(0)
                load('b')
                assert page.evaluate('captureDraft()') == fee_b['draft']
                expect(selected.locator('[data-fee-field="quantity"]')).to_have_value('2')
                expect(selected.locator('[data-fee-field="fx_rate"]')).to_have_value('7.8')
                expect(selected.locator('[data-fee-field="eligibility_confirmed"]')).to_be_checked()
                calculate('215,639.6')
                assert page.evaluate('BudgetScenarios.matchingSlots(result,PlanningFlow.budgetScenarios().slots)') == ['b']
                assert page.evaluate("()=>{const b=structuredClone(result);b.fee_reference.metadata.revision='other';return BudgetScenarios.matchingSlots(b,PlanningFlow.budgetScenarios().slots)}") == []
                checks.append('Fresh fee validation restores quantities, FX and confirmations exactly; loading manual A removes B fees; matching requires exact method/request/source revision.')

                fee_data = page.request.get(base+'/api/planning/fees').json()
                for kind in ('unavailable','stale','missing'):
                    candidate = copy.deepcopy(fee_data)
                    if kind == 'stale': candidate['metadata']['revision'] = 'stale'
                    if kind == 'missing': candidate['fees'] = [row for row in candidate['fees'] if row['fee_id'] != 'F002']
                    before = current()
                    page.route('**/api/planning/fees', lambda route, request, data=candidate, mode=kind: route.fulfill(status=503 if mode=='unavailable' else 200,json=data))
                    page.locator('#scenario-load-b').click()
                    expect(page.locator('#budget-scenarios-status')).to_contain_text('未能載入')
                    assert current() == before
                    assert page.evaluate('PlanningFlow.budgetScenarios().slots.b') == fee_b
                    page.unroute('**/api/planning/fees')
                page.evaluate("()=>{const s=JSON.parse(sessionStorage.getItem('gamescope.planning.workspace.v1'));s.budget_scenarios.b.budget.method_version='unsupported';sessionStorage.setItem('gamescope.planning.workspace.v1',JSON.stringify(s));}")
                before = current()
                page.locator('#scenario-load-b').click()
                expect(page.locator('#budget-scenarios-status')).to_contain_text('計算方法不受')
                assert current() == before
                page.evaluate("snapshot=>{const s=JSON.parse(sessionStorage.getItem('gamescope.planning.workspace.v1'));s.budget_scenarios.b=snapshot;sessionStorage.setItem('gamescope.planning.workspace.v1',JSON.stringify(s));BudgetScenarios.refreshCurrent();}",fee_b)
                checks.append('Unavailable/stale/missing fee sources and unsupported methods reject the entire restoration, preserving visible form, result and immutable snapshots.')

                # Real legacy planning context; the restored cost assumptions must not replace it.
                page.goto(base)
                expect(page.locator('#a-genre')).to_be_visible()
                page.locator('#a-genre').select_option('Action')
                page.locator('#b-genre').select_option('RPG')
                page.locator('#compare').click()
                expect(page.locator('#results')).to_be_visible()
                page.locator('[data-plan-choice="a"]').click()
                expect(page.locator('#ref-price')).to_be_visible()
                page.locator('#ref-price').fill('14.99')
                page.locator('#ref-submit').click()
                expect(page.locator('#ref-results')).to_be_visible()
                page.locator('[data-plan-game]').first.check()
                page.locator('#ref-to-budget').click()
                expect(page.locator('#load-example')).to_be_enabled()
                page.locator('#load-example').click()
                calculate('176,000')
                initial = current()

                page.evaluate("()=>{window.originalStorageSet=Storage.prototype.setItem;Storage.prototype.setItem=function(k,v){if(k==='gamescope.planning.v1')throw new DOMException('QA quota','QuotaExceededError');return originalStorageSet.call(this,k,v);};}")
                page.locator('#scenario-load-b').click()
                expect(page.locator('#budget-scenarios-status')).to_contain_text('無法保存')
                assert current() == initial
                page.evaluate('()=>{Storage.prototype.setItem=window.originalStorageSet;}')
                load('b')
                assert '只載入成本假設' in dialogs[-1]
                after = current()
                assert after['legacy']['budget'] is None and after['result'] is None
                assert after['legacy']['draft'] == fee_b['draft']
                for key in ('context_id','comparison','choice','references','reference_draft','reference_skip'):
                    assert after['legacy'].get(key) == initial['legacy'].get(key)
                calculate('215,639.6')
                load('a')
                calculate('176,000')
                page.locator('#budget-to-summary').click()
                expect(page.locator('.plan-budget-current')).to_contain_text('方案 A')
                expect(page.locator('#plan-budget')).to_contain_text('176,000')
                page.goto(base+'/planning')
                expect(page.locator('#budget-results')).to_be_visible()
                assert page.evaluate('PlanningFlow.budgetScenarios().slots') == {'a':a,'b':fee_b}
                checks.append('Legacy write failure is atomic. Cross-context loads explicitly preserve current platform/comparison/references; only recalculation replaces active budget and summary labels the matching saved inputs.')

                # Keep the network promise pending without blocking the browser thread.
                page.evaluate("()=>{window.originalFetch=window.fetch;window.fetch=(url,...args)=>url==='/api/planning/fees'?new Promise(resolve=>window.releaseRestore=()=>originalFetch(url,...args).then(resolve)):originalFetch(url,...args);}")
                page.locator('#scenario-load-b').click()
                page.wait_for_function('typeof window.releaseRestore === "function"')
                assert page.evaluate("document.getElementById('budget-form').inert && document.getElementById('fee-library').inert")
                expect(page.locator('#load-example')).to_be_disabled()
                before = current()
                page.evaluate("()=>{const s=JSON.parse(sessionStorage.getItem('gamescope.planning.v1'));s.context_id='changed-while-loading';sessionStorage.setItem('gamescope.planning.v1',JSON.stringify(s));releaseRestore();window.fetch=originalFetch;}")
                expect(page.locator('#budget-scenarios-status')).to_contain_text('情境或保存方案已改變')
                assert current()['draft'] == before['draft'] and current()['result'] == before['result']
                assert not page.evaluate("document.getElementById('budget-form').inert")

                # A pending older budget response must not overwrite a freshly loaded draft.
                page.evaluate("()=>{window.originalFetch=window.fetch;window.fetch=(url,...args)=>url==='/api/planning/budget'?new Promise(resolve=>window.releaseBudget=()=>originalFetch(url,...args).then(response=>{window.budgetResponseArrived=true;resolve(response);})):originalFetch(url,...args);}")
                page.locator('#budget-months').fill('11')
                page.locator('#calculate-budget').click()
                page.wait_for_function('typeof window.releaseBudget === "function"')
                load('a')
                page.evaluate('()=>{releaseBudget();window.fetch=originalFetch;}')
                expect(page.locator('#calculate-budget')).to_be_enabled()
                page.wait_for_function('result===null && document.getElementById("budget-months").value==="12"')
                # Drain the actual old HTTP response before asserting that it stayed ignored.
                page.wait_for_function('window.budgetResponseArrived===true')
                page.evaluate('()=>new Promise(resolve=>setTimeout(resolve,0))')
                assert current()['result'] is None and current()['legacy']['budget'] is None
                assert current()['draft'] == a['draft']
                checks.append('Async fee validation freezes editing and rejects changed contexts. Pending old calculation responses cannot overwrite a restored, uncalculated draft.')

                calculate('176,000')
                page.set_viewport_size({'width':390,'height':844})
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                page.locator('#budget-scenarios').screenshot(path=str(output/'restore-mobile.png'))
                page.set_viewport_size({'width':1440,'height':1000})
                page.locator('#budget-scenarios').screenshot(path=str(output/'restore-desktop.png'))
                assert not errors, errors
                checks.append('Restore controls and current-input status fit at 390px; no JavaScript errors.')
                report['passed'] = True
            finally:
                browser.close()
    except Exception as exc:
        report['error'] = f'{type(exc).__name__}: {exc}'
        raise
    finally:
        server.shutdown();server.server_close();thread.join();isolated.cleanup()
        (output/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
