#ifndef WSTP_TASK_H_
#define WSTP_TASK_H_

#include <functional>
#include <future>
#include <type_traits>

namespace wstp {

// Task type using std::function for type erasure
// Phase 3: Could replace with small-buffer optimization
using Task = std::function<void()>;

// Helper to extract return type from callable for future
template <typename F>
using ResultType = std::invoke_result_t<F>;

}  // namespace wstp

#endif  // WSTP_TASK_H_
