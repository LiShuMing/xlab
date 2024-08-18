// 03_task_chain.cpp - Task Chaining Demo
// Phase 1: Demonstrates co_await chaining between tasks
//
// This demo shows:
//   - Multiple tasks awaiting each other
//   - Value propagation through the chain
//   - Error handling (if any task throws)

#include <iostream>
#include "miniseastar/runtime.hpp"

using namespace miniseastar;

// ---------------------------------------------------------------------------
// Task that produces a value
// ---------------------------------------------------------------------------
Task<int> produce_value(int value) {
    std::cout << "[produce] Generating value: " << value << "\n";
    co_return value;
}

// ---------------------------------------------------------------------------
// Task that transforms a value
// ---------------------------------------------------------------------------
Task<int> transform_value(int input) {
    std::cout << "[transform] Received: " << input << "\n";

    int result = input * 2 + 1;

    std::cout << "[transform] Returning: " << result << "\n";
    co_return result;
}

// ---------------------------------------------------------------------------
// Task that consumes a value
// ---------------------------------------------------------------------------
Task<void> consume_value(int value) {
    std::cout << "[consume] Final value: " << value << "\n";
    co_return;
}

// ---------------------------------------------------------------------------
// Pipeline task that chains everything together
// ---------------------------------------------------------------------------
Task<void> pipeline() {
    std::cout << "[pipeline] Starting...\n";

    // Chain: produce -> transform -> consume
    int value = co_await produce_value(10);
    value = co_await transform_value(value);
    co_await consume_value(value);

    std::cout << "[pipeline] Complete\n";
    co_return;
}

// ---------------------------------------------------------------------------
// Parallel pipeline demo - use std::move to transfer ownership
// ---------------------------------------------------------------------------
Task<void> parallel_demo() {
    std::cout << "\n[parallel] Starting parallel tasks...\n";

    // Run multiple pipelines in parallel using std::move
    auto t1 = produce_value(1);
    auto t2 = produce_value(2);
    auto t3 = produce_value(3);

    int r1 = co_await std::move(t1);
    int r2 = co_await std::move(t2);
    int r3 = co_await std::move(t3);

    std::cout << "[parallel] Results: " << r1 << ", " << r2 << ", " << r3 << "\n";
    co_return;
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------
int main() {
    std::cout << "=== MiniSeastar Task Chain Demo ===\n\n";

    Runtime runtime;

    runtime.spawn(pipeline());
    runtime.spawn(parallel_demo());

    std::cout << "[main] Running event loop...\n\n";

    runtime.run();

    std::cout << "\n=== Demo Complete ===\n";
    return 0;
}
