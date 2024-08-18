# TinyKV Coding Standards

This document defines coding standards for the TinyKV project, following Harness Engineering standards for modern C++.

## Naming Conventions

### Types (Classes, Structs, Enums, Typedefs)

- Use **PascalCase**
- Examples: `SkipList`, `MemTable`, `Arena`, `StatusCode`

```cpp
class SkipList {
    // ...
};

enum class StatusCode {
    kOk,
    kNotFound,
    kCorruption
};
```

### Functions and Methods

- Use **camelCase**
- Examples: `put()`, `get()`, `allocateMemory()`, `isEmpty()`

```cpp
class MemTable {
public:
    Status put(const Slice& key, const Slice& value);
    bool get(const Slice& key, std::string* value);
    bool isEmpty() const;
};
```

### Variables

- Use **snake_case**
- Member variables: trailing underscore (`member_variable_`)
- Examples: `arena_`, `max_height_`, `current_key`

```cpp
class SkipList {
private:
    Arena* const arena_;
    Node* const head_;
    int max_height_;
};
```

### Constants

- Use **kPascalCase** for constants
- Examples: `kMaxHeight`, `kBranching`

```cpp
constexpr int kMaxHeight = 12;
constexpr double kBranching = 0.25;
```

### Macros

- Use **UPPER_SNAKE_CASE**
- Prefer `constexpr` or `const` over macros when possible
- Examples: `TINYKV_VERSION`, `LIKELY(x)`

```cpp
#define TINYKV_VERSION_MAJOR 0
#define TINYKV_VERSION_MINOR 1

// Prefer constexpr
constexpr int kVersionMajor = 0;
```

### File Names

- Headers: **snake_case.hpp** for C++ headers
- Source: **snake_case.cpp**
- Examples: `skiplist.hpp`, `memtable.cpp`

## Formatting

### Column Limit

- **100 columns** maximum line length
- Break lines at logical points (operators, commas)

### Indentation

- 4 spaces (no tabs)
- Brace style: K&R (opening brace on same line for functions/classes)

```cpp
class MemTable {
public:
    explicit MemTable(Arena* arena);
    ~MemTable();

    Status put(const Slice& key, const Slice& value) {
        if (key.empty()) {
            return Status::InvalidArgument("Empty key");
        }
        // ...
    }

private:
    Arena* arena_;
};
```

### Include Order

```cpp
// 1. Associated header (for .cpp files)
#include "tinykv/memtable/memtable.hpp"

// 2. Project headers
#include "tinykv/common/slice.hpp"
#include "tinykv/common/status.hpp"

// 3. Third-party headers
#include <gtest/gtest.h>

// 4. System headers (alphabetically)
#include <atomic>
#include <cstddef>
#include <memory>
#include <string>
#include <vector>
```

## Modern C++ Guidelines

### C++20 Features

- Use `std::string_view` where appropriate (prefer Slice for consistency)
- Use concepts for template constraints where beneficial
- Use designated initializers for clarity
- Use `[[nodiscard]]` for functions where ignoring return is likely a bug

```cpp
[[nodiscard]] Status put(const Slice& key, const Slice& value);
[[nodiscard]] bool empty() const noexcept;
```

### Memory Management

- Prefer stack allocation
- Use Arena for bulk allocations in hot paths
- Avoid raw `new`/`delete` in application code
- Use smart pointers for ownership (`std::unique_ptr`, `std::shared_ptr`)

```cpp
// Good - Arena allocation
char* mem = arena_->Allocate(node_size);

// Good - Smart pointer
std::unique_ptr<Table> table = std::make_unique<Table>(options);
```

### Error Handling

- Use `Status` for recoverable errors
- Use exceptions only for truly exceptional conditions
- Check Status with `ok()` method
- Use `[[nodiscard]]` on Status-returning functions

```cpp
Status s = db->Put(key, value);
if (!s.ok()) {
    LOG_ERROR("Put failed: %s", s.ToString().c_str());
    return s;
}
```

### Type Safety

- Use `explicit` on single-argument constructors
- Prefer `enum class` over plain `enum`
- Use `std::size_t` for sizes and indices
- Use `const` aggressively

```cpp
class Slice {
public:
    explicit Slice(const std::string& str);
    explicit Slice(const char* data, size_t size);
    // ...
};
```

