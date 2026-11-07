#ifndef RINGSERVER_COMMON_UTIL_HPP_
#define RINGSERVER_COMMON_UTIL_HPP_

#include <cerrno>
#include <cstring>
#include <fcntl.h>
#include <memory>
#include <string_view>
#include <unistd.h>

namespace ringserver {

// RAII wrapper for file descriptors
class UniqueFd {
public:
    explicit UniqueFd(int fd = -1) : fd_(fd) {}
    ~UniqueFd() { reset(); }

    // Disable copy
    UniqueFd(const UniqueFd&) = delete;
    UniqueFd& operator=(const UniqueFd&) = delete;

    // Move semantics
    UniqueFd(UniqueFd&& other) noexcept : fd_(other.fd_) { other.fd_ = -1; }
    UniqueFd& operator=(UniqueFd&& other) noexcept {
        if (this != &other) {
            reset();
            fd_ = other.fd_;
            other.fd_ = -1;
        }
        return *this;
    }

    // Accessors
    [[nodiscard]] int get() const { return fd_; }
    [[nodiscard]] bool valid() const { return fd_ != -1; }
    [[nodiscard]] explicit operator bool() const { return valid(); }

    // Modifiers
    int release() {
        int old = fd_;
        fd_ = -1;
        return old;
    }

    void reset(int fd = -1) {
        if (fd_ != -1) {
            ::close(fd_);
        }
        fd_ = fd;
    }

private:
    int fd_;
};

// Create a non-blocking socket
inline int CreateNonBlockingSocket() {
    int fd = ::socket(AF_INET, SOCK_STREAM, 0);
    if (fd < 0) {
        return -1;
    }
    // Set non-blocking
    int flags = ::fcntl(fd, F_GETFL, 0);
    if (flags < 0 || ::fcntl(fd, F_SETFL, flags | O_NONBLOCK) < 0) {
        ::close(fd);
        return -1;
    }
    // Allow address reuse
    int opt = 1;
    if (::setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt)) < 0) {
        ::close(fd);
        return -1;
    }
    return fd;
}

// Get last error as string
inline std::string_view LastErrorString() {
    return std::strerror(errno);
}

// Get errno
inline int LastError() {
    return errno;
}

}  // namespace ringserver

#endif  // RINGSERVER_COMMON_UTIL_HPP_
