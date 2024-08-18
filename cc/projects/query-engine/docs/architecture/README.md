# vagg Architecture Documentation

This directory contains architecture documentation for vagg.

## Contents

- [`../../DESIGN.md`](../../DESIGN.md) - Current project design and staged roadmap
- `overview.md` - High-level architecture overview
- `vectorized-execution.md` - Columnar execution model
- `hashtable.md` - Hash table design
- `operators.md` - Query operator framework

## Architecture Overview

vagg is a vectorized query execution engine for analytical workloads.

### Design Principles

1. **Vectorized Execution**: Process batches, not rows
2. **Columnar Layout**: Cache-friendly data access
3. **Pull-Based Pipeline**: Simple operator composition
4. **Performance First**: Measured optimizations

### System Architecture

```
┌─────────────────────────────────────────┐
│           Query Pipeline                │
│                                         │
│   Scan → Filter → Project → Agg → Sink  │
│                                         │
└─────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│         Vectorized Engine               │
│                                         │
│   Chunk (N rows × M columns)            │
│   ├── FlatVector<T> column storage      │
│   ├── ValidityBitmap for nulls          │
│   └── SelectionVector for filtering     │
│                                         │
│   HashTable for aggregation             │
│   └── Linear probing baseline           │
│                                         │
└─────────────────────────────────────────┘
```

### Execution Flow

1. **Scan**: Read `KeyValueChunk` batches from a data source
2. **Process**: Operators transform or block on chunks
3. **Output**: Sink prints or collects results

## Current Implementation Status

Implemented:

- `ScanOp` over `MemoryDataSource` and `GeneratedDataSource`
- `HashAggregateOp` for `GROUP BY key SUM(value)`
- `HashJoinOp` prototype for single-key inner joins
- `SortOp` and `TopNOp` prototypes for in-memory ordering
- `SinkOp` and `ResultCollectorOp`

Planned next:

- `FilterOp`, `ProjectOp`, and `LimitOp`
- Correct duplicate-key join semantics
- Multi-key sort semantics
- Runtime-schema chunk model after the typed path is stable

## Quick Links

- [Project README](../../README.md)
- [Project Design](../../DESIGN.md)
- [API Documentation](../api/)
- [TODOs](../../TODOS.md)
