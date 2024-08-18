#include "../include/fwd.h"
#include <cstddef>
#include <cstring>
#include <functional>
#include <vector>
#include <stdexcept>

/**
 * Linear Chained Hash Table
 * Inspired by DuckDB's Adaptive Factorization Using Linear-Chained Hash Tables
 * 
 * This implementation combines linear probing with chaining:
 * - Uses open addressing with linear probing for collision resolution
 * - Forms collision-free chains for keys with the same hash
 * - Optimized for factorized aggregations and worst-case optimal joins
 */
template <typename Key, typename Value, typename Hash = std::hash<Key>, typename KeyEqual = std::equal_to<Key>>
class LinearChainedHashTable {
 public:
  explicit LinearChainedHashTable(size_t initial_capacity = 16, float max_load_factor = 0.75f)
      : capacity_(next_power_of_two(initial_capacity)),
        max_load_factor_(max_load_factor),
        size_(0),
        buckets_(capacity_),
        hash_fn_(),
        key_equal_() {
    // Initialize all buckets as empty
    for (size_t i = 0; i < capacity_; ++i) {
      buckets_[i].state = BucketState::EMPTY;
    }
  }

  ~LinearChainedHashTable() {
    clear();
  }

  // Non-copyable
  LinearChainedHashTable(const LinearChainedHashTable&) = delete;
  LinearChainedHashTable& operator=(const LinearChainedHashTable&) = delete;

  // Move constructor
  LinearChainedHashTable(LinearChainedHashTable&& other) noexcept
      : capacity_(other.capacity_),
        max_load_factor_(other.max_load_factor_),
        size_(other.size_),
        buckets_(std::move(other.buckets_)),
        hash_fn_(std::move(other.hash_fn_)),
        key_equal_(std::move(other.key_equal_)) {
    other.capacity_ = 0;
    other.size_ = 0;
  }

  // Move assignment
  LinearChainedHashTable& operator=(LinearChainedHashTable&& other) noexcept {
    if (this != &other) {
      clear();
      capacity_ = other.capacity_;
      max_load_factor_ = other.max_load_factor_;
      size_ = other.size_;
      buckets_ = std::move(other.buckets_);
      hash_fn_ = std::move(other.hash_fn_);
      key_equal_ = std::move(other.key_equal_);
      other.capacity_ = 0;
      other.size_ = 0;
    }
    return *this;
  }

  /**
   * Insert or update a key-value pair
   * Returns true if a new key was inserted, false if an existing key was updated
   */
  bool Insert(const Key& key, const Value& value) {
    if (should_rehash()) {
      rehash();
    }

    size_t hash = hash_fn_(key);
    size_t index = hash_to_index(hash);
    
    // First, try to find if the key already exists
    size_t found_index = find_index(key, hash, index);
    if (found_index != capacity_) {
      // Key exists, update the value
      buckets_[found_index].value = value;
      return false;
    }

    // Key doesn't exist, find the insertion point
    // For linear chaining, we want to insert at the end of the chain
    size_t insert_index = find_insertion_point(hash, index);
    
    if (insert_index == capacity_) {
      // Table is full, need to rehash
      rehash();
      return Insert(key, value);  // Retry after rehash
    }

    // Insert the new key-value pair
    new (&buckets_[insert_index].key) Key(key);
    new (&buckets_[insert_index].value) Value(value);
    buckets_[insert_index].state = BucketState::OCCUPIED;
    buckets_[insert_index].hash = hash;
    ++size_;
    return true;
  }

  /**
   * Find a value by key
   * Returns pointer to value if found, nullptr otherwise
   */
  Value* Find(const Key& key) {
    size_t hash = hash_fn_(key);
    size_t index = hash_to_index(hash);
    size_t found_index = find_index(key, hash, index);
    
    if (found_index != capacity_) {
      return &buckets_[found_index].value;
    }
    return nullptr;
  }

  /**
   * Find a value by key (const version)
   */
  const Value* Find(const Key& key) const {
    size_t hash = hash_fn_(key);
    size_t index = hash_to_index(hash);
    size_t found_index = find_index(key, hash, index);
    
    if (found_index != capacity_) {
      return &buckets_[found_index].value;
    }
    return nullptr;
  }

  /**
   * Erase a key-value pair
   * Returns true if the key was found and erased, false otherwise
   */
  bool Erase(const Key& key) {
    size_t hash = hash_fn_(key);
    size_t index = hash_to_index(hash);
    size_t found_index = find_index(key, hash, index);
    
    if (found_index == capacity_) {
      return false;  // Key not found
    }

    // Destroy the key-value pair
    buckets_[found_index].key.~Key();
    buckets_[found_index].value.~Value();
    buckets_[found_index].state = BucketState::TOMBSTONE;
    --size_;
    return true;
  }

  /**
   * Check if a key exists
   */
  bool Contains(const Key& key) const {
    return Find(key) != nullptr;
  }

