import Foundation

public enum TaskStatus: String, Codable, CaseIterable, Sendable {
    case todo, doing, done
    public var label: String { switch self { case .todo: "待开始"; case .doing: "进行中"; case .done: "已完成" } }
}
public enum DaySection: String, Codable, CaseIterable, Sendable {
    case day, closing
    public var label: String { self == .day ? "今天" : "收尾时" }
}
public struct TaskStep: Codable, Identifiable, Equatable, Sendable {
    public var id = UUID()
    public var text: String
    public var done = false
    public init(text: String) { self.text = text }
}
public struct WorkTask: Codable, Identifiable, Equatable, Sendable {
    public var id = UUID()
    public var title: String
    public var notes = ""
    public var status = TaskStatus.todo
    public var lastOpenStatus = TaskStatus.todo
    public var steps: [TaskStep] = []
    public var revision = 0
    public var createdAt: Date
    public init(title: String, now: Date) { self.title = title; self.createdAt = now }
}
public struct PlanItem: Codable, Identifiable, Equatable, Sendable {
    public var id = UUID()
    public var taskID: UUID
    public var section = DaySection.day
    public var snapshot: WorkTask?
    public init(taskID: UUID) { self.taskID = taskID }
}
public struct WorkDay: Codable, Identifiable, Equatable, Sendable {
    public var id: String
    public var timeZoneID: String
    public var start: Date
    public var end: Date
    public var focus = ""
    public var plans: [PlanItem] = []
    public var closed = false
}
public enum EntryKind: String, Codable, Sendable { case work, personal, progress, summary }
public struct JournalEntry: Codable, Identifiable, Equatable, Sendable {
    public var id = UUID()
    public var dayID: String
    public var taskID: UUID?
    public var body: String
    public var kind: EntryKind
    public var time: Date
    public init(dayID: String, taskID: UUID? = nil, body: String, kind: EntryKind, time: Date) {
        self.dayID = dayID; self.taskID = taskID; self.body = body; self.kind = kind; self.time = time
    }
}
public struct TaskEvent: Codable, Identifiable, Equatable, Sendable {
    public var id = UUID()
    public var taskID: UUID
    public var time: Date
    public var message: String
    public var before: WorkTask?
    public var after: WorkTask
}
public struct ReviewDraft: Codable, Identifiable, Equatable, Sendable {
    public var id = UUID()
    public var dayIDs: [String]
    public var source: Data
    public var text: String
    public var createdAt: Date
    public var acceptedEntryID: UUID?
    public init(dayIDs: [String], source: Data, text: String, createdAt: Date) {
        self.dayIDs = dayIDs; self.source = source; self.text = text; self.createdAt = createdAt
    }
}
public struct ReminderPreferences: Codable, Equatable, Sendable {
    public var enabled = false
    public var morning = "09:30"
    public var evening = "18:00"
    public var weekdays = [2, 3, 4, 5, 6] // Calendar: Sunday = 1
    public var overrides: [String: Bool] = [:]
    public init() {}
}
public enum DomainError: Error, LocalizedError {
    case invalid(String)
    case conflict
    case closedDay
    case staleReview
    public var errorDescription: String? {
        switch self {
        case .invalid(let reason): reason
        case .conflict: "内容已在另一个入口更新。请重新打开任务后编辑。"
        case .closedDay: "这个日期已归档，不能修改当日任务状态。"
        case .staleReview: "草稿来源已变化，请重新生成后采纳。"
        }
    }
}

