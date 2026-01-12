#ifndef VAGG_HT_HASH_TABLE_H_
#define VAGG_HT_HASH_TABLE_H_

#include <cstddef>
#include <cstdint>
#include <memory>
#include <vector>

#include "vagg/common/likely.h"
#include "vagg/ht/hash.h"

namespace vagg {

// Forward declaration
template <typename Key, typename Value>
class HashTable;

// Entry in the hash table
template <typename Key, typename Value>
struct HashTableEntry {
  Key key;
  Value value;
  uint64_t hash;  // Stored hash for verification
  bool occupied;
};

// Configuration for hash table
struct HashTableConfig {
  size_t capacity = 4096;          // Initial capacity
  double max_load_factor = 0.7;    // Trigger rehash at this load
  bool store_hash = true;          // Store hash for faster comparison
};

// Statistics for the hash table
struct HashTableStats {
  size_t num_entries = 0;
  size_t num_probes = 0;
  size_t num_collisions = 0;
  size_t num_resizes = 0;
  double average_probes = 0.0;
  double load_factor = 0.0;
};

// Open-addressing hash table with robin hood probing
// Key: key type (e.g., int32_t)
// Value: value type (e.g., int64_t for SUM aggregation)
template <typename Key, typename Value>
class HashTable {
 public:
  using Entry = HashTableEntry<Key, Value>;

  HashTable() : HashTable(HashTableConfig()) {}

  explicit HashTable(const HashTableConfig& config)
      : config_(config),
        capacity_(config.capacity),
        mask_(capacity_ - 1),  // Assuming power of 2
        entries_(std::make_unique<Entry[]>(capacity_)),
        num_entries_(0) {
    // Initialize entries
    for (size_t i = 0; i < capacity_; ++i) {
      entries_[i].occupied = false;
      entries_[i].hash = 0;
    }
  }

  // Find entry, return nullptr if not found
  Entry* Find(const Key& key, uint64_t hash = 0) {
    uint64_t h = hash ? hash : Hash<Key>(key);
    size_t index = h & mask_;
    size_t probes = 0;

    while (true) {
      probes++;
      if (VAGG_UNLIKELY(!entries_[index].occupied)) {
        // Empty slot - key not found
        UpdateStats(probes, false);
        return nullptr;
      }

      // Check if keys match
      if (entries_[index].hash == h && entries_[index].key == key) {
        UpdateStats(probes, false);
        return &entries_[index];
      }

      // Robin hood: swap if probe length is much shorter
      // For simplicity, just continue probing
      index = (index + 1) & mask_;
    }
  }

  // Find or insert entry
  Entry* FindOrInsert(const Key& key, uint64_t hash = 0) {
    if (VAGG_UNLIKELY(num_entries_ >= capacity_ * config_.max_load_factor)) {
      Resize(capacity_ * 2);
    }

    uint64_t h = hash ? hash : Hash<Key>(key);
    size_t index = h & mask_;
    size_t probes = 0;

    while (true) {
      probes++;
      if (VAGG_UNLIKELY(!entries_[index].occupied)) {
        // Found empty slot - insert new entry here
        entries_[index].key = key;
        entries_[index].value = Value{};
        entries_[index].hash = h;
        entries_[index].occupied = true;
        num_entries_++;
        UpdateStats(probes, true);
        return &entries_[index];
      }

      // Check if keys match
      if (entries_[index].hash == h && entries_[index].key == key) {
        UpdateStats(probes, false);
        return &entries_[index];
      }

      // Continue to next slot (linear probing)
      index = (index + 1) & mask_;
    }
  }

  // Insert only if key doesn't exist (for join build phase)
  Entry* InsertIfAbsent(const Key& key, uint64_t hash = 0) {
    if (VAGG_UNLIKELY(num_entries_ >= capacity_ * config_.max_load_factor)) {
      Resize(capacity_ * 2);
    }

    uint64_t h = hash ? hash : Hash<Key>(key);
    size_t index = h & mask_;
    size_t probes = 0;

    while (true) {
      probes++;
      if (VAGG_UNLIKELY(!entries_[index].occupied)) {
        // Empty slot - insert here
        entries_[index].key = key;
        entries_[index].value = Value{};
        entries_[index].hash = h;
        entries_[index].occupied = true;
        num_entries_++;
        UpdateStats(probes, true);
        return &entries_[index];
      }

      // Check if key already exists
      if (entries_[index].hash == h && entries_[index].key == key) {
        UpdateStats(probes, false);
        return nullptr;  // Already exists
      }

      index = (index + 1) & mask_;
    }
  }

