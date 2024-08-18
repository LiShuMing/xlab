#include "wstp/ws_deque.h"

#include <algorithm>
#include <cassert>
#include <stdexcept>

namespace wstp {

WSDeque::WSDeque(size_t capacity) : capacity_(capacity), buffer_(capacity) {
  // Ensure capacity is power of 2 for efficient modulo
  if ((capacity & (capacity - 1)) != 0) {
    throw std::invalid_argument("deque capacity must be power of 2");
  }
}

WSDeque::~WSDeque() = default;

void WSDeque::PushBottom(Task task) {
  // Read bottom with relaxed order (owner-only access)
  size_t b = bottom_.load(std::memory_order_relaxed);
  size_t t = top_.load(std::memory_order_acquire);

  // Check if we need to resize
  // For fixed capacity: we assume capacity is sufficient
  // Phase 3: implement dynamic resize if needed

  // Store task in buffer
  buffer_[Index(b, capacity_)] = std::move(task);

  // Release semantics: ensures task is visible before updating bottom
  // This prevents a thief from seeing bottom > b but stale task data
  bottom_.store(b + 1, std::memory_order_release);
}

Task WSDeque::PopBottom() {
  // Read both indices with acquire semantics
  // This pairs with release stores to ensure consistent view
  size_t b = bottom_.load(std::memory_order_acquire) - 1;
  size_t t = top_.load(std::memory_order_acquire);

  // Re-read after potential modification
  bottom_.store(b, std::memory_order_release);

  std::atomic_thread_fence(std::memory_order_acquire);

  if (t <= b) {
    // Non-empty case
    Task task = std::move(buffer_[Index(b, capacity_)]);

    if (t < b) {
      // More than one element, done
      bottom_.store(b, std::memory_order_release);
      return task;
    }

    // Single element case: owner and thief may race
    // Try to CAS top from t to t+1
    // If successful, we got the task
    // If failed, thief stole it
    bool cas_success = top_.compare_exchange_strong(
        t, t + 1, std::memory_order_acq_rel, std::memory_order_acquire);

    bottom_.store(t + 1, std::memory_order_release);

    return cas_success ? std::move(task) : nullptr;
  }

  // Empty - restore bottom
  bottom_.store(b + 1, std::memory_order_release);
  return nullptr;
}

Task WSDeque::StealTop() {
  // Acquire semantics: see consistent state of top/bottom
  size_t t = top_.load(std::memory_order_acquire);
  std::atomic_thread_fence(std::memory_order_acquire);
  size_t b = bottom_.load(std::memory_order_acquire);

  if (t >= b) {
    // Empty
    return nullptr;
  }

  // Read task before CAS (acquire ensures we see the data)
  Task task = std::move(buffer_[Index(t, capacity_)]);

  // Try to CAS top from t to t+1
  // Memory order:
  // - success: acq_rel - synchronizes with other acquire operations
  // - failure: acquire - we lost the race, need to see updated state
  bool cas_success = top_.compare_exchange_strong(
      t, t + 1, std::memory_order_acq_rel, std::memory_order_acquire);

  if (!cas_success) {
    // CAS failed - another thief stole this task
    // Return nullptr (caller will try another victim)
    return nullptr;
  }

  return task;
}

bool WSDeque::Empty() const {
  return top_.load(std::memory_order_acquire) >=
         bottom_.load(std::memory_order_acquire);
}

size_t WSDeque::Size() const {
  return bottom_.load(std::memory_order_acquire) -
         top_.load(std::memory_order_acquire);
}

size_t WSDeque::Capacity() const { return capacity_; }

}  // namespace wstp
