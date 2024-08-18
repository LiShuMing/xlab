#include "ringserver/server/connection.hpp"

#include <unistd.h>

namespace ringserver {

Connection::Connection(int fd, int64_t id)
    : fd_(fd), id_(id), state_(ConnState::kReading) {}

Connection::~Connection() {
    Close();
}

void Connection::Close() {
    if (fd_ >= 0) {
        ::close(fd_);
        fd_ = -1;
    }
    state_ = ConnState::kClosed;
}

}  // namespace ringserver
