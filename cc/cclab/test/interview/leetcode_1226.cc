#include <gtest/gtest.h>

#include <atomic>
#include <cassert>
#include <cstring>
#include <functional>
#include <iostream>
#include <thread>
#include <vector>
#include <semaphore>

using namespace std;

class Leetcode1226Test : public testing::Test {};

class DiningPhilosophers {
private:
    mutex ms[5];
    counting_semaphore<5> sem{4};
public:
    DiningPhilosophers() {
        
    }

    void wantsToEat(int philosopher, function<void()> pickLeftFork, function<void()> pickRightFork,
                    function<void()> eat, function<void()> putLeftFork,
                    function<void()> putRightFork) {
        sem.acquire();
        int l = philosopher, r = (philosopher + 1) % 5;
        // lock the smaller mutex first
        // if (l > r) {
        //     swap(l, r);
        // }
        // lock_guard<mutex> l1(ms[l]), l2(ms[r]);
        scoped_lock l1(ms[l], ms[r]);

        pickLeftFork();
        pickRightFork();
        eat();
        putLeftFork();
        putRightFork();
        sem.release();
    }
};


TEST_F(Leetcode1226Test, Test1) {
    DiningPhilosophers dp;

    auto pickLeftFork = []() { cout << "Pick Left Fork\n"; };
    auto pickRightFork = []() { cout << "Pick Right Fork\n"; };
    auto eat = []() { cout << "Eating\n"; };
    auto putLeftFork = []() { cout << "Put Left Fork\n"; };
    auto putRightFork = []() { cout << "Put Right Fork\n"; };

    vector<thread> threads;
    for (int i = 0; i < 5; ++i) {
        threads.emplace_back(
                [&dp, i, pickLeftFork, pickRightFork, eat, putLeftFork, putRightFork]() {
                    dp.wantsToEat(i, pickLeftFork, pickRightFork, eat, putLeftFork, putRightFork);
                });
    }

    for (auto &t : threads)
        t.join();
}