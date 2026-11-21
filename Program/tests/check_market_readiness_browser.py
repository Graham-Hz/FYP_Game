"""Real isolated CSV versions plus explicit missing-field response fixtures."""
import csv
import io
import json
import sys
import tempfile
import threading
from pathlib import Path

from playwright.sync_api import expect, sync_playwright
from market_browser_controls import market_control

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src/demo'))
from server import ComparisonStore, make_server
from test_csv_import import metadata, mobile, pc, raw


def main():
    output = ROOT / 'data/processed/market_readiness_qa'
    output.mkdir(parents=True, exist_ok=True)
    checks, errors = [], []
    report = {'passed': False, 'checks': checks, 'page_errors': errors}
    with tempfile.TemporaryDirectory(prefix='market-readiness-') as folder:
        store = ComparisonStore(app_path=Path(folder))
        missing_date = mobile()
        missing_id = store.repository.save(raw([missing_date]), metadata())['version_id']
        first = mobile(); second = mobile(); second.update(app_id='example.two')
        constant_id = store.repository.save(raw([first, second]), metadata())['version_id']
        a = pc(); a.update(app_id='1001', release_date='2018-01-01')
        b = pc(); b.update(app_id='1002', release_date='2020-01-01')
        pc_id = store.repository.save(raw([a, b], 'pc'), metadata('pc'))['version_id']
        server = make_server(store, 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        base = f'http://127.0.0.1:{server.server_port}'
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(channel='msedge', headless=True)
                try:
                    context = browser.new_context(viewport={'width': 1365, 'height': 1000}, accept_downloads=True)
                    page = context.new_page(); page.set_default_timeout(45000); expect.set_options(timeout=45000)
                    page.on('pageerror', lambda e: errors.append(str(e)))
                    page.goto(base + '/market#relationships')
                    expect(page.locator('#market-section-title')).to_contain_text('關聯')
                    expect(page.locator('[data-market-section="relationships"]')).to_have_attribute('aria-current', 'page')
                    expect(page.locator('#market-analysis-tabs')).to_be_hidden()
                    page.locator('[data-market-section="distribution"]').click()
                    expect(page).to_have_url(base + '/market#distribution')
                    page.go_back()
                    expect(page.locator('#market-section-title')).to_contain_text('關聯')
                    page.go_forward()
                    expect(page.locator('#market-section-title')).to_contain_text('多數')
                    market_control(page, '#market-source').select_option('mobile')
                    expect(page.locator('#market-summary')).to_contain_text('221,806')
                    market_control(page, '#market-group').select_option('Adventure')
                    expect(page.locator('[data-market-section="cohorts"]')).to_have_attribute('data-availability', 'pending')
                    market_control(page, '#market-apply').click()
                    expect(page.locator('#market-charts > article[data-chart-id="cohort_comparison"]')).to_be_visible()
                    expect(page.locator('#market-charts svg')).to_be_visible()
                    expect(page.locator('#market-charts svg')).to_contain_text('樣本 15,795 款')
                    selected=page.locator('#market-charts rect[data-cohort="selected"][data-tier="M3_100k_plus"]')
                    baseline=page.locator('#market-charts rect[data-cohort="baseline"][data-tier="M3_100k_plus"]')
                    selected.focus()
                    baseline.dispatch_event('pointerover',{'clientX':100,'clientY':100})
                    page.locator('#market-charts svg').dispatch_event('pointerleave',{'clientX':100,'clientY':100})
                    expect(page.locator('#market-charts [role="tooltip"]')).to_contain_text('2,487 / 15,795')
                    # Real mouse movement remains usable while a mark has focus.
                    page.mouse.move(0,0); baseline.hover()
                    expect(page.locator('#market-charts [role="tooltip"]')).to_contain_text('34,008 / 206,011')
                    selected.focus(); selected.press('Escape')
                    expect(page.locator('#market-charts [role="tooltip"]')).to_be_hidden()
                    expect(page.locator('#market-comparison')).to_contain_text('此數值有資料的遊戲：15,795 款')
                    page.locator('#market-reading-guide summary').click()
                    expect(page.locator('#market-reading-guide')).to_contain_text('不是精確下載量')
                    page.locator('#market-analysis-panel').screenshot(path=str(output / 'historical-readable.png'))
                    checks.append('Direct section entry, sidebar navigation and browser back/forward preserve section; dirty filters mark readiness pending; sample labels and glossary explain actual historical counts.')

                    store.activate('mobile', missing_id)
                    # Missing release dates are excluded by the current CSV contract.
                    # Simulate only this API condition to test UI handling without
                    # weakening eligibility or changing historical source records.
                    def no_dates(route):
                        response=route.fetch(); data=response.json()
                        for chart in data['charts']:
                            if chart['id'] in ['release_count','release_volume_median','price_outcome_scatter']:
                                chart['rows']=[];chart['points']=[]
                                scatter=chart['id']=='price_outcome_scatter'
                                chart['description']='此測試回應的發售日期缺漏：無法計算觀測距發售日數，沒有完整配對。' if scatter else '此測試回應沒有有效發售日期，未產生發售年份／月份的分組數值。'
                                if scatter: chart['summary']={'paired_rows':0,'displayed_rows':0,'spearman_rho':None}
                                chart['availability']={'status':'unavailable','reason':'沒有同時包含兩個軸所需資料的遊戲。' if scatter else '目前沒有有效發售日期，無法按年份／月份分組。','action':'補充有效發售日期後重新分析。','valid_rows':0,'total_rows':1,'requirements':['同一款遊戲須有有效發售日期、觀測日期及安裝量下限。'] if scatter else ['按發售年份／月份分組需要有效發售日期。']+(['同一款遊戲還須有安裝量下限，才能計算中位數。'] if chart['id']=='release_volume_median' else [])}
                        route.fulfill(response=response,json=data)
                    page.route('**/api/market',no_dates)
                    market_control(page, '#market-refresh').click()
                    expect(page.locator('#market-summary')).to_contain_text('1')
                    page.locator('[data-market-section="cohorts"]').click()
                    expect(page.locator('[data-market-section="cohorts"]')).to_have_attribute('data-availability', 'unavailable')
                    expect(page.locator('#market-charts .game-chart-readiness')).to_contain_text('有效發售日期')
                    expect(page.locator('#market-charts svg')).to_have_count(0)
                    expect(page.locator('#market-charts .game-chart-actions')).to_have_count(0)
                    expect(page.locator('#market-finding-capture')).to_be_hidden()
                    expect(page.locator('#market-chart-select option')).to_have_count(2)
                    page.locator('#market-charts .game-chart-readiness summary').click()
                    expect(page.locator('#market-charts .game-chart-readiness')).to_contain_text('需要哪些資料')
                    page.locator('#market-analysis-panel').screenshot(path=str(output / 'missing-release-date.png'))
                    page.locator('[data-market-section="relationships"]').click()
                    page.locator('#market-chart-select').select_option('price_outcome_scatter')
                    expect(page.locator('#market-charts .game-chart-readiness')).to_contain_text('沒有同時包含兩個軸')
                    expect(page.locator('#market-charts svg')).to_have_count(0)
                    with page.expect_download() as event: page.locator('#market-export-csv').click()
                    csv_path=output/'missing-date-chart-data.csv'; event.value.save_as(str(csv_path))
                    rows=list(csv.DictReader(io.StringIO(csv_path.read_text(encoding='utf-8-sig'))))
                    unavailable=next(row for row in rows if row['record_type']=='chart_metadata' and row['chart_id']=='release_count')
                    assert json.loads(unavailable['record_json'])['availability']['status']=='unavailable'
                    assert not any(row['record_type']=='chart_value' and row['chart_id']=='release_count' for row in rows)
                    assert sum(row['record_type']=='chart_metadata' for row in rows)==14
                    checks.append('Explicit missing-date response fixture leaves release/scatter choices visible with cause/action and no blank SVG/download/finding; CSV retains all 14 chart descriptions. The current importer excludes missing-date rows.')

                    page.unroute('**/api/market',no_dates)
                    store.activate('mobile', constant_id)
                    market_control(page, '#market-refresh').click()
                    expect(page.locator('#market-summary')).to_contain_text('2')
                    page.locator('[data-market-section="relationships"]').click()
                    page.locator('#market-chart-select').select_option('price_outcome_scatter')
                    expect(page.locator('#market-charts .game-chart-readiness')).to_contain_text('全部相同')
                    expect(page.locator('#market-charts svg')).to_be_visible()
                    expect(page.locator('#market-charts .game-chart-statistics')).to_contain_text('無法計算')
                    expect(page.locator('#market-charts .game-chart-statistics')).to_contain_text('兩個數值均有資料：2 款')
                    expect(page.locator('#market-charts .game-chart-reading-help')).to_contain_text('不是因果或收益預測')
                    page.locator('#market-analysis-panel').screenshot(path=str(output / 'constant-pairs.png'))
                    page.locator('[data-market-section="distribution"]').click()
                    page.locator('#market-chart-select').select_option('genre_boxplot')
                    expect(page.locator('#market-charts .game-chart-readiness')).to_contain_text('5')
                    expect(page.locator('#market-charts svg')).to_have_count(0)
                    checks.append('Constant valid pairs remain visible with no-correlation explanation; too-small boxplot groups explain the display requirement instead of drawing an empty plot.')

                    # One populated selected group and an empty comparison stays partial.
                    market_control(page, '#market-group').select_option('Puzzle'); market_control(page, '#market-apply').click()
                    expect(page.locator('#market-charts .game-chart-readiness')).to_contain_text('所選組 2 款；對照組 0 款')
                    expect(page.locator('#market-charts svg')).to_be_visible()
                    checks.append('A comparison with one empty cohort displays separate valid counts and an explicit inability to interpret group differences.')

                    store.activate('pc', pc_id)
                    market_control(page, '#market-refresh').click()
                    expect(page.locator('#market-summary')).to_contain_text('2')
                    market_control(page, '#market-source').select_option('pc')
                    expect(page.locator('#market-summary')).to_contain_text('2')
                    market_control(page, '#market-year-from').fill('2019'); market_control(page, '#market-year-to').fill('2019')
                    market_control(page, '#market-apply').click()
                    expect(page.locator('#market-empty')).to_be_visible()
                    expect(page.locator('[data-market-section="overview"]')).to_have_attribute('data-availability', 'unavailable')
                    page.locator('[data-market-section="distribution"]').click()
                    expect(page.locator('#market-charts svg')).to_have_count(0)
                    expect(page.locator('#market-finding-capture')).to_be_hidden()
                    expect(page.locator('#market-export-csv')).to_be_disabled()
                    expect(page.locator('#market-export-json')).to_be_enabled()
                    page.set_viewport_size({'width':390,'height':844})
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                    page.locator('#market-analysis-panel').screenshot(path=str(output / 'empty-mobile.png'))
                    checks.append('A real empty year filter suppresses zero-filled tier plots and saving while preserving an explanatory JSON export; 390px layout has no document overflow.')
                    assert not errors, errors
                    report['passed']=True
                finally: browser.close()
        finally:
            server.shutdown();server.server_close();thread.join();store.db.close()
            (output/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__': main()
