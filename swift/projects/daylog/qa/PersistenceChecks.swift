import Foundation
#if XCODE_TESTING
import DayLogCore
#endif

actor ControlledStorage: WorkspaceStorage {
    private var value: Workspace
    private var gate: CheckedContinuation<Void,Never>?
    private var hold = false
    private var fail = false
    private var failuresRemaining = 0
    private var active = 0
    private(set) var maxActive = 0
    private(set) var writtenTitles: [String] = []
    private(set) var attempts = 0
    init(_ value: Workspace) {self.value=value}
    func load() -> Workspace {value}
    func configure(hold: Bool = false, fail: Bool = false, failures: Int = 0) {self.hold=hold; self.fail=fail; failuresRemaining=failures}
    func release(fail: Bool = false) {hold=false; self.fail=fail; gate?.resume(); gate=nil}
    func save(_ value: Workspace) async throws {
        active += 1; maxActive=max(active,maxActive); attempts += 1
        defer {active -= 1}
        if hold {await withCheckedContinuation {gate=$0}}
        if fail || failuresRemaining > 0 {failuresRemaining=max(0,failuresRemaining-1); throw DomainError.invalid("Injected disk error")}
        self.value=value; writtenTitles.append(value.tasks.first?.title ?? "empty")
    }
    func isHeld() -> Bool {gate != nil}
}

#if !XCODE_TESTING
@main
#endif
@MainActor struct PersistenceChecks {
    static func check(_ condition: Bool, _ label: String) throws {
        guard condition else {throw DomainError.invalid("FAIL: \(label)")}
        print("PASS: \(label)")
    }
    static func until(_ condition: () async -> Bool) async throws {
        let deadline=ContinuousClock.now.advanced(by:.seconds(5))
        while !(await condition()) {
            guard ContinuousClock.now < deadline else {throw DomainError.invalid("Timed out waiting for test condition")}
            try await Task.sleep(for:.milliseconds(1))
        }
    }
    static func main() async {
        do {try await run()} catch {print(error); exit(1)}
    }
    static func run() async throws {
        var initial=Workspace(); let now=Date(timeIntervalSince1970:floor(Date().timeIntervalSince1970))
        let id = try initial.addTask("initial",now:now)
        let backend=ControlledStorage(initial)
        let queue=SaveQueue(storage:backend,debounce:.seconds(60))
        for index in 0..<100 {
            var next=initial; next.tasks[0].title="edit-\(index)"; queue.enqueue(next)
        }
        try check(queue.hasPendingWrites && queue.savedRevision == 0,"accepted edits are not reported as persisted")
        try check(await queue.flush(),"flush bypasses debounce")
        let coalesced=await backend.writtenTitles
        try check(coalesced == ["edit-99"],"100 rapid edits coalesce to the newest complete snapshot")

        await backend.configure(hold:true)
        var older=initial; older.tasks[0].title="older"
        queue.enqueue(older); queue.retry()
        try await until {await backend.isHeld()}
        var latest=initial; latest.tasks[0].title="latest"
        queue.enqueue(latest)
        try check(queue.hasPendingWrites,"newer edit remains dirty while an older write is blocked")
        await backend.release()
        try check(await queue.flush(),"flush includes edits arriving during a write")
        let saved=await backend.load(), concurrency=await backend.maxActive
        try check(saved.tasks[0].title == "latest" && concurrency == 1,"no overlapping writes or stale snapshot overwrite")

        await backend.configure(hold:true,failures:1)
        queue.enqueue(older); queue.retry()
        try await until {await backend.isHeld()}
        queue.enqueue(latest); await backend.release()
        try check(await queue.flush(),"an old write failure does not discard a newer pending snapshot")
        try check((await backend.load()).tasks[0].title == "latest" && queue.failure == nil,"newer successful write supersedes the failed old revision")

        await backend.configure(fail:true)
        var retry=initial; retry.tasks[0].title="recoverable"
        queue.enqueue(retry)
        try check(!(await queue.flush()) && queue.hasPendingWrites && queue.failure != nil,"failed save stays dirty and flush rejects termination")
        try check((await backend.load()).tasks[0].title == "latest","failed save keeps the previous durable snapshot")
        await backend.configure()
        try check(await queue.flush(),"retry persists the retained failed snapshot")
        try check((await backend.load()).tasks[0].title == "recoverable" && queue.failure == nil,"retry clears failure only after durable success")

        let appBackend=ControlledStorage(initial)
        let app=AppStore(inMemory:true,storage:appBackend); await app.waitUntilReady()
        await appBackend.configure(hold:true,fail:true)
        _ = app.commit {try $0.updateTask(id,now:now,message:"edit") {$0.title="pending-at-quit"}}
        let finishing=Task {await app.flushForTermination()}
        try await until {await appBackend.isHeld()}
        try check(app.isTerminating && app.saves.hasPendingWrites,"normal quit waits while disk write is in flight")
        try check(!app.addTask("must not enter during quit"),"new mutations cannot race termination flush")
        await appBackend.release(fail:true)
        try check(!(await finishing.value) && !app.isTerminating,"failed termination flush re-enables the app")
        try check(app.state.task(id)?.title == "pending-at-quit" && app.saves.failure != nil,"failed background save preserves visible edits for retry or export")
        await appBackend.configure()
        try check(await app.flushForTermination(),"retrying quit persists every accepted edit")
        try check((await appBackend.load()).task(id)?.title == "pending-at-quit","quit flush leaves the latest title durable")

        let folder=FileManager.default.temporaryDirectory.appendingPathComponent("DayLog-import-check-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at:folder,withIntermediateDirectories:true)
        defer {try? FileManager.default.removeItem(at:folder)}
        let file=folder.appendingPathComponent("oversized.json")
        FileManager.default.createFile(atPath:file.path,contents:nil)
        let handle=try FileHandle(forWritingTo:file); try handle.truncate(atOffset:UInt64(Workspace.backupImportLimit+1)); try handle.close()
        var rejected=false
        do {_ = try Workspace.readBackup(from:file)} catch {rejected=true}
        try check(rejected,"external oversized backup is rejected before unbounded file loading")
        try initial.encoded().write(to:file)
        try check(try Workspace.readBackup(from:file) == initial,"normal v1 pretty JSON backup stays compatible")
        print("Persistence regression checks passed")
    }
}
