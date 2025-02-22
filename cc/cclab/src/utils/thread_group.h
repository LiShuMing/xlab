// 线程池，添加异步任务时支持 指定线程号 和 池内自动调度 两种方式。
// 指定线程号方式
//   将任务按业务方自身需求分类打到固定线程中执行。
//   适用于同类任务要求顺序执行的场景，
//   且由于同类任务串行执行，业务方可以少一些锁。
//   任务映射成唯一index的方法放在业务放自己实现，业务方可根据自身业务（比如user id）或者使用xlab::hash（见xlab_hash.hpp）。
// 池内自动调度方式
//   支持round-robin轮转循环，随机，当前最空闲（即未完成任务数最少）线程三种方式。
//   适用于任务不要求强顺序性执行的场景。

#pragma once

#include <string>
#include <vector>
#include <assert.h>
#include <stdio.h>
#include <sstream>


#include "env.h"
#include "task_thread.h"

namespace xlab {

  class ThreadGroup {
    public:
      /// 当添加异步任务时没有指定线程号，内部的调度策略
      enum inner_dispatch_strategy {
        INNER_DISPATCH_STRATEGY_ROUND_ROBIN=1, /// 轮转循环指派给池里的线程
        INNER_DISPATCH_STRATEGY_RANDOM,        /// 随机指派给池里的线程
        INNER_DISPATCH_STRATEGY_IDLE           /// 指派给池里当前任务数最小的线程（如果有多个线程任务数最小，则选取线程号最小的）
      };

      typedef std::function<void()> task;

    public:
      explicit ThreadGroup(uint32_t num_of_thread,
                            inner_dispatch_strategy strategy=INNER_DISPATCH_STRATEGY_ROUND_ROBIN,
                            const std::string &thread_prefix_name=std::string());
      ~ThreadGroup();

    public:
      /// 开启后台线程池，非阻塞函数
      void start();

      /**
       * 添加异步任务，非阻塞函数
       * 任务执行策略取决于构造时配置的inner_dispatch_strategy
       *
       */
      void add(const task &t);

      /// 添加异步任务时指定线程号（内部用<index>对线程数取余得到线程号）
      void add(const task &t, uint32_t index);

      /// 返回还没执行完的任务数量
      uint64_t num_of_undone_task();

    private:
      ThreadGroup(const ThreadGroup &);
      ThreadGroup &operator=(const ThreadGroup &);

    private:
      typedef std::vector<std::shread_ptr<xlab::task_thread> > thread_vector;

    private:
      uint32_t                num_of_thread_;
      inner_dispatch_strategy strategy_;
      std::string             thread_prefix_name_;
      thread_vector           threads_;
      uint32_t                round_robin_index_;

  }; // class ThreadGroup

} // namespace xlab


namespace xlab {

  inline ThreadGroup::ThreadGroup(uint32_t num_of_thread, inner_dispatch_strategy strategy, const std::string &thread_prefix_name)
    : num_of_thread_(num_of_thread)
    , strategy_(strategy)
    , thread_prefix_name_(thread_prefix_name)
    , round_robin_index_(0)
  {
    assert(num_of_thread > 0);

    for (uint32_t i = 0; i < num_of_thread; i++) {
      std::ostringstream ss;
      ss << thread_prefix_name << i;
      threads_.push_back(std::make_shared<xlab::task_thread>(ss.str()));
    }

    srand((unsigned)time(0));
  }

  inline ThreadGroup::~ThreadGroup() {}

  inline void ThreadGroup::start() {
    for (uint32_t i = 0; i < num_of_thread_; i++) {
      threads_[i]->start();
    }
  }

  inline void ThreadGroup::add(const task &t) {
    if (strategy_ == INNER_DISPATCH_STRATEGY_ROUND_ROBIN) {
      add(t, round_robin_index_++);
    } else if (strategy_ == INNER_DISPATCH_STRATEGY_RANDOM) {
      add(t, rand());
    } else if (strategy_ == INNER_DISPATCH_STRATEGY_IDLE) {
      uint32_t min_index = 0;
      uint32_t min_undone = threads_[0]->num_of_undone_task();
      for (uint32_t i = 1; i < num_of_thread_; i++) {
        uint32_t undone = threads_[i]->num_of_undone_task();
        if (undone < min_undone) {
          min_index = i;
          min_undone = undone;
        }
      }
      add(t, min_index);
    }
  }

  inline void ThreadGroup::add(const task &t, uint32_t index) {
    threads_[index % num_of_thread_]->add(t);
  }

  inline uint64_t ThreadGroup::num_of_undone_task() {
    uint64_t ret = 0;
    for (uint32_t i = 0; i < num_of_thread_; i++) {
      ret += threads_[i]->num_of_undone_task();
    }
    return ret;
  }

} // namespace xlab
