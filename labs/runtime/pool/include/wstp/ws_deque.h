#ifndef WSTP_WS_DEQUE_H_
#define WSTP_WS_DEQUE_H_

#include <cstddef>
#include <memory>
#include <mutex>
#include <vector>

#include "wstp/task.h"

namespace wstp {

// A synchronized work-stealing deque: local pops are LIFO, steals are FIFO.
// A mutex protects std::function ownership and permits external producers.
// The ring grows instead of overwriting tasks when its capacity is exhausted.
class WSDeque {
public:
    explicit WSDeque(size_t capacity = 1024);
    ~WSDeque();

    WSDeque(const WSDeque&) = delete;
    WSDeque& operator=(const WSDeque&) = delete;
    WSDeque(WSDeque&&) = delete;
    WSDeque& operator=(WSDeque&&) = delete;

    void PushBottom(Task task);
    Task PopBottom();
    Task StealTop();

    // These methods return synchronized snapshots.
    bool Empty() const;
    size_t Size() const;
    size_t Capacity() const;

private:
    mutable std::mutex mutex_;
    size_t capacity_;
    size_t head_ = 0;
    size_t size_ = 0;
    std::vector<Task> buffer_;
};

using WSDequePtr = std::shared_ptr<WSDeque>;

} // namespace wstp

#endif // WSTP_WS_DEQUE_H_
