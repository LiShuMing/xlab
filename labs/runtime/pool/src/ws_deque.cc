#include "wstp/ws_deque.h"

#include <limits>
#include <stdexcept>
#include <utility>

namespace wstp {

WSDeque::WSDeque(size_t capacity) : capacity_(capacity) {
    if (capacity == 0 || (capacity & (capacity - 1)) != 0) {
        throw std::invalid_argument("deque capacity must be a nonzero power of 2");
    }
    buffer_.resize(capacity);
}

WSDeque::~WSDeque() = default;

void WSDeque::PushBottom(Task task) {
    std::lock_guard lock(mutex_);
    if (size_ == capacity_) {
        if (capacity_ > std::numeric_limits<size_t>::max() / 2) {
            throw std::length_error("deque capacity overflow");
        }
        std::vector<Task> grown(capacity_ * 2);
        for (size_t i = 0; i < size_; ++i) {
            grown[i] = std::move(buffer_[(head_ + i) & (capacity_ - 1)]);
        }
        buffer_ = std::move(grown);
        capacity_ *= 2;
        head_ = 0;
    }
    buffer_[(head_ + size_) & (capacity_ - 1)] = std::move(task);
    ++size_;
}

Task WSDeque::PopBottom() {
    std::lock_guard lock(mutex_);
    if (size_ == 0) {
        return nullptr;
    }
    --size_;
    return std::move(buffer_[(head_ + size_) & (capacity_ - 1)]);
}

Task WSDeque::StealTop() {
    std::lock_guard lock(mutex_);
    if (size_ == 0) {
        return nullptr;
    }
    Task task = std::move(buffer_[head_]);
    head_ = (head_ + 1) & (capacity_ - 1);
    --size_;
    return task;
}

bool WSDeque::Empty() const {
    std::lock_guard lock(mutex_);
    return size_ == 0;
}

size_t WSDeque::Size() const {
    std::lock_guard lock(mutex_);
    return size_;
}

size_t WSDeque::Capacity() const {
    std::lock_guard lock(mutex_);
    return capacity_;
}

} // namespace wstp
