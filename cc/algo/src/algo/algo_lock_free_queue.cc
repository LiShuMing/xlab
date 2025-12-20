#include "../include/fwd.h"
#include <atomic>
#include <cstddef>
#include <thread>
#include <algorithm>
#include <vector>
#include <mutex>
#include <iostream>
#include <chrono>

// A simple lock-free ring buffer
// Uses Capacity+1 slots to distinguish between full and empty states
template <typename T, size_t Capacity>
class LockFreeQueue {
 public:
  bool Push(const T& value) {
    while (true) {
      size_t head = head_.load(std::memory_order_relaxed);
      size_t next_head = (head + 1) % (Capacity + 1);
      
      // Check if queue is full
      size_t tail = tail_.load(std::memory_order_acquire);
      if (next_head == tail) {
        return false; // Queue full
      }
      
      // Try to atomically reserve the slot using CAS
      // Use acquire-release: acquire to see previous operations, release to publish our write
      if (head_.compare_exchange_weak(head, next_head,
                                     std::memory_order_acquire,
                                     std::memory_order_relaxed)) {
        // Successfully reserved the slot, now write the value
        data_[head] = value;
        
        // The release semantics on CAS above ensures operations before CAS are visible,
        // but we write after CAS. We need to ensure this write is visible.
        // Use a release fence to ensure the write to data_[head] is visible
        // before other threads see the updated head via acquire-load in Pop
        std::atomic_thread_fence(std::memory_order_release);
        return true;
      }
      // CAS failed, another thread reserved this slot, retry
    }
  }

  bool Pop(T& value) {
    while (true) {
      size_t tail = tail_.load(std::memory_order_relaxed);
      
      // Check if queue is empty - use acquire to see writes from Push()
      size_t head = head_.load(std::memory_order_acquire);
      if (head == tail) {
        return false; // Queue empty
      }
      
      // Try to atomically update tail using CAS to reserve this slot
      size_t next_tail = (tail + 1) % (Capacity + 1);
      // Use release on success to ensure:
      // 1. The read of data_[tail] (line 60) completes before tail_ update
      // 2. The tail_ update is visible to Push() threads (which use acquire-load on tail_)
      if (tail_.compare_exchange_weak(tail, next_tail,
                                      std::memory_order_release,
                                      std::memory_order_relaxed)) {
        // Successfully reserved the slot, now read the value
        // The acquire-load of head above ensures we see the write from Push()
        value = std::move(data_[tail]);
        return true;
      }
      // CAS failed, another thread consumed this slot, retry
    }
  }
  size_t Size() const {
    return (tail_.load(std::memory_order_acquire) - head_.load(std::memory_order_acquire) + Capacity + 1) % (Capacity + 1);
  }
  bool Empty() const {
    return head_.load(std::memory_order_acquire) == tail_.load(std::memory_order_acquire);
  }
  bool Full() const {
    return (head_.load(std::memory_order_acquire) + 1) % (Capacity + 1) == tail_.load(std::memory_order_acquire);
  }

 private:
  // Use Capacity+1 slots: when head == tail, queue is empty
  // when (head+1) % (Capacity+1) == tail, queue is full
  std::atomic<size_t> head_{0};
  std::atomic<size_t> tail_{0};
  T data_[Capacity + 1];
};


/**
 * A specialized Lock-free Queue for Single-Producer Single-Consumer (SPSC).
 * Leverages C++11 memory barriers to ensure visibility without mutexes.
 */
template <typename T, size_t Capacity>
class SpscLockFreeQueueV2 {
 public:
  SpscLockFreeQueueV2() : head_(0), tail_(0) {}

  // Non-copyable.
  SpscLockFreeQueueV2(const SpscLockFreeQueueV2&) = delete;
  SpscLockFreeQueueV2& operator=(const SpscLockFreeQueueV2&) = delete;

  /**
   * Pushes an element. Only called by the Producer thread.
   */
  bool Push(const T& value) {
    size_t h = head_.load(std::memory_order_relaxed);
    size_t next_h = (h + 1) % Capacity;

    // Check if the queue is full.
    // Use 'acquire' to ensure we see the latest 'tail_' from the consumer.
    if (next_h == tail_.load(std::memory_order_acquire)) {
      return false;
    }

    data_[h] = value;

    // 'release' ensures the data write is visible to the consumer 
    // BEFORE the head_ index is updated.
    head_.store(next_h, std::memory_order_release);
    return true;
  }

