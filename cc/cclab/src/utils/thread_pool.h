#pragma once

#include <deque>
#include <string>
#include <vector>
#include <assert.h>
#include <stdio.h>

#ifdef __linux__
#include <sys/prctl.h>
#endif

#include "wait_event_counter.h"
#include "env.h"

namespace xlab {

/**
 * Thread pool, idle threads in the pool preemptively execute added tasks.
 * Suitable for scenarios where tasks do not require strict sequential execution.
 */
class ThreadPool {
  public:
    typedef std::function<void()> task;

  public:
    explicit ThreadPool(uint32_t num_of_thread,
                        const std::string &thread_prefix_name = std::string());

    /**
     * - When destructing, it will wait for all background threads to finish, i.e., the tasks being executed need to be completed (of course), 
     *   but tasks that have not started will not be executed (for the sake of releasing resources quickly), 
     *   so it may block for a while (depending on the complexity of the tasks being executed)~
     * - Additionally, users should not assume that tasks added via add will definitely be executed before the ThreadPool is destructed. 
     *   If you have such a scenario, it is recommended to add a synchronization statement at the end of the task, such as using xlab_WaitEventCounter~
     */
    ~ThreadPool();

  public:
    // start the background thread pool, non-blocking function
    void start();

    // add an asynchronous task, non-blocking function
    void add(const task &t);

    // return the number of tasks that have not been executed yet
    uint64_t num_of_undone_task();

  private:
    void run_in_thread_(int index);
    task take_();

  private:
    ThreadPool(const ThreadPool &);
    ThreadPool &operator=(const ThreadPool &);

  private:
    typedef std::vector<std::shread_ptr<xlab::thread>> thread_vector;
    typedef std::vector<std::shread_ptr<xlab::WaitEventCounter>> wait_event_vector;

  private:
    // number of threads
    uint32_t num_of_thread_;
    // thread prefix name
    std::string thread_prefix_name_;
    // exit flag
    bool exit_flag_;
    // thread pool
    thread_vector threads_;
    // used to notify the thread pool that the thread is ready
    wait_event_vector thread_runned_events_;
    // task queue
    // tasks are not protected by mutex, so the task queue is not thread-safe
    // tasks are not limited in size, so the task queue is not size-limited
    std::deque<task> tasks_;
    // thread pool mutex
    std::mutex mutex_;
    // the number of tasks that have not been executed yet
    std::atomic<uint64_t> num_of_undone_task_;
    // used to wake up the thread pool in case of new tasks are empty or added
    xlab::condition_variable cond_;
};

} // namespace xlab


namespace xlab {

inline ThreadPool::ThreadPool(uint32_t num_of_thread, const std::string &thread_prefix_name)
    : num_of_thread_(num_of_thread), thread_prefix_name_(thread_prefix_name), exit_flag_(false),
      num_of_undone_task_(0) {
    assert(num_of_thread > 0);
}

inline ThreadPool::~ThreadPool() {
    exit_flag_ = true;
    cond_.notify_all();
    for (uint32_t i = 0; i < num_of_thread_; i++) {
        threads_[i]->join();
    }
}

inline void ThreadPool::start() {
    for (uint32_t i = 0; i < num_of_thread_; i++) {
        thread_runned_events_.push_back(std::make_shared<xlab::WaitEventCounter>());

        // add a thread to the thread pool
        threads_.push_back(
                std::make_shared<xlab::thread>(std::bind(&ThreadPool::run_in_thread_, this, i)));

        // wait for the thread to be ready
        thread_runned_events_[i]->wait();
    }
}

inline void ThreadPool::add(const task &t) {
    num_of_undone_task_++;
    std::unique_lock<std::mutex> lock(mutex_);
    tasks_.push_back(t);
    // wake up one thread
    cond_.notify_one();
}

inline uint64_t ThreadPool::num_of_undone_task() { return num_of_undone_task_.load(); }

inline void ThreadPool::run_in_thread_(int index) {
#ifdef __linux__
    if (!thread_prefix_name_.empty()) {
        char thread_name[32] = {0};
        snprintf(thread_name, 31, "%s%d", thread_prefix_name_.c_str(), index + 1);
        ::prctl(PR_SET_NAME, thread_name);
    }
#endif

    // only notify after the thread is ready
    thread_runned_events_[index]->notify();

    //printf("thread %d start\n", index);

    for (; !exit_flag_;) {
        task t(take_());
        if (t) {
            t();
            num_of_undone_task_--;
        }
    }
}

inline ThreadPool::task ThreadPool::take_() {
    std::unique_lock<std::mutex> lock(mutex_);
    for (; !exit_flag_ && tasks_.empty();) {
        cond_.wait(lock);
    }
    task t;
    if (!tasks_.empty()) {
        t = tasks_.front();
        tasks_.pop_front();
    }
    return t;
}

} // namespace xlab