"""TransferBay · LAN file transfer. Python 3 standard library only."""
import discovery, inbox, re, port_settings, short_pair, text_history
from native_drop import Desktop
desktop_controls=None
from peer_session import Peer, PeerError, Slice
import argparse, json, os, secrets, shutil, socket, tempfile, threading, time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit, quote, parse_qs
from collections import deque

ROOT = Path(__file__).parent / 'static'
TMP = tempfile.TemporaryDirectory(prefix='feidu-')
lock = threading.RLock()
users, asks, files, hits = {}, {}, {}, {}
now = time.monotonic
key = lambda: secrets.token_urlsafe(24)
LIMIT = 2 * 1024**3
def ip():
    return next(iter(discovery.addresses()),'127.0.0.1')
def drop(fid):
    files.pop(fid,None)
    try:(Path(TMP.name)/fid).unlink(missing_ok=True)
    except PermissionError:pass  # Windows releases open downloads after streaming.
def disconnect(t):
    p=users[t]['peer']; users[t]['peer']=None
    if p in users: users[p]['peer']=None
    for f,x in list(files.items()):
        if t in (x['src'],x['dst']): drop(f)
def sweep():
    for t,u in list(users.items()):
        if now()-u['seen']>180:
            disconnect(t); del users[t]
    for a,x in list(asks.items()):
        if x['end']<now() or x['src'] not in users or x['dst'] not in users: del asks[a]
    for f,x in list(files.items()):
        if now()-x['time']>3600: drop(f)
    for orphan in Path(TMP.name).iterdir():
        if orphan.name not in files:
            try:orphan.unlink(missing_ok=True)
            except PermissionError:pass
    for bucket,q in list(hits.items()):
        if not q or now()-q[-1]>60: hits.pop(bucket,None)
def cleanup():
    while True:
        time.sleep(15)
        with lock: sweep()
def code():
    while True:
        c=f'{secrets.randbelow(1000000):06d}'
        if all(u['code']!=c for u in users.values()): return c
def need(ok,msg,status=400):
    if not ok: raise Problem(status,msg)
