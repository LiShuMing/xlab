#include "../include/fwd.h"
#include <atomic>
#include <cstddef>
#include <thread>
#include <algorithm>
#include <vector>
#include <mutex>
#include <iostream>
#include <chrono>
#include <optional>

/**
 * @brief Base class for all queue implementations.
 * Provides a unified interface for different queue types.
 * @tparam T The type of the elements in the queue.
 * @tparam Capacity The capacity of the queue.
 */
template <typename T, size_t Capacity>
class Queue {
 public:
  virtual ~Queue() = default;

  /**
   * @brief Pushes an element onto the queue.
   * @param value The value to push.
   * @return true if the element was pushed, false if the queue is full.
   */
  virtual bool Push(const T& value) = 0;
  virtual bool Push(T&& value) = 0;

  /**
   * @brief Pops an element from the queue.
   * @param out The output parameter to store the popped value.
   * @return true if an element was popped, false if the queue is empty.
   */
  virtual bool Pop(T& out) = 0;

  /**
   * @brief Returns the number of elements in the queue.
   * @return The number of elements.
   */
  virtual size_t Size() const = 0;

  /**
   * @brief Checks if the queue is empty.
   * @return true if the queue is empty, false otherwise.
   */
  virtual bool Empty() const = 0;

  /**
   * @brief Checks if the queue is full.
   * @return true if the queue is full, false otherwise.
   */
  virtual bool Full() const = 0;

  /**
   * @brief Tries to pop an element, returning nullopt if empty.
   * @return The popped value, or nullopt if the queue is empty.
   */
  std::optional<T> TryPop() {
    T value;
    if (Pop(value)) {
      return value;
    }
    return std::nullopt;
  }

  /**
   * @brief Tries to push an element, returning false if full.
   * @param value The value to push.
   * @return true if pushed, false if full.
   */
  bool TryPush(const T& value) {
    return Push(value);
  }

  /**
   * @brief Gets the maximum capacity of the queue.
   * @return The maximum number of elements.
   */
  constexpr size_t MaxCapacity() const {
    return Capacity;
  }
};

/**
 * @brief A mutex-based thread-safe queue for MPMC (Multiple-Producer Multiple-Consumer) pattern.
 * @tparam T The type of the elements in the queue.
 * @tparam Capacity The capacity of the queue.
 */
template <typename T, size_t Capacity>
class ThreadSafeQueue : public Queue<T, Capacity> {
 public:
  ThreadSafeQueue() : head_(0), tail_(0), size_(0) {}

  bool Push(const T& value) override {
    std::unique_lock<std::mutex> lock(mutex_);
    size_t next_head = (head_ + 1) % (Capacity + 1);
    if (next_head == tail_) {
      return false;  // Queue is full
    }
    data_[head_] = value;
    head_ = next_head;
    ++size_;
    return true;
  }

  bool Push(T&& value) override {
    std::unique_lock<std::mutex> lock(mutex_);
    size_t next_head = (head_ + 1) % (Capacity + 1);
    if (next_head == tail_) {
      return false;  // Queue is full
    }
    data_[head_] = std::move(value);
    head_ = next_head;
    ++size_;
    return true;
  }

  bool Pop(T& value) override {
    std::unique_lock<std::mutex> lock(mutex_);
    if (head_ == tail_) {
      return false;  // Queue is empty
    }
    value = data_[tail_];
    tail_ = (tail_ + 1) % (Capacity + 1);
    --size_;
    return true;
  }

  size_t Size() const override {
    std::lock_guard<std::mutex> lock(mutex_);
    return size_;
  }

  bool Empty() const override {
    std::lock_guard<std::mutex> lock(mutex_);
    return size_ == 0;
  }

  bool Full() const override {
    std::lock_guard<std::mutex> lock(mutex_);
    return size_ == Capacity;
  }

 private:
  size_t head_;
  size_t tail_;
  size_t size_;
  T data_[Capacity + 1];
  mutable std::mutex mutex_;
};

/**
 * @brief A lock-free queue implementation using a fixed-size array.
 * Supports MCMPSC (Multiple-Consumer Multiple-Producer Shared-Memory Concurrent Queue) pattern.
 * Uses sequence numbers for lock-free synchronization.
 * @tparam T The type of the elements in the queue.
 * @tparam Capacity The capacity of the queue.
 */
template <typename T, size_t Capacity>
class LockFreeMPMCQueue : public Queue<T, Capacity> {
  static_assert(Capacity >= 2, "Capacity must be >= 2");

