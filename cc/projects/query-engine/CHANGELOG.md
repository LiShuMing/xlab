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
- Core components:
  - `Vector<T>` - Columnar vector representation
  - `HashTable` - Robin Hood hash table for aggregation
  - `Chunk` - Row batch (collection of vectors)
  - `Status` - Error handling
  - `Slice` - String reference
- Query operators:
  - `ScanOp` - Data source scanner
  - `AggregateOp` - Hash aggregation
  - `SinkOp` - Result collector
- Hash functions for integer keys
- Testing infrastructure:
  - Google Test integration
  - Hash table unit tests
  - Aggregation tests
  - Vector tests
  - Hash join tests
  - Sort tests
  - Aggregation benchmarks
- Build system:
  - CMake 3.16+ configuration
  - Support for Debug and Release builds
- Code quality:
  - C++20 standard compliance
  - Compiler warnings enabled

### Technical Details

- C++20 standard
- Columnar (vectorized) execution model
- Robin Hood hash table with open addressing
- Pull-based operator pipeline
- Chunk-based processing (1024/4096 rows)

### Dependencies

- CMake 3.16+
- C++20 compiler (GCC 10+, Clang 12+)
- GoogleTest (in cc/thirdparty/googletest)
- Google Benchmark (in cc/thirdparty/benchmark)

[Unreleased]: https://github.com/LiShuMing/xlab/compare/vagg-v0.1.0...HEAD
[0.1.0]: https://github.com/LiShuMing/xlab/releases/tag/vagg-v0.1.0
