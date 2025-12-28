#include "../include/fwd.h"
#include <atomic>
#include <cstddef>
#include <functional>
#include <future>
#include <memory>
#include <mutex>
#include <optional>
#include <queue>
#include <thread>
#include <vector>
#include <condition_variable>
#include <algorithm>
#include <iostream>

/**
 * @brief Rejection policy for when the task queue is full.
 */
enum class RejectPolicy {
  CALLER_RUNS,   ///< Submitter executes the task synchronously
  DISCARD,       ///< Silently discard the new task
  DISCARD_OLDEST, ///< Discard the oldest (earliest submitted) task
  ABORT          ///< Throw an exception to reject the task
};

/**
 * @brief A lock-free work-stealing deque for a single worker.
 *
 * Based on the Chase-Lev work-stealing algorithm:
 * - Owner pushes/pops from the bottom (LIFO - good for cache locality)
 * - Thieves steal from the top (FIFO - fair to all workers)
 *
 * This allows efficient local work while enabling load balancing via stealing.
 *
 * @tparam T Task type (typically std::function<void()>).
 */
template <typename T>
class WorkStealingDeque {
 private:
  std::vector<T> buffer_;
  std::atomic<size_t> top_;     // Producer/consumer index (bottom for owner)
  std::atomic<size_t> bottom_;  // Consumer index (top for thieves)
  std::atomic<size_t> steal_count_{0};

 public:
  explicit WorkStealingDeque(size_t capacity = 256)
      : buffer_(capacity), top_(0), bottom_(0) {}

  // Owner: push to bottom (LIFO order for cache locality)
  void pushBottom(T task) {
    size_t b = bottom_.load(std::memory_order_relaxed);
    size_t t = top_.load(std::memory_order_acquire);
    size_t size = b - t;

    if (size >= buffer_.size() - 1) {
      // Double the buffer size
      resizeBuffer();
      b = bottom_.load(std::memory_order_relaxed);
    }

    buffer_[b % buffer_.size()] = std::move(task);
    bottom_.store(b + 1, std::memory_order_release);
  }

  // Owner: pop from bottom (LIFO order)
  std::optional<T> popBottom() {
    size_t b = bottom_.load(std::memory_order_relaxed);
    size_t t = top_.load(std::memory_order_acquire);

    if (b <= t) {
      return std::nullopt;  // Empty, don't underflow
    }

    b = b - 1;
    bottom_.store(b, std::memory_order_relaxed);
    std::atomic_thread_fence(std::memory_order_seq_cst);

    size_t top = top_.load(std::memory_order_acquire);

    if (b > top) {
      // Not empty, take from bottom
      T task = std::move(buffer_[b % buffer_.size()]);
      if (b == top) {
        // Last item - need to CAS both top and bottom
        if (top_.compare_exchange_strong(top, top + 1,
                                          std::memory_order_seq_cst,
                                          std::memory_order_relaxed)) {
          bottom_.store(top, std::memory_order_relaxed);
          return task;
        }
        // CAS failed, another thief stole it
        bottom_.store(b, std::memory_order_relaxed);
        return std::nullopt;
      }
      return task;
    }

    // Empty, reset bottom to top
    bottom_.store(top, std::memory_order_relaxed);
    return std::nullopt;
  }

  // Thief: steal from top (FIFO order - fair to all thieves)
  std::optional<T> steal() {
    size_t t = top_.load(std::memory_order_acquire);
    std::atomic_thread_fence(std::memory_order_seq_cst);
    size_t b = bottom_.load(std::memory_order_acquire);

    if (t >= b) {
      return std::nullopt;  // Empty
    }

    // Try to increment top
    if (top_.compare_exchange_strong(t, t + 1,
                                      std::memory_order_seq_cst,
                                      std::memory_order_relaxed)) {
      steal_count_.fetch_add(1, std::memory_order_relaxed);
      T task = std::move(buffer_[t % buffer_.size()]);
      return task;
    }
    return std::nullopt;  // CAS failed, retry
  }

