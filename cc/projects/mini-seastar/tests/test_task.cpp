// test_task.cpp - Task unit tests
// Phase 1: Tests for task<T> coroutine type

#include <gtest/gtest.h>
#include "miniseastar/task.hpp"
#include "miniseastar/scheduler.hpp"

using namespace miniseastar;

// ---------------------------------------------------------------------------
// Test: Basic task creation and execution
// ---------------------------------------------------------------------------
TEST(TaskTest, BasicTask) {
    bool executed = false;

    auto task = [&executed]() -> Task<void> {
        executed = true;
        co_return;
    }();

    EXPECT_FALSE(executed);

    Scheduler scheduler;
    scheduler.schedule(task.handle());
    scheduler.run();

    EXPECT_TRUE(executed);
}

// ---------------------------------------------------------------------------
// Test: Task with return value
// ---------------------------------------------------------------------------
TEST(TaskTest, ReturnValue) {
    auto task = []() -> Task<int> {
        co_return 42;
    }();

    Scheduler scheduler;
    scheduler.schedule(task.handle());
    scheduler.run();

    EXPECT_TRUE(task.is_ready());
    EXPECT_EQ(task.get(), 42);
}

// ---------------------------------------------------------------------------
// Test: Task chaining with co_await
// ---------------------------------------------------------------------------
TEST(TaskTest, Chaining) {
    auto inner = []() -> Task<int> {
        co_return 10;
    }();

    auto outer = [&inner]() -> Task<int> {
        int value = co_await std::move(inner);
        co_return value * 2;
    }();

    // Use global scheduler for chained tasks
    global_scheduler().schedule(outer.handle());
    global_scheduler().run();

    EXPECT_TRUE(outer.is_ready());
    EXPECT_EQ(outer.get(), 20);
}

// ---------------------------------------------------------------------------
// Test: Task exception propagation
// ---------------------------------------------------------------------------
TEST(TaskTest, ExceptionPropagation) {
    auto task = []() -> Task<int> {
        throw std::runtime_error("Test error");
        co_return 0;
    }();

    Scheduler scheduler;
    scheduler.schedule(task.handle());
    scheduler.run();

    EXPECT_TRUE(task.is_ready());
    EXPECT_THROW(task.get(), std::runtime_error);
}

// ---------------------------------------------------------------------------
// Test: Multiple tasks execution
// ---------------------------------------------------------------------------
TEST(TaskTest, MultipleTasks) {
    std::atomic<int> counter{0};

    auto make_task = [&counter](int value) -> Task<void> {
        counter += value;
        co_return;
    };

    Scheduler scheduler;
    scheduler.schedule(make_task(1).handle());
    scheduler.schedule(make_task(2).handle());
    scheduler.schedule(make_task(3).handle());

    scheduler.run();

    EXPECT_EQ(counter.load(), 6);
}

// ---------------------------------------------------------------------------
// Test: Task move semantics
// ---------------------------------------------------------------------------
TEST(TaskTest, MoveSemantics) {
    auto task1 = []() -> Task<int> {
        co_return 100;
    }();

    Task<int> task2 = std::move(task1);

    EXPECT_FALSE(task1);
    EXPECT_TRUE(task2);

    Scheduler scheduler;
    scheduler.schedule(task2.handle());
    scheduler.run();

    EXPECT_EQ(task2.get(), 100);
}

// ---------------------------------------------------------------------------
// Test: Task done check
// ---------------------------------------------------------------------------
TEST(TaskTest, DoneCheck) {
    auto task = []() -> Task<int> {
        co_return 42;
    }();

    EXPECT_FALSE(task.done());

    Scheduler scheduler;
    scheduler.schedule(task.handle());
    scheduler.run();

    EXPECT_TRUE(task.done());
}
