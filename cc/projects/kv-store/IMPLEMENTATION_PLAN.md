# TinyKV Phase 1: MemTable + Put/Get

## Goal
Build a single-threaded in-memory KV store with correct semantics, serving as the foundation for the LSM-tree implementation.

## Success Criteria
1. `MemTable::Put(key, value)` stores key-value pairs
2. `MemTable::Get(key)` returns latest value or NotFound
3. `MemTable::Delete(key)` marks key as deleted (tombstone)
4. All operations are thread-safe (mutex-protected)
5. gtest suite passes with 100% coverage of MemTable/SkipList APIs
6. Benchmark shows Put/Get throughput within 2x of std::map

---

## 1. Module Structure

```
tinykv/
├── CMakeLists.txt                    # Root build config
├── IMPLEMENTATION_PLAN.md            # This file
├── include/tinykv/
│   ├── common/
│   │   ├── slice.hpp                 # Non-owning string view
│   │   ├── status.hpp                # Error return type
│   │   └── macros.hpp                # DISALLOW_COPY, NOLINT, etc.
│   ├── memtable/
│   │   ├── arena.hpp                 # Memory pool for nodes
│   │   ├── skiplist.hpp              # SkipList implementation
│   │   └── memtable.hpp              # MemTable API wrapper
│   └── util/
│       └── comparator.hpp            # Key comparison interface
├── src/
│   ├── common/
│   │   └── slice.cpp
│   └── memtable/
│       ├── arena.cpp
│       ├── skiplist.cpp
│       └── memtable.cpp
├── tests/
│   └── memtable/
│       ├── skiplist_test.cpp
│       └── memtable_test.cpp
└── bench/
    └── memtable/
        └── memtable_bench.cpp
```

---

## 2. API Design

### 2.1 Slice (Non-owning string view)

```cpp
namespace tinykv {

class Slice {
public:
    // Constructors
    Slice() : data_(""), size_(0) {}
    Slice(const char* data, size_t size) : data_(data), size_(size) {}
    Slice(const std::string& s) : data_(s.data()), size_(s.size()) {}

    // Accessors
    const char* data() const { return data_; }
    size_t size() const { return size_; }
    bool empty() const { return size_ == 0; }

    // Byte access
    char operator[](size_t n) const { return data_[n]; }

    // Comparison
    int compare(const Slice& other) const;
    bool operator==(const Slice& other) const;
    bool operator<(const Slice& other) const;

    // Utilities
    std::string ToString() const { return std::string(data_, size_); }

private:
    const char* data_;
    size_t size_;
};

}  // namespace tinykv
```

**Design Notes:**
- Non-owning: caller manages lifetime
- Null-safe: empty slice has `data_=""`, never nullptr
- Used throughout API to avoid string copies

### 2.2 Status (Error return type)

```cpp
namespace tinykv {

class Status {
public:
    // Factory methods
    static Status OK() { return Status(kOk, {}, {}); }
    static Status NotFound(Slice msg = {}) { return Status(kNotFound, msg, {}); }
    static Status Corruption(Slice msg = {}) { return Status(kCorruption, msg, {}); }
    static Status InvalidArgument(Slice msg = {}) { return Status(kInvalidArgument, msg, {}); }

    // Accessors
    bool ok() const { return code_ == kOk; }
    bool IsNotFound() const { return code_ == kNotFound; }
    bool IsCorruption() const { return code_ == kCorruption; }
    std::string ToString() const;

private:
    enum Code { kOk, kNotFound, kCorruption, kInvalidArgument };
    Code code_;
    std::string message_;  // Only for non-OK status
};

}  // namespace tinykv
```

**Design Notes:**
- Zero-allocation for OK status (small buffer optimization)
- No exceptions - return by value
- Consistent with RocksDB/Pebble API style

### 2.3 Comparator (Key ordering)

```cpp
namespace tinykv {

class Comparator {
public:
    virtual ~Comparator() = default;

    // Three-way comparison: returns -1, 0, +1
    virtual int Compare(const Slice& a, const Slice& b) const = 0;

    // For SkipList: find first node with key >= given
    virtual const char* FindShortestSeparator(const Slice& start,
                                               const Slice& limit) const;
    virtual const char* FindShortSuccessor(const Slice& key) const;

    // Name for debugging and file format identification
    virtual const char* Name() const = 0;
};

// Default comparator using lexicographic order
class BytewiseComparator : public Comparator {
public:
    int Compare(const Slice& a, const Slice& b) const override;
    const char* Name() const override { return "tinykv.BytewiseComparator"; }
};

}  // namespace tinykv
```

### 2.4 Arena (Memory pool for SkipList nodes)