def path_is_discovery(path):return path=='/api/discover'
class Problem(Exception): pass
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def reply(self,obj,status=200):
        b=json.dumps(obj,ensure_ascii=False).encode()
        self.send_response(status); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Cache-Control','no-store'); self.send_header('Content-Length',str(len(b))); self.end_headers(); self.wfile.write(b)
    def run(self):
        path=urlsplit(self.path).path
        if self.command=='GET' and path in ['/','/app.js','/text.js','/style.css']:
            name=path[1:] or 'index.html'; b=(ROOT/name).read_bytes(); self.send_response(200); self.send_header('Content-Type',{'html':'text/html; charset=utf-8','css':'text/css','js':'application/javascript','svg':'image/svg+xml'}[name.split('.')[-1]]); self.send_header('Content-Length',str(len(b))); self.end_headers(); self.wfile.write(b); return
        origin=self.headers.get('Origin')
        need(not origin or urlsplit(origin).netloc==self.headers.get('Host'),'来源不符',403)
        t=self.headers.get('Authorization','').removeprefix('Bearer ')
        d={}
        if self.command=='POST':
            need(self.headers.get('Content-Type','').startswith('application/json'),'请求格式不正确',415)
            n=int(self.headers.get('Content-Length',0)); need(0<n<=(32768 if path=='/api/text/send' else 8192),'无效请求')
            d=json.loads(self.rfile.read(n)); need(isinstance(d,dict),'无效请求')
        desktop=(self.client_address[0]=='127.0.0.1' and self.headers.get('Host')==f'127.0.0.1:{self.server.server_port}')
        if path=='/api/locate' and self.command=='POST':
            nonce=d.get('nonce');need(isinstance(nonce,str) and len(nonce)==24,'请求无效')
            main=getattr(self.server,'main_server',self.server)
            with lock:
                match=any(discovery.digest('short:'+short,nonce)==d.get('proof')
                          for u in users.values() if now()-u['seen']<180 and (short:=local_short(u)))
            return self.reply({'nonce':nonce,'port':main.server_port if match else None})
        if path=='/api/settings/port':
            need(desktop,'请在本机窗口修改设置',403)
            with lock:need(t in users,'会话已过期',401)
            if self.command=='POST':
                try:port_settings.save(d.get('port'))
                except ValueError as e:raise Problem(400,str(e))
                except OSError:raise Problem(500,'无法保存设置，请检查用户目录权限。')
            else:need(self.command=='GET','请求无效',405)
            return self.reply({'port':port_settings.preferred(),'active':self.server.server_port,'default':port_settings.DEFAULT})
        if path=='/api/native' and self.command=='POST':
            need(desktop and not origin and desktop_controls and secrets.compare_digest(t,desktop_controls.native_key),'不可访问',403)
            try:result=desktop_controls.action(d)
            except ValueError as e:raise Problem(400,str(e))
            return self.reply(result)
        if path=='/api/float' and self.command=='POST':
            need(desktop and os.name=='nt' and desktop_controls and t and t==desktop_controls.token,'请在本机 Windows 窗口操作',403)
            with desktop_controls.lock:
                desktop_controls.visible=not desktop_controls.visible
                return self.reply({'visible':desktop_controls.visible})
        with lock:
            local_user=users.get(t)
            if local_user:local_user['seen']=now()
            bridge=local_user.get('bridge') if local_user and desktop else None
        native=desktop_controls if desktop and desktop_controls and t and t==desktop_controls.token else None
        def managed_info():
            if not native:return {}
            with native.lock:return {'autoReceive':True,'saveErrors':dict(native.failed),'savingFiles':list(native.saving),'nativeQueued':sum(len(p) for p,_ in native.pending)}
        if path in ('/api/text/history','/api/text/clear'):
            need(local_user,'会话已过期',401)
            journal=local_user['journal']
            need(not journal.path or desktop,'请在本机窗口查看文字记录',403)
            if path=='/api/text/history' and self.command=='GET':
                after=int(parse_qs(urlsplit(self.path).query).get('after',['0'])[0])
                return self.reply(journal.snapshot(after))
            need(path=='/api/text/clear' and self.command=='POST','请求无效',405)
            through=d.get('through')
            need(type(through) is int and through>=0,'无效的记录范围')
            journal.clear(through)
            return self.reply(journal.snapshot())
        if path=='/api/inbox/retry' and self.command=='POST':
            need(native,'请在桌面客户端重试',403);native.retry(d.get('id'));return self.reply({})
        if path.startswith('/api/inbox/'):
            need(desktop and local_user,'请在本机 TransferBay 窗口操作',403)
            need(self.command=='POST','请求无效',405)
            if path=='/api/inbox/open':
                try:inbox.reveal()
                except OSError:raise Problem(500,'无法打开接收目录，请检查下载文件夹权限')
                return self.reply({})
            need(path=='/api/inbox/save','请求无效',404)
            fid=d.get('id');need(isinstance(fid,str) and re.fullmatch(r'[A-Za-z0-9_-]{32}',fid),'文件无效')
            source=bridge or Peer(f'http://127.0.0.1:{self.server.server_port}',t)
            # Use a wire-only state request so a local save cannot recurse into a bridge.
            st=source.json('GET','/api/state');item=next((i for i in st['files'] if i['id']==fid and not i['out']),None)
            need(item and item['status'] in ('ready','saved'),'文件已失效',404)
            with source.request('GET','/api/file/'+fid+'?receipt=explicit') as r:
                need(int(r.getheader('Content-Length','-1'))==item['size'] and 0<=item['size']<=LIMIT,'文件大小不匹配')
                try:dest=inbox.save(r,item['size'],item['name'],st['peer'])
                except OSError:raise Problem(500,'保存失败，请检查磁盘空间和目录权限')
            try:source.json('POST','/api/receipt/'+fid,{})
            except PeerError:pass  # The local copy is already complete.
            return self.reply({'name':dest.name,'category':dest.parent.name})
        if bridge:
            if path=='/api/state' and self.command=='GET':
                try:st=bridge.json('GET',path)
                except PeerError as e:
                    if e.args[0]!=401:raise
                    st=None
                if st:
                    text_history.pull(bridge,local_user['journal'],st.get('textRevision',0))
                    st['textRevision']=local_user['journal'].revision
                if st and (st['peer'] or st['pending']):
                    st.update(shortCode=local_short(local_user),code=local_user['code'],pairingCode=discovery.pairing_code(ip(),self.server.server_port,local_user['code']),inboxPath=str(inbox.root()),**managed_info())
                    return self.reply(st)
                with lock:local_user.pop('bridge',None)
            elif self.command=='PUT' and re.fullmatch(r'/api/file/[A-Za-z0-9_-]{32}',path):
                length=int(self.headers.get('Content-Length',-1));need(0<=length<=LIMIT,'文件大小无效')
                with bridge.request('PUT',path,Slice(self.rfile,length),length) as response:return self.reply(json.loads(response.read(4096)))
            elif self.command=='POST' and path in ('/api/offer','/api/disconnect','/api/text/send'):
                result=bridge.json('POST',path,d)
                if path=='/api/disconnect':
                    # A final state poll imports any messages sent immediately before disconnect.
                    if local_user.get('textCapable'):
                        st=bridge.json('GET','/api/state')
                        text_history.pull(bridge,local_user['journal'],st.get('textRevision',0))
                    with lock:
                        if local_user.get('bridge') is bridge:local_user.pop('bridge',None)
                return self.reply(result)
        if (self.command,path)==('POST','/api/probe'):
            nonce=d.get('nonce');need(isinstance(nonce,str) and len(nonce)==24,'请求无效')
            with lock:
                q=hits.setdefault('probe:'+self.client_address[0],deque())
                while q and now()-q[0]>60:q.popleft()
                need(len(q)<16,'尝试过于频繁',429);q.append(now())
                matched=any(discovery.digest(c,nonce)==d.get('proof') for c in active_codes())
            return self.reply({'feidu':nonce,'match':matched})
        if (self.command,path)==('POST','/api/discover'):
            c,endpoint=discovery.read_code(str(d.get('code','')))
            with lock:
                need(t in users,'会话已过期',401)
                q=hits.setdefault('lookup:'+self.client_address[0],deque())
                while q and now()-q[0]>60:q.popleft()
                need(len(q)<12,'尝试过于频繁，请稍后再试',429);q.append(now())
                local=c in active_codes()
            short=d.get('short') is True and endpoint is None and not d.get('address')
            if short:
                need(desktop,'请在本机窗口输入六位码',403)
                with lock:
                    if any(local_short(u)==c and now()-u['seen']<180 for u in users.values()):return self.reply({'local':True,'short':True})
                url=short_pair.lookup(c,self.server.preferred_port)
            elif endpoint:
                if local and endpoint in (f'http://{a}:{self.server.server_port}' for a in discovery.addresses()):
                    return self.reply({'local':True,'pin':c})
                url=discovery.direct(endpoint,c)
            elif d.get('address'):
                raw=str(d['address']).strip()
                parsed=urlsplit(raw if '://' in raw else 'http://'+raw)
                can_check=(d.get('short') is True and desktop and parsed.scheme=='http' and discovery.lan(parsed.hostname)
                           and not (parsed.username or parsed.password or parsed.query or parsed.fragment) and parsed.path in ('','/'))
                port=parsed.port if parsed.port is not None else self.server.preferred_port
                url=short_pair.check(c,parsed.hostname,port) if can_check and 0<port<=65535 else None
                short=bool(url)
                if not url:url=discovery.direct(raw,c,self.server.preferred_port)
            elif local:return self.reply({'local':True})
            else:
                url=discovery.lookup(c)
                if url:url=discovery.direct(url,c)
            if url and desktop and d.get('stayLocal'):
                bridge=Peer(url);bridge.token=bridge.json('POST','/api/device',{'name':local_user['name'],'supportsText':local_user['textCapable']})['token']
                bridge.json('POST','/api/pair',{'code':c,'short':short})
                with lock:local_user['bridge']=bridge
                return self.reply({'requested':True})
            return self.reply({'url':url,'local':False,'pin':c,'short':short})
        if self.command=='GET' and path.startswith('/download/'):
            secret=path.split('/')[-1]
            with lock:
                target=next(((f,x) for f,x in files.items() if x.get('ticket')==secret and now()<x['until']),None)
                need(target,'下载链接已失效',404); f,x=target; t=x['dst']; path='/api/file/'+f; x.pop('ticket',None)
        with lock:
            if (self.command,path)==('POST','/api/device'):
                native_ui=desktop and desktop_controls and isinstance(d.get('uiKey'),str) and secrets.compare_digest(d['uiKey'],desktop_controls.ui_key)
                if native_ui and desktop_controls.token in users:
                    return self.reply({'token':desktop_controls.token})
                need(len(users)<512,'当前设备过多',429)
                t=key(); users[t]=dict(code=code(),name=str(d.get('name') or '未知设备')[:45],peer=None,seen=now())
                if desktop and (native_ui or not desktop_controls) and not any(u.get('shortSlot') is not None and now()-u['seen']<180 for k,u in users.items() if k!=t):
                    users[t]['shortSlot']=self.server.short_slot
                users[t]['textCapable']=d.get('supportsText') is True
                users[t]['journal']=text_history.device() if native_ui else text_history.Journal()
                if native_ui:desktop_controls.token=t
                return self.reply({'token':t})
            need(t in users,'设备会话已过期',401)
            u=users[t]; u['seen']=now(); p=u['peer']
            if (self.command,path)==('GET','/api/state'):
                return self.reply(dict(**managed_info(),textRevision=u['journal'].revision,canText=bool(p and users[p]['textCapable']),code=u['code'],shortCode=local_short(u),pairingCode=discovery.pairing_code(ip(),self.server.server_port,u['code']),name=u['name'],pairID=u.get('pairID') if p else None,inboxPath=str(inbox.root()) if desktop else None,peer=users[p]['name'] if p else None,lan=f'http://{ip()}:{self.server.server_port}',addresses=[f'{a}:{self.server.server_port}' for a in discovery.addresses()],ask=next((dict(id=a,name=users[x['src']]['name'],words=x.get('words')) for a,x in asks.items() if x['dst']==t and x['end']>now()),None),pendingWords=next((x.get('words') for x in asks.values() if x['src']==t and x['end']>now()),None),pending=any(x['src']==t and x['end']>now() for x in asks.values()),files=[dict(id=f,name=x['name'],size=x['size'],out=x['src']==t,status=x['status'],createdAt=x['createdAt']) for f,x in files.items() if t in (x['src'],x['dst'])]))
            if (self.command,path)==('POST','/api/pair'):
                q=hits.setdefault(self.client_address[0],deque())
                while q and now()-q[0]>60:q.popleft()
                need(len(q)<12,'尝试过于频繁，请稍后再试',429); q.append(now())
                short=d.get('short') is True
                need(isinstance(d.get('code'),str) and re.fullmatch('[0-9]{6}',d['code']),'配对码无效')
                v=next((k for k,b in users.items() if (local_short(b) if short else b['code'])==d.get('code') and now()-b['seen']<180),None)
                need(v and v!=t,'配对码无效，请核对另一台设备上的数字')
                need(not p and not users[v]['peer'] and not users[v].get('bridge'),'设备已连接，请先断开')
                need(not any(x['end']>now() and ({t,v}&{x['src'],x['dst']}) for x in asks.values()),'设备正在等待配对，请稍后再试')
                if short:
                    recent=hits.setdefault('invite:'+v,deque())
                    while recent and now()-recent[0]>60:recent.popleft()
                    need(len(recent)<5,'配对请求过多，请稍后再试',429);recent.append(now())
                asks[key()]=dict(src=t,dst=v,end=now()+45,words=short_pair.phrase() if short else None)
            elif (self.command,path)==('POST','/api/answer'):
                a=str(d.get('id')); x=asks.get(a); need(x and x['dst']==t and x['end']>now(),'请求已失效')
                del asks[a]
                if d.get('accept') is True:
                    v=x['src']; need(not p and not users[v]['peer'] and not users[v].get('bridge'),'设备已连接')
                    u['peer']=v; users[v]['peer']=t;u['pairID']=users[v]['pairID']=key()
            elif (self.command,path)==('POST','/api/disconnect'): disconnect(t)
            elif (self.command,path)==('POST','/api/text/send'):
                need(p and d.get('pairID')==u.get('pairID'),'连接已改变，请重新确认接收设备',409)
                need(users[p]['textCapable'],'请将对方的 TransferBay 更新到 1.8 或更高版本',409)
                body=d.get('text')
                need(isinstance(body,str) and body.strip(),'请输入文字')
                need(len(body.encode('utf-16-le'))<=2*text_history.MAX_UNITS,'每条文字最多 4096 个字符')
                request_id=d.get('requestID')
                need(isinstance(request_id,str) and re.fullmatch('[a-f0-9]{32}',request_id),'请求编号无效')
                import hashlib
                mid=hashlib.sha256((t+u['pairID']+request_id).encode()).hexdigest()
                message=dict(id=mid,text=body,createdAt=time.time_ns()//1_000_000,pairID=u['pairID'])
                users[p]['journal'].append([dict(message,out=False,peer=u['name'])])
                u['journal'].append([dict(message,out=True,peer=users[p]['name'])])
                return self.reply({'id':mid})
            elif (self.command,path)==('POST','/api/offer'):
                need(p,'请先连接设备');need(not d.get('pairID') or u.get('pairID')==d['pairID'],'设备连接已改变'); n=d.get('size'); need(type(n)==int and 0<=n<=LIMIT,'单个文件上限为 2 GB')
                need(len(files)<1000 and sum(x['size'] for x in files.values())+n<=8*1024**3 and n+128*1024**2<shutil.disk_usage(TMP.name).free,'临时空间不足')
                f=key(); files[f]=dict(src=t,dst=p,name=str(d.get('name','文件'))[:240],size=n,status='offered',time=now(),createdAt=time.time_ns()//1_000_000)
                return self.reply(dict(id=f))
            elif self.command=='POST' and path.startswith('/api/receipt/'):
                x=files.get(path.split('/')[-1]);need(x and x['dst']==t and x['status'] in ('ready','saved'),'无法确认',403)
                x['status']='saved'
            elif path.startswith('/api/file/'):
                f=path.split('/')[-1]; x=files.get(f); need(x,'文件已失效',404); dest=Path(TMP.name)/f
                if self.command=='PUT':
                    need(t==x['src'] and x['status']=='offered','无法上传',403); need(int(self.headers.get('Content-Length',-1))==x['size'],'大小不匹配')
                    handle=dest.open('xb'); x['status']='uploading'
                elif self.command=='GET':
                    need(t==x['dst'] and x['status'] in ('ready','saved'),'无法下载',403); handle=dest.open('rb')
                elif self.command=='POST':
                    need(t==x['dst'] and x['status'] in ('ready','saved'),'无法确认',403); x['ticket']=key(); x['until']=now()+60; return self.reply({'href':'/download/'+x['ticket']})
                else: raise Problem(405,'无效操作')
            else: raise Problem(404,'地址不存在')
            if not path.startswith('/api/file/'): return self.reply({})
        with handle:
            if self.command=='GET':
                self.send_response(200); self.send_header('Content-Type','application/octet-stream'); self.send_header('Content-Disposition',"attachment; filename*=UTF-8''"+quote(x['name'],safe='')); self.send_header('Cache-Control','no-store'); self.send_header('Content-Length',str(x['size'])); self.end_headers(); shutil.copyfileobj(handle,self.wfile,256*1024)
                with lock:
                    if urlsplit(self.path).query!='receipt=explicit':x['status']='saved'
                return
            left=x['size']
            try:
                while left:
                    buf=self.rfile.read(min(left,256*1024)); need(buf,'上传中断'); handle.write(buf); left-=len(buf)
                    with lock: need(f in files,'连接已断开'); users[t]['seen']=now(); x['time']=now()
                handle.flush()
                with lock: need(f in files,'连接已断开'); x['status']='ready'
            except Exception:
                with lock: drop(f)
                raise
        self.reply({})
    def dispatch(self):
        try:self.run()
        except (Problem,PeerError) as e:self.reply({'error':e.args[1]},e.args[0])
        except ValueError as e:self.reply({'error':str(e) if path_is_discovery(self.path) else '请求无效'},400)
        except TypeError:self.reply({'error':'请求无效'},400)
        except (ConnectionError,TimeoutError):pass
        except OSError:self.reply({'error':'无法读写本机记录，请检查磁盘空间和目录权限'},500)
    do_GET=do_POST=do_PUT=dispatch
class LocatorHandler(Handler):
    def run(self):
        need(self.command=='POST' and self.path=='/api/locate','地址不存在',404)
        super().run()

def local_short(u):return short_pair.locator(ip(),u.get('shortSlot')) if u.get('shortSlot') is not None else None
def discovery_codes():
    with lock:return active_codes()+['short:'+c for u in users.values() if now()-u['seen']<180 and (c:=local_short(u))]
def active_codes():
    with lock:return [u['code'] for u in users.values() if now()-u['seen']<180]
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int);a=parser.parse_args()
    server=port_settings.listen(lambda p:ThreadingHTTPServer(('0.0.0.0',p),Handler),a.port)
    short_pair.attach(server,LocatorHandler)
    if os.environ.get('TRANSFERBAY_NATIVE') and os.environ.get('TRANSFERBAY_UI'):
        desktop_controls=Desktop(server.server_port,os.environ['TRANSFERBAY_UI'],os.environ['TRANSFERBAY_NATIVE'])
    threading.Thread(target=discovery.listen,args=(server.server_port,discovery_codes),daemon=True).start()
    threading.Thread(target=cleanup,daemon=True).start()
    print(f'TransferBay 已启动：http://{ip()}:{server.server_port}',flush=True)
    import signal
    signal.signal(signal.SIGTERM,lambda *_: (_ for _ in ()).throw(SystemExit(0)))
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close(); TMP.cleanup()
