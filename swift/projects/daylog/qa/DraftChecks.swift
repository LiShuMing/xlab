import Foundation
#if XCODE_TESTING
import DayLogCore
#endif

#if !XCODE_TESTING
@main
#endif
@MainActor struct DraftChecks {
    static var count=0
    static func check(_ condition: Bool, _ label: String) throws {
        guard condition else {throw DomainError.invalid("FAIL: \(label)")}
        count += 1; print("PASS: \(label)")
    }
    static func main() async {
        do {try await run(); print("\(count) draft and reading checks passed")} catch {print(error); exit(1)}
    }
    static func run() async throws {
        let folder=FileManager.default.temporaryDirectory.appendingPathComponent("DayLog-draft-check-\(UUID().uuidString)")
        defer {try? FileManager.default.removeItem(at:folder)}
        let app=AppStore(inMemory:true,storage:LocalStore(directory:folder)); await app.waitUntilReady()
        app.morningDraft="10:15"; app.eveningDraft="19:00"; app.route="today"; app.route="settings"
        try check(app.morningDraft == "10:15" && app.state.reminders.morning == "09:30" && app.hasUnsavedChanges,"reminder drafts survive navigation without changing the saved schedule")
        try check(app.pendingDrafts.map(\.id) == [.reminderTimes],"both reminder fields form one discoverable pending item")
        app.revealDraft(.reminderTimes)
        try check(app.route == "settings" && app.draftNavigation?.target == .reminderTimes,"reminder draft navigation requests the correct field")
        try check(app.saveDrafts([.reminderTimes]) && app.state.reminders.morning == "10:15" && !app.hasUnsavedChanges,"explicit reminder save commits and clears its buffers")
        app.morningDraft=app.state.reminders.morning; app.focusDraft=app.today?.focus; app.newTaskDraft="  \n "
        try check(!app.hasUnsavedChanges,"unchanged values and whitespace do not create phantom exit blockers")
        app.morningDraft=nil; app.focusDraft=nil; app.newTaskDraft=""

        _ = app.addTask("Task A"); let id=app.selectedTaskID!
        app.progressDrafts[id]="Keep progress"; app.journalDraft="Keep private draft"; app.morningDraft="11:00"
        app.generateReview()
        try check(app.showDrafts && app.visibleDrafts.count == 1 && app.visibleDrafts[0].title.contains("Task A"),"blocked generation identifies the exact task and excludes private/settings inputs")
        try check(app.hasTaskDraft(id),"task row exposes its pending progress marker")
        app.error="已在草稿列表展示的校验错误"
        app.revealDraft(.progress(id))
        let firstRequest=app.draftNavigation?.id
        try check(app.selectedTaskID == id && app.inspector == "task" && app.route == "today" && !app.showDrafts && app.error == nil,"go-to restores the inspector without repeating the inline error")
        app.revealDraft(.progress(id))
        try check(app.draftNavigation?.id != firstRequest,"repeated go-to requests can refocus the same field")
        try check(app.saveDrafts([.progress(id)]) && app.journalDraft == "Keep private draft" && app.morningDraft == "11:00","saving a work blocker does not submit unrelated private/settings drafts")
        try check(!app.hasTaskDraft(id) && app.reviewBlockingDrafts(dayIDs:[app.todayID]).isEmpty,"submitted progress clears the marker and review blocker")

        app.workNoteDraft="UNSUBMITTED_WORK"; app.journalDraft="UNSUBMITTED_PRIVATE"
        let snapshot=app.state
        app.export(json:true)
        try check(app.showDrafts && app.draftPurpose == .export(json:true) && app.queuedExport == nil,"export requests an explicit scope choice before opening the save panel")
        app.showDrafts=false
        let committed=app.prepareExport(json:true,saveDrafts:false)!
        let committedText=String(decoding:try committed.data(),as:UTF8.self)
        try check(committed.omittedCount == 3 && !committedText.contains("UNSUBMITTED_WORK") && !committedText.contains("UNSUBMITTED_PRIVATE"),"committed-only export explicitly records omitted input count")
        try check(app.state == snapshot && app.workNoteDraft == "UNSUBMITTED_WORK" && app.journalDraft == "UNSUBMITTED_PRIVATE","committed-only export never clears or submits drafts")
        app.workNoteDraft="LATER_WORK"
        try check(committed.snapshot == snapshot,"export uses an immutable snapshot despite later editing")

        app.newTaskDraft="New task"; app.menuDraft="Menu task"; app.focusDraft="Today's focus"
        app.stepDrafts[id]="A new step"; app.progressDrafts[id]="Later progress"
        var buffer=TaskBuffer(app.state.task(id)!); buffer.title="Edited Task A"; buffer.notes="Notes"
        app.taskBuffers[id]=buffer; app.dirtyEditors.insert(id)
        app.exceptionDateDraft=app.todayID; app.exceptionWorkdayDraft=false
        let review=ReviewDraft(dayIDs:[app.todayID],source:try app.state.reviewSource(dayIDs:[app.todayID]),text:"old output",createdAt:Date())
        _ = app.commit {$0.reviews.append(review)}
        app.reviewTextDrafts[review.id]="**Edited output**"
        let all=app.prepareExport(json:true,saveDrafts:true)!
        let allText=String(decoding:try all.data(),as:UTF8.self)
        try check(all.omittedCount == 0 && !app.hasUnsavedChanges && allText.contains("UNSUBMITTED_PRIVATE") && allText.contains("LATER_WORK"),"save-then-export includes all drafts only after explicit selection")
        try check(app.state.task(id)?.title == "Edited Task A" && app.state.task(id)?.steps.last?.text == "A new step" && app.state.tasks.count == 3,"save-all handles task text, steps and both new-task entrances without revision conflicts")
        try check(app.state.reminders.morning == "11:00" && app.state.reminders.overrides[app.todayID] == false && app.today?.focus == "Today's focus","save-all includes reminders, date exceptions and focus")
        try check(app.state.reviews.last?.text == "**Edited output**" && app.state.reviews.last?.acceptedEntryID == nil,"save-all saves output editing without adopting a review")
        let entries=app.state.entries.count
        try check(app.saveDrafts() && app.state.entries.count == entries && app.state.tasks.count == 3,"repeated save-all does not duplicate entries, tasks or steps")
        try check(await app.saves.flush(),"all accepted drafts flush successfully")
        let restored=try await LocalStore(directory:folder).load()
        try check(restored == Workspace.decode(app.state.encoded()),"reminder times and submitted drafts survive a real SQLite reopen")
        let markdown=app.prepareExport(json:false,saveDrafts:false)!
        try check(!String(decoding:try markdown.data(),as:UTF8.self).contains("UNSUBMITTED_PRIVATE"),"Markdown export still excludes saved personal entries")

        let before=app.state
        app.workNoteDraft="MUST_NOT_PARTIALLY_SAVE"; app.morningDraft="99:99"
        try check(app.prepareExport(json:true,saveDrafts:true) == nil && app.state == before,"invalid settings abort the whole save-all/export operation atomically")
        try check(app.workNoteDraft == "MUST_NOT_PARTIALLY_SAVE" && app.morningDraft == "99:99" && app.hasUnsavedChanges,"failed save retains every draft for correction")
        app.morningDraft=nil
        buffer=TaskBuffer(app.state.task(id)!); buffer.title="Conflict draft"
        app.taskBuffers[id]=buffer; app.dirtyEditors.insert(id)
        _ = app.commit {try $0.updateTask(id,now:Date(),message:"another editor") {$0.notes="Newer notes"}}
        let newer=app.state
        try check(!app.saveDrafts() && app.state == newer && app.workNoteDraft == "MUST_NOT_PARTIALLY_SAVE","a stale task revision cannot partially save other inputs")
        app.taskBuffers.removeValue(forKey:id); app.dirtyEditors.remove(id)
        try check(app.saveDrafts() && app.error == nil,"correcting invalid drafts allows retry without duplicates")
        guard await app.saves.flush() else {throw DomainError.invalid("Final fixture flush failed")}

        let blocks=ReviewMarkdown.blocks("# Review\n\n**Done**\n- Item A\n2. Item B\n\n```swift\nprint(\"hi\")\n```")
        try check(blocks.map(\.kind) == [.heading(1),.paragraph,.item("•"),.item("2."),.code],"Markdown reading distinguishes headings, paragraphs, lists and code")
        let bold=ReviewMarkdown.inline("**Done** and *next*")
        try check(String(bold.characters) == "Done and next" && bold.runs.contains {$0.inlinePresentationIntent?.contains(.stronglyEmphasized) == true},"reading removes bold markers while preserving emphasis")
        let unsafe=ReviewMarkdown.inline("[local](file:///tmp/example) [custom](daylog://open) [web](https://example.com)")
        try check(unsafe.runs.allSatisfy {$0.link == nil},"model links cannot launch file or custom URLs from the reader")
        try check(ReviewMarkdown.blocks("```\n**literal**").first?.text == "**literal**","unfinished code fences preserve literal content")
    }
}
