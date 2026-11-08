#pragma once
#include <coroutine>
#include <exception>
#include <optional>
#include <stdexcept>
#include <type_traits>
#include <utility>

namespace uio {
template <typename T = void>
class Task;
template <typename T>
struct TaskReturn {
    std::optional<T> value;
    void return_value(T result) { value = std::move(result); }
};
template <>
struct TaskReturn<void> {
    void return_void() {}
};

// Lazy, structured tasks. There is no detach: started tasks must finish before destruction.
template <typename T>
class Task {
public:
    struct promise_type : TaskReturn<T> {
        std::exception_ptr error;
        std::coroutine_handle<> continuation = std::noop_coroutine();
        Task get_return_object() { return Task(Handle::from_promise(*this)); }
        std::suspend_always initial_suspend() noexcept { return {}; }
        struct FinalAwaiter {
            bool await_ready() const noexcept { return false; }
            std::coroutine_handle<> await_suspend(std::coroutine_handle<promise_type> h) noexcept {
                return h.promise().continuation;
            }
            void await_resume() noexcept {}
        };
        FinalAwaiter final_suspend() noexcept { return {}; }
        void unhandled_exception() noexcept { error = std::current_exception(); }
    };
    using Handle = std::coroutine_handle<promise_type>;
    Task(const Task&) = delete;
    Task& operator=(const Task&) = delete;
    Task(Task&& other) noexcept
            : handle_(std::exchange(other.handle_, {})), started_(other.started_) {}
    Task& operator=(Task&&) = delete;
    ~Task() {
        if (!handle_) return;
        // Otherwise the kernel could still reference an awaiter inside this frame.
        if (started_ && !handle_.done()) std::terminate();
        handle_.destroy();
    }
    bool done() const { return handle_.done(); }
    void Start() {
        if (started_) throw std::logic_error("task already started");
        started_ = true;
        handle_.resume();
    }
    T Result() {
        if (!done()) throw std::logic_error("task is not complete");
        if (handle_.promise().error) std::rethrow_exception(handle_.promise().error);
        if constexpr (!std::is_void_v<T>) return std::move(*handle_.promise().value);
    }
    bool await_ready() const noexcept { return false; }
    Handle await_suspend(std::coroutine_handle<> continuation) {
        if (started_) throw std::logic_error("task already started");
        started_ = true;
        handle_.promise().continuation = continuation;
        return handle_;
    }
    T await_resume() { return Result(); }

private:
    explicit Task(Handle handle) : handle_(handle) {}
    Handle handle_;
    bool started_ = false;
};
template <typename T = void, bool = false>
using task = Task<T>;
} // namespace uio
