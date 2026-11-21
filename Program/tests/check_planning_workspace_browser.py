"""Cross-page market findings, immutable budget scenarios and summary evidence.

Uses an isolated application registry and real historical/calculation APIs.
Run: uv run --locked --with playwright python -B tests/check_planning_workspace_browser.py
"""
import json
from pathlib import Path
import sys
import tempfile
import threading

from playwright.sync_api import expect, sync_playwright
from market_browser_controls import market_control

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src/demo'))
from server import ComparisonStore, make_server


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    output = ROOT / 'data/processed/planning_workspace_qa'
    output.mkdir(parents=True, exist_ok=True)
    checks, errors = [], []
    report = {'passed': False, 'checks': checks, 'page_errors': errors,
              'note': 'Automated local task-path checks; no participant or second-computer validation.'}
    with tempfile.TemporaryDirectory(prefix='planning-workspace-ui-') as folder:
        store = ComparisonStore(app_path=Path(folder))
        server = make_server(store, 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f'http://127.0.0.1:{server.server_port}'
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(channel='msedge', headless=True)
                try:
                    context = browser.new_context(viewport={'width': 1440, 'height': 1000}, accept_downloads=True)
                    page = context.new_page()
                    page.set_default_timeout(30000)
                    expect.set_options(timeout=30000)
                    page.on('pageerror', lambda error: errors.append(str(error)))

                    def export_plan(filename):
                        expect(page.locator('#plan-export')).to_be_enabled()
                        with page.expect_download() as event:
                            page.locator('#plan-export').click()
                        path = output / filename
                        event.value.save_as(str(path))
                        return json.loads(path.read_text(encoding='utf-8'))

                    def workspace():
                        return page.evaluate('PlanningFlow.readWorkspace()')

                    # Capture a real result before any historical planning condition exists.
                    page.goto(base + '/market')
                    expect(page.locator('#market-results')).to_be_visible()
                    market_control(page, '#market-source').select_option('mobile')
                    expect(page.locator('#market-scope-source')).to_contain_text('Android')
                    market_control(page, '#market-group').select_option('Adventure')
                    market_control(page, '#market-apply').click()
                    expect(page.locator('article[data-chart-id="cohort_comparison"]')).to_be_visible()
                    page.locator('#market-finding-open').click()
                    page.locator('#market-finding-title').fill('Adventure distribution needs context')
                    note = 'The same median hides different tier shares; ask a developer whether the sample matches the concept.'
                    page.locator('#market-finding-note').fill(note)
                    page.locator('#market-finding-save').click()
                    expect(page.locator('.market-finding-item')).to_have_count(1)
                    require(page.evaluate('PlanningFlow.read()') is None, 'Capturing a finding fabricated a historical planning condition')
                    original_finding = workspace()['findings'][0]
                    require(original_finding['source']['id'] == 'mobile', 'Finding lost platform identity')
                    require(original_finding['comparison']['selected']['n'] == 15795, 'Finding selected denominator differs from the real cohort')
                    require(original_finding['comparison']['baseline']['n'] == 206011, 'Finding baseline denominator differs from the real cohort')

                    page.goto(base + '/plan')
                    expect(page.locator('#plan-content')).to_be_visible()
                    expect(page.locator('#plan-findings')).to_contain_text('Adventure distribution needs context')
                    expect(page.locator('#plan-findings')).to_contain_text(note)
                    page.locator('#plan-name').fill('Workspace before choosing a condition')
                    page.locator('#plan-notes').fill('Evidence first; budget assumptions remain independently entered.')
                    first = export_plan('finding-only-summary.json')
                    require(first['historical_comparison'] is None and first['selected_condition'] is None,
                            'Workspace-only export invented a selected planning condition')
                    require(not first['completion']['complete'], 'Finding-only workspace was incorrectly marked complete')
                    require(first['market_findings'][0] == original_finding, 'Summary altered saved historical evidence')
                    require(first['name'] == 'Workspace before choosing a condition', 'Workspace-only title was not saved')
                    checks.append('Market finding can precede a plan; the summary preserves evidence and notes without inventing condition or completion')

                    # The active market version may change while a finding remains saved.
                    def changed_market(route):
                        response = route.fetch()
                        data = response.json()
                        next(source for source in data['sources'] if source['id'] == 'mobile')['version_id'] = 'qa_changed_version'
                        route.fulfill(response=response, json=data)

                    page.route('**/api/market/options', changed_market)
                    page.locator('#plan-refresh').click()
                    expect(page.locator('#plan-status')).to_contain_text('部分來源版本未通過核對')
                    expect(page.locator('#plan-export')).to_be_disabled()
                    page.wait_for_function("document.querySelector('#plan-checks').textContent.includes('版本')")
                    require(workspace()['findings'][0] == original_finding, 'Source mismatch erased or modified the saved finding')
                    page.unroute('**/api/market/options')
                    page.locator('#plan-refresh').click()
                    expect(page.locator('#plan-export')).to_be_enabled()
                    checks.append('A changed market version blocks qualified summary export while keeping the original evidence available for review')

                    # Budget capture controls are exercised below once both UI modules are loaded.
                    page.goto(base + '/planning')
                    expect(page.locator('#load-example')).to_be_enabled()
                    page.locator('#load-example').click()
                    page.locator('#calculate-budget').click()
                    expect(page.locator('#budget-metrics')).to_contain_text('176,000')

                    page.locator('#scenario-name-a').fill('Small team baseline')
                    page.locator('#scenario-save-a').click()
                    expect(page.locator('#budget-scenarios-status')).to_contain_text('已保存方案 A')
                    original_a = workspace()['budget_scenarios']['a']
                    require(original_a['budget']['base']['cash_budget'] == 176000, 'Scenario A differs from the completed calculator result')
                    require(original_a.get('context_id') is None and original_a.get('platform') is None,
                            'Standalone budget capture invented a planning context or platform')

                    page.locator('#monthly_overhead').fill('3000')
                    expect(page.locator('#budget-results')).to_be_hidden()
                    expect(page.locator('#scenario-save-b')).to_be_disabled()
                    require(workspace()['budget_scenarios']['a'] == original_a, 'Editing the form changed immutable scenario A')
                    expect(page.locator('#fee-count')).to_contain_text('26')
                    page.locator('[data-add-fee="F002"]').click()
                    fee = page.locator('.fee-selection[data-fee-id="F002"]')
                    fee.locator('[data-fee-field="quantity"]').fill('2')
                    fee.locator('[data-fee-field="fx_rate"]').fill('7.8')
                    fee.locator('[data-fee-field="eligibility_confirmed"]').check()
                    page.locator('#calculate-budget').click()
                    expect(page.locator('#budget-metrics')).to_contain_text('228,839.6')
                    page.locator('#scenario-name-b').fill('More overhead and two tool seats')
                    page.locator('#scenario-save-b').click()
                    expect(page.locator('#budget-scenarios-status')).to_contain_text('已保存方案 B')
                    expect(page.locator('#scenario-export')).to_be_enabled()
                    original_b = workspace()['budget_scenarios']['b']
                    require(original_b['budget']['base']['cash_budget'] == 228839.6, 'Scenario B lost the fee or overhead assumptions')
                    require(workspace()['budget_scenarios']['a'] == original_a, 'Saving B replaced A')

                    page.goto(base + '/plan')
                    expect(page.locator('#plan-scenarios')).to_contain_text('Small team baseline')
                    expect(page.locator('#plan-scenarios')).to_contain_text('228,839.6')
                    paired = export_plan('workspace-with-alternatives.json')
                    require(paired['budget_scenarios']['a'] == original_a and paired['budget_scenarios']['b'] == original_b,
                            'Summary export does not preserve both complete budget snapshots')
                    comparison = paired['budget_scenario_comparison']
                    require(comparison['ready'], 'Same-currency, current-source alternatives did not compare')
                    cash = next(row for row in comparison['metrics'] if row['key'] == 'cash_budget')
                    require(abs(cash['delta'] - 52839.6) < .001, 'A/B cash difference disagrees with the stored results')
                    require(paired['budget'] is None and not paired['completion']['complete'],
                            'Saved alternatives were silently promoted into the active planning budget')
                    require(paired['market_findings'][0] == original_finding, 'Budget work changed market evidence')
                    checks.append('Standalone A/B snapshots preserve inputs, fee sources and results through editing/navigation; summary comparisons do not choose an active budget')

                    def changed_fees(route):
                        response = route.fetch()
                        data = response.json()
                        data['metadata']['revision'] = 'qa_changed_fee_revision'
                        route.fulfill(response=response, json=data)

                    page.route('**/api/planning/fees', changed_fees)
                    page.locator('#plan-refresh').click()
                    expect(page.locator('#plan-status')).to_contain_text('部分來源版本未通過核對')
                    expect(page.locator('#plan-export')).to_be_disabled()
                    page.wait_for_function("document.querySelector('#plan-checks').textContent.includes('費用')")
                    require(workspace()['budget_scenarios']['b'] == original_b, 'Stale fee check changed the saved scenario')
                    page.unroute('**/api/planning/fees')
                    page.locator('#plan-refresh').click()
                    expect(page.locator('#plan-export')).to_be_enabled()
                    checks.append('Summary checks fee provenance inside saved alternatives even when no active budget or legacy plan exists')

                    # Choosing a condition creates an independent plan, retaining the evidence workspace.
                    page.goto(base)
                    expect(page.locator('#a-genre')).to_be_visible()
                    page.locator('[data-platform="mobile"]').click()
                    expect(page.locator('#a-category')).to_be_visible()
                    page.locator('#a-category').select_option('Action')
                    page.locator('#compare').click()
                    expect(page.locator('#results')).to_be_visible()
                    page.locator('[data-plan-choice="a"]').click()
                    expect(page).to_have_url(base + '/planning#budget-section')
                    expect(page.locator('#calculate-budget')).to_be_enabled()
                    require(page.evaluate('PlanningFlow.read().budget') is None, 'Creating a plan silently adopted an unrelated saved alternative')
                    require(workspace()['budget_scenarios']['a'] == original_a, 'Creating a plan destroyed saved standalone alternatives')
                    require(workspace()['findings'][0] == original_finding, 'Creating a plan silently relabelled the Adventure finding as Action')
                    page.locator('#load-example').click()
                    page.locator('#calculate-budget').click()
                    expect(page.locator('#budget-metrics')).to_contain_text('176,000')
                    page.goto(base + '/plan')
                    expect(page.locator('#plan-market')).to_contain_text('Action')
                    expect(page.locator('#plan-findings')).to_contain_text('Adventure')
                    combined = export_plan('android-plan-with-findings-and-alternatives.json')
                    require(combined['completion']['complete'], 'An otherwise complete Android workflow lost its prior completion semantics')
                    require(combined['historical_comparison']['platform'] == 'mobile', 'Legacy comparison platform changed')
                    require(combined['budget']['base']['cash_budget'] == 176000, 'Current plan budget was replaced by scenario B')
                    require(combined['budget_scenarios']['b']['budget']['base']['cash_budget'] == 228839.6, 'Alternative B was lost from the combined export')
                    require(combined['market_findings'][0] == original_finding, 'Combined plan changed saved finding scope or user interpretation')
                    require(combined['name'] == first['name'] and combined['decision_notes'] == first['decision_notes'],
                            'Creating the first historical plan lost the previously entered workspace title or notes')
                    expect(page.locator('#plan-title')).to_have_text(first['name'])
                    expect(page.locator('#plan-note-display')).to_have_text(first['decision_notes'])
                    finding_details = page.locator('.plan-finding details').first
                    finding_details.locator(':scope > summary').click()
                    expect(page.locator('.plan-finding svg')).to_have_count(1)
                    expect(page.locator('.plan-finding svg')).to_contain_text('15,795')
                    expect(page.locator('.plan-finding svg')).to_contain_text('206,011')
                    page.locator('.plan-finding').screenshot(path=str(output / 'saved-finding-chart-desktop.png'))
                    finding_details.locator(':scope > summary').click()
                    page.screenshot(path=str(output / 'combined-summary-desktop.png'), full_page=True)
                    page.set_viewport_size({'width': 390, 'height': 844})
                    require(page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Summary overflows at 390px')
                    page.screenshot(path=str(output / 'combined-summary-390px.png'), full_page=True)
                    page.set_viewport_size({'width': 1440, 'height': 1000})
                    checks.append('A later Android condition integrates supplementary evidence and alternatives without rewriting their filters or selecting a budget automatically')

                    page.locator('#plan-name').fill('')
                    page.locator('#plan-notes').fill('')
                    page.locator('#plan-refresh').click()
                    expect(page.locator('#plan-name')).to_have_value('')
                    expect(page.locator('#plan-notes')).to_have_value('')
                    cleared_meta = export_plan('intentionally-blank-plan-metadata.json')
                    require(cleared_meta['name'] == '' and cleared_meta['decision_notes'] == '',
                            'Explicitly cleared plan metadata was silently repopulated from older workspace text')
                    checks.append('Workspace title/notes carry into the first plan; later deliberate blank values remain blank in the form, heading and export')

                    # Failure of workspace writes must never claim that evidence was removed.
                    page.evaluate("""() => {
                        window.qaOriginalSetItem = Storage.prototype.setItem;
                        Storage.prototype.setItem = function(key, value) {
                            if (key === 'gamescope.planning.workspace.v1') throw new DOMException('QA write denied', 'QuotaExceededError');
                            return window.qaOriginalSetItem.call(this, key, value);
                        };
                    }""")
                    page.locator('[data-remove-finding]').first.click()
                    require(workspace()['findings'][0] == original_finding, 'Failed removal nevertheless changed stored evidence')
                    expect(page.locator('#plan-findings .plan-finding')).to_have_count(1)
                    page.evaluate('() => {Storage.prototype.setItem = window.qaOriginalSetItem;}')
                    page.locator('[data-remove-finding]').first.click()
                    expect(page.locator('#plan-findings .plan-finding')).to_have_count(0)
                    require(not workspace()['findings'], 'Successful explicit removal did not persist')
                    require(workspace()['budget_scenarios']['a'] == original_a, 'Removing a finding erased a budget alternative')
                    require(page.evaluate('PlanningFlow.read().budget.base.cash_budget') == 176000, 'Removing supplementary evidence erased the active budget')
                    checks.append('Failed workspace writes retain visible evidence; successful explicit removal preserves both alternatives and the active budget')

                    require(not errors, f'JavaScript errors: {errors}')
                    report['passed'] = True
                finally:
                    browser.close()
        except Exception as error:
            report['error'] = f'{type(error).__name__}: {error}'
            raise
        finally:
            server.shutdown(); server.server_close(); thread.join(); store.db.close()
            (output / 'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
