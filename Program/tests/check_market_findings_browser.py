"""Market findings: compact evidence, stable provenance and honest persistence.

Run: uv run --offline --locked --with playwright python -B tests/check_market_findings_browser.py
Uses an ephemeral server/import registry and writes only ignored QA artifacts.
"""
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


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    output = ROOT / 'data/processed/market_findings_qa'
    output.mkdir(parents=True, exist_ok=True)
    checks, errors = [], []
    report = dict(passed=False, checks=checks, page_errors=errors)
    with tempfile.TemporaryDirectory(prefix='market-findings-ui-') as folder:
        store = ComparisonStore(app_path=Path(folder))
        server = make_server(store, 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f'http://127.0.0.1:{server.server_port}'
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(channel='msedge', headless=True)
                try:
                    context = browser.new_context(viewport={'width': 1365, 'height': 1000})
                    page = context.new_page()
                    page.set_default_timeout(45000)
                    expect.set_options(timeout=45000)
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    current_options = context.request.get(base + '/api/market/options').json()
                    sources = {s['id']: s for s in current_options['sources']}

                    def items():
                        return page.evaluate('PlanningFlow.findings().items')

                    def select_mobile(group='Adventure'):
                        page.locator('#market-source').select_option('mobile')
                        expect(page.locator('#market-results')).to_be_visible()
                        page.locator('#market-group').select_option(group)
                        page.locator('#market-apply').click()
                        expect(page.locator('#market-charts > article[data-chart-id="cohort_comparison"]')).to_be_visible()

                    def prepare(title, note=''):
                        page.locator('#market-finding-open').click()
                        page.locator('#market-finding-title').fill(title)
                        page.locator('#market-finding-note').fill(note)

                    def save(title, note=''):
                        prepare(title, note)
                        page.locator('#market-finding-save').click()
                        expect(page.locator('#market-finding-status')).to_contain_text('已保存')

                    page.goto(base + '/market')
                    expect(page.locator('#market-results')).to_be_visible()
                    require(page.evaluate('PlanningFlow.read()') is None, 'Fixture unexpectedly has a legacy plan')
                    select_mobile()
                    note = 'Two medians match; inspect distribution before choosing scope. <script>not executable</script>'
                    save('Adventure sample observation', note)
                    expect(page.locator('#market-findings-count')).to_have_text('1 / 5')
                    expect(page.locator('.market-finding-note')).to_have_text(note)
                    finding = items()[0]
                    require(finding['source']['version_id'] == sources['mobile']['version_id'], 'Wrong saved version')
                    require(finding['provenance']['input_hashes'] == sources['mobile']['input_hashes'], 'Missing saved hashes')
                    require(finding['comparison']['selected']['n'] == 15795 and finding['comparison']['baseline']['n'] == 206011,
                            'Cohort denominators were lost')
                    require(finding['comparison']['selected']['tiers'][2]['count'] == 2487, 'Tier evidence was lost')
                    require(finding['comparison']['selected']['statistics']['volume_lower']['q1'] == 100, 'Quartiles were lost')
                    require(finding['charts'][0]['id'] == 'cohort_comparison' and len(finding['charts'][0]['rows']) == 2,
                            'Current chart evidence was not captured')
                    require('chart' not in finding['comparison'] and 'points' not in finding['charts'][0], 'Repeated/raw points saved')
                    require(page.evaluate('PlanningFlow.read()') is None, 'Saving a finding silently invented a planning choice')
                    page.reload()
                    expect(page.locator('#market-findings-count')).to_have_text('1 / 5')
                    select_mobile()
                    prepare('Different title must not bypass duplicate check')
                    page.locator('#market-finding-save').click()
                    expect(page.locator('#market-finding-save')).to_be_enabled()
                    expect(page.locator('#market-finding-status')).to_have_attribute('data-error', 'true')
                    require(len(items()) == 1, 'Duplicate evidence was appended')
                    checks.append('Standalone findings persist across reload, preserve exact cohorts/provenance and reject duplicate evidence despite changed titles')

                    # Metadata can change without a new version string. A hash mismatch
                    # must invalidate capture before any storage mutation.
                    changed = copy.deepcopy(current_options)
                    mobile = next(s for s in changed['sources'] if s['id'] == 'mobile')
                    key = next(iter(mobile['input_hashes']))
                    mobile['input_hashes'][key] = '0' * 64
                    page.route('**/api/market/options', lambda route: route.fulfill(json=changed))
                    page.locator('#market-tab-overview').click()
                    prepare('Must not save changed bytes')
                    page.locator('#market-finding-save').click()
                    expect(page.locator('#market-results')).to_be_hidden()
                    expect(page.locator('#market-status')).to_contain_text('尚未保存')
                    require(len(items()) == 1, 'Stale hashes accepted')
                    page.unroute('**/api/market/options')
                    page.locator('#market-refresh').click()
                    expect(page.locator('#market-results')).to_be_visible()
                    select_mobile()
                    pending = []
                    page.route('**/api/market/options', lambda route: pending.append(route))
                    page.locator('#market-tab-overview').click()
                    prepare('Must not survive changed filters')
                    page.locator('#market-finding-save').click()
                    page.wait_for_timeout(120)
                    require(len(pending) == 1, 'Expected one pending capture check')
                    page.locator('#market-group').select_option('Action')
                    expect(page.locator('#market-results')).to_be_hidden()
                    pending.pop().fulfill(json=current_options)
                    page.wait_for_timeout(120)
                    require(len(items()) == 1, 'Late capture response appended stale evidence')
                    page.unroute('**/api/market/options')
                    checks.append('Same-version changed source hashes and late responses after dirty filters cannot save stale evidence')

                    page.locator('#market-apply').click()
                    expect(page.locator('#market-results')).to_be_visible()
                    prepare('Write failure is not a saved finding')
                    page.evaluate("() => {window.originalSetItem=Storage.prototype.setItem; Storage.prototype.setItem=function(){throw new DOMException('Storage blocked','QuotaExceededError')};}")
                    page.locator('#market-finding-save').click()
                    expect(page.locator('#market-finding-status')).to_have_attribute('data-error', 'true')
                    require(len(items()) == 1, 'Failed storage write changed the finding list')
                    page.evaluate('() => {Storage.prototype.setItem=window.originalSetItem;}')
                    page.locator('#market-finding-save').click()
                    expect(page.locator('#market-finding-status')).to_contain_text('已保存')
                    expect(page.locator('#market-findings-count')).to_have_text('2 / 5')
                    checks.append('Storage failure is explicit and preserves prior findings; retry succeeds after storage recovery')

                    page.locator('#market-tab-relationships').click()
                    scatter_id = page.locator('#market-chart-select option').evaluate_all("nodes=>nodes.find(n=>n.value.includes('scatter')).value")
                    page.locator('#market-chart-select').select_option(scatter_id)
                    save('Scatter relationship observation')
                    scatter = items()[-1]['charts'][0]
                    require(scatter['type'] == 'scatter' and scatter['points_omitted'] and scatter['point_count'] > 0,
                            'Scatter scope is not explicit')
                    require('points' not in scatter and scatter.get('summary', {}).get('paired_rows', 0) > 0,
                            'Scatter evidence failed to retain aggregate statistics without raw points')
                    page.locator('#market-tab-cohorts').click()
                    save('Release cohort observation')
                    page.locator('#market-tab-rankings').click()
                    save('Observed ranking')
                    expect(page.locator('#market-findings-count')).to_have_text('5 / 5')
                    page.locator('#market-tab-overview').click()
                    prepare('Sixth distinct finding')
                    page.locator('#market-finding-save').click()
                    expect(page.locator('#market-finding-status')).to_have_attribute('data-error', 'true')
                    require(len(items()) == 5, 'Finding limit exceeded')
                    page.locator('[data-finding-remove]').first.click()
                    expect(page.locator('#market-findings-count')).to_have_text('4 / 5')
                    page.locator('#market-finding-save').click()
                    expect(page.locator('#market-finding-status')).to_contain_text('已保存')
                    expect(page.locator('#market-findings-count')).to_have_text('5 / 5')
                    checks.append('Scatter findings retain aggregate statistics without raw points; five-item limit requires explicit removal before adding another finding')

                    page.locator('#market-findings').screenshot(path=str(output / 'findings-desktop.png'))
                    page.set_viewport_size({'width': 390, 'height': 844})
                    prepare('Narrow layout capture')
                    require(page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Narrow layout overflows')
                    page.locator('#market-finding-capture').screenshot(path=str(output / 'finding-form-390px.png'))
                    page.locator('#market-findings').screenshot(path=str(output / 'findings-390px.png'))
                    require(not errors, f'JavaScript errors: {errors}')
                    checks.append('390px capture and saved findings stay within the viewport; no JavaScript errors')
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
