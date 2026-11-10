"""Keep the UI on localhost while using the paired computer's transfer service."""
import http.client,json,threading
from contextlib import contextmanager
from urllib.parse import urlsplit

class PeerError(Exception):pass

class Peer:
    def __init__(self,url,token=''):
        u=urlsplit(url);self.host=u.hostname;self.port=u.port;self.token=token
        self.text_cursor=0
        self.text_lock=threading.Lock()

    @contextmanager
    def request(self,method,path,body=None,length=None):
        conn=http.client.HTTPConnection(self.host,self.port,timeout=7200 if path=='/api/inbox/save' else 45)
        headers={'Authorization':'Bearer '+self.token}
        if isinstance(body,dict):
            body=json.dumps(body).encode();headers['Content-Type']='application/json'
        if length is not None:headers['Content-Length']=str(length)
        try:
            conn.request(method,path,body=body,headers=headers)
            response=conn.getresponse()
            if response.status>=400:
                try:message=json.loads(response.read(4096))['error']
                except (KeyError,ValueError):message='对方服务未响应'
                raise PeerError(response.status,message)
            yield response
        except (OSError,http.client.HTTPException) as e:raise PeerError(502,'与对方的传输中断，请重试') from e
        finally:conn.close()

    def json(self,method,path,body=None):
        with self.request(method,path,body) as r:return json.loads(r.read(2*1024*1024))

class Slice:
    def __init__(self,stream,length):self.stream=stream;self.left=length
    def read(self,n):
        if not self.left:return b''
        data=self.stream.read(min(n,self.left))
        if not data:raise OSError('上传中断')
        self.left-=len(data);return data