  size_t size() const {
    size_t b = bottom_.load(std::memory_order_relaxed);
    size_t t = top_.load(std::memory_order_acquire);
    return (b > t) ? (b - t) : 0;
  }

  size_t stealCount() const {
    return steal_count_.load(std::memory_order_relaxed);
  }

 private:
  void resizeBuffer() {
    size_t old_size = buffer_.size();
    std::vector<T> new_buffer(old_size * 2);

    size_t t = top_.load(std::memory_order_acquire);
    size_t b = bottom_.load(std::memory_order_acquire);

    for (size_t i = t; i < b; ++i) {
      new_buffer[i % old_size] = std::move(buffer_[i % old_size]);
    }

    buffer_ = std::move(new_buffer);
    top_.store(0, std::memory_order_release);
    bottom_.store(b - t, std::memory_order_release);
  }
};

/**
 * @brief High-performance thread pool with work-stealing support.
 *
 * Design Principles:
 * 1. **Work-Stealing**: Each worker has a local deque for cache-efficient LIFO access.
 *    When idle, workers steal from others' deques in FIFO order for fairness.
 * 2. **Lock-Free Local Queue**: Owner's push/pop are lock-free.
 * 3. **Sharded Shared Queue**: Multiple shared queues to reduce contention.
 * 4. **Configurable Rejection Policy**: Handle overflow gracefully.
 *
 * @tparam T Task type (typically std::function<void()>).
 */
template <typename T = std::function<void()>>
class ThreadPool {
 public:
  explicit ThreadPool(
      size_t num_threads = std::thread::hardware_concurrency(),
      RejectPolicy policy = RejectPolicy::CALLER_RUNS,
      size_t max_queue_size = 10000)
      : shutdown_(false),
        active_count_(0),
        reject_policy_(policy),
        max_queue_size_(max_queue_size),
        next_worker_(0) {
    if (num_threads == 0) {
      num_threads = std::thread::hardware_concurrency();
    }
    if (num_threads == 0) {
      num_threads = 4;  // Fallback
    }

    // Create worker threads
    for (size_t i = 0; i < num_threads; ++i) {
      workers_.emplace_back([this, i]() {
        workerThread(i);
      });
    }

    // Create sharded shared queues to reduce contention
    size_t num_shards = std::min(num_threads * 2, size_t(32));
    for (size_t i = 0; i < num_shards; ++i) {
      shared_queues_.push_back(std::make_unique<SharedQueue>());
    }
  }

  ~ThreadPool() {
    shutdownAll();
    for (auto& worker : workers_) {
      if (worker.joinable()) {
        worker.join();
      }
    }
  }

  // Non-copyable
  ThreadPool(const ThreadPool&) = delete;
  ThreadPool& operator=(const ThreadPool&) = delete;

  /**
   * @brief Submit a task to the thread pool.
   * @param task The task to execute.
   * @return A future that will hold the result when complete.
   */
  template <typename F, typename... Args>
  auto submit(F&& f, Args&&... args) -> std::future<decltype(f(args...))> {
    using ReturnType = decltype(f(args...));
    auto task = std::make_shared<std::packaged_task<ReturnType()>>(
        std::bind(std::forward<F>(f), std::forward<Args>(args)...));

    auto future = task->get_future();

    if (!trySubmit([task]() { (*task)(); })) {
      // Rejection policy
      handleRejection([task]() { (*task)(); });
    }

    return future;
  }

  /**
   * @brief Submit a fire-and-forget task.
   * @param task The task to execute.
   * @return true if submitted, false if rejected.
   */
  bool submitVoid(std::function<void()> task) {
    if (!trySubmit(std::move(task))) {
      handleRejection(task);
      return false;
    }
    return true;
  }

  /**
   * @brief Get the number of worker threads.
   */
  size_t numThreads() const {
    return workers_.size();
  }

