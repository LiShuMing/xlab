#include "../include/fwd.h"
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <deque>
#include <functional>
#include <future>
#include <mutex>
#include <stdexcept>
#include <thread>
#include <utility>

/**
有界线程池 —— 面试版（核心 60 行，其余全是自验证）。

「有界」= 排队任务数有全局上限。作用不是省内存，而是**背压（backpressure）**：
提交方拿不到入队许可就必须自己处理（等待 / 丢弃 / 同步执行 / 抛异常），
否则无界队列会把上游的突发流量全吞下来，最终 OOM 或延迟雪崩。

五个组成部分：
  1. workers_     固定数量线程，各自死循环取任务
  2. tasks_       std::deque<std::function<void()>>（不用 vector：要头删）
  3. mu_ + cv_    用「互斥量 + 条件变量」阻塞等待（绝不自旋，空闲时 0% CPU）
  4. capacity_    队列上限，submit 时检查 → 返回 false 就是背压信号
  5. stop_        关闭标志，配合 cv 的谓词实现「排空后退出」

面试必须说对的三个细节：
  ① cv_.wait 必须带谓词（内部是 while 循环），否则虚假唤醒会让空队列被 pop
  ② 取任务要在锁内、执行任务必须在锁外，否则任务串行化，线程池白建
  ③ 关闭要 notify_all 而不是 notify_one，否则只叫醒一个线程，其余永远睡着

与仓库里 508 行的 algo_thread_pool.cc 的区别（后者实测现场 SIGSEGV）：
  工作窃取 Chase-Lev 双端队列的正确实现要处理「数组扩容与窃取并发」，
  单这一条就够写 300 行且极易写错，不适合放进 45 分钟的面试。
 */
class BoundedThreadPool {
public:
    BoundedThreadPool(size_t workers, size_t capacity)
        : capacity_(capacity == 0 ? 1 : capacity), stop_(false) {
        if (workers == 0) workers = 1;
        for (size_t i = 0; i < workers; ++i) {
            workers_.emplace_back([this] { workerLoop(); });
        }
    }

    ~BoundedThreadPool() { shutdown(); }

    BoundedThreadPool(const BoundedThreadPool&) = delete;
    BoundedThreadPool& operator=(const BoundedThreadPool&) = delete;

    // 返回 false = 被拒绝（队列满或已关闭）。由调用方决定后续策略。
    bool submit(std::function<void()> task) {
        if (!task) return false;
        {
            std::lock_guard<std::mutex> lock(mu_);  // 锁内只做「检查 + 入队」，很短
            if (stop_) return false;
            if (tasks_.size() >= capacity_) return false;  // 有界的检查点就在这里
            tasks_.push_back(std::move(task));
        }  // 先放锁再唤醒：否则被唤醒的线程会立刻撞在还没释放的锁上，白做一次上下文切换
        cv_.notify_one();
        return true;
    }

    // 需要返回值时用它：packaged_task 把结果/异常都装进 future
    template <typename F, typename... Args>
    auto submitFuture(F&& f, Args&&... args) -> std::future<std::invoke_result_t<F, Args...>> {
        using ReturnType = std::invoke_result_t<F, Args...>;
        auto task = std::make_shared<std::packaged_task<ReturnType()>>(
            std::bind(std::forward<F>(f), std::forward<Args>(args)...));
        auto future = task->get_future();
        if (!submit([task] { (*task)(); })) {
            throw std::runtime_error("BoundedThreadPool: queue is full");
        }
        return future;
    }

    // 优雅关闭：不再接受新任务，但已入队的必须跑完；重复调用安全
    void shutdown() {
        {
            std::lock_guard<std::mutex> lock(mu_);
            if (stop_) return;
            stop_ = true;
        }
        cv_.notify_all();  // 必须 all：所有 worker 都得醒来看到 stop_
        for (auto& worker : workers_) {
            if (worker.joinable()) worker.join();
        }
    }

    size_t pending() const {
        std::lock_guard<std::mutex> lock(mu_);  // mu_ 声明为 mutable，const 方法也能加锁
        return tasks_.size();
    }

private:
    void workerLoop() {
        for (;;) {
            std::function<void()> task;
            {
                std::unique_lock<std::mutex> lock(mu_);
                // 谓词版 wait：醒来先复查条件，虚假唤醒时自动继续睡
                cv_.wait(lock, [this] { return stop_ || !tasks_.empty(); });
                if (tasks_.empty()) {
                    if (stop_) return;  // 只有「已关闭 且 已排空」才退出 → 不丢任务
                    continue;
                }
                task = std::move(tasks_.front());  // 先取再 pop，顺序不能反
                tasks_.pop_front();
            }  // 锁已释放，下面是真正的并行执行
            try {
                task();
            } catch (...) {
                // 单个任务抛异常不能杀掉 worker，否则线程池会逐渐「漏气」
            }
        }
    }

    mutable std::mutex mu_;
    std::condition_variable cv_;
    std::deque<std::function<void()>> tasks_;
    std::vector<std::thread> workers_;
    const size_t capacity_;
    bool stop_;
};

