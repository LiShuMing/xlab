# TinyKV

[![C++20](https://img.shields.io/badge/C%2B%2B-20-blue.svg)](https://isocpp.org/std/the-standard)
[![CMake](https://img.shields.io/badge/CMake-3.16%2B-green.svg)](https://cmake.org)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A high-performance LSM-tree key-value store in modern C++20. TinyKV is designed as a learning project for practicing systems programming, storage engine design, and performance optimization.

## Features

- **LSM-Tree Architecture**: Log-Structured Merge Tree for write-optimized storage
- **MemTable**: In-memory write buffer using SkipList for O(log n) operations
- **Arena Allocator**: Efficient bulk memory management reducing malloc overhead
- **Modern C++20**: RAII, move semantics, constexpr, and zero-cost abstractions
- **Comprehensive Testing**: Unit tests with GoogleTest and microbenchmarks
- **Zero-Copy Design**: Slice-based references minimize memory copies

## Quick Start

### Prerequisites

- CMake 3.16 or higher
- C++20 compatible compiler (GCC 10+, Clang 12+, MSVC 2019+)
- Local thirdparty dependencies (googletest, benchmark in `cc/thirdparty/`)

### Build

```bash
cd cc/projects/kv-store
mkdir -p build && cd build
cmake ..
make -j$(nproc)
```

### Run Tests

```bash
ctest --output-on-failure
```

### Run Benchmarks

```bash
make tinykv_memtable_bench
./tinykv_memtable_bench
```

## Example Usage

```cpp
#include <tinykv/memtable/memtable.hpp>
#include <tinykv/memtable/arena.hpp>
#include <iostream>

int main() {
    // Create arena and memtable
    tinykv::Arena arena;
    tinykv::MemTable memtable(&arena);

    // Insert key-value pairs
    tinykv::Slice key("hello");
    tinykv::Slice value("world");

    tinykv::Status s = memtable.Put(key, value);
    if (!s.ok()) {
        std::cerr << "Put failed: " << s.ToString() << std::endl;
        return 1;
    }

    // Retrieve value
    std::string result;
    if (memtable.Get(key, &result)) {
        std::cout << "Found: " << result << std::endl;
    }

    return 0;
}
```

## Architecture

TinyKV follows a modular LSM-tree design with clear phase-based development:

### Phase 1: MemTable Foundation (Current)

| Component | Description | Complexity |
|-----------|-------------|------------|
| `Arena` | Bulk memory allocator | O(1) allocation |
| `SkipList` | Probabilistic ordered structure | O(log n) ops |
| `MemTable` | In-memory write buffer | O(log n) ops |
| `Slice` | Zero-copy string reference | O(1) ops |
| `Status` | Error handling | - |

### Phase 2: Durability (Planned)

- **WAL (Write-Ahead Log)**: Crash recovery with fsync
- **Record Format**: Length-prefixed records with CRC32 checksums
- **Recovery**: Replay WAL on startup

### Phase 3: SSTable (Planned)

- **Block Format**: Key-value blocks with prefix compression
- **Index Block**: Sparse index for efficient lookups
- **Footer**: Metadata and block offsets
- **Bloom Filter**: Optional false-positive filtering

### Phase 4: Version Management (Planned)

- **VersionSet**: Multi-level SSTable management
- **Manifest**: Persistent metadata log
- **Atomic Switch**: CURRENT file for atomic updates

### Phase 5: Compaction (Planned)

- **Leveled Compaction**: L0 → L1 → L2 → ...
- **Merging Iterator**: Multi-source iteration
- **Tombstone Handling**: Delete marker cleanup

## Project Structure

```
cc/projects/kv-store/
├── include/tinykv/          # Public headers
│   ├── common/              # Slice, Status, macros
│   ├── memtable/            # MemTable, SkipList, Arena
│   └── util/                # Comparator utilities
├── src/                     # Implementation files
│   └── memtable/            # MemTable components
├── tests/                   # Unit tests (gtest)
│   └── memtable/            # MemTable tests
├── bench/                   # Benchmarks
│   └── memtable/            # Performance tests
├── docs/                    # Documentation
│   ├── api/                 # API reference
│   └── architecture/        # Design documents
└── CMakeLists.txt           # Build configuration
```

## Performance

Microbenchmarks on Intel i7-9700K (GCC 11, -O2):

| Operation | Throughput | Latency (p99) |
|-----------|------------|---------------|
| MemTable Put | ~2.5M ops/sec | 0.8 µs |
| MemTable Get | ~3.0M ops/sec | 0.5 µs |

*Results may vary based on hardware and compiler.*

## Development

### Code Style

This project follows consistent C++ style guidelines:

- **Classes**: `PascalCase` (e.g., `SkipList`, `MemTable`)
- **Functions**: `camelCase` (e.g., `put()`, `get()`)
- **Variables**: `snake_case` with trailing underscore for members (e.g., `arena_`)
- **Constants**: `kPascalCase` (e.g., `kMaxHeight`)

See [RULES.md](./RULES.md) for complete coding standards.

### Running Format Check

```bash
make format
```

### Building with Sanitizers

```bash
cmake -DCMAKE_CXX_FLAGS="-fsanitize=address,undefined" ..
make
```

## Roadmap

- [x] Phase 1: MemTable + Arena + SkipList + Tests
- [ ] Phase 2: WAL + Crash Recovery
- [ ] Phase 3: SSTable Format + BlockBuilder
- [ ] Phase 4: VersionSet + Manifest
- [ ] Phase 5: Compaction + Leveled Structure
- [ ] Phase 6: Iterator Interface + Range Scans
- [ ] Phase 7: Bloom Filters + Optimizations

## Documentation

- [API Reference](./docs/api/)
- [Architecture Documentation](./docs/architecture/)
- [Agent Guide](./AGENTS.md) - For AI assistants
- [Coding Standards](./RULES.md)
- [TODOs](./TODOS.md)

## Contributing

This is a learning project. Contributions that improve code quality, add tests, or enhance documentation are welcome.

## License

MIT License - See LICENSE file for details.

## Acknowledgments

- Inspired by LevelDB and RocksDB design principles
- Built for learning systems programming and storage engine internals

---

*Previous Chinese documentation: See [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md) for the original Chinese implementation plan.*
