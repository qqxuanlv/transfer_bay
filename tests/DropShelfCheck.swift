import Cocoa

@main struct DropShelfCheck {
    static func main(){
        _=NSApplication.shared
        let shelf=DropShelf(),screen=NSScreen.main!.frame
        let icon=NSRect(x:screen.midX,y:screen.maxY-24,width:24,height:24)
        let nearby=NSPoint(x:icon.midX-60,y:icon.minY-10)
        let move={ (held:Bool,p:NSPoint) in shelf.track(held:held,at:p,icon:icon,screen:screen) }
        let text=NSPasteboard.withUniqueName(),files=NSPasteboard.withUniqueName()
        defer{text.releaseGlobally();files.releaseGlobally()}
        text.setString("just text",forType:.string)
        let urls=[URL(fileURLWithPath:"/tmp/shelf-test-A"),URL(fileURLWithPath:"/tmp/shelf-test-B")]
        files.writeObjects(urls as [NSURL])
        var sent=[[URL]]();shelf.onFiles={sent.append($0)}
        move(false,nearby);assert(!shelf.showing)
        move(true,nearby);assert(!shelf.showing && shelf.destination.window!.isVisible)
        assert(shelf.destination.enter(text).isEmpty && !shelf.showing)
        assert(shelf.destination.enter(files) == .copy && shelf.showing)
        shelf.leave();_ = shelf.destination.enter(files)
        RunLoop.main.run(until:Date().addingTimeInterval(0.16));assert(shelf.showing)
        move(true,NSPoint(x:screen.midX,y:screen.midY));assert(!shelf.showing && sent.isEmpty)
        move(true,nearby);_=shelf.destination.enter(files);shelf.leave()
        RunLoop.main.run(until:Date().addingTimeInterval(0.16));assert(!shelf.showing && sent.isEmpty)
        move(false,nearby);move(true,nearby);_=shelf.destination.enter(files)
        assert(shelf.destination.accept(files) && !shelf.showing && sent==[urls])
        move(false,nearby);assert(!shelf.destination.window!.isVisible)
        let left=DropShelf.layout(icon:NSRect(x:screen.minX,y:icon.minY,width:24,height:24),screen:screen)
        assert(screen.contains(left))
        print("PASS: AppKit file-only reveal, icon-to-panel hold, leave, cancel, single drop and screen-edge layout")
    }
}
