// task.hpp - MiniSeastar Coroutine Task Type
// Phase 1: Coroutine runtime without I/O
//
// This file implements task<T>, a C++20 coroutine-friendly future-like type.
// It provides:
//   - task<T> with promise_type for coroutine integration
//   - co_await task<T> support (continuation/chaining)
//   - Error propagation via std::exception_ptr
//
// Invariants:
//   - A task is std::move-constructible but not copyable
//   - task<void> is valid and co_return; works correctly
//   - Destruction of an unstarted task destroys the coroutine frame
//   - co_await on a completed task returns immediately

#ifndef MINISEASTAR_TASK_HPP
#define MINISEASTAR_TASK_HPP

#include <atomic>
#include <exception>
#include <type_traits>
#include <utility>
#include <variant>
#include <initializer_list>

#if defined(__APPLE__) && defined(__clang__)
// Use experimental coroutines on Apple Clang
#include <experimental/coroutine>
namespace coroutine_ns = std::experimental::coroutines_v1;
#else
// Use standard coroutines elsewhere
#include <coroutine>
namespace coroutine_ns = std;
#endif

namespace miniseastar {

// Forward declaration
template<typename T>
class Task;

// ============================================================================
// TaskAwaiter<T> - Awaitable for Task<T>
// ============================================================================

/**
 * TaskAwaiter implements the awaitable concept for Task<T>.
 *
 * When co_await task is used:
 *   1. await_ready(): checks if task is already complete
 *   2. If not ready: await_suspend() stores continuation and suspends
 *   3. When task completes: await_resume() returns the result
 */
template<typename T>
class TaskAwaiter {
public:
    explicit TaskAwaiter(Task<T> task) noexcept : task_(std::move(task)) {}

    // No suspend needed if already ready
    [[nodiscard]] bool await_ready() const noexcept {
        return task_.is_ready();
    }

    // Task not ready: suspend current coroutine
    // continuation: the coroutine that is waiting on this task
    void await_suspend(coroutine_ns::coroutine_handle<> continuation) noexcept {
        // Store continuation in promise for later resumption
        task_.promise().set_continuation(continuation);
    }

    // Task completed: return the result
    template<typename U = T>
    [[nodiscard]] std::enable_if_t<!std::is_void_v<U>, U> await_resume() {
        return std::move(task_.promise().get_result());
    }

    // Void specialization
    template<typename U = T>
    [[nodiscard]] std::enable_if_t<std::is_void_v<U>, void> await_resume() {
        task_.promise().rethrow_if_exception();
    }

private:
    Task<T> task_;
};

// ============================================================================
// TaskPromise<T> - Coroutine promise for Task<T>
// ============================================================================

template<typename T>
class TaskPromise {
public:
    coroutine_ns::suspend_always initial_suspend() noexcept { return {}; }
    coroutine_ns::suspend_always final_suspend() noexcept { return {}; }

    void return_value(T&& value) noexcept(std::is_nothrow_move_constructible_v<T>) {
        Result* r = reinterpret_cast<Result*>(storage_);
        r->v.template emplace<1>(std::move(value));
        ready_.store(true, std::memory_order_release);
    }

    void unhandled_exception() noexcept {
        Result* r = reinterpret_cast<Result*>(storage_);
        r->v.template emplace<2>(std::current_exception());
        ready_.store(true, std::memory_order_release);
    }

    Task<T> get_return_object() noexcept;

    // Result access
    T get_result() {
        if (!ready_.load(std::memory_order_acquire)) {
            std::terminate();  // Bug: get_result called before completion
        }
        Result* r = reinterpret_cast<Result*>(storage_);
        if (r->v.index() == 2) {  // exception
            std::rethrow_exception(std::get<2>(r->v));
        }
        return std::move(std::get<1>(r->v));
    }

    bool is_ready() const noexcept {
        return ready_.load(std::memory_order_acquire);
    }

    bool has_exception() const noexcept {
        Result* r = reinterpret_cast<Result*>(storage_);
        return r->v.index() == 2;
    }

    std::exception_ptr exception() const noexcept {
        Result* r = reinterpret_cast<Result*>(storage_);
        return std::get<2>(r->v);
    }

    // Continuation support
    void set_continuation(coroutine_ns::coroutine_handle<> continuation) noexcept {
        continuation_ = continuation;
    }

    coroutine_ns::coroutine_handle<> continuation() noexcept {
        return continuation_;
    }

