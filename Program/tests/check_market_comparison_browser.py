"""Focused comparison/drill-through UI checks against real historical data.

Run: uv run --locked --with playwright python -B tests/check_market_comparison_browser.py
Outputs use ignored data/processed/market_comparison_qa; imported state is temporary.
"""
import csv
import io
import json
import sys
import tempfile
import threading
import xml.etree.ElementTree as ET
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/demo"))
from server import ComparisonStore, make_server


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    output = ROOT / 'data/processed/market_comparison_qa'
    output.mkdir(parents=True, exist_ok=True)
    checks, errors = [], []
    report = {'passed': False, 'checks': checks, 'page_errors': errors}
    with tempfile.TemporaryDirectory(prefix='market-comparison-ui-') as folder:
        store = ComparisonStore(app_path=Path(folder))
        server = make_server(store, 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f'http://127.0.0.1:{server.server_port}'
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(channel='msedge', headless=True)
                try:
                    context = browser.new_context(viewport={'width': 1365, 'height': 1000}, accept_downloads=True)
                    page = context.new_page()
                    page.set_default_timeout(45000)
                    expect.set_options(timeout=45000)
                    page.on('pageerror', lambda error: errors.append(str(error)))

                    def api(path, payload):
                        response = context.request.post(base + path, data=payload)
                        require(response.ok, response.text())
                        return response.json()

                    response = context.request.get(base + '/api/market/options')
                    require(response.ok, response.text())
                    sources = {source['id']: source for source in response.json()['sources']}

                    def analysis(source='mobile', group='Adventure', compare_group=''):
                        return dict(source=source, version_id=sources[source]['version_id'],
                                    group=group, compare_group=compare_group, tag='',
                                    year_from=None, year_to=None, top_n=10, rank_metric='volume')

                    def records(payload, cohort='selected', tier='', q='', page_number=1, page_size=20, sort='title'):
                        return dict(analysis=payload, cohort=cohort, tier=tier, q=q,
                                    page=page_number, page_size=page_size, sort=sort)

                    page.goto(base + '/market')
                    expect(page.locator('#market-results')).to_be_visible()
                    page.locator('#market-tab-distribution').click()
                    expect(page.locator('#market-charts > article')).to_have_attribute('data-chart-id', 'outcome_tiers')
                    page.locator('#market-source').select_option('mobile')
                    expect(page.locator('#market-summary')).to_contain_text('221,806')
                    page.locator('#market-tab-distribution').click()
                    expect(page.locator('#market-charts > article')).to_have_attribute('data-chart-id', 'outcome_tiers')
                    page.locator('#market-charts rect[role="button"]').first.click()
                    expect(page.locator('#market-records-table')).to_be_visible()
                    expect(page.locator('#market-records-status')).to_contain_text('221,806')
                    page.locator('#market-records-close').click()
                    checks.append('Unfiltered distribution defaults to quantity tiers, whose bars open matching records')

                    page.locator('#market-group').select_option('Adventure')
                    expect(page.locator('#market-comparison-control')).to_be_visible()
                    require(page.locator('#market-compare-group option[value="Adventure"]').count() == 0,
                            'A group must not be its own named baseline')
                    page.locator('#market-apply').click()
                    expected = api('/api/market', analysis())
                    comparison = expected['comparison']
                    expect(page.locator('#market-charts > article')).to_have_attribute('data-chart-type', 'stacked_bar')
                    expect(page.locator('#market-comparison')).to_be_visible()
                    expect(page.locator('#market-summary')).to_contain_text('15,795')
                    expect(page.locator('.market-cohort-card[data-cohort="selected"]')).to_contain_text('15,795')
                    expect(page.locator('.market-cohort-card[data-cohort="baseline"]')).to_contain_text('206,011')
                    expect(page.locator('#market-comparison-context')).to_contain_text('0 款重疊')
                    segment = page.locator('#market-charts rect[data-cohort="selected"][data-tier="M3_100k_plus"]')
                    segment.focus()
                    expect(page.locator('#market-charts [role="tooltip"]')).to_be_visible()
                    expect(page.locator('#market-charts [role="tooltip"]')).to_contain_text('2,487 / 15,795')
                    page.locator('#market-analysis-panel').screenshot(path=str(output / 'adventure-comparison-desktop.png'))
                    segment.press('Enter')
                    expect(page.locator('#market-records-table')).to_be_visible()
                    expect(page.locator('#market-records-status')).to_contain_text('2,487')
                    expect(page.locator('#market-records-status')).to_contain_text('15,795')
                    expect(page.locator('#market-records-table tbody tr')).to_have_count(20)
                    selected_records = api('/api/market/records', records(analysis(), tier='M3_100k_plus'))
                    expect(page.locator('#market-records-table tbody tr').first).to_contain_text(selected_records['rows'][0]['app_id'])
                    checks.append('Adventure compares two independently denominated cohorts; focus tooltip and Enter drill to exact high-install records')

                    # Force a valid but far-away page request to verify the UI uses
                    # the server-clamped page instead of its requested page.
                    page.route('**/api/market/records', lambda route: route.continue_(post_data=json.dumps(
                        {**route.request.post_data_json, 'page': 999999})))
                    page.locator('#market-records-next').click()
                    expect(page.locator('#market-records-page')).to_have_text('第 125 / 125 頁')
                    expect(page.locator('#market-records-next')).to_be_disabled()
                    expect(page.locator('#market-records-table tbody tr')).to_have_count(7)
                    page.unroute('**/api/market/records')
                    ident = selected_records['rows'][0]['app_id']
                    page.locator('#market-records-q').fill(ident)
                    expect(page.locator('#market-records-table')).to_be_hidden()
                    page.locator('#market-records-search-button').click()
                    matching = api('/api/market/records', records(analysis(), tier='M3_100k_plus', q=ident))
                    expect(page.locator('#market-records-table tbody tr')).to_have_count(len(matching['rows']))
                    expect(page.locator('#market-records-table')).to_contain_text(ident)
                    page.locator('#market-records-q').fill('')
                    page.locator('#market-records-sort').select_option('volume')
                    sorted_records = api('/api/market/records', records(analysis(), tier='M3_100k_plus', sort='volume'))
                    expect(page.locator('#market-records-table tbody tr').first).to_contain_text(sorted_records['rows'][0]['app_id'])
                    page.locator('#market-records-size').select_option('50')
                    expect(page.locator('#market-records-table tbody tr')).to_have_count(50)
                    page.locator('#market-records-panel').screenshot(path=str(output / 'adventure-records-desktop.png'))
                    checks.append('Record search, quantity sorting, page size and server-clamped pagination preserve the selected cohort/tier')

                    page.locator('#market-records-close').click()
                    with page.expect_download() as event:
                        page.locator('#market-export-json').click()
                    event.value.save_as(str(output / 'adventure-analysis.json'))
                    exported = json.loads((output / 'adventure-analysis.json').read_text(encoding='utf-8'))
                    require(exported['comparison'] == comparison, 'JSON comparison differs from API evidence')
                    require(exported['provenance']['filtered_rows'] == 15795, 'Selected KPIs must not include baseline')
                    with page.expect_download() as event:
                        page.locator('#market-export-csv').click()
                    event.value.save_as(str(output / 'adventure-comparison.csv'))
                    rows = list(csv.DictReader(io.StringIO((output / 'adventure-comparison.csv').read_text(encoding='utf-8-sig'))))
                    for cohort in ('selected', 'baseline'):
                        sample = comparison[cohort]
                        row = next(row for row in rows if row['record_type'] == 'comparison_cohort' and row['cohort'] == cohort)
                        require(int(row['cohort_n']) == sample['n'], 'CSV cohort denominator differs')
                        require(json.loads(row['provenance_json'])['cohort'] == cohort, 'CSV provenance loses cohort identity')
                        statistics = [row for row in rows if row['record_type'] == 'comparison_statistic' and row['cohort'] == cohort]
                        require(len(statistics) == 3, 'Android CSV should contain Q1, median and Q3')
                        require(all(int(row['n']) == sample['statistics']['volume_lower']['n'] for row in statistics), 'CSV statistic valid-n differs')
                        tiers = [json.loads(row['record_json']) for row in rows if row['record_type'] == 'comparison_tier' and row['cohort'] == cohort]
                        require(tiers == sample['tiers'], 'CSV tier counts/percentages differ')
                    with page.expect_download() as event:
                        page.locator('#market-charts .game-chart-actions button').click()
                    event.value.save_as(str(output / 'adventure-comparison.svg'))
                    svg = ET.fromstring((output / 'adventure-comparison.svg').read_bytes())
                    text = ' '.join(svg.itertext())
                    require('15,795' in text and '206,011' in text, 'SVG export loses cohort sizes')
                    require(not any(item.tag.endswith('script') for item in svg.iter()), 'SVG should not embed scripts')
                    checks.append('JSON, typed CSV and self-contained SVG retain separate cohort denominators, quartiles and tier evidence')

                    page.locator('[data-records-cohort="baseline"]').click()
                    expect(page.locator('#market-records-status')).to_contain_text('206,011')
                    held = []
                    page.route('**/api/market/records', lambda route: held.append(route))
                    page.locator('#market-records-q').fill('delayed')
                    page.locator('#market-records-search-button').click()
                    expect(page.locator('#market-records-search-button')).to_be_disabled()
                    page.locator('#market-group').select_option('Puzzle')
                    expect(page.locator('#market-records-panel')).to_be_hidden()
                    expect(page.locator('#market-results')).to_be_hidden()
                    require(len(held) == 1, 'Expected one held stale record request')
                    held[0].fulfill(json=selected_records)
                    page.unroute('**/api/market/records')
                    page.locator('#market-apply').click()
                    expect(page.locator('#market-summary')).to_contain_text('34,175')
                    expect(page.locator('#market-records-panel')).to_be_hidden()
                    checks.append('Dirty analysis filters cancel and clear record results; late old requests cannot reopen stale tables')

                    page.locator('#market-source').select_option('pc')
                    expect(page.locator('#market-summary')).to_contain_text('51,152')
                    page.locator('#market-group').select_option('Action')
                    page.locator('#market-compare-group').select_option('Adventure')
                    page.locator('#market-apply').click()
                    steam = api('/api/market', analysis('pc', 'Action', 'Adventure'))
                    expect(page.locator('#market-comparison-context')).to_contain_text(f"{steam['comparison']['overlap_count']:,} 款重疊")
                    require(steam['comparison']['overlap_count'] > 0, 'Steam named genres should disclose their overlap')
                    page.locator('#market-chart-select').select_option('group_volume_median')
                    expect(page.locator('#market-charts rect[role="button"]')).to_have_count(4)
                    page.locator('#market-charts rect[role="button"]').last.press('Enter')
                    expect(page.locator('#market-records-context')).to_contain_text('Adventure')
                    expect(page.locator('#market-records-table')).to_be_visible()
                    checks.append('Named Steam baselines disclose shared games; median chart bars drill to their own cohort')

                    page.locator('#market-source').select_option('revenue')
                    expect(page.locator('#market-summary')).to_contain_text('1,500')
                    expect(page.locator('#market-records-panel')).to_be_hidden()
                    page.locator('#market-tab-distribution').click()
                    expect(page.locator('#market-charts > article')).to_have_attribute('data-chart-type', 'histogram')
                    page.locator('#market-group').select_option('Action')
                    page.locator('#market-apply').click()
                    expect(page.locator('#market-comparison')).to_be_visible()
                    expect(page.locator('#market-charts > article')).to_have_attribute('data-chart-type', 'bar')
                    expect(page.locator('.market-cohort-card[data-cohort="selected"]')).to_contain_text('已知估計營收')
                    expect(page.locator('.market-cohort-card[data-cohort="selected"]')).not_to_contain_text('已知數量分層')
                    page.locator('#market-charts rect[role="button"]').last.click()
                    expect(page.locator('#market-records-table')).to_be_visible()
                    expect(page.locator('#market-records-table thead')).to_contain_text('營收')
                    page.locator('#market-records-close').click()
                    page.locator('#market-view-records').click()
                    expect(page.locator('#market-records-context')).to_contain_text('Action')
                    checks.append('Revenue defaults to histogram, supports two-cohort median comparison and inspectable selected/baseline records')

                    for width in (390, 320):
                        page.set_viewport_size({'width': width, 'height': 844})
                        if not page.evaluate('document.documentElement.scrollWidth <= innerWidth'):
                            page.screenshot(path=str(output / f'overflow-{width}px.png'), full_page=True)
                            overflow = page.evaluate("[...document.querySelectorAll('body > *, header > *, main > *')].filter(n=>n.getBoundingClientRect().right>innerWidth).map(n=>({tag:n.tagName,id:n.id,cls:n.className,right:n.getBoundingClientRect().right}))")
                            raise RuntimeError(f'Outer horizontal overflow at {width}px: {overflow}')
                        page.locator('#market-records-panel').screenshot(path=str(output / f'records-{width}px.png'))
                        page.locator('#market-records-close').click()
                        page.locator('#market-analysis-panel').screenshot(path=str(output / f'comparison-{width}px.png'))
                        page.locator('#market-view-records').click()
                        expect(page.locator('#market-records-table')).to_be_visible()
                    require(not errors, f'JavaScript errors: {errors}')
                    checks.append('390px and 320px layouts retain local chart/table scrolling without page overflow; no JavaScript errors')
                    report['passed'] = True
                finally:
                    browser.close()
        except Exception as exc:
            report['error'] = f'{type(exc).__name__}: {exc}'
            raise
        finally:
            server.shutdown(); server.server_close(); thread.join(); store.db.close()
            (output / 'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
