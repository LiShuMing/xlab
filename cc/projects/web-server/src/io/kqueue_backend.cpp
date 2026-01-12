#include "ringserver/io/kqueue_backend.hpp"

#include <cerrno>
#include <cstring>
#include <iostream>
#include <sys/socket.h>
#include <unistd.h>

namespace ringserver {

KqueueBackend::KqueueBackend() = default;

KqueueBackend::~KqueueBackend() {
    if (kq_fd_ >= 0) {
        ::close(kq_fd_);
    }
}

Status KqueueBackend::Init() {
    kq_fd_ = ::kqueue();
    if (kq_fd_ < 0) {
        return Status::Unknown(
            std::string_view(strerror(errno)));
    }
    return Status::Ok();
}

Status KqueueBackend::SubmitAccept(int listen_fd, int64_t user_data) {
    // Register interest in accept readiness
    struct kevent change;
    EV_SET(&change, listen_fd, EVFILT_READ, EV_ADD | EV_ENABLE, 0, 0,
           reinterpret_cast<void*>(user_data));

    if (::kevent(kq_fd_, &change, 1, nullptr, 0, nullptr) < 0) {
        return Status::Unknown(
            std::string_view(strerror(errno)));
    }
    return Status::Ok();
}

Status KqueueBackend::SubmitRead(int fd, uint8_t* buf, size_t cap, int64_t user_data) {
    // For kqueue, we register read interest and track context
    // Actual read happens in Poll when socket is ready
    struct kevent change;
    EV_SET(&change, fd, EVFILT_READ, EV_ADD | EV_ENABLE, 0, 0,
           reinterpret_cast<void*>(user_data));

    if (::kevent(kq_fd_, &change, 1, nullptr, 0, nullptr) < 0) {
        return Status::Unknown(
            std::string_view(strerror(errno)));
    }

    // Store context for when socket becomes ready
    read_pending_[fd] = {buf, cap, user_data};
    return Status::Ok();
}

Status KqueueBackend::SubmitWrite(int fd, const uint8_t* buf, size_t len, int64_t user_data) {
    struct kevent change;
    EV_SET(&change, fd, EVFILT_WRITE, EV_ADD | EV_ENABLE, 0, 0,
           reinterpret_cast<void*>(user_data));

    if (::kevent(kq_fd_, &change, 1, nullptr, 0, nullptr) < 0) {
        return Status::Unknown(
            std::string_view(strerror(errno)));
    }

    write_pending_[fd] = {buf, len, user_data};
    return Status::Ok();
}

Status KqueueBackend::SubmitSendFile(int out_fd, int file_fd, off_t offset,
                                     size_t len, int64_t user_data) {
    // TODO: Implement sendfile for macOS
    // For Phase 0, fall back to read+write
    return Status::InvalidArg("SendFile not implemented in kqueue backend");
}

Status KqueueBackend::SubmitClose(int fd, int64_t user_data) {
    // Remove from kqueue tracking
    struct kevent change;
    EV_SET(&change, fd, EVFILT_READ, EV_DELETE, 0, 0, nullptr);
    ::kevent(kq_fd_, &change, 1, nullptr, 0, nullptr);
    EV_SET(&change, fd, EVFILT_WRITE, EV_DELETE, 0, 0, nullptr);
    ::kevent(kq_fd_, &change, 1, nullptr, 0, nullptr);

    read_pending_.erase(fd);
    write_pending_.erase(fd);

    return Status::Ok();
}

Status KqueueBackend::Poll(std::vector<CompletionEvent>* out, int timeout_ms) {
    struct timespec ts;
    if (timeout_ms >= 0) {
        ts.tv_sec = timeout_ms / 1000;
        ts.tv_nsec = (timeout_ms % 1000) * 1000000;
    }

    std::array<struct kevent, 64> events;
    int n = ::kevent(kq_fd_, nullptr, 0, events.data(), events.size(),
                     timeout_ms >= 0 ? &ts : nullptr);

    if (n < 0) {
        if (errno == EINTR) {
            return Status::Again();
        }
        return Status::Unknown(
            std::string_view(strerror(errno)));
    }

    out->clear();
    out->reserve(n);

    for (int i = 0; i < n; ++i) {
        const struct kevent& ev = events[i];
        int fd = static_cast<int>(ev.ident);
        int64_t user_data = reinterpret_cast<int64_t>(ev.udata);

        CompletionEvent ce;
        ce.fd = fd;
        ce.user_data = user_data;
        ce.result = 0;
        ce.flags = 0;

        if (ev.flags & EV_EOF) {
            // Connection closed
            ce.op = OpKind::kClose;
            ce.result = -ECONNRESET;
            ce.flags |= EV_EOF;
            read_pending_.erase(fd);
            write_pending_.erase(fd);
        } else if (ev.filter == EVFILT_READ) {
            ce.op = OpKind::kRead;
            // Perform the actual read
            auto it = read_pending_.find(fd);
            if (it != read_pending_.end()) {
                ssize_t r = ::read(fd, it->second.buf, it->second.cap);
                if (r < 0) {
                    if (errno == EAGAIN || errno == EWOULDBLOCK) {
                        ce.result = 0;  // No data yet
                    } else {
                        ce.result = -errno;
                    }
                } else if (r == 0) {
                    ce.result = 0;  // EOF
                    ce.flags |= EV_EOF;
                } else {
                    ce.result = static_cast<int32_t>(r);
                }
                read_pending_.erase(it);
            } else {
                // Accept ready
                ce.op = OpKind::kAccept;
                ce.result = 0;
            }
        } else if (ev.filter == EVFILT_WRITE) {
            ce.op = OpKind::kWrite;
            auto it = write_pending_.find(fd);
            if (it != write_pending_.end()) {
                ssize_t w = ::write(fd, it->second.buf, it->second.len);
                if (w < 0) {
                    if (errno == EAGAIN || errno == EWOULDBLOCK) {
                        ce.result = 0;
                    } else {
                        ce.result = -errno;
                    }
                } else {
                    ce.result = static_cast<int32_t>(w);
                }
                if (w != static_cast<ssize_t>(it->second.len)) {
                    // Partial write, keep pending
                    write_pending_[fd] = {
                        it->second.buf + w,
                        it->second.len - static_cast<size_t>(w),
                        it->second.user_data
                    };
                } else {
                    write_pending_.erase(it);
                }
            }
        }

        out->push_back(ce);
    }

    return Status::Ok();
}

}  // namespace ringserver
