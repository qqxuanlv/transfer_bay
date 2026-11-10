"""Six-digit LAN locators. A locator identifies a UI; only a human accepts an invite."""
import http.client, ipaddress, json, secrets, threading
import discovery
from http.server import ThreadingHTTPServer

BASE=47773
WORDS="松树 月亮 灯塔 飞鸟 橙子 小鹿 雪山 帆船 星星 鲸鱼 竹林 风铃 贝壳 海岛 云朵 木桥 苹果 蓝莓 火车 风筝 西瓜 溪流 海鸥 蝴蝶 沙丘 小熊 银杏 蜂蜜 森林 天鹅 桃花 雨滴".split()

def phrase():
    a,b=secrets.SystemRandom().sample(WORDS,2)
    return a+' · '+b

def locator(host,slot):
    if slot is None or not discovery.lan(host):return None
    return f'{(int(ipaddress.IPv4Address(host)) & 65535)+65536*slot:06d}'

def candidates(code,addresses):
    # Try only one exact host per local /16 plus the 192.168 private prefix.
    tail=int(code)%65536
    prefixes=list(dict.fromkeys([int(ipaddress.IPv4Address(a))>>16 for a in addresses if discovery.lan(a)]+[0xc0a8]))
    return [h for p in prefixes if discovery.lan(h:=str(ipaddress.IPv4Address((p<<16)|tail)))]

def attach(server,handler):
    slots=list(range(15));secrets.SystemRandom().shuffle(slots)
    server.short_slot=slots[0]
    # For a nonstandard data port, reserve the small resolver port encoded in the
    # six digits. It only answers /api/locate and never accepts uploads or files.
    for slot in slots:
        if BASE+slot==server.server_port:
            server.short_slot=slot;return
        try:aux=ThreadingHTTPServer(('',BASE+slot),handler)
        except OSError:continue
        aux.main_server=server;server.short_slot=slot
        threading.Thread(target=aux.serve_forever,daemon=True).start()
        return
    # Preferred TCP port and ordinary LAN discovery still work when all slots are busy.

def check(code,host,port):
    c=http.client.HTTPConnection(host,port,timeout=.8)
    try:
        nonce=secrets.token_hex(12)
        c.request('POST','/api/locate',json.dumps({'nonce':nonce,'proof':discovery.digest('short:'+code,nonce)}),{'Content-Type':'application/json'})
        r=c.getresponse()
        if r.status!=200:return
        d=json.loads(r.read(1024));p=d.get('port')
        if d.get('nonce')==nonce and type(p) is int and 0<p<65536:return f'http://{host}:{p}'
    except (OSError,http.client.HTTPException,ValueError,AttributeError):pass
    finally:c.close()

def lookup(code,preferred):
    if int(code)//65536>=15:return None
    for host in candidates(code,discovery.addresses()):
        for port in dict.fromkeys((preferred,8765,BASE+int(code)//65536)):
            if url:=check(code,host,port):return url
    return discovery.lookup('short:'+code)
