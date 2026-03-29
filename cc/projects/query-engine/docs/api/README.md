# vagg API Documentation

This directory contains API reference documentation for vagg components.

## Components

### Core Data Structures

| Component | Header | Description |
|-----------|--------|-------------|
| `Vector<T>` | `<vagg/vector/vector.h>` | Columnar data storage |
| `Chunk` | `<vagg/vector/vector.h>` | Row batch container |
| `HashTable` | `<vagg/ht/hash_table.h>` | Robin Hood hash table |
| `Status` | `<vagg/common/status.h>` | Error handling |
| `Slice` | `<vagg/common/slice.h>` | String reference |

### Query Operators

| Component | Header | Description |
|-----------|--------|-------------|
| `Operator` | `<vagg/exec/operator.h>` | Base operator class |
| `ScanOp` | `<vagg/ops/scan_op.h>` | Data source scanner |
| `AggregateOp` | `<vagg/ops/aggregate_op.h>` | Hash aggregation |
| `SinkOp` | `<vagg/ops/sink_op.h>` | Result collector |

### Utilities

| Component | Header | Description |
|-----------|--------|-------------|
| `Arena` | `<vagg/util/arena.h>` | Memory allocator |
| `ExecContext` | `<vagg/exec/context.h>` | Execution context |

## Quick Links

- [Project README](../README.md)
- [Architecture Documentation](../architecture/)
- [Coding Standards](../RULES.md)
