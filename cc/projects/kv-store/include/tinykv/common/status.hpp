#ifndef TINYKV_COMMON_STATUS_HPP_
#define TINYKV_COMMON_STATUS_HPP_

#include <string>

namespace tinykv {

// Status: error return type for operations that may fail.
// Zero-allocation for OK status (uses small buffer optimization).
class Status {
public:
    // Factory methods for common status codes
    static auto OK() -> Status { return Status(); }
    static auto NotFound(const std::string& msg = "") -> Status {
        return Status(kNotFound, msg);
    }
    static auto Corruption(const std::string& msg = "") -> Status {
        return Status(kCorruption, msg);
    }
    static auto InvalidArgument(const std::string& msg = "") -> Status {
        return Status(kInvalidArgument, msg);
    }
    static auto IOError(const std::string& msg = "") -> Status {
        return Status(kIOError, msg);
    }
    static auto Busy(const std::string& msg = "") -> Status {
        return Status(kBusy, msg);
    }

    // Default constructor creates OK status
    Status() noexcept : code_(kOk), message_("") {}

    // Destructor
    ~Status() = default;

    // Movable
    Status(Status&&) noexcept = default;
    Status& operator=(Status&&) noexcept = default;

    // Non-copyable for simplicity (statuses are usually returned by value)
    Status(const Status&) = delete;
    Status& operator=(const Status&) = delete;

    // Accessors
    auto ok() const noexcept -> bool { return code_ == kOk; }
    auto IsNotFound() const noexcept -> bool { return code_ == kNotFound; }
    auto IsCorruption() const noexcept -> bool { return code_ == kCorruption; }
    auto IsInvalidArgument() const noexcept -> bool { return code_ == kInvalidArgument; }
    auto IsIOError() const noexcept -> bool { return code_ == kIOError; }
    auto IsBusy() const noexcept -> bool { return code_ == kBusy; }

    // Returns error message (empty for OK status)
    auto ToString() const -> std::string {
        if (code_ == kOk) return "OK";
        std::string result = CodeToString(code_);
        if (!message_.empty()) {
            result += ": ";
            result += message_;
        }
        return result;
    }

    // Returns just the message (empty for OK status)
    auto Message() const -> std::string { return message_; }

private:
    enum Code {
        kOk = 0,
        kNotFound,
        kCorruption,
        kInvalidArgument,
        kIOError,
        kBusy
    };

    explicit Status(Code code, const std::string& msg = "")
        : code_(code), message_(msg) {}

    static auto CodeToString(Code code) -> const char* {
        switch (code) {
            case kOk: return "OK";
            case kNotFound: return "NotFound";
            case kCorruption: return "Corruption";
            case kInvalidArgument: return "InvalidArgument";
            case kIOError: return "IOError";
            case kBusy: return "Busy";
        }
        return "Unknown";
    }

    Code code_;
    std::string message_;
};

}  // namespace tinykv

#endif  // TINYKV_COMMON_STATUS_HPP_
