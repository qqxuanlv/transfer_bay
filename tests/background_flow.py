"""Desktop drop anywhere, pairing consent, and native drop with the web windows gone."""
import hashlib,json,os,secrets,sys,time,subprocess,tempfile
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from playwright.sync_api import sync_playwright,expect

root=Path(__file__).resolve().parents[1];processes=[]
def post(url,key,op):
    req=Request(url+'/api/native',data=json.dumps(op).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+key})
    with urlopen(req,timeout=8) as r:return json.load(r)
def eventually(fn,limit=15):
    end=time.monotonic()+limit
    while time.monotonic()<end:
        if fn():return
        time.sleep(.12)
    assert fn(),'timed out: '+repr(fn)
def drop(p,selector,name,data):
    p.locator(selector).evaluate("""(el,[name,data])=>{const dt=new DataTransfer();dt.items.add(new File([new Uint8Array(data)],name));el.dispatchEvent(new DragEvent('drop',{bubbles:true,cancelable:true,dataTransfer:dt}))}""",[name,list(data)])
try:
    with tempfile.TemporaryDirectory() as work,sync_playwright() as w:
        apps=[]
        for i in range(2):
            home=Path(work)/str(i);home.mkdir();ui,key=secrets.token_hex(16),secrets.token_hex(16)
            cmd=[os.environ['TRANSFERBAY_ENGINE']] if os.environ.get('TRANSFERBAY_ENGINE') else [sys.executable,str(root/'server.py')]
            p=subprocess.Popen(cmd+['--port','0'],stdout=subprocess.PIPE,text=True,env={**os.environ,'HOME':str(home),'TRANSFERBAY_UI':ui,'TRANSFERBAY_NATIVE':key})
            processes.append(p);url='http://127.0.0.1:'+p.stdout.readline().strip().rsplit(':',1)[-1];apps.append((url,ui,key,home))
        browser=w.chromium.launch(executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args=['--no-proxy-server'])
        pages=[]
        for i,(url,ui,key,home) in enumerate(apps):
            p=browser.new_page(viewport={'width':980,'height':630},user_agent=['Macintosh','Windows NT 10.0'][i]);pages.append(p)
            p.goto(url+'/#desktop='+ui);expect(p.locator('#online')).to_have_text('局域网在线')
        a,b=pages
        drop(a,'header','拖入顶栏.txt',b'queued before approval')
        code=b.locator('#mycode').inner_text().replace(' ','')
        a.locator('#digits').fill(code);a.locator('#connect').click();expect(b.locator('#invite')).to_be_visible()
        inboxB=apps[1][3]/'Downloads/TransferBay 接收/来自 Mac'
        assert len(code)==6 and code.isascii() and code.isdigit()
        words=b.locator('#words').inner_text();assert ' · ' in words
        expect(a.locator('#pairhint')).to_contain_text(words)
        b.locator('#no').click()
        expect(a.locator('#problem')).to_contain_text('未接受')
        assert not inboxB.exists()
        a.locator('#connect').click();expect(b.locator('#invite')).to_be_visible()
        expect(a.locator('#pairhint')).to_contain_text(b.locator('#words').inner_text())
        assert not inboxB.exists()
        b.locator('#yes').click()
        target=inboxB/'拖入顶栏.txt';eventually(lambda:target.exists() and target.read_bytes()==b'queued before approval')
        # Drop another batch from the history route, without pressing a send/save button.
        a.locator('[data-view=history]').click()
        drop(a,'#logs','拖入顶栏.txt',b'duplicate');drop(a,'nav','尾件.bin',b'last file')
        eventually(lambda:(inboxB/'拖入顶栏 (1).txt').is_file() and (inboxB/'尾件.bin').is_file())
        assert (inboxB/'拖入顶栏 (1).txt').read_bytes()==b'duplicate'
        # Exercise the same copy, shortcut, persistence and clear actions as the desktop UI.
        a.locator('[data-view=home]').click()
        for page in (a,b):page.locator('#modeText').click()
        for sender,receiver,body in [(a,b,'第一行 🌿\n  <b>保留原文</b>'),(b,a,'收到\nSecond line')]:
            sender.locator('#textDraft').fill(body)
            sender.locator('#textDraft').press('Control+Enter')
            message=receiver.locator('#currentTexts .textRow').filter(has=receiver.locator('pre',has_text=body.split('\n')[0]))
            expect(message).to_have_count(1)
            assert message.locator('pre').text_content()==body
            receiver.bring_to_front()
            receiver.context.grant_permissions(['clipboard-read','clipboard-write'])
            message.get_by_role('button',name='复制').click()
            assert receiver.evaluate('navigator.clipboard.readText()')==body
        a.locator('[data-view=history]').click()
        a.locator('#historyText').click()
        expect(a.locator('#textLogs .textRow')).to_have_count(2)
        a.locator('#clearTexts').click()
        expect(a.locator('#textLogs .textRow')).to_have_count(0)
        a.locator('#historyFiles').click()
        expect(a.locator('#logs .row')).to_have_count(3)
        b.locator('[data-view=history]').click();expect(b.locator('#clearLog')).to_be_enabled();b.locator('#clearLog').click()
        expect(b.locator('#logs .row')).to_have_count(0);assert target.read_bytes()==b'queued before approval'
        b.reload();b.locator('[data-view=history]').click();b.locator('#historyText').click()
        expect(b.locator('#textLogs .textRow')).to_have_count(2)
        assert target.read_bytes()==b'queued before approval'
        for p in pages:p.close()
        url,_,key,home=apps[1]
        try:post(url,'wrong-key',{'op':'drop','paths':[str(target)]});assert False
        except HTTPError as e:assert e.code==403
        blob=os.urandom(364217);nativeFile=home/'桌面投递.bin';nativeFile.write_bytes(blob)
        post(url,key,{'op':'drop','paths':[str(nativeFile)]})
        post(url,key,{'op':'drop','paths':[str(nativeFile)]})
        inboxA=apps[0][3]/'Downloads/TransferBay 接收/来自 Windows'
        for name in ['桌面投递.bin','桌面投递 (1).bin']:
            saved=inboxA/name;eventually(lambda:saved.is_file() and saved.stat().st_size==len(blob))
            assert hashlib.sha256(saved.read_bytes()).digest()==hashlib.sha256(blob).digest()
        print('PASS: drop on header before consent, history/nav drops, auto-save, collision, clear without deletion, and two native background drops after both UI pages close')
        browser.close()
finally:
    for p in processes:p.terminate();p.wait(timeout=10)
