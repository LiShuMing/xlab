# vagg Architecture Documentation

This directory contains architecture documentation for vagg.

## Contents

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
│   ├── Vector<T> column storage          │
│   ├── ValidityBitmap for nulls          │
│   └── SelectionVector for filtering     │
│                                         │
│   HashTable for aggregation             │
│   └── Robin Hood with control bytes     │
│                                         │
└─────────────────────────────────────────┘
```

### Execution Flow

1. **Scan**: Read chunk from data source
2. **Process**: Operators transform chunk
3. **Output**: Sink collects results

## Quick Links

- [Project README](../README.md)
- [API Documentation](../api/)
- [TODOs](../TODOS.md)
