// scheduler.hpp - MiniSeastar Scheduler
// Phase 1: Coroutine runtime without I/O
//
// This file implements the Scheduler, which manages coroutine execution.
// It maintains a ready queue of coroutine handles and drives the event loop.
//
// Key responsibilities:
//   - Maintain a queue of ready-to-run coroutines
//   - Execute run() loop that drains ready queue
//   - Support timer/sleep operations via internal timer queue
//
// Design:
//   - Single-threaded event loop (multi-threaded in Phase 4)
//   - FIFO ready queue for fairness
//   - Timer heap for sleep operations
//
// Invariants:
//   - All coroutines run on the same thread
//   - Scheduler must outlive all tasks
//   - run() is called from the scheduler thread only

#ifndef MINISEASTAR_SCHEDULER_HPP
#define MINISEASTAR_SCHEDULER_HPP

#include <chrono>
#include <cstddef>
#include <deque>
#include <memory>
#include <optional>
#include <queue>
#include <thread>

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

// Forward declaration of Task
template<typename T>
class Task;

// ============================================================================
// TimerEntry - Entry in the timer heap
// ============================================================================

/**
 * TimerEntry represents a scheduled timer with wakeup time and associated
 * coroutine handle.
 */
struct TimerEntry {
    std::chrono::steady_clock::time_point wake_time;
    coroutine_ns::coroutine_handle<> handle;

    // Order by wake_time (earliest first for min-heap)
    bool operator<(const TimerEntry& other) const {
        return wake_time > other.wake_time;  // Reverse for std::priority_queue
    }
};

// ============================================================================
// Scheduler - Single-threaded coroutine scheduler
// ============================================================================

/**
 * Scheduler manages coroutine execution via an event loop pattern.
 *
 * The run() loop follows this pattern:
 *   1. Drain the ready queue (resume all ready coroutines)
 *   2. Process timers (wake up expired sleepers)
 *   3. If no ready coroutines and no timers, exit (or block on condition)
 *
 * Thread safety:
 *   - Single-threaded in Phase 1; tasks must be resumed on scheduler thread
 *   - All public methods except construction must be called from scheduler thread
 */
class Scheduler {
public:
    Scheduler() = default;
    ~Scheduler() {
        // Drain any remaining coroutines
        while (!ready_queue_.empty()) {
            auto h = ready_queue_.front();
            ready_queue_.pop_front();
            h.destroy();
        }
    }

    // Non-copyable, non-movable
    Scheduler(const Scheduler&) = delete;
    Scheduler& operator=(const Scheduler&) = delete;

    // ------------------------------------------------------------------------
    // Public API
    // ------------------------------------------------------------------------

    /**
     * Schedule a coroutine to run.
     *
     * The coroutine is added to the ready queue and will be resumed
     * when the scheduler's run() loop processes it.
     *
     * @param handle The coroutine handle to schedule
     */
    void schedule(coroutine_ns::coroutine_handle<> handle) {
        ready_queue_.push_back(handle);
    }

    /**
     * Schedule a task by extracting its handle.
     * Convenience method for task<T>.
     */
    template<typename T>
    void schedule(Task<T>& task);

    /**
     * Run the event loop.
     *
     * This loops until:
     *   - All coroutines complete (ready queue empty and no pending timers)
     *   - An exception is thrown (propagates to caller)
     *
     * @return Number of coroutines that were executed
     */
    std::size_t run();

    /**
     * Run the event loop with a maximum number of iterations.
     * Useful for testing or bounded execution.
     */
    std::size_t run(std::size_t max_iterations);

    /**
     * Get the number of ready coroutines.
     */
    std::size_t ready_count() const noexcept {
        return ready_queue_.size();
    }

    /**
     * Get the number of pending timers.
     */
    std::size_t timer_count() const noexcept {
        return timers_.size();
    }

    /**
     * Check if the scheduler has work to do.
     */
    bool has_work() const noexcept {
        return !ready_queue_.empty() || !timers_.empty();
    }

    // For use by awaitables
    void add_timer(const TimerEntry& entry);

private:
    // Ready queue: FIFO for fairness
    std::deque<coroutine_ns::coroutine_handle<>> ready_queue_;

    // Timer heap: min-heap ordered by wake_time
    std::priority_queue<TimerEntry> timers_;
};

// ============================================================================
// Scheduler singleton (optional convenience)
// ============================================================================

/**
 * Get the global scheduler instance.
 * Thread-safe for single-threaded use (Phase 1).
 */
inline Scheduler& global_scheduler() {
    static Scheduler instance;
    return instance;
}

}  // namespace miniseastar

#endif  // MINISEASTAR_SCHEDULER_HPP
