#ifndef WSTP_WS_DEQUE_H_
#define WSTP_WS_DEQUE_H_

#include <atomic>
#include <cstddef>
#include <memory>
#include <vector>

#include "wstp/cache_padding.h"
#include "wstp/task.h"

namespace wstp {

/**
 * Work-Stealing Deque (Chase-Lev style)
 *
 * A lock-free double-ended queue where:
 * - Owner thread: push_bottom() and pop_bottom() (LIFO order, efficient)
 * - Thief threads: steal_top() (FIFO order, steals from opposite end)
 *
 * Memory ordering rationale:
 * - push_bottom: release semantics ensures task is visible before bottom index
 * - pop_bottom: acquire semantics ensures we see consistent top/bottom
 * - steal_top: acquire on read, release on CAS for synchronization
 *
 * Invariants:
 * - top >= 0, bottom >= top
 * - Size = bottom - top
 * - Empty when bottom == top
 * - Single element race: when size == 1, owner pop and thief steal may race
 */
class WSDeque {
 public:
  explicit WSDeque(size_t capacity = 1024);
  ~WSDeque();

  // Non-copyable, non-movable (deques are tied to specific threads)
  WSDeque(const WSDeque&) = delete;
  WSDeque& operator=(const WSDeque&) = delete;
  WSDeque(WSDeque&&) = delete;
  WSDeque& operator=(WSDeque&&) = delete;

  /**
   * Push a task to the bottom (owner thread only)
   * Memory order: release - makes task visible to other threads
   */
  void PushBottom(Task task);

  /**
   * Pop a task from the bottom (owner thread only)
   * Returns nullptr if empty
   * Memory order: acquire - sees consistent state
   */
  Task PopBottom();

  /**
   * Steal a task from the top (thief threads)
   * Returns nullptr if empty
   * Memory order: acquire on read, release on CAS
   */
  Task StealTop();

  /**
   * Check if deque is empty (for debugging/testing)
   * Not thread-safe, caller must synchronize
   */
  bool Empty() const;

  /**
   * Get current size (for debugging/testing)
   * Not thread-safe, caller must synchronize
   */
  size_t Size() const;

  /**
   * Get capacity (for debugging/testing)
   */
  size_t Capacity() const;

 private:
  // Helper to compute index in circular buffer
  static size_t Index(size_t pos, size_t capacity) { return pos & (capacity - 1); }

  // Buffer capacity (power of 2 for efficient modulo)
  size_t capacity_;

  // Aligned to cache line to avoid false sharing
  // bottom: owner-only write, thieves read with acquire
  WSTP_CACHELINE_ALIGN std::atomic<size_t> bottom_{0};

  // top: thieves write via CAS, owner reads with acquire
  WSTP_CACHELINE_ALIGN std::atomic<size_t> top_{0};

  // Ring buffer of tasks
  std::vector<Task> buffer_;
};

// Shared pointer for moving deques between workers
using WSDequePtr = std::shared_ptr<WSDeque>;

}  // namespace wstp

#endif  // WSTP_WS_DEQUE_H_
