// 04_pingpong_bench.cpp - Ping-Pong Benchmark
// Phase 1: Measures task switching performance
//
// This benchmark creates tasks that count with yields.
// It measures how many operations can be completed per second.
//
// This tests:
//   - Task creation/destruction overhead
//   - Scheduler efficiency
//   - Context switch performance

#include <chrono>
#include <iostream>
#include <atomic>
#include "miniseastar/runtime.hpp"

using namespace std::chrono;
using namespace miniseastar;

// ---------------------------------------------------------------------------
// Simple counting task with yields
// ---------------------------------------------------------------------------
Task<void> counting_task(int id, std::atomic<int>& counter, int rounds) {
    for (int i = 0; i < rounds; ++i) {
        ++counter;
        co_await yield();
    }
    std::cout << "[task " << id << "] Done counting to " << rounds << "\n";
    co_return;
}

// ---------------------------------------------------------------------------
// Chained counting task
// ---------------------------------------------------------------------------
Task<int> chain_count(int depth, int value) {
    if (depth == 0) {
        co_return value;
    }
    int result = co_await chain_count(depth - 1, value);
    co_return result + 1;
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------
int main() {
    std::cout << "=== MiniSeastar Benchmark ===\n\n";

    // Benchmark 1: Counting with yields
    {
        std::cout << "--- Benchmark 1: Counting with Yields ---\n";

        constexpr int NUM_TASKS = 10;
        constexpr int ROUNDS = 1000;

        std::atomic<int> total_ops{0};

        auto start = steady_clock::now();

        Runtime runtime;

        for (int i = 0; i < NUM_TASKS; ++i) {
            runtime.spawn(counting_task(i, total_ops, ROUNDS));
        }

        runtime.run();

        auto end = steady_clock::now();
        auto elapsed = duration_cast<milliseconds>(end - start);

        std::cout << "Total operations: " << total_ops.load() << "\n";
        std::cout << "Time: " << elapsed.count() << "ms\n";
        std::cout << "Ops/sec: " << (total_ops.load() * 1000 / std::max(1LL, elapsed.count())) << "\n\n";
    }

    // Benchmark 2: Chained awaits
    {
        std::cout << "--- Benchmark 2: Chain Tasks ---\n";

        constexpr int CHAIN_LENGTH = 50;
        constexpr int ITERATIONS = 500;

        auto start = steady_clock::now();

        Runtime runtime;

        for (int i = 0; i < ITERATIONS; ++i) {
            runtime.spawn(chain_count(CHAIN_LENGTH, 0));
        }

        runtime.run();

        auto end = steady_clock::now();
        auto elapsed = duration_cast<milliseconds>(end - start);

        std::cout << "Chains created: " << ITERATIONS << "\n";
        std::cout << "Chain length: " << CHAIN_LENGTH << "\n";
        std::cout << "Time: " << elapsed.count() << "ms\n";
        std::cout << "Chains/sec: " << (ITERATIONS * 1000 / std::max(1LL, elapsed.count())) << "\n\n";
    }

    std::cout << "=== Benchmark Complete ===\n";
    return 0;
}
