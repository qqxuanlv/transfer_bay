"""Local, per-user TCP port preference shared by both desktop launchers."""
import errno,json,os,sys,tempfile
from pathlib import Path

DEFAULT=8765
def file():
    if sys.platform=='darwin':base=Path.home()/'Library/Application Support'
    elif os.name=='nt':base=Path(os.environ['LOCALAPPDATA'])
    else:base=Path(os.environ.get('XDG_CONFIG_HOME',Path.home()/'.config'))
    return base/'TransferBay'/'network.json'
def valid(port):return type(port) is int and 1<=port<=65535
def preferred():
    try:p=json.loads(file().read_text(encoding='utf-8')).get('port')
    except (OSError,ValueError,AttributeError):return DEFAULT
    return p if valid(p) else DEFAULT
def save(p):
    if not valid(p):raise ValueError('请输入 1 到 65535 之间的整数。')
    path=file();path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w',dir=path.parent,delete=False,encoding='utf-8') as f:
        tmp=Path(f.name)
        try:
            json.dump({'port':p},f);f.close();os.replace(tmp,path)
        finally:tmp.unlink(missing_ok=True)
def listen(factory,explicit=None):
    configured=preferred();port=configured if explicit is None else explicit
    try:server=factory(port)
    except OSError as e:
        if explicit is not None or e.errno not in (errno.EADDRINUSE,errno.EACCES,10048,10013):raise
        server=factory(0)
    server.preferred_port=configured
    return server
