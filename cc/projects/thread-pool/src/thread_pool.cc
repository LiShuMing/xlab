#include "wstp/thread_pool.h"

#include <algorithm>
#include <condition_variable>
#include <cstdlib>
#include <mutex>
#include <queue>
#include <random>
#include <stdexcept>

namespace wstp {

// Phase 1: Global queue implementation
struct ThreadPool::GlobalQueueImpl {
  std::mutex mu;
  std::condition_variable cv;
  std::queue<Task> queue;
  bool shutting_down = false;
};

ThreadPool::ThreadPool(size_t num_threads, bool use_work_stealing)
    : num_threads_(num_threads == 0 ? std::thread::hardware_concurrency()
                                    : num_threads),
      use_work_stealing_(use_work_stealing),
      stopped_(false),
      global_queue_(std::make_unique<GlobalQueueImpl>()) {
  if (num_threads_ == 0) {
    throw std::invalid_argument("num_threads must be > 0");
  }

  if (use_work_stealing_) {
    // Phase 2: Create per-thread deques
    deques_.reserve(num_threads_);
    for (size_t i = 0; i < num_threads_; ++i) {
      deques_.push_back(std::make_shared<WSDeque>(1024));
    }

    // Start workers in work-stealing mode
    for (size_t i = 0; i < num_threads_; ++i) {
      workers_.emplace_back([this, i]() { WorkerLoopWorkStealing(i); });
    }
  } else {
    // Phase 1: Start workers in global queue mode
    for (size_t i = 0; i < num_threads_; ++i) {
      workers_.emplace_back([this]() { WorkerLoopGlobalQueue(); });
    }
  }
}

ThreadPool::~ThreadPool() { Stop(); }

void ThreadPool::Stop() {
  // Set stop flag with release semantics
  // This ensures all workers see the flag before we wait
  bool expected = false;
  if (stopped_.compare_exchange_strong(expected, true,
                                       std::memory_order_acq_rel,
                                       std::memory_order_acquire)) {
    if (use_work_stealing_) {
      // For work-stealing: notify all workers to wake up and check stop flag
      // Use a simple mechanism - threads will wake up and exit when queue is empty
      // Phase 2: could use a condition variable for faster wakeup
    } else {
      // Signal global queue workers
      {
        std::lock_guard<std::mutex> lock(global_queue_->mu);
        global_queue_->shutting_down = true;
      }
      global_queue_->cv.notify_all();
    }

    // Wait for all workers to finish
    for (auto& worker : workers_) {
      if (worker.joinable()) {
        worker.join();
      }
    }
  }
}

void ThreadPool::SubmitGlobalQueue(Task task) {
  // Reject submissions after stop
  if (stopped_.load(std::memory_order_acquire)) {
    return;
  }
  {
    std::lock_guard<std::mutex> lock(global_queue_->mu);
    global_queue_->queue.push(std::move(task));
  }
  // Notify one worker
  global_queue_->cv.notify_one();
}

void ThreadPool::WorkerLoopGlobalQueue() {
  while (true) {
    Task task;
    {
      std::unique_lock<std::mutex> lock(global_queue_->mu);

      // Wait for work - check both conditions
      global_queue_->cv.wait(
          lock, [this]() {
            return !global_queue_->queue.empty() ||
                   stopped_.load(std::memory_order_acquire);
          });

      // Exit if stopped AND no more work to process
      if (global_queue_->queue.empty()) {
        break;
      }

      task = std::move(global_queue_->queue.front());
      global_queue_->queue.pop();
    }

    // Execute task outside the lock
    if (task) {
      task();
    }
  }
}

void ThreadPool::SubmitWorkStealing(Task task) {
  // Round-robin submission to spread work across deques
  // This improves initial work distribution
  static std::atomic<size_t> round_robin{0};
  size_t idx = round_robin.fetch_add(1, std::memory_order_relaxed) %
               num_threads_;
  deques_[idx]->PushBottom(std::move(task));
}

void ThreadPool::WorkerLoopWorkStealing(size_t worker_id) {
  // Random generator for steal victim selection
  std::mt19937 rng(static_cast<uint32_t>(worker_id + std::hash<std::thread::id>{}(std::this_thread::get_id())));

  WSDeque& my_deque = *deques_[worker_id];

  while (!stopped_.load(std::memory_order_acquire)) {
    // Try to pop from local deque (fast path)
    Task task = my_deque.PopBottom();
    if (task) {
      task();
      continue;
    }

    // Local deque is empty, try to steal
    // Random victim selection to avoid thundering herd
    std::vector<size_t> candidates;
    candidates.reserve(num_threads_ - 1);
    for (size_t i = 0; i < num_threads_; ++i) {
      if (i != worker_id) {
        candidates.push_back(i);
      }
    }
    std::shuffle(candidates.begin(), candidates.end(), rng);

    for (size_t victim_id : candidates) {
      Task stolen = deques_[victim_id]->StealTop();
      if (stolen) {
        task = std::move(stolen);
        break;
      }
    }

    if (task) {
      task();
      continue;
    }

    // All deques empty, sleep briefly
    // Phase 3: Add exponential backoff here
    std::this_thread::sleep_for(std::chrono::microseconds(100));
  }
}

uint32_t ThreadPool::RandomVictim(size_t exclude_id) const {
  // Use thread-local RNG for better randomness and avoid atomic RNG issues
  thread_local std::mt19937 rng(std::random_device{}());
  std::uniform_int_distribution<uint32_t> dist(0, static_cast<uint32_t>(num_threads_) - 2);
  uint32_t victim = dist(rng);
  if (victim >= exclude_id) {
    victim++;
  }
  return victim;
}

size_t ThreadPool::QueueSize() const {
  if (use_work_stealing_) {
    size_t total = 0;
    for (const auto& deque : deques_) {
      total += deque->Size();
    }
    return total;
  } else {
    std::lock_guard<std::mutex> lock(global_queue_->mu);
    return global_queue_->queue.size();
  }
}

ThreadPool::Stats ThreadPool::GetStats() const {
  // Phase 3: Implement actual statistics gathering
  return Stats();
}

}  // namespace wstp
