# C++ Lab

A comprehensive C++ laboratory for experimenting with data structures, algorithms, benchmarks, and utilities.

## Overview

This project contains:
- **Data Structures**: B-trees, skip lists, hash maps, queues
- **Benchmarks**: Performance testing for various data structures and algorithms
- **Utilities**: Common C++ utilities and helpers
- **Experiments**: Experimental code and prototypes
- **Tests**: Comprehensive test suite

## Building

The project uses CMake for building:

```bash
./build.sh
```

Or manually:

```bash
mkdir -p build
cd build
cmake -DCMAKE_BUILD_TYPE=Release ..
make -j$(nproc)
```

### Build Types

- `DEBUG`: Debug build with symbols and no optimization
- `RELEASE`: Optimized release build
- `ASAN`: Address sanitizer build
- `LSAN`: Leak sanitizer build

## Project Structure

### Source Code (`src/`)

- **`common/`**: Common data structures and utilities
  - `btree/`: B-tree and B+ tree implementations
  - `skiplist/`: Skip list data structure
  - `consistent_hash/`: Consistent hashing implementation
  - `map/`: Map implementations (robin_hood_map)
  - `queue/`: Queue implementations (MPMC, SPMC, SPSC, blocking queues)
  - `coroutine.h`: Coroutine utilities
  - `cow.h`: Copy-on-write utilities

- **`bench/`**: Benchmarking code
  - `hashmap/`: Hash map benchmarks comparing different implementations
  - `queue/`: Queue performance benchmarks
  - Various CPU and memory performance benchmarks

- **`experiment/`**: Experimental code
  - `helloworld.cc`: Simple hello world example

- **`utils/`**: Utility functions
  - File operations, process operations, thread pools, defer utilities, etc.

### Tests (`test/`)

- **`common/`**: Tests for common data structures and utilities
- **`interview/`**: Interview problem solutions
- **`tools/`**: Testing tools and utilities
- **`utils/`**: Tests for utility functions

## Running Tests

```bash
# Build first
./build.sh

# Run all tests
cd build
ctest --output-on-failure

# Run specific test
./build/test/common/btree_test
```

## Features

### Data Structures

- **B-trees and B+ trees**: Efficient ordered data structures
- **Skip Lists**: Probabilistic data structure for ordered sets
- **Hash Maps**: Multiple implementations including robin_hood_map
- **Queues**: Various queue implementations (lock-free, blocking, etc.)

### Benchmarks

The benchmark suite includes:
- Hash map performance comparisons
- Queue throughput tests
- CPU performance analysis
- Memory cache behavior studies

### Utilities

- Thread pools and task management
- File and process operations
- Defer utilities (RAII-style cleanup)
- Environment variable handling
- SIMD operations

## Dependencies

- C++20 standard
- CMake 3.12+
- Thread support (pthread)
- Optional: fmt library (included in thirdparty/)

## Configuration Options

The CMakeLists.txt supports various configuration options:
- `USE_SSE4_2`: Enable SSE4.2 instructions
- `USE_BMI_2`: Enable BMI2 instructions
- `USE_AVX2`: Enable AVX2 instructions
- `USE_AVX512`: Enable AVX512 instructions (disabled by default)

