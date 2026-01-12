// 01_coro_demo.cpp - Basic Coroutine Demo
// Phase 1: Demonstrates basic task creation and execution
//
// This demo shows:
//   - Creating coroutine tasks
//   - Scheduling tasks on the runtime
//   - Running the event loop

#include <iostream>
#include "miniseastar/runtime.hpp"

using namespace miniseastar;

// ---------------------------------------------------------------------------
// A simple coroutine that returns a value
// ---------------------------------------------------------------------------
Task<int> simple_task() {
    std::cout << "[simple_task] Starting\n";
    co_return 42;
}

// ---------------------------------------------------------------------------
// A coroutine that calls another coroutine (chaining)
// ---------------------------------------------------------------------------
Task<int> chained_task() {
    std::cout << "[chained_task] Calling simple_task...\n";

    int result = co_await simple_task();

    std::cout << "[chained_task] Got result: " << result << "\n";
    co_return result * 2;
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------
int main() {
    std::cout << "=== MiniSeastar Coroutine Demo ===\n\n";

    Runtime runtime;

    std::cout << "[main] Spawning tasks...\n";

    runtime.spawn(simple_task());
    runtime.spawn(chained_task());

    std::cout << "[main] Running event loop...\n\n";

    runtime.run();

    std::cout << "\n=== Demo Complete ===\n";
    return 0;
}