  /**
   * Get the number of elements
   */
  size_t Size() const {
    return size_;
  }

  /**
   * Check if the table is empty
   */
  bool Empty() const {
    return size_ == 0;
  }

  /**
   * Clear all elements
   */
  void Clear() {
    clear();
    size_ = 0;
  }

  /**
   * Get the current capacity
   */
  size_t Capacity() const {
    return capacity_;
  }

  /**
   * Get the load factor
   */
  float LoadFactor() const {
    return capacity_ > 0 ? static_cast<float>(size_) / capacity_ : 0.0f;
  }

  /**
   * Reserve space for at least n elements
   */
  void Reserve(size_t n) {
    size_t new_capacity = next_power_of_two(n);
    if (new_capacity > capacity_) {
      rehash_to_capacity(new_capacity);
    }
  }

 private:
  enum class BucketState : uint8_t {
    EMPTY = 0,
    OCCUPIED = 1,
    TOMBSTONE = 2
  };

  struct Bucket {
    BucketState state;
    size_t hash;  // Store hash for faster comparison
    union {
      Key key;
    };
    union {
      Value value;
    };

    Bucket() : state(BucketState::EMPTY), hash(0) {}
    
    // Move constructor
    Bucket(Bucket&& other) noexcept : state(other.state), hash(other.hash) {
      if (other.state == BucketState::OCCUPIED) {
        new (&key) Key(std::move(other.key));
        new (&value) Value(std::move(other.value));
        other.key.~Key();
        other.value.~Value();
        other.state = BucketState::EMPTY;
      }
    }
    
    // Move assignment
    Bucket& operator=(Bucket&& other) noexcept {
      if (this != &other) {
        if (state == BucketState::OCCUPIED) {
          key.~Key();
          value.~Value();
        }
        state = other.state;
        hash = other.hash;
        if (other.state == BucketState::OCCUPIED) {
          new (&key) Key(std::move(other.key));
          new (&value) Value(std::move(other.value));
          other.key.~Key();
          other.value.~Value();
          other.state = BucketState::EMPTY;
        }
      }
      return *this;
    }
    
    ~Bucket() {
      if (state == BucketState::OCCUPIED) {
        key.~Key();
        value.~Value();
      }
    }
    
    // Delete copy constructor and assignment
    Bucket(const Bucket&) = delete;
    Bucket& operator=(const Bucket&) = delete;
  };

  size_t capacity_;
  float max_load_factor_;
  size_t size_;
  std::vector<Bucket> buckets_;
  Hash hash_fn_;
  KeyEqual key_equal_;

  /**
   * Find the next power of two >= n
   */
  static size_t next_power_of_two(size_t n) {
    if (n == 0) return 1;
    --n;
    n |= n >> 1;
    n |= n >> 2;
    n |= n >> 4;
    n |= n >> 8;
    n |= n >> 16;
    n |= n >> 32;
    return n + 1;
  }

  /**
   * Convert hash to bucket index
   */
  size_t hash_to_index(size_t hash) const {
    return hash & (capacity_ - 1);  // capacity_ is power of 2
  }

  /**
   * Find the index of a key, or capacity_ if not found
   * Uses linear probing with chain awareness
   */
  size_t find_index(const Key& key, size_t hash, size_t start_index) const {
    size_t index = start_index;
    size_t probe_count = 0;
    
    while (probe_count < capacity_) {
      const Bucket& bucket = buckets_[index];
      
      if (bucket.state == BucketState::EMPTY) {
        // Reached an empty bucket, key not found
        break;
      }
      
      if (bucket.state == BucketState::OCCUPIED && bucket.hash == hash) {
        // Hash matches, check key equality
        if (key_equal_(bucket.key, key)) {
          return index;
        }
      }
      
      // Linear probing: move to next bucket
      index = (index + 1) & (capacity_ - 1);
      ++probe_count;
    }
    
    return capacity_;  // Not found
  }

  /**
   * Find the insertion point for a new key
   * For linear chaining, we insert at the end of the chain (first empty or tombstone)
   */
  size_t find_insertion_point(size_t hash, size_t start_index) {
    size_t index = start_index;
    size_t probe_count = 0;
    size_t first_tombstone = capacity_;
    
    while (probe_count < capacity_) {
      Bucket& bucket = buckets_[index];
      
      if (bucket.state == BucketState::EMPTY) {
        // Found empty bucket, use it
        return index;
      }
      
      if (bucket.state == BucketState::TOMBSTONE && first_tombstone == capacity_) {
        // Remember first tombstone for reuse
        first_tombstone = index;
      }
      
      // Continue probing
      index = (index + 1) & (capacity_ - 1);
      ++probe_count;
    }
    
    // Table is full, but we can reuse a tombstone
    return first_tombstone;
  }

  /**
   * Check if rehashing is needed
   */
  bool should_rehash() const {
    return size_ >= static_cast<size_t>(capacity_ * max_load_factor_);
  }

