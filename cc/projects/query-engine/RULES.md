# Vectorized Query Engine (vagg) Coding Standards

This document defines coding standards for the vagg project, following Harness Engineering standards for modern C++.

## Naming Conventions

### Types (Classes, Structs, Enums, Typedefs)

- Use **PascalCase**
- Examples: `HashTable`, `Vector`, `AggregateOp`, `DataType`

```cpp
class HashTable {
    // ...
};

enum class DataType {
    kInt32,
    kInt64,
    kString
};
```

### Functions and Methods

- Use **camelCase**
- Examples: `findOrInsert()`, `next()`, `prepare()`, `isNull()`

```cpp
class Operator {
public:
    Status prepare(ExecContext* ctx);
    Status next(Chunk* out);
    bool isNull(int index) const;
};
```

### Variables

- Use **snake_case**
- Member variables: trailing underscore (`member_variable_`)
- Examples: `hash_table_`, `num_rows_`, `current_key`

```cpp
class HashTable {
private:
    uint8_t* ctrl_;
    Entry* entries_;
    size_t capacity_;
    size_t size_;
};
```

### Constants

- Use **kPascalCase** for constants
- Examples: `kMaxLoadFactor`, `kDefaultChunkSize`

```cpp
constexpr double kMaxLoadFactor = 0.85;
constexpr int kDefaultChunkSize = 1024;
```

### Macros

- Use **UPPER_SNAKE_CASE**
- Prefer `constexpr` or `const` over macros when possible
- Examples: `VAGG_RETURN_NOT_OK`, `VAGG_LIKELY`

```cpp
#define VAGG_RETURN_NOT_OK(status) \
    do { \
        auto _s = (status); \
        if (!_s.ok()) return _s; \
    } while (0)

// Prefer constexpr
constexpr size_t kCacheLineSize = 64;
```

### File Names

- Headers: **snake_case.h** or **snake_case.hpp**
- Source: **snake_case.cc** or **snake_case.cpp**
- Examples: `hash_table.h`, `aggregate_op.cc`

## Formatting

### Column Limit

- **100 columns** maximum line length
- Break lines at logical points

### Indentation

- 4 spaces (no tabs)
- Brace style: K&R

```cpp
class AggregateOp : public Operator {
public:
    explicit AggregateOp(std::unique_ptr<Operator> child);

    Status next(Chunk* out) override {
        if (!prepared_) {
            return Status::InvalidState("Not prepared");
        }
        // ...
    }

private:
    bool prepared_ = false;
};
```

### Include Order

```cpp
// 1. Associated header
#include "vagg/ops/aggregate_op.h"

// 2. Project headers
#include "vagg/vector/vector.h"
#include "vagg/ht/hash_table.h"

// 3. Third-party headers
#include <gtest/gtest.h>

// 4. System headers
#include <cstdint>
#include <memory>
#include <vector>
```

## Modern C++ Guidelines

### C++20 Features

- Use concepts for template constraints
- Use `[[nodiscard]]` for important returns
- Use designated initializers

```cpp
[[nodiscard]] Status next(Chunk* out);
[[nodiscard]] bool empty() const noexcept;
```

### Memory Management

- Prefer stack allocation
- Use unique_ptr for ownership
- Avoid raw new/delete

```cpp
std::unique_ptr<Operator> scan_op = std::make_unique<ScanOp>(source);
```

### Error Handling

- Use `Status` for recoverable errors
- Use `VAGG_RETURN_NOT_OK` macro
- Check Status with `ok()`

```cpp
VAGG_RETURN_NOT_OK(child_->prepare(ctx));
Status s = hash_table_->Insert(key, &entry);
if (!s.ok()) return s;
```

### Type Safety

- Use `explicit` on single-argument constructors
- Prefer `enum class` over `enum`
- Use `const` aggressively

```cpp
explicit Vector(size_t size);
const Chunk* input() const { return input_.get(); }
```

### Const Correctness

```cpp
class Vector {
public:
    size_t size() const { return size_; }
    const int64_t* data() const { return data_; }
};
```

## Testing Standards

### Test Naming

```cpp
TEST(HashTableTest, InsertAndFind) { }
TEST(AggregateOpTest, SumSingleGroup) { }
```

### Test Structure

```cpp
TEST(ComponentTest, SpecificBehavior) {
    // Arrange
    Component component;

    // Act
    auto result = component.process(input);

    // Assert
    EXPECT_EQ(result, expected);
}
```

## Performance Guidelines

### Hot Paths

- Minimize allocations in loops
- Use prefetching for hash table access
- Keep branches predictable

```cpp
// Prefetch next bucket
__builtin_prefetch(&ctrl_[next_index]);
```

### Vectorization

- Process data in chunks
- Use columnar layout
- Avoid branching in inner loops

## References

- [C++ Core Guidelines](https://isocpp.github.io/CppCoreGuidelines/)
- [Project README](./README.md)
- [AGENTS.md](./AGENTS.md)