### Const Correctness

- Member functions that don't modify should be `const`
- Pass non-primitive types by const reference
- Return values by const reference when appropriate

```cpp
class MemTable {
public:
    size_t memoryUsage() const { return arena_->MemoryUsage(); }
    bool contains(const Slice& key) const;
};
```

### Move Semantics

- Implement move constructor/assignment for resource-managing classes
- Use `std::move` to enable moves
- Use `noexcept` on move operations

```cpp
class WriteBatch {
public:
    WriteBatch(WriteBatch&& other) noexcept;
    WriteBatch& operator=(WriteBatch&& other) noexcept;
};
```

## Testing Standards

### Test Naming

- Test suite: `<Component>Test` (e.g., `SkipListTest`)
- Test case: `<Action><Condition>` (e.g., `PutEmptyKeyFails`)

```cpp
TEST(SkipListTest, InsertAndFind) {
    // ...
}

TEST(SkipListTest, InsertDuplicateKeyUpdatesValue) {
    // ...
}
```

### Test Structure

```cpp
TEST(ComponentTest, SpecificBehavior) {
    // Arrange
    Component component;
    Input input = CreateTestInput();

    // Act
    auto result = component.Process(input);

    // Assert
    EXPECT_EQ(result.status, Status::OK());
    EXPECT_EQ(result.value, expected_value);
}
```

### Assertion Selection

- Use `ASSERT_*` when failure means subsequent checks are invalid
- Use `EXPECT_*` when multiple independent checks are possible

```cpp
ASSERT_NE(ptr, nullptr);        // Fatal - can't use ptr if null
EXPECT_EQ(ptr->size(), 10);     // Non-fatal - continue on failure
```

## Performance Guidelines

### Hot Paths

- Minimize heap allocations
- Use Arena for bulk allocations
- Keep branch prediction friendly (likely/unlikely hints)
- Prefer cache-friendly data structures

```cpp
// Cache-friendly iteration
for (const auto& item : container) {
    // Process item
}
```

### Compiler Hints

```cpp
#define LIKELY(x) __builtin_expect(!!(x), 1)
#define UNLIKELY(x) __builtin_expect(!!(x), 0)

if (UNLIKELY(key.empty())) {
    return Status::InvalidArgument("Empty key");
}
```

### Inlining

- Small, frequently-called functions: inline in header
- Large functions: implementation in .cpp
- Let compiler decide for most cases

```cpp
// In header - small getter
inline size_t Arena::MemoryUsage() const {
    return memory_usage_.load(std::memory_order_relaxed);
}
```

## Documentation

### File Headers

```cpp
// Copyright (c) 2025 TinyKV Authors
// SPDX-License-Identifier: MIT

#pragma once

// Brief description of this file's purpose
```

### Class Documentation

```cpp
/**
 * @brief In-memory sorted table using SkipList
 *
 * MemTable serves as the write buffer for the LSM tree.
 * All writes go to the active MemTable first, then to WAL.
 * Thread-unsafe: requires external synchronization.
 */
class MemTable {
    // ...
};
```

### Function Documentation

```cpp
/**
 * @brief Insert a key-value pair into the memtable
 *
 * @param key The key to insert (must not be empty)
 * @param value The value to associate with the key
 * @return Status::OK() on success, error status otherwise
 *
 * @note This operation is not thread-safe
 */
Status put(const Slice& key, const Slice& value);
```

## Code Quality Tools

### clang-format

Configuration is in `.clang-format` at project root. Run with:

```bash
make format
```

### clang-tidy

Enable checks progressively:

```bash
clang-tidy src/*.cpp -- -I include
```

Recommended checks:
- `cppcoreguidelines-*`
- `modernize-*`
- `performance-*`
- `readability-*`

### Sanitizers

Build with sanitizers for debugging:

```bash
cmake -DCMAKE_BUILD_TYPE=Debug \
      -DCMAKE_CXX_FLAGS="-fsanitize=address,undefined" ..
```

## References

- [C++ Core Guidelines](https://isocpp.github.io/CppCoreGuidelines/CppCoreGuidelines)
- [Google C++ Style Guide](https://google.github.io/styleguide/cppguide.html)
- [Project README](./README.md)
- [AGENTS.md](./AGENTS.md)
