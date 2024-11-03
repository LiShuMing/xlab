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

    // wait until condition is met
    while( !cond ) {
        cond_var.wait(lock1);
    }
    std::cout << "t4: condition met \n";
}

// Basic Test
class LockTest : public testing::Test {};

// test lock with multiple mutex
TEST_F(LockTest, TestWithMultiMutexes) {
    std::thread t1( Take_Locks ), t2( Take_Locks ), t3( Take_Locks );
    std::thread t4( Conditional_Code );

    std::cout << "threads started \n";

    {
        std::unique_lock<std::mutex> lock1(mutex1);
        std::cout << "mutex1 locked \n" << "setting condition/notify \n";
        cond = true;
        cond_var.notify_one();
        lock1.unlock();
        std::cout << "mutex1 unlocked \n";
    }

    done = true;
    t4.join(); t3.join(); t2.join(); t1.join();
}

void worker() {
    cout<<"thread:"<<this_thread::get_id()<<", start to work..."<<endl;

    {
        unique_lock<mutex> lk(m);
        cv.wait(lk, [] { return ready; });
        cout << "thread:" << this_thread::get_id() << ", wait done..." << endl;
        processed = true;
        cout << "2. processed done..." << endl;
        lk.unlock();
        cv.notify_one();
    }
}

TEST_F(LockTest, TestWorker) {
    thread t1(worker);
    string data = "berfore start ...";

    // no notify, but with condition set
    {
        lock_guard<mutex> lk(m);
        ready=true;
        cout << "1. ready to notify worker..." << endl;
    }

    {
        unique_lock<mutex> lk(m);
        cv.wait(lk, []{return processed;});
        cout << "3. processed done..." << endl;
    }
    cv.notify_one();
    cout << "main thread notify worker..." << endl;
    t1.join();
}

TEST_F(LockTest, TestMultiThreads1) {
    bool ready1 = true;
    bool ready2 = false;
    int k = 10;
    thread t1([&](){
        while(k > 0) {
            {
                unique_lock<mutex> lk(m);
                cv.wait(lk, [&] { return ready1; });

                cout << "thread:" << this_thread::get_id() << ", start to work..." << k << endl;
                ready1 = false;
                ready2 = true;
                k -= 1;
                lk.unlock();
                cv.notify_one();
            }
        }
    });

    thread t2([&]() {
        while (k > 0) {
            {
                unique_lock<mutex> lk(m);
                cv.wait(lk, [&] { return ready2; });

                cout << "thread:" << this_thread::get_id() << ", start to work..." << k << endl;
                ready2 = false;
                ready1 = true;

                k -= 1;
                lk.unlock();
                cv.notify_one();
            }
        }
    });

    //cv.notify_one();
    t1.join();
    t2.join();
}

TEST_F(LockTest, TestTwoThreads2) {
    int k = 100;
    bool exit = false;
    vector<thread> threads;
    for (int i = 0; i <10; i++) {
        thread t([&](int tid){
            while(k > 0) {
                {
                    unique_lock<mutex> lk(m);

                    // wait until k % 10 == tid or exit
                    cv.wait(lk, [&] { return exit || k % 10 == tid ; });

                    // only output when not exist
                    if (!exit) {
                        cout << "thread:" << tid << "," << this_thread::get_id()
                             << ", start to work..." << k << endl;
                    }

                    // next
                    k -= 1;

                    // check if exit
                    if (k <= 0) {
                        cout << "thread:" << tid << "," << this_thread::get_id() << ", exit..."
                             << endl;
                        exit = true;
                    }
                    // notify all since all threads are waiting
                    cv.notify_all();
                }
            }
        }, i);
        threads.push_back(move(t));
    }
    for (int i = 0; i < 10; i++) {
        threads[i].join();
    }
}

TEST_F(LockTest, TestMemoryBarrier1) {
    atomic<int> a(0);
    atomic<bool> is_ready = false;
    thread t1([&](){
        a.store(1, memory_order_relaxed);
        is_ready.store(true, memory_order_release);
    });

    thread t2([&](){
        while (!is_ready.load(memory_order_acquire)) {
            this_thread::yield();
        }
        cout << "a=" << a.load(memory_order_relaxed) << endl;
        GTEST_ASSERT_EQ(a.load(memory_order_relaxed), 1);
    });
    t1.join();
    t2.join();
}

TEST_F(LockTest, TestMemoryBarrier2) {
    atomic<int> a(100);
    atomic<bool> is_ready1 = true;
    atomic<bool> is_ready2 = false;
    thread t1([&](){
        while (a.load(memory_order_relaxed) > 0) {
            while (!is_ready1.load(memory_order_acquire)) {
                this_thread::yield();
            }
            cout << "thread:" << std::this_thread::get_id() << ", a:" << a.load(memory_order_relaxed) << endl;
            // a.store(1, memory_order_relaxed);
            a--;

            is_ready1.store(false, memory_order_release);
            is_ready2.store(true, memory_order_release);
        }
    });

    thread t2([&]() {
        while (a.load(memory_order_relaxed) > 0) {
            while (!is_ready2.load(memory_order_acquire)) {
                this_thread::yield();
            }
            cout << "thread:" << std::this_thread::get_id() << ", a:" << a.load(memory_order_relaxed) << endl;
            // a.store(1, memory_order_relaxed);
            a--;

            is_ready1.store(true, memory_order_release);
            is_ready2.store(false, memory_order_release);
        }
    });
    t1.join();
    t2.join();
}

int main(int argc, char** argv) {
    ::testing::InitGoogleTest(&argc, argv);
    return RUN_ALL_TESTS();
}