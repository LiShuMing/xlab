#include <gtest/gtest.h>

#include <atomic>
#include <cassert>
#include <cstring>
#include <functional>
#include <iostream>
#include <thread>
#include <vector>

// Thread Test
class ThreadTest : public testing::Test {
public:
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

protected:
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

int main(int argc, char** argv) {
    ::testing::InitGoogleTest(&argc, argv);
    return RUN_ALL_TESTS();
}