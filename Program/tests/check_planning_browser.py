"""Headless UI exercise: case filters, budgets, missing inputs, exports and stale responses."""
import json
import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src/demo'))
from server import make_server


def main():
    output=ROOT/'data/processed/planning_qa'
    output.mkdir(parents=True,exist_ok=True)
    server=make_server(SimpleNamespace(root=ROOT),0)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    errors=[]
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(channel='msedge',headless=True)
            page=browser.new_page(viewport={'width':1440,'height':1000},device_scale_factor=1)
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(f'http://127.0.0.1:{server.server_port}/planning')
            expect(page.locator('#case-count')).to_contain_text('10 個案例')
            expect(page.locator('.case-entry')).to_have_count(10)
            page.locator('#case-search').fill('TOEM')
            expect(page.locator('.case-entry')).to_have_count(1)
            page.locator('.case-entry summary').click()
            expect(page.locator('.case-entry table')).to_contain_text('1,500,000 SEK')
            page.locator('#case-library').screenshot(path=str(output/'cases-desktop.png'))
            with page.expect_download() as event: page.get_by_role('link',name='來源 CSV',exact=True).click()
            event.value.save_as(str(output/'sources.csv'))
            assert (output/'sources.csv').read_bytes()==(ROOT.parent/'Dataset/Development Cost Cases/sources.csv').read_bytes()
            page.locator('#case-search').fill('')
            page.locator('#case-platform').select_option('Android')
            expect(page.locator('.case-entry')).to_have_count(1)
            expect(page.locator('.case-entry')).to_contain_text('Hang Line')
            page.locator('#case-search').fill('zz-no-result')
            expect(page.locator('#case-status')).to_contain_text('沒有符合')
            page.locator('#case-search').fill('');page.locator('#case-platform').select_option('')
            page.locator('#calculate-budget').click()
            expect(page.locator('#budget-results')).to_be_hidden()
            assert not page.locator('#budget-form').evaluate('(f)=>f.checkValidity()')
            page.locator('#load-example').click();page.locator('#calculate-budget').click()
            expect(page.locator('#budget-results')).to_be_visible()
            expect(page.locator('#budget-metrics')).to_contain_text('176,000')
            expect(page.locator('#budget-metrics')).to_contain_text('320,000')
            expect(page.locator('#requirements')).to_contain_text('14.4')
            expect(page.locator('#requirements')).to_contain_text('4,400')
            expect(page.locator('#delay-table')).to_contain_text('209,000')
            page.locator('#budget-results').screenshot(path=str(output/'budget-desktop.png'))
            with page.expect_download() as event: page.locator('#budget-export').click()
            event.value.save_as(str(output/'budget-export.json'))
            exported=json.loads((output/'budget-export.json').read_text(encoding='utf-8'))
            assert exported['base']['cash_budget']==176000
            assert exported['request']['team'][1]['allocation']==0.5
            assert exported['data_kind']=='user_assumptions'
            page.locator('#net_unit_contribution').fill('0')
            expect(page.locator('#budget-results')).to_be_hidden()
            page.locator('#available_funds').fill('')
            page.locator('#calculate-budget').click()
            expect(page.locator('#requirements')).to_contain_text('沒有回本份數')
            expect(page.locator('#requirements')).to_contain_text('未提供資金')
            page.locator('#budget-currency').select_option('USD')
            expect(page.locator('#budget-status')).to_contain_text('未作匯率換算')
            expect(page.locator('#budget-results')).to_be_hidden()
            page.locator('#load-example').click()
            held=[]
            page.route('**/api/planning/budget',lambda route:held.append(route))
            page.locator('#calculate-budget').click()
            expect(page.locator('#calculate-budget')).to_be_disabled()
            page.locator('#budget-months').fill('15')
            assert len(held)==1
            held[0].continue_()
            expect(page.locator('#calculate-budget')).to_be_enabled()
            expect(page.locator('#budget-results')).to_be_hidden()
            page.unroute('**/api/planning/budget')
            page.locator('#calculate-budget').click()
            expect(page.locator('#budget-metrics')).to_contain_text('209,000')
            page.set_viewport_size({'width':390,'height':844})
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.locator('#budget-results').screenshot(path=str(output/'budget-mobile.png'))
            page.locator('#case-search').fill('Fall of Lazarus')
            page.locator('.case-entry summary').click()
            expect(page.locator('.case-entry table')).to_contain_text('166,717')
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.locator('#case-library').screenshot(path=str(output/'cases-mobile.png'))
            page.locator('button[type=reset]').click()
            expect(page.locator('#budget-results')).to_be_hidden()
            expect(page.locator('.team-row')).to_have_count(1)
            assert not errors,errors
            browser.close()
        print('Planning browser checks passed: case provenance/filter/download, budget arithmetic/export, missing values, stale responses, desktop/mobile layout.')
    finally:
        server.shutdown();server.server_close();thread.join()


if __name__=='__main__':main()
