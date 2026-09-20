import Foundation
import DayLogCore

enum StorageChecks {
    static func run(_ arguments: [String]) async -> Int32? {
        guard arguments.count == 3, ["--storage-write","--storage-read","--storage-write-large","--storage-read-large"].contains(arguments[1]) else {return nil}
        do {
            let directory = URL(fileURLWithPath:arguments[2],isDirectory:true)
            let local = LocalStore(directory:directory)
            let fixture = directory.appendingPathComponent("expected.json")
            if arguments[1].hasPrefix("--storage-write") {
                var state = Workspace(); let now = Date(timeIntervalSince1970:1_800_000_000)
                let id = try state.addTask("持久化验证",now:now)
                try state.updateTask(id,now:now,message:"edit") {$0.notes="SQLite restart fixture"; $0.steps=[TaskStep(text:"verify")]}
                try state.appendEntry(arguments[1].hasSuffix("-large") ? String(repeating:"x",count:50_000_001) : "本地日记",kind:.personal,now:now)
                try await local.save(state); try state.encoded().write(to:fixture,options:.atomic)
                var broken = state; broken.tasks=[]
                var rejected = false
                do {try await local.save(broken)} catch {rejected=true}
                guard rejected, try await local.load() == state else {throw DomainError.invalid("invalid write changed store")}
                print("PASS: SQLite transaction saved; invalid graph leaves saved state intact")
            } else {
                let expected = try Workspace.decode(Data(contentsOf:fixture))
                guard try await local.load() == expected else {throw DomainError.invalid("restart mismatch")}
                print("PASS: separate process restored complete SQLite workspace")
            }
            return 0
        } catch {print("FAIL: SQLite persistence check"); return 1}
    }
}
