#ifndef WSTP_STATUS_H_
#define WSTP_STATUS_H_

#include <string>

namespace wstp {

// Status codes for thread pool operations
enum class StatusCode {
  kOk,
  kStopped,
  kInvalidArgument,
  kShuttingDown,
};

// Simple status result type
class Status {
 public:
  Status() : code_(StatusCode::kOk), message_("") {}

  Status(StatusCode code, std::string message)
      : code_(code), message_(std::move(message)) {}

  static Status Ok() { return Status(); }
  static Status Stopped() { return Status(StatusCode::kStopped, "pool is stopped"); }
  static Status InvalidArgument(const std::string& msg) {
    return Status(StatusCode::kInvalidArgument, msg);
  }
  static Status ShuttingDown() {
    return Status(StatusCode::kShuttingDown, "pool is shutting down");
  }

  bool ok() const { return code_ == StatusCode::kOk; }
  StatusCode code() const { return code_; }
  const std::string& message() const { return message_; }

 private:
  StatusCode code_;
  std::string message_;
};

}  // namespace wstp

#endif  // WSTP_STATUS_H_
