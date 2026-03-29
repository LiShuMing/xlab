# TinyKV Agent Guide

This file provides guidance for AI agents working on the TinyKV project.

## Project Overview

TinyKV is a high-performance LSM-tree key-value store in modern C++20. It is designed as a learning project to practice systems programming, storage engine design, and performance optimization.

## Build Commands

### Prerequisites

- CMake 3.16+
- C++20 compatible compiler (GCC 10+, Clang 12+)
- Local thirdparty dependencies in `cc/thirdparty/` (googletest, benchmark)

### Build

```bash
cd cc/projects/kv-store
mkdir -p build && cd build
cmake ..
make -j$(nproc)
```

### Build Types

```bash
# Debug build (default)
cmake -DCMAKE_BUILD_TYPE=Debug ..

# Release build
make -DCMAKE_BUILD_TYPE=Release ..

# With sanitizers
cmake -DCMAKE_BUILD_TYPE=Debug -DCMAKE_CXX_FLAGS="-fsanitize=address,undefined" ..
```

## Test Commands

### Run All Tests

```bash
cd cc/projects/kv-store/build
ctest --output-on-failure
```

### Run Specific Tests

```bash
# Run memtable tests only
./tinykv_memtable_test

# Run with verbose output
./tinykv_memtable_test --gtest_verbose=1
```

## Benchmark Commands

```bash
# Build benchmarks
make tinykv_memtable_bench

# Run benchmarks
./tinykv_memtable_bench
```

## Code Formatting

```bash
# Format all code
make format
```

Requires clang-format to be installed.

## Directory Structure

```
cc/projects/kv-store/
├── include/tinykv/          # Public headers
│   ├── common/              # Common utilities (Slice, Status, macros)
│   ├── memtable/            # MemTable components (SkipList, Arena)
│   └── util/                # Utility components (Comparator)
├── src/                     # Source files
│   └── memtable/            # MemTable implementation
├── tests/                   # Unit tests
│   └── memtable/            # MemTable tests
├── bench/                   # Benchmarks
│   └── memtable/            # MemTable benchmarks
├── docs/                    # Documentation
│   ├── api/                 # API reference
│   └── architecture/        # Architecture docs
├── CMakeLists.txt           # Build configuration
└── README.md                # Project documentation
```

## Dependencies

- **googletest**: Unit testing framework (from cc/thirdparty/googletest)
- **benchmark**: Microbenchmarking library (from cc/thirdparty/benchmark)
- **CMake**: Build system
- **clang-format**: Code formatting (optional)

## Architecture Overview

TinyKV follows a modular LSM-tree architecture:

### Current Implementation (Phase 1)

- **MemTable**: In-memory write buffer using SkipList
- **SkipList**: Probabilistic ordered data structure for O(log n) operations
- **Arena**: Memory allocator for reducing malloc overhead
- **Slice**: Lightweight string reference (non-owning)
- **Status**: Error handling with codes and messages

### Planned Phases

1. **Phase 1: MemTable + Put/Get** (Current) - In-memory KV with Arena/SkipList
2. **Phase 2: WAL + Recovery** - Write-ahead log for durability
3. **Phase 3: SSTable** - Disk format with BlockBuilder/TableReader
4. **Phase 4: VersionSet + Manifest** - Multi-file metadata management
5. **Phase 5: Compaction** - Leveled compaction for read/space optimization

## Key Components

### MemTable

In-memory write buffer:
- Uses SkipList for ordered storage
- Arena allocator for efficient memory management
- Supports Put, Get, Delete operations
- Thread-unsafe (single writer assumption)

### SkipList

Probabilistic ordered data structure:
- O(log n) average time for search/insert/delete
- Lock-free reads possible with proper memory ordering
- Supports forward iteration
- Used by MemTable for ordering keys

### Arena

Simple memory allocator:
- Allocates fixed-size blocks
- Reduces malloc/free overhead
- All memory freed at once on Arena destruction
- Used by MemTable and SkipList

### Slice

Lightweight string reference:
- Non-owning reference to byte array
- Used for keys and values throughout
- Zero-copy when passing by value

### Status

Error handling:
- OK status for success
- Error codes with messages
- Used for API error propagation

## Coding Patterns

### Error Handling

```cpp
Status Put(const Slice& key, const Slice& value) {
    if (key.empty()) {
        return Status::InvalidArgument("Key cannot be empty");
    }
    // ... implementation
    return Status::OK();
}

// Usage
Status s = memtable.Put(key, value);
if (!s.ok()) {
    // Handle error
}
```

### Memory Management

```cpp
// Arena allocation
char* mem = arena.Allocate(size);

// Slice for references
Slice key(data, length);  // Non-owning
```

### Testing Pattern

```cpp
TEST(ComponentTest, BasicOperation) {
    // Setup
    Component c;

    // Execute
    auto result = c.Operation();

    // Verify
    EXPECT_EQ(result, expected);
}
```

## Common Tasks

### Adding a New Component

1. Create header in `include/tinykv/<module>/`
2. Create implementation in `src/<module>/`
3. Add to CMakeLists.txt
4. Create tests in `tests/<module>/`
5. Update AGENTS.md with component info

### Adding Tests

1. Create test file in `tests/<module>/<name>_test.cpp`
2. Add to CMakeLists.txt `tinykv_memtable_test` sources
3. Follow gtest patterns (TEST, TEST_F, ASSERT_*, EXPECT_*)

### Adding Benchmarks

1. Create benchmark file in `bench/<module>/<name>_bench.cpp`
2. Add to CMakeLists.txt as new executable
3. Use `BENCHMARK()` macro
4. Run with `make <benchmark_target>`

## Performance Considerations

- **Hot paths**: Minimize allocations, use Arena
- **Cache locality**: Prefer contiguous storage
- **Branch prediction**: Keep fast paths simple
- **Syscalls**: Batch when possible
- **Memory ordering**: Be explicit about concurrency

## References

- [Project README](./README.md)
- [Coding Standards](./RULES.md)
- [API Documentation](./docs/api/)
- [Architecture Documentation](./docs/architecture/)
- [TODOs](./TODOS.md)
