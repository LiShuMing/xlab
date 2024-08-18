#include <cmath>
#include <iostream>
#include <list>
#include <optional>
#include <random>
#include <unordered_map>
#include <vector>

#include "../include/fwd.h"

// Simplified Count-Min Sketch for TinyLFU.
// Uses 4-bit counters to save memory.
class TinyLFUSketch {
public:
    explicit TinyLFUSketch(size_t size) : size_(size), counters_(size, 0) {}

    // Increments the frequency estimation.
    void Increment(uint64_t hash) {
        // In practice, use 4 different hash functions or 4 different seeds.
        for (int i = 0; i < 4; ++i) {
            size_t idx = ComputeHash(hash, i) % size_;
            if (counters_[idx] < 15) { // 4-bit saturation at 15
                counters_[idx]++;
            }
        }
    }

    // Returns the estimated frequency.
    uint32_t Estimate(uint64_t hash) const {
        uint32_t min_freq = 15;
        for (int i = 0; i < 4; ++i) {
            size_t idx = ComputeHash(hash, i) % size_;
            min_freq = std::min(min_freq, static_cast<uint32_t>(counters_[idx]));
        }
        return min_freq;
    }

    // Halves all counters to implement aging.
    void Reset() {
        for (auto& c : counters_) {
            c >>= 1;
        }
    }

private:
    size_t ComputeHash(uint64_t key, int seed) const {
        // Use MurmurHash3 or simple mixing function.
        return key ^ (seed * 0x9e3779b9);
    }

    size_t size_;
    std::vector<uint8_t> counters_; // Each byte can store two 4-bit counters.
};

// A simple zipf distribution generator for demonstration
// First Principle: P(k) = (1/k^s) / sum(1/n^s)
class ZipfGenerator {
public:
    ZipfGenerator(int n, double s) : n_(n), s_(s) {
        double sum = 0;
        for (int i = 1; i <= n; ++i) sum += 1.0 / std::pow(i, s);
        for (int i = 1; i <= n; ++i) {
            probs_.push_back((1.0 / std::pow(i, s)) / sum);
        }
    }

    int Next(std::mt19937& gen) {
        std::discrete_distribution<> d(probs_.begin(), probs_.end());
        return d(gen) + 1; // Returns rank starting from 1
    }

private:
    int n_;
    double s_;
    std::vector<double> probs_;
};

void test_zipf_distribution() {
    std::mt19937 gen(42);

    // Normal Distribution: Expect values tightly around 50
    std::normal_distribution<> norm(50, 10);

    // Zipf Distribution: N=100 elements, s=1.0 (typical)
    ZipfGenerator zipf(100, 1.0);

    // Compare 1000 samples
    // In Normal, you will rarely see > 90 or < 10.
    // In Zipf, Rank 1 will appear ~100 times more than Rank 100.
}

class CountMinSketch {
public:
    CountMinSketch(size_t d, size_t w)
            : depth_(d), width_(w), table_(d, std::vector<uint64_t>(w, 0)) {
        for (size_t i = 0; i < d; i++) {
            seeds_.push_back(0x9e3779b97f4a7c15ULL + i * 13331);
        }
    }

    void add(const std::string& key, uint64_t count = 1) {
        uint64_t h = base_hash_(key);
        for (size_t i = 0; i < depth_; i++) {
            size_t idx = mix(h, seeds_[i]) % width_;
            table_[i][idx] += count;
        }
    }

    uint64_t estimate(const std::string& key) const {
        uint64_t h = base_hash_(key);
        uint64_t res = std::numeric_limits<uint64_t>::max();
        for (size_t i = 0; i < depth_; i++) {
            size_t idx = mix(h, seeds_[i]) % width_;
            res = std::min(res, table_[i][idx]);
        }
        return res;
    }

private:
    size_t depth_;
    size_t width_;
    std::vector<std::vector<uint64_t>> table_;
    std::vector<uint64_t> seeds_;

    std::hash<std::string> base_hash_;

    static uint64_t mix(uint64_t h, uint64_t seed) {
        h ^= seed;
        h ^= (h >> 33);
        h *= 0xff51afd7ed558ccdULL;
        h ^= (h >> 33);
        h *= 0xc4ceb9fe1a85ec53ULL;
        h ^= (h >> 33);
        return h;
    }
};

template<typename K, typename V>
class LRUCache {
public:
    explicit LRUCache(size_t capacity) : capacity_(capacity) {}

    void put(const K& key, const V& value) {
        auto it = cache_map_.find(key);
        if (it != cache_map_.end()) {
            it->second->second = value;
            cache_list_.splice(cache_list_.begin(), cache_list_, it->second);
            return;
        }
        if (cache_map_.size() >= capacity_) {
            cache_map_.erase(cache_list_.back().first);
            cache_list_.pop_back();
        }
        cache_list_.push_front(std::make_pair(key, value));
        cache_map_[key] = cache_list_.begin();
    }

