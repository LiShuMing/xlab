#ifndef RINGSERVER_SERVER_CONNECTION_HPP_
#define RINGSERVER_SERVER_CONNECTION_HPP_

#include <array>
#include <cstddef>
#include <cstdint>
#include <string>
#include <string_view>

#include "ringserver/common/status.hpp"

namespace ringserver {

// Connection state machine
enum class ConnState : uint8_t {
    kReading = 0,   // Reading request
    kProcessing,    // Request being processed
    kWriting,       // Sending response
    kClosing,       // Connection closing
    kClosed,        // Connection closed
};

// Connection manages a single client connection
// Handles read/write buffers and state transitions
class Connection {
public:
    Connection(int fd, int64_t id);
    ~Connection();

    // Disable copy
    Connection(const Connection&) = delete;
    Connection& operator=(const Connection&) = delete;

    // Accessors
    [[nodiscard]] int fd() const { return fd_; }
    [[nodiscard]] int64_t id() const { return id_; }
    [[nodiscard]] ConnState state() const { return state_; }
    [[nodiscard]] bool closed() const { return state_ == ConnState::kClosed; }
    [[nodiscard]] bool reading() const { return state_ == ConnState::kReading; }
    [[nodiscard]] bool writing() const { return state_ == ConnState::kWriting; }

    // Get read buffer for I/O backend
    [[nodiscard]] uint8_t* read_buf() { return read_buf_.data(); }
    [[nodiscard]] size_t read_cap() const { return read_buf_.size(); }

    // Get write buffer
    [[nodiscard]] const uint8_t* write_buf() const { return write_buf_.data(); }
    [[nodiscard]] size_t write_len() const { return write_len_; }

    // Set write buffer from response
    void SetResponse(std::string_view response) {
        write_len_ = std::min(response.size(), write_buf_.size());
        std::memcpy(write_buf_.data(), response.data(), write_len_);
    }

    // State transitions
    void SetReading() { state_ = ConnState::kReading; }
    void SetProcessing() { state_ = ConnState::kProcessing; }
    void SetWriting() { state_ = ConnState::kWriting; }
    void SetClosing() { state_ = ConnState::kClosing; }
    void SetClosed() { state_ = ConnState::kClosed; }

    // Mark connection for closure
    void MarkForClosure() {
        state_ = ConnState::kClosing;
    }

    // Close the connection
    void Close();

    // Check if keep-alive should be used
    [[nodiscard]] bool KeepAlive() const { return keep_alive_; }
    void SetKeepAlive(bool ka) { keep_alive_ = ka; }

    // Track bytes transferred
    void AddBytesRead(size_t n) { bytes_read_ += n; }
    void AddBytesWritten(size_t n) { bytes_written_ += n; }
    [[nodiscard]] size_t bytes_read() const { return bytes_read_; }
    [[nodiscard]] size_t bytes_written() const { return bytes_written_; }

private:
    int fd_;
    int64_t id_;
    ConnState state_ = ConnState::kReading;
    bool keep_alive_ = true;

    // Read buffer for incoming requests
    std::array<uint8_t, 4096> read_buf_;

    // Write buffer for responses (fixed 200 OK response)
    std::array<uint8_t, 4096> write_buf_;
    size_t write_len_ = 0;

    // Statistics
    size_t bytes_read_ = 0;
    size_t bytes_written_ = 0;
};

}  // namespace ringserver

#endif  // RINGSERVER_SERVER_CONNECTION_HPP_
