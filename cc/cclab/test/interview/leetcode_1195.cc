#include <gtest/gtest.h>

#include <atomic>
#include <cassert>
#include <cstring>
#include <functional>
#include <iostream>
#include <thread>
#include <vector>

using namespace std;

class Leetcode1195Test : public testing::Test {};

class FizzBuzz {
  private:
    int n;
    mutex m1;
    condition_variable cv;
    atomic<int> cnt = 1;

  public:
    FizzBuzz(int n) { this->n = n; }

    // printFizz() outputs "fizz".
    void fizz(function<void()> printFizz) {
        while (cnt <= n) {
            unique_lock<mutex> l(m1);
            cv.wait(l, [&] {
                cout << "thread 1 waiting, cnt: " << cnt << endl;
                return cnt > n || (cnt % 3 == 0 and cnt % 5 != 0);
            });
            if (cnt > n) {
                break;
            }
            printFizz();
            cnt++;
            cv.notify_all();
        }
    }

    // printBuzz() outputs "buzz".
    void buzz(function<void()> printBuzz) {
        while (cnt <= n) {
            unique_lock<mutex> l(m1);
            cv.wait(l, [&] {
                cout << "thread 2 waiting, cnt: " << cnt << endl;
                return cnt > n || (cnt % 3 != 0 and cnt % 5 == 0);
            });

            if (cnt > n) {
                break;
            }
            printBuzz();
            cnt++;
            cv.notify_all();
        }
    }

    // printFizzBuzz() outputs "fizzbuzz".
    void fizzbuzz(function<void()> printFizzBuzz) {
        while (cnt <= n) {
            unique_lock<mutex> l(m1);
            cv.wait(l, [&] {
                cout << "thread 3 waiting, cnt: " << cnt << endl;
                return cnt > n || (cnt % 3 == 0 and cnt % 5 == 0);
            });
            if (cnt > n) {
                break;
            }
            printFizzBuzz();
            cnt++;
            cv.notify_all();
        }
    }

    // printNumber(x) outputs "x", where x is an integer.
    void number(function<void(int)> printNumber) {
        while (cnt <= n) {
            unique_lock<mutex> l(m1);
            cv.wait(l, [&] {
                cout << "thread 4 waiting, cnt: " << cnt << endl;
                return cnt > n || (cnt % 3 != 0 and cnt % 5 != 0);
            });
            if (cnt > n) {
                break;
            }
            printNumber(cnt);
            cnt++;
            cv.notify_all();
        }
    }
};


TEST_F(Leetcode1195Test, Test1) {
    FizzBuzz fb(15);
    vector<string> res;
    thread t1([&] { fb.fizz([&] { res.push_back("fizz"); }); });
    thread t2([&] { fb.buzz([&] { res.push_back("buzz"); }); });
    thread t3([&] { fb.fizzbuzz([&] { res.push_back("fizzbuzz"); }); });
    thread t4([&] { fb.number([&](int i) { res.push_back(to_string(i)); }); });
    t1.join();
    t2.join();
    t3.join();
    t4.join();
    for (auto &s : res) {
        cout << s << endl;
    }
    // vector<string> expected = {"1",    "2",    "fizz", "4",    "buzz", "fizz", "7",       "8",
    //                            "fizz", "buzz", "11",   "fizz", "13",   "14",   "fizzbuzz"};
    // for (int i = 0; i < expected.size(); i++) {
    //     EXPECT_EQ(res[i], expected[i]);
    // }
}