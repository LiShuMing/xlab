# RULES.md - cc/cclab

## Project Rules and Conventions

This document defines the coding standards, conventions, and rules for the cc/cclab project.

## C++ Standards

### Language Standard
- **Primary**: C++20
- **Experimental**: C++23 (where supported)
- **Minimum**: C++17 (for compatibility)

### Compiler Requirements
- GCC 11+
- Clang 14+
- MSVC 2022 (experimental)

## Code Style Rules

### Naming Conventions

| Element | Convention | Example |
|---------|------------|---------|
| Files | snake_case | `skip_list.h`, `thread_pool.cpp` |
| Directories | snake_case | `consistent_hash/`, `thread_pool/` |
| Classes/Structs | PascalCase | `SkipList`, `ThreadPool` |
| Functions | camelCase | `insert()`, `getValue()` |
| Variables | snake_case | `node_count`, `buffer_size` |
| Member Variables | snake_case with trailing underscore | `size_`, `capacity_` |
| Constants | kPascalCase | `kDefaultCapacity`, `kMaxSize` |
| Macros | UPPER_SNAKE_CASE | `CCLAB_ASSERT`, `LIKELY` |
| Templates | PascalCase | `Allocator`, `Compare` |
| Enums | PascalCase for type, kPascalCase for values | `enum class Status { kOk, kError }` |
| Namespaces | snake_case | `namespace cclab { }` |

### Formatting Rules

From `.clang-format`:
- **Column Limit**: 100
- **Indent Width**: 4 spaces
- **Continuation Indent**: 4
- **Tab Width**: 4
- **Use Tab**: Never
- **Pointer Alignment**: Left (`int* ptr`)
- **Reference Alignment**: Left (`int& ref`)
- **Brace Style**: Attach (K&R style)
- **Allow Short Functions on Single Line**: true
- **Always Break Template Declarations**: Yes

### Example
```cpp
#pragma once

#include <vector>
#include <memory>

namespace cclab {

constexpr size_t kDefaultCapacity = 1024;

class DataProcessor {
public:
    explicit DataProcessor(size_t capacity = kDefaultCapacity)
        : capacity_(capacity), size_(0) {}

    [[nodiscard]] bool process(const std::vector<int>& data);
    [[nodiscard]] size_t size() const { return size_; }

private:
    size_t capacity_;
    size_t size_;
    std::unique_ptr<int[]> buffer_;
};

} // namespace cclab
```

## Include Order

```cpp
#pragma once  // First line for headers

// 1. Standard library headers
#include <vector>
#include <memory>
#include <string>

// 2. Third-party headers
#include <gtest/gtest.h>
#include <absl/container/flat_hash_map.h>

// 3. Project headers (alphabetical within sections)
#include "common/skiplist/SkipList.h"
#include "utils/thread_pool.h"
```

## Testing Rules

### Test File Naming
- Pattern: `{component}_test.cc`
- Location: `test/common/` or `test/utils/`
- Extension: `.cc` (not `.cpp`)

### Test Structure
```cpp
#include <gtest/gtest.h>
#include "common/component/Component.h"

namespace cclab {
namespace test {

// Use descriptive test names
class ComponentTest : public ::testing::Test {
protected:
    void SetUp() override {
        // Setup code
    }

    void TearDown() override {
        // Cleanup code
    }

    Component component_;
};

// Simple tests
TEST(ComponentTest, BasicOperation) {
    Component c;
    EXPECT_TRUE(c.empty());
    EXPECT_EQ(c.size(), 0);
}

// Fixture-based tests
TEST_F(ComponentTest, InsertAndRetrieve) {
    component_.insert(42);
    EXPECT_EQ(component_.size(), 1);
    EXPECT_TRUE(component_.contains(42));
}

// Edge cases
TEST(ComponentTest, HandlesEmptyInput) {
    Component c;
    EXPECT_FALSE(c.contains(0));
}

// Error conditions
TEST(ComponentTest, ThrowsOnInvalidAccess) {
    Component c;
    EXPECT_THROW(c.at(0), std::out_of_range);
}

} // namespace test
} // namespace cclab
```

### Test Coverage Requirements
- **Minimum**: 80% line coverage for core components
- **Required Tests**:
  - Happy path (normal operation)
  - Edge cases (empty, single element, maximum)
  - Error conditions (exceptions, error returns)
  - Boundary conditions

## Documentation Rules

### File Header
```cpp
#pragma once

/**
 * @file skip_list.h
 * @brief SkipList implementation with O(log n) operations
 *
 * This file contains the SkipList data structure implementation
 * providing logarithmic time complexity for search, insert, and delete.
 */
```

