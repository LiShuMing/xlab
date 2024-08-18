#include <gtest/gtest.h>

#include <atomic>
#include <cassert>
#include <cstring>
#include <functional>
#include <iostream>
#include <thread>
#include <vector>

using namespace std;

class Leetcode1116Test : public testing::Test {};

class ZeroEvenOdd {
  private:
    int n;
    condition_variable cv;
    mutex m1;
    // atomic<bool> flag = true;
    atomic<int> flag = 0;

  public:
    ZeroEvenOdd(int n) { this->n = n; }

    // printNumber(x) outputs "x", where x is an integer.
    void zero(function<void(int)> printNumber) {
        for (int i = 0; i < n; ++i) {
            unique_lock<mutex> l(m1);
            cv.wait(l, [&] {
                // cout << "Thread 0 waiting, flag: " << flag << ", count: " << i << endl;
                return flag == 0;
            });
            printNumber(0);
            flag = i % 2 + 1;
            cv.notify_all();
        }
    }

    void even(function<void(int)> printNumber) {
        for (int i = 2; i <= n; i += 2) {
            unique_lock<mutex> l(m1);
            cv.wait(l, [&] {
                // cout << "Thread 1 waiting, flag: " << flag << ", count: " << i << endl;
                return flag == 2;
            });
            printNumber(i);
            flag = 0;
            cv.notify_all();
        }
    }

    void odd(function<void(int)> printNumber) {
        for (int i = 1; i <= n; i += 2) {
            unique_lock<mutex> l(m1);
            cv.wait(l, [&] {
                // cout << "Thread 2 waiting, flag: " << flag << ", count: " << i << endl;
                return flag == 1;
            });
            printNumber(i);
            flag = 0;
            // count += 1;
            cv.notify_all();
        }
    }
};

TEST_F(Leetcode1116Test, Test1) {
    ZeroEvenOdd zeo(100);
    vector<thread> threads;
    threads.emplace_back([&] { zeo.zero([](int x) { cout << x; }); });
    threads.emplace_back([&] { zeo.even([](int x) { cout << x; }); });
    threads.emplace_back([&] { zeo.odd([](int x) { cout << x; }); });
    for (auto &t : threads) {
        t.join();
    }
    cout << endl;
}