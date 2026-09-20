import Foundation
import UserNotifications
import DayLogCore

@MainActor final class ReminderService {
    private var queued: Task<String,Error>?
    func authorize() async throws -> Bool {
        try await UNUserNotificationCenter.current().requestAuthorization(options:[.alert,.sound,.badge])
    }
    func reconcile(_ workspace: Workspace) async throws -> String {
        let previous = queued
        let next = Task { @MainActor in
            _ = try? await previous?.value
            return try await self.apply(workspace)
        }
        queued = next
        return try await next.value
    }
    private func apply(_ workspace: Workspace) async throws -> String {
        let center = UNUserNotificationCenter.current()
        let existing = await center.pendingNotificationRequests()
        let own = existing.filter { $0.identifier.hasPrefix("daylog.") }.map(\.identifier)
        guard workspace.reminders.enabled else { center.removePendingNotificationRequests(withIdentifiers:own); return "提醒已关闭" }
        let status = await center.notificationSettings().authorizationStatus
        guard status == .authorized || status == .provisional else {
            center.removePendingNotificationRequests(withIdentifiers:own)
            return "未获得通知权限，请在系统设置中允许通知"
        }
        let requests = try ReminderSchedule.requests(workspace:workspace,now:Date())
        center.removePendingNotificationRequests(withIdentifiers:own)
        for item in requests {
            let content = UNMutableNotificationContent(); content.title = item.title; content.body = "打开刻白，记录和整理你的工作。"; content.sound = .default
            content.userInfo = ["dayID":item.dayID]
            var components = workspace.calendar.dateComponents([.year,.month,.day,.hour,.minute],from:item.date)
            components.timeZone = workspace.calendar.timeZone
            try await center.add(UNNotificationRequest(identifier:item.id,content:content,trigger:UNCalendarNotificationTrigger(dateMatching:components,repeats:false)))
        }
        return "已安排未来 14 天内 \(requests.count) 条提醒"
    }
}