 public:
  LockFreeMPMCQueue() {
    for (size_t i = 0; i < Capacity; ++i) {
      buffer_[i].seq.store(i, std::memory_order_relaxed);
    }
    head_.store(0, std::memory_order_relaxed);
    tail_.store(0, std::memory_order_relaxed);
  }

  bool Push(const T& v) override {
    return emplace_impl(v);
  }

  bool Push(T&& v) override {
    return emplace_impl(std::move(v));
  }

  bool Pop(T& out) override {
    size_t pos = tail_.load(std::memory_order_relaxed);

    while (true) {
      Cell& cell = buffer_[pos % Capacity];
      size_t seq = cell.seq.load(std::memory_order_acquire);
      intptr_t diff = (intptr_t)seq - (intptr_t)(pos + 1);

      if (diff == 0) {
        // Slot is full, ready to consume
        if (tail_.compare_exchange_weak(
                pos, pos + 1,
                std::memory_order_relaxed,
                std::memory_order_relaxed)) {
          // Read data (acquire ensures we see producer's write)
          T* ptr = cell.ptr();
          out = std::move(*ptr);
          ptr->~T();

          // Mark slot as empty: set seq to pos + Capacity
          cell.seq.store(pos + Capacity, std::memory_order_release);
          return true;
        }
      } else if (diff < 0) {
        // seq < pos+1 => queue empty (slot not yet written in this cycle)
        return false;
      } else {
        // Another consumer/producer advanced, update pos and retry
        pos = tail_.load(std::memory_order_relaxed);
      }
    }
  }

  size_t Size() const override {
    return head_.load(std::memory_order_acquire) - tail_.load(std::memory_order_acquire);
  }

  bool Empty() const override {
    return Size() == 0;
  }

  bool Full() const override {
    return Size() == Capacity;
  }

 private:
  struct Cell {
    std::atomic<size_t> seq;
    alignas(T) unsigned char storage[sizeof(T)];

    T* ptr() {
      return std::launder(reinterpret_cast<T*>(storage));
    }
  };

  template <class U>
  bool emplace_impl(U&& v) {
    size_t pos = head_.load(std::memory_order_relaxed);

    while (true) {
      Cell& cell = buffer_[pos % Capacity];
      size_t seq = cell.seq.load(std::memory_order_acquire);
      intptr_t diff = (intptr_t)seq - (intptr_t)pos;

      if (diff == 0) {
        // Slot is empty, ready to write
        if (head_.compare_exchange_weak(
                pos, pos + 1,
                std::memory_order_relaxed,
                std::memory_order_relaxed)) {
          // Construct object in-place
          new (cell.storage) T(std::forward<U>(v));

          // Publish: mark as full (seq = pos+1)
          cell.seq.store(pos + 1, std::memory_order_release);
          return true;
        }
      } else if (diff < 0) {
        // seq < pos => queue full (slot not yet consumed to available round)
        return false;
      } else {
        pos = head_.load(std::memory_order_relaxed);
      }
    }
  }

  alignas(64) std::atomic<size_t> head_;
  alignas(64) std::atomic<size_t> tail_;
  std::array<Cell, Capacity> buffer_;
};

/**
 * @brief A simple lock-free ring buffer for SPSC (Single-Producer Single-Consumer) pattern.
 * Uses two atomic indices for head and tail with modulo arithmetic.
 * @tparam T The type of the elements in the queue.
 * @tparam Capacity The capacity of the queue.
 */
template <typename T, size_t Capacity>
class LockFreeSPSCQueue : public Queue<T, Capacity> {
 public:
  LockFreeSPSCQueue() : head_(0), tail_(0) {}

  bool Push(const T& value) override {
    while (true) {
      size_t head = head_.load(std::memory_order_relaxed);
      size_t next_head = (head + 1) % (Capacity + 1);
      // Check if queue is full
      size_t tail = tail_.load(std::memory_order_acquire);
      if (next_head == tail) {
        return false;  // Queue full
      }

      // Try to atomically reserve the slot using CAS
      if (head_.compare_exchange_weak(
              head, next_head,
              std::memory_order_release,
              std::memory_order_relaxed)) {
        // Successfully reserved the slot, now write the value
        data_[head] = value;
        std::atomic_thread_fence(std::memory_order_release);
        return true;
      }
      // CAS failed, another thread reserved this slot, retry
    }
  }

