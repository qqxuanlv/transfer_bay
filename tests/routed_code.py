"""Ticket boundaries, old codes and reject invalid / non-LAN tickets."""
import itertools,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import discovery as d
for addr,port,pin in itertools.product(('192.168.0.1','192.168.255.254','10.0.0.1','10.255.255.254','172.16.0.1','172.31.255.254','169.254.88.9'),(1,8765,65535),('000000','000001','999999')):
    ticket=d.pairing_code(addr,port,pin)
    grouped='-'.join(ticket[i:i+4] for i in range(0,len(ticket),4))
    assert d.read_code(grouped.lower())==(pin,f'http://{addr}:{port}')
assert d.read_code('001 234')==('001234',None)
assert d.pairing_code('127.0.0.1',8765,'001234')=='001234'
for invalid in ('12345','11111U11','Z'*9,'0'*11,'Z'*15,
                d.base32((int.from_bytes(bytes([8,8,8,8]),'big')<<20|123456)<<3,11)):
    try:d.read_code(invalid)
    except ValueError:continue
    raise AssertionError(invalid)
print('PASS: compact tickets, custom ports, leading zeros, out-of-range and non-LAN rejection')
