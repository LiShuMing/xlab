import AppKit
import SwiftUI
import DayLogCore

// Render production views into isolated offscreen windows. This is a visual
// fixture, not a screenshot of the user's desktop or a substitute for UI tests.
@main @MainActor struct AppearanceChecks {
    static func main() {
        let app = NSApplication.shared
        app.setActivationPolicy(.prohibited)
        Task { @MainActor in
            do {
                try await render()
                exit(0)
            } catch {
                print("FAIL: \(error)")
                exit(1)
            }
        }
        app.run()
    }

    static func render() async throws {
        guard CommandLine.arguments.count == 2 else {throw DomainError.invalid("Supply output directory")}
        let output = URL(fileURLWithPath:CommandLine.arguments[1],isDirectory:true)
        try FileManager.default.createDirectory(at:output,withIntermediateDirectories:true)
        let icon = ImageRenderer(content:KebaiAppIcon().frame(width:1024,height:1024))
        guard let cgImage=icon.cgImage,
              let iconPNG=NSBitmapImageRep(cgImage:cgImage).representation(using:.png,properties:[:]) else {
            throw DomainError.invalid("Cannot export brand icon")
        }
        try iconPNG.write(to:output.appendingPathComponent("kebai-icon.png"))
        print("PASS: rendered clean vector icon")
        let store = AppStore(inMemory:true,demoData:true)
        await store.waitUntilReady()
        guard store.fatalError == nil, store.config == nil else {throw DomainError.invalid("Fixture is not isolated")}
        for (name, dark, route) in [
            ("today-light",false,"today"), ("today-dark",true,"today"),
            ("history-light",false,"history"), ("journal-light",false,"journal"),
            ("settings-light",false,"settings"), ("settings-dark",true,"settings"),
            ("review-light",false,"today"), ("menu-light",false,"menu"),
            ("drafts-light",false,"drafts")
        ] {
            store.route=route
            store.inspector = name == "review-light" ? "review" : "task"
            let appearance = NSAppearance(named:dark ? .darkAqua : .aqua)!
            NSApp.appearance=appearance
            // Separate process and bundle defaults; never touch the real app's preferences.
            UserDefaults.standard.set(dark ? "dark" : "light",forKey:"appearance")
            let size = route == "menu" ? CGSize(width:360,height:490) : route == "drafts" ? CGSize(width:600,height:340) : CGSize(width:1080,height:780)
            let view: AnyView
            if route == "menu" {
                view=AnyView(MenuBarView(store:store))
            } else if route == "drafts" {
                store.newTaskDraft="完善亮色主题的使用体验"
                view=AnyView(DraftsView(store:store))
            } else {
                view=AnyView(WorkspaceView(store:store))
            }
            let root = view.environment(\.colorScheme,dark ? .dark : .light)
                .frame(width:size.width,height:size.height)
            let host=NSHostingView(rootView:root)
            host.frame=NSRect(origin:.zero,size:size)
            host.appearance=appearance
            let window=NSWindow(contentRect:host.frame,styleMask:.borderless,backing:.buffered,defer:false)
            window.isReleasedWhenClosed=false
            window.appearance=appearance
            window.contentView=host
            host.layoutSubtreeIfNeeded()
            try await Task.sleep(for:.milliseconds(250))
            host.layoutSubtreeIfNeeded()
            guard let bitmap=host.bitmapImageRepForCachingDisplay(in:host.bounds) else {throw DomainError.invalid("No bitmap")}
            host.cacheDisplay(in:host.bounds,to:bitmap)
            guard let png=bitmap.representation(using:.png,properties:[:]) else {throw DomainError.invalid("No PNG")}
            try png.write(to:output.appendingPathComponent("\(name).png"))
            window.close()
            print("PASS: rendered \(name)")
        }
    }
}
