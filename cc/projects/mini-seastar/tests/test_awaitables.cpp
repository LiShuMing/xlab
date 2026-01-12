// test_awaitables.cpp - Awaitable unit tests
// Phase 1: Tests for yield and sleep_for awaitables

#include <gtest/gtest.h>
#include "miniseastar/awaitables.hpp"
#include "miniseastar/scheduler.hpp"
#include "miniseastar/task.hpp"

using namespace miniseastar;

// ---------------------------------------------------------------------------
// Test: Yield always suspends
// ---------------------------------------------------------------------------
TEST(AwaitablesTest, YieldSuspends) {
    YieldAwaiter awaiter;

    EXPECT_FALSE(awaiter.await_ready());
}

// ---------------------------------------------------------------------------
// Test: Yield execution
// ---------------------------------------------------------------------------
TEST(AwaitablesTest, Yield) {
    std::vector<int> order;

    auto task1 = [&order]() -> Task<void> {
        order.push_back(1);
        co_await yield();
        order.push_back(3);
        co_return;
    }();

    auto task2 = [&order]() -> Task<void> {
        order.push_back(2);
        co_return;
    }();

    Scheduler scheduler;
    scheduler.schedule(task1.handle());
    scheduler.schedule(task2.handle());

    scheduler.run();

    ASSERT_EQ(order.size(), 3);
    EXPECT_EQ(order[0], 1);
    EXPECT_EQ(order[1], 2);
    EXPECT_EQ(order[2], 3);
}

// ---------------------------------------------------------------------------
// Test: Multiple yields
// ---------------------------------------------------------------------------
TEST(AwaitablesTest, MultipleYields) {
    int count = 0;

    auto task = [&count]() -> Task<void> {
        for (int i = 0; i < 5; ++i) {
            ++count;
            if (i < 4) {
                co_await yield();
            }
        }
        co_return;
    }();

    Scheduler scheduler;
    scheduler.schedule(task.handle());
    scheduler.run();

    EXPECT_EQ(count, 5);
}

// ---------------------------------------------------------------------------
// Test: Sleep with zero duration returns immediately
// ---------------------------------------------------------------------------
TEST(AwaitablesTest, SleepZero) {
    auto sleep_zero = []() -> Task<void> {
        co_await sleep_for(std::chrono::milliseconds(0));
        co_return;
    }();

    Scheduler scheduler;
    scheduler.schedule(sleep_zero.handle());

    // Should complete quickly
    auto start = std::chrono::steady_clock::now();
    scheduler.run();
    auto end = std::chrono::steady_clock::now();

    auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(end - start);

    // Should complete in a short time (less than 10ms)
    EXPECT_LT(elapsed.count(), 10);
}

// ---------------------------------------------------------------------------
// Test: Sleep with positive duration
// ---------------------------------------------------------------------------
TEST(AwaitablesTest, SleepDuration) {
    auto task = []() -> Task<void> {
        auto start = std::chrono::steady_clock::now();
        co_await sleep_for(std::chrono::milliseconds(50));
        auto end = std::chrono::steady_clock::now();
        auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(end - start);
        EXPECT_GE(elapsed.count(), 40);  // Allow some tolerance
        co_return;
    }();

    Scheduler scheduler;
    scheduler.schedule(task.handle());
    scheduler.run();
}

// ---------------------------------------------------------------------------
// Test: Sleep and yield combination
// ---------------------------------------------------------------------------
TEST(AwaitablesTest, SleepAndYield) {
    std::vector<int> order;

    auto task = [&order]() -> Task<void> {
        order.push_back(1);
        co_await sleep_for(std::chrono::milliseconds(10));
        order.push_back(2);
        co_await yield();
        order.push_back(3);
        co_return;
    }();

    Scheduler scheduler;
    scheduler.schedule(task.handle());

    auto start = std::chrono::steady_clock::now();
    scheduler.run();
    auto end = std::chrono::steady_clock::now();

    auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(end - start);

    ASSERT_EQ(order.size(), 3);
    EXPECT_EQ(order[0], 1);
    EXPECT_EQ(order[1], 2);
    EXPECT_EQ(order[2], 3);
    EXPECT_GE(elapsed.count(), 10);
}