    bool has_continuation() const noexcept {
        return continuation_ != nullptr;
    }

    void clear_continuation() noexcept {
        continuation_ = nullptr;
    }

private:
    // Type-erased storage: std::monostate (empty), T (value), std::exception_ptr (exception)
    struct Result {
        std::variant<std::monostate, T, std::exception_ptr> v;
    };
    alignas(Result) unsigned char storage_[sizeof(Result)];
    std::atomic<bool> ready_{false};
    coroutine_ns::coroutine_handle<> continuation_{nullptr};
};

// Specialization for void
template<>
class TaskPromise<void> {
public:
    coroutine_ns::suspend_always initial_suspend() noexcept { return {}; }
    coroutine_ns::suspend_always final_suspend() noexcept { return {}; }

    void return_void() noexcept {
        ready_.store(true, std::memory_order_release);
    }

    void unhandled_exception() noexcept {
        exception_ptr_ = std::current_exception();
        ready_.store(true, std::memory_order_release);
    }

    Task<void> get_return_object() noexcept;

    void rethrow_if_exception() {
        if (exception_ptr_) {
            std::rethrow_exception(exception_ptr_);
        }
    }

    bool is_ready() const noexcept {
        return ready_.load(std::memory_order_acquire);
    }

    bool has_exception() const noexcept { return exception_ptr_ != nullptr; }
    std::exception_ptr exception() const noexcept { return exception_ptr_; }

    // Continuation support
    void set_continuation(coroutine_ns::coroutine_handle<> continuation) noexcept {
        continuation_ = continuation;
    }

    coroutine_ns::coroutine_handle<> continuation() noexcept {
        return continuation_;
    }

    bool has_continuation() const noexcept {
        return continuation_ != nullptr;
    }

    void clear_continuation() noexcept {
        continuation_ = nullptr;
    }

private:
    std::atomic<bool> ready_{false};
    std::exception_ptr exception_ptr_{nullptr};
    coroutine_ns::coroutine_handle<> continuation_{nullptr};
};

// ============================================================================
// Task<T> - Coroutine handle type
// ============================================================================

template<typename T>
class Task {
public:
    using promise_type = TaskPromise<T>;
    using handle_type = coroutine_ns::coroutine_handle<promise_type>;

    Task() noexcept : handle_(nullptr) {}

    Task(Task&& other) noexcept : handle_(other.handle_) {
        other.handle_ = nullptr;
    }

    Task& operator=(Task&& other) noexcept {
        if (this != &other) {
            destroy();
            handle_ = other.handle_;
            other.handle_ = nullptr;
        }
        return *this;
    }

    Task(const Task&) = delete;
    Task& operator=(const Task&) = delete;

    ~Task() { destroy(); }

    void destroy() {
        if (handle_) {
            handle_.destroy();
            handle_ = nullptr;
        }
    }

    explicit operator bool() const noexcept { return handle_ != nullptr; }

    void resume() {
        if (handle_ && !handle_.done()) {
            handle_.resume();
        }
    }

    bool done() const noexcept {
        return handle_ && handle_.done();
    }

    bool is_ready() const noexcept {
        return !handle_ || handle_.promise().is_ready();
    }

    template<typename U = T>
    U get() {
        if constexpr (std::is_void_v<U>) {
            promise().rethrow_if_exception();
        } else {
            return std::move(promise().get_result());
        }
    }

    promise_type& promise() const noexcept {
        return handle_.promise();
    }

    handle_type handle() noexcept { return handle_; }

private:
    explicit Task(handle_type h) noexcept : handle_(h) {}

    handle_type handle_;

    template<typename U>
    friend class TaskPromise;
};

// ============================================================================
// operator co_await for Task<T>
// ============================================================================

template<typename T>
[[nodiscard]] TaskAwaiter<T> operator co_await(Task<T> task) noexcept {
    return TaskAwaiter<T>(std::move(task));
}

// ============================================================================
// Promise get_return_object implementations
// ============================================================================

template<typename T>
Task<T> TaskPromise<T>::get_return_object() noexcept {
    return Task<T>(coroutine_ns::coroutine_handle<TaskPromise<T>>::from_promise(*this));
}

inline Task<void> TaskPromise<void>::get_return_object() noexcept {
    return Task<void>(coroutine_ns::coroutine_handle<TaskPromise<void>>::from_promise(*this));
}

}  // namespace miniseastar

#endif  // MINISEASTAR_TASK_HPP
