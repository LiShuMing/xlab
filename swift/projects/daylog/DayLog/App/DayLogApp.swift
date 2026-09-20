import SwiftUI
import UserNotifications
import DayLogCore

@MainActor final class AppDelegate: NSObject, NSApplicationDelegate, UNUserNotificationCenterDelegate {
    var store: AppStore? {didSet {if let pendingDay {self.pendingDay=nil; openNotification(dayID:pendingDay)}}}
    private var pendingDay: String?
    private var timer: Timer?
    func applicationDidFinishLaunching(_ notification: Notification) {
        UNUserNotificationCenter.current().delegate = self
        NSWorkspace.shared.notificationCenter.addObserver(self,selector:#selector(wake),name:NSWorkspace.didWakeNotification,object:nil)
        timer = Timer.scheduledTimer(timeInterval:60,target:self,selector:#selector(refresh),userInfo:nil,repeats:true)
    }
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { false }
    func applicationShouldHandleReopen(_ sender: NSApplication,hasVisibleWindows flag: Bool) -> Bool {store?.showWindow?(); return true}
    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        guard let store else {return .terminateNow}
        if store.isRestoring {return .terminateCancel}
        if store.isTerminating {return .terminateLater}
        if store.hasUnsavedChanges {
            let alert = NSAlert(); alert.messageText = "有 \(store.pendingDrafts.count) 处未保存内容"
            alert.informativeText = "可查看并定位输入，或保存全部后退出。保存全部会提交私人日记；回顾文字只保存为草稿。放弃只丢弃未提交输入。"
            alert.addButton(withTitle:"查看未保存内容"); alert.addButton(withTitle:"保存全部并退出"); alert.addButton(withTitle:"放弃草稿并退出")
            let choice=alert.runModal()
            if choice == .alertFirstButtonReturn {store.presentDrafts(); return .terminateCancel}
            if choice == .alertSecondButtonReturn && !store.saveDrafts() {
                let failure=store.error; store.presentDrafts(); store.error=failure; return .terminateCancel
            }
        }
        guard store.saves.hasPendingWrites else {return .terminateNow}
        store.isTerminating=true
        Task {
            let success = await store.flushForTermination()
            sender.reply(toApplicationShouldTerminate:success)
            if !success {store.error="保存未成功，已取消退出。请重试保存或先导出备份。"; store.showWindow?()}
        }
        return .terminateLater
    }
    @objc func refresh() { store?.refreshDay() }
    @objc func wake() {store?.refreshDay(); Task {await store?.syncReminders()}}
    private func openNotification(dayID: String) {
        guard let store else {pendingDay=dayID; return}
        store.refreshDay()
        if !dayID.isEmpty && dayID != store.todayID {store.route="history"; store.historyDayID=dayID} else {store.route="today"}
        NSApp.activate(ignoringOtherApps:true); store.showWindow?()
    }
    nonisolated func userNotificationCenter(_ center: UNUserNotificationCenter, didReceive response: UNNotificationResponse) async {
        let dayID = response.notification.request.content.userInfo["dayID"] as? String
        await MainActor.run {
            self.openNotification(dayID:dayID ?? "")
        }
    }
    nonisolated func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent notification: UNNotification) async -> UNNotificationPresentationOptions { [.banner,.sound] }
}

@main @MainActor struct DayLogApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var delegate
    @State private var store: AppStore
    init() {
        if ProcessInfo.processInfo.arguments.dropFirst().first?.hasPrefix("--storage-") == true {
            Task.detached {exit(await StorageChecks.run(ProcessInfo.processInfo.arguments) ?? 1)}
            dispatchMain()
        }
        #if DAYLOG_DEVELOPMENT
        let demo = true
        #else
        let demo = ProcessInfo.processInfo.arguments.contains("--demo")
        #endif
        _store = State(initialValue:AppStore(inMemory:demo, demoData:demo))
    }
    var body: some Scene {
        Window("刻白",id:"workspace") {
            WorkspaceView(store:store)
                .onAppear { delegate.store = store }
        }
        .defaultSize(width:1080,height:780)
        .commands {
            CommandGroup(replacing:.newItem) {
                Button("新建待办") { store.route = "today"; store.showWindow?(); NotificationCenter.default.post(name:Notification.Name("DayLogQuickAdd"),object:nil) }.keyboardShortcut("n")
            }
            CommandGroup(replacing:.saveItem) {
                Button("保存全部") {if !store.saveDrafts() {let failure=store.error; store.presentDrafts(); store.error=failure}}.keyboardShortcut("s").disabled(!store.hasUnsavedChanges)
                Button("查看未保存内容…") {store.presentDrafts()}.disabled(!store.hasUnsavedChanges)
            }
            CommandGroup(after:.saveItem) {
                Button("导出 Markdown…") { store.export(json:false) }
                Button("备份 JSON…") { store.export(json:true) }
            }
        }
        MenuBarExtra { MenuBarView(store:store) } label: {
            KebaiMark(monochrome:true).frame(width:18,height:18).accessibilityLabel("刻白")
        }.menuBarExtraStyle(.window)
        Settings { SettingsView(store:store).frame(width:640,height:640) }
    }
}
