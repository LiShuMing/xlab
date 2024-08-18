---
created: 2026-03-27
topics: [database, query-execution, performance]
projects: [query-engine, py-toydb]
review: 2026-03-30
stage: active
---

# Vectorized Execution

## Overview

Vectorized execution processes data in batches (vectors) rather than row-by-row, enabling SIMD instructions and better cache utilization.

**Row-by-row (Iterator Model):**
```python
for row in table:
    result = process(row)
    yield result
```

**Vectorized (Batch Model):**
```python
for batch in table.chunks(1024):
    result = process_batch(batch)  # SIMD-friendly
    yield result
```

## Why Vectorized?

| Aspect | Row-by-row | Vectorized |
|--------|-----------|------------|
| Function calls | Per row | Per batch (amortized) |
| Cache efficiency | Poor (scattered access) | Good (sequential) |
| SIMD | Hard | Natural |
| Branch prediction | Unpredictable | More predictable |
| Interpretation overhead | High | Low |

**Typical Speedup:** 10-100x for analytical workloads

## Core Concepts

### 1. Columnar Layout

```
Row-oriented:                    Column-oriented:
[ row1: A,1,X ]                  Column A: [A,A,B,B,C,C]
[ row2: A,2,Y ]  →  Transform   Column B: [1,2,3,4,5,6]
[ row3: B,3,Z ]                  Column C: [X,Y,Z,W,U,V]
[ row4: B,4,W ]
[ row5: C,5,U ]
[ row6: C,6,V ]
```

**Benefits:**
- Cache-friendly: Read only needed columns
- Compression: Same type = better compression
- SIMD: Process columns as arrays

### 2. Vector Types

```cpp
// FlatVector: Simple contiguous array
template<typename T>
class FlatVector {
    T* data_;                    // Values
    uint8_t* null_bitmap_;       // Null flags
    int size_;                   // Number of rows
};

// DictionaryVector: Encoded values
class DictionaryVector {
    Vector* indices_;            // Int indices
    Vector* dictionary_;         // Unique values
};

// ConstantVector: All same value
class ConstantVector {
    Value value_;
    int size_;
};
```

### 3. Selection Vectors

**Problem:** Filter creates sparse data, copying is expensive.

**Solution:** Selection vector = indices of active rows.

```cpp
// Before filter: 1000 rows
// After filter (10% pass): 100 rows

// Option 1: Copy (expensive)
Vector filtered = copy_matching_rows(vector);

// Option 2: Selection vector (cheap)
SelectionVector sel = {2, 5, 8, 12, ...};  // 100 indices
// Access via: vector[sel[i]]
```

### 4. Batch/Chunk Processing

```cpp
class Chunk {
    vector<unique_ptr<Vector>> columns_;
    int row_count_;

public:
    // Process all rows in batch
    void filter(const SelectionVector& sel);
    void project(const vector<int>& column_indices);
};

// Typical batch size: 1024 or 4096 rows
// - Small enough for cache
// - Large enough for SIMD efficiency
```

## Operators

### Scan Operator

```cpp
class ScanOp : public Operator {
    Table* table_;
    int current_row_ = 0;
    static constexpr int BATCH_SIZE = 1024;

public:
    Status Next(Chunk* out) override {
        // Read next batch
        int remaining = table_->row_count() - current_row_;
        int to_read = min(BATCH_SIZE, remaining);

        if (to_read == 0) return Status::DONE;

        *out = table_->ReadRows(current_row_, to_read);
        current_row_ += to_read;
        return Status::OK;
    }
};
```

### Filter Operator

```cpp
class FilterOp : public Operator {
    unique_ptr<Operator> child_;
    Expression* predicate_;

public:
    Status Next(Chunk* out) override {
        Chunk input;
        RETURN_IF_ERROR(child_->Next(&input));

        // Evaluate predicate on batch
        SelectionVector sel;
        for (int i = 0; i < input.row_count(); i++) {
            if (predicate_->Evaluate(input, i)) {
                sel.add(i);
            }
        }

        // Apply selection without copying
        *out = input.Select(sel);
        return Status::OK;
    }
};
```

### Aggregation Operator

