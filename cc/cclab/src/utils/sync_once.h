#pragma once

#include <sstream>
#include <string>

namespace xlab {

class SyncOnce {
  public:
    void run(std::function<void()> f);

  private:
    std::atomic<bool> done_;
    std::mutex m_;
};

inline void SyncOnce::run(std::function<void()> f) {
    if (done_ == 0) {
        m_.lock();
        if (done_ == 0) {
            f();
            done_ = 1;
        }
        m_.unlock();
    }
}

} // namespace xlab
