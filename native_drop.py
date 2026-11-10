"""Native drop targets share the desktop window's pairing and transfer protocol."""
import os, threading, time
from pathlib import Path
from peer_session import Peer, PeerError

class Desktop:
    def __init__(self,port,ui_key,native_key):
        self.url=f'http://127.0.0.1:{port}'
        self.ui_key,self.native_key=ui_key,native_key
        self.token='';self.lock=threading.RLock()
        self.pending=[];self.saving=set();self.saved=set();self.failed={}
        self.state={};self.notice='';self.sending=False;self.visible=True
        threading.Thread(target=self._heartbeat,daemon=True).start()
    def client(self):return Peer(self.url,self.token)
    def refresh(self):
        if self.token:
            state=self.client().json('GET','/api/state')
            with self.lock:self.state=state
    def _heartbeat(self):
        while True:
            try:
                self.refresh()
                with self.lock:
                    s=self.state;active={f['id'] for f in s.get('files',[])}
                    self.saved.intersection_update(active);self.failed={i:e for i,e in self.failed.items() if i in active}
                    ready=next((f for f in s.get('files',[]) if not f['out'] and f['status']=='ready' and f['id'] not in self.saved and f['id'] not in self.failed),None)
                    if ready and not self.saving:
                        fid=ready['id'];self.saving.add(fid)
                        threading.Thread(target=self._receive,args=(fid,),daemon=True).start()
                    self._pump()

            except (PeerError,OSError,ValueError):
                with self.lock:self.state={}
            time.sleep(0.9)
    def _receive(self,fid):
        try:
            r=self.client().json('POST','/api/inbox/save',{'id':fid,'automatic':True})
            with self.lock:self.saved.add(fid);self.notice='已保存：'+r['name']
        except (PeerError,ValueError,OSError) as e:
            with self.lock:self.failed[fid]=str(e.args[-1]);self.notice='自动保存失败：'+str(e.args[-1])
        finally:
            with self.lock:self.saving.discard(fid)
    def retry(self,fid):
        with self.lock:self.failed.pop(fid,None)
    def _pump(self):
        peer=self.state.get('peer');pair=self.state.get('pairID') or peer
        if self.sending or not peer or not self.pending:return
        paths,wanted=self.pending.pop(0)
        if wanted and wanted!=pair:
            self.notice='原连接已断开，请重新拖入文件。';return
        self.sending=True
        threading.Thread(target=self._send,args=(paths,pair),daemon=True).start()
    def snapshot(self):
        with self.lock:
            s=self.state
            return {'peer':s.get('peer'),'ask':s.get('ask'),'code':s.get('code'),
                    'incoming':[{'id':f['id'],'name':f['name']} for f in s.get('files',[]) if f['id'] in self.failed],
                    'sending':self.sending,'queued':sum(len(p) for p,_ in self.pending),'notice':self.notice}
    def drop(self,paths):
        if not isinstance(paths,list) or not 0<len(paths)<=100 or not all(isinstance(p,str) for p in paths):
            raise ValueError('每次可拖入 1 至 100 个文件。')
        self.refresh()
        with self.lock:
            if sum(len(p) for p,_ in self.pending)+len(paths)>2000:raise ValueError('队列已满，请稍候再拖入。')
            pair=self.state.get('pairID') or self.state.get('peer')
            self.pending.append((paths,pair))
            self.notice='已加入发送队列' if pair else '已排队，等待配对'
            self._pump()
    def _send(self,paths,pair):
        sent=0
        try:
            c=self.client()
            for idx,raw in enumerate(paths,1):
                p=Path(raw)
                if not p.is_file():raise ValueError('只能发送文件；文件夹请先压缩。')
                with p.open('rb') as stream:
                    n=os.fstat(stream.fileno()).st_size
                    if n>2*1024**3:raise ValueError('单个文件最大为 2 GB。')
                    s=c.json('GET','/api/state')
                    if (s.get('pairID') or s.get('peer'))!=pair:raise ValueError('连接已更改，本批次停止发送。')
                    with self.lock:self.notice=f'正在发送 {idx}/{len(paths)}：{p.name}'
                    f=c.json('POST','/api/offer',{'name':p.name,'size':n,'pairID':s.get('pairID')})['id']
                    with c.request('PUT','/api/file/'+f,stream,n) as r:r.read(4096)
                    sent+=1
            message=f'已发送 {sent} 个文件'
        except (OSError,PeerError,ValueError) as e:message=f'已发送 {sent} 个；'+str(e.args[-1])
        finally:
            with self.lock:self.sending=False;self.notice=locals().get('message','发送失败')
    def action(self,d):
        cmd=d.get('op')
        if cmd=='drop':self.drop(d.get('paths'))
        elif cmd=='answer':self.client().json('POST','/api/answer',{'id':d['id'],'accept':bool(d.get('accept'))});self.refresh()
        elif cmd=='save':
            self.retry(d['id'])
        elif cmd!='state':raise ValueError('未知操作')
        return self.snapshot()
