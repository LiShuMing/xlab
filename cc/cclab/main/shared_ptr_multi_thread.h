
#include "stdio.h"

#include <vector>
#include <unordered_map>
#include <iostream>
#include <memory>

#include <chrono>
#include <thread>
#include <mutex>

using namespace std;

class Class1  {
    unordered_map<int, vector<shared_ptr<int>>> data_;
    mutex m1;
public:
    void change_data() {
        //lock_guard<mutex> l(m1);
        vector<shared_ptr<int>> t;
        for (int i = 0; i < 10; i++) {
            t.emplace_back(make_shared<int>(i));
        }
        data_[0] = std::move(t);
    }

    vector<shared_ptr<int>>* f1(int k) {
        return &data_[k];
    }
};
Class1 a;

void func1() {
    while (true) {
        cout<<"thread_id::"<< this_thread::get_id()<<"\n";
        auto* ret = a.f1(0);
        for (auto a: *ret) {
            cout<<"a:"<<*a<<",";
            *a = *a + 1;
        }
        cout<<endl;
    }
}

void func2() {
    while (true) {
        a.change_data();
        // this_thread::sleep_for(chrono::seconds(2));
    }
}

//int main() {
//    // how to wait it finish?
//    a.change_data();
//    func1();
//
//    thread t1(func1);
//    thread t2(func1);
//    thread t3(func2);
//    t1.join();
//    t2.join();
//    t3.join();
//}
//
