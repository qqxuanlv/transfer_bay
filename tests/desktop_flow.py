"""Two servers and isolated Chromium clients; exercise discovery, consent and bytes."""
import os,sys,subprocess,tempfile,hashlib,urllib.request,json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
root=Path(__file__).resolve().parents[1]
binary=os.environ.get('FEIDU_SERVER')
servers=[]
homes=tempfile.TemporaryDirectory();home_dirs=[]
def start(silent=False):
    cmd=[binary] if binary else [sys.executable,str(root/'server.py')]
    if silent:
        cmd=[sys.executable,'-c',"import discovery,runpy; discovery.listen=lambda *args:None; runpy.run_module('server',run_name='__main__')"]
    h=Path(homes.name)/str(len(servers));h.mkdir();home_dirs.append(h)
    p=subprocess.Popen(cmd+['--port','0'],stdout=subprocess.PIPE,text=True,env={**os.environ,'HOME':str(h)});servers.append(p)
    port=p.stdout.readline().strip().rsplit(':',1)[-1]
    return 'http://127.0.0.1:'+port
try:
    blocked=os.environ.get('FEIDU_TEST_BLOCK_UDP')=='1'
    a,b=start(),start(silent=blocked)
    with sync_playwright() as pw,tempfile.TemporaryDirectory() as temp:
        browser=pw.chromium.launch(executable_path=os.environ.get('CHROME','/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'),args=['--no-proxy-server'])
        one=browser.new_page(viewport={'width':1200,'height':828},accept_downloads=True);two=browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)",accept_downloads=True)
        for page,url in [(one,a),(two,b)]:
            page.goto(url);expect(page.locator('#online')).to_have_text('局域网在线')
        if not blocked:one.screenshot(path=str(root/'release/工作台预览.png'))
        code=two.locator('#mycode').inner_text().replace(' ','')
        legacy=two.locator('#legacy').text_content().split('：')[-1]
        one.locator('#digits').fill(legacy if blocked else code);one.locator('#connect').click()
        if blocked:
            expect(one.locator('#problem')).to_contain_text('未发现对方设备')
            address=two.locator('#lan').inner_text().split(' / ')[0]
            one.locator('#address').fill(address)
            wrong=next(c for c in ('012345','123456','369258') if c not in (legacy,one.locator('#legacy').text_content().split('：')[-1]))
            one.locator('#digits').fill(wrong);one.locator('#connect').click()
            expect(one.locator('#problem')).to_contain_text('配对码不匹配')
            one.locator('#address').fill('')
            one.locator('#manual summary').click()
            # No UDP listener, typed IP, saved peer, or previous pairing on either side.
            one.locator('#digits').fill(code.lower());one.locator('#connect').click()
        expect(two.locator('#invite')).to_be_visible(timeout=12000)
        expect(one.locator('#pairtitle')).to_have_text('连接其他设备')
        two.locator('#yes').click()
        for page in [one,two]:expect(page.locator('#connect')).to_have_text('断开连接')
        for i,(src,dst) in enumerate([(one,two),(two,one)]):
            blob=os.urandom(1536391 if i==0 else 262144)
            src.locator('#pick').set_input_files({'name':f'设计稿 {i}.bin','mimeType':'application/octet-stream','buffer':blob})
            save=dst.locator('#queue').get_by_role('button',name='保存')
            with dst.expect_response('**/api/inbox/save') as e:save.click()
            assert e.value.ok,e.value.text()
            target=home_dirs[1-i]/'Downloads/TransferBay 接收'/('来自 Mac' if i==0 else '来自 Windows')
            saved=target/f'设计稿 {i}.bin'
            assert hashlib.sha256(saved.read_bytes()).digest()==hashlib.sha256(blob).digest()
            with dst.expect_response('**/api/inbox/save') as e:save.click()
            assert e.value.ok and (target/f'设计稿 {i} (1).bin').read_bytes()==blob

        # A long transfer session at the smallest supported desktop window.
        one.set_viewport_size({'width':640,'height':530})
        expect(one.locator('#mycode')).to_be_hidden()
        one.locator('#infoToggle').click();expect(one.locator('#miniInfo')).to_be_visible()
        one.locator('#infoToggle').click();expect(one.locator('#miniInfo')).to_be_hidden()
        samples=[{'name':f'传输样本 {i:02d}.txt','mimeType':'text/plain','buffer':bytes([i])} for i in range(18)]
        one.locator('#pick').set_input_files(samples)
        expect(two.locator('#queue .row')).to_have_count(20,timeout=30000)
        newest=one.locator('#queue .row strong').first
        expect(newest).to_have_text(samples[-1]['name'])
        def check_scroller(page, selector):
            sizes=page.locator(selector).evaluate("""el=>{el.scrollTop=el.scrollHeight;return [el.scrollTop,el.clientHeight,document.documentElement.scrollHeight,innerHeight]}""")
            assert sizes[0]>0 and sizes[1]>0 and sizes[2]<=sizes[3],sizes
        check_scroller(one,'#queue')
        anchor=one.locator('#queue').evaluate('el=>el.scrollTop')
        one.wait_for_timeout(1350)
        assert one.locator('#queue').evaluate('el=>el.scrollTop')==anchor
        one.locator('#queueHead select').select_option('asc')
        expect(newest).to_have_text('设计稿 0.bin')
        one.locator('button[data-view="history"]').click()
        check_scroller(one,'#logs')
        one.locator('#history select').select_option('desc')
        expect(one.locator('#logs .row strong').first).to_have_text(samples[-1]['name'])
        one.locator('#clearLog').click();expect(one.locator('#logs .row')).to_have_count(0)
        one.reload();expect(one.locator('#disconnect')).to_be_visible()
        one.locator('button[data-view="history"]').click();expect(one.locator('#logs .row')).to_have_count(0)
        assert saved.read_bytes()==blob
        one.locator('button[data-view="home"]').click()
        one.set_viewport_size({'width':980,'height':630})
        one.locator('#queue').evaluate('el=>el.scrollTop=0')
        if not blocked:one.screenshot(path=str(root/'release/配对后预览.png'))
        two.on('dialog',lambda d:d.accept());two.locator('#disconnect').click()
        expect(one.locator('#pairtitle')).to_have_text('连接其他设备')
        expect(two.locator('#queue .row')).to_have_count(0)
        expect(one.locator('#mycode')).to_be_visible()
        print('PASS: LAN discovery across services, consent, bidirectional SHA-256, Unicode downloads, disconnect')
        assert saved.read_bytes()==blob
        browser.close()
finally:
    for p in servers:p.terminate();p.wait(timeout=8)
