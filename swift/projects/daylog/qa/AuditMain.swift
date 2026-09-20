import Foundation

/// Isolated diagnostics: no real workspace, credentials, notifications or network.
@main @MainActor struct AuditMain {
    static func measure(_ action: () async throws -> Void) async rethrows -> Double {
        let start = ProcessInfo.processInfo.systemUptime
        try await action()
        return (ProcessInfo.processInfo.systemUptime-start)*1000
    }
    static func main() async throws {
        let store = AppStore(inMemory:true); await store.waitUntilReady()
        _ = store.addTask("Undo fixture")
        let id = store.selectedTaskID!
        store.changeStatus(store.state.task(id)!,to:.done)
        var buffer = TaskBuffer(store.state.task(id)!); buffer.notes="A later note"
        store.taskBuffers[id]=buffer; store.dirtyEditors.insert(id); store.saveBuffer(id)
        store.undo()
        guard store.error == nil, !store.canUndo, store.state.task(id)?.status == .todo,
              store.state.task(id)?.notes == buffer.notes else {throw DomainError.invalid("Undo after edit regressed")}
        print("PASS: undo_after_edit")

        let privateStore = AppStore(inMemory:true); await privateStore.waitUntilReady()
        privateStore.journalDraft="Unsubmitted private diary"
        guard privateStore.reviewBlockingReason(dayIDs:[privateStore.todayID]) == nil,
              privateStore.hasUnsavedChanges else {throw DomainError.invalid("Private draft scope regressed")}
        print("PASS: private_draft_does_not_block_work_review")

        let directory = FileManager.default.temporaryDirectory.appendingPathComponent("DayLog-audit-\(UUID().uuidString)")
        defer {try? FileManager.default.removeItem(at:directory)}
        let local = LocalStore(directory:directory)
        let fixed = Calendar.current.date(byAdding:.day,value:-364,to:Date(timeIntervalSince1970:floor(Date().timeIntervalSince1970)))!
        var state = Workspace(); state.timeZoneID="Asia/Shanghai"
        let note = String(repeating:"技术方案与验证进展。",count:25)
        for day in 0..<365 {
            let now = state.calendar.date(byAdding:.day,value:day,to:fixed)!
            for index in 0..<10 {
                let id = try state.addTask("Day \(day) task \(index)",now:now)
                try state.updateTask(id,now:now,message:"Start") {$0.notes=note; $0.status = .doing; $0.steps=[TaskStep(text:"Test"),TaskStep(text:"Review")]}
                try state.updateTask(id,now:now,message:"Finish") {$0.status = .done; $0.steps[0].done=true}
            }
            try state.appendEntry(note,kind:.work,now:now)
            if [29,179,364].contains(day) {
                let bytes = try state.encoded().count
                let save = try await measure {try await local.save(state)}
                let load = try await measure {_ = try await local.load()}
                let lastID = state.tasks.last!.id
                let edit = try await measure {
                    var copy = state
                    try copy.updateTask(lastID,now:now,message:"Edit") {$0.title += " edited"}
                    try await local.save(copy)
                }
                print(String(format:"BENCH days=%d tasks=%d events=%d payload_MB=%.2f save_ms=%.1f load_ms=%.1f edit_and_save_ms=%.1f",day+1,state.tasks.count,state.events.count,Double(bytes)/1_000_000,save,load,edit))
                let ui = AppStore(inMemory:true,storage:local); await ui.waitUntilReady()
                _ = await ui.saves.flush()
                let clock=ContinuousClock()
                var ticks=0, maxGap=0.0, previous=ProcessInfo.processInfo.systemUptime
                let heartbeat=Task { @MainActor in
                    while !Task.isCancelled {
                        do {try await Task.sleep(for:.milliseconds(1))} catch {break}
                        let now=ProcessInfo.processInfo.systemUptime
                        maxGap=max(maxGap,(now-previous)*1000); previous=now; ticks += 1
                    }
                }
                let start=clock.now
                _ = ui.commit {try $0.updateTask(lastID,now:Date(),message:"UI edit") {$0.title += " UI"}}
                let submit=start.duration(to:clock.now)
                let flushed=await ui.saves.flush()
                heartbeat.cancel(); await heartbeat.value
                guard flushed else {throw DomainError.invalid("benchmark flush failed")}
                print("UI_BENCH days=\(day+1) submit=\(submit) heartbeat_ticks=\(ticks) max_gap_ms=\(String(format:"%.1f",maxGap))")

            }
        }
        var huge = Workspace()
        try huge.appendEntry(String(repeating:"x",count:50_000_001),kind:.personal,now:fixed)
        try await local.save(huge)
        var loadRejected=false
        do {_ = try await local.load()} catch {loadRejected=true}
        print("DIAGNOSTIC over_50MB_workspace: save_succeeded=true, reload_rejected=\(loadRejected)")
        guard !loadRejected else {throw DomainError.invalid("Large local workspace still cannot reload")}
        print("Audit finished; temporary database removed on return")
    }
}
