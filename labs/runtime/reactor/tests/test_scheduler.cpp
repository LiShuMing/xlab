// test_scheduler.cpp - Scheduler unit tests
// Phase 1: Tests for the coroutine scheduler

#include <gtest/gtest.h>
#include "miniseastar/scheduler.hpp"
#include "miniseastar/task.hpp"

using namespace miniseastar;

// ---------------------------------------------------------------------------
// Test: Schedule and run single task
// ---------------------------------------------------------------------------
TEST(SchedulerTest, SingleTask) {
    bool executed = false;

    auto task = [&executed]() -> Task<void> {
        executed = true;
        co_return;
    }();

    Scheduler scheduler;
    scheduler.schedule(task.handle());

    EXPECT_EQ(scheduler.ready_count(), 1);
    EXPECT_TRUE(scheduler.has_work());

    scheduler.run();

    EXPECT_TRUE(executed);
    EXPECT_EQ(scheduler.ready_count(), 0);
    EXPECT_FALSE(scheduler.has_work());
}

// ---------------------------------------------------------------------------
// Test: FIFO execution order
// ---------------------------------------------------------------------------
TEST(SchedulerTest, FIFOOrder) {
    std::vector<int> order;

    auto make_task = [&order](int id) -> Task<void> {
        order.push_back(id);
        co_return;
    };

    Scheduler scheduler;
    scheduler.schedule(make_task(1).handle());
    scheduler.schedule(make_task(2).handle());
    scheduler.schedule(make_task(3).handle());

    scheduler.run();

    ASSERT_EQ(order.size(), 3);
    EXPECT_EQ(order[0], 1);
    EXPECT_EQ(order[1], 2);
    EXPECT_EQ(order[2], 3);
}

// ---------------------------------------------------------------------------
// Test: Empty scheduler run
// ---------------------------------------------------------------------------
TEST(SchedulerTest, EmptyRun) {
    Scheduler scheduler;

    std::size_t executed = scheduler.run();

    EXPECT_EQ(executed, 0);
    EXPECT_EQ(scheduler.ready_count(), 0);
}

// ---------------------------------------------------------------------------
// Test: Run with max iterations
// ---------------------------------------------------------------------------
TEST(SchedulerTest, MaxIterations) {
    std::atomic<int> counter{0};

    auto task = [&counter]() -> Task<void> {
        ++counter;
        co_return;
    };

    Scheduler scheduler;
    scheduler.schedule(task().handle());
    scheduler.schedule(task().handle());
    scheduler.schedule(task().handle());

    std::size_t executed = scheduler.run(2);

    EXPECT_EQ(executed, 2);
    EXPECT_EQ(counter.load(), 2);
    EXPECT_EQ(scheduler.ready_count(), 1);
}

// ---------------------------------------------------------------------------
// Test: Task that completes during schedule
// ---------------------------------------------------------------------------
TEST(SchedulerTest, ImmediateCompletion) {
    int value = 0;

    auto task = [&value]() -> Task<int> {
        value = 42;
        co_return std::move(value);
    }();

    Scheduler scheduler;
    scheduler.schedule(task.handle());
    scheduler.run();

    EXPECT_EQ(value, 42);
    EXPECT_TRUE(task.is_ready());
}

// ---------------------------------------------------------------------------
// Test: Ready count tracking
// ---------------------------------------------------------------------------
TEST(SchedulerTest, ReadyCount) {
    auto make_task = []() -> Task<void> {
        co_return;
    };

    Scheduler scheduler;

    EXPECT_EQ(scheduler.ready_count(), 0);

    scheduler.schedule(make_task().handle());
    EXPECT_EQ(scheduler.ready_count(), 1);

    scheduler.schedule(make_task().handle());
    EXPECT_EQ(scheduler.ready_count(), 2);

    scheduler.run();
    EXPECT_EQ(scheduler.ready_count(), 0);
}