  // Iterator for iteration
  class Iterator {
   public:
    // Default constructor creates an end iterator
    Iterator() : current_(nullptr), end_(nullptr) {}

    Iterator(Entry* entry, Entry* end) : current_(entry), end_(end) {
      if (current_ != nullptr) {
        AdvanceToValid();
      }
    }

    Entry* operator*() const { return current_; }
    Entry* operator->() const { return current_; }

    Iterator& operator++() {
      ++current_;
      AdvanceToValid();
      return *this;
    }

    bool operator==(const Iterator& other) const { return current_ == other.current_; }
    bool operator!=(const Iterator& other) const { return current_ != other.current_; }

   private:
    void AdvanceToValid() {
      while (current_ < end_ && !current_->occupied) {
        ++current_;
      }
    }

    Entry* current_;
    Entry* end_;
  };

  Iterator begin() { return Iterator(entries_.get(), entries_.get() + capacity_); }
  Iterator end() { return Iterator(entries_.get() + capacity_, entries_.get() + capacity_); }

  // Access entry by index (for iteration)
  Entry& entry(size_t index) { return entries_[index]; }
  const Entry& entry(size_t index) const { return entries_[index]; }

  // Statistics
  size_t size() const { return num_entries_; }
  size_t capacity() const { return capacity_; }
  double load_factor() const { return static_cast<double>(num_entries_) / capacity_; }

  HashTableStats GetStats() const {
    HashTableStats stats;
    stats.num_entries = num_entries_;
    stats.num_probes = total_probes_;
    stats.num_collisions = total_collisions_;
    stats.num_resizes = num_resizes_;
    stats.load_factor = load_factor();
    stats.average_probes = num_entries_ > 0
        ? static_cast<double>(total_probes_) / num_entries_
        : 0.0;
    return stats;
  }

  void ResetStats() {
    total_probes_ = 0;
    total_collisions_ = 0;
  }

  void Clear() {
    for (size_t i = 0; i < capacity_; ++i) {
      entries_[i].occupied = false;
    }
    num_entries_ = 0;
    ResetStats();
  }

 private:
  void Resize(size_t new_capacity) {
    auto old_entries = std::move(entries_);
    size_t old_capacity = capacity_;
    capacity_ = new_capacity;
    mask_ = capacity_ - 1;
    entries_ = std::make_unique<Entry[]>(capacity_);

    // Clear new entries
    for (size_t i = 0; i < capacity_; ++i) {
      entries_[i].occupied = false;
    }

    // Rehash all entries
    num_entries_ = 0;
    for (size_t i = 0; i < old_capacity; ++i) {
      if (old_entries[i].occupied) {
        uint64_t h = old_entries[i].hash;
        size_t index = h & mask_;

        // Find empty slot
        while (entries_[index].occupied) {
          index = (index + 1) & mask_;
        }

        // Copy key, value, and hash, then explicitly set occupied
        entries_[index].key = old_entries[i].key;
        entries_[index].value = old_entries[i].value;
        entries_[index].hash = old_entries[i].hash;
        entries_[index].occupied = true;
        num_entries_++;
      }
    }

    num_resizes_++;
  }

  void UpdateStats(size_t probes, bool inserted) {
    total_probes_ += probes;
    if (inserted && probes > 1) {
      total_collisions_++;
    }
  }

  HashTableConfig config_;
  size_t capacity_;
  size_t mask_;
  std::unique_ptr<Entry[]> entries_;
  size_t num_entries_ = 0;

  // Statistics (reset on clear)
  size_t total_probes_ = 0;
  size_t total_collisions_ = 0;
  size_t num_resizes_ = 0;
};

// Alias for common use case: int32 key, int64 value (for SUM aggregation)
using Int32Int64HashTable = HashTable<int32_t, int64_t>;

}  // namespace vagg

#endif  // VAGG_HT_HASH_TABLE_H_
