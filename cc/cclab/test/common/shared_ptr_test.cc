#include <gtest/gtest.h>

#include <atomic>
#include <chrono>
#include <condition_variable>
#include <iostream>
#include <memory>
#include <mutex>
#include <shared_mutex>
#include <thread>
#include <unordered_map>
#include <vector>

#include "stdio.h"

using namespace std;

class SharedPtrMap {
private:
    std::unordered_map<int, std::vector<std::shared_ptr<int>>> _data;
    std::shared_mutex _m1;

public:
    SharedPtrMap() {}

    void addValue(int key, int value) {
        std::unique_lock<std::shared_mutex> lock(_m1); // 独占锁
        _data[key].emplace_back(std::make_shared<int>(value));
    }

    void modifyValue(int key, int newValue) {
        std::unique_lock<std::shared_mutex> lock(_m1); // 独占锁
        auto it = _data.find(key);
        if (it != _data.end() && !it->second.empty()) {
            it->second[0] = std::make_shared<int>(newValue); // 修改第一个元素
        }
    }

    std::vector<std::shared_ptr<int>> getValues(int key) {
        std::shared_lock<std::shared_mutex> lock(_m1); // 共享锁
        auto it = _data.find(key);
        if (it != _data.end()) {
            return it->second;
        }
        return {}; // 返回空向量
    }

    void change_data() {
        vector<shared_ptr<int>> t;
        for (int i = 0; i < 10; i++) {
            t.emplace_back(make_shared<int>(i));
        }
        _data[0] = std::move(t);
    }

    void change__datalocked() {
        // NOTE: it's not safe to change data here, needs a lock
        {
            unique_lock<std::shared_mutex> l(_m1);
            change_data();
        }
    }

    shared_mutex* get_mutex() { return &_m1; }

    vector<shared_ptr<int>>* get_data(int k) {
        if (_data.find(k) == _data.end()) {
            return nullptr;
        } else {
            // NOTE: lock here to protect _data
            // unique_lock<mutex> l(_m1);
            return &_data[k];
        }
    }
};

void incrFunc(SharedPtrMap& a) {
    int i = 0;
    auto* m = a.get_mutex();
    while (true && i < 100) {
        unique_lock<std::shared_mutex> l(*m);
        auto* ret = a.get_data(0);
        if (ret == nullptr) {
            i += 1;
            continue;
        }

        cout << "thread_id::" << this_thread::get_id()
             << ", size:" << ret->size() << ", ";
        for (auto a : *ret) {
            cout << "a:" << *a << ",";
            *a = *a + 1;
        }
        cout << endl;
        i += 1;
    }
}

void changeDataFunc(SharedPtrMap& a) {
    int i = 0;
    auto* m = a.get_mutex();
    while (true && i < 100) {
        unique_lock<std::shared_mutex> l(*m);
        a.change_data();
        std::this_thread::sleep_for(chrono::milliseconds(100));
        i += 1;
    }
}

class PtrTest : public testing::Test {};
TEST_F(PtrTest, TestBasic) {
    SharedPtrMap a;
    // how to wait it finish?
    a.change_data();
    incrFunc(a);

    std::vector<std::thread> threads;

    thread t1(incrFunc, std::ref(a));
    thread t2(incrFunc, std::ref(a));
    thread t3(changeDataFunc, std::ref(a));

    threads.emplace_back(std::move(t1));
    threads.emplace_back(std::move(t2));
    threads.emplace_back(std::move(t3));

    for (auto& t : threads) {
        t.join();
    }
}