  /**
   * Pops an element. Only called by the Consumer thread.
   */
  bool Pop(T& value) {
    size_t t = tail_.load(std::memory_order_relaxed);

    // Check if the queue is empty.
    // Use 'acquire' to ensure we see the latest 'head_' from the producer.
    if (t == head_.load(std::memory_order_acquire)) {
      return false;
    }

    value = std::move(data_[t]);

    // 'release' ensures the value is moved out BEFORE tail_ is updated.
    tail_.store((t + 1) % Capacity, std::memory_order_release);
    return true;
  }

  size_t Size() const {
    return (head_.load(std::memory_order_acquire) - tail_.load(std::memory_order_acquire) + Capacity) % Capacity;
  }
  bool Empty() const {
    return head_.load(std::memory_order_acquire) == tail_.load(std::memory_order_acquire);
  }
  bool Full() const {
    return (head_.load(std::memory_order_acquire) + 1) % Capacity == tail_.load(std::memory_order_acquire);
  }

 private:
  // Align to cache line size (typically 64 bytes) to prevent False Sharing.
  alignas(64) std::atomic<size_t> head_;
  alignas(64) std::atomic<size_t> tail_;
  
  T data_[Capacity];
};

// Fixed version of the original LockFreeQueue
template <typename T, size_t Capacity>
class FixedLockFreeQueue {
 public:
  static_assert(Capacity > 0, "Capacity must be greater than 0");
  static constexpr size_t kCapacity = Capacity + 1;  // Use one extra slot for full/empty detection
  
  FixedLockFreeQueue() : head_(0), tail_(0) {}
  
  bool Push(const T& value) {
    while (true) {
      // Load current head
      size_t current_head = head_.load(std::memory_order_relaxed);
      size_t next_head = (current_head + 1) % kCapacity;
      
      // Load current tail (acquire to see previous writes)
      size_t current_tail = tail_.load(std::memory_order_acquire);
      
      // Check if queue is full
      if (next_head == current_tail) {
        return false; // Queue is full
      }
      
      // Try to reserve the slot
      if (head_.compare_exchange_weak(current_head, next_head,
                                      std::memory_order_acq_rel,
                                      std::memory_order_acquire)) {
        // Successfully reserved the slot, now write the data
        data_[current_head] = value;
        return true;
      }
      // CAS failed, another thread modified head, retry
    }
  }
  
  bool Pop(T& value) {
    while (true) {
      // Load current tail
      size_t current_tail = tail_.load(std::memory_order_relaxed);
      
      // Load current head (acquire to see previous writes)
      size_t current_head = head_.load(std::memory_order_acquire);
      
      // Check if queue is empty
      if (current_tail == current_head) {
        return false; // Queue is empty
      }
      
      // Calculate next tail
      size_t next_tail = (current_tail + 1) % kCapacity;
      
      // Try to consume the slot
      if (tail_.compare_exchange_weak(current_tail, next_tail,
                                      std::memory_order_acq_rel,
                                      std::memory_order_acquire)) {
        // Successfully consumed the slot, now read the data
        value = data_[current_tail];
        return true;
      }
      // CAS failed, another thread modified tail, retry
    }
  }
  
  bool Empty() const {
    return tail_.load(std::memory_order_acquire) == 
           head_.load(std::memory_order_acquire);
  }
  
  bool Full() const {
    size_t head = head_.load(std::memory_order_acquire);
    size_t tail = tail_.load(std::memory_order_acquire);
    return ((head + 1) % kCapacity) == tail;
  }
  
  size_t Size() const {
    size_t head = head_.load(std::memory_order_acquire);
    size_t tail = tail_.load(std::memory_order_acquire);
    
    if (head >= tail) {
      return head - tail;
    } else {
      return kCapacity - (tail - head);
    }
  }
  
  static constexpr size_t GetCapacity() { return Capacity; }  // Actual usable capacity
  
