#include <fcntl.h>
#include <sys/event.h>
#include <sys/socket.h>
#include <unistd.h>

#include <algorithm>
#include <cerrno>
#include <cstring>
#include <unordered_map>

#include "ringserver/io/io_backend.hpp"

namespace ringserver {
namespace {
class KqueueBackend final : public IoBackend {
public:
    KqueueBackend(unsigned batch, bool dispatch) : events_(batch), dispatch_(dispatch) {}
    ~KqueueBackend() override {
        if (kqueue_fd_ >= 0) ::close(kqueue_fd_);
    }
    Status Init() override {
        kqueue_fd_ = kqueue();
        if (kqueue_fd_ >= 0) fcntl(kqueue_fd_, F_SETFD, FD_CLOEXEC);
        return kqueue_fd_ < 0 ? Status::Unknown(std::strerror(errno)) : Status::Ok();
    }
    Status SubmitAccept(int fd, int64_t token) override {
        return Register({OpKind::kAccept, fd, token, nullptr, nullptr, 0}, EVFILT_READ);
    }
    Status SubmitRead(int fd, uint8_t* buffer, size_t size, int64_t token) override {
        return Register({OpKind::kRead, fd, token, buffer, nullptr, size}, EVFILT_READ);
    }
    Status SubmitWrite(int fd, const uint8_t* buffer, size_t size, int64_t token) override {
        return Register({OpKind::kWrite, fd, token, nullptr, buffer, size}, EVFILT_WRITE);
    }
    Status SubmitClose(int fd, int64_t) override {
        // A missing read filter must not prevent deleting a still-live write filter.
        // libkqueue requires explicit removal before close, unlike native kernel cleanup.
        int error = 0;
        for (int16_t filter : {EVFILT_READ, EVFILT_WRITE}) {
            struct kevent change;
            EV_SET(&change, fd, filter, EV_DELETE, 0, 0, nullptr);
            int result;
            do {
                result = kevent(kqueue_fd_, &change, 1, nullptr, 0, nullptr);
            } while (result < 0 && errno == EINTR);
            if (result < 0 && errno != ENOENT) error = errno;
        }
        stats.cancelled += pending_.erase(fd);
        registered_filters_.erase(fd);
        return error ? Status::Unknown(std::strerror(error)) : Status::Ok();
    }
    Status Drain() override {
        return pending_.empty() ? Status::Ok() : Status::Unknown("pending operations");
    }
    std::string_view name() const override {
#ifdef RINGSERVER_KQUEUE_COMPAT
        return dispatch_ ? "kqueue-compat-dispatch" : "kqueue-compat";
#else
        return "kqueue";
#endif
    }
    Status Poll(std::vector<CompletionEvent>* out, int timeout_ms) override {
        out->clear();
        ++stats.polls;
        timespec timeout {timeout_ms / 1000, (timeout_ms % 1000) * 1000000L};
        int count = kevent(kqueue_fd_, nullptr, 0, events_.data(), events_.size(),
                           timeout_ms < 0 ? nullptr : &timeout);
        if (count < 0)
            return errno == EINTR ? Status::Again() : Status::Unknown(std::strerror(errno));
        if (!count) ++stats.empty_polls;
        for (int i = 0; i < count; ++i) {
            const auto found = pending_.find(int(events_[i].ident));
            if (found == pending_.end()) continue;
            const Operation operation = found->second;
            int result;
            do {
                if (operation.kind == OpKind::kAccept) {
                    result = accept(operation.fd, nullptr, nullptr);
                    if (result >= 0) {
                        if (fcntl(result, F_SETFL, O_NONBLOCK) < 0 ||
                            fcntl(result, F_SETFD, FD_CLOEXEC) < 0) {
                            const int error = errno;
                            close(result);
                            errno = error;
                            result = -1;
                        }
                    }
                } else if (operation.kind == OpKind::kRead)
                    result = recv(operation.fd, operation.read, operation.size, 0);
                else
                    result = send(operation.fd, operation.write, operation.size, 0);
            } while (result < 0 && errno == EINTR);
            if (result < 0 && (errno == EAGAIN || errno == EWOULDBLOCK)) {
                ++stats.retries;
                auto status = Arm(operation.fd,
                                  operation.kind == OpKind::kWrite ? EVFILT_WRITE : EVFILT_READ);
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
    Status Arm(int fd, int16_t interest) {
        struct kevent event;
        const uint8_t bit = interest == EVFILT_READ ? 1 : 2;
        const auto found = registered_filters_.find(fd);
        const bool exists = found != registered_filters_.end() && (found->second & bit);
        // Bare EV_ENABLE avoids re-declaring a socket filter; libkqueue rejects that modify.
        const uint16_t flags =
                dispatch_ ? (exists ? EV_ENABLE : EV_ADD | EV_DISPATCH) : EV_ADD | EV_ONESHOT;
        EV_SET(&event, fd, interest, flags, 0, 0, nullptr);
        if (kevent(kqueue_fd_, &event, 1, nullptr, 0, nullptr) < 0)
            return Status::Unknown(std::strerror(errno));
        if (dispatch_) registered_filters_[fd] |= bit;
        return Status::Ok();
    }
    Status Register(Operation operation, int16_t interest) {
        if (pending_.contains(operation.fd))
            return Status::InvalidArg("duplicate pending operation");
        auto status = Arm(operation.fd, interest);
        if (!status.ok()) return status;
        pending_.emplace(operation.fd, operation);
        ++stats.submitted;
        stats.max_pending = std::max<uint64_t>(stats.max_pending, pending_.size());
        return Status::Ok();
    }
    int kqueue_fd_ = -1;
    std::vector<struct kevent> events_;
    std::unordered_map<int, Operation> pending_;
    std::unordered_map<int, uint8_t> registered_filters_;
    const bool dispatch_;
};
} // namespace
std::unique_ptr<IoBackend> MakeKqueueBackend(unsigned batch, bool dispatch) {
    return std::make_unique<KqueueBackend>(batch, dispatch);
}
} // namespace ringserver
