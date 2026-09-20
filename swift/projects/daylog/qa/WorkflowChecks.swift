import Foundation
#if XCODE_TESTING
import DayLogCore
#endif

actor ReviewProbe {
    private(set) var prompts: [String] = []
    func generate(_ prompt: String) -> String {prompts.append(prompt); return "已完成：测试任务。下一步建议：继续验证。"}
}

/// Runs production domain + AppStore code with isolated storage and a captured
/// model boundary. No user diary, credentials or network are accessed.
#if !XCODE_TESTING
@main
#endif
@MainActor struct WorkflowChecks {
    static var count = 0
    static func check(_ condition: Bool, _ label: String) throws {
        guard condition else {throw DomainError.invalid("FAIL: \(label)")}
        count += 1; print("PASS: \(label)")
    }
    static func main() async {
        do {try await undoChecks(); try await reviewChecks(); print("\(count) workflow regression checks passed")}
        catch {print(error); exit(1)}
    }
    static func undoChecks() async throws {
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent("DayLog-workflow-\(UUID().uuidString)")
        defer {try? FileManager.default.removeItem(at:directory)}
        let backend = LocalStore(directory:directory)
        let app = AppStore(inMemory:true,storage:backend); await app.waitUntilReady()
        _ = app.addTask("Original title"); let id = app.selectedTaskID!
        app.changeStatus(app.state.task(id)!,to:.doing)
        app.changeStatus(app.state.task(id)!,to:.done)
        var buffer = TaskBuffer(app.state.task(id)!); buffer.title="Edited after completion"; buffer.notes="Keep these notes"
        app.taskBuffers[id]=buffer; app.dirtyEditors.insert(id); app.saveBuffer(id)
        _ = app.commit {try $0.updateTask(id,now:Date(),message:"add step") {$0.steps.append(TaskStep(text:"Keep this step"))}}
        _ = app.addTask("Unrelated task")
        try check(app.canUndo,"text, steps and unrelated tasks do not invalidate status undo")
        let revision = app.state.task(id)!.revision
        app.undo()
        let task = app.state.task(id)!
        try check(task.status == .doing && task.title == buffer.title && task.notes == buffer.notes && task.steps.count == 1,"undo preserves all later content and restores the previous status")
        try check(task.revision == revision+1 && app.state.events.last?.before?.title == buffer.title && app.state.events.last?.after == task,"undo increments revision and records current before/after snapshots")
        try check(!app.canUndo && app.error == nil,"successful undo removes the button without a conflict error")
        try check(await app.saves.flush(),"undo and retained content flush to SQLite")
        let reopened = try await LocalStore(directory:directory).load()
        // The v1 JSON format stores timestamps to whole-second precision.
        let expected = try Workspace.decode(app.state.encoded()).task(id)
        try check(reopened.task(id) == expected,"reopening SQLite preserves the undone status and later text")

        app.changeStatus(app.state.task(id)!,to:.done)
        buffer=TaskBuffer(app.state.task(id)!); buffer.title="Still typing when undo is clicked"
        app.taskBuffers[id]=buffer; app.dirtyEditors.insert(id)
        app.undo()
        try check(app.state.task(id)?.status == .doing && app.state.task(id)?.title == buffer.title && !app.dirtyEditors.contains(id),"undo first submits an unsaved text buffer")

        app.changeStatus(app.state.task(id)!,to:.done)
        buffer=TaskBuffer(app.state.task(id)!); buffer.title=" "
        app.taskBuffers[id]=buffer; app.dirtyEditors.insert(id); app.undo()
        try check(app.state.task(id)?.status == .done && app.dirtyEditors.contains(id) && app.canUndo,"invalid text blocks undo while retaining the draft and undo action")
        app.taskBuffers.removeValue(forKey:id); app.dirtyEditors.remove(id); app.error=nil
        let events = app.state.events.count
        app.changeStatus(app.state.task(id)!,to:.done); app.undo()
        try check(app.state.events.count == events+1 && app.state.task(id)?.status == .doing,"selecting the same status does not replace the real undo action")

        app.changeStatus(app.state.task(id)!,to:.done)
        app.changeStatus(app.state.task(id)!,to:.todo)
        app.undo()
        try check(app.state.task(id)?.status == .done && app.state.task(id)?.lastOpenStatus == .doing,"undo of reopening restores the original last-open status")

        app.changeStatus(app.state.task(id)!,to:.doing)
        _ = app.commit {try $0.updateTask(id,now:Date(),message:"another status entry") {$0.status = .todo}}
        try check(!app.canUndo,"a later status change through another entry invalidates the button")
        let before = app.state; app.undo()
        try check(app.state == before,"an invalidated undo cannot mutate the task")

        var state = Workspace(); let now = Date(); let domainID = try state.addTask("ABA",now:now)
        try state.updateTask(domainID,now:now,message:"complete") {$0.status = .done}
        let oldEvent = state.events.last!.id
        try state.updateTask(domainID,now:now,message:"reopen") {$0.status = .doing}
        try state.updateTask(domainID,now:now,message:"complete again") {$0.status = .done}
        var rejected = false
        do {try state.undoStatusChange(oldEvent,now:now)} catch {rejected=true}
        try check(rejected && !state.canUndoStatusChange(oldEvent) && state.task(domainID)?.status == .done,"ABA status changes reject an old undo event")
        let latestEvent = state.events.last!.id
        let tomorrow = state.calendar.date(byAdding:.day,value:1,to:now)!
        try state.undoStatusChange(latestEvent,now:tomorrow)
        try check(state.days.first?.plans.first?.snapshot?.status == .done && state.task(domainID)?.status == .doing,"cross-day undo preserves the previous day's frozen snapshot")
        guard await app.saves.flush() else {throw DomainError.invalid("Final fixture flush failed")}
    }
    static func reviewChecks() async throws {
        let probe = ReviewProbe()
        let app = AppStore(inMemory:true,reviewGenerator:{_,_,prompt in await probe.generate(prompt)})
        await app.waitUntilReady()
        app.config = try LLMConfig(values:["LLM_BASE_URL":"https://example.invalid/v1","LLM_API_KEY":"test-placeholder","LLM_MODEL":"fixture","LLM_TIMEOUT":"5"])
        _ = app.addTask("Work included in prompt"); let id=app.selectedTaskID!
        _ = app.append("SAVED_PRIVATE_SENTINEL",kind:.personal)
        app.journalDraft="UNSAVED_PRIVATE_SENTINEL"
        app.reviewTextDrafts[UUID()]="OUTPUT_DRAFT_SENTINEL"
        app.generateReview(); await app.activeRequest?.value
        try check(app.error == nil && app.selectedReview != nil && !app.reviewStale,"private and output drafts allow work review generation and adoption")
        let prompts = await probe.prompts
        try check(prompts.count == 1 && prompts[0].contains("Work included in prompt") && !prompts[0].contains("PRIVATE_SENTINEL") && !prompts[0].contains("OUTPUT_DRAFT_SENTINEL"),"captured provider input excludes saved/unsaved private content and output drafts")
        try check(app.journalDraft == "UNSAVED_PRIVATE_SENTINEL" && app.hasUnsavedChanges,"generation preserves the private draft and normal quit/restore protection")
        let reviewID = app.selectedReview!.id
        app.reviewTextDrafts[reviewID]="Edited output"; app.saveReviewText(reviewID)
        try check(!app.reviewStale && app.commit {_ = try $0.acceptReview(reviewID,now:Date())},"editing and adopting output succeeds with a private draft present")

        let blockers: [(String, (AppStore) -> Void, (AppStore) -> Void)] = [
            ("new task",{$0.newTaskDraft="pending"},{$0.newTaskDraft=""}),
            ("menu task",{$0.menuDraft="pending"},{$0.menuDraft=""}),
            ("work note",{$0.workNoteDraft="pending"},{$0.workNoteDraft=""}),
            ("focus",{$0.focusDraft="pending"},{$0.focusDraft=nil}),
            ("progress",{$0.progressDrafts[id]="pending"},{$0.progressDrafts.removeValue(forKey:id)}),
            ("task edit",{$0.dirtyEditors.insert(id)},{$0.dirtyEditors.remove(id)}),
            ("task step",{$0.stepDrafts[id]="pending"},{$0.stepDrafts.removeValue(forKey:id)})
        ]
        for (label, set, clear) in blockers {
            app.error=nil; app.showDrafts=false; set(app)
            let stale=app.reviewStale
            app.generateReview(); await app.activeRequest?.value
            let calls = await probe.prompts.count
            try check(stale && app.showDrafts && !app.visibleDrafts.isEmpty && calls == 1,"unsaved \(label) still blocks relevant generation/adoption without calling the provider")
            clear(app)
        }
        app.error=nil
        app.newTaskDraft=" \n "; app.workNoteDraft="  "; app.focusDraft=app.today?.focus
        try check(app.reviewBlockingReason(dayIDs:[app.todayID]) == nil,"whitespace and an unchanged focus do not create a false source conflict")
        app.newTaskDraft=""; app.workNoteDraft=""; app.focusDraft=nil

        let yesterday=app.state.calendar.date(byAdding:.day,value:-1,to:Date())!
        var history=Workspace(); let historicalID=try history.addTask("Historical task",now:yesterday)
        let dayID=history.dayID(at:yesterday); _ = try history.prepareDay(at:Date())
        let draft=ReviewDraft(dayIDs:[dayID],source:try history.reviewSource(dayIDs:[dayID]),text:"Historical output",createdAt:Date())
        history.reviews.append(draft)
        _ = app.commit {$0=history}; app.selectedReviewID=draft.id
        app.workNoteDraft="Today's pending note"; app.dirtyEditors.insert(historicalID); app.stepDrafts[historicalID]="Later step"
        try check(!app.reviewStale,"today's inputs and later task edits do not invalidate a closed-day review")
        app.workNoteDraft=""; app.dirtyEditors.removeAll(); app.stepDrafts.removeAll()
        _ = app.addTask("Current task"); app.generateReview(); await app.activeRequest?.value
        try check(app.selectedReview != nil && !app.reviewStale,"review starts fresh after relevant drafts are cleared")
        _ = app.append("New work after generation")
        try check(app.reviewStale,"saved work-source changes still invalidate the generated review")
        var accepted=false
        _ = app.commit {_ = try $0.acceptReview(app.selectedReview!.id,now:Date()); accepted=true}
        try check(!accepted,"domain guard rejects adoption of a stale source")
    }
}