```cpp
namespace tinykv {

class Arena {
public:
    Arena();
    ~Arena();

    // Allocate bytes with alignment
    char* Allocate(size_t bytes);

    // Allocate space for an object, construct in-place
    template<typename T, typename... Args>
    T* Allocate(Args&&... args) {
        void* buf = Allocate(alignof(T), sizeof(T));
        return new (buf) T(std::forward<Args>(args)...);
    }

    // Memory usage tracking
    size_t MemoryUsage() const { return memory_usage_; }

    // Non-copyable, movable
    Arena(const Arena&) = delete;
    Arena& operator=(const Arena&) = delete;
    Arena(Arena&&) noexcept;
    Arena& operator=(Arena&&) noexcept;

private:
    static constexpr size_t kBlockSize = 4096;

    struct Block {
        Block* prev;
        char* data;
        size_t size;
    };

    Block* head_ = nullptr;
    char* current_ = nullptr;
    char* limit_ = nullptr;
    size_t memory_usage_ = 0;
};

}  // namespace tinykv
```

**Design Notes:**
- Linear allocation within blocks, O(1) allocation time
- Blocks are chained, freed on Arena destruction
- Cache-friendly: allocations are sequential
- Memory usage tracked for diagnostics

### 2.5 SkipList (Ordered map)

```cpp
namespace tinykv {

template<typename Key, typename Value, typename Comparator>
class SkipList {
public:
    explicit SkipList(Comparator cmp, Arena* arena);

    // Insert or update key-value
    // Returns true if inserted, false if updated
    bool Insert(const Key& key, const Value& value);

    // Find value for key
    // Returns true if found, fills *value
    bool Get(const Key& key, Value* value) const;

    // Delete key
    bool Delete(const Key& key);

    // Check if key exists
    bool Contains(const Key& key) const { return Get(key, nullptr); }

    // Iterator
    class Iterator {
    public:
        explicit Iterator(const SkipList* list);
        bool Valid() const;
        void Seek(const Key& key);
        void Next();
        void Prev();
        const Key& Key() const;
        const Value& Value() const;
    };

    // Statistics
    size_t Size() const { return size_; }
    bool Empty() const { return size_ == 0; }

private:
    struct Node {
        Key key;
        Value value;
        // Dynamic array of forward pointers
        Node** forward;
        int node_type;  // For debugging
    };

    static constexpr int kMaxHeight = 12;  // ~2^12 = 4096 elements
    static constexpr double kP = 0.5;

    Comparator cmp_;
    Arena* arena_;
    Node* head_;
    int max_height_ = 1;
    size_t size_ = 0;

    // Random level generation
    int RandomHeight();

    // Internal search
    Node* FindGreaterOrEqual(const Key& key, Node** prev) const;
};

}  // namespace tinykv
```

**Invariants:**
1. Nodes are sorted by key in ascending order
2. Forward pointers at level i skip over nodes with height <= i
3. Height follows geometric distribution with p=0.5
4. No duplicate keys (Insert replaces existing)

**Failure Modes:**
- Memory allocation failure: handled by Arena (throws bad_alloc)
- Concurrent access: NOT thread-safe (MemTable wraps with mutex)

### 2.6 MemTable (Public API wrapper)

```cpp
namespace tinykv {

class MemTable {
public:
    explicit MemTable(const Comparator* comparator);
    ~MemTable();

    // Insert key-value. Returns size added to memory usage.
    size_t Put(const Slice& key, const Slice& value);

    // Get value for key. Returns true if found.
    bool Get(const Slice& key, std::string* value) const;

    // Mark key as deleted (tombstone)
    size_t Delete(const Slice& key);

    // Check if key exists
    bool Contains(const Slice& key) const { return Get(key, nullptr); }

    // Statistics
    size_t ApproximateMemoryUsage() const;
    size_t Size() const;

    // For internal use: get approximate size of an item
    static size_t ApproximateSizeOf(const Slice& key, const Slice& value);

private:
    struct KeyValueNode {
        Slice key;
        Slice value;
        // InternalKey encoding: key + 8-byte sequence + 1-byte type
        // For Phase 1: just store raw key/value, seq used later
    };

    using SkipListType = SkipList<Slice, Slice, BytewiseComparator>;

    std::unique_ptr<SkipListType> list_;
    Arena arena_;
    const Comparator* comparator_;
    mutable std::shared_mutex mutex_;  // Readers-writers lock
};

}  // namespace tinykv
```

**Key Design Decisions for Phase 1:**
1. `Slice` as key/value type - avoids copies, caller manages lifetime
2. `std::shared_mutex` - concurrent reads, exclusive writes
3. No sequence numbers yet - single version only
4. Tombstone is just a Delete with empty value (compaction handles later)

