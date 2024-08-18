#include <gtest/gtest.h>

#include <atomic>
#include <chrono>
#include <condition_variable>
#include <iostream>
#include <mutex>
#include <thread>

using namespace std;
using namespace std::chrono_literals;

std::mutex m;

std::mutex m1, m2;
std::mutex mutex1, mutex2;

std::condition_variable cond_var;
std::condition_variable cv;
std::atomic<bool>done{false};
bool cond = false;
bool ready = false;
bool processed = false;

void f1() {
    while (true)
    {
        std::unique_lock<std::mutex> l1(m1, std::defer_lock);
        std::unique_lock<std::mutex> l2(m2, std::defer_lock);
        std::lock(l1, l2);
        std::cout << "f1 has the two locks\n";
        std::this_thread::sleep_for(100ms);
    }
}

void f2() {
    while (true)
    {
        std::unique_lock<std::mutex> l2(m2, std::defer_lock);
        std::unique_lock<std::mutex> l1(m1, std::defer_lock);
        std::lock(l2, l1);
        std::cout << "f2 has the two locks\n";
        std::this_thread::sleep_for(100ms);
    }
}

template<class L0>
void lock(L0& l0, L0& l1) {
    if (l0.mutex < l1.muxt) {
        unique_lock<L0> u0(l0);
        l1.lock();
        u0.realase();
    } else {
        unique_lock<L0> u1(l1);
        l0.lock();
        u1.release();
    }
}

void low_load() {
    std::thread t1(f1);
    std::thread t2(f2);
    t1.join();
    t2.join();
}

void Take_Locks()
{
    while( !done )
    {
        std::this_thread::sleep_for( 1s );

        std::unique_lock<std::mutex> lock1( mutex1, std::defer_lock );
        std::unique_lock<std::mutex> lock2( mutex2, std::defer_lock );
        std::lock( lock1, lock2 );
        std::cout << "Take_Locks id:" << this_thread::get_id() << " waiting \n";

        std::this_thread::sleep_for( 1s );
        lock1.unlock();
        lock2.unlock();
        std::cout << "Take_Locks id:" << this_thread::get_id() << " done. \n";
    }
}

void Conditional_Code()
{
    std::unique_lock<std::mutex> lock1( mutex1, std::defer_lock );
    std::unique_lock<std::mutex> lock2( mutex2, std::defer_lock );

    std::lock( lock1, lock2 );
    std::cout << "Conditional id:" << this_thread::get_id() << " waiting \n";

    while( !cond )
        cond_var.wait( lock1 );

    std::cout << "t4: condition met \n";
}

// Basic Test
class LockTest : public testing::Test {};

TEST_F(LockTest, bad_case) {
    std::thread t1( Take_Locks ), t2( Take_Locks ), t3( Take_Locks );
    std::thread t4( Conditional_Code );

    std::cout << "threads started \n";
    std::this_thread::sleep_for( 10s );

    std::unique_lock<std::mutex> lock1( mutex1 );
    std::cout << "mutex1 locked \n" ;
    std::this_thread::sleep_for( 5s );

    std::cout << "setting condition/notify \n";
    cond = true;
    cond_var.notify_one();
    std::this_thread::sleep_for( 5s );

    lock1.unlock();
    std::cout << "mutex1 unlocked \n";
    std::this_thread::sleep_for( 6s );

    done = true;
    t4.join(); t3.join(); t2.join(); t1.join();
}

void worker() {
    cout<<"thread:"<<this_thread::get_id()<<", start to work..."<<endl;

    unique_lock<mutex> lk(m);
    cv.wait(lk, [] {return ready;});
    cout<<"thread:"<<this_thread::get_id()<<", wait done..."<<endl;
    // data += "thread:"+ to_string(this_thread::get_id()) +" after processed.";
//    data += "thread after processed.";
    processed=true;
    lk.unlock();
    cv.notify_one();
}

TEST_F(LockTest, test_worker) {
    thread t1(worker);
    string data = "berfore start ...";
    {
        lock_guard<mutex> lk(m);
        ready=true;
    }
    {
        unique_lock<mutex> lk(m);
        cv.wait(lk, []{return processed;});
    }
    cout<<"wait 2s..."<<endl;
    this_thread::sleep_for(chrono::milliseconds(2000));
    cout<<"wait 2s done..."<<endl;

    cv.notify_one();
    t1.join();
}

int main(int argc, char** argv) {
    ::testing::InitGoogleTest(&argc, argv);
    return RUN_ALL_TESTS();
}