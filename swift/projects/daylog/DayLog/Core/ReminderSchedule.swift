import Foundation

public struct ScheduledReminder: Equatable, Sendable {
    public var id: String
    public var dayID: String
    public var date: Date
    public var title: String
}
public enum ReminderSchedule {
    public static func time(_ text: String) -> (Int, Int)? {
        let parts = text.split(separator: ":", omittingEmptySubsequences: false)
        guard parts.count == 2, let h = Int(parts[0]), let m = Int(parts[1]), (0...23).contains(h), (0...59).contains(m) else { return nil }
        return (h,m)
    }
    public static func validate(_ prefs: ReminderPreferences) throws {
        guard time(prefs.morning) != nil, time(prefs.evening) != nil,
              prefs.weekdays.allSatisfy({ (1...7).contains($0) }), Set(prefs.weekdays).count == prefs.weekdays.count else { throw DomainError.invalid("提醒时间应为 HH:mm，工作周配置必须有效") }
        let format = DateFormatter(); format.calendar = Calendar(identifier: .gregorian); format.locale = Locale(identifier: "en_US_POSIX"); format.timeZone = TimeZone(secondsFromGMT: 0); format.dateFormat = "yyyy-MM-dd"; format.isLenient = false
        guard prefs.overrides.keys.allSatisfy({ key in format.date(from:key).map { format.string(from:$0) == key } ?? false }) else { throw DomainError.invalid("日期例外应为 yyyy-MM-dd") }
    }
    public static func requests(workspace: Workspace, now: Date, horizon: Int = 14) throws -> [ScheduledReminder] {
        try validate(workspace.reminders)
        guard workspace.reminders.enabled else { return [] }
        let calendar = workspace.calendar
        var result: [ScheduledReminder] = []
        for offset in 0..<max(0,horizon) {
            guard let day = calendar.date(byAdding: .day, value: offset, to: calendar.startOfDay(for: now)) else { continue }
            let key = workspace.dayID(at: day), weekday = calendar.component(.weekday, from: day)
            guard workspace.reminders.overrides[key] ?? workspace.reminders.weekdays.contains(weekday) else { continue }
            for (kind, text, title) in [("morning", workspace.reminders.morning, "安排今天的工作"), ("evening", workspace.reminders.evening, "回顾今天的进展")] {
                let (h,m) = time(text)!
                // Calendar handles DST gaps; never add a fixed 86400 seconds.
                guard let date = calendar.date(bySettingHour:h, minute:m, second:0, of:day), date > now else { continue }
                result.append(ScheduledReminder(id:"daylog.\(key).\(kind)", dayID:key, date:date, title:title))
            }
        }
        return result.sorted { $0.date < $1.date }
    }
}
