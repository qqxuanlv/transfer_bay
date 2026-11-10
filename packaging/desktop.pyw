import os,threading,subprocess,webbrowser,time,ctypes,secrets
from pathlib import Path
import server
from native_drop import Desktop

def main():
    user=ctypes.windll.user32
    existing=user.FindWindowW('TransferBay.DropWindow.1',None)
    if existing:user.PostMessageW(existing,0x8002,0,0);return
    srv=server.port_settings.listen(lambda p:server.ThreadingHTTPServer(('0.0.0.0',p),server.Handler))
    server.short_pair.attach(srv,server.LocatorHandler)
    port=srv.server_port
    ctrl=server.desktop_controls=Desktop(port,secrets.token_urlsafe(32),secrets.token_urlsafe(32))
    url=f'http://127.0.0.1:{port}/#desktop={ctrl.ui_key}'
    for fn,args in [(server.discovery.listen,(port,server.discovery_codes)),(server.cleanup,()),(srv.serve_forever,())]:
        threading.Thread(target=fn,args=args,daemon=True).start()
    edge=next((p for k in ('ProgramFiles(x86)','ProgramFiles','LOCALAPPDATA') if (p:=Path(os.environ.get(k,''))/'Microsoft/Edge/Application/msedge.exe').is_file()),None)
    def show():
        # Chromium app window title may include a browser suffix.
        from ctypes import wintypes
        callback=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
        matches=[]
        @callback
        def visit(w,param):
            buf=ctypes.create_unicode_buffer(512);user.GetWindowTextW(w,buf,len(buf))
            if user.IsWindowVisible(w) and buf.value.startswith('TransferBay · 文件传输'):matches.append(w);return False
            return True
        user.EnumWindows(visit,0)
        if matches:user.ShowWindow(matches[0],9);user.SetForegroundWindow(matches[0]);return
        if edge:
            profile=str(Path(os.environ['LOCALAPPDATA'])/'Feidu'/'WindowProfile')
            subprocess.Popen([str(edge),'--app='+url,'--user-data-dir='+profile,'--no-first-run','--disable-background-mode','--window-size=980,630'])
        else:webbrowser.open(url)
    show()
    proc=subprocess.Popen([str(Path(__file__).with_name('TransferBayDrop.exe'))],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,encoding='utf-8')
    msg=['',0.0]
    def status():
        last=None
        while proc.poll() is None:
            st=ctrl.snapshot()
            label=(msg[0] if time.monotonic()<msg[1] else '正在发送…' if st['sending'] else '有配对请求' if st['ask'] else '保存失败，打开查看' if st['incoming'] else '拖入文件发送' if st['peer'] else '排队中，双击配对' if st['queued'] else '双击打开配对')
            line=str(int(ctrl.visible))+str(int(bool(st['peer'])))+label
            if line!=last:
                try:proc.stdin.write(line+'\n');proc.stdin.flush()
                except (OSError,ValueError):return
                last=line
            if st['notice'] and not st['sending'] and st['notice']!=getattr(status,'last',''):
                status.last=st['notice'];msg[:]=[st['notice'],time.monotonic()+6]
            time.sleep(.45)
    threading.Thread(target=status,daemon=True).start()
    try:
        for line in proc.stdout:
            action,*paths=line.rstrip('\r\n').split('\t')
            if action=='OPEN':show()
            elif action=='QUIT':break
            elif action=='HIDE':
                show();ctrl.visible=False
            elif action=='LIMIT':msg[:]=['最多 100 个文件',time.monotonic()+5]
            elif action=='DROP':
                try:ctrl.drop(paths)
                except Exception as e:msg[:]=[str(e.args[-1]),time.monotonic()+6]
    finally:
        proc.stdin.close();srv.shutdown();srv.server_close()
try:main()
except Exception as e:ctypes.windll.user32.MessageBoxW(0,str(e),'TransferBay 启动失败',16)
