"""Change the preferred port without disrupting service; restart and pair by IP alone."""
import os,sys,tempfile,subprocess,socket,json
from pathlib import Path
from urllib.request import Request,urlopen,build_opener,ProxyHandler
from urllib.error import HTTPError
from playwright.sync_api import sync_playwright,expect
base=Path(__file__).resolve().parents[1]
servers=[];net=build_opener(ProxyHandler({}))
def launch(home,override=False):
    cmd=[os.environ['TRANSFERBAY_ENGINE']] if os.environ.get('TRANSFERBAY_ENGINE') else [sys.executable,str(base/'server.py')]
    p=subprocess.Popen(cmd+(['--port','0'] if override else []),stdout=subprocess.PIPE,text=True,env={**os.environ,'HOME':home})
    servers.append(p);port=int(p.stdout.readline().strip().rsplit(':',1)[-1])
    return p,port
def api(port,path,data=None,token=''):
    req=Request(f'http://127.0.0.1:{port}/api/'+path,data=json.dumps(data).encode() if data is not None else None,headers={'Content-Type':'application/json','Authorization':'Bearer '+token})
    with net.open(req,timeout=5) as r:return json.load(r)
try:
    with tempfile.TemporaryDirectory() as home,sync_playwright() as pw:
        with socket.socket() as s:s.bind(('127.0.0.1',0));custom=s.getsockname()[1]
        p,port=launch(home,True)
        browser=pw.chromium.launch(executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args=['--no-proxy-server'])
        page=browser.new_page();page.goto(f'http://127.0.0.1:{port}/')
        page.locator('#settingsButton').click();expect(page.locator('#portField')).to_have_value('')
        page.locator('#portField').fill(str(custom));page.locator('#savePort').click();expect(page.locator('#settings')).to_be_hidden()
        t=api(port,'device',{'name':'test'})['token']
        assert api(port,'settings/port',token=t)=={'port':custom,'active':port,'default':8765}
        for invalid in (-1,0,65536,1.5,True):
            try:api(port,'settings/port',{'port':invalid},t);raise AssertionError(invalid)
            except HTTPError as e:assert e.code==400
        p.terminate();p.wait()
        b,portB=launch(home);assert portB==custom
        a,portA=launch(home);assert portA!=custom
        bt=api(portB,'device',{'name':'B'})['token'];at=api(portA,'device',{'name':'A'})['token'];st=api(portB,'state',token=bt)
        host=st['addresses'][0].split(':')[0]
        assert api(portA,'discover',{'code':st['code'],'address':host},at)['url']==f'http://{host}:{custom}'
        assert api(portA,'discover',{'code':st['code'],'address':f'{host}:{custom}'},at)['url']==f'http://{host}:{custom}'
        page.goto(f'http://127.0.0.1:{portA}/');page.locator('#settingsButton').click();page.locator('#portField').fill('');page.locator('#savePort').click()
        expect(page.locator('#settings')).to_be_hidden()
        assert api(portA,'settings/port',token=at)['port']==8765
        browser.close();print('PASS: settings UI, invalid values, live session preserved, persisted restart, occupied port fallback, IP-only and explicit-port requests, blank resets default')
finally:
    for p in servers:
        if p.poll() is None:p.terminate();p.wait(timeout=8)
