#include <gtest/gtest.h>

#include <atomic>
#include <cassert>
#include <cstring>
#include <functional>
#include <iostream>
#include <thread>
#include <vector>

// Thread Test
using CpuIds = std::vector<int>;
struct WorkGroup {
    int id;
};

class ThreadTest : public testing::Test {
public:
    static constexpr WorkGroup* COMMON_WORKGROUP = nullptr;
    void f() {
        for (int n = 0; n < 1000; ++n) {
            cnt.fetch_add(1, std::memory_order_relaxed);
            // cnt += 1;
        }
    }
    void producer() {
        data = 100;                                   // A
        ready.store(true, std::memory_order_release); // B
    }
    void consumer() {
        while (!ready.load(std::memory_order_acquire)) // C
            ;
        ASSERT_EQ(data, 100); // never failed              // D
    }

    void thread1(int _a) {
        a = _a;
        b = a + 2;
        c = a + 3;
    }

    void thread2() { std::cout << "a=" << a << " b=" << b << " c=" << c << std::endl; }


    const CpuIds &get_cpuids_of_workgroup(WorkGroup *wg) const {
        static const CpuIds empty_cpuids;
        const auto it = _wg_to_cpuids.find(wg);
        if (it == _wg_to_cpuids.end()) {
            return empty_cpuids;
        }
        return it->second;
    }

protected:
    std::unordered_map<WorkGroup *, CpuIds> _wg_to_cpuids;
    std::atomic<int> cnt = {0};
    std::atomic<bool> ready{false};
    int data = 0;
    int a; int b; int c;
};

TEST_F(ThreadTest, TestBasic) {
    std::vector<std::thread> v;
    for (int n = 0; n < 10; ++n) {
        v.emplace_back(&ThreadTest::f, this);
    }
    for (auto& t : v) {
        t.join();
    }
    std::cout << "Final counter value is " << cnt << '\n';
    ASSERT_EQ(cnt, 10000);
}

TEST_F(ThreadTest, TestProducerConsuemer) {
    std::thread t1(&ThreadTest::producer, this);
    std::thread t2(&ThreadTest::consumer, this);
    t1.join();
    t2.join();
}

TEST_F(ThreadTest, TestThreadFunc1) {
    std::thread t1(&ThreadTest::thread1, this, 1);
    std::thread t2(&ThreadTest::thread2, this);
    t1.join();
    t2.join();
}

std::atomic<int> flag{0};
int data = 0;

static void producer() {
    data = 42;
    __asm__ __volatile__("" ::: "memory"); // 编译屏障
    flag.store(1, std::memory_order_relaxed);
}

static void consumer() {
    while (flag.load(std::memory_order_relaxed) == 0);
    __asm__ __volatile__("" ::: "memory"); // 编译屏障
    std::cout << "Data: " << data << std::endl; // 确保data读取的正确性
}

TEST_F(ThreadTest, TestMemoryBarrier) {
    std::thread t1(::producer);
    std::thread t2(::consumer);
    t1.join();
    t2.join();
}

thread_local int tls_i = 0;
TEST_F(ThreadTest, TestThreadLocal) {
    tls_i = 42;
    std::thread t1([]() {
        tls_i = 43;
        std::cout << "tls_i in thread: " << tls_i << std::endl;
    });
    t1.join();
    std::cout << "tls_i in main: " << tls_i << std::endl;
}

TEST_F(ThreadTest, TestAsanBug) {
    {
        _wg_to_cpuids[COMMON_WORKGROUP] = {1, 2, 3, 4, 5};
    }
    WorkGroup* wg = new WorkGroup{1};
    _wg_to_cpuids[wg] = {1, 2, 3, 4, 5};

    const auto& cpuids = get_cpuids_of_workgroup(wg);
    if (cpuids.empty()) {
        return;
    }

    // std::ranges::copy(cpuids, std::back_inserter(_wg_to_cpuids[COMMON_WORKGROUP]));
    // _wg_to_cpuids.erase(wg);

    // for (auto cpuid : cpuids) {
    //     std::cout << cpuid << std::endl;
    // }
}