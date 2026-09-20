import Foundation
import DayLogCore

#if !XCODE_TESTING
@main
#endif
struct Checks {
    static func main() async {
        do {
            if CommandLine.arguments.contains("--llm-check") {
                let config = try DotEnv.loadDefault()
                _ = try await LLMClient.generate(config:config,system:"Return only OK.",prompt:"Reply OK.",test:true)
                print("PASS: configured Chat Completions service returned a valid response (no journal data sent)")
                return
            }
            try runChecks()
        } catch {
            if let error = error as? LLMError { print("FAIL: \(error.localizedDescription)") }
            else { print("FAIL: \(error)") }
            exit(1)
        }
    }
    static func check(_ value: @autoclosure () throws -> Bool, _ name: String) throws {
        guard try value() else { throw DomainError.invalid("check failed: \(name)") }
        print("PASS: \(name)")
    }
    static func rejects(_ name: String, _ operation: () throws -> Void) throws {
        do { try operation() } catch { print("PASS: \(name)"); return }
        throw DomainError.invalid("check failed: \(name)")
    }
    static func runChecks() throws {
        let date = ISO8601DateFormatter()
        let d1 = date.date(from:"2026-09-18T15:59:00Z")!, d2 = date.date(from:"2026-09-18T16:01:00Z")!
        var state = Workspace(); state.timeZoneID = "Asia/Shanghai"
        let id = try state.addTask("Ship DayLog",now:d1)
        try state.updateTask(id,now:d1,message:"Begin") { $0.status = .doing; $0.steps = [TaskStep(text:"Build")] }
        try state.updateTask(id,now:d2,message:"Finish") { $0.status = .done; $0.steps[0].done = true }
        try check(state.days[0].closed && state.days[0].plans[0].snapshot?.status == .doing,"midnight snapshots precede task mutation")
        try check(state.task(id)?.lastOpenStatus == .doing,"completion remembers previous status")
        try state.carry(id,to:state.dayID(at:d2)); try state.carry(id,to:state.dayID(at:d2))
        try check(state.days[1].plans.count == 1,"carry is idempotent")
        try rejects("stale revision rejects overwrite") { try state.updateTask(id,expectedRevision:0,now:d2,message:"stale") {$0.title="Wrong"} }
        try rejects("closed date rejects backwards clock") { _ = try state.prepareDay(at:d1) }
        try state.appendEntry("Private secret diary",kind:.personal,now:d2)
        let ids = [state.dayID(at:d2)], source = try state.reviewSource(dayIDs:ids)
        try check(!String(decoding:source,as:UTF8.self).contains("Private secret diary"),"personal diary excluded from AI context")
        let draft = ReviewDraft(dayIDs:ids,source:source,text:"Done",createdAt:d2); state.reviews.append(draft)
        let accepted = try state.acceptReview(draft.id,now:d2)
        try check(try state.acceptReview(draft.id,now:d2) == accepted,"AI adoption is idempotent")
        let stale = ReviewDraft(dayIDs:ids,source:source,text:"Old",createdAt:d2); state.reviews.append(stale)
        try state.appendEntry("Changed progress",kind:.work,now:d2)
        try rejects("changed source blocks stale AI adoption") { _ = try state.acceptReview(stale.id,now:d2) }
        try check(try Workspace.decode(state.encoded()) == state,"JSON restores complete workspace graph")
        var broken = state; broken.tasks = []
        try rejects("broken backup references rejected") { try broken.validate() }
        try check(!state.markdown(dayIDs:ids).contains("Private secret diary"),"work Markdown excludes personal diary")
        let env = try DotEnv.parse("export LLM_MODEL='a=b' # note\nLLM_API_KEY=placeholder # comment\nUNRELATED=ignored\n")
        try check(env["LLM_MODEL"] == "a=b" && env["LLM_API_KEY"] == "placeholder" && env.count == 2,"dotenv quote and allowlist parsing")
        try rejects("duplicate config rejected") { _ = try DotEnv.parse("LLM_MODEL=a\nLLM_MODEL=b") }
        try rejects("shell expansion rejected") { _ = try DotEnv.parse("LLM_MODEL=${OTHER}") }
        try rejects("partial environment never merges file secrets") { _ = try DotEnv.loadDefault(environment:["LLM_MODEL":"test"],home:URL(fileURLWithPath:"/nonexistent")) }
        let config = try LLMConfig(values:["LLM_BASE_URL":"https://example.com/v1/","LLM_API_KEY":"placeholder","LLM_MODEL":"test","LLM_TIMEOUT":"10"])
        try check(config.endpoint.absoluteString == "https://example.com/v1/chat/completions","API root appends endpoint once")
        state.reminders.enabled = true
        state.reminders.overrides["2026-09-19"] = true
        let schedule = try ReminderSchedule.requests(workspace:state,now:d2)
        try check(schedule.filter {$0.dayID == "2026-09-19"}.count == 2,"weekend workday override schedules both reminders")
        state.reminders.overrides["2026-09-21"] = false
        try check(try ReminderSchedule.requests(workspace:state,now:d2).allSatisfy {$0.dayID != "2026-09-21"},"holiday override removes weekday reminders")
        var dst = Workspace(); dst.timeZoneID = "America/Los_Angeles"
        _ = try dst.prepareDay(at:date.date(from:"2026-03-08T12:00:00Z")!)
        try check(dst.days[0].end.timeIntervalSince(dst.days[0].start) == 23*3600,"DST day uses calendar boundary")
        print("All core checks passed")
    }
}
