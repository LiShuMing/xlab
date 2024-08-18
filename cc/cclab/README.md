# cc/cclab - C++ Laboratory

[![C++20](https://img.shields.io/badge/C%2B%2B-20-blue.svg)](https://en.cppreference.com/w/cpp/20)
[![CMake](https://img.shields.io/badge/CMake-3.22+-green.svg)](https://cmake.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A comprehensive C++ laboratory for experimenting with modern data structures, algorithms, concurrency primitives, and system programming utilities.

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Features](#features)
- [Building](#building)
- [Testing](#testing)
- [Project Structure](#project-structure)
- [Documentation](#documentation)
- [Contributing](#contributing)

## Overview

**cc/cclab** serves as a research and experimentation platform for:

- **High-Performance Data Structures**: Lock-free collections, specialized trees, hash maps
- **Concurrency**: Thread pools, synchronization primitives, coroutines
- **System Programming**: File operations, process management, SIMD
- **Algorithms**: Custom implementations for learning and benchmarking

### Key Highlights

| Component | Description | Status |
|-----------|-------------|--------|
| SkipList | Probabilistic ordered data structure | ✅ Tested |
| B+Tree | Disk-friendly ordered tree | ✅ Tested |
| Robin Hood Hash Map | Open addressing hash map | ✅ Tested |
| MPMC Queue | Lock-free multi-producer multi-consumer queue | ✅ Tested |
| Thread Pool | Work-stealing thread pool | 🚧 In Progress |
| Coroutines | C++20 coroutine utilities | 🚧 Experimental |

## Quick Start

### Prerequisites

- C++ compiler (GCC 11+, Clang 14+, or MSVC 2022)
- CMake 3.22+
- Make or Ninja

### Build and Test

```bash
# Clone and navigate to project
cd cc/cclab

# Build with Address Sanitizer (recommended for development)
./build.sh

# Run all tests
cd build_ASAN && ctest --output-on-failure

# Or build release version
BUILD_TYPE=RELEASE ./build.sh
cd build_RELEASE && ctest
```

## Features

### Data Structures

#### SkipList (`src/common/skiplist/`)
Probabilistic data structure with O(log n) search/insert/delete.

```cpp
#include "common/skiplist/SkipList.h"

cclab::SkipList<int> list;
list.insert(42);
list.insert(17);
if (list.contains(42)) {
    // Found!
}
```

#### B+Tree (`src/common/btree/`)
Disk-optimized ordered tree for range queries.

```cpp
#include "common/btree/bplustree.h"

BPlusTree<int, std::string> tree(128);  // 128 keys per node
tree.insert(1, "one");
tree.insert(2, "two");
auto range = tree.range_query(1, 3);
```

#### Robin Hood Hash Map (`src/common/map/`)
Open addressing hash map with low variance in probe lengths.

```cpp
#include "common/map/robin_hood_map.h"

RobinHoodMap<std::string, int> map;
map["key"] = 42;
int value = map.get("key").value_or(0);
```

#### Lock-Free Queues (`src/common/queue/`)
Multiple queue implementations for different concurrency patterns:
- **MPMC Queue**: Multi-producer multi-consumer
- **SPSC Queue**: Single-producer single-consumer (fastest)
- **SPMC Queue**: Single-producer multi-consumer

```cpp
#include "common/queue/mpmc_queue.h"

MPMCQueue<int> queue(1024);
queue.enqueue(42);
int value;
if (queue.dequeue(value)) {
    // Process value
}
```

### Utilities

#### Thread Pool (`src/utils/thread_pool.h`)
Work-stealing thread pool for parallel task execution.

```cpp
#include "utils/thread_pool.h"

ThreadPool pool(4);  // 4 threads
auto future = pool.submit([]() { return 42; });
int result = future.get();
```

#### LRU Cache (`src/utils/lru.hpp`)
Least Recently Used cache with O(1) operations.

```cpp
#include "utils/lru.hpp"

LRUCache<int, std::string> cache(100);  // Capacity 100
cache.put(1, "one");
auto value = cache.get(1);  // Returns std::optional<std::string>
```

#### Defer (`src/utils/defer.h`)
RAII-style deferred execution (Go's defer in C++).

```cpp
#include "utils/defer.h"

FILE* file = fopen("data.txt", "r");
DEFER { fclose(file); };  // Will execute when scope exits
// Use file...
```

## Building

### Build Script (Recommended)

```bash
./build.sh [BUILD_TYPE] [OPTIONS]
```

**Build Types:**
- `DEBUG` - Debug symbols, no optimization
- `RELEASE` - Optimized release build (-O3)
- `ASAN` - Address Sanitizer (detects memory errors)
- `LSAN` - Leak Sanitizer (detects memory leaks)
- `UBSAN` - Undefined Behavior Sanitizer

**Examples:**
```bash
./build.sh                    # Default: ASAN build
BUILD_TYPE=RELEASE ./build.sh # Release build
./build.sh ASAN --verbose     # Verbose output
```

### Manual CMake Build

```bash
mkdir -p build_ASAN
cd build_ASAN
cmake .. \
    -DCMAKE_BUILD_TYPE=ASAN \
    -DCMAKE_CXX_STANDARD=20 \
    -DCMAKE_CXX_COMPILER=clang++
make -j$(nproc)
```

### Build Options

| Option | Description | Default |
|--------|-------------|---------|
| `USE_SSE4_2` | Enable SSE4.2 instructions | ON |
| `USE_BMI_2` | Enable BMI2 instructions | ON |
| `USE_AVX2` | Enable AVX2 instructions | ON |
| `USE_AVX512` | Enable AVX512 instructions | OFF |

## Testing

### Running Tests

```bash
# Build first
./build.sh

# Run all tests
cd build_ASAN
ctest --output-on-failure

# Run with verbose output
ctest -V

# Run specific test category
./common_test      # Common component tests
./utils_test       # Utility tests
./interview_test   # Interview problem tests
```

### Test Structure

```
test/
├── common/          # Data structure tests
│   ├── skiplist_test.cc
│   ├── btree_test.cc
│   └── ...
├── utils/           # Utility tests
│   ├── defer_test.cc
│   ├── thread_pool_test.cc
│   └── ...
├── interview/       # Interview problem solutions
└── tools/           # Testing utilities
```

### Writing Tests

```cpp
#include <gtest/gtest.h>
#include "common/skiplist/SkipList.h"

using namespace cclab;

TEST(SkipListTest, BasicOperations) {
    SkipList<int> list;

    // Insertion
    EXPECT_TRUE(list.insert(42));
    EXPECT_TRUE(list.insert(17));

    // Search
    EXPECT_TRUE(list.contains(42));
    EXPECT_FALSE(list.contains(100));

    // Size
    EXPECT_EQ(list.size(), 2);
}

TEST(SkipListTest, EdgeCases) {
    SkipList<int> list;
    EXPECT_TRUE(list.empty());
    EXPECT_FALSE(list.contains(0));
}
```

## Project Structure

```
cc/cclab/
├── src/
│   ├── common/          # Data structures and algorithms
│   │   ├── btree/       # B-tree and B+ tree
│   │   ├── map/         # Hash maps
│   │   ├── queue/       # Lock-free queues
│   │   ├── skiplist/    # Skip list variants
│   │   ├── coroutine.h  # C++20 coroutines
│   │   └── cow.h        # Copy-on-write
│   ├── utils/           # Utility classes
│   │   ├── thread_pool.h
│   │   ├── lru.hpp
│   │   ├── defer.h
│   │   └── ...
│   └── experiment/      # Experimental code
├── test/
│   ├── common/          # Component tests
│   ├── utils/           # Utility tests
│   ├── interview/       # Interview problems
│   └── tools/           # Test utilities
├── CMakeLists.txt       # Build configuration
├── build.sh             # Build script
├── .clang-format        # Code formatting
├── .clang-tidy          # Static analysis
├── AGENTS.md            # AI agent guide
└── RULES.md             # Coding standards
```

## Documentation

- **[AGENTS.md](AGENTS.md)** - Guide for AI coding agents
- **[RULES.md](RULES.md)** - Coding standards and conventions
- **[docs/](docs/)** - Architecture and API documentation

### Code Style

The project uses clang-format and clang-tidy for consistent code style:

```bash
# Format all code
find src test -name "*.cc" -o -name "*.h" | xargs clang-format -i

# Run static analysis
clang-tidy src/common/skiplist/SkipList.h
```

## Contributing

1. Follow the coding standards in [RULES.md](RULES.md)
2. Add tests for new functionality
3. Ensure all tests pass with sanitizers
4. Run clang-format before committing

### Commit Message Format

```
<type>: <description>

<body>

Types:
- feat: New feature
- fix: Bug fix
- docs: Documentation changes
- test: Adding/updating tests
- refactor: Code refactoring
- perf: Performance improvements
```

## Dependencies

### Required
- CMake 3.22+
- C++20 compatible compiler
- pthread

### Optional
- Google Test (bundled or system)
- Abseil (for some components)
- Boost (for some benchmarks)

## License

MIT License - See LICENSE file for details.

## See Also

- [Parent Repository](../../README.md)
- [C++ Reference](https://en.cppreference.com/)
- [Google Test](https://google.github.io/googletest/)
