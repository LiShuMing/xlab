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
- Data structures:
  - SkipList with probabilistic leveling
  - B+Tree for ordered data
  - Robin Hood Hash Map
  - MPMC Queue (lock-free)
  - SPSC Queue (lock-free)
  - Blocking Queue
- Utilities:
  - Thread Pool with work stealing
  - LRU Cache
  - Defer (RAII-style cleanup)
  - File and process operations
  - Environment variable handling
  - SIMD operations
- Concurrency:
  - Coroutine utilities (C++20)
  - Copy-on-write wrapper
  - Synchronization primitives
- Tests:
  - Google Test integration
  - Unit tests for core components
  - Interview problem solutions
- Build system:
  - CMake configuration with multiple build types
  - build.sh script for easy building
  - Support for DEBUG, RELEASE, ASAN, LSAN, UBSAN builds
- Code quality:
  - clang-format configuration
  - clang-tidy configuration

### Technical Details
- C++20/23 standard support
- CMake 3.22+ required
- Google Test for unit testing
- Sanitizer support for debugging

[Unreleased]: https://github.com/LiShuMing/xlab/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/LiShuMing/xlab/releases/tag/v0.1.0
