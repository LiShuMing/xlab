#ifndef VAGG_COMMON_STATUS_H_
#define VAGG_COMMON_STATUS_H_

#include <string>
#include <string_view>

namespace vagg {

// Status codes for engine operations
enum class StatusCode {
  kOk,
  kInvalidArgument,
  kNotFound,
  kAlreadyExists,
  kOutOfMemory,
  kEndOfFile,
  kNotImplemented,
};

// Simple status result type
class Status {
 public:
  Status() : code_(StatusCode::kOk), message_("") {}

  Status(StatusCode code, std::string message)
      : code_(code), message_(std::move(message)) {}

  static Status Ok() { return Status(); }
  static Status InvalidArgument(const std::string& msg) {
    return Status(StatusCode::kInvalidArgument, msg);
  }
  static Status NotFound(const std::string& msg) {
    return Status(StatusCode::kNotFound, msg);
  }
  static Status AlreadyExists(const std::string& msg) {
    return Status(StatusCode::kAlreadyExists, msg);
  }
  static Status OutOfMemory(const std::string& msg) {
    return Status(StatusCode::kOutOfMemory, msg);
  }
  static Status EndOfFile() { return Status(StatusCode::kEndOfFile, "EOF"); }
  static Status Invalid(const std::string& msg) {
    return Status(StatusCode::kInvalidArgument, msg);
  }
  static Status NotImplemented(const std::string& msg) {
    return Status(StatusCode::kNotImplemented, msg);
  }

  bool ok() const { return code_ == StatusCode::kOk; }
  StatusCode code() const { return code_; }
  std::string_view message() const { return message_; }

  std::string ToString() const {
    if (ok()) return "OK";
    return std::string(StatusCodeToString(code_)) + ": " + message_;
  }

 private:
  static const char* StatusCodeToString(StatusCode code) {
    switch (code) {
      case StatusCode::kOk:
        return "OK";
      case StatusCode::kInvalidArgument:
        return "InvalidArgument";
      case StatusCode::kNotFound:
        return "NotFound";
      case StatusCode::kAlreadyExists:
        return "AlreadyExists";
      case StatusCode::kOutOfMemory:
        return "OutOfMemory";
      case StatusCode::kEndOfFile:
        return "EndOfFile";
      case StatusCode::kNotImplemented:
        return "NotImplemented";
    }
    return "Unknown";
  }

  StatusCode code_;
  std::string message_;
};

}  // namespace vagg

// Macro for error handling
#define RETURN_IF_ERROR(expr) \
  do { \
    auto _status = (expr); \
    if (!_status.ok()) { \
      return _status; \
    } \
  } while (0)

#endif  // VAGG_COMMON_STATUS_H_
