#include "../include/fwd.h"

#include <iostream>
#include <random>
#include <vector>
#include <cmath>
#include <map>

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

/**
 * Cache implementation
 */
class Cache {
public:
    Cache() {
    }
};
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

    std::cout << "hot_key estimate: "
              << cms.estimate("hot_key") << std::endl;

    std::cout << "key_42 estimate: "
              << cms.estimate("key_42") << std::endl;

    std::cout << "non_exist estimate: "
              << cms.estimate("not_exist") << std::endl;

}


int main() {
    Cache cache;
    test_count_min_sketch();
    return 0;
}