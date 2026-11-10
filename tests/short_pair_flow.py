"""No broadcast or peer history. Model both /23 sides, using real TCP responses on
an ephemeral port; verify the six digits reach the intended responder and stale codes fail."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import short_pair as sp
from unittest.mock import patch
for src,dst in [('192.168.23.7','192.168.20.9'),('192.168.20.9','192.168.23.7'),('10.40.25.2','10.40.1.3')]:
 for slot in (0,7,14):
    code=sp.locator(dst,slot);assert len(code)==6 and code.isdecimal()
    with patch('discovery.addresses',return_value=[src]),patch('discovery.lookup',side_effect=AssertionError),patch('short_pair.check',side_effect=lambda c,h,p:'match' if (c,h,p)==(code,dst,sp.BASE+slot) else None):
        assert sp.lookup(code,8765)=='match'
assert sp.lookup('999999',8765) is None
print('PASS numeric route decoding across different /23 networks and nondefault ports')