 private:
  alignas(64) std::atomic<size_t> head_;
  alignas(64) std::atomic<size_t> tail_;
  alignas(64) T data_[kCapacity];
};

template <typename T, size_t Capacity>
class ThreadSafeQueue {
public:
  ThreadSafeQueue() : head_(0), tail_(0), size_(0) {}
  
  bool Push(const T& value) {
    std::unique_lock<std::mutex> lock(mutex_);
    // Check if queue is full
    // With Capacity+1 slots, we can store at most Capacity elements
    // Full condition: (head_ + 1) % (Capacity + 1) == tail_ OR size_ == Capacity
    size_t next_head = (head_ + 1) % (Capacity + 1);
    if (next_head == tail_) {
      // Queue is full
      return false;
    }
    data_[head_] = value;
    head_ = next_head;
    ++size_;
    return true;
  }

  bool Pop(T& value) {
    std::unique_lock<std::mutex> lock(mutex_);
    // Check if queue is empty
    if (head_ == tail_) {
      // Queue is empty
      return false;
    }
    value = data_[tail_];
    tail_ = (tail_ + 1) % (Capacity + 1);
    --size_;
    return true;
  }

  size_t Size() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return size_;
  }
  bool Empty() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return size_ == 0;
  }
  bool Full() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return size_ == Capacity;
  }
private:
  size_t head_;
  size_t tail_;
  size_t size_;  // For debugging/monitoring, but head_/tail_ relationship is authoritative
  T data_[Capacity + 1];
  mutable std::mutex mutex_;
};

template <typename Queue, typename T>
void test_thread_safe_queue() {
  // Test thread safety by using multiple threads to Push and Pop concurrently
  Queue queue;
  const int num_threads = 4;
  const int num_ops = 100;

  // Producer threads
  auto producer = [&queue](int base) {
    for (int i = 0; i < num_ops; ++i) {
      int val = base * num_ops + i;
      // std::cout << "producer: " << val << std::endl;
      while (!queue.Push(val)) {
        std::this_thread::yield(); // Wait if queue is full
      }
    }
  };

  // Consumer threads
  size_t total_size = num_threads * num_ops;  
  std::vector<int> results(total_size);
  std::mutex results_mutex;
  std::atomic<size_t> idx(0);
  auto consumer = [&queue, &results_mutex, &results, &idx, total_size](int tid) {
    int value;
    size_t local_count = 0;
    // Each consumer should consume exactly num_ops items
    while (local_count < num_ops) {
      if (queue.Pop(value)) {
        size_t i = idx.fetch_add(1, std::memory_order_relaxed);
        if (i < total_size) {
          std::lock_guard<std::mutex> lock(results_mutex);
          results[i] = value;
          // std::cout << "consumer: " << tid << ", " << i << ", " << value << std::endl;
        }
        local_count++;
      } else {
        std::this_thread::yield(); // Wait if queue is empty
      }
    }
  };

  std::vector<std::thread> producers;
  std::vector<std::thread> consumers;

  // Start producers
  for (int i = 0; i < num_threads; ++i)
    producers.emplace_back(producer, i);

  // Start consumers
  for (int i = 0; i < num_threads; ++i)
    consumers.emplace_back(consumer, i);

  // Join producers
  for (auto& p : producers) p.join();
  // Join consumers
  for (auto& c : consumers) c.join();

  // Verify
  std::sort(results.begin(), results.end());
  // std::cout << "results: ";
  // for (int i = 0; i < num_threads * num_ops; ++i) {
  //   std::cout << results[i] << " ";
  // }
  // std::cout << std::endl;
  bool ok = true;
  for (int i = 0; i < num_threads * num_ops; ++i) {
    if (results[i] != i) {
      std::cout << "results[i] != i: " << results[i] << " != " << i << std::endl;
      ok = false;
      break;
    }
  }
  if (ok)
    std::cout << "Thread safety test passed: all values accounted for." << std::endl;
  else
    std::cout << "Thread safety test failed!" << std::endl;
}