// ============================================================================
// 自验证：六个面试官最可能追问的行为
// ============================================================================

static bool waitUntil(const std::atomic<int>& v, int target, int timeout_ms = 3000) {
    for (int waited = 0; waited < timeout_ms && v.load() < target; ++waited) {
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }
    return v.load() >= target;
}

int main() {
    int failed = 0;
    auto check = [&failed](bool ok, const string& name) {
        cout << (ok ? "[OK]   " : "[FAIL] ") << name << endl;
        if (!ok) ++failed;
    };

    // 1) 每个任务要么被执行、要么被明确拒绝 —— 不存在「静默丢任务」
    {
        BoundedThreadPool pool(4, 1024);
        std::atomic<int> ran{0};
        int accepted = 0;
        int rejected = 0;
        const int kTasks = 2000;
        for (int i = 0; i < kTasks; ++i) {
            if (pool.submit([&ran] { ran.fetch_add(1); })) {
                ++accepted;
            } else {
                ++rejected;
            }
        }
        const bool all_ran = waitUntil(ran, accepted);
        check(all_ran && accepted + rejected == kTasks,
              "提交 " + to_string(kTasks) + " 个：执行 " + to_string(ran.load()) + " + 拒绝 " +
                  to_string(rejected) + " = 全部有交代");
    }

    // 2) 有界性 + 背压可见：队列压到 4，狂提交必然被拒
    {
        BoundedThreadPool pool(2, 4);
        int accepted = 0;
        int rejected = 0;
        std::atomic<int> ran{0};
        for (int i = 0; i < 5000; ++i) {
            if (pool.submit([&ran] {
                    ran.fetch_add(1);
                    std::this_thread::sleep_for(std::chrono::microseconds(50));
                })) {
                ++accepted;
            } else {
                ++rejected;
            }
        }
        pool.shutdown();
        check(rejected > 0, "队列满时 submit 立即返回 false（背压可见），被拒 " + to_string(rejected) +
                                " 次");
        check(ran.load() == accepted, "shutdown 会排空：接受 " + to_string(accepted) + " 个，执行 " +
                                          to_string(ran.load()) + " 个");
        check(pool.pending() == 0, "shutdown 返回后队列已空");
        check(!pool.submit([] {}), "shutdown 之后再 submit 返回 false（不会凭空复活）");
    }

    // 3) 立即 shutdown 也必须把已接受的任务跑完（优雅关闭的语义）
    {
        BoundedThreadPool pool(1, 512);  // 只给 1 个 worker，任务一定在排队
        std::atomic<int> ran{0};
        int accepted = 0;
        for (int i = 0; i < 100; ++i) {
            if (pool.submit([&ran] {
                    std::this_thread::sleep_for(std::chrono::microseconds(200));
                    ran.fetch_add(1);
                })) {
                ++accepted;
            }
        }
        pool.shutdown();  // 不等，直接关
        check(ran.load() == accepted,
              "提交后立刻 shutdown：已接受的 " + to_string(accepted) + " 个全部执行完才退出");
    }

    // 4) 任务抛异常不杀死 worker
    {
        BoundedThreadPool pool(2, 16);
        std::atomic<bool> after{false};
        pool.submit([] { throw std::runtime_error("boom"); });
        pool.submit([&after] { after.store(true); });
        for (int i = 0; i < 3000 && !after.load(); ++i) {
            std::this_thread::sleep_for(std::chrono::milliseconds(1));
        }
        check(after.load(), "前面的任务抛异常，后面的任务照常执行");
    }

    // 5) 带返回值的提交
    {
        BoundedThreadPool pool(4, 64);
        auto f1 = pool.submitFuture([](int a, int b) { return a * b; }, 6, 7);
        auto f2 = pool.submitFuture([] { return string("ok"); });
        check(f1.get() == 42 && f2.get() == "ok", "submitFuture 支持任意返回类型（int / string）");

        auto f3 = pool.submitFuture([]() -> int { throw std::runtime_error("x"); });
        bool threw = false;
        try {
            f3.get();
        } catch (const std::runtime_error&) {
            threw = true;
        }
        check(threw, "任务异常存进 future，get() 时原样抛出（packaged_task 的语义）");
    }

    // 6) 空任务、0 线程/0 容量等边界不崩
    {
        BoundedThreadPool pool(0, 0);  // 内部各自兜底成 1
        check(!pool.submit(std::function<void()>()), "提交空 std::function 返回 false");
        std::atomic<int> ran{0};
        const bool ok = pool.submit([&ran] { ran.fetch_add(1); }) && waitUntil(ran, 1);
        check(ok, "workers=0 / capacity=0 时仍能正常跑一个任务");
    }

    cout << (failed == 0 ? "algo_bounded_thread_pool: all checks passed"
                         : "algo_bounded_thread_pool: FAILED")
         << endl;
    return failed == 0 ? 0 : 1;
}
