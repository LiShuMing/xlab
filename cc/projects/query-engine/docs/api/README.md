# vagg API Documentation

This directory contains API reference documentation for vagg components.

## Components

### Core Data Structures

| Component | Header | Description |
|-----------|--------|-------------|
| `FlatVector<T>` | `<vagg/vector/vector.h>` | Columnar data storage |
| `Chunk` | `<vagg/vector/vector.h>` | Row batch container |
| `HashTable` | `<vagg/ht/hash_table.h>` | Open-addressing linear-probing hash table |
| `Status` | `<vagg/common/status.h>` | Error handling |
| `Slice` | `<vagg/common/slice.h>` | String reference |

### Query Operators

| Component | Header | Description |
|-----------|--------|-------------|
| `Operator` | `<vagg/exec/operator.h>` | Base operator class |
| `ScanOp` | `<vagg/ops/scan_op.h>` | Data source scanner |
| `HashAggregateOp` | `<vagg/ops/aggregate_op.h>` | Hash aggregation |
| `SimpleHashAggregateOp` | `<vagg/ops/aggregate_op.h>` | `std::unordered_map` comparison aggregation |
| `HashJoinOp` | `<vagg/ops/hash_join_op.h>` | Prototype single-key inner hash join |
| `NestedLoopJoinOp` | `<vagg/ops/hash_join_op.h>` | Reference nested-loop join |
| `SortOp` | `<vagg/ops/sort_op.h>` | Prototype in-memory sort |
| `TopNOp` | `<vagg/ops/sort_op.h>` | Prototype Top-N |
| `SinkOp` | `<vagg/ops/sink_op.h>` | Result collector |
| `ResultCollectorOp` | `<vagg/ops/sink_op.h>` | In-memory sink for tests |

### Data Sources

| Component | Header | Description |
|-----------|--------|-------------|
| `DataSource` | `<vagg/ops/scan_op.h>` | Key-value chunk source interface |
| `MemoryDataSource` | `<vagg/ops/scan_op.h>` | In-memory source for tests/examples |
| `GeneratedDataSource` | `<vagg/ops/scan_op.h>` | Synthetic benchmark source |

### Utilities

| Component | Header | Description |
|-----------|--------|-------------|
| `ExecContext` | `<vagg/exec/operator.h>` | Execution context |

## API Caveats

- Most operators currently expect `KeyValueChunk` output buffers.
- `HashJoinOp` preserves only one aggregated build value per key; it is not yet
  a complete relational join.
- `SortOp` and `TopNOp` are in-memory prototypes and do not implement external
  sorting or full null-order semantics.

## Quick Links

- [Project README](../../README.md)
- [Project Design](../../DESIGN.md)
- [Architecture Documentation](../architecture/)
- [Coding Standards](../../RULES.md)
