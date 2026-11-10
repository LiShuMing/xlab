#ifndef CACHE_LAB_REFERENCE_LRU_H_
#define CACHE_LAB_REFERENCE_LRU_H_

#include <cstddef>
#include <cstdint>
#include <memory>
#include <mutex>
#include <stdexcept>
#include <unordered_map>

#include "policies.h"

namespace cache_lab {

// CacheSystem's LruCache keeps one mutex, a hash index into a doubly linked list
// whose back link is weak_ptr, and the value inside the node. Reproducing that
// layout here makes the cost of the reference comparable to the lock-free
// policies: container, lock and payload, not a different eviction rule.
//
// The structure is written for this lab instead of vendored: the upstream
// repository ships no license file, so no upstream line is copied.
template <typename Key, typename Value>
class LockedLruCache {
private:
    struct Node {
        Node(const Key& node_key, const Value& node_value) : key(node_key), value(node_value) {}
        Key key;
        Value value;
        std::shared_ptr<Node> next;
        std::weak_ptr<Node> prev;
    };
    using NodePtr = std::shared_ptr<Node>;

public:
    explicit LockedLruCache(std::size_t capacity) : capacity_(capacity) {
        head_ = std::make_shared<Node>(Key(), Value());
        tail_ = std::make_shared<Node>(Key(), Value());
        head_->next = tail_;
        tail_->prev = head_;
    }

    // Returns true and writes the resident value when the key is present.
    bool Get(const Key& key, Value& value) {
        std::lock_guard<std::mutex> lock(mutex_);
        auto it = index_.find(key);
        if (it == index_.end()) return false;
        Unlink(it->second);
        AppendMostRecent(it->second);
        value = it->second->value;
        return true;
    }

    // Inserts or refreshes key; a full cache drops the oldest entry first.
    void Put(const Key& key, const Value& value) {
        if (capacity_ == 0) return;
        std::lock_guard<std::mutex> lock(mutex_);
        auto it = index_.find(key);
        if (it != index_.end()) {
            it->second->value = value;
            Unlink(it->second);
            AppendMostRecent(it->second);
            return;
        }
        while (index_.size() >= capacity_) {
            NodePtr victim = head_->next;
            Unlink(victim);
            index_.erase(victim->key);
        }
        NodePtr node = std::make_shared<Node>(key, value);
        AppendMostRecent(node);
        index_.emplace(key, node);
    }

private:
    void Unlink(const NodePtr& node) {
        NodePtr previous = node->prev.lock();
        if (!previous || !node->next) return;
        previous->next = node->next;
        node->next->prev = previous;
        node->next = nullptr;
    }

    void AppendMostRecent(const NodePtr& node) {
        node->next = tail_;
        node->prev = tail_->prev;
        tail_->prev.lock()->next = node;
        tail_->prev = node;
    }

    const std::size_t capacity_;
    NodePtr head_, tail_;
    std::mutex mutex_;
    std::unordered_map<Key, NodePtr> index_;
};

// Benchmark adapter: read-through with a stored-value round trip, so a payload
// corrupted by the cache counts as an error instead of a hit.
class ReferenceLru {
public:
    explicit ReferenceLru(std::size_t capacity) : capacity_(capacity), cache_(capacity) {}

    bool Access(Key key) {
        std::uint64_t value = 0;
        if (cache_.Get(key, value)) {
            if (value != (key ^ kValueSalt))
                throw std::runtime_error("reference value mismatch");
            return true;
        }
        if (capacity_ != 0) {
            cache_.Put(key, key ^ kValueSalt);
            ++events_.admissions;
            if (size_ == capacity_)
                ++events_.evictions;
            else
                ++size_;
        }
        return false;
    }

    Layout GetLayout() const { return {size_}; }
    Events GetEvents() const { return events_; }

private:
    static constexpr std::uint64_t kValueSalt = 0xa5a5a5a5a5a5a5a5ULL;
    std::size_t capacity_;
    std::size_t size_ = 0;
    LockedLruCache<Key, std::uint64_t> cache_;
    Events events_;
};

} // namespace cache_lab

#endif