public struct Workspace: Codable, Equatable, Sendable {
    public var schemaVersion = 1
    public var timeZoneID = TimeZone.current.identifier
    public var tasks: [WorkTask] = []
    public var days: [WorkDay] = []
    public var entries: [JournalEntry] = []
    public var events: [TaskEvent] = []
    public var reviews: [ReviewDraft] = []
    public var reminders = ReminderPreferences()
    public init() {}
    public var calendar: Calendar {
        var result = Calendar(identifier: .gregorian)
        result.timeZone = TimeZone(identifier: timeZoneID) ?? .current
        return result
    }
    public func dayID(at date: Date) -> String {
        let c = calendar.dateComponents([.year, .month, .day], from: date)
        return String(format: "%04d-%02d-%02d", c.year!, c.month!, c.day!)
    }
    @discardableResult public mutating func prepareDay(at now: Date) throws -> String {
        for index in days.indices where !days[index].closed && days[index].end <= now {
            for p in days[index].plans.indices {
                days[index].plans[p].snapshot = tasks.first { $0.id == days[index].plans[p].taskID }
            }
            days[index].closed = true
        }
        let key = dayID(at: now)
        if let day = days.first(where: { $0.id == key }) {
            guard !day.closed else { throw DomainError.closedDay }
        } else {
            let start = calendar.startOfDay(for: now)
            guard let end = calendar.date(byAdding: .day, value: 1, to: start) else { throw DomainError.invalid("日期无效") }
            days.append(WorkDay(id: key, timeZoneID: timeZoneID, start: start, end: end))
        }
        return key
    }
    public func task(_ id: UUID) -> WorkTask? { tasks.first { $0.id == id } }
    public func displayedTask(_ plan: PlanItem, day: WorkDay) -> WorkTask? { day.closed ? plan.snapshot : task(plan.taskID) }
    @discardableResult public mutating func addTask(_ title: String, now: Date) throws -> UUID {
        let title = title.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !title.isEmpty, title.count <= 500 else { throw DomainError.invalid("请输入不超过 500 字的任务标题") }
        let day = try prepareDay(at: now)
        let task = WorkTask(title: title, now: now)
        tasks.append(task)
        try carry(task.id, to: day)
        events.append(TaskEvent(taskID: task.id, time: now, message: "创建任务", before: nil, after: task))
        return task.id
    }
    public mutating func carry(_ id: UUID, to dayID: String) throws {
        guard task(id) != nil, let d = days.firstIndex(where: { $0.id == dayID }), !days[d].closed else { throw DomainError.closedDay }
        if !days[d].plans.contains(where: { $0.taskID == id }) { days[d].plans.append(PlanItem(taskID: id)) }
    }
    public mutating func updateTask(_ id: UUID, expectedRevision: Int? = nil, now: Date, message: String,
                                    change: (inout WorkTask) -> Void) throws {
        _ = try prepareDay(at: now)
        guard let i = tasks.firstIndex(where: { $0.id == id }) else { throw DomainError.invalid("任务不存在") }
        if let expectedRevision, tasks[i].revision != expectedRevision { throw DomainError.conflict }
        let before = tasks[i]
        var updated = before
        change(&updated)
        updated.title = updated.title.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !updated.title.isEmpty, updated.title.count <= 500 else { throw DomainError.invalid("任务标题不能为空或超过 500 字") }
        guard updated != before else { return }
        if updated.status == .done && before.status != .done { updated.lastOpenStatus = before.status }
        updated.revision = before.revision + 1
        tasks[i] = updated
        events.append(TaskEvent(taskID: id, time: now, message: message, before: before, after: updated))
    }
    public mutating func setSection(taskID: UUID, section: DaySection, now: Date) throws {
        let day = try prepareDay(at: now)
        guard let d = days.firstIndex(where: { $0.id == day }), let p = days[d].plans.firstIndex(where: { $0.taskID == taskID }) else { return }
        days[d].plans[p].section = section
    }
    public func canUndoStatusChange(_ eventID: UUID) -> Bool {
        guard let event = events.last(where: {$0.id == eventID}),
              let before = event.before, before.status != event.after.status,
              task(event.taskID)?.status == event.after.status else {return false}
        // Compare status-changing events, not the task's general edit revision.
        // This also rejects an intervening A -> B -> A change (ABA).
        return events.last(where: {$0.taskID == event.taskID && $0.before != nil && $0.before?.status != $0.after.status})?.id == eventID
    }
    public mutating func undoStatusChange(_ eventID: UUID, now: Date) throws {
        _ = try prepareDay(at:now)
        guard canUndoStatusChange(eventID), let event = events.last(where: {$0.id == eventID}),
              let previous = event.before, let index = tasks.firstIndex(where: {$0.id == event.taskID}) else {
            throw DomainError.invalid("任务状态已有后续修改，这次撤销已失效")
        }
        let before = tasks[index]
        var after = before
        after.status = previous.status; after.lastOpenStatus = previous.lastOpenStatus
        after.revision += 1
        tasks[index] = after
        events.append(TaskEvent(taskID:after.id,time:now,message:"撤销状态修改",before:before,after:after))
    }
    public mutating func appendEntry(_ body: String, kind: EntryKind, taskID: UUID? = nil, now: Date) throws {
        let text = body.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        let day = try prepareDay(at: now)
        guard taskID == nil || task(taskID!) != nil else { throw DomainError.invalid("任务不存在") }
        entries.append(JournalEntry(dayID: day, taskID: taskID, body: text, kind: kind, time: now))
    }
    public func reviewSource(dayIDs: [String]) throws -> Data {
        struct Source: Codable { var days: [WorkDay]; var tasks: [WorkTask]; var entries: [JournalEntry] }
        let selectedDays = days.filter { dayIDs.contains($0.id) }.sorted { $0.id < $1.id }
        let openIDs = Set(selectedDays.filter { !$0.closed }.flatMap(\.plans).map(\.taskID))
        let source = Source(days: selectedDays, tasks: tasks.filter { openIDs.contains($0.id) }.sorted { $0.id.uuidString < $1.id.uuidString }, entries: entries.filter { dayIDs.contains($0.dayID) && $0.kind != .personal && $0.kind != .summary }.sorted { $0.id.uuidString < $1.id.uuidString })
        let encoder = JSONEncoder(); encoder.outputFormatting = [.sortedKeys]; encoder.dateEncodingStrategy = .iso8601
        return try encoder.encode(source)
    }
    @discardableResult public mutating func acceptReview(_ id: UUID, now: Date) throws -> UUID {
        _ = try prepareDay(at: now)
        guard let i = reviews.firstIndex(where: { $0.id == id }) else { throw DomainError.invalid("草稿不存在") }
        if let accepted = reviews[i].acceptedEntryID { return accepted }
        guard reviews[i].source == (try reviewSource(dayIDs: reviews[i].dayIDs)) else { throw DomainError.staleReview }
        guard !reviews[i].text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { throw DomainError.invalid("草稿为空") }
        let entry = JournalEntry(dayID: dayID(at: now), body: reviews[i].text, kind: .summary, time: now)
        entries.append(entry); reviews[i].acceptedEntryID = entry.id
        return entry.id
    }
    public func encoded(pretty: Bool = true) throws -> Data {
        let e = JSONEncoder(); e.outputFormatting = pretty ? [.prettyPrinted, .sortedKeys] : [.sortedKeys]; e.dateEncodingStrategy = .iso8601
        return try e.encode(self)
    }
    public static func decode(_ data: Data) throws -> Workspace {
        let d = JSONDecoder(); d.dateDecodingStrategy = .iso8601
        let state = try d.decode(Workspace.self, from: data)
        try state.validate(); return state
    }
    // Resource limits belong to explicitly imported files, not trusted local
    // documents. A successful local save must always be readable on restart.
    public static let backupImportLimit = 50_000_000
    public static func decodeBackup(_ data: Data) throws -> Workspace {
        guard data.count <= backupImportLimit else {throw DomainError.invalid("导入备份超过 50 MB；本地数据库不受此限制")}
        return try decode(data)
    }
    public static func readBackup(from url: URL) throws -> Workspace {
        // URL resource values may cache the size after a file is replaced.
        let size = (try FileManager.default.attributesOfItem(atPath:url.path)[.size] as? NSNumber)?.intValue
        guard let size, size <= backupImportLimit else {throw DomainError.invalid("导入备份超过 50 MB；本地数据库不受此限制")}
        let file = try FileHandle(forReadingFrom:url); defer {try? file.close()}
        // Bounded read also covers a file growing after the metadata check.
        let data = try file.read(upToCount:backupImportLimit+1) ?? Data()
        return try decodeBackup(data)
    }
    public func validate() throws {
        guard schemaVersion == 1, TimeZone(identifier: timeZoneID) != nil else { throw DomainError.invalid("不支持的备份版本或时区") }
        let taskIDs = Set(tasks.map(\.id)), dayIDs = Set(days.map(\.id))
        guard taskIDs.count == tasks.count, dayIDs.count == days.count,
              Set(entries.map(\.id)).count == entries.count, Set(reviews.map(\.id)).count == reviews.count,
              Set(events.map(\.id)).count == events.count else { throw DomainError.invalid("备份包含重复 ID") }
        for day in days {
            guard day.id == dayID(at:day.start), day.timeZoneID == timeZoneID,
                  day.start == calendar.startOfDay(for:day.start), day.end == calendar.date(byAdding:.day,value:1,to:day.start),
                  Set(day.plans.map(\.id)).count == day.plans.count, Set(day.plans.map(\.taskID)).count == day.plans.count,
                  day.plans.allSatisfy({ taskIDs.contains($0.taskID) && (!day.closed || $0.snapshot?.id == $0.taskID) }) else { throw DomainError.invalid("日计划关系不完整") }
        }
        guard entries.allSatisfy({ dayIDs.contains($0.dayID) && ($0.taskID == nil || taskIDs.contains($0.taskID!)) }),
              events.allSatisfy({ taskIDs.contains($0.taskID) && $0.after.id == $0.taskID }),
              reviews.allSatisfy({ review in review.dayIDs.allSatisfy(dayIDs.contains) && (review.acceptedEntryID == nil || entries.contains(where: { $0.id == review.acceptedEntryID })) }) else { throw DomainError.invalid("备份引用不完整") }
        for task in tasks {
            guard !task.title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty, task.title.count <= 500, task.revision >= 0,
                  task.lastOpenStatus != .done, Set(task.steps.map(\.id)).count == task.steps.count,
                  task.steps.allSatisfy({!$0.text.trimmingCharacters(in:.whitespacesAndNewlines).isEmpty}) else { throw DomainError.invalid("备份任务无效") }
        }
        try ReminderSchedule.validate(reminders)
    }
    public func markdown(dayIDs: [String]) -> String {
        days.filter { dayIDs.contains($0.id) }.sorted { $0.id < $1.id }.map { day in
            let rows = day.plans.compactMap { plan -> String? in
                guard let task = displayedTask(plan, day: day) else { return nil }
                return "- [\(task.status == .done ? "x" : " ")] \(task.title)"
            }
            let logs = entries.filter { $0.dayID == day.id && $0.kind != .personal }.map { "- \($0.body)" }
            return (["# \(day.id)", "", day.focus, "", "## 待办"] + rows + ["", "## 工作记录"] + logs).joined(separator: "\n")
        }.joined(separator: "\n\n")
    }
}
