#pragma once

#include "env.h"

namespace xlab {

// Block and wait for 1~N events to occur
// Optionally set a timeout, after which it will no longer block and wait
// Users do not need to worry about the details of thread synchronization implementation (such as
// the timing of event sending and receiving, atomic counting, spurious wakeups, etc.)

class WaitEventCounter {
  public:
    // param nc notify how many times to pass
    explicit WaitEventCounter(int nc = 1);
    ~WaitEventCounter();

  public:
    // non-blocking, notify calls occur before or during wait execution
    void notify();

    // wait until the specified <need_count_> times notify has occurred.
    void wait();

    /**
     * wait until the specified <need_count_> times notify has occurred or timed out.
     */
    bool wait_for(uint32_t timeout_ms);

  public:
    int need_count() const { return need_count_; }
    int counted() const { return counted_; }

  private:
    bool check_();

  private:
    WaitEventCounter(const WaitEventCounter &);
    WaitEventCounter operator=(const WaitEventCounter &);

  private:
    const int need_count_;
    std::atomic<int> counted_;
    std::mutex mutex_;
    std::condition_variable cond_;
};

} // namespace xlab

namespace xlab {

inline WaitEventCounter::WaitEventCounter(int nc) : need_count_(nc), counted_(0) {}

inline WaitEventCounter::~WaitEventCounter() {}

inline void WaitEventCounter::notify() {
    std::unique_lock<std::mutex> lock(mutex_);
    counted_++;
    cond_.notify_one();
}

inline void WaitEventCounter::wait() {
    std::unique_lock<std::mutex> lock(mutex_);
    for (; counted_.load() < need_count_;) {
        cond_.wait(lock);
    }
}

inline bool WaitEventCounter::wait_for(uint32_t timeout_ms) {
    if (timeout_ms == 0) {
        wait();
        return true;
    }

    std::unique_lock<std::mutex> lock(mutex_);
    return cond_.wait_for(lock, std::chrono::milliseconds(timeout_ms),
                          std::bind(&WaitEventCounter::check_, this));
}

inline bool WaitEventCounter::check_() { return this->counted_.load() >= need_count_; }

} // namespace xlab