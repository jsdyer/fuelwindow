"""Exercise the built application at its project subpath in Chromium."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json,os,shutil,tempfile,threading
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
class QuietHandler(SimpleHTTPRequestHandler):
 def log_message(self,*args):pass
def main():
 screenshots=ROOT/'browser-checks';screenshots.mkdir(exist_ok=True)
 with tempfile.TemporaryDirectory() as temporary:
  shutil.copytree(ROOT/'dist',Path(temporary)/'fuelwindow')
  server=ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=temporary));threading.Thread(target=server.serve_forever,daemon=True).start()
  try:
   with sync_playwright() as p:
    options={}
    executable=os.environ.get('CHROMIUM_PATH')
    if executable:options['executable_path']=executable
    browser=p.chromium.launch(**options)
    page=browser.new_page(viewport={'width':1280,'height':1000});errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(f'http://127.0.0.1:{server.server_port}/fuelwindow/')
    page.locator('#prices tr').first.wait_for()
    assert page.locator('#prices tr').count()==21
    assert '156.0' in page.locator('#price-range').inner_text()
    page.locator('#litres').fill('50');page.locator('#distance').fill('250');page.locator('#consumption').fill('8')
    assert '$78.00' in page.locator('#fill').inner_text()
    assert '$31.20' in page.locator('#trip').inner_text()
    page.locator('#price').select_option('pei-island-furnace-delivery')
    assert 'Up to' in page.locator('#price-range').inner_text()
    assert not page.locator('#trip-card').is_visible()
    assert 'maximum' in page.locator('#change').inner_text()
    page.locator('#plan-name').fill('<img src=x onerror=alert(1)>')
    page.locator('#save').click();assert page.locator('#saved article').count()==1
    assert page.locator('img').count()==0
    page.reload();page.locator('#saved article').wait_for();assert '2026-' in page.locator('#saved').inner_text()
    with page.expect_download() as event:page.locator('#export').click()
    path=Path(temporary)/'plans.json';event.value.save_as(path)
    exported=json.loads(path.read_text());assert exported['plans'][0]['price']['min'] is None
    page.locator('#clear').click();assert page.locator('#saved article').count()==0
    page.locator('#import').set_input_files(str(path));page.locator('#saved article').wait_for()
    page.locator('#filter').fill('Zone 6');assert page.locator('#prices tr').count()==2
    page.locator('#litres').fill('-1');assert page.locator('#save').is_disabled()
    page.locator('#litres').fill('50')
    page.screenshot(path=str(screenshots/'desktop.png'),full_page=True)
    page.set_viewport_size({'width':390,'height':844})
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
    page.screenshot(path=str(screenshots/'mobile.png'),full_page=True)
    assert not errors,errors
    browser.close()
   print('Browser checks passed: subpath, source data, calculations, safe saved plans, reload, JSON export/import and mobile layout')
  finally:server.shutdown()
if __name__=='__main__':main()