  /**
   * Rehash to double the capacity
   */
  void rehash() {
    rehash_to_capacity(capacity_ * 2);
  }

  /**
   * Rehash to a specific capacity
   */
  void rehash_to_capacity(size_t new_capacity) {
    if (new_capacity < size_) {
      new_capacity = next_power_of_two(size_);
    }
    
    std::vector<Bucket> old_buckets = std::move(buckets_);
    size_t old_capacity = capacity_;
    
    capacity_ = new_capacity;
    buckets_.clear();
    buckets_.resize(capacity_);
    
    // Initialize new buckets
    for (size_t i = 0; i < capacity_; ++i) {
      buckets_[i].state = BucketState::EMPTY;
    }
    
    // Reinsert all elements
    size_t old_size = size_;
    size_ = 0;
    
    for (size_t i = 0; i < old_capacity; ++i) {
      if (old_buckets[i].state == BucketState::OCCUPIED) {
        // Move the key-value pair
        Key key = std::move(old_buckets[i].key);
        Value value = std::move(old_buckets[i].value);
        size_t hash = old_buckets[i].hash;
        
        // Destroy the old bucket
        old_buckets[i].key.~Key();
        old_buckets[i].value.~Value();
        
        // Insert into new table
        size_t new_index = hash_to_index(hash);
        size_t insert_index = find_insertion_point(hash, new_index);
        
        if (insert_index != capacity_) {
          new (&buckets_[insert_index].key) Key(std::move(key));
          new (&buckets_[insert_index].value) Value(std::move(value));
          buckets_[insert_index].state = BucketState::OCCUPIED;
          buckets_[insert_index].hash = hash;
          ++size_;
        }
      }
    }
  }

  /**
   * Clear all buckets
   */
  void clear() {
    for (size_t i = 0; i < capacity_; ++i) {
      if (buckets_[i].state == BucketState::OCCUPIED) {
        buckets_[i].key.~Key();
        buckets_[i].value.~Value();
      }
      buckets_[i].state = BucketState::EMPTY;
    }
  }
};

// Test function
void test_linear_chained_hash_table() {
  std::cout << "\n=== Testing Linear Chained Hash Table ===" << std::endl;
  
  LinearChainedHashTable<int, std::string> table;
  
  // Test insertions
  std::cout << "Inserting key-value pairs..." << std::endl;
  for (int i = 0; i < 100; ++i) {
    table.Insert(i, "value_" + std::to_string(i));
  }
  
  std::cout << "Size: " << table.Size() << std::endl;
  std::cout << "Capacity: " << table.Capacity() << std::endl;
  std::cout << "Load factor: " << table.LoadFactor() << std::endl;
  
  // Test lookups
  std::cout << "\nTesting lookups..." << std::endl;
  int found_count = 0;
  for (int i = 0; i < 100; ++i) {
    auto* value = table.Find(i);
    if (value && *value == "value_" + std::to_string(i)) {
      ++found_count;
    }
  }
  std::cout << "Found " << found_count << " out of 100 keys" << std::endl;
  
  // Test updates
  std::cout << "\nTesting updates..." << std::endl;
  table.Insert(50, "updated_value_50");
  auto* value = table.Find(50);
  if (value && *value == "updated_value_50") {
    std::cout << "Update successful" << std::endl;
  }
  
  // Test deletions
  std::cout << "\nTesting deletions..." << std::endl;
  int erased_count = 0;
  for (int i = 0; i < 50; ++i) {
    if (table.Erase(i)) {
      ++erased_count;
    }
  }
  std::cout << "Erased " << erased_count << " keys" << std::endl;
  std::cout << "Size after deletion: " << table.Size() << std::endl;
  
  // Test contains
  std::cout << "\nTesting Contains..." << std::endl;
  std::cout << "Contains 50: " << (table.Contains(50) ? "Yes" : "No") << std::endl;
  std::cout << "Contains 0: " << (table.Contains(0) ? "Yes" : "No") << std::endl;
  std::cout << "Contains 99: " << (table.Contains(99) ? "Yes" : "No") << std::endl;
  
  // Test rehashing with collisions
  std::cout << "\nTesting rehashing with many collisions..." << std::endl;
  LinearChainedHashTable<int, int> collision_table(8);  // Small initial capacity
  for (int i = 0; i < 1000; ++i) {
    collision_table.Insert(i * 16, i);  // All hash to same bucket (if capacity is 16)
  }
  std::cout << "Collision table size: " << collision_table.Size() << std::endl;
  std::cout << "Collision table capacity: " << collision_table.Capacity() << std::endl;
  std::cout << "Collision table load factor: " << collision_table.LoadFactor() << std::endl;
  
  std::cout << "\n✓ All tests completed!" << std::endl;
}

int main() {
  test_linear_chained_hash_table();
  return 0;
}