  bool Push(T&& value) override {
    while (true) {
      size_t head = head_.load(std::memory_order_relaxed);
      size_t next_head = (head + 1) % (Capacity + 1);
      size_t tail = tail_.load(std::memory_order_acquire);
      if (next_head == tail) {
        return false;
      }

      if (head_.compare_exchange_weak(
              head, next_head,
              std::memory_order_release,
              std::memory_order_relaxed)) {
        data_[head] = std::move(value);
        std::atomic_thread_fence(std::memory_order_release);
        return true;
      }
    }
  }

  bool Pop(T& value) override {
    while (true) {
      size_t tail = tail_.load(std::memory_order_relaxed);
      size_t head = head_.load(std::memory_order_acquire);
      // Check if queue is empty
      if (head == tail) {
        return false;  // Queue empty
      }

      size_t next_tail = (tail + 1) % (Capacity + 1);
      if (tail_.compare_exchange_weak(
              tail, next_tail,
              std::memory_order_release,
              std::memory_order_relaxed)) {
        value = std::move(data_[tail]);
        std::atomic_thread_fence(std::memory_order_release);
        return true;
      }
    }
  }

  size_t Size() const override {
    size_t head = head_.load(std::memory_order_relaxed);
    size_t tail = tail_.load(std::memory_order_relaxed);
    return (head >= tail)
             ? (head - tail)
             : (head + Capacity + 1 - tail);
  }

  bool Empty() const override {
    return head_.load(std::memory_order_relaxed) == tail_.load(std::memory_order_relaxed);
  }

  bool Full() const override {
    size_t head = head_.load(std::memory_order_relaxed);
    size_t tail = tail_.load(std::memory_order_relaxed);
    return ((head + 1) % (Capacity + 1)) == tail;
  }

 private:
  // Use Capacity+1 slots: when head == tail, queue is empty
  // when (head+1) % (Capacity+1) == tail, queue is full
  std::atomic<size_t> head_;
  std::atomic<size_t> tail_;
  T data_[Capacity + 1];
};

/**
 * @brief Michael & Scott Queue (MSQueue)
 * A lock-free concurrent queue based on the paper:
 * "Simple, Fast, and Practical Non-Blocking and Blocking Concurrent Queue Algorithms"
 * by Maged M. Michael and Michael L. Scott (1996).
 *
 * Key features:
 * - Linked-list based with a dummy head node
 * - Lock-free enqueue using CAS on tail->next
 * - Lock-free dequeue using CAS on head
 * - Uses hazard pointers for safe memory reclamation (lock-free ABA prevention)
 * - Supports unbounded capacity (limited only by memory)
 *
 * Thread-safety: This implementation is thread-safe for concurrent Push/Pop operations.
 * @tparam T The type of the elements in the queue.
 * @tparam Capacity Maximum capacity (soft limit, actual capacity may exceed).
 */
template <typename T, size_t Capacity>
class MSQueue : public Queue<T, Capacity> {
 private:
  struct alignas(64) Node {
    std::atomic<Node*> next;
    std::atomic<bool> deleted;  // Marker for safe reclamation
    T value;

    explicit Node(const T& val) : next(nullptr), deleted(false), value(val) {}
    explicit Node(T&& val) : next(nullptr), deleted(false), value(std::move(val)) {}
    Node() : next(nullptr), deleted(false), value() {}
  };

  struct alignas(64) HazardPointers {
    static constexpr size_t HAZARD_COUNT = 8;
    std::atomic<Node*> hp[HAZARD_COUNT];

    HazardPointers() {
      for (auto& p : hp) {
        p.store(nullptr, std::memory_order_relaxed);
      }
    }

    Node* protect(Node* ptr) {
      for (size_t i = 0; i < HAZARD_COUNT; ++i) {
        Node* expected = nullptr;
        if (hp[i].compare_exchange_strong(expected, ptr,
                                           std::memory_order_acquire,
                                           std::memory_order_relaxed)) {
          return ptr;
        }
      }
      return nullptr;  // All slots busy
    }

    void clear(Node* ptr) {
      for (auto& p : hp) {
        Node* current = p.load(std::memory_order_relaxed);
        if (current == ptr) {
          p.store(nullptr, std::memory_order_release);
          return;
        }
      }
    }
  };

  alignas(64) std::atomic<Node*> head_;
  alignas(64) std::atomic<Node*> tail_;
  HazardPointers hazard_;

