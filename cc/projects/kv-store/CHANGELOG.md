# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Modern project documentation (AGENTS.md, RULES.md)
- Enhanced README with badges and quick start
- This CHANGELOG file

## [0.1.0] - 2025-03-29

### Added
- Initial project structure with CMake build system
- Core data structures:
  - `Arena` - Memory allocator for reducing malloc overhead
  - `SkipList` - Probabilistic ordered data structure for MemTable
  - `MemTable` - In-memory write buffer using SkipList
- Common utilities:
  - `Slice` - Lightweight non-owning string reference
  - `Status` - Error handling with codes and messages
  - `Comparator` - Key comparison interface
- Testing infrastructure:
  - Google Test integration
  - SkipList unit tests
  - MemTable unit tests
  - MemTable benchmarks with Google Benchmark
- Build system:
  - CMake 3.16+ configuration
  - Support for Debug and Release builds
  - Code formatting target with clang-format
  - Install rules
- Code quality:
  - clang-format configuration
  - Compiler warnings enabled (-Wall -Wextra -Wpedantic)

### Phase 1: MemTable Foundation

This release implements Phase 1 of the TinyKV roadmap:

- **MemTable**: In-memory KV store with O(log n) operations
- **SkipList**: Lock-free friendly ordered structure
- **Arena**: Efficient bulk memory allocation
- **Testing**: Comprehensive unit tests and microbenchmarks

### Technical Details

- C++20 standard
- Header-only templates where appropriate
- Arena-based memory management for hot paths
- Slice-based zero-copy key/value references
- Status-based error handling

### Dependencies

- CMake 3.16+
- C++20 compiler (GCC 10+, Clang 12+)
- GoogleTest (in cc/thirdparty/googletest)
- Google Benchmark (in cc/thirdparty/benchmark)

[Unreleased]: https://github.com/LiShuMing/xlab/compare/tinykv-v0.1.0...HEAD
[0.1.0]: https://github.com/LiShuMing/xlab/releases/tag/tinykv-v0.1.0
