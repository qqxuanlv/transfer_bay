import Cocoa

final class DropTarget: NSView {
    var onFiles:(([URL])->Void)?
    var onClick:(()->Void)?
    var onFileDrag:((Int)->Void)?
    var onExit:(()->Void)?
    var onEnd:(()->Void)?
    var allowsDrop:((NSPoint)->Bool)?
    override init(frame:NSRect){super.init(frame:frame);registerForDraggedTypes([.fileURL]);setAccessibilityElement(false)}
    required init?(coder:NSCoder){fatalError()}
    override func hitTest(_ point:NSPoint)->NSView?{isHidden ? nil : self}
    override func mouseDown(with event:NSEvent){onClick?()}
    override func rightMouseDown(with event:NSEvent){onClick?()}
    func enter(_ pb:NSPasteboard)->NSDragOperation{
        guard pb.availableType(from:[.fileURL]) != nil else{return []}
        onFileDrag?(pb.pasteboardItems?.count ?? 1);return .copy
    }
    func accept(_ pb:NSPasteboard)->Bool{
        let files=pb.readObjects(forClasses:[NSURL.self],options:[.urlReadingFileURLsOnly:true]) as? [URL] ?? []
        guard !files.isEmpty else{return false}
        onFiles?(files);onEnd?();return true
    }
    private func acceptsLocation(_ s:NSDraggingInfo)->Bool{allowsDrop?(convert(s.draggingLocation,from:nil)) ?? true}
    override func draggingEntered(_ s:NSDraggingInfo)->NSDragOperation{let op=enter(s.draggingPasteboard);return acceptsLocation(s) ? op:[]}
    override func draggingUpdated(_ s:NSDraggingInfo)->NSDragOperation{
        acceptsLocation(s) && s.draggingPasteboard.availableType(from:[.fileURL]) != nil ? .copy:[]
    }
    override func draggingExited(_ sender:NSDraggingInfo?){onExit?()}
    override func draggingEnded(_ sender:NSDraggingInfo){onEnd?()}
    override func prepareForDragOperation(_ s:NSDraggingInfo)->Bool{acceptsLocation(s) && s.draggingPasteboard.availableType(from:[.fileURL]) != nil}
    override func performDragOperation(_ sender:NSDraggingInfo)->Bool{acceptsLocation(sender) && accept(sender.draggingPasteboard)}
}

private final class PassivePanel:NSPanel {
    override var canBecomeKey:Bool{false}
    override var canBecomeMain:Bool{false}
}