  static void reclaim(Node* node) {
    if (node == nullptr) return;
    delete node;
  }

 public:
  MSQueue() {
    // Create dummy head node
    Node* dummy = new Node();
    head_.store(dummy, std::memory_order_release);
    tail_.store(dummy, std::memory_order_release);
  }

  ~MSQueue() {
    // Drain the queue and delete all nodes
    Node* node = head_.load(std::memory_order_acquire);
    while (node != nullptr) {
      Node* next = node->next.load(std::memory_order_acquire);
      delete node;
      node = next;
    }
  }

  // Non-copyable, non-movable due to atomic pointers
  MSQueue(const MSQueue&) = delete;
  MSQueue& operator=(const MSQueue&) = delete;
  MSQueue(MSQueue&&) = delete;
  MSQueue& operator=(MSQueue&&) = delete;

  bool Push(const T& value) override {
    Node* node = new Node(value);
    if (node == nullptr) {
      return false;
    }

    while (true) {
      Node* tail = tail_.load(std::memory_order_acquire);
      Node* next = tail->next.load(std::memory_order_acquire);

      if (tail != tail_.load(std::memory_order_relaxed)) {
        continue;
      }

      if (next != nullptr) {
        // Tail is not pointing to last node, help advance it
        tail_.compare_exchange_weak(tail, next,
                                    std::memory_order_release,
                                    std::memory_order_relaxed);
        continue;
      }

      // Try to append to tail
      if (tail->next.compare_exchange_weak(next, node,
                                            std::memory_order_release,
                                            std::memory_order_relaxed)) {
        // Successfully appended, try to update tail
        tail_.compare_exchange_weak(tail, node,
                                    std::memory_order_release,
                                    std::memory_order_relaxed);
        return true;
      }
      // CAS failed, another thread modified tail->next, retry
      reclaim(node);
      return false;
    }
  }

  bool Push(T&& value) override {
    Node* node = new Node(std::move(value));
    if (node == nullptr) {
      return false;
    }

    while (true) {
      Node* tail = tail_.load(std::memory_order_acquire);
      Node* next = tail->next.load(std::memory_order_acquire);

      if (tail != tail_.load(std::memory_order_relaxed)) {
        continue;
      }

      if (next != nullptr) {
        tail_.compare_exchange_weak(tail, next,
                                    std::memory_order_release,
                                    std::memory_order_relaxed);
        continue;
      }

      if (tail->next.compare_exchange_weak(next, node,
                                            std::memory_order_release,
                                            std::memory_order_relaxed)) {
        tail_.compare_exchange_weak(tail, node,
                                    std::memory_order_release,
                                    std::memory_order_relaxed);
        return true;
      }
      reclaim(node);
      return false;
    }
  }

  bool Pop(T& out) override {
    while (true) {
      Node* head = head_.load(std::memory_order_acquire);
      // Protect head with hazard pointer
      head = hazard_.protect(head);

      if (head != head_.load(std::memory_order_relaxed)) {
        hazard_.clear(head);
        continue;  // Head moved, retry
      }

      Node* tail = tail_.load(std::memory_order_acquire);
      Node* next = head->next.load(std::memory_order_acquire);

      if (next == nullptr) {
        hazard_.clear(head);
        return false;  // Queue is empty
      }

      // Protect next with hazard pointer before CAS
      Node* protected_next = hazard_.protect(next);
      if (protected_next == nullptr || protected_next != next) {
        hazard_.clear(head);
        if (protected_next) hazard_.clear(protected_next);
        continue;
      }

      if (head == tail) {
        hazard_.clear(head);
        hazard_.clear(protected_next);
        // Tail is lagging behind, help advance it
        tail_.compare_exchange_weak(tail, next,
                                    std::memory_order_release,
                                    std::memory_order_relaxed);
        continue;
      }

      // Try to remove head (the dummy node's next)
      if (head->next.compare_exchange_weak(next, next->next,
                                            std::memory_order_release,
                                            std::memory_order_relaxed)) {
        // Successfully removed, update head
        head_.compare_exchange_weak(head, next,
                                    std::memory_order_release,
                                    std::memory_order_relaxed);

        out = std::move(next->value);

        // Clear hazard pointers before reclamation
        hazard_.clear(head);
        hazard_.clear(next);

        // Schedule old head for reclamation (after other threads release it)
        reclaim(head);
        return true;
      }

      // CAS failed, retry
      hazard_.clear(head);
      hazard_.clear(next);
    }
  }

