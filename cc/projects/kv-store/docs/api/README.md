# TinyKV API Documentation

This directory contains API reference documentation for TinyKV components.

## Components

### Data Structures

| Component | Header | Description |
|-----------|--------|-------------|
| Arena | `<tinykv/memtable/arena.hpp>` | Bulk memory allocator |
| SkipList | `<tinykv/memtable/skiplist.hpp>` | Probabilistic ordered structure |
| MemTable | `<tinykv/memtable/memtable.hpp>` | In-memory write buffer |

### Common Utilities

| Component | Header | Description |
|-----------|--------|-------------|
| Slice | `<tinykv/common/slice.hpp>` | Non-owning string reference |
| Status | `<tinykv/common/status.hpp>` | Error handling |
| Comparator | `<tinykv/util/comparator.hpp>` | Key comparison |

## Planned Components

### Phase 2: WAL

- `WALWriter` - Write-ahead log writer
- `WALReader` - Write-ahead log reader
- `Record` - Log record format

### Phase 3: SSTable

- `TableBuilder` - SSTable builder
- `TableReader` - SSTable reader
- `BlockBuilder` - Data block builder
- `BlockReader` - Data block reader

### Phase 4: Version Management

- `VersionSet` - Multi-version management
- `VersionEdit` - Version changes
- `Manifest` - Persistent metadata

## Quick Links

- [Project README](../README.md)
- [Architecture Documentation](../architecture/)
- [Coding Standards](../RULES.md)
