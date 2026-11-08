#pragma once
#include <sys/types.h>

#include <cstddef>
#include <cstdint>
#include <memory>
#include <string_view>
#include <vector>

#include "ringserver/common/status.hpp"

namespace ringserver {
enum class OpKind : uint8_t { kAccept, kRead, kWrite, kClose };
struct CompletionEvent {
    OpKind op;
    int fd;
    int64_t user_data;
    int32_t result;
    uint32_t flags = 0;
};
struct BackendStats {
    uint64_t submitted = 0, completed = 0, polls = 0, empty_polls = 0;
    uint64_t submit_calls = 0, retries = 0, queue_full = 0, cancelled = 0;
    uint64_t max_pending = 0;
    uint64_t operation_allocations = 0, copied_bytes = 0;
};
// Exactly one pending read/write per connection. SubmitClose suppresses future
// events and retains backend-owned kernel buffers until cancellation completes.
class IoBackend {
public:
    virtual ~IoBackend() = default;
    virtual Status Init() = 0;
    virtual Status SubmitAccept(int listen_fd, int64_t user_data) = 0;
    virtual Status SubmitRead(int fd, uint8_t* buf, size_t cap, int64_t user_data) = 0;
    virtual Status SubmitWrite(int fd, const uint8_t* buf, size_t len, int64_t user_data) = 0;
    virtual Status SubmitClose(int fd, int64_t user_data) = 0;
    virtual Status Poll(std::vector<CompletionEvent>* out, int timeout_ms) = 0;
    virtual Status Drain() = 0;
    virtual std::string_view name() const = 0;
    BackendStats stats;
};
std::unique_ptr<IoBackend> CreateIoBackend(std::string_view name, unsigned depth, unsigned batch);
} // namespace ringserver
