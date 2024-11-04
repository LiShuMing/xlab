
#pragma once

#include <deque>
#include <map>
#include <stdint.h>
#include <string>

#include <stdio.h>
#include <sys/time.h>
#include <time.h>
#ifdef __linux__
#include <sys/prctl.h>
#endif

#include "env.h"
#include "wait_event_counter.h"

namespace xlab {

/**
 * Starts a thread that can continuously add asynchronous tasks.
 * The tasks are executed serially, and the execution order is consistent with the addition order.
 * Supports adding delayed tasks.
 */
class TaskThread {
  public:
    typedef std::function<void()> task;

    // release mode when stopping the thread
    enum ReleaseMode {
        RELEASE_MODE_ASAP,            /// disable all tasks when stopping the thread
        RELEASE_MODE_DO_SHOULD_DONE,  /// do some tasks before timeout when stopping the thread
        RELEASE_MODE_DO_ALL_DONE,     /// do all tasks before stopping the thread
    };

  public:
    explicit TaskThread(const std::string &name = std::string(),
                        ReleaseMode rm = RELEASE_MODE_ASAP);
    ~TaskThread();

  public:
    /// start the background thread, non-blocking function
    void start();

    /// add an asynchronous task, non-blocking function, if defferred_time_ms is not 0, 
    /// execute after the specified milliseconds
    void add(const task &t, int defferred_time_ms = 0);

    /// stop the background thread and wait for it to finish
    void stop_and_join();

    uint64_t num_of_undone_task();

    std::string thread_name() const { return name_; }

  private:
    void run_in_thread_();

    /// collect the delayed tasks that should be executed at the scheduled time
    void append_expired_tasks_(std::deque<task> &tasks);

    uint64_t now_();

    /// execute all tasks in <tasks> and clear <tasks>
    void execute_tasks_(std::deque<task> &tasks);

    void execute_tasks_(std::multimap<uint64_t, task> &tasks);

  private:
    TaskThread(const TaskThread &);
    TaskThread &operator=(const TaskThread &);

  private:
    std::string name_;
    ReleaseMode release_mode_;
    std::atomic<bool> exit_flag_;
    std::shared_ptr<std::thread> thread_;
    std::deque<task> tasks_;
    std::multimap<uint64_t, task> defferred_tasks_;
    std::mutex mutex_;
    std::atomic<uint64_t> num_of_undone_task_;
    std::condition_variable cond_;
    xlab::WaitEventCounter runned_event_;

}; // class TaskThread

} // namespace xlab

namespace xlab {

inline TaskThread::TaskThread(const std::string &name, ReleaseMode rm)
    : name_(name), release_mode_(rm), exit_flag_(false), num_of_undone_task_(0) {}

inline TaskThread::~TaskThread() { stop_and_join(); }

inline void TaskThread::start() {
    thread_ = std::make_shared<std::thread>(std::bind(&TaskThread::run_in_thread_, this));
    runned_event_.wait();
}

inline void TaskThread::stop_and_join() {
    exit_flag_ = true;
    if (thread_) {
        thread_->join();
        thread_.reset();
    }
}

inline void TaskThread::add(const task &t, int defferred_time_ms) {
    num_of_undone_task_++;
    std::lock_guard<std::mutex> guard(mutex_);
    if (defferred_time_ms == 0) {
        tasks_.push_back(t);
    } else {
        defferred_tasks_.insert(std::pair<uint64_t, task>(now_() + defferred_time_ms, t));
    }
    cond_.notify_one();
}

inline uint64_t TaskThread::num_of_undone_task() { return num_of_undone_task_.load(); }

inline void TaskThread::run_in_thread_() {
#ifdef __linux__
    if (!name_.empty()) {
        prctl(PR_SET_NAME, name_.c_str());
    }
#endif

    runned_event_.notify();

    std::deque<task> collect_tasks;
    for (;;) {
        { /// enter lock scope
            std::unique_lock<std::mutex> lock(mutex_);
            for (; !exit_flag_ && tasks_.empty();) {
                cond_.wait_for(lock, std::chrono::milliseconds(100));
                if (!defferred_tasks_.empty()) {
                    break;
                }
            }
            /// collect tasks to execute
            if (!tasks_.empty()) {
                collect_tasks.swap(tasks_);
            }
            /// collect the delayed tasks that should be executed at the scheduled time
            if (!defferred_tasks_.empty()) {
                append_expired_tasks_(collect_tasks);
            }
            if (exit_flag_) {
                break;
            }
        } /// leave lock scope
        execute_tasks_(collect_tasks);
    }

    std::lock_guard<std::mutex> lock(mutex_);
    switch (release_mode_) {
    case RELEASE_MODE_ASAP:
        break;
    case RELEASE_MODE_DO_SHOULD_DONE:
        execute_tasks_(collect_tasks);
        break;
    case RELEASE_MODE_DO_ALL_DONE:
        execute_tasks_(collect_tasks);
        execute_tasks_(defferred_tasks_);
        break;
    }
}

inline void TaskThread::append_expired_tasks_(std::deque<task> &tasks) {
    if (defferred_tasks_.empty()) {
        return;
    }

    uint64_t now_ms = now_();

    std::multimap<uint64_t, task>::iterator iter = defferred_tasks_.begin();
    for (; iter != defferred_tasks_.end(); ++iter) {
        if (iter->first > now_ms) {
            break;
        }
        tasks.push_back(iter->second);
    }
    defferred_tasks_.erase(defferred_tasks_.begin(), iter);
}

inline void TaskThread::execute_tasks_(std::deque<task> &tasks) {
    for (; !tasks.empty();) {
        tasks.front()();
        num_of_undone_task_--;
        tasks.pop_front();
    }
}

inline void TaskThread::execute_tasks_(std::multimap<uint64_t, task> &tasks) {
    std::multimap<uint64_t, task>::iterator iter = tasks.begin();
    for (; iter != tasks.end(); ++iter) {
        iter->second();
        num_of_undone_task_--;
    }
    tasks.clear();
}

inline uint64_t TaskThread::now_() {
    struct timespec ts;
#if defined(CLOCK_REALTIME) && !defined(__MACH__)
    clock_gettime(CLOCK_MONOTONIC, &ts);
#else
    {
        struct timeval tv;
        gettimeofday(&tv, NULL);
        ts.tv_sec = tv.tv_sec;
        ts.tv_nsec = tv.tv_usec * 1000;
    }
#endif
    return ts.tv_sec * 1000 + ts.tv_nsec / 1000000;
}

} // namespace xlab