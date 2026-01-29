#include "../include/fwd.h"

/**
Design a data structure that follows the constraints of a Least Recently Used (LRU) cache.

Implement the LRUCache class:

LRUCache(int capacity) Initialize the LRU cache with positive size capacity.
int get(int key) Return the value of the key if the key exists, otherwise return -1.
void put(int key, int value) Update the value of the key if the key exists. Otherwise, add the key-value pair to the cache. If the number of keys exceeds the capacity from this operation, evict the least recently used key.
 */
class LRUCache {
private:
    int capacity_;
    unordered_map<int, pair<int, typename list<int>::iterator>> cache_;
    list<int> keys_;

    void evict() {
        if (cache_.size() >= capacity_) {
            int key = keys_.back();
            keys_.pop_back();
            cache_.erase(key);
        }
    }
public:
    LRUCache(int capacity) : capacity_(capacity) {}

    int get(int key) {
        auto it = cache_.find(key);
        if (it == cache_.end()) {
            return -1;
        }
        keys_.splice(keys_.begin(), keys_, it->second.second);
        return it->second.first;
    }

    void put(int key, int value) {
        auto it = cache_.find(key);
        if (it != cache_.end()) {
            it->second.first = value;
            keys_.splice(keys_.begin(), keys_, it->second.second);
            return;
        }
        if (cache_.size() >= capacity_) {
            evict();
        }
        keys_.push_front(key);
        cache_[key] = {value, keys_.begin()};
    }
};