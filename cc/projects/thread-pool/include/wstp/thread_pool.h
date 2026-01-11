#ifndef WSTP_THREAD_POOL_H_
#define WSTP_THREAD_POOL_H_

#include <atomic>
#include <cstddef>
#include <future>
#include <memory>
#include <thread>
#include <vector>

#include "wstp/cache_padding.h"
#include "wstp/status.h"
#include "wstp/task.h"
#include "wstp/ws_deque.h"

namespace wstp {

/**
 * ThreadPool - A work-stealing thread pool implementation
 *
 * Phase 1: Baseline with single global queue protected by mutex
 * Phase 2: Work-stealing with per-thread deques
 *
 * Execution semantics:
 * - Tasks are executed exactly once (unless StopNow is called)
 * - Submit() returns std::future for result retrieval
 * - Stop() performs graceful shutdown: waits for all submitted tasks to complete
 *
 * Failure modes:
 * - Submit after Stop(): returns future with exception or invalid status
 * - Destructor calls Stop() then joins all threads
 */
class ThreadPool {
 public:
  /**
   * Create thread pool with specified number of workers
   *
   * @param num_threads Number of worker threads (0 = hardware_concurrency)
   * @param use_work_stealing Use work-stealing deques (Phase 2), false = global queue (Phase 1)
   */
  explicit ThreadPool(size_t num_threads = 0, bool use_work_stealing = false);
  ~ThreadPool();

  // Non-copyable, non-movable
  ThreadPool(const ThreadPool&) = delete;
  ThreadPool& operator=(const ThreadPool&) = delete;
  ThreadPool(ThreadPool&&) = delete;
  ThreadPool& operator=(ThreadPool&&) = delete;

  /**
   * Submit a callable task for execution
   *
   * @param f Callable to execute
   * @return std::future with the result
   *
   * Semantics:
   * - If pool is stopped: returns future with std::runtime_error
   * - If pool is shutting down: may block or fail
   */
  template <typename F>
  std::future<std::invoke_result_t<F>> Submit(F&& f);

  /**
   * Submit a callable with arguments
   */
  template <typename F, typename... Args>
  std::future<std::invoke_result_t<F, Args...>> Submit(F&& f, Args&&... args);

  /**
   * Graceful stop - waits for all submitted tasks to complete
   *
   * Semantics:
   * - Sets stopped_ flag
   * - Wakes all waiting threads
   * - Waits for all worker threads to finish
   * - Can be called multiple times (idempotent after first call)
   */
  void Stop();

  /**
   * Get number of worker threads
   */
  size_t NumThreads() const { return num_threads_; }

  /**
   * Get current queue size (approximate, for debugging)
   */
  size_t QueueSize() const;

  /**
   * Check if pool is stopped
   */
  bool IsStopped() const { return stopped_.load(std::memory_order_acquire); }

  // Statistics (Phase 3)
  struct Stats {
    size_t total_tasks_submitted = 0;
    size_t total_tasks_completed = 0;
    size_t steal_attempts = 0;
    size_t successful_steals = 0;
    size_t failed_cas = 0;
    size_t idle_spins = 0;
  };

  Stats GetStats() const;

 private:
  // Stop token type (compatible wrapper for compilers without std::stop_token)
  using StopFlag = std::atomic<bool>;

  // Phase 1: Global queue implementation
  void WorkerLoopGlobalQueue();
  void SubmitGlobalQueue(Task task);

  // Phase 2: Work-stealing implementation
  void WorkerLoopWorkStealing(size_t worker_id);
  void SubmitWorkStealing(Task task);

  // Random number generation for steal victim selection
  uint32_t RandomVictim(size_t exclude_id) const;

  // Get stop flag reference for workers
  StopFlag& GetStopFlag() { return stopped_; }
  const StopFlag& GetStopFlag() const { return stopped_; }

  // Number of worker threads
  const size_t num_threads_;

  // Whether to use work-stealing mode
  const bool use_work_stealing_;

  // Stop flag - acquire semantics for visibility
  WSTP_CACHELINE_ALIGN std::atomic<bool> stopped_{false};

  // Phase 1: Global queue protected by mutex
  struct GlobalQueueImpl;
  std::unique_ptr<GlobalQueueImpl> global_queue_;

  // Phase 2: Per-thread deques
  std::vector<WSDequePtr> deques_;

  // Worker threads
  std::vector<std::thread> workers_;

  // Random seed for steal victim selection (mutable for const methods)
  mutable std::atomic<uint32_t> rng_seed_{123456789};
};

// Template implementation must be in header

template <typename F>
std::future<std::invoke_result_t<F>> ThreadPool::Submit(F&& f) {
  if (stopped_.load(std::memory_order_acquire)) {
    std::promise<std::invoke_result_t<F>> p;
    p.set_exception(std::make_exception_ptr(
        std::runtime_error("cannot submit to stopped pool")));
    return p.get_future();
  }

  using ReturnType = std::invoke_result_t<F>;
  using PackagedTask = std::packaged_task<ReturnType()>;

  auto task = std::make_shared<PackagedTask>(std::forward<F>(f));
  std::future<ReturnType> future = task->get_future();

  if (use_work_stealing_) {
    SubmitWorkStealing([task]() { (*task)(); });
  } else {
    SubmitGlobalQueue([task]() { (*task)(); });
  }

  return future;
}

template <typename F, typename... Args>
std::future<std::invoke_result_t<F, Args...>> ThreadPool::Submit(F&& f,
                                                                Args&&... args) {
  if (stopped_.load(std::memory_order_acquire)) {
    using ReturnType = std::invoke_result_t<F, Args...>;
    std::promise<ReturnType> p;
    p.set_exception(std::make_exception_ptr(
        std::runtime_error("cannot submit to stopped pool")));
    return p.get_future();
  }

  using ReturnType = std::invoke_result_t<F, Args...>;
  using PackagedTask = std::packaged_task<ReturnType()>;

  auto task = std::make_shared<PackagedTask>(
      std::bind(std::forward<F>(f), std::forward<Args>(args)...));
  std::future<ReturnType> future = task->get_future();

  if (use_work_stealing_) {
    SubmitWorkStealing([task]() { (*task)(); });
  } else {
    SubmitGlobalQueue([task]() { (*task)(); });
  }

  return future;
}

}  // namespace wstp

#endif  // WSTP_THREAD_POOL_H_