---

## 3. Invariants

### SkipList Invariants
1. **Ordering**: For any node n and level i > 0, all nodes between n.forward[i-1] and n.forward[i] have height <= i
2. **Height distribution**: P(height > k) = (0.5)^(k+1)
3. **No gaps**: If n.forward[i] exists, then n.forward[i-1] also exists

### MemTable Invariants
1. **Single sorted map**: All keys stored in sorted order
2. **Unique keys**: Latest value for a key is the one returned by Get
3. **Atomic visibility**: Get sees all previously completed Puts
4. **Memory safety**: Arena owns all node memory

---

## 4. File Format (Memory layout)

### Arena Block Layout
```
+-------------------+
| Block header      |  (prev pointer, block size)
+-------------------+
| Allocated nodes   |  <- grows upward
| (SkipList nodes)  |
| ...               |
+-------------------+
| Free space        |
+-------------------+
```

### SkipList Node Layout
```
+-------------------+
| Key (Slice)       |  <- pointer to arena memory
+-------------------+
| Value (Slice)     |  <- pointer to arena memory
+-------------------+
| Height (int)      |
+-------------------+
| Forward pointers  |  <- array of Node* of length = height
| [0], [1], ..., [h-1] |
+-------------------+
```

---

## 5. Test Plan

### 5.1 Unit Tests (gtest)

#### SkipList Tests
1. **Insert/Get basic**: Insert 100 items, verify all retrievable
2. **Insert/Update**: Insert same key twice, verify Get returns latest
3. **Ordering**: Insert random keys, verify in-order iteration matches sorted vector
4. **Delete**: Insert then delete, verify Get returns false
5. **Empty**: Test Empty(), Size() on empty list
6. **Iterator**: Test Iterator::Seek, Next, Prev, Valid on various states
7. **Boundary**: Test first key, last key, non-existent key cases
8. **Concurrent reads**: (not for Phase 1 - single thread only)

#### MemTable Tests
1. **Put/Get round-trip**: Put 1000 key-value pairs, verify all retrievable
2. **Overwrite**: Put same key different values, verify latest returned
3. **Delete**: Put then Delete, verify Get returns not found
4. **Memory tracking**: Verify ApproximateMemoryUsage grows correctly
5. **Empty key/value**: Test edge cases for empty slices
6. **Large values**: Test with 1MB value (stress arena allocation)

#### Correctness Tests (Reference Model)
1. **Random operations**: Run 10000 random Put/Get/Delete ops against both MemTable and std::map, compare results
2. **Deterministic seed**: Use fixed random seed for reproducibility

### 5.2 Crash Tests (Not for Phase 1 - needs WAL)

### 5.3 Performance Tests
See benchmark section below.

---

## 6. Benchmark Plan

### 6.1 Microbenchmarks (google benchmark)

#### Put Throughput
```cpp
// Sequential keys
for (i = 0; i < N; i++) {
    memtable.Put(Key(i), value);
}
```

#### Get Throughput
```cpp
// Random keys
for (i = 0; i < N; i++) {
    memtable.Get(Key(Random()));
}
```

#### Mixed Workload
- 50% Put / 50% Get
- 90% Put / 10% Get (write-heavy)
- 10% Put / 90% Get (read-heavy)

### 6.2 Metrics to Collect
| Metric | Tool | Target |
|--------|------|--------|
| Throughput (ops/sec) | google benchmark | > 100K ops/sec |
| Latency p50/p99 | google benchmark | < 10us / < 100us |
| Memory per entry | heaptrack | < 64 bytes overhead |

### 6.3 Comparison Baseline
| Implementation | Expected throughput |
|----------------|---------------------|
| MemTable+SkipList | Baseline |
| std::map | Within 2x of SkipList |
| std::unordered_map | 2-5x faster (hashing vs sorting) |

---

## 7. Profiling Checklist

### 7.1 CPU Profiling
```bash
# Build with debug info
cmake -DCMAKE_BUILD_TYPE=Debug ...

# Profile with perf
perf record -g ./bench_memtable
perf report --symbol-filter="SkipList"
```

**Hot paths to examine:**
- `SkipList::Insert` - random level generation, pointer updates
- `SkipList::Get` - traversal down levels

### 7.2 Memory Profiling
```bash
# Use heaptrack
heaptrack ./bench_memtable
heaptrack --analyze heaptrack.*
```

**Metrics to check:**
- Arena allocation overhead
- Memory per node vs theoretical minimum
- Allocation frequency

### 7.3 Cache Behavior
```bash
# Cachegrind
valgrind --tool=cachegrind ./bench_memtable
cg_annotate skiplist.cpp
```

