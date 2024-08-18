# TinyKV - MemTable Implementation Summary

## Overview

TinyKV is an embedded key-value store with MemTable as the first component. The MemTable uses a SkipList for O(log n) ordered operations.

## Architecture

```
tinykv/
├── include/tinykv/
│   ├── common/
│   │   └── slice.hpp          # Non-owning string reference
│   └── memtable/
│       ├── arena.hpp          # Memory pool allocator
│       ├── skiplist.hpp       # SkipList implementation
│       └── memtable.hpp       # Thread-safe key-value store
├── src/memtable/
│   ├── arena.cpp              # Arena implementation
│   ├── skiplist.cpp           # (header-only)
│   └── memtable.cpp           # MemTable implementation
├── tests/memtable/
│   ├── skiplist_test.cpp      # SkipList unit tests
│   └── memtable_test.cpp      # MemTable unit tests
└── build/                      # CMake build directory
```

## Design Decisions

### 1. Slice - Non-owning String Reference

**Purpose**: Avoid string copying throughout the API.

**Design**:
- Lightweight wrapper around `const char*` + size
- No ownership semantics (caller ensures lifetime)
- Supports implicit conversion from `std::string` and `const char*`

**Trade-offs**:
- ✅ Zero copy for API calls
- ✅ Memory efficient for temporary values
- ❌ Caller must manage data lifetime
- ❌ Potential dangling references if misused

### 2. Arena - Memory Pool Allocator

**Purpose**: Reduce malloc overhead for frequent small allocations.

**Design**:
- Pre-allocate 4KB blocks
- Serve small allocations from current block
- Allocate new block when needed
- Simple bump-pointer allocation

**Trade-offs**:
- ✅ Single allocation per block amortizes malloc cost
- ✅ Good cache locality for related allocations
- ❌ No deallocation until Arena destruction
- ❌ Internal fragmentation (wasted block space)

### 3. SkipList - Ordered Data Structure

**Purpose**: O(log n) insert, delete, search with ordered iteration.

**Design**:
- Probabilistic skip list with max height 12
- Random height with P=0.5 branching factor
- Flexible forward pointers per node

**Memory Layout Decision**:
```
// Before (broken for non-trivial types):
struct Node {
    Node* forward_[1];  // Flexible array member
    Key key_;
    Value value_;
};

// After (works for all types):
struct Node {
    Node** forward_;    // Separate allocation
    Key key_;
    Value value_;
};
```

**Why separate allocation?**
- Flexible array members require standard layout
- `std::string` breaks standard layout (has non-trivial members)
- Separate pointer ensures predictable offsets

**Trade-offs**:
- ✅ O(log n) expected time complexity
- ✅ Simple implementation vs balanced BST
- ✅ Ordered iteration support
- ❌ Probabilistic (worst-case O(n))
- ❌ Extra pointer indirection for forward arrays

### 4. MemTable - Thread-Safe Key-Value Store

**Purpose**: Thread-safe ordered key-value storage.

**Design**:
- Wraps SkipList<Slice, Slice>
- Arena allocates key/value copies (Slice doesn't own memory)
- `std::shared_mutex` for concurrent reads, exclusive writes

**Thread Safety**:
- Multiple readers can access simultaneously
- Writers block all other access
- Uses `std::shared_lock` for reads, `std::unique_lock` for writes

**Trade-offs**:
- ✅ Good read concurrency
- ✅ Write serialization prevents corruption
- ❌ Single writer bottleneck
- ❌ Memory not reclaimed on delete

## Key Invariants

1. **SkipList**:
   - Keys are totally ordered via Comparator
   - Forward pointers always point to next node at that level
   - Height 1 node always exists (level 0 chain)
   - Insertions never remove nodes from the list

2. **Arena**:
   - Allocations are sequential within a block
   - No deallocation until destruction
   - Memory usage tracked for reporting

3. **MemTable**:
   - All stored Slices point to Arena-allocated memory
   - Size reflects number of key-value pairs
   - Iterator yields keys in sorted order

## Limitations

1. **Memory Management**:
   - No individual node deletion from Arena
   - Delete operations free SkipList nodes but not Arena memory
   - Large values increase memory pressure

2. **Concurrency**:
   - Single writer at a time
   - No concurrent read during write
   - No snapshot isolation

3. **Durability**:
   - Memory-only (no persistence)
   - Lost on process exit

4. **SkipList**:
   - Probabilistic structure (random seed affects shape)
   - Max height limits max elements (~4096 with current params)

## Usage

### Basic Operations

```cpp
#include "tinykv/memtable/memtable.hpp"

tinykv::MemTable memtable;

// Put
memtable.Put("key1", "value1");
memtable.Put("key2", "value2");

// Get
std::string value;
bool found = memtable.Get("key1", &value);  // found=true, value="value1"

// Delete
memtable.Delete("key1");

// Check existence
bool exists = memtable.Contains("key2");

// Get size
size_t n = memtable.Size();

// Memory usage
size_t bytes = memtable.ApproximateMemoryUsage();
```

### Iteration

```cpp
auto it = memtable.NewIterator();

// Forward iteration
for (it.SeekToFirst(); it.Valid(); it.Next()) {
    std::cout << it.CurrentKey() << ": " << it.CurrentValue() << "\n";
}

// Seek to position
it.Seek("key1");  // Points to first key >= "key1"
```

### With Slice

```cpp
// Slice is implicit from const char* and std::string
memtable.Put("key", "value");  // Converts to Slice

// Explicit Slice construction
memtable.Put(tinykv::Slice(key_data, key_size), tinykv::Slice(value_data, value_size));

// Convert back to std::string
std::string s = retrieved_value.ToString();
```

## Testing

Run unit tests:
```bash
cd build
./tinykv_memtable_test
```

All 14 tests cover:
- Basic Put/Get operations
- Multiple entries and ordering
- Update semantics (same key overwrites)
- Delete operations
- Empty keys and values
- Memory usage tracking
- Iterator traversal and seek
- Stress tests (1000 random operations)
- Large values (10KB)
- Many small entries (1000)

## Build System

```bash
cd build
cmake -DCMAKE_BUILD_TYPE=Release ..
make -j4
```

Build types:
- **Release**: Optimized build
- **ASAN**: Address sanitizer for debugging memory issues
- **DEBUG**: Debug symbols, no optimization

## Future Improvements

1. **WAL (Write-Ahead Log)**: Add durability via log
2. **Compaction**: Threshold-based flushing to SSTable
3. **Bloom Filter**: Faster negative lookups
4. **Lock-free SkipList**: Better write concurrency
5. **Custom Allocators**: Per-node memory tracking
