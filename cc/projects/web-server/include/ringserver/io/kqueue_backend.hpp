#ifndef RINGSERVER_IO_KQUEUE_BACKEND_HPP_
#define RINGSERVER_IO_KQUEUE_BACKEND_HPP_

#include <memory>
#include <unordered_map>
#include <vector>

#include <sys/event.h>

#include "ringserver/io/io_backend.hpp"

namespace ringserver {

// Kqueue-based I/O backend for macOS
// Adapts reactor-style kqueue into completion-based interface
class KqueueBackend : public IoBackend {
public:
    KqueueBackend();
    ~KqueueBackend() override;

    // Disable copy
    KqueueBackend(const KqueueBackend&) = delete;
    KqueueBackend& operator=(const KqueueBackend&) = delete;

    [[nodiscard]] Status Init() override;
    [[nodiscard]] Status SubmitAccept(int listen_fd, int64_t user_data) override;
    [[nodiscard]] Status SubmitRead(int fd, uint8_t* buf, size_t cap, int64_t user_data) override;
    [[nodiscard]] Status SubmitWrite(int fd, const uint8_t* buf, size_t len, int64_t user_data) override;
    [[nodiscard]] Status SubmitSendFile(int out_fd, int file_fd, off_t offset,
                                        size_t len, int64_t user_data) override;
    [[nodiscard]] Status SubmitClose(int fd, int64_t user_data) override;
    [[nodiscard]] Status Poll(std::vector<CompletionEvent>* out, int timeout_ms) override;
    [[nodiscard]] std::string_view name() const override { return "kqueue"; }

private:
    // Track pending read operations
    struct ReadContext {
        uint8_t* buf;
        size_t cap;
        int64_t user_data;
    };

    // Track pending write operations
    struct WriteContext {
        const uint8_t* buf;
        size_t len;
        int64_t user_data;
    };

    int kq_fd_ = -1;
    std::unordered_map<int, ReadContext> read_pending_;
    std::unordered_map<int, WriteContext> write_pending_;
};

}  // namespace ringserver

#endif  // RINGSERVER_IO_KQUEUE_BACKEND_HPP_