**What to look for:**
- L1 cache miss rate on traversal
- Prefetch effectiveness

---

## 8. Common Pitfalls

### 8.1 Correctness Pitfalls

| Pitfall | Symptom | Fix |
|---------|---------|-----|
| Slice lifetime mismatch | Crash or garbage values | Ensure Arena owns all key/value memory |
| Iterator invalidation during insert | Crash or infinite loop | SkipList iterators don't invalidate (no concurrent mod) |
| Comparator inconsistency | Wrong ordering, missed keys | Test with known key ordering |
| Race condition in MemTable | Concurrent read/write crash | Use mutex for all public methods |

### 8.2 Performance Pitfalls

| Pitfall | Symptom | Fix |
|---------|---------|-----|
| Excessive small allocations | High allocation time | Arena batches allocations |
| Poor cache locality | High cache miss rate | Sequential node layout in Arena |
| Unpredictable branch outcomes | Poor branch prediction | Optimize fast path (common case first) |

### 8.3 Debugging Techniques

1. **Enable invariant checking**:
   ```cpp
   #ifdef TINYKV_ENABLE_CHECK_INVARIANTS
   list_->SanityCheck();
   #endif
   ```

2. **Deterministic testing**:
   ```cpp
   Random rng(42);  // Fixed seed for reproducibility
   ```

3. **Verbose mode**:
   ```bash
   ./test_memtable --v=2
   ```

---

## 9. Implementation Steps

### Step 1: Setup
- [ ] Create project structure
- [ ] Write CMakeLists.txt with gtest and google benchmark
- [ ] Configure C++20 standard, warnings

### Step 2: Common utilities
- [ ] Implement `Slice` class
- [ ] Implement `Status` class
- [ ] Add comparator interface

### Step 3: Arena
- [ ] Implement `Arena::Allocate()`
- [ ] Implement block management
- [ ] Add memory tracking
- [ ] Write Arena unit tests

### Step 4: SkipList
- [ ] Define Node structure
- [ ] Implement `RandomLevel()`
- [ ] Implement `FindGreaterOrEqual()`
- [ ] Implement `Insert()`
- [ ] Implement `Get()`
- [ ] Implement `Delete()`
- [ ] Implement Iterator
- [ ] Write SkipList unit tests

### Step 5: MemTable
- [ ] Implement `MemTable` wrapper
- [ ] Add thread safety (mutex)
- [ ] Add memory usage tracking
- [ ] Write MemTable unit tests

### Step 6: Integration tests
- [ ] Random operation comparison with std::map
- [ ] Stress test (large dataset)

### Step 7: Benchmarks
- [ ] Put throughput benchmark
- [ ] Get throughput benchmark
- [ ] Mixed workload benchmark
- [ ] Compare with std::map/std::unordered_map

### Step 8: Profiling
- [ ] Run CPU profiling with perf
- [ ] Run memory profiling with heaptrack
- [ ] Document findings

---

## 10. Skills Learned

After completing Phase 1, you will have learned:

1. **Memory management**:
   - Arena allocation pattern for high-frequency small allocations
   - Trade-offs between malloc and pooled allocation

2. **Data structure design**:
   - SkipList as an alternative to balanced BSTs
   - Probability-based height distribution
   - Iterator design for sorted containers

3. **Modern C++ patterns**:
   - RAII for resource management (Arena)
   - Non-owning types (Slice) to avoid copies
   - Smart pointers and std::shared_mutex
   - Templates for generic SkipList

4. **Testing methodology**:
   - Reference model testing (compare with std::map)
   - Deterministic testing with fixed random seeds
   - Boundary condition testing

5. **Performance mindset**:
   - Benchmark-driven optimization
   - Memory layout for cache efficiency
   - Allocation patterns affecting performance

---

## 11. Next Optimization Candidates (Phase 2+)

Based on Phase 1 implementation, candidates include:

1. **WAL (Write-Ahead Log)** - Durability
   - Append-only log for crash recovery
   - Group commit for write throughput

2. **SSTable Flush** - Disk persistence
   - Block-based storage format
   - Index block for fast lookup

3. **Compaction** - Space/performance
   - Level-based compaction
   - Tombstone handling

4. **Concurrency** - Multi-threaded access
   - Fine-grained locking or lock-free SkipList
   - Read-write lock optimization

---

## 12. References

- [SkipList original paper](https://www.cs.cmu.edu/~adamchik/15-121/lectures/SkipLists.pdf)
- [RocksDB MemTable](https://github.com/facebook/rocksdb/blob/main/memtable/)
- [LevelDB implementation](https://github.com/google/leveldb)
