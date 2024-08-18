// runtime.hpp - MiniSeastar Runtime
// Phase 1: Coroutine runtime without I/O
//
// This file provides the main runtime interface for MiniSeastar.
// It integrates the scheduler, task type, and awaitables.
//
// Usage:
//   int main() {
//       Runtime runtime;
//       runtime.spawn(task1());
//       runtime.spawn(task2());
//       runtime.run();
//   }
//
// Or using the global scheduler directly:
//   int main() {
//       spawn(task1());
//       spawn(task2());
//       global_scheduler().run();
//   }

#ifndef MINISEASTAR_RUNTIME_HPP
#define MINISEASTAR_RUNTIME_HPP

#include "awaitables.hpp"
#include "scheduler.hpp"
#include "task.hpp"

namespace miniseastar {

// ============================================================================
// Runtime - Main runtime interface
// ============================================================================

/**
 * Runtime is the main entry point for the coroutine system.
 *
 * In Phase 1, it's a simple wrapper around the scheduler.
 * In Phase 2, it will also manage the reactor (kqueue).
 * In Phase 4, it will be per-thread (sharded).
 *
 * Design:
 *   - Owns the scheduler instance
 *   - Provides spawn() to add coroutines
 *   - Provides run() to execute the event loop
 */
class Runtime {
public:
    Runtime() = default;
    ~Runtime() = default;

    // Non-copyable, non-movable
    Runtime(const Runtime&) = delete;
    Runtime& operator=(const Runtime&) = delete;
    Runtime(Runtime&&) = delete;
    Runtime& operator=(Runtime&&) = delete;

    /**
     * Spawn a coroutine task.
     *
     * The task is added to the ready queue and will be executed
     * when run() is called.
     *
     * @param task The task to spawn (moved into the runtime)
     */
    template<typename T>
    void spawn(Task<T> task) {
        // Schedule the task but don't start it yet
        // The scheduler's run() will process it
        if (task.handle()) {
            scheduler_.schedule(task.handle());
        }
    }

    /**
     * Run the event loop until all tasks complete.
     *
     * @return Number of tasks executed
     */
    std::size_t run() {
        return scheduler_.run();
    }

    /**
     * Run the event loop with a maximum iteration count.
     *
     * @param max_iterations Maximum number of tasks to execute
     * @return Number of tasks actually executed
     */
    std::size_t run(std::size_t max_iterations) {
        return scheduler_.run(max_iterations);
    }

    /**
     * Check if the runtime has work pending.
     */
    bool has_work() const noexcept {
        return scheduler_.has_work();
    }

    /**
     * Get the number of ready tasks.
     */
    std::size_t ready_count() const noexcept {
        return scheduler_.ready_count();
    }

private:
    Scheduler scheduler_;
};

// ============================================================================
// spawn - Convenience function to add tasks to the global scheduler
// ============================================================================

/**
 * Spawn a task onto the global scheduler.
 *
 * Usage:
 *   spawn(task_example());
 *
 * Note: The global scheduler must be running (via run()) for
 * the spawned task to execute.
 */
template<typename T>
void spawn(Task<T> task) {
    global_scheduler().schedule(task.handle());
}

}  // namespace miniseastar

#endif  // MINISEASTAR_RUNTIME_HPP
