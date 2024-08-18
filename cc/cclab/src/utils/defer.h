#pragma once

#include "env.h"

namespace xlab {

class Defer {
  public:
    typedef std::function<void()> task;

  public:
    explicit Defer(const task &t = nullptr) : cancel_(false), t_(t) {}

    ~Defer() {
        if (!cancel_ && t_) {
            t_();
        }
    }

  public:
    void cancel() { cancel_ = true; }

  private:
    Defer(const Defer &);
    Defer &operator=(const Defer &);

  private:
    bool cancel_;
    task t_;

}; // class defer

}; // namespace xlab
