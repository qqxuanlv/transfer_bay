"""Build a Windows x64 portable ZIP and per-user NSIS installer."""
import hashlib
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PACKAGING = ROOT / 'packaging'
OUT = Path(os.environ.get('OUT_DIR', ROOT / 'release')).resolve()
OUT.mkdir(parents=True, exist_ok=True)
VERSION = plistlib.loads((PACKAGING / 'Info.plist').read_bytes())['CFBundleShortVersionString']
PYTHON_ZIP = 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip'
PYTHON_SHA = '4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3'


def run(args, cwd):
    subprocess.run(list(map(str, args)), cwd=cwd, check=True)


with tempfile.TemporaryDirectory() as temp:
    work = Path(temp)
    payload = work / 'TransferBay'
    runtime = payload / 'runtime'
    runtime.mkdir(parents=True)
    archive = Path(os.environ.get('PYTHON_EMBED_ZIP', work / 'python.zip'))
    if not archive.exists():
        urllib.request.urlretrieve(PYTHON_ZIP, archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != PYTHON_SHA:
        raise ValueError('Unexpected Python runtime checksum')
    with zipfile.ZipFile(archive) as zipped:
        zipped.extractall(runtime)
    for module in ROOT.glob('*.py'):
        shutil.copy2(module, runtime)
    shutil.copytree(ROOT / 'static', runtime / 'static')
    shutil.copy2(PACKAGING / 'desktop.pyw', runtime)
    shutil.copy2(ROOT / 'README.md', payload / '使用说明.txt')

    targets = [('win.c', payload / 'TransferBay.exe'), ('float.c', runtime / 'TransferBayDrop.exe')]
    if os.name == 'nt':
        res = work / 'icon.res'
        run(['rc', '/nologo', '/fo', res, 'win.rc'], PACKAGING)
        for source, dest in targets:
            run(['cl', '/nologo', '/utf-8', '/O2', PACKAGING / source, res, '/link',
                 '/SUBSYSTEM:WINDOWS', '/OUT:' + str(dest), 'user32.lib', 'shell32.lib', 'gdi32.lib'], work)
    else:
        res = os.environ.get('WIN_ICON_RES')
        for source, dest in targets:
            run([sys.executable, '-m', 'ziglang', 'cc', '-target', 'x86_64-windows-gnu', '-Os',
                 '-municode', '-Wl,--subsystem,windows', PACKAGING / source, *([res] if res else []),
                 '-lgdi32', '-lshell32', '-o', dest], work)
    with zipfile.ZipFile(OUT / 'TransferBay-Windows-x64.zip', 'w', zipfile.ZIP_DEFLATED) as portable:
        for path in sorted(payload.rglob('*')):
            if path.is_file():
                portable.write(path, path.relative_to(work))
    cleanup = work / 'remove.nsh'
    lines = []
    for path in sorted(payload.rglob('*'), reverse=True):
        relative = str(path.relative_to(payload)).replace('/', chr(92))
        op = 'RMDir' if path.is_dir() else 'Delete'
        lines.append(f'{op} "$INSTDIR\\{relative}"')
    cleanup.write_text('\n'.join(lines), encoding='utf-8-sig')
    prefix = '/' if os.name == 'nt' else '-'
    run([os.environ.get('MAKENSIS','makensis'), prefix + 'V2',
         prefix + 'DOUTPUT=' + str(OUT / 'TransferBay-Windows-x64-Setup.exe'),
         prefix + 'DPAYLOAD=' + str(payload), prefix + 'DUNINSTALL_FILES=' + str(cleanup),
         prefix + 'DVERSION=' + VERSION, 'installer.nsi'], PACKAGING)
