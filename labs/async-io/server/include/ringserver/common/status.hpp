#ifndef RINGSERVER_COMMON_STATUS_HPP_
#define RINGSERVER_COMMON_STATUS_HPP_

#include <cstdint>
#include <string>
#include <string_view>

namespace ringserver {

// Status code for I/O operations
enum class StatusCode : uint8_t {
    kOk = 0,
    kAgain,       // EAGAIN/EWOULDBLOCK - retry operation
    kEndOfFile,   // Connection closed
    kInvalidArg,  // Invalid argument
    kWouldBlock,  // Operation would block (non-blocking socket)
    kConnectionReset,
    kConnectionClosed,
    kUnknown,
};

// Result type for operations that can fail
class Status {
public:
    Status() : code_(StatusCode::kOk), message_() {}

    Status(StatusCode code, std::string_view msg)
        : code_(code), message_(msg) {}

    // Factory methods
    static Status Ok() { return Status(); }
    static Status Again(std::string_view msg = {}) { return Status(StatusCode::kAgain, msg); }
    static Status Eof(std::string_view msg = {}) { return Status(StatusCode::kEndOfFile, msg); }
    static Status InvalidArg(std::string_view msg = {}) { return Status(StatusCode::kInvalidArg, msg); }
    static Status WouldBlock(std::string_view msg = {}) { return Status(StatusCode::kWouldBlock, msg); }
    static Status ConnectionReset(std::string_view msg = {}) { return Status(StatusCode::kConnectionReset, msg); }
    static Status ConnectionClosed(std::string_view msg = {}) { return Status(StatusCode::kConnectionClosed, msg); }
    static Status Unknown(std::string_view msg = {}) { return Status(StatusCode::kUnknown, msg); }

    // Accessors
    [[nodiscard]] bool ok() const { return code_ == StatusCode::kOk; }
    [[nodiscard]] bool IsAgain() const { return code_ == StatusCode::kAgain; }
    [[nodiscard]] bool IsEof() const { return code_ == StatusCode::kEndOfFile; }
    [[nodiscard]] bool IsWouldBlock() const { return code_ == StatusCode::kWouldBlock; }
    [[nodiscard]] bool IsConnectionError() const {
        return code_ == StatusCode::kConnectionReset ||
               code_ == StatusCode::kConnectionClosed;
    }

    [[nodiscard]] StatusCode code() const { return code_; }
    [[nodiscard]] std::string_view message() const { return message_; }

    // Convert to string for logging
    [[nodiscard]] std::string ToString() const {
        if (message_.empty()) {
            return CodeToString(code_);
        }
        return std::string(CodeToString(code_)) + ": " + std::string(message_);
    }

private:
    static const char* CodeToString(StatusCode code) {
        switch (code) {
            case StatusCode::kOk: return "OK";
            case StatusCode::kAgain: return "AGAIN";
            case StatusCode::kEndOfFile: return "EOF";
            case StatusCode::kInvalidArg: return "INVALID_ARG";
            case StatusCode::kWouldBlock: return "WOULD_BLOCK";
            case StatusCode::kConnectionReset: return "CONNECTION_RESET";
            case StatusCode::kConnectionClosed: return "CONNECTION_CLOSED";
            case StatusCode::kUnknown: return "UNKNOWN";
        }
        return "UNKNOWN";
    }

    StatusCode code_;
    std::string message_;
};

}  // namespace ringserver

#endif  // RINGSERVER_COMMON_STATUS_HPP_