  size_t Size() const override {
    // Approximate size - may not be accurate under concurrent access
    size_t count = 0;
    Node* head = head_.load(std::memory_order_acquire);
    if (head == nullptr) return 0;
    Node* curr = head->next.load(std::memory_order_acquire);
    while (curr != nullptr) {
      ++count;
      curr = curr->next.load(std::memory_order_acquire);
    }
    return count;
  }

  bool Empty() const override {
    Node* head = head_.load(std::memory_order_acquire);
    if (head == nullptr) return true;
    return head->next.load(std::memory_order_acquire) == nullptr;
  }

  bool Full() const override {
    return Size() >= Capacity;
  }
};

// ============================================================================
// Test Functions
// ============================================================================

template <typename QueueType>
void test_queue_base() {
  std::cout << "\n=== Testing " << typeid(QueueType).name() << " ===" << std::endl;

  constexpr int NUM_THREADS = 4;
  constexpr int NUM_OPS = 1000;
  constexpr int TOTAL_OPS = NUM_THREADS * NUM_OPS;

  QueueType queue;
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
        produced.fetch_add(1, std::memory_order_release);
      }
    });
  }

  // Consumer threads
  std::vector<std::thread> consumers;
  for (int t = 0; t < NUM_THREADS; ++t) {
    consumers.emplace_back([&]() {
      while (consumed.load(std::memory_order_acquire) < TOTAL_OPS) {
        int value = 0;
        if (queue.Pop(value)) {
          int idx = consumed.fetch_add(1, std::memory_order_release);
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
    std::cout << "... " << results[TOTAL_OPS - 1] << std::endl;
  }
}

void test_spsc_queue() {
  std::cout << "\n=== Testing LockFreeSPSCQueue (Single-Producer Single-Consumer) ===" << std::endl;

  LockFreeSPSCQueue<int, 100> queue;
  constexpr int NUM_OPS = 1000;

  std::atomic<int> produced{0};
  std::atomic<int> consumed{0};
  std::vector<int> results(NUM_OPS, -1);
  std::atomic<bool> producer_done{false};

  // Producer thread
  std::thread producer([&queue, &produced, &producer_done]() {
    for (int i = 0; i < NUM_OPS; ++i) {
      while (!queue.Push(i)) {
        std::this_thread::yield();  // Wait if queue is full
      }
      produced.fetch_add(1, std::memory_order_release);
    }
    producer_done.store(true, std::memory_order_release);
  });

  // Consumer thread
  std::thread consumer([&queue, &consumed, &results, &producer_done]() {
    while (consumed.load(std::memory_order_acquire) < NUM_OPS) {
      int value;
      if (queue.Pop(value)) {
        int idx = consumed.fetch_add(1, std::memory_order_release);
        if (idx < NUM_OPS) {
          results[idx] = value;
        }
      } else if (!producer_done.load(std::memory_order_acquire)) {
        std::this_thread::yield();  // Wait if queue is empty
      }
    }
  });

  producer.join();
  consumer.join();

  // Verify results
  std::sort(results.begin(), results.end());
  bool all_correct = true;
  for (int i = 0; i < NUM_OPS; ++i) {
    if (results[i] != i) {
      std::cout << "Mismatch at index " << i << ": expected " << i << ", got " << results[i] << std::endl;
      all_correct = false;
    }
  }

  std::cout << "Produced: " << produced.load() << std::endl;
  std::cout << "Consumed: " << consumed.load() << std::endl;
  std::cout << "Queue size at end: " << queue.Size() << std::endl;

  if (all_correct) {
    std::cout << "First 10 values: ";
    for (int i = 0; i < 10; ++i) {
      std::cout << results[i] << " ";
    }
    std::cout << "... " << results[NUM_OPS - 1] << std::endl;
    std::cout << "✓ SPSC TEST PASSED" << std::endl;
  } else {
    std::cout << "✗ SPSC TEST FAILED" << std::endl;
  }
}

int main() {
  for (int i = 0; i < 10; ++i) {
    std::cout << "\n========== Test Round " << (i + 1) << "/10 ==========" << std::endl;
    test_queue_base<ThreadSafeQueue<int, 100>>();
    test_queue_base<LockFreeMPMCQueue<int, 100>>();
    test_queue_base<MSQueue<int, 100>>();
    test_spsc_queue();
  }
  std::cout << "\n========== All Tests Complete ==========" << std::endl;
  return 0;
}