    std::optional<V> get(const K& key) {
        auto it = cache_map_.find(key);
        if (it != cache_map_.end()) {
            // use splice to move the node to the front of the list
            cache_list_.splice(cache_list_.begin(), cache_list_, it->second);
            return it->second->second;
        }
        return std::nullopt;
    }

    bool contains(const K& key) const {
        return cache_map_.find(key) != cache_map_.end();
    }

    size_t size() const {
        return cache_map_.size();
    }

    size_t capacity() const {
        return capacity_;
    }

private:
    size_t capacity_;
    std::unordered_map<K, typename std::list<std::pair<K, V>>::iterator> cache_map_;
    std::list<std::pair<K, V>> cache_list_;
};

template<typename K, typename V>
class LRUKCache {
public:
    LRUKCache(size_t capacity, size_t k) : capacity_(capacity), k_(k) {}

    void put(const K& key, const V& value) {
        auto it = cache_map_.find(key);
        if (it != cache_map_.end()) {
            // Key exists - update value and handle access
            handle_access(it->second, key, value);
            return;
        }

        // New key - check if we need to evict
        if (total_size() >= capacity_) {
            evict();
        }

        // Add to history list with count = 1
        history_list_.push_front({key, value, 1, access_count_++});
        auto list_it = history_list_.begin();
        cache_map_[key] = {NodeType::HISTORY, list_it};
    }

    std::optional<V> get(const K& key) {
        auto it = cache_map_.find(key);
        if (it == cache_map_.end()) {
            return std::nullopt;
        }

        // Get node and update access info
        auto& node = *it->second.list_it;
        handle_access(it->second, key, node.value);
        return node.value;
    }

    bool contains(const K& key) const {
        return cache_map_.find(key) != cache_map_.end();
    }

    size_t size() const {
        return total_size();
    }

    size_t capacity() const {
        return capacity_;
    }

private:
    struct Node {
        K key;
        V value;
        size_t count;      // Access count
        size_t timestamp;  // Monotonic access timestamp
    };

    enum class NodeType { HISTORY, CACHE };

    struct MapValue {
        NodeType type;
        typename std::list<Node>::iterator list_it;
    };

    size_t capacity_;
    size_t k_;
    size_t access_count_ = 0;  // Monotonic counter for tie-breaking

    std::list<Node> history_list_;  // count < k, LRU order (front = most recent)
    std::list<Node> cache_list_;    // count >= k, ordered by k-th access time (front = most recent k-th access)
    std::unordered_map<K, MapValue> cache_map_;

    size_t total_size() const {
        return history_list_.size() + cache_list_.size();
    }

    void handle_access(MapValue& mv, const K& key, const V& value) {
        auto& node = *mv.list_it;
        node.value = value;      // Update value
        node.count++;            // Increment access count
        node.timestamp = access_count_++;

        if (mv.type == NodeType::HISTORY && node.count >= k_) {
            // Promote to cache list
            cache_list_.splice(cache_list_.begin(), cache_list_, mv.list_it);
            mv.type = NodeType::CACHE;
        } else if (mv.type == NodeType::HISTORY) {
            // Move to front in history list (most recent)
            history_list_.splice(history_list_.begin(), history_list_, mv.list_it);
        } else {
            // Move to front in cache list (most recent k-th access)
            cache_list_.splice(cache_list_.begin(), cache_list_, mv.list_it);
        }
    }

    void evict() {
        if (!history_list_.empty()) {
            // Evict least recent from history (back = oldest)
            auto& oldest = history_list_.back();
            cache_map_.erase(oldest.key);
            history_list_.pop_back();
        } else if (!cache_list_.empty()) {
            // Evict least recent k-th access from cache (back = oldest k-th access time)
            auto& oldest = cache_list_.back();
            cache_map_.erase(oldest.key);
            cache_list_.pop_back();
        }
    }
};

template<typename K, typename V>
class LFUCache {
public:
    explicit LFUCache(size_t capacity) : capacity_(capacity), min_freq_(0) {}

