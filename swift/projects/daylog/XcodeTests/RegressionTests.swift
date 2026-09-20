import XCTest
import DayLogCore

/// Reuse the executable checks so Xcode and the CLT workflow exercise the same
/// production code and assertions. These tests use memory or temporary SQLite.
@MainActor final class RegressionTests: XCTestCase {
    func testDomainConfigurationAndScheduling() throws {
        try Checks.runChecks()
    }

    func testSaveQueueFailureRecoveryAndTermination() async throws {
        try await PersistenceChecks.run()
    }

    func testUndoPreservesLaterEditsAndSQLite() async throws {
        try await WorkflowChecks.undoChecks()
    }

    func testReviewSourceAndPrivateDiaryIsolation() async throws {
        try await WorkflowChecks.reviewChecks()
    }

    func testDraftTransactionsExportAndMarkdown() async throws {
        try await DraftChecks.run()
    }

    func testDevelopmentFixturesStayInMemory() async throws {
        let demo = AppStore(inMemory:true, demoData:true)
        await demo.waitUntilReady()
        XCTAssertNil(demo.fatalError)
        XCTAssertEqual(demo.state.tasks.count, 4)
        XCTAssertNil(demo.config)
        let flushed = await demo.saves.flush()
        XCTAssertTrue(flushed)
        XCTAssertTrue(demo.persistenceLabel.contains("演示模式"))
        let fresh = AppStore(inMemory:true, demoData:false)
        await fresh.waitUntilReady()
        XCTAssertTrue(fresh.state.tasks.isEmpty)
    }
}
