#include <gtest/gtest.h>

#include <array>
#include <chrono>
#include <iostream>
#include <mutex>
#include <random>
#include <thread>
#include <vector>

using namespace std;

template <class L0, class L1>
void lock1(L0& l0, L1& l1) {
    while (true) {
        {
            std::unique_lock<L0> u0(l0);
            if (l1.try_lock()) {
                break;
            }
        }

        std::this_thread::yield();
        {
            std::unique_lock<L1> u1(l1);
            if (l0.try_lock()) {
                break;
            }
        }
        std::this_thread::yield();
    }
}

template <class L0, class L1>
void lock2(L0& l0, L1& l1) {
    while (true) {
        {
            std::unique_lock<L0> u0(l0);
            if (l1.try_lock()) {
                break;
            }
        }
        {
            std::unique_lock<L1> u1(l1);
            if (l0.try_lock()) {
                break;
            }
        }
    }
}

template <class L0, class L1>
void lock3(L0& l0, L1& l1) {
    while (true) {
        std::unique_lock<L0> u0(l0);
        if (l1.try_lock()) {
            break;
        }
    }
}

template <class L0>
void lock4(L0& l0, L0& l1) {
    if (l0.mutex() < l1.mutex()) {
        std::unique_lock<L0> u0(l0);
        l1.lock();
    } else {
        std::unique_lock<L0> u1(l1);
        l0.lock();
    }
}

// 3 seconds

class Philosopher {
private:
    // random device
    std::mt19937_64 eng_ {std::random_device {}()};

    // philosopher id
    int id_;
    // lock type
    int lock_type_;
    // left fork
    std::mutex& lf_;
    // right fork
    std::mutex& rf_;
    // eat time
    std::chrono::seconds eat_time_ {0};

    // each philosopher needs to eat for 3 seconds
    static const int MAX_EAT_TIME = 3;
    static constexpr std::chrono::seconds full_ {MAX_EAT_TIME};

public:
    Philosopher(int id, int lock_type, std::mutex& left, std::mutex& right)
            : id_(id), lock_type_(lock_type), lf_(left), rf_(right) {}

    void dine() {
        while (eat_time_ < full_) {
            std::this_thread::sleep_for(100ms);
            _eat();
        }
    }

private:
    void _eat() {
        using Lock = std::unique_lock<std::mutex>;
        Lock l;
        Lock r;
        if (_flip_coin()) {
            l = Lock(lf_, std::defer_lock);
            r = Lock(rf_, std::defer_lock);
        } else {
            l = Lock(rf_, std::defer_lock);
            r = Lock(lf_, std::defer_lock);
        }
        auto d = _get_eat_duration();
        // call lock with the two locks
        cout << "id:" << id_ << ",  wait to lock\n";

        switch (lock_type_) {
            case 1:
                lock1(l, r);
                break;
            case 2:
                lock2(l, r);
                break;
            case 3:
                lock3(l, r);
                break;
            default:
                lock4(l, r);
                break;
        }

        cout << "id:" << id_ << ", locked, start to eat\n";
        auto end = std::chrono::steady_clock::now() + d;
        while (std::chrono::steady_clock::now() < end) {
            //thread::yield();
            // std::this_thread::yield();
            std::this_thread::sleep_for(100ms);
        }
        eat_time_ += d;
        cout << "id:" << id_ << ", after eating, duration: " << eat_time_.count() << "s\n";
    }

    bool _flip_coin() {
        std::bernoulli_distribution d;
        return d(eng_);
    }

    std::chrono::seconds _get_eat_duration() {
        std::uniform_int_distribution<> ms(1, MAX_EAT_TIME);
        return std::min(std::chrono::seconds(ms(eng_)), full_ - eat_time_);
    }
};

// Basic Test
class DiningLockTest : public testing::Test {
public:
    void test_lock(int lock_type) {
        const unsigned nt = 5;
        vector<std::mutex> tables(nt);
        vector<Philosopher> diners;

        for (unsigned i = 0; i < tables.size(); ++i) {
            int k = i < nt - 1 ? i + 1 : 0;
            diners.push_back(Philosopher(i, lock_type, tables[i], tables[k]));
        }
        std::vector<std::thread> threads(nt);
        unsigned i = 0;
        auto t0 = std::chrono::high_resolution_clock::now();
        for (int i = 0; i < nt; ++i) {
            threads[i] = std::thread(&Philosopher::dine, diners[i]);
        }
        for (auto& t : threads) {
            t.join();
        }
        auto t1 = std::chrono::high_resolution_clock::now();
        using secs = std::chrono::duration<float>;
        cout << "nt = " << nt << " : " << secs(t1 - t0).count() << endl;
    }
};

TEST_F(DiningLockTest, TestLock1) {
    test_lock(1);
}
TEST_F(DiningLockTest, TestLock2) {
    test_lock(2);
}
TEST_F(DiningLockTest, TestLock3) {
    test_lock(3);
}
TEST_F(DiningLockTest, TestLock4) {
    test_lock(4);
}

int main(int argc, char** argv) {
    ::testing::InitGoogleTest(&argc, argv);
    return RUN_ALL_TESTS();
}