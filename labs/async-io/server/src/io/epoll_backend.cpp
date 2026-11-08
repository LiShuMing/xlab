#include <sys/epoll.h>
#include <sys/socket.h>
#include <unistd.h>

#include <algorithm>
#include <cerrno>
#include <cstring>
#include <unordered_map>
#include <unordered_set>

#include "ringserver/io/io_backend.hpp"

namespace ringserver {
namespace {
class EpollBackend final : public IoBackend {
public:
    EpollBackend(unsigned batch, bool recreate) : events_(batch), recreate_(recreate) {}
    ~EpollBackend() override {
        if (epoll_fd_ >= 0) ::close(epoll_fd_);
    }
    Status Init() override {
        epoll_fd_ = epoll_create1(EPOLL_CLOEXEC);
        return epoll_fd_ < 0 ? Status::Unknown(std::strerror(errno)) : Status::Ok();
    }
    Status SubmitAccept(int fd, int64_t token) override {
        return Register({OpKind::kAccept, fd, token, nullptr, nullptr, 0}, EPOLLIN);
    }
    Status SubmitRead(int fd, uint8_t* buffer, size_t size, int64_t token) override {
        return Register({OpKind::kRead, fd, token, buffer, nullptr, size}, EPOLLIN);
    }
    Status SubmitWrite(int fd, const uint8_t* buffer, size_t size, int64_t token) override {
        return Register({OpKind::kWrite, fd, token, nullptr, buffer, size}, EPOLLOUT);
    }
    Status SubmitClose(int fd, int64_t) override {
        epoll_ctl(epoll_fd_, EPOLL_CTL_DEL, fd, nullptr);
        registered_.erase(fd);
        stats.cancelled += pending_.erase(fd);
        return Status::Ok();
    }
    Status Drain() override {
        return pending_.empty() ? Status::Ok() : Status::Unknown("pending operations");
    }
    std::string_view name() const override { return recreate_ ? "epoll-recreate" : "epoll"; }
    Status Poll(std::vector<CompletionEvent>* out, int timeout_ms) override {
        out->clear();
        ++stats.polls;
        int count = epoll_wait(epoll_fd_, events_.data(), events_.size(), timeout_ms);
        if (count < 0)
            return errno == EINTR ? Status::Again() : Status::Unknown(std::strerror(errno));
        if (!count) ++stats.empty_polls;
        for (int i = 0; i < count; ++i) {
            const auto found = pending_.find(events_[i].data.fd);
            if (found == pending_.end()) continue;
            const Operation operation = found->second;
            // Match libkqueue's Linux disable/delete path before delivering readiness.
            if (recreate_) {
                if (epoll_ctl(epoll_fd_, EPOLL_CTL_DEL, operation.fd, nullptr) < 0)
                    return Status::Unknown(std::strerror(errno));
            }
            int result;
            do {
                if (operation.kind == OpKind::kAccept)
                    result = accept4(operation.fd, nullptr, nullptr, SOCK_NONBLOCK | SOCK_CLOEXEC);
                else if (operation.kind == OpKind::kRead)
                    result = recv(operation.fd, operation.read, operation.size, 0);
                else
                    result = send(operation.fd, operation.write, operation.size, MSG_NOSIGNAL);
            } while (result < 0 && errno == EINTR);
            if (result < 0 && (errno == EAGAIN || errno == EWOULDBLOCK)) {
                ++stats.retries;
                auto status =
                        Arm(operation.fd, operation.kind == OpKind::kWrite ? EPOLLOUT : EPOLLIN);
                if (!status.ok()) return status;
                continue;
            }
            out->push_back(
                    {operation.kind, operation.fd, operation.token, result < 0 ? -errno : result});
            pending_.erase(found);
            ++stats.completed;
        }
        return Status::Ok();
    }

private:
    struct Operation {
        OpKind kind;
        int fd;
        int64_t token;
        uint8_t* read;
        const uint8_t* write;
        size_t size;
    };
    Status Arm(int fd, uint32_t interest) {
        epoll_event event {};
        event.events = interest | EPOLLONESHOT;
        event.data.fd = fd;
        // Keep the same user-space index in both arms: vary kernel registration only.
        const int command = !recreate_ && registered_.contains(fd) ? EPOLL_CTL_MOD : EPOLL_CTL_ADD;
        if (epoll_ctl(epoll_fd_, command, fd, &event) < 0)
            return Status::Unknown(std::strerror(errno));
        registered_.insert(fd);
        return Status::Ok();
    }
    Status Register(Operation operation, uint32_t interest) {
        if (pending_.contains(operation.fd))
            return Status::InvalidArg("duplicate pending operation");
        auto status = Arm(operation.fd, interest);
        if (!status.ok()) return status;
        pending_.emplace(operation.fd, operation);
        ++stats.submitted;
        stats.max_pending = std::max<uint64_t>(stats.max_pending, pending_.size());
        return Status::Ok();
    }
    int epoll_fd_ = -1;
    std::vector<epoll_event> events_;
    std::unordered_set<int> registered_;
    std::unordered_map<int, Operation> pending_;
    const bool recreate_;
};
} // namespace
std::unique_ptr<IoBackend> MakeEpollBackend(unsigned batch, bool recreate) {
    return std::make_unique<EpollBackend>(batch, recreate);
}
} // namespace ringserver
