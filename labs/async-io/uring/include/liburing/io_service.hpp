#pragma once
#include <liburing.h>

#include <algorithm>
#include <array>
#include <cerrno>
#include <cstdint>
#include <span>
#include <system_error>

#include "liburing/sqe_awaitable.hpp"
#include "liburing/task.hpp"

namespace uio {
class IoService {
public:
    explicit IoService(unsigned entries = 256, unsigned batch = 64)
            : depth_(entries), batch_(batch) {
        if (!batch || batch > 256) throw std::invalid_argument("batch must be 1..256");
        Check(io_uring_queue_init(entries, &ring_, 0));
    }
    ~IoService() { io_uring_queue_exit(&ring_); }
    IoService(const IoService&) = delete;
    IoService& operator=(const IoService&) = delete;
    IoAwaitable Nop() {
        auto* sqe = Next();
        io_uring_prep_nop(sqe);
        return IoAwaitable(sqe);
    }
    IoAwaitable Read(int fd, void* buffer, unsigned size, off_t offset = -1) {
        auto* sqe = Next();
        io_uring_prep_read(sqe, fd, buffer, size, offset);
        return IoAwaitable(sqe);
    }
    IoAwaitable Write(int fd, const void* buffer, unsigned size, off_t offset = -1) {
        auto* sqe = Next();
        io_uring_prep_write(sqe, fd, buffer, size, offset);
        return IoAwaitable(sqe);
    }
    IoAwaitable Timeout(__kernel_timespec* duration) {
        auto* sqe = Next();
        io_uring_prep_timeout(sqe, duration, 0, 0);
        return IoAwaitable(sqe);
    }
    IoAwaitable Cancel(IoAwaitable& operation) {
        auto* sqe = Next();
        io_uring_prep_cancel(sqe, &operation, 0);
        return IoAwaitable(sqe);
    }
    template <typename T>
    T Run(Task<T>& task) {
        task.Start();
        while (!task.done()) Pump();
        return task.Result();
    }
    void RunAll(std::span<Task<>> tasks) {
        // Bound in-flight coroutine operations to SQ capacity, including during startup.
        // Starting an unbounded task list before reaping CQ can overflow even a NODROP ring.
        for (size_t offset = 0; offset < tasks.size(); offset += depth_) {
            auto group = tasks.subspan(offset, std::min<size_t>(depth_, tasks.size() - offset));
            for (auto& task : group) task.Start();
            while (true) {
                bool done = true;
                for (const auto& task : group) done &= task.done();
                if (done) break;
                Pump();
            }
            for (auto& task : group) task.Result();
        }
    }
    uint64_t submissions = 0, completions = 0, waits = 0, queue_full = 0;

private:
    static void Check(int result) {
        if (result < 0) throw std::system_error(-result, std::generic_category());
    }
    void Submit() {
        if (!io_uring_sq_ready(&ring_)) return;
        int result;
        do {
            result = io_uring_submit(&ring_);
        } while (result == -EINTR);
        Check(result);
        ++submissions;
    }
    io_uring_sqe* Next() {
        auto* entry = io_uring_get_sqe(&ring_);
        if (!entry) {
            ++queue_full;
            Submit();
            entry = io_uring_get_sqe(&ring_);
        }
        if (!entry) throw std::runtime_error("submission queue remains full");
        return entry;
    }
    void Pump() {
        Submit();
        io_uring_cqe* completion = nullptr;
        __kernel_timespec deadline {5, 0};
        int result;
        do {
            ++waits;
            result = io_uring_wait_cqe_timeout(&ring_, &completion, &deadline);
        } while (result == -EINTR);
        Check(result);
        std::array<io_uring_cqe*, 256> entries {};
        const unsigned count = io_uring_peek_batch_cqe(&ring_, entries.data(), batch_);
        std::array<std::pair<IoAwaitable*, int>, 256> ready {};
        for (unsigned i = 0; i < count; ++i) {
            ready[i] = {static_cast<IoAwaitable*>(io_uring_cqe_get_data(entries[i])),
                        entries[i]->res};
        }
        // Release the entire batch before any resume; no re-entrant CQ advancement.
        io_uring_cq_advance(&ring_, count);
        completions += count;
        for (unsigned i = 0; i < count; ++i) {
            auto [operation, value] = ready[i];
            if (operation) {
                operation->result = value;
                operation->continuation.resume();
            }
        }
    }
    io_uring ring_ {};
    unsigned depth_, batch_;
};
using io_service = IoService;
} // namespace uio
