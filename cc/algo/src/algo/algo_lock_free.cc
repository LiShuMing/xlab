#include "../include/fwd.h"

#include <atomic>
#include <memory>
#include <vector>
#include <functional>
#include <thread>
#include <mutex>
#include <condition_variable>
#include <algorithm>

template<typename T>
class RCUContainer {
private:
    struct RCUNode {
        std::shared_ptr<T> data;
        std::atomic<RCUNode*> next{nullptr};
        std::atomic<int> readers{0};
        explicit RCUNode(std::shared_ptr<T> d) : data(std::move(d)) {}
    };
    
    alignas(64) std::atomic<RCUNode*> current_;
    std::vector<RCUNode*> garbage_;
    static thread_local int reader_count_;
    
    // Use a dedicated thread for RCU synchronization and garbage cleanup
    std::thread cleanup_thread;
    std::mutex cleanup_mutex;
    std::condition_variable cleanup_cv;
    std::vector<RCUNode*> cleanup_queue;
    std::atomic<bool> should_stop_{false};

    void start_cleanup_thread() {
        cleanup_thread = std::thread([this]() {
            while (!should_stop_.load(std::memory_order_acquire)) {
                RCUNode* node_to_cleanup = nullptr;
                {
                    std::unique_lock<std::mutex> lock(cleanup_mutex);
                    cleanup_cv.wait(lock, [this]{ 
                        return !cleanup_queue.empty() || should_stop_.load(std::memory_order_acquire); 
                    });
                    if (should_stop_.load(std::memory_order_acquire)) {
                        break;
                    }
                    if (!cleanup_queue.empty()) {
                        node_to_cleanup = cleanup_queue.front();
                        cleanup_queue.erase(cleanup_queue.begin());
                    }
                }
                if (node_to_cleanup) {
                    // synchronize the RCU
                    synchronize_rcu();
                    // remove the node from garbage and delete it
                    {
                        std::lock_guard<std::mutex> lock(cleanup_mutex);
                        auto it = std::find(garbage_.begin(), garbage_.end(), node_to_cleanup);
                        if (it != garbage_.end()) {
                            garbage_.erase(it);
                        }
                    }
                    delete node_to_cleanup;
                }
            }
        });
    }
    class ReaderGuard {
    public:
        explicit ReaderGuard(RCUNode* node) : node_(node) {
            if (node_) {
                // Use relaxed for counter increments - we only need atomicity, not ordering
                node_->readers.fetch_add(1, std::memory_order_relaxed);
                ++reader_count_;
            }
        }
        ~ReaderGuard() {
            if (node_) {
                // Use release to ensure all reads from the node complete before decrement
                node_->readers.fetch_sub(1, std::memory_order_release);
                --reader_count_;
            }
        }
        
        ReaderGuard(const ReaderGuard&) = delete;
        ReaderGuard& operator=(const ReaderGuard&) = delete;
        
    private:
        RCUNode* node_;
    };
    
public:
    RCUContainer() : current_(new RCUNode(nullptr)) {
        start_cleanup_thread();
    }
    
    ~RCUContainer() {
        // Stop cleanup thread
        should_stop_.store(true, std::memory_order_release);
        cleanup_cv.notify_one();
        if (cleanup_thread.joinable()) {
            cleanup_thread.join();
        }
        
        synchronize_rcu();
        delete current_.load(std::memory_order_acquire);
        for (auto* node : garbage_) {
            delete node;
        }
    }
    
    // Non-copyable
    RCUContainer(const RCUContainer&) = delete;
    RCUContainer& operator=(const RCUContainer&) = delete;
    
    std::shared_ptr<T> read() const {
        // Load current node once and protect it with ReaderGuard
        auto* node = current_.load(std::memory_order_acquire);
        ReaderGuard guard(node);
        // Return data from the protected node
        return node->data;
    }
    
    void update(std::shared_ptr<T> new_data) {
        auto* new_node = new RCUNode(std::move(new_data));
        // atomic exchange to update the current pointer
        auto* old_node = current_.exchange(new_node, std::memory_order_acq_rel);
        // add the old node to the garbage list (protected by mutex)
        {
            std::lock_guard<std::mutex> lock(cleanup_mutex);
            garbage_.push_back(old_node);
            cleanup_queue.push_back(old_node);
        }
        cleanup_cv.notify_one();
    }
    
    void synchronize_rcu() {
        // wait for all readers to complete
        // Use acquire to see all release operations from readers
        std::vector<RCUNode*> nodes_to_check;
        {
            std::lock_guard<std::mutex> lock(cleanup_mutex);
            nodes_to_check = garbage_;
        }
        for (auto* node : nodes_to_check) {
            while (node->readers.load(std::memory_order_acquire) > 0) {
                std::this_thread::yield();
            }
        }
    }
    
    static std::shared_ptr<T> fast_read(RCUNode* node) {
        ++reader_count_;
        node->readers.fetch_add(1, std::memory_order_relaxed);
        auto data = node->data;
        // Use release to ensure data is read before decrement
        node->readers.fetch_sub(1, std::memory_order_release);
        --reader_count_;
        return data;
    }
};

// Define the static thread_local member
template<typename T>
thread_local int RCUContainer<T>::reader_count_ = 0;

class TinyRCU {
public:
  void read_lock() noexcept {
    readers_.fetch_add(1, std::memory_order_acquire);
  }
  void read_unlock() noexcept {
    readers_.fetch_sub(1, std::memory_order_release);
  }

  // 等所有读者退出（宽限期）
  void synchronize() noexcept {
    while (readers_.load(std::memory_order_acquire) != 0) {
      std::this_thread::yield();
    }
  }

  // 延迟回收：先入队，合适时机批量释放
  // Note: This is not thread-safe. Caller must ensure single writer or external synchronization
  void retire(std::function<void()> fn) {
    retired_.push_back(std::move(fn));
  }

  // 写侧调用：等待宽限期后执行所有回收
  void flush() {
    synchronize();
    for (auto &fn : retired_) fn();
    retired_.clear();
  }

private:
  std::atomic<int> readers_{0};
  std::vector<std::function<void()>> retired_; // demo 简化：单写线程或外部保护
};

void test_rcu_container() {
    RCUContainer<int> container;
    std::vector<std::thread> threads;
    for (int i = 0; i < 10; ++i) {
        threads.emplace_back([&]() {
            container.update(std::make_shared<int>(i));
            std::cout << *container.read() << std::endl;
        });
    }
    for (auto& t : threads) {
        t.join();
    }
    std::cout << *container.read() << std::endl;
}
void test_tiny_rcu() {
    std::vector<std::thread> threads;
    for (int i = 0; i < 10; ++i) {
        threads.emplace_back([&]() {
            TinyRCU rcu;
            rcu.read_lock();
            rcu.read_unlock();
            rcu.synchronize();
        });
    }   
    for (auto& t : threads) {
        t.join();
    }
}
int main() {
    test_rcu_container();
    test_tiny_rcu();
    return 0;
}