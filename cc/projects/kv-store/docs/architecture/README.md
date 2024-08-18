# TinyKV Architecture Documentation

This directory contains architecture documentation for TinyKV.

## Contents

- `overview.md` - High-level architecture overview
- `memtable.md` - MemTable and in-memory structures
- `lsm-tree.md` - LSM-tree design principles
- `phases.md` - Development phases and milestones

## Architecture Overview

TinyKV is a single-node LSM-tree key-value store designed for learning systems programming concepts.

### Design Principles

1. **Correctness First**: All optimizations must be validated with benchmarks
2. **Memory Efficiency**: Arena allocation, zero-copy where possible
3. **Durability**: WAL for crash recovery, checksums for integrity
4. **Performance**: Measured optimization with profiling

### System Architecture

```
┌─────────────────────────────────────────┐
│           Client API Layer              │
│  Put(key, value) | Get(key) | Delete   │
└─────────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────┐
│            Write Batch                  │
│         (Atomic operations)             │
└─────────────────────────────────────────┘
                   │
        ┌──────────┴──────────┐
        │                     │
┌───────▼────────┐   ┌────────▼────────┐
│   MemTable     │   │      WAL        │
│  (SkipList)    │   │  (Durability)   │
└───────┬────────┘   └─────────────────┘
        │
        │ Flush
        ▼
┌─────────────────────────────────────────┐
│           SSTable Files                 │
│  Level 0 │ Level 1 │ Level 2 │ ...     │
└─────────────────────────────────────────┘
```

### Phase-Based Development

The project follows a strict phase-based approach:

| Phase | Component | Status |
|-------|-----------|--------|
| 1 | MemTable + Arena + SkipList | ✅ Complete |
| 2 | WAL + Recovery | 🚧 Planned |
| 3 | SSTable Format | 🚧 Planned |
| 4 | VersionSet + Manifest | 🚧 Planned |
| 5 | Compaction | 🚧 Planned |

## Quick Links

- [Project README](../README.md)
- [API Documentation](../api/)
- [TODOs](../TODOS.md)
