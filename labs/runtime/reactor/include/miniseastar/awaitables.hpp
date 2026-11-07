// awaitables.hpp - MiniSeastar Awaitable Types
// Phase 1: Coroutine runtime without I/O
//
// This file provides fundamental awaitable types:
//   - yield: cooperative yield back to scheduler
//   - sleep_for: timer-based suspension
//
// These awaitables are the building blocks for coroutine-based async operations.
//
// Invariants:
//   - All awaitables implement the awaitable concept (await_ready, await_suspend, await_resume)
//   - sleep_for uses the scheduler's timer mechanism
//   - yield always suspends (never returns ready)

#ifndef MINISEASTAR_AWAITABLES_HPP
#define MINISEASTAR_AWAITABLES_HPP

#include <chrono>

// Include scheduler first for TimerEntry and global_scheduler
#include <miniseastar/scheduler.hpp>

#if defined(__APPLE__) && defined(__clang__)
// Use experimental coroutines on Apple Clang
#include <experimental/coroutine>
namespace coroutine_ns = std::experimental::coroutines_v1;
#else
// Use standard coroutines elsewhere
#include <coroutine>
namespace coroutine_ns = std;
#endif

namespace miniseastar {

// ============================================================================
// yield - Cooperative yield back to scheduler
// ============================================================================

/**
 * YieldAwaiter implements the yield awaitable.
 *
 * When co_await yield() is called:
 *   1. await_ready() returns false (always suspend)
 *   2. await_suspend() reschedules the current coroutine
 *   3. await_resume() never called (suspend always happens)
 *
 * This gives up execution to other ready coroutines, enabling
 * fair scheduling among coroutines.
 *
 * Usage:
 *   for (int i = 0; i < 1000; ++i) {
 *       do_work();
 *       co_await yield();  // Let other coroutines run
 *   }
 */
class YieldAwaiter {
public:
    [[nodiscard]] bool await_ready() const noexcept {
        return false;  // Always suspend
    }

    void await_suspend(coroutine_ns::coroutine_handle<> continuation) noexcept {
        // Re-schedule the current coroutine for later execution
        // This puts it at the back of the ready queue
        global_scheduler().schedule(continuation);
    }

    void await_resume() const noexcept {
        // Never reached because await_ready() returns false
    }
};

/**
 * Convenience function for yielding execution.
 */
[[nodiscard]] YieldAwaiter yield() noexcept {
    return YieldAwaiter{};
}

// ============================================================================
// sleep_for - Timer-based suspension
// ============================================================================

/**
 * SleepAwaiter implements the sleep_for awaitable.
 *
 * When co_await sleep_for(duration) is called:
 *   1. await_ready() returns false (always suspend unless duration is 0)
 *   2. await_suspend() registers a timer and suspends
 *   3. await_resume() returns when timer expires
 *
 * The timer is registered with the scheduler's timer queue.
 * When the timer expires, the coroutine is resumed.
 *
 * Failure modes:
 *   - If the scheduler is destroyed before the timer expires,
 *     the coroutine will never resume (resource leak)
 *   - If duration is very small, may busy-spin
 *
 * @param duration The amount of time to sleep
 */
template<typename Duration>
class SleepAwaiter {
public:
    explicit SleepAwaiter(Duration duration)
        : duration_(duration)
        , wake_time_(std::chrono::steady_clock::now() + duration)
    {}

    [[nodiscard]] bool await_ready() const noexcept {
        return duration_.count() <= 0;
    }

    void await_suspend(coroutine_ns::coroutine_handle<> continuation) noexcept {
        // Register timer with the scheduler
        TimerEntry entry;
        entry.wake_time = wake_time_;
        entry.handle = continuation;
        global_scheduler().add_timer(entry);
    }

    void await_resume() const noexcept {
        // Sleep complete
    }

private:
    Duration duration_;
    std::chrono::steady_clock::time_point wake_time_;
};

/**
 * Sleep for a specified duration.
 *
 * @param duration The amount of time to sleep (any Duration type)
 * @return An awaitable that suspends until the duration expires
 */
template<typename Duration>
[[nodiscard]] SleepAwaiter<Duration> sleep_for(Duration duration) {
    return SleepAwaiter<Duration>(duration);
}

/**
 * Sleep for a specified duration (convenience overload for std::chrono).
 */
[[nodiscard]] SleepAwaiter<std::chrono::milliseconds>
sleep_for(std::chrono::milliseconds duration) {
    return SleepAwaiter<std::chrono::milliseconds>(duration);
}

}  // namespace miniseastar

#endif  // MINISEASTAR_AWAITABLES_HPP