### Class Documentation
```cpp
/**
 * @brief Thread-safe skip list implementation
 *
 * @tparam T Type of elements stored in the list
 * @tparam Compare Comparison function object (default: std::less<T>)
 *
 * Thread safety: All public methods are thread-safe.
 */
template <typename T, typename Compare = std::less<T>>
class SkipList {
public:
    /**
     * @brief Insert a value into the list
     *
     * @param value The value to insert
     * @return true if inserted, false if already exists
     * @complexity O(log n) average case
     */
    bool insert(const T& value);
};
```

### Function Documentation
```cpp
/**
 * @brief Process input data and return result
 *
 * @param input Input data vector
 * @param options Processing options (optional)
 * @return Processed result
 * @throw std::invalid_argument if input is empty
 * @note This function is thread-safe
 */
Result processData(const std::vector<int>& input,
                   const Options& options = {});
```

## Modern C++ Rules

### Required Practices
1. **Smart Pointers**: Use `std::unique_ptr` / `std::make_unique`
2. **RAII**: Resources acquired in constructor, released in destructor
3. **nodiscard**: Mark functions whose return values must not be ignored
4. **override**: Always use when overriding virtual functions
5. **final**: Use when class/method should not be overridden
6. **constexpr**: Use for compile-time computable values
7. **const**: Use for methods that don't modify object state

### Forbidden Practices
1. **Raw new/delete**: Use smart pointers
2. **Manual memory management**: Use containers and RAII
3. **C-style casts**: Use static_cast, dynamic_cast, reinterpret_cast
4. **NULL**: Use nullptr
5. **Macros**: Prefer constexpr/inline functions
6. **Exceptions for control flow**: Use only for exceptional conditions

### Example
```cpp
// GOOD
std::unique_ptr<Resource> createResource() {
    return std::make_unique<Resource>();
}

// BAD
Resource* createResource() {
    return new Resource();  // Memory leak risk
}

// GOOD
[[nodiscard]] bool isEmpty() const {
    return size_ == 0;
}

// GOOD
void process(const Item& item) override {
    // Implementation
}
```

## Concurrency Rules

### Thread Safety Annotations
```cpp
class ThreadSafeCounter {
public:
    void increment() {
        std::lock_guard<std::mutex> lock(mutex_);
        ++count_;
    }

    [[nodiscard]] int get() const {
        std::lock_guard<std::mutex> lock(mutex_);
        return count_;
    }

private:
    mutable std::mutex mutex_;
    int count_ = 0;
};
```

### Lock-Free Code
- Document memory ordering requirements
- Use std::atomic with explicit memory_order when needed
- Prefer seq_cst (default) unless performance critical

## Error Handling Rules

### Exceptions
- Use exceptions for exceptional conditions
- Use return values for expected failures
- Document exceptions thrown in function comments

```cpp
// Exception for exceptional case
void openFile(const std::string& path) {
    if (!std::filesystem::exists(path)) {
        throw std::runtime_error("File not found: " + path);
    }
    // ...
}

// Return value for expected case
[[nodiscard]] std::optional<Value> find(const Key& key) {
    auto it = map_.find(key);
    if (it == map_.end()) {
        return std::nullopt;
    }
    return it->second;
}
```

## Build Rules

### CMake Requirements
- Minimum version: 3.22
- Use target-based properties (not global)
- Specify compile features explicitly

```cmake
add_library(common INTERFACE)
target_compile_features(common INTERFACE cxx_std_20)
target_include_directories(common INTERFACE ${CMAKE_CURRENT_SOURCE_DIR}/src)
```

### Compiler Warnings
Treat warnings as errors in release builds:
```cmake
target_compile_options(target PRIVATE -Wall -Wextra -Werror)
```

## Git Commit Rules

### Commit Message Format
```
<type>: <short description>

<body>

Co-Authored-By: Claude <noreply@anthropic.com>
```

### Types
- **feat**: New feature
- **fix**: Bug fix
- **docs**: Documentation changes
- **style**: Code style changes (formatting)
- **refactor**: Code refactoring
- **test**: Adding or updating tests
- **chore**: Build/config/tooling changes

### Examples
```
feat: add lock-free MPMC queue implementation

fix: correct boundary check in B+Tree insertion

test: add concurrent access tests for SkipList

docs: update AGENTS.md with build instructions
```

## Code Review Checklist

Before submitting code:

- [ ] Code compiles without warnings
- [ ] All tests pass
- [ ] clang-format applied
- [ ] clang-tidy passes
- [ ] New code has tests
- [ ] Documentation updated
- [ ] Commit message follows convention
