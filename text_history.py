"""Per-device text history and temporary history for a paired LAN session."""
import json
import os
from pathlib import Path
import tempfile
import threading
import port_settings

MAX_ENTRIES = 80
MAX_UNITS = 4096


class Journal:
    def __init__(self, path=None):
        self.path = path
        self.lock = threading.RLock()
        self.revision = 0
        self.items = []
        if path and path.exists():
            saved = json.loads(path.read_text(encoding='utf-8'))
            self.revision = saved['revision']
            self.items = saved['items']

    def _commit(self, items, revision):
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile('w', dir=self.path.parent, encoding='utf-8', delete=False) as stream:
                tmp = Path(stream.name)
                try:
                    json.dump({'revision': revision, 'items': items}, stream, ensure_ascii=False)
                    stream.close()
                    os.replace(tmp, self.path)
                finally:
                    tmp.unlink(missing_ok=True)
        self.items = items
        self.revision = revision

    def append(self, rows):
        with self.lock:
            known = {row['id'] for row in self.items}
            items = list(self.items)
            revision = self.revision
            for row in rows:
                if row['id'] in known:
                    continue
                known.add(row['id'])
                revision += 1
                items.append(dict(row, seq=revision))
            if revision != self.revision:
                self._commit(items[-MAX_ENTRIES:], revision)

    def snapshot(self, after=0):
        with self.lock:
            return {'revision': self.revision, 'items': [row for row in self.items if row['seq'] > after]}

    def clear(self, through):
        with self.lock:
            items = [row for row in self.items if row['seq'] > through]
            if len(items) != len(self.items):
                self._commit(items, self.revision + 1)


_device = None
def device():
    global _device
    if _device is None:
        _device = Journal(port_settings.file().with_name('text-history.json'))
    return _device


def pull(bridge, journal, remote_revision):
    with bridge.text_lock:
        if remote_revision <= bridge.text_cursor:
            return
        page = bridge.json('GET', f'/api/text/history?after={bridge.text_cursor}')
        journal.append(page['items'])
        bridge.text_cursor = page['revision']
