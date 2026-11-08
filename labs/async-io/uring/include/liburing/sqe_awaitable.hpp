#pragma once
#include <liburing.h>

#include <coroutine>

namespace uio {
struct IoAwaitable {
    explicit IoAwaitable(io_uring_sqe* entry) : entry(entry) {}
    IoAwaitable(const IoAwaitable&) = delete;
    bool await_ready() const noexcept { return false; }
    void await_suspend(std::coroutine_handle<> caller) noexcept {
        continuation = caller;
        io_uring_sqe_set_data(entry, this);
    }
    int await_resume() const noexcept { return result; }
    io_uring_sqe* entry;
    std::coroutine_handle<> continuation;
    int result = 0;
};
using sqe_awaitable = IoAwaitable;
} // namespace uio
