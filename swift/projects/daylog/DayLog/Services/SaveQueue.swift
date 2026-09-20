import Foundation
import Observation
import DayLogCore

/// MainActor owns only queue metadata and immutable value snapshots. The
/// storage actor performs all validation/encoding/I/O. At most one write is
/// active and one newer snapshot is pending, so rapid edits coalesce safely.
@MainActor @Observable final class SaveQueue {
    private let storage: any WorkspaceStorage
    private let debounce: Duration
    private var pending: (revision: Int, state: Workspace)?
    private var scheduled: Task<Void,Never>?
    private var worker: Task<Void,Never>?
    private(set) var revision = 0
    private(set) var savedRevision = 0
    private(set) var failure: String?
    var hasPendingWrites: Bool { savedRevision < revision }
    var isWriting: Bool {worker != nil}

    init(storage: any WorkspaceStorage, debounce: Duration = .milliseconds(200)) {
        self.storage=storage; self.debounce=debounce
    }
    func enqueue(_ state: Workspace) {
        revision += 1; pending=(revision,state); failure=nil
        guard worker == nil else {return}
        scheduled?.cancel()
        scheduled = Task { [weak self, debounce] in
            do {try await Task.sleep(for:debounce)} catch {return}
            guard let self else {return}
            self.scheduled=nil; self.startWorker()
        }
    }
    private func startWorker() {
        guard worker == nil, pending != nil else {return}
        worker = Task {
            while let snapshot = pending {
                pending=nil
                do {
                    try await storage.save(snapshot.state)
                    savedRevision=snapshot.revision
                    if savedRevision == revision {failure=nil}
                } catch {
                    // Never drop newer edits or roll the UI back to an old save.
                    // If a newer snapshot exists, try that complete state next.
                    if pending == nil {
                        pending=snapshot
                        failure="保存失败，修改仍保留在内存。请重试或导出备份。"
                        break
                    }
                }
            }
            worker=nil
        }
    }
    func retry() {
        scheduled?.cancel(); scheduled=nil; failure=nil; startWorker()
    }
    /// Used by normal termination and restore. It bypasses debounce and awaits
    /// every accepted edit; a failed write returns false and retains its state.
    func flush() async -> Bool {
        scheduled?.cancel(); scheduled=nil
        startWorker()
        if let worker {await worker.value}
        return !hasPendingWrites
    }
}