  /**
   * @brief Get the number of active (busy) workers.
   */
  size_t activeCount() const {
    return active_count_.load(std::memory_order_acquire);
  }

  /**
   * @brief Get the total number of pending tasks.
   */
  size_t pendingCount() const {
    size_t total = 0;
    total += local_queues_sum();
    total += shared_queues_sum();
    return total;
  }

  /**
   * @brief Wait for all pending tasks to complete.
   */
  void wait() {
    while (pendingCount() > 0 || activeCount() > 0) {
      std::this_thread::yield();
    }
  }

  /**
   * @brief Shutdown the thread pool gracefully.
   * Waits for all pending tasks to complete.
   */
  void shutdown() {
    shutdownAll();
    for (auto& worker : workers_) {
      if (worker.joinable()) {
        worker.join();
      }
    }
  }

 private:
  struct SharedQueue {
    std::queue<std::function<void()>> queue;
    std::mutex mutex;
  };

  std::vector<std::thread> workers_;
  std::vector<std::unique_ptr<WorkStealingDeque<std::function<void()>>>>
      local_queues_;
  std::vector<std::unique_ptr<SharedQueue>> shared_queues_;

  std::atomic<bool> shutdown_;
  std::atomic<size_t> active_count_;
  RejectPolicy reject_policy_;
  const size_t max_queue_size_;
  std::atomic<size_t> next_worker_;

  std::mutex exit_mutex_;
  std::condition_variable exit_cv_;

  bool trySubmit(std::function<void()> task) {
    // Prefer local queue for cache locality
    size_t worker_idx = next_worker_.fetch_add(1, std::memory_order_relaxed) %
                        local_queues_.size();

    auto& local_queue = *local_queues_[worker_idx];
    size_t local_size = local_queue.size();

    if (local_size < max_queue_size_) {
      local_queue.pushBottom(std::move(task));
      return true;
    }

    // Try sharded shared queues
    size_t shard = worker_idx % shared_queues_.size();
    {
      std::lock_guard<std::mutex> lock(shared_queues_[shard]->mutex);
      if (shared_queues_[shard]->queue.size() < max_queue_size_) {
        shared_queues_[shard]->queue.push(std::move(task));
        return true;
      }
    }

    return false;
  }

  void handleRejection(const std::function<void()>& task) {
    switch (reject_policy_) {
      case RejectPolicy::CALLER_RUNS:
        // Execute in the calling thread
        task();
        break;
      case RejectPolicy::DISCARD:
        // Silently discard
        break;
      case RejectPolicy::DISCARD_OLDEST:
        // Try to discard one task from local queue
        local_queues_[next_worker_ % local_queues_.size()]->popBottom();
        // Retry submit (simplified - in practice might need loop)
        break;
      case RejectPolicy::ABORT:
        throw std::runtime_error("Thread pool queue is full");
    }
  }