/// An invisible, temporary drag destination widens the menu item. Only a real
/// AppKit file drag reveals its card; mouse movement never reads the clipboard.
final class DropShelf {
    let destination:DropTarget
    private let panel:PassivePanel
    private let card=NSVisualEffectView(),title=NSTextField(labelWithString:""),detail=NSTextField(labelWithString:"")
    private var dismiss:DispatchWorkItem?
    private var blocked=false
    var iconTarget:NSRect = .zero
    private(set) var showing=false
    var peer:(()->String?)?
    var onFiles:(([URL])->Void)?
    init(){
        panel=PassivePanel(contentRect:.zero,styleMask:[.borderless,.nonactivatingPanel],backing:.buffered,defer:true)
        panel.isReleasedWhenClosed=false;panel.isOpaque=false;panel.backgroundColor = .clear;panel.hidesOnDeactivate=false;panel.hasShadow=false
        panel.level=NSWindow.Level(rawValue:NSWindow.Level.statusBar.rawValue+1)
        panel.collectionBehavior=[.canJoinAllSpaces,.fullScreenAuxiliary,.ignoresCycle,.stationary]
        panel.animationBehavior = .none
        destination=DropTarget(frame:.zero);panel.contentView=destination
        destination.wantsLayer=true
        // Nearly transparent surface still participates in WindowServer hit testing.
        destination.layer?.backgroundColor=NSColor.white.withAlphaComponent(0.012).cgColor
        card.material = .popover;card.blendingMode = .behindWindow;card.state = .active
        card.wantsLayer=true;card.layer?.cornerRadius=13;card.layer?.masksToBounds=true
        card.layer?.borderWidth=1;card.layer?.borderColor=NSColor.separatorColor.cgColor
        destination.addSubview(card);card.isHidden=true
        let symbol=NSImageView(frame:NSRect(x:13,y:22,width:26,height:26))
        symbol.image=NSImage(systemSymbolName:"paperplane.fill",accessibilityDescription:nil)
        symbol.contentTintColor=NSColor(calibratedRed:0.43,green:0.34,blue:0.57,alpha:1)
        card.addSubview(symbol)
        title.font = .systemFont(ofSize:14,weight:.semibold);detail.font = .systemFont(ofSize:12);detail.textColor = .secondaryLabelColor
        for label in [title,detail]{label.lineBreakMode = .byTruncatingTail;label.maximumNumberOfLines=1;card.addSubview(label)}
        destination.allowsDrop={ [weak self] p in
            guard let self=self else{return false}
            let global=NSPoint(x:p.x+self.panel.frame.minX,y:p.y+self.panel.frame.minY)
            return self.card.frame.contains(p) || self.iconTarget.contains(global)
        }
        destination.onFileDrag={[weak self] count in self?.reveal(count)}
        destination.onExit={[weak self] in self?.leave()}
        destination.onEnd={[weak self] in self?.released()}
        destination.onFiles={[weak self] files in self?.onFiles?(files);self?.finish()}
    }
    static func layout(icon:NSRect,screen:NSRect)->NSRect{
        let width=min(240,screen.width-12),bottom=icon.minY-80
        let x=max(screen.minX+6,min(icon.midX-width/2,screen.maxX-width-6))
        return NSRect(x:x,y:bottom,width:width,height:80)
    }
    func track(held:Bool,at point:NSPoint,icon:NSRect,screen:NSRect){
        iconTarget=icon
        let frame=Self.layout(icon:icon,screen:screen)
        let band=icon.insetBy(dx:-65,dy:0)
        let approach=frame.insetBy(dx:showing ? -3:-22,dy:showing ? -3:-20)
        guard held,band.contains(point) || approach.contains(point) else{reset();return}
        guard !blocked else{return}
        // Don't arm over a stationary click on the item; its native menu remains clickable.
        if icon.contains(point) && !panel.isVisible{return}
        arm(frame)
    }
    func arm(_ frame:NSRect){
        guard !blocked else{return}
        if !panel.isVisible || panel.frame != frame{
            panel.setFrame(frame,display:false)
            let w=frame.width-8
            card.frame=NSRect(x:4,y:3,width:w,height:70)
            title.frame=NSRect(x:50,y:36,width:w-60,height:19);detail.frame=NSRect(x:50,y:15,width:w-60,height:17)
            if !panel.isVisible{panel.orderFrontRegardless()}
        }
    }
    func reveal(_ count:Int){
        guard panel.isVisible,!blocked else{return}
        dismiss?.cancel();dismiss=nil
        title.stringValue=count>1 ? "松开发送 "+String(count)+" 个文件":"松开发送文件"
        detail.stringValue=peer?().map{"发送至 "+$0} ?? "尚未配对 · 松开后加入队列"
        card.isHidden=false;showing=true
    }
    func leave(){
        dismiss?.cancel()
        let task=DispatchWorkItem{[weak self] in self?.finish()};dismiss=task
        DispatchQueue.main.asyncAfter(deadline:.now()+0.12,execute:task)
    }
    func released(){
        guard panel.isVisible else{blocked=false;return}
        // The mouse-up monitor can run before AppKit delivers performDragOperation.
        // Keep the registered destination alive for that final handoff.
        if dismiss==nil{leave()}
    }
    func finish(){blocked=true;hide()}
    func reset(){blocked=false;hide()}
    private func hide(){
        dismiss?.cancel();dismiss=nil
        if panel.isVisible{panel.orderOut(nil)}
        card.isHidden=true;showing=false
    }
}