```cpp
class HashAggOp : public Operator {
    unique_ptr<Operator> child_;
    vector<Expression*> group_by_;
    vector<Aggregate*> aggregates_;
    HashTable* ht_;

public:
    Status Next(Chunk* out) override {
        // Phase 1: Build (consume all input)
        Chunk input;
        while (child_->Next(&input).ok()) {
            for (int i = 0; i < input.row_count(); i++) {
                auto key = ExtractKey(input, i);
                auto entry = ht_->FindOrInsert(key);
                UpdateAggregates(entry, input, i);
            }
        }

        // Phase 2: Output results
        *out = ht_->ScanResults();
        return Status::OK;
    }
};
```

## SIMD Optimization

### Example: Vectorized Sum

```cpp
// Scalar version
int64_t sum_scalar(const int32_t* data, int n) {
    int64_t sum = 0;
    for (int i = 0; i < n; i++) {
        sum += data[i];
    }
    return sum;
}

// SIMD version (AVX2)
int64_t sum_simd(const int32_t* data, int n) {
    __m256i sum_vec = _mm256_setzero_si256();

    // Process 8 ints at a time
    for (int i = 0; i < n; i += 8) {
        __m256i vec = _mm256_loadu_si256(
            reinterpret_cast<const __m256i*>(data + i)
        );
        sum_vec = _mm256_add_epi32(sum_vec, vec);
    }

    // Horizontal sum
    // ... extract from sum_vec ...

    return total_sum;
}
```

### Auto-Vectorization

```cpp
// Compiler can auto-vectorize simple loops
// Key: contiguous memory, no aliasing, simple control flow

// Good: Compiler can vectorize
void good_example(int* __restrict a,
                  int* __restrict b,
                  int n) {
    for (int i = 0; i < n; i++) {
        a[i] = b[i] * 2;
    }
}

// Bad: Compiler can't vectorize
void bad_example(int* a, int* b, int n) {
    for (int i = 0; i < n; i++) {
        if (a[i] > 0) {  // Branch
            a[i] = b[i] * 2;
        }
    }
}
```

## Real Systems

### MonetDB/X100

**Pioneer of vectorized execution**

- Columnar storage
- Vectorized operators
- Give-away compilation

### DuckDB

**Modern embedded OLAP**

- Pure columnar
- Aggressive compression
- Parallel CSV parsing

### ClickHouse

**Distributed OLAP**

- Vectorized execution
- MergeTree engine
- Materialized projections

### Velox (Meta)

**Unified execution engine**

- Used by Presto, Spark
- Pluggable architecture
- C++ implementation

## My Projects

### query-engine (C++)

**Status:** Phase 1 complete (scalar), Phase 2 (vectorized) in progress

**Key Files:**
- `include/vector/vector.h` - Vector types
- `include/exec/operator.h` - Operator interface
- `src/ops/aggregate_op.cpp` - Hash aggregation

**Benchmarks:**
- Low cardinality: ~100M rows/sec
- High cardinality: ~10M rows/sec

### py-toydb (Python)

**Status:** Row-oriented MVP, planning columnar version

**Learning:** Compare row vs column performance

## Common Pitfalls

| Pitfall | Solution |
|---------|----------|
| Too small batches | Use 1024-4096 rows |
| Virtual calls in loop | Template specialization |
| Branch misprediction | Branchless code, bit masks |
| Cache thrashing | Process column-at-a-time |
| Type dispatch overhead | Code generation (JIT) |

## Connections

### Related Topics
- [Columnar Storage](./columnar-storage.md)
- [Query Execution](./query-execution.md)
- [SIMD Programming](./simd-programming.md)
- [Cache Optimization](./cache-optimization.md)

### Projects
- [query-engine](../build/query-engine.md) - C++ implementation
- [py-toydb](../build/py-toydb.md) - Python comparison

### Readings
- [MonetDB/X100 Paper](../read/papers/monetdb-x100.md)
- [Everything You Always Wanted to Know...](../read/papers/compiled-vectorized.md)
- [DuckDB Internals](../read/code/duckdb/internals.md)

## Resources

### Papers
- MonetDB/X100: Hyper-Pipelining Query Execution
- Everything You Always Wanted to Know About Compiled and Vectorized Queries But Were Afraid to Ask
- Access Path Selection in Main-Memory Optimized Data Systems

### Code
- [DuckDB](https://github.com/duckdb/duckdb)
- [ClickHouse](https://github.com/ClickHouse/ClickHouse)
- [Velox](https://github.com/facebookincubator/velox)

## Review Log
- 2026-03-27: Created, connecting query-engine project learnings
