import Cocoa
import WebKit

final class App: NSObject, NSApplicationDelegate, WKNavigationDelegate, WKDownloadDelegate, WKUIDelegate, NSWindowDelegate {
    var window:NSWindow!
    var child:Process?
    var web:WKWebView!
    var tray:MenuTransfer?
    let uiKey=UUID().uuidString,nativeKey=UUID().uuidString
    func applicationDidFinishLaunching(_ n: Notification) {
        let task=Process(), pipe=Pipe()
        task.executableURL=Bundle.main.resourceURL!.appendingPathComponent("engine/feidu-server")
        task.standardOutput=pipe
        var env=ProcessInfo.processInfo.environment;env["TRANSFERBAY_UI"]=uiKey;env["TRANSFERBAY_NATIVE"]=nativeKey;task.environment=env
        child=task
        do {
            try task.run()
            let data=pipe.fileHandleForReading.availableData
            guard let line=String(data:data,encoding:.utf8),let port=line.trimmingCharacters(in:.whitespacesAndNewlines).split(separator:":").last,Int(port) != nil else {throw NSError(domain:"TransferBay 服务启动失败",code:1)}
            window=NSWindow(contentRect:NSRect(x:0,y:0,width:980,height:630),styleMask:[.titled,.closable,.miniaturizable,.resizable],backing:.buffered,defer:false)
            window.delegate=self;window.isReleasedWhenClosed=false
            tray=MenuTransfer(port:Int(port)!,key:nativeKey){[weak self] in self?.restore()}
            window.title="TransferBay · 文件传输";window.minSize=NSSize(width:640,height:530)
            web=WKWebView();web.navigationDelegate=self;web.uiDelegate=self;window.contentView=web
            window.center();window.makeKeyAndOrderFront(nil); NSApp.activate(ignoringOtherApps:true)
            web.load(URLRequest(url:URL(string:"http://127.0.0.1:\(port)/#desktop=\(uiKey)")!))
        } catch {NSAlert(error:error).runModal();NSApp.terminate(nil)}
    }
    func webView(_ w:WKWebView,runOpenPanelWith p:WKOpenPanelParameters,initiatedByFrame f:WKFrameInfo,completionHandler:@escaping ([URL]?)->Void){let panel=NSOpenPanel();panel.allowsMultipleSelection=p.allowsMultipleSelection;panel.beginSheetModal(for:window){r in completionHandler(r == .OK ? panel.urls:nil)}}
    func webView(_ w:WKWebView,runJavaScriptConfirmPanelWithMessage m:String,initiatedByFrame f:WKFrameInfo,completionHandler:@escaping(Bool)->Void){let a=NSAlert();a.messageText=m;a.addButton(withTitle:"继续");a.addButton(withTitle:"取消");a.beginSheetModal(for:window){r in completionHandler(r == .alertFirstButtonReturn)}}
    func webView(_ w:WKWebView,decidePolicyFor a:WKNavigationAction,decisionHandler:@escaping (WKNavigationActionPolicy)->Void){decisionHandler(a.shouldPerformDownload || a.request.url?.path.hasPrefix("/download/")==true ? .download:.allow)}
    func webView(_ w:WKWebView,navigationAction:WKNavigationAction,didBecome download:WKDownload){download.delegate=self}
    func download(_ d:WKDownload,decideDestinationUsing r:URLResponse,suggestedFilename n:String,completionHandler:@escaping(URL?)->Void){let p=NSSavePanel();p.nameFieldStringValue=(n as NSString).lastPathComponent;p.beginSheetModal(for:window){v in completionHandler(v == .OK ? p.url:nil)}}
    func restore(){NSApp.setActivationPolicy(.regular);if window.isMiniaturized{window.deminiaturize(nil)};window.makeKeyAndOrderFront(nil);NSApp.activate(ignoringOtherApps:true)}
    func windowDidMiniaturize(_ n:Notification){NSApp.setActivationPolicy(.accessory)}
    func windowShouldClose(_ w:NSWindow)->Bool{w.orderOut(nil);NSApp.setActivationPolicy(.accessory);return false}
    func applicationShouldHandleReopen(_ sender:NSApplication,hasVisibleWindows flag:Bool)->Bool{restore();return true}
    func applicationShouldTerminateAfterLastWindowClosed(_ sender:NSApplication)->Bool {false}
    func applicationWillTerminate(_ n:Notification){if child?.isRunning==true{child?.terminate()}}
}
let app=NSApplication.shared, delegate=App()
app.delegate=delegate;app.setActivationPolicy(.regular)
let bar=NSMenu(), item=NSMenuItem();bar.addItem(item);let menu=NSMenu();menu.addItem(withTitle:"退出 TransferBay",action:#selector(NSApplication.terminate(_:)),keyEquivalent:"q");item.submenu=menu
let edit=NSMenuItem();bar.addItem(edit);let em=NSMenu(title:"编辑");for (title,act,k) in [("复制","copy:","c"),("粘贴","paste:","v"),("全选","selectAll:","a")]{em.addItem(withTitle:title,action:Selector(act),keyEquivalent:k)};edit.submenu=em
app.mainMenu=bar;app.run()
