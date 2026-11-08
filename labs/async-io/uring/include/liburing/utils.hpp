#pragma once
#include <liburing.h>

#include <chrono>
#include <system_error>

namespace uio {
inline __kernel_timespec Duration(std::chrono::nanoseconds duration) {
    const auto seconds = std::chrono::duration_cast<std::chrono::seconds>(duration);
    return {seconds.count(), (duration - seconds).count()};
}
inline int CheckResult(int result) {
    if (result < 0) throw std::system_error(-result, std::generic_category());
    return result;
}
} // namespace uio
