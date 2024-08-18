# C++ Lab (cc/cclab)

## Overview
Main C++ laboratory with focus on systems programming, data structures, and algorithms. C++23 standard with CMake build system.

## Build System
- **Build Tool**: CMake
- **Build Types**: DEBUG, RELEASE, ASAN, LSAN
- **Compiler**: C++23 (can use C++20/C++17 if needed)
- **Build Command**: `cd cc/cclab && ./build.sh`
- **Test Command**: `cd cc/cclab/build_* && ctest`

## Project Structure
```
cc/
├── cclab/           # Main C++ lab with data structures
│   ├── src/         # Source files
│   ├── include/     # Headers
│   ├── test/        # Google Test tests
│   └── build.sh     # Build script
├── algo/            # Algorithm implementations
├── ccbench/         # Benchmarks
├── srlab/           # Serialization lab
├── simd/            # SIMD experiments
├── golab/           # Go language lab (mixed)
├── projects/        # Personal projects
├── thirdparty/      # External dependencies
├── extentions/      # Language extensions
└── nasm/            # Assembly code
```

## Key Components
- **Data Structures**: SkipList, B+Tree, Robin Hood Hash Map, MPSC/MPMC Queue
- **Utilities**: Thread pools, coroutines, consistent hash, LRU cache
- **Testing**: Google Test framework

## Coding Conventions
- Use `.clang-format` and `.clang-tidy` for formatting/linting
- Follow RAII principles
- Prefer `std::` containers over raw arrays
- Use `[[nodiscard]], [[likely]], [[unlikely]]` attributes
- Pass by reference for expensive types

## AI Vibe Coding Tips
- Generate compilable code first, then optimize
- Include proper headers (no incomplete code)
- Use `std::make_unique` / `std::make_shared` for owned pointers
- Consider move semantics for large objects
- Handle edge cases: empty containers, null pointers, boundary conditions
- Add comments for non-obvious logic
