# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is a multi-language laboratory codebase with implementations in C++, Java, Python, Go, Rust, and shell scripts. The main focus appears to be on systems programming, data structures, and algorithms.

## C++ Codebase (cc/cclab)

### Build System
- Uses CMake as the build system
- Supports multiple build types: DEBUG, RELEASE, ASAN (Address Sanitizer), LSAN (Leak Sanitizer)
- Uses C++23 standard (can be changed to C++20 or C++17)
- Build with: `cd cc/cclab && ./build.sh`

### Key Components
- Data structures: SkipList, B+Tree, Robin Hood Hash Map, MPMC Queue
- Utilities: Thread pools, coroutines, consistent hash, LRU cache
- Experimental implementations and benchmarks

### Testing
- Uses Google Test framework
- Tests organized by modules in `cc/cclab/test/` directory
- Run tests with: `cd cc/cclab/build_* && ctest` or execute individual test binaries

## Python Codebase (python/pylab)

### Environment Setup
- Install dependencies with: `pip install -r python/pylab/requirements.txt`
- Uses pytest for testing

### Testing
- Run tests with: `cd python/pylab/test && make test`
- Individual tests can be run with: `pytest -s test_file.py`

## Java Codebase

### Build System
- Uses Gradle for build management
- Build with: `./gradlew build` in the respective project directory

## Rust Codebase

### Build System
- Uses Cargo for build management
- Build with: `cargo build` in the respective project directory