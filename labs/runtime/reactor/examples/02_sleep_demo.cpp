// 02_sleep_demo.cpp - Sleep/Delay Demo
// Phase 1: Demonstrates timer-based suspension
//
// This demo shows:
//   - Using sleep_for to suspend a coroutine
//   - Multiple coroutines sleeping concurrently
//   - The scheduler managing timers

#include <chrono>
#include <iostream>
#include "miniseastar/runtime.hpp"

using namespace miniseastar;

// ---------------------------------------------------------------------------
// A task that sleeps for a specified duration
// ---------------------------------------------------------------------------
Task<void> sleeping_task(int id, std::chrono::milliseconds duration) {
    std::cout << "[task " << id << "] Starting, will sleep for "
              << duration.count() << "ms\n";

    co_await sleep_for(duration);

    std::cout << "[task " << id << "] Woke up after " << duration.count() << "ms\n";
    co_return;
}

// ---------------------------------------------------------------------------
// A task that counts with yields
// ---------------------------------------------------------------------------
Task<void> counting_task(int id, int count) {
    for (int i = 1; i <= count; ++i) {
        std::cout << "[task " << id << "] Count: " << i << "\n";

        // Yield every few iterations to allow other tasks to run
        if (i % 3 == 0) {
            co_await yield();
        }
    }
    std::cout << "[task " << id << "] Done counting\n";
    co_return;
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------
int main() {
    std::cout << "=== MiniSeastar Sleep Demo ===\n\n";

    Runtime runtime;

    // Spawn tasks with different sleep durations
    runtime.spawn(sleeping_task(1, std::chrono::milliseconds(100)));
    runtime.spawn(sleeping_task(2, std::chrono::milliseconds(50)));
    runtime.spawn(sleeping_task(3, std::chrono::milliseconds(150)));

    // Spawn a counting task
    runtime.spawn(counting_task(4, 12));

    std::cout << "[main] Running event loop...\n\n";

    auto start = std::chrono::steady_clock::now();
    runtime.run();
    auto end = std::chrono::steady_clock::now();

    auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(end - start);
    std::cout << "\n[main] Total time: " << elapsed.count() << "ms\n";

    std::cout << "\n=== Demo Complete ===\n";
    return 0;
}