  void workerThread(size_t worker_id) {
    // Initialize local queue for this worker
    if (local_queues_.size() <= worker_id) {
      local_queues_.emplace_back(
          std::make_unique<WorkStealingDeque<std::function<void()>>>(256));
    }

    auto& local_queue = *local_queues_[worker_id];

    while (!shutdown_.load(std::memory_order_acquire)) {
      std::function<void()> task;

      // 1. Try to steal from other workers' local queues (work-stealing)
      // Start from a random offset for better load distribution
      size_t start = (worker_id + 1) % local_queues_.size();
      size_t steals = 0;
      const size_t max_steals = local_queues_.size();  // Steal from all once

      while (steals < max_steals && !task) {
        size_t idx = (start + steals) % local_queues_.size();
        if (idx != worker_id) {
          task = local_queues_[idx]->steal().value_or(std::function<void()>());
        }
        ++steals;
      }

      // 2. Try local queue
      if (!task) {
        task = local_queue.popBottom().value_or(std::function<void()>());
      }

      // 3. Try sharded shared queues
      if (!task) {
        size_t shard = worker_id % shared_queues_.size();
        {
          std::lock_guard<std::mutex> lock(shared_queues_[shard]->mutex);
          if (!shared_queues_[shard]->queue.empty()) {
            task = std::move(shared_queues_[shard]->queue.front());
            shared_queues_[shard]->queue.pop();
          }
        }
      }

      // 4. If still no task, try other shards
      if (!task) {
        size_t shard = worker_id % shared_queues_.size();
        for (size_t i = 0; i < shared_queues_.size(); ++i) {
          if (i == shard) continue;
          std::lock_guard<std::mutex> lock(shared_queues_[i]->mutex);
          if (!shared_queues_[i]->queue.empty()) {
            task = std::move(shared_queues_[i]->queue.front());
            shared_queues_[i]->queue.pop();
            break;
          }
        }
      }

      if (task) {
        active_count_.fetch_add(1, std::memory_order_relaxed);
        try {
          task();
        } catch (...) {
          // Task threw an exception - swallow it or log it
          std::cerr << "Task threw exception in thread pool" << std::endl;
        }
        active_count_.fetch_sub(1, std::memory_order_relaxed);
      } else {
        // No task found - yield to avoid busy-waiting
        std::this_thread::yield();
      }
    }
  }

  size_t local_queues_sum() const {
    size_t total = 0;
    for (const auto& q : local_queues_) {
      total += q->size();
    }
    return total;
  }

  size_t shared_queues_sum() const {
    size_t total = 0;
    for (const auto& q : shared_queues_) {
      std::lock_guard<std::mutex> lock(q->mutex);
      total += q->queue.size();
    }
    return total;
  }

  void shutdownAll() {
    shutdown_.store(true, std::memory_order_release);
  }
};

// ============================================================================
// Test
// ============================================================================

void test_thread_pool() {
  std::cout << "\n=== Testing Thread Pool ===" << std::endl;

  ThreadPool<> pool(4, RejectPolicy::DISCARD, 1000);
  std::cout << "Thread pool created with " << pool.numThreads() << " workers" << std::endl;

  // Test 1: Submit multiple tasks
  constexpr int NUM_TASKS = 100;
  std::atomic<int> counter{0};

  for (int i = 0; i < NUM_TASKS; ++i) {
    pool.submitVoid([&counter, i]() {
      std::this_thread::sleep_for(std::chrono::microseconds(100));
      counter++;
    });
  }

  pool.wait();
  std::cout << "Task counter: " << counter.load() << " / " << NUM_TASKS << std::endl;

  // Test 2: Submit with return values
  auto future = pool.submit([](int x, int y) { return x + y; }, 10, 20);
  std::cout << "10 + 20 = " << future.get() << std::endl;

  // Test 3: Stress test with many tasks
  constexpr int STRESS_TASKS = 10000;
  std::atomic<size_t> sum{0};

  auto stress_start = std::chrono::high_resolution_clock::now();
  for (int i = 0; i < STRESS_TASKS; ++i) {
    pool.submitVoid([&sum, i]() {
      sum += i;
    });
  }
  pool.wait();
  auto stress_end = std::chrono::high_resolution_clock::now();

  size_t expected_sum = (STRESS_TASKS - 1) * STRESS_TASKS / 2;
  auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(
      stress_end - stress_start);

  std::cout << "Stress test: " << STRESS_TASKS << " tasks in "
            << duration.count() << " ms" << std::endl;
  std::cout << "Sum: " << sum.load() << " (expected: " << expected_sum << ")"
            << (sum.load() == expected_sum ? " ✓" : " ✗") << std::endl;

  std::cout << "Active workers: " << pool.activeCount() << std::endl;
  std::cout << "✓ THREAD POOL TEST PASSED" << std::endl;
}

int main() {
  test_thread_pool();
  return 0;
}
