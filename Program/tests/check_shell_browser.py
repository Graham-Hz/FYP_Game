"""Consistent shared navigation, responsive access, and same-tab planning state."""
import json
from pathlib import Path
import sys
import tempfile
import threading

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src/demo'))
from server import ComparisonStore, make_server


def main():
    output = ROOT / 'data/processed/shell_qa'
    output.mkdir(parents=True, exist_ok=True)
    checks, errors = [], []
    report = {'passed': False, 'checks': checks, 'page_errors': errors}
    with tempfile.TemporaryDirectory(prefix='shell-browser-') as folder:
        server = make_server(ComparisonStore(app_path=Path(folder)), 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(channel='msedge', headless=True)
                try:
                    page = browser.new_page(viewport={'width': 1440, 'height': 1000})
                    page.set_default_timeout(45000)
                    expect.set_options(timeout=45000)
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    base = f'http://127.0.0.1:{server.server_port}'
                    for path, active in [('/market', 'overview'), ('/', 'comparison'), ('/revenue', 'revenue'), ('/planning', 'budget'), ('/plan', 'summary')]:
                        page.goto(base + path, wait_until='networkidle')
                        expect(page.locator('#app-sidebar')).to_be_visible()
                        expect(page.locator('.app-nav-link[aria-current="page"]')).to_have_count(1)
                        expect(page.locator(f'[data-shell-link="{active}"]')).to_have_attribute('aria-current', 'page')
                        expect(page.locator('.module-nav')).to_have_count(0)
                        expect(page.locator('.workflow-steps')).to_have_count(0)
                        expect(page.locator('.app-nav-group h2')).to_have_text(['資料分析', '開發規劃'])
                        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                        assert page.locator('main').bounding_box()['x'] == 254
                        assert page.locator('.app-header').bounding_box()['height'] == 74
                        assert page.evaluate('sessionStorage.length') == 0
                        page.screenshot(path=str(output / f'{active}-desktop.png'))
                    checks.append('Five routes share sidebar groups, header geometry, link styles and one current item; old navigation removed; initial navigation writes no session state.')
                    page.goto(base + '/revenue#reference-panel', wait_until='networkidle')
                    expect(page.locator('[data-shell-link="references"]')).to_have_attribute('aria-current', 'page')
                    expect(page.locator('#reference-panel')).to_have_attribute('open', '')
                    page.locator('[data-shell-link="revenue"]').click()
                    expect(page.locator('[data-shell-link="revenue"]')).to_have_attribute('aria-current', 'page')
                    checks.append('Reference step opens its disclosure directly and is distinct from revenue analysis current state.')
                    page.goto(base + '/market#distribution', wait_until='networkidle')
                    expect(page.locator('[data-market-section="distribution"]')).to_have_attribute('aria-current', 'page')
                    page.evaluate("GameShell.setMarketSections([{id:'cohorts',status:'unavailable',reason:'No release dates supplied.'}])")
                    expect(page.locator('[data-market-section="cohorts"]')).to_contain_text('資料不足')
                    expect(page.locator('[data-market-section="cohorts"]')).to_have_attribute('title', 'No release dates supplied.')
                    assert not page.locator('[data-market-section="cohorts"]').is_disabled()
                    page.locator('[data-market-section="cohorts"]').click()
                    expect(page).to_have_url(base + '/market#cohorts')
                    expect(page.locator('[data-market-section="cohorts"]')).to_have_attribute('aria-current', 'page')
                    checks.append('Analysis hash links remain navigable when unavailable so reasons can be inspected; current item follows the chosen section.')
                    page.set_viewport_size({'width':390, 'height':844})
                    expect(page.locator('.app-menu-toggle')).to_be_visible()
                    assert page.locator('#app-sidebar').evaluate('n => n.inert')
                    assert not page.locator('main').evaluate('n => n.inert')
                    page.locator('.app-menu-toggle').click()
                    expect(page.locator('.app-menu-toggle')).to_have_attribute('aria-expanded', 'true')
                    expect(page.locator('#app-sidebar')).to_have_attribute('aria-modal', 'true')
                    expect(page.locator('#app-sidebar')).to_have_css('transform', 'matrix(1, 0, 0, 1, 0, 0)')
                    assert page.locator('#app-sidebar').bounding_box()['x'] >= 0
                    assert page.locator('#app-sidebar').bounding_box()['width'] == 300
                    expect(page.locator('.app-sidebar-close')).to_be_focused()
                    page.keyboard.press('Shift+Tab')
                    expect(page.locator('[data-shell-link="summary"]')).to_be_focused()
                    page.keyboard.press('Tab')
                    expect(page.locator('.app-sidebar-close')).to_be_focused()
                    assert page.locator('main').evaluate('n => n.inert')
                    page.screenshot(path=str(output/'mobile-menu.png'), animations='disabled')
                    page.keyboard.press('Escape')
                    expect(page.locator('.app-menu-toggle')).to_be_focused()
                    expect(page.locator('.app-menu-toggle')).to_have_attribute('aria-expanded', 'false')
                    assert not page.locator('main').evaluate('n => n.inert')
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                    page.locator('.app-menu-toggle').click()
                    page.locator('[data-market-section="overview"]').click()
                    expect(page.locator('.app-menu-toggle')).to_have_attribute('aria-expanded', 'false')
                    expect(page.locator('[data-market-section="overview"]')).to_have_attribute('aria-current', 'page')
                    page.screenshot(path=str(output/'market-mobile.png'), animations='disabled')
                    checks.append('390px drawer has inert background, focus wrapping, Escape/focus restoration and close-on-navigation; content remains accessible without overflow.')
                    page.set_viewport_size({'width': 1440, 'height': 1000})
                    page.emulate_media(media='print')
                    expect(page.locator('#app-sidebar')).to_be_hidden()
                    expect(page.locator('.app-header')).to_be_hidden()
                    assert page.locator('main').bounding_box()['x'] == 0
                    checks.append('Print layout removes sidebar/header and restores full content width.')
                    assert not errors, errors
                    report['passed'] = True
                finally:
                    browser.close()
        except Exception as exc:
            report['error'] = f'{type(exc).__name__}: {exc}'
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()
    (output/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True,indent=2))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
