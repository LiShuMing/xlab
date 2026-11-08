#pragma once
#include <unistd.h>

#include <array>
#include <cstddef>
#include <cstdint>
#include <string>
#include <string_view>

namespace ringserver {
enum class ParseResult { kNeedMore, kReady, kBad };
class Connection {
public:
    Connection(int fd, int64_t id) : fd_(fd), id_(id) {}
    ~Connection() {
        if (fd_ >= 0) ::close(fd_);
    }
    Connection(const Connection&) = delete;
    Connection& operator=(const Connection&) = delete;
    int fd() const { return fd_; }
    int64_t id() const { return id_; }
    uint8_t* read_buf() { return read_buf_.data() + read_size_; }
    size_t read_cap() const { return read_buf_.size() - read_size_; }
    void AddRead(size_t bytes) { read_size_ += bytes; }
    ParseResult Parse();
    bool keep_alive() const { return keep_alive_ && !invalid_request; }
    bool invalid_request = false;
    void SetResponse(std::string_view response) {
        response_.assign(response);
        written_ = 0;
    }
    const uint8_t* write_buf() const {
        return reinterpret_cast<const uint8_t*>(response_.data() + written_);
    }
    size_t write_len() const { return response_.size() - written_; }
    void AddWritten(size_t bytes) { written_ += bytes; }
    bool writing() const { return !response_.empty(); }
    void FinishWrite() {
        response_.clear();
        written_ = 0;
    }
    uint64_t request_start = 0, last_activity = 0;

private:
    int fd_;
    int64_t id_;
    std::array<uint8_t, 16384> read_buf_ {};
    size_t read_size_ = 0;
    bool keep_alive_ = true;
    std::string response_;
    size_t written_ = 0;
};
} // namespace ringserver
