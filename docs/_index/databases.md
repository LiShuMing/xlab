# Database Systems Index

## Open Source Projects (Reading)

| Project | Status | Key Learnings | Last Updated |
|---------|--------|---------------|--------------|
| [ClickHouse](../read/code/clickhouse/) | 🟡 In Progress | 向量化执行、MergeTree | - |
| [DuckDB](../read/code/duckdb/) | 🟡 In Progress | 嵌入式OLAP、优化器 | - |
| [StarRocks](../read/code/starrocks/) | 🔴 Not Started | 物化视图、查询优化 | - |
| [DataFusion](../read/code/datafusion/) | 🔴 Not Started | Rust实现、Arrow生态 | - |
| [Flink](../read/code/flink/) | 🔴 Not Started | 流处理、Checkpoint | - |

## Key Concepts

### Query Execution
- [Vectorized Execution](../learn/vectorized-execution.md)
- [Code Generation](../learn/code-generation.md)
- [Parallel Execution](../learn/parallel-execution.md)

### Storage
- [Columnar Storage](../learn/columnar-storage.md)
- [LSM Tree](../learn/lsm-tree.md)
- [Buffer Management](../learn/buffer-management.md)

### Optimization
- [Cost-Based Optimization](../learn/cbo.md)
- [Join Algorithms](../learn/join-algorithms.md)
- [Statistics & Cardinality](../learn/statistics.md)

## My Implementations

- [query-engine](../build/query-engine.md) - C++向量化查询引擎
- [py-toydb](../build/py-toydb.md) - Python玩具数据库
