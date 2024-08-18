# AGENTS.md - cc/cclab

## Project Overview

**cc/cclab** is the core C++ laboratory containing data structures, algorithms, and system programming utilities. It serves as a research and experimentation platform for modern C++ features and high-performance computing patterns.

### Key Components

- **Data Structures**: SkipList, B+Tree, Robin Hood Hash Map, MPMC Queue, SPSC Queue
- **Utilities**: Thread pools, Coroutines, Consistent Hash, LRU Cache, File Operations
- **Concurrency**: Lock-free data structures, synchronization primitives

## Technology Stack

| Component | Version/Type |
|-----------|--------------|
| C++ Standard | C++20/23 (configurable) |
| Build System | CMake 3.22+ |
| Test Framework | Google Test |
| Compilers | GCC 11+, Clang 14+ |
| Code Formatter | clang-format (Google style) |
| Linter | clang-tidy |
| Sanitizers | ASAN, LSAN, UBSAN |

## Build Commands

### Quick Build
```bash
./build.sh                    # Default ASAN build
```

### Build Types
```bash
BUILD_TYPE=DEBUG ./build.sh      # Debug build
BUILD_TYPE=RELEASE ./build.sh    # Release build (optimized)
BUILD_TYPE=ASAN ./build.sh       # Address Sanitizer build
BUILD_TYPE=LSAN ./build.sh       # Leak Sanitizer build
BUILD_TYPE=UBSAN ./build.sh      # Undefined Behavior Sanitizer build
```

### Manual CMake Build
```bash
mkdir -p build_ASAN
cd build_ASAN
cmake .. -DCMAKE_BUILD_TYPE=ASAN -DCMAKE_CXX_STANDARD=20
make -j$(nproc)
```

## Test Commands

### Run All Tests
```bash
cd build_ASAN
ctest --output-on-failure
```

### Run Specific Test
```bash
cd build_ASAN
./common_test        # Run common tests
./utils_test         # Run utility tests
```

### Run with Verbosity
```bash
cd build_ASAN
ctest -V
```

## Directory Structure

```
cc/cclab/
├── src/
│   ├── common/          # Data structures and algorithms
│   │   ├── btree/       # B+Tree implementation
│   │   ├── map/         # Hash maps (Robin Hood)
│   │   ├── queue/       # Lock-free queues (MPMC, SPSC)
│   │   ├── skiplist/    # SkipList variants
│   │   └── ...
│   ├── utils/           # Utility classes and helpers
│   │   ├── thread_pool.h
│   │   ├── lru.hpp
│   │   └── ...
│   └── experiment/      # Experimental code
├── test/
│   ├── common/          # Tests for common components
│   ├── utils/           # Tests for utilities
│   ├── interview/       # Interview problem solutions
│   └── tools/           # Testing tools
├── CMakeLists.txt       # Main CMake configuration
├── build.sh             # Build script
├── .clang-format        # Code formatting rules
└── .clang-tidy          # Linting configuration
```

## Code Style Guidelines

### Formatting
- **Column Limit**: 100 characters
- **Indent**: 4 spaces
- **Pointer Alignment**: Left (`int* ptr` not `int *ptr`)
- **Brace Style**: Attach to control statements

```bash
# Format all source files
find src test -name "*.h" -o -name "*.hpp" -o -name "*.cpp" -o -name "*.cc" | xargs clang-format -i
```

### Linting
```bash
# Run clang-tidy
clang-tidy src/common/skiplist/SkipList.h
```

### Naming Conventions
- **Files**: lowercase_with_underscores (.h, .cpp)
- **Classes/Structs**: PascalCase
- **Functions**: camelCase
- **Variables**: snake_case
- **Constants**: kPascalCase or UPPER_SNAKE_CASE
- **Templates**: PascalCase with descriptive names

### Modern C++ Practices
- Use `std::make_unique` / `std::make_shared`
- Prefer smart pointers over raw pointers
- Use `[[nodiscard]]` for functions returning important values
- Use move semantics for large objects
- Use RAII for resource management

## Header Guidelines

All header files must use `#pragma once`:

```cpp
#pragma once

#include <vector>
// ... includes

namespace cclab {
// ... code
} // namespace cclab
```

## Testing Guidelines

### Test File Naming
- Test files use `.cc` extension
- Named `{component}_test.cc`

### Test Structure
```cpp
#include <gtest/gtest.h>
#include "common/skiplist/SkipList.h"

namespace cclab {
namespace test {

TEST(SkipListTest, BasicInsertion) {
    SkipList<int> list;
    list.insert(42);
    EXPECT_TRUE(list.contains(42));
}

} // namespace test
} // namespace cclab
```

## Sanitizer Usage

### Address Sanitizer (ASAN)
Detects memory errors (use-after-free, buffer overflow, etc.)
```bash
BUILD_TYPE=ASAN ./build.sh
```

### Leak Sanitizer (LSAN)
Detects memory leaks
```bash
BUILD_TYPE=LSAN ./build.sh
```

### Undefined Behavior Sanitizer (UBSAN)
Detects undefined behavior
```bash
BUILD_TYPE=UBSAN ./build.sh
```

## Important Files

| File | Purpose |
|------|---------|
| `CMakeLists.txt` | Main CMake configuration |
| `build.sh` | Convenience build script |
| `.clang-format` | Code formatting rules |
| `.clang-tidy` | Static analysis rules |
| `test/CMakeLists.txt` | Test configuration |

## Dependencies

### Required
- CMake 3.22+
- C++ compiler (GCC 11+ or Clang 14+)
- pthread

### Optional (for some components)
- Google Test (included as submodule or system package)
- Abseil (for some tests)
- Boost (for some components)

## Common Tasks

### Adding a New Component
1. Create header in `src/common/` or `src/utils/`
2. Add tests in `test/common/` or `test/utils/`
3. Update `CMakeLists.txt` if needed
4. Run tests: `./build.sh ASAN && cd build_ASAN && ctest`

### Adding a New Test
1. Create `{name}_test.cc` in appropriate test directory
2. Include `<gtest/gtest.h>` and component header
3. Write TEST() or TEST_F() cases
4. Rebuild and run tests

## Debugging Tips

### With GDB
```bash
cd build_DEBUG
gdb ./common_test
```

### With LLDB
```bash
cd build_DEBUG
lldb ./common_test
```

### Sanitizer Output
When ASAN/LSAN/UBSAN detect issues, they print detailed stack traces. Use `ASAN_SYMBOLIZER_PATH` for better output:
```bash
ASAN_SYMBOLIZER_PATH=/usr/bin/llvm-symbolizer ./common_test
```

## Contact & References

- **Repository**: https://github.com/LiShuMing/xlab
- **Parent AGENTS.md**: See `/home/lism/work/xlab/AGENTS.md`