final class MenuTransfer:NSObject, NSMenuDelegate {
    private let item=NSStatusBar.system.statusItem(withLength:NSStatusItem.squareLength)
    private let shelf=DropShelf()
    private var trackingTimer:Timer?
    private var downPoint:NSPoint?
    private var monitors:[Any]=[]
    private let dragBoard=NSPasteboard(name:.drag)
    private var generation:Int?
    private let endpoint:URL,secret:String,show:()->Void
    private var state:[String:Any]=[:],timer:Timer?,polling=false,lastIcon=""
    init(port:Int,key:String,show:@escaping()->Void){
        endpoint=URL(string:"http://127.0.0.1:\(port)/api/native")!;secret=key;self.show=show;super.init()
        guard let b=item.button else{return}
        b.image=NSImage(systemSymbolName:"paperplane",accessibilityDescription:"TransferBay")
        b.setAccessibilityLabel("TransferBay");b.toolTip="TransferBay · 拖入文件发送"
        b.target=self;b.action=#selector(openMenu)
        let drop=DropTarget(frame:b.bounds);drop.autoresizingMask=[.width,.height];drop.wantsLayer=true;drop.layer?.cornerRadius=4
        drop.onFiles={ [weak self] in self?.send($0) };drop.onClick={ [weak self] in self?.openMenu() };b.addSubview(drop)
        shelf.onFiles={ [weak self] in self?.send($0) }
        shelf.peer={ [weak self] in self?.state["peer"] as? String }
        drop.onFileDrag={ [weak self] count in
            guard let self=self,let (icon,screen)=self.anchor() else{return}
            self.shelf.iconTarget=icon
            self.shelf.arm(DropShelf.layout(icon:icon,screen:screen));self.shelf.reveal(count)
        }
        drop.onExit={ [weak self] in self?.shelf.leave() }
        drop.onEnd={ [weak self] in self?.shelf.released() }
        // Mouse-only notifications; never monitor keys or require Accessibility access.
        let mask:NSEvent.EventTypeMask=[.leftMouseDown,.leftMouseDragged,.leftMouseUp]
        let observe: (NSEvent)->Void = { [weak self] event in
            guard let self=self else{return}
            if event.type == .leftMouseDown {self.generation=self.dragBoard.changeCount;self.downPoint=NSEvent.mouseLocation}
            else if event.type == .leftMouseUp {self.downPoint=nil;self.generation=nil;self.shelf.released()}
            else {self.trackDrag(moved:true)}
        }
        if let m=NSEvent.addGlobalMonitorForEvents(matching:mask,handler:observe){monitors.append(m)}
        if let m=NSEvent.addLocalMonitorForEvents(matching:mask,handler:{ e in observe(e);return e }){monitors.append(m)}
        let watch=Timer(timeInterval:0.12,repeats:true){[weak self] _ in self?.trackDrag()}
        watch.tolerance=0.025;trackingTimer=watch;RunLoop.main.add(watch,forMode:.common)
        let t=Timer(timeInterval:2.5,repeats:true){[weak self] _ in self?.poll()};timer=t;RunLoop.main.add(t,forMode:.common);poll()
    }
    deinit{for m in monitors{NSEvent.removeMonitor(m)};trackingTimer?.invalidate();timer?.invalidate()}
    private func anchor()->(NSRect,NSRect)?{
        guard let b=item.button,let win=b.window,let screen=win.screen,win.isVisible else{return nil}
        let icon=win.convertToScreen(b.convert(b.bounds,to:nil))
        guard icon.intersects(screen.frame) else{return nil}
        return (icon,screen.frame)
    }
    private func trackDrag(moved:Bool=false){
        guard NSEvent.pressedMouseButtons & 1 != 0 else{downPoint=nil;generation=nil;shelf.released();return}
        let p=NSEvent.mouseLocation
        if downPoint==nil{downPoint=p;if !moved{return}}
        guard let start=downPoint,moved || hypot(start.x-p.x,start.y-p.y)>3 || shelf.showing,
              let (icon,screen)=anchor() else{return}
        shelf.track(held:true,at:p,icon:icon,screen:screen)
        // When approaching sideways along the menu bar, confirm a fresh file gesture
        // by type. The panel stays *below* the bar so adjacent system items remain usable.
        let near=DropShelf.layout(icon:icon,screen:screen).insetBy(dx:-5,dy:-3).union(icon.insetBy(dx:-65,dy:0))
        if !shelf.showing,near.contains(p),let baseline=generation,
           baseline != dragBoard.changeCount,dragBoard.availableType(from:[.fileURL]) != nil {
            shelf.arm(DropShelf.layout(icon:icon,screen:screen));shelf.reveal(dragBoard.pasteboardItems?.count ?? 1)
        }
    }
    private func update(_ json:[String:Any]){
        state=json;let pending=json["ask"] is [String:Any] || !(json["incoming"] as? [[String:Any]] ?? []).isEmpty
        let symbol=pending ? "tray.and.arrow.down.fill":((json["peer"] is String) ? "paperplane.fill":"paperplane")
        if symbol != lastIcon {item.button?.image=NSImage(systemSymbolName:symbol,accessibilityDescription:"TransferBay");lastIcon=symbol}
        let note=json["notice"] as? String ?? ""
        item.button?.toolTip="TransferBay · "+(note.isEmpty ? (json["peer"] as? String ?? "尚未配对"):note)
    }
    private func call(_ body:[String:Any],quiet:Bool=false,done:(()->Void)?=nil){
        var req=URLRequest(url:endpoint);req.httpMethod="POST";req.timeoutInterval=3600;req.httpBody=try? JSONSerialization.data(withJSONObject:body)
        req.setValue("application/json",forHTTPHeaderField:"Content-Type");req.setValue("Bearer "+secret,forHTTPHeaderField:"Authorization")
        URLSession.shared.dataTask(with:req){[weak self] data,response,error in
            let status=(response as? HTTPURLResponse)?.statusCode
            let obj=data.flatMap{try? JSONSerialization.jsonObject(with:$0) as? [String:Any]} ?? [:]
            DispatchQueue.main.async{guard let self=self else{return};defer{done?()}
                if status==200{self.update(obj)}else if !quiet{let a=NSAlert();a.messageText="TransferBay";a.informativeText=obj["error"] as? String ?? error?.localizedDescription ?? "服务未连接";a.runModal()}
            }
        }.resume()
    }
    private func poll(){if polling{return};polling=true;call(["op":"state"],quiet:true){[weak self] in self?.polling=false}}
    private func send(_ files:[URL]){call(["op":"drop","paths":files.map(\.path)])}
    private func line(_ m:NSMenu,_ title:String,_ action:Selector?=nil,_ object:Any?=nil){let v=NSMenuItem(title:title,action:action,keyEquivalent:"");v.target=self;v.representedObject=object;m.addItem(v)}
    @objc private func openMenu(){
        guard let b=item.button else{return};let m=NSMenu()
        let peer=state["peer"] as? String, notice=state["notice"] as? String ?? ""
        line(m,peer.map{"已连接 · "+$0} ?? "TransferBay · 尚未配对")
        if !notice.isEmpty{line(m,notice)}
        if let a=state["ask"] as? [String:Any],let id=a["id"] as? String{if let words=a["words"] as? String{line(m,"请核对："+words)};line(m,"允许 "+(a["name"] as? String ?? "设备")+" 配对",#selector(accept(_:)),id);line(m,"拒绝请求",#selector(decline(_:)),id)}
        if peer != nil{line(m,"选择文件发送…",#selector(selectFiles))}
        for f in (state["incoming"] as? [[String:Any]] ?? []).prefix(8){if let id=f["id"] as? String,let name=f["name"] as? String{line(m,"重试保存 "+name,#selector(save(_:)),id)}}
        m.addItem(.separator());line(m,"打开主窗口",#selector(reopen));line(m,"退出 TransferBay",#selector(quit));m.popUp(positioning:nil,at:NSPoint(x:0,y:b.bounds.minY),in:b)
    }
    @objc private func selectFiles(){NSApp.activate(ignoringOtherApps:true);let p=NSOpenPanel();p.allowsMultipleSelection=true;p.canChooseDirectories=false;if p.runModal() == .OK{send(p.urls)}}
    @objc private func save(_ sender:NSMenuItem){if let id=sender.representedObject as? String{call(["op":"save","id":id])}}
    @objc private func accept(_ sender:NSMenuItem){answer(sender,true)}
    @objc private func decline(_ sender:NSMenuItem){answer(sender,false)}
    private func answer(_ s:NSMenuItem,_ accepted:Bool){if let id=s.representedObject as? String{call(["op":"answer","id":id,"accept":accepted])}}
    @objc private func reopen(){show()}
    @objc private func quit(){NSApp.terminate(nil)}
}
