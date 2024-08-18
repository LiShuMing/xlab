#include <gtest/gtest.h>

#include <atomic>
#include <cassert>
#include <cstring>
#include <functional>
#include <iostream>
#include <thread>
#include <vector>

using namespace std;

class Leetcode1115Test : public testing::Test {};

class FooBar {
private:
    int n;
    mutex m1;
    condition_variable cv;
    atomic<int> flag = 0;

public:
    FooBar(int n) {
        this->n = n;
    }

    void foo(function<void()> printFoo) {
        
        for (int i = 0; i < n; i++) {
            unique_lock<mutex> l(m1);
            cv.wait(l, [&] {
                return flag == 0;
            });
            
        	// printFoo() outputs "foo". Do not change or remove this line.
        	printFoo();
            flag = 1;
            cv.notify_all();
        }
    }

    void bar(function<void()> printBar) {
        
        for (int i = 0; i < n; i++) {
            unique_lock<mutex> l(m1);
            cv.wait(l, [&] {
                return flag == 1;
            });
            
        	// printBar() outputs "bar". Do not change or remove this line.
        	printBar();
            flag = 0;
            cv.notify_all();
        }
    }
};

TEST_F(Leetcode1115Test, Test1) {
    FooBar fb(20);
    vector<string> res;
    thread t1([&] {
        fb.foo([&] {
            res.push_back("foo");
        });
    });
    thread t2([&] {
        fb.bar([&] {
            res.push_back("bar");
        });
    });
    t1.join();
    t2.join();
    // ASSERT_EQ(res[0], "foo");
    // ASSERT_EQ(res[1], "bar");
    for (auto &s : res) {
        cout << s << endl;
    }
}