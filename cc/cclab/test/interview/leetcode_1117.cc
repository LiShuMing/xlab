#include <gtest/gtest.h>

#include <atomic>
#include <cassert>
#include <cstring>
#include <functional>
#include <iostream>
#include <thread>
#include <vector>

using namespace std;

class Leetcode1117Test : public testing::Test {};

class H2O {
public:
    H2O() {
    }

    void hydrogen(function<void()> releaseHydrogen) {
        {
            unique_lock<mutex> l(m1);
            cv.wait(l, [this] { return h_count < 2; });
            h_count.fetch_add(1);
        }
        
        // releaseHydrogen() outputs "H". Do not change or remove this line.
        releaseHydrogen();

        {
            // unique_lock<mutex> lock(m2);
            if (h_count == 2 and o_count == 1) {
                h_count = 0;
                o_count = 0;
                cv.notify_all();
            }
        }

    }

    void oxygen(function<void()> releaseOxygen) {
        {
            unique_lock<mutex> l(m1);
            cv.wait(l, [this] { return o_count < 1; });
            o_count.fetch_add(1);
        }
        
        // releaseOxygen() outputs "O". Do not change or remove this line.
        releaseOxygen();
        {
            // unique_lock<mutex> lock(m2);
            if (h_count == 2 and o_count == 1) {
                h_count = 0;
                o_count = 0;
                cv.notify_all();
            }
        }
    }

  private:
    atomic<int> h_count = 0;
    atomic<int> o_count = 0;
    condition_variable cv;
    mutex m1;
    mutex m2;
};


TEST_F(Leetcode1117Test, Test1) {
    H2O h2o;
    vector<thread> threads;
    for (int i = 0; i < 10; ++i) {
        threads.emplace_back([&h2o] { h2o.hydrogen([] { cout << "H"; }); });
        threads.emplace_back([&h2o] { h2o.hydrogen([] { cout << "H"; }); });
        threads.emplace_back([&h2o] { h2o.oxygen([] { cout << "O"; }); });
    }
    for (auto& t : threads) {
        t.join();
    }
    cout << endl;
}