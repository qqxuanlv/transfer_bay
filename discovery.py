"""IPv4 LAN discovery. Broadcast still works if multicast is unavailable."""
import hashlib, http.client, ipaddress, json, re, secrets, socket, subprocess, sys, time
from functools import lru_cache
from urllib.parse import urlsplit

PORT = 47772
GROUP = '239.255.77.72'

# A ticket carries the live endpoint and the original random six-digit challenge.
# Length tags make the common RFC1918 addresses compact, without assuming that
# the sender and recipient share any part of their address.
ALPHABET='0123456789ABCDEFGHJKMNPQRSTVWXYZ'
SHORT_NET=ipaddress.IPv4Network('192.168.0.0/16')
TEN_NET=ipaddress.IPv4Network('10.0.0.0/8')
MID_NET=ipaddress.IPv4Network('172.16.0.0/12')
def base32(n,width):
    return ''.join(ALPHABET[n >> (5*i) & 31] for i in reversed(range(width)))

def pairing_code(host,port,pin):
    if not lan(host):return pin
    ip=ipaddress.IPv4Address(host)
    if ip in SHORT_NET:width,index=8,int(ip)-int(SHORT_NET.network_address)
    elif ip in TEN_NET:width,index=9,int(ip)-int(TEN_NET.network_address)
    elif ip in MID_NET:width,index=9,TEN_NET.num_addresses+int(ip)-int(MID_NET.network_address)
    else:width,index=11,int(ip)
    # Bind unused bits to the contents to catch common transcription errors.
    import zlib
    check_bits={8:4,9:0,11:3}[width]
    check=zlib.crc32(ip.packed+port.to_bytes(2,'big')+pin.encode()) & ((1<<check_bits)-1)
    n=(((index<<20)|int(pin))<<check_bits)|check
    return base32(n,width)+(base32(port,4) if port!=8765 else '')

def read_code(raw):
    msg='配对码格式不正确，请复制对方窗口当前的完整配对码。'
    clean=re.sub(r'[\s-]','',raw).upper().translate(str.maketrans('OIL','011'))
    if re.fullmatch(r'[0-9]{6}',clean):return clean,None
    width={8:8,9:9,11:11,12:8,13:9,15:11}.get(len(clean))
    if not width or any(c not in ALPHABET for c in clean):raise ValueError(msg)
    def number(s):
        n=0
        for c in s:n=(n<<5)|ALPHABET.index(c)
        return n
    port=number(clean[width:]) if len(clean)>width else 8765
    n=number(clean[:width])>>{8:4,9:0,11:3}[width]
    index,pin=divmod(n,1<<20)
    if width==8:host=int(SHORT_NET.network_address)+index
    elif width==9:
        host=int(TEN_NET.network_address)+index if index<TEN_NET.num_addresses else int(MID_NET.network_address)+index-TEN_NET.num_addresses
    else:host=index
    if not 1<=port<=65535 or pin>999999 or host>=2**32:raise ValueError(msg)
    host=str(ipaddress.IPv4Address(host));pin=f'{pin:06d}'
    if not lan(host) or pairing_code(host,port,pin)!=clean:raise ValueError(msg)
    return pin,f'http://{host}:{port}'

def lan(address):
    try:
        a=ipaddress.IPv4Address(address)
        return a.is_private and a not in ipaddress.IPv4Network('198.18.0.0/15') and not (a.is_loopback or a.is_reserved or a.is_unspecified or a.is_multicast)
    except ValueError:return False

@lru_cache(maxsize=1)
def interfaces(epoch):
    addresses=[]
    def add(a):
        if lan(a) and a not in addresses:addresses.append(a)
    # Prefer physical LAN interfaces over VPN routes on multihomed computers.
    if sys.platform=='darwin':
        try:
            listing=subprocess.check_output(['/sbin/ifconfig','-a'],timeout=2,text=True)
            for block in re.split(r'\n(?=\S)',listing):
                if re.match(r'(en\d+|bridge\d+):',block) and 'status: inactive' not in block:
                    for a in re.findall(r'\binet ([\d.]+)',block):add(a)
        except (OSError,subprocess.SubprocessError):pass
    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:
        try:sock.connect(('192.0.2.1',9));add(sock.getsockname()[0])
        except OSError:pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(),None,socket.AF_INET):add(info[4][0])
    except OSError:pass
    return addresses

def addresses():return interfaces(int(time.monotonic()//30))
def digest(code,nonce):return hashlib.sha256((code+nonce).encode()).hexdigest()

def listen(port,getcodes):
    while True:
        try:
            with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as s:
                s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
                if hasattr(socket,'SO_REUSEPORT'):s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEPORT,1)
                s.bind(('',PORT));s.settimeout(30);joined=set()
                while True:
                    for a in addresses() or ['0.0.0.0']:
                        if a not in joined:
                            try:s.setsockopt(socket.IPPROTO_IP,socket.IP_ADD_MEMBERSHIP,socket.inet_aton(GROUP)+socket.inet_aton(a));joined.add(a)
                            except OSError:pass
                    try:raw,addr=s.recvfrom(256)
                    except (TimeoutError,ConnectionResetError):continue
                    fields=raw.decode('ascii','ignore').split()
                    if lan(addr[0]) and len(fields)==3 and fields[0]=='FD1' and len(fields[1])==24 and any(digest(c,fields[1])==fields[2] for c in getcodes()):
                        try:s.sendto(f'FD2 {fields[1]} {port}'.encode(),addr)
                        except OSError:pass
        except OSError:time.sleep(1)

def lookup(code):
    import select
    nonce=secrets.token_hex(12);msg=f'FD1 {nonce} {digest(code,nonce)}'.encode()
    sockets=[]
    try:
        for a in addresses() or ['0.0.0.0']:
            s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
            try:
                s.bind((a,0));s.setsockopt(socket.SOL_SOCKET,socket.SO_BROADCAST,1)
                s.setsockopt(socket.IPPROTO_IP,socket.IP_MULTICAST_TTL,1)
                s.setsockopt(socket.IPPROTO_IP,socket.IP_MULTICAST_IF,socket.inet_aton(a));sockets.append(s)
            except OSError:s.close()
        if not sockets:return None
        for delay in (.55,.8,1.1):
            for s in sockets:
                for dst in (GROUP,'255.255.255.255'):
                    try:s.sendto(msg,(dst,PORT))
                    except OSError:pass
            end=time.monotonic()+delay
            while time.monotonic()<end:
                for s in select.select(sockets,[],[],max(0,end-time.monotonic()))[0]:
                    try:raw,addr=s.recvfrom(160)
                    except OSError:continue
                    parts=raw.decode('ascii','ignore').split()
                    if len(parts)==3 and parts[:2]==['FD2',nonce] and parts[2].isdigit() and 0<int(parts[2])<65536 and lan(addr[0]):
                        return f'http://{addr[0]}:{int(parts[2])}'
    finally:
        for s in sockets:s.close()

def direct(raw,code,default_port=8765):
    """Probe the supplied LAN address before handing the view to that server."""
    try:
        parsed=urlsplit(raw if '://' in raw else 'http://'+raw)
        host=parsed.hostname;port=default_port if parsed.port is None else parsed.port
        if not 1<=port<=65535:raise ValueError()
        if parsed.scheme!='http' or not lan(host) or parsed.username or parsed.password or parsed.path not in ('','/') or parsed.query or parsed.fragment:raise ValueError()
    except (ValueError,TypeError):raise ValueError('请输入对方 TransferBay 显示的局域网 IP；需要指定端口时，使用 IP:端口。')
    conn=http.client.HTTPConnection(host,port,timeout=2)
    try:
        nonce=secrets.token_hex(12)
        conn.request('POST','/api/probe',body=json.dumps({'nonce':nonce,'proof':digest(code,nonce)}),headers={'Content-Type':'application/json'})
        response=conn.getresponse()
        if response.status==429:raise ValueError('尝试过于频繁，请稍后再试。')
        try:result=json.loads(response.read(2048))
        except (ValueError,UnicodeError):result={}
        if not isinstance(result,dict) or result.get('feidu')!=nonce:raise ValueError('地址可达，但没有找到新版 TransferBay。请检查端口，并更新对方的应用。')
        if result.get('match') is not True:raise ValueError('已找到对方的 TransferBay，但配对码不匹配。请复制对方窗口当前的配对码。')
        return f'http://{host}:{port}'
    except (OSError,http.client.HTTPException):raise ValueError('无法访问这个地址。请确认对方 TransferBay 已打开，并允许它通过局域网防火墙。')
    finally:conn.close()
