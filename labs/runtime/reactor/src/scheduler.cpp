// scheduler.cpp - Scheduler Implementation
// Phase 1: Coroutine runtime without I/O

#include "miniseastar/scheduler.hpp"
#include "miniseastar/task.hpp"

namespace miniseastar {

// ---------------------------------------------------------------------------
// Template implementations that need to be in .cpp
// ---------------------------------------------------------------------------

template<typename T>
void Scheduler::schedule(Task<T>& task) {
    if (task.handle()) {
        schedule(task.handle());
    }
}

std::size_t Scheduler::run() {
    std::size_t executed = 0;
    auto now = std::chrono::steady_clock::now();

    while (true) {
        // Step 1: Process ready queue
        while (!ready_queue_.empty()) {
            auto h = ready_queue_.front();
            ready_queue_.pop_front();

            if (!h.done()) {
                h.resume();
                ++executed;
            } else {
                h.destroy();
            }
        }

        // Step 2: Process expired timers
        while (!timers_.empty() && timers_.top().wake_time <= now) {
            auto entry = timers_.top();
            timers_.pop();

            if (!entry.handle.done()) {
                entry.handle.resume();
                ++executed;
            } else {
                entry.handle.destroy();
            }
        }

        // Step 3: Check if we should exit
        if (ready_queue_.empty() && timers_.empty()) {
            break;
        }

        // Step 4: Block until next timer or ready event
        if (!timers_.empty() && ready_queue_.empty()) {
            auto sleep_duration = timers_.top().wake_time - now;
            if (sleep_duration > std::chrono::milliseconds(0)) {
                // Simple spin wait for now (Phase 1)
                // In Phase 2, this would block on kqueue
                auto sleep_ms = std::chrono::duration_cast<std::chrono::milliseconds>(
                    sleep_duration);
                // Cap at 10ms to avoid long blocking during testing
                if (sleep_ms.count() > 10) {
                    sleep_ms = std::chrono::milliseconds(10);
                }
                std::this_thread::sleep_for(sleep_ms);
            }
        }

        now = std::chrono::steady_clock::now();
    }

    return executed;
}

std::size_t Scheduler::run(std::size_t max_iterations) {
    std::size_t executed = 0;
    auto now = std::chrono::steady_clock::now();

    while (executed < max_iterations) {
        // Process ready queue
        while (!ready_queue_.empty() && executed < max_iterations) {
            auto h = ready_queue_.front();
            ready_queue_.pop_front();

            if (!h.done()) {
                h.resume();
                ++executed;
            } else {
                h.destroy();
            }
        }

        // Process expired timers
        while (!timers_.empty() && timers_.top().wake_time <= now) {
            auto entry = timers_.top();
            timers_.pop();

            if (!entry.handle.done()) {
                entry.handle.resume();
                ++executed;
            } else {
                entry.handle.destroy();
            }
        }

        if (ready_queue_.empty() && timers_.empty()) {
            break;
        }

        now = std::chrono::steady_clock::now();
    }

    return executed;
}

void Scheduler::add_timer(const TimerEntry& entry) {
    timers_.push(entry);
}

// Explicit template instantiations
template void Scheduler::schedule(Task<void>& task);
template void Scheduler::schedule(Task<int>& task);

}  // namespace miniseastar
