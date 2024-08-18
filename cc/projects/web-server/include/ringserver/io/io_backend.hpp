#ifndef RINGSERVER_IO_IO_BACKEND_HPP_
#define RINGSERVER_IO_IO_BACKEND_HPP_

#include <cstdint>
#include <memory>
#include <vector>

#include "ringserver/common/status.hpp"

namespace ringserver {

// Operation types supported by the I/O backend
enum class OpKind : uint8_t {
    kAccept = 0,
    kRead,
    kWrite,
    kSendFile,
    kClose,
};

// Completion event returned by Poll()
struct CompletionEvent {
    OpKind op;
    int fd;                    // Connection file descriptor
    int64_t user_data;         // Connection ID or custom data
    int32_t result;            // Bytes transferred, or -errno on error
    uint32_t flags;            // Optional flags (e.g., EOF)

    // Convenience accessors
    [[nodiscard]] bool ok() const { return result >= 0; }
    [[nodiscard]] int32_t bytes() const { return result; }
    [[nodiscard]] int error() const { return result < 0 ? -result : 0; }
};

// Abstract I/O backend interface
// Provides unified completion-based API across platforms
class IoBackend {
public:
    virtual ~IoBackend() = default;

    // Initialize the backend
    [[nodiscard]] virtual Status Init() = 0;

    // Submit operations
    // user_data: opaque value passed back in CompletionEvent
    [[nodiscard]] virtual Status SubmitAccept(int listen_fd, int64_t user_data) = 0;
    [[nodiscard]] virtual Status SubmitRead(int fd, uint8_t* buf, size_t cap, int64_t user_data) = 0;
    [[nodiscard]] virtual Status SubmitWrite(int fd, const uint8_t* buf, size_t len, int64_t user_data) = 0;
    [[nodiscard]] virtual Status SubmitSendFile(int out_fd, int file_fd, off_t offset,
                                                size_t len, int64_t user_data) = 0;
    [[nodiscard]] virtual Status SubmitClose(int fd, int64_t user_data) = 0;

    // Poll for completed operations
    // timeout_ms: milliseconds to wait, -1 for infinite, 0 for non-blocking
    // Returns completion events in out vector
    [[nodiscard]] virtual Status Poll(std::vector<CompletionEvent>* out, int timeout_ms) = 0;

    // Get backend name for logging
    [[nodiscard]] virtual std::string_view name() const = 0;
};

// Factory function to create appropriate backend for platform
std::unique_ptr<IoBackend> CreateIoBackend();

}  // namespace ringserver

#endif  // RINGSERVER_IO_IO_BACKEND_HPP_
