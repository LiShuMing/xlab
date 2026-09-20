import Foundation
import DayLogCore

enum DraftID: Hashable {
    case task(UUID), step(UUID), progress(UUID), review(UUID)
    case newTask, menuTask, focus, workNote, journal, reminderTimes, reminderException
    var taskID: UUID? {
        switch self {case .task(let id), .step(let id), .progress(let id): id; default: nil}
    }
}
struct PendingDraft: Identifiable {
    let id: DraftID
    let title: String
    let detail: String
}
enum DraftPurpose: Equatable {case manage, review([String]), export(json: Bool)}
struct DraftNavigation: Equatable {var id=UUID(); let target: DraftID}
struct ExportDocument: Sendable {
    let snapshot: Workspace
    let json: Bool
    let omittedCount: Int
    func data() throws -> Data {json ? try snapshot.encoded() : Data(snapshot.markdown(dayIDs:snapshot.days.map(\.id)).utf8)}
}

@MainActor extension AppStore {
    var pendingDrafts: [PendingDraft] {
        var result: [PendingDraft] = []
        func add(_ id: DraftID, _ title: String, _ text: String, changed: Bool? = nil) {
            if changed ?? !text.trimmingCharacters(in:.whitespacesAndNewlines).isEmpty {
                result.append(PendingDraft(id:id,title:title,detail:String(text.prefix(100))))
            }
        }
        // Task text precedes steps, so their shared revision is checked once
        // before later step updates in an atomic save-all operation.
        for id in Set(dirtyEditors).union(stepDrafts.keys).union(progressDrafts.keys).sorted(by:{$0.uuidString < $1.uuidString}) {
            guard let task=state.task(id) else {continue}
            if dirtyEditors.contains(task.id) {add(.task(task.id),"任务编辑 · \(task.title)",taskBuffers[task.id]?.title ?? "",changed:true)}
            add(.step(task.id),"步骤 · \(task.title)",stepDrafts[task.id] ?? "")
            add(.progress(task.id),"进展 · \(task.title)",progressDrafts[task.id] ?? "")
        }
        add(.newTask,"新增待办",newTaskDraft)
        add(.menuTask,"菜单栏新增待办",menuDraft)
        if let focusDraft {add(.focus,"今日重点",focusDraft,changed:focusDraft != (today?.focus ?? ""))}
        add(.workNote,"工作随记",workNoteDraft)
        add(.journal,"私人日记",journalDraft)
        for review in state.reviews {
            if let text=reviewTextDrafts[review.id] {add(.review(review.id),"回顾文字 · \(review.dayIDs.last ?? "")",text,changed:text != review.text)}
        }
        let changedTimes = (morningDraft != nil && morningDraft != state.reminders.morning) || (eveningDraft != nil && eveningDraft != state.reminders.evening)
        add(.reminderTimes,"提醒时间","\(morningDraft ?? state.reminders.morning) / \(eveningDraft ?? state.reminders.evening)",changed:changedTimes)
        add(.reminderException,"工作日例外",exceptionDateDraft)
        return result
    }
    func hasTaskDraft(_ id: UUID) -> Bool {
        dirtyEditors.contains(id) || !(stepDrafts[id] ?? "").trimmingCharacters(in:.whitespacesAndNewlines).isEmpty || !(progressDrafts[id] ?? "").trimmingCharacters(in:.whitespacesAndNewlines).isEmpty
    }
    func reviewBlockingDrafts(dayIDs: [String]) -> [PendingDraft] {
        let todayIncluded=dayIDs.contains(todayID)
        let liveTasks=Set(state.days.filter {dayIDs.contains($0.id) && !$0.closed}.flatMap(\.plans).map(\.taskID))
        return pendingDrafts.filter {
            switch $0.id {
            case .newTask, .menuTask, .focus, .workNote, .progress: todayIncluded
            case .task(let id), .step(let id): liveTasks.contains(id)
            default: false
            }
        }
    }
    var visibleDrafts: [PendingDraft] {
        if case .review(let days)=draftPurpose {return reviewBlockingDrafts(dayIDs:days)}
        return pendingDrafts
    }
    func presentDrafts(_ purpose: DraftPurpose = .manage) {
        draftPurpose=purpose; error=nil; showWindow?(); showDrafts=true
    }
    func dismissDrafts() {error=nil; showDrafts=false}
    func revealDraft(_ id: DraftID) {
        dismissDrafts()
        switch id {
        case .task(let task), .step(let task), .progress(let task): route="today"; select(task)
        case .review(let review): route="today"; inspector="review"; inspectorVisible=true; selectedReviewID=review
        case .journal: route="journal"
        case .reminderTimes, .reminderException: route="settings"
        default: route="today"
        }
        draftNavigation=DraftNavigation(target:id); showWindow?()
    }
    @discardableResult func saveDrafts(_ ids: Set<DraftID>? = nil) -> Bool {
        let items=pendingDrafts.filter {ids?.contains($0.id) ?? true}
        guard !items.isEmpty else {return true}
        let oldReminders=state.reminders
        let success=commit {next in
            for item in items {try applyDraft(item.id,to:&next)}
        }
        if success {
            for item in items {clearDraft(item.id)}
            error=nil
            if state.reminders != oldReminders {reconcileSavedReminderDrafts()}
        }
        return success
    }
    private func applyDraft(_ id: DraftID, to next: inout Workspace) throws {
        let now=Date()
        switch id {
        case .task(let id):
            guard let buffer=taskBuffers[id] else {throw DomainError.invalid("任务编辑不存在")}
            try next.updateTask(id,expectedRevision:buffer.revision,now:now,message:"编辑任务") {$0.title=buffer.title; $0.notes=buffer.notes}
        case .step(let id):
            let text=(stepDrafts[id] ?? "").trimmingCharacters(in:.whitespacesAndNewlines)
            try next.updateTask(id,now:now,message:"添加步骤") {$0.steps.append(TaskStep(text:text))}
        case .progress(let id): try next.appendEntry(progressDrafts[id] ?? "",kind:.progress,taskID:id,now:now)
        case .newTask: _ = try next.addTask(newTaskDraft,now:now)
        case .menuTask: _ = try next.addTask(menuDraft,now:now)
        case .focus:
            if let index=next.days.firstIndex(where:{$0.id == next.dayID(at:now)}) {next.days[index].focus=focusDraft ?? ""}
        case .workNote: try next.appendEntry(workNoteDraft,kind:.work,now:now)
        case .journal: try next.appendEntry(journalDraft,kind:.personal,now:now)
        case .review(let id):
            guard let index=next.reviews.firstIndex(where:{$0.id == id}), next.reviews[index].acceptedEntryID == nil else {throw DomainError.invalid("已采纳草稿不可修改")}
            next.reviews[index].text=reviewTextDrafts[id] ?? next.reviews[index].text
        case .reminderTimes:
            next.reminders.morning=morningDraft ?? next.reminders.morning
            next.reminders.evening=eveningDraft ?? next.reminders.evening
        case .reminderException: next.reminders.overrides[exceptionDateDraft]=exceptionWorkdayDraft
        }
    }
    private func clearDraft(_ id: DraftID) {
        switch id {
        case .task(let id): dirtyEditors.remove(id); taskBuffers.removeValue(forKey:id)
        case .step(let id): stepDrafts.removeValue(forKey:id)
        case .progress(let id): progressDrafts.removeValue(forKey:id)
        case .review(let id): reviewTextDrafts.removeValue(forKey:id)
        case .newTask: newTaskDraft=""
        case .menuTask: menuDraft=""
        case .focus: focusDraft=nil
        case .workNote: workNoteDraft=""
        case .journal: journalDraft=""
        case .reminderTimes: morningDraft=nil; eveningDraft=nil
        case .reminderException: exceptionDateDraft=""
        }
    }
    func prepareExport(json: Bool, saveDrafts: Bool) -> ExportDocument? {
        guard !isLoading, !isRestoring, !isTerminating else {return nil}
        if saveDrafts && !self.saveDrafts() {return nil}
        return ExportDocument(snapshot:state,json:json,omittedCount:pendingDrafts.count)
    }
    func confirmExport(saveDrafts: Bool) {
        guard case .export(let json)=draftPurpose, let document=prepareExport(json:json,saveDrafts:saveDrafts) else {return}
        queuedExport=document; dismissDrafts()
    }
}