    void put(const K& key, const V& value) {
        if (capacity_ == 0) return;

        auto it = key_node_map_.find(key);
        if (it != key_node_map_.end()) {
            // Key exists - update value and increment frequency
            Node& node = it->second;
            node.value = value;
            node.freq++;
            // Move to higher frequency list
            freq_list_map_[node.freq].splice(
                freq_list_map_[node.freq].begin(),
                freq_list_map_[node.freq - 1],
                node.list_it
            );
            // Clean up empty old frequency list
            if (freq_list_map_[node.freq - 1].empty()) {
                freq_list_map_.erase(node.freq - 1);
                if (min_freq_ == node.freq - 1) {
                    min_freq_ = node.freq;
                }
            }
            return;
        }

        // New key - check if we need to evict
        if (key_node_map_.size() >= capacity_) {
            // Evict least frequently used (at min_freq_)
            auto& evict_list = freq_list_map_[min_freq_];
            auto evict_node_it = evict_list.back();
            key_node_map_.erase(evict_node_it.first);
            evict_list.pop_back();
            if (evict_list.empty()) {
                freq_list_map_.erase(min_freq_);
            }
        }

        // Insert new node with frequency = 1
        freq_list_map_[1].push_front(std::make_pair(key, value));
        auto list_it = freq_list_map_[1].begin();
        key_node_map_[key] = {value, 1, list_it};
        min_freq_ = 1;
    }

    std::optional<V> get(const K& key) {
        auto it = key_node_map_.find(key);
        if (it == key_node_map_.end()) {
            return std::nullopt;
        }

        // Increment frequency
        Node& node = it->second;
        size_t old_freq = node.freq;
        node.freq++;

        // Move to higher frequency list
        freq_list_map_[node.freq].splice(
            freq_list_map_[node.freq].begin(),
            freq_list_map_[old_freq],
            node.list_it
        );

        // Update iterator in map
        node.list_it = std::prev(freq_list_map_[node.freq].begin());

        // Clean up empty old frequency list
        if (freq_list_map_[old_freq].empty()) {
            freq_list_map_.erase(old_freq);
            if (min_freq_ == old_freq) {
                min_freq_ = node.freq;
            }
        }

        return node.value;
    }

    bool contains(const K& key) const {
        return key_node_map_.find(key) != key_node_map_.end();
    }

    size_t size() const {
        return key_node_map_.size();
    }

    size_t capacity() const {
        return capacity_;
    }

private:
    struct Node {
        V value;
        size_t freq;
        typename std::list<std::pair<K, V>>::iterator list_it;
    };

    size_t capacity_;
    size_t min_freq_;

    // key -> Node (value, freq, iterator to freq_list)
    std::unordered_map<K, Node> key_node_map_;
    // freq -> list of (key, value) in LRU order (front = most recent at this freq)
    std::map<size_t, std::list<std::pair<K, V>>> freq_list_map_;
};

void test_count_min_sketch() {
    CountMinSketch cms(/*d=*/4, /*w=*/64);

    // 高频元素
    for (int i = 0; i < 100000; i++) {
        cms.add("hot_key");
    }

    // 一堆低频元素
    for (int i = 0; i < 5000; i++) {
        cms.add("key_" + std::to_string(i));
    }

    std::cout << "hot_key estimate: " << cms.estimate("hot_key") << std::endl;
    std::cout << "key_42 estimate: " << cms.estimate("key_42") << std::endl;
    std::cout << "non_exist estimate: " << cms.estimate("not_exist") << std::endl;
}

void test_lru_cache() {
    LRUCache<std::string, uint64_t> lru(/*capacity=*/10);
    lru.put("key1", 1);
    lru.put("key2", 2);
    lru.put("key3", 3);
    std::cout << lru.get("key1").value_or(0) << std::endl;
    std::cout << lru.get("key2").value_or(0) << std::endl;
    std::cout << lru.get("key3").value_or(0) << std::endl;

    // Test with integer keys
    LRUCache<int, std::string> int_lru(/*capacity=*/5);
    int_lru.put(1, "one");
    int_lru.put(2, "two");
    std::cout << int_lru.get(1).value_or("not found") << std::endl;
}

void test_lruk_cache() {
    LRUKCache<std::string, uint64_t> lruk(/*capacity=*/10, /*k=*/2);
    lruk.put("key1", 1);
    lruk.put("key2", 2);
    lruk.put("key3", 3);
    std::cout << lruk.get("key1").value_or(0) << std::endl;
    std::cout << lruk.get("key2").value_or(0) << std::endl;
    std::cout << lruk.get("key3").value_or(0) << std::endl;
}

void test_lfu_cache() {
    LFUCache<std::string, uint64_t> lfu(/*capacity=*/10);
    lfu.put("key1", 1);
    lfu.put("key2", 2);
    lfu.put("key3", 3);
    std::cout << lfu.get("key1").value_or(0) << std::endl;
    std::cout << lfu.get("key2").value_or(0) << std::endl;
    std::cout << lfu.get("key3").value_or(0) << std::endl;
}

int main() {
    Cache cache;
    test_count_min_sketch();
    test_lru_cache();
    test_lruk_cache();
    test_lfu_cache();
    return 0;
}