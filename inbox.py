"""Permanent local receive folder. No history operation touches this module."""
import os, sys, re, subprocess, unicodedata
from pathlib import Path

def root():
    base=Path.home()/'Downloads'
    if sys.platform=='win32':
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders') as k:
                base=Path(os.path.expandvars(winreg.QueryValueEx(k,'{374DE290-123F-4565-9164-39C4925E467B}')[0]))
        except OSError:pass
    return base/'TransferBay 接收'

def category(peer):
    return {'Windows 电脑':'来自 Windows','Mac 电脑':'来自 Mac','Android 设备':'来自 Android','iOS 设备':'来自 iOS'}.get(peer,'来自其他设备')

def clean_name(raw):
    name=unicodedata.normalize('NFC',str(raw)).replace('\\','/').split('/')[-1]
    name=re.sub(r'[<>:"/\\|?*\x00-\x1f\x7f]', '_',name).strip(' .')
    name=name.encode('utf-8')[:180].decode('utf-8','ignore').rstrip(' .') or '文件'
    if re.fullmatch(r'CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³]',name.split('.')[0].rstrip(),re.I):name='_'+name
    return name

def save(source,size,name,peer):
    folder=root()/category(peer);folder.mkdir(parents=True,exist_ok=True)
    base=Path(clean_name(name))
    for i in range(10000):
        dest=folder/(base.name if not i else f'{base.stem} ({i}){base.suffix}')
        try:out=dest.open('xb')
        except FileExistsError:continue
        try:
            with out:
                left=size
                while left:
                    data=source.read(min(left,256*1024))
                    if not data:raise OSError('传输中断')
                    out.write(data);left-=len(data)
            return dest
        except BaseException:
            dest.unlink(missing_ok=True);raise
    raise OSError('同名文件过多')

def reveal():
    path=root();path.mkdir(parents=True,exist_ok=True)
    if sys.platform=='win32':os.startfile(str(path))
    elif sys.platform=='darwin':subprocess.Popen(['/usr/bin/open',str(path)])
    else:subprocess.Popen(['xdg-open',str(path)])
