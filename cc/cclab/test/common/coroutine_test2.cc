#include <gtest/gtest.h>

#include <atomic>
#include <cassert>
#include <cstring>
#include <functional>
#include <iostream>
#include <thread>
#include <vector>

#include <iostream>
#include <coroutine>


struct Task {
    struct promise_type {
        Task get_return_object() {
            return Task{std::coroutine_handle<promise_type>::from_promise(*this)};
        }
        std::suspend_never initial_suspend() { return {}; }
        std::suspend_always final_suspend() noexcept { return {}; }
        void return_void() {}
        void unhandled_exception() {}

    private:
        // 内部数据可扩展
    };

    explicit Task(std::coroutine_handle<promise_type> h) : handle(h) {}

    ~Task() {
        if (handle) {
            handle.destroy(); // 销毁协程
        }
    }

    void resume() {
        if (handle && !handle.done()) {
            handle.resume(); // 恢复协程
        }
    }

private:
    std::coroutine_handle<promise_type> handle; // 保存协程句柄
};

Task example() {
    std::cout << "Hello, ";
    co_await std::suspend_always{};
    std::cout << "world!" << std::endl;
}
class Coroutine2Test : public testing::Test {
};

TEST_F(Coroutine2Test, TestBasic) {
    auto task = example(); // 创建协程
    task.resume(); // 恢复执行
}


