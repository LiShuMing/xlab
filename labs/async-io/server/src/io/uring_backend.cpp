#include <liburing.h>
#include <poll.h>
#include <sys/socket.h>
#include <unistd.h>

#include <algorithm>
#include <array>
#include <cerrno>
#include <chrono>
#include <cstring>
#include <unordered_map>

#include "ringserver/io/io_backend.hpp"

namespace ringserver {
namespace {
class UringBackend final : public IoBackend {
public:
    UringBackend(unsigned depth, unsigned batch) : depth_(depth), cqes_(batch) {}
    ~UringBackend() override {
        if (initialized_) {
            // Buffer memory cannot be freed until every target and cancellation CQE is consumed.
            if (outstanding_) std::terminate();
            io_uring_queue_exit(&ring_);
        }
    }
    Status Init() override {
        int result = io_uring_queue_init(depth_, &ring_, 0);
        if (result < 0) return Status::Unknown(std::strerror(-result));
        initialized_ = true;
        auto* probe = io_uring_get_probe_ring(&ring_);
        if (!probe) return Status::Unknown("opcode probe failed");
        bool supported = true;
        for (int op : {IORING_OP_ACCEPT, IORING_OP_RECV, IORING_OP_SEND, IORING_OP_ASYNC_CANCEL})
            supported &= io_uring_opcode_supported(probe, op);
        io_uring_free_probe(probe);
        return supported ? Status::Ok() : Status::Unknown("required opcode unavailable");
    }
    std::string_view name() const override { return "uring"; }
    Status SubmitAccept(int fd, int64_t token) override {
        return Add(OpKind::kAccept, fd, nullptr, nullptr, 0, token);
    }
    Status SubmitRead(int fd, uint8_t* buf, size_t cap, int64_t token) override {
        return Add(OpKind::kRead, fd, buf, nullptr, cap, token);
    }
    Status SubmitWrite(int fd, const uint8_t* buf, size_t len, int64_t token) override {
        return Add(OpKind::kWrite, fd, nullptr, buf, len, token);
    }
    Status SubmitClose(int fd, int64_t token) override {
        for (auto& [id, operation] : pending_) {
            if (operation->fd != fd || operation->token != token || operation->closed) continue;
            operation->closed = true;
            operation->destination = nullptr;
            auto* entry = Next();
            if (!entry) return Status::Unknown("cannot submit cancellation");
            io_uring_prep_cancel64(entry, id, 0);
            io_uring_sqe_set_data64(entry, 0); // Cancellation acknowledgement has no user buffer.
            ++outstanding_;
            ++stats.cancelled;
        }
        return Status::Ok();
    }
    Status Poll(std::vector<CompletionEvent>* out, int timeout_ms) override {
        out->clear();
        ++stats.polls;
        auto status = Submit();
        if (!status.ok()) return status;
        unsigned count = io_uring_peek_batch_cqe(&ring_, cqes_.data(), cqes_.size());
        if (!count) {
            pollfd descriptor {ring_.ring_fd, POLLIN, 0};
            int result = ::poll(&descriptor, 1, timeout_ms);
            if (result < 0)
                return errno == EINTR ? Status::Again() : Status::Unknown(std::strerror(errno));
            count = io_uring_peek_batch_cqe(&ring_, cqes_.data(), cqes_.size());
        }
        if (!count) ++stats.empty_polls;
        for (unsigned i = 0; i < count; ++i) {
            auto* completion = cqes_[i];
            --outstanding_;
            const uint64_t id = io_uring_cqe_get_data64(completion);
            if (!id) continue;
            const auto found = pending_.find(id);
            if (found == pending_.end()) return Status::Unknown("unknown completion token");
            auto& operation = *found->second;
            const int result = completion->res;
            ++stats.completed;
            if (!operation.closed) {
                if (operation.kind == OpKind::kRead && result > 0)
                    std::memcpy(operation.destination, operation.storage.data(), result);
                if (operation.kind == OpKind::kRead && result > 0) stats.copied_bytes += result;
                out->push_back({operation.kind, operation.fd, operation.token, result});
            } else if (operation.kind == OpKind::kAccept && result >= 0) {
                ::close(result); // An accept may win the race with cancellation.
            }
            free_.push_back(std::move(found->second));
            pending_.erase(found);
        }
        io_uring_cq_advance(&ring_, count);
        return Status::Ok();
    }
    Status Drain() override {
        const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(5);
        std::vector<CompletionEvent> discarded;
        while (outstanding_) {
            auto status = Poll(&discarded, 20);
            if (!status.ok() && !status.IsAgain()) return status;
            if (std::chrono::steady_clock::now() > deadline)
                return Status::Unknown("cancellation drain deadline exceeded");
        }
        return Status::Ok();
    }

private:
    struct Operation {
        OpKind kind;
        int fd;
        int64_t token;
        uint8_t* destination;
        std::array<uint8_t, 16384> storage;
        bool closed = false;
    };
    Status Submit() {
        if (!io_uring_sq_ready(&ring_)) return Status::Ok();
        int result;
        do {
            result = io_uring_submit(&ring_);
        } while (result == -EINTR);
        ++stats.submit_calls;
        return result < 0 ? Status::Unknown(std::strerror(-result)) : Status::Ok();
    }
    io_uring_sqe* Next() {
        auto* entry = io_uring_get_sqe(&ring_);
        if (!entry) {
            ++stats.queue_full;
            if (!Submit().ok()) return nullptr;
            entry = io_uring_get_sqe(&ring_);
        }
        return entry;
    }
    Status Add(OpKind kind, int fd, uint8_t* read, const uint8_t* write, size_t size,
               int64_t token) {
        if (kind != OpKind::kAccept && pending_.size() >= depth_ - 1)
            return Status::Again("bounded operation capacity reached");
        if (size > 16384) return Status::InvalidArg("operation buffer limit exceeded");
        std::unique_ptr<Operation> operation;
        if (free_.empty()) {
            operation = std::make_unique<Operation>();
            ++stats.operation_allocations;
        } else {
            operation = std::move(free_.back());
            free_.pop_back();
        }
        operation->kind = kind;
        operation->fd = fd;
        operation->token = token;
        operation->destination = read;
        operation->closed = false;
        if (write) {
            std::memcpy(operation->storage.data(), write, size);
            stats.copied_bytes += size;
        }
        auto* entry = Next();
        if (!entry) return Status::Again("SQ full");
        if (kind == OpKind::kAccept)
            io_uring_prep_accept(entry, fd, nullptr, nullptr, SOCK_NONBLOCK | SOCK_CLOEXEC);
        else if (kind == OpKind::kRead)
            io_uring_prep_recv(entry, fd, operation->storage.data(), size, 0);
        else
            io_uring_prep_send(entry, fd, operation->storage.data(), size, MSG_NOSIGNAL);
        const uint64_t id = next_id_++;
        io_uring_sqe_set_data64(entry, id);
        pending_.emplace(id, std::move(operation));
        ++outstanding_;
        ++stats.submitted;
        stats.max_pending = std::max<uint64_t>(stats.max_pending, pending_.size());
        return Status::Ok();
    }
    io_uring ring_ {};
    unsigned depth_;
    std::vector<io_uring_cqe*> cqes_;
    bool initialized_ = false;
    uint64_t next_id_ = 1, outstanding_ = 0;
    std::unordered_map<uint64_t, std::unique_ptr<Operation>> pending_;
    std::vector<std::unique_ptr<Operation>> free_;
};
} // namespace
std::unique_ptr<IoBackend> MakeUringBackend(unsigned depth, unsigned batch) {
    return std::make_unique<UringBackend>(depth, batch);
}
} // namespace ringserver