// Test function
template <typename Queue>
void test_queue() {
  std::cout << "\n=== Testing " << typeid(Queue).name() << " ===" << std::endl;
  
  constexpr int NUM_THREADS = 4;
  constexpr int NUM_OPS = 1000;
  constexpr int TOTAL_OPS = NUM_THREADS * NUM_OPS;
  
  Queue queue;
  std::atomic<int> produced{0};
  std::atomic<int> consumed{0};
  std::vector<int> results(TOTAL_OPS, -1);
  std::mutex results_mutex;
  
  auto start = std::chrono::high_resolution_clock::now();
  
  // Producer threads
  std::vector<std::thread> producers;
  for (int t = 0; t < NUM_THREADS; ++t) {
    producers.emplace_back([&, t]() {
      for (int i = 0; i < NUM_OPS; ++i) {
        int value = t * NUM_OPS + i;
        while (!queue.Push(value)) {
          std::this_thread::yield();
        }
        produced.fetch_add(1, std::memory_order_relaxed);
      }
    });
  }
  
  // Consumer threads
  std::vector<std::thread> consumers;
  for (int t = 0; t < NUM_THREADS; ++t) {
    consumers.emplace_back([&]() {
      while (consumed.load(std::memory_order_relaxed) < TOTAL_OPS) {
        int value = 0;
        if (queue.Pop(value)) {
          int idx = consumed.fetch_add(1, std::memory_order_relaxed);
          if (idx < TOTAL_OPS) {
            std::lock_guard<std::mutex> lock(results_mutex);
            results[idx] = std::move(value);
          }
        } else {
          std::this_thread::yield();
        }
      }
    });
  }
  
  // Wait for all threads
  for (auto& t : producers) t.join();
  for (auto& t : consumers) t.join();
  
  auto end = std::chrono::high_resolution_clock::now();
  auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(end - start);
  
  // Verify results
  std::vector<bool> found(TOTAL_OPS, false);
  bool all_correct = true;
  int duplicates = 0;
  int missing = 0;
  
  for (int i = 0; i < TOTAL_OPS; ++i) {
    int val = results[i];
    if (val >= 0 && val < TOTAL_OPS) {
      if (found[val]) {
        ++duplicates;
        std::cout << "Duplicate: " << val << std::endl;
        all_correct = false;
      }
      found[val] = true;
    } else {
      ++missing;
      std::cout << "Invalid or missing at index " << i << ": " << val << std::endl;
      all_correct = false;
    }
  }
  
  // Check all values were found
  for (int i = 0; i < TOTAL_OPS; ++i) {
    if (!found[i]) {
      ++missing;
      std::cout << "Missing value: " << i << std::endl;
      all_correct = false;
    }
  }
  
  std::cout << "Duration: " << duration.count() << " ms" << std::endl;
  std::cout << "Produced: " << produced.load() << std::endl;
  std::cout << "Consumed: " << consumed.load() << std::endl;
  std::cout << "Duplicates: " << duplicates << std::endl;
  std::cout << "Missing: " << missing << std::endl;
  std::cout << "Queue size at end: " << queue.Size() << std::endl;
  std::cout << "Queue empty at end: " << (queue.Empty() ? "Yes" : "No") << std::endl;
  
  if (all_correct) {
    std::cout << "✓ TEST PASSED" << std::endl;
  } else {
    std::cout << "✗ TEST FAILED" << std::endl;
  }
  
  // Print some statistics
  if (all_correct) {
    std::sort(results.begin(), results.end());
    std::cout << "First 10 values: ";
    for (int i = 0; i < 10; ++i) {
      std::cout << results[i] << " ";
    }
    std::cout << "... " << results[TOTAL_OPS-1] << std::endl;
  }
}

int main() {
  for (int i = 0; i < 10; ++i) {
    // test_thread_safe_queue<ThreadSafeQueue<int, 100>, int>();
    // test_thread_safe_queue<FixedLockFreeQueue<int, 100>, int>();
    // test_thread_safe_queue<LockFreeQueue<int, 100>, int>();
    // test_thread_safe_queue<SpscLockFreeQueueV2<int, 100>, int>();

    // test_queue<ThreadSafeQueue<int, 100>>();
    test_queue<FixedLockFreeQueue<int, 100>>();
    // test_queue<LockFreeQueue<int, 100>>();
    // test_queue<SpscLockFreeQueueV2<int, 100>>();
  }
  return 0;
}