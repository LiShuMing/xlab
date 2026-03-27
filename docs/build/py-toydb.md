# py-toydb Project

## Overview

A toy database implementation in Python for learning query engine fundamentals.

**Goal:** Understand database internals by building one from scratch.

## Goals

1. **SQL Parser** - 解析简单SQL语句
2. **Query Planner** - 生成执行计划
3. **Execution Engine** - 向量化执行
4. **Storage Layer** - 简单的列式存储

## Knowledge Dependencies

### Database Theory
- [Query Processing](../learn/query-processing.md)
- [Query Optimization](../learn/query-optimization.md)
- [Columnar Storage](../learn/columnar-storage.md)
- [Vectorized Execution](../learn/vectorized-execution.md)

### Python Implementation
- [Pydantic Data Models](../learn/pydantic-models.md)
- [Type Hints](../learn/python-type-hints.md)
- [AST Parsing](../learn/python-ast.md)

### Reference Code
- [DuckDB Code](../read/code/duckdb/)
- [DataFusion Code](../read/code/datafusion/)
- [Query Engine C++](../../cc/projects/query-engine/)

## Key Decisions

| Decision | Context | Trade-offs |
|----------|---------|------------|
| Python implementation | 快速迭代，易于理解 | 性能不如C++，但适合学习 |
| Pydantic for types | 数据验证，序列化 | 运行时开销，但开发效率高 |
| Simple in-memory storage | MVP阶段 | 后续可添加持久化 |
| Row-oriented first | 简单易懂 | 后续实现columnar对比 |

## Architecture

```
SQL String
    │
    ▼
┌─────────────┐
│    Parser   │ ◀─── SQL → AST
│   (sqlparse)│
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Planner   │ ◀─── AST → Logical Plan
│             │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Optimizer  │ ◀─── Logical → Physical Plan
│   (rules)   │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Executor  │ ◀─── Execute Plan
│  (iterator) │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Storage   │ ◀─── Tables/Rows
│  (in-memory)│
└─────────────┘
```

## Learnings

### What Worked
- Pydantic模型清晰定义数据结构
- 迭代器模式适合执行引擎
- 从简单开始，逐步添加功能

### What Didn't
- 需要更好的错误处理
- 缺少性能基准测试
- 类型系统可以更严格

### Next Steps
- [ ] 实现WHERE子句
- [ ] 添加JOIN支持
- [ ] 实现简单优化器规则
- [ ] 对比row vs column存储

## Code

- **Location:** [../../python/projects/py-toydb/](../../python/projects/py-toydb/)
- **Main Module:** `toydb/`
- **Tests:** `tests/`

## Related Projects

- [query-engine](../../cc/projects/query-engine/) - C++向量化查询引擎
- [py-radar](./py-radar.md) - 数据收集（可作为数据源）

## Resources

- [Database Internals Book](https://www.databass.dev/)
- [How Query Engines Work](https://howqueryengineswork.com/)
- [DuckDB Architecture](https://duckdb.org/docs/internals/overview)

## Comparison with C++ Query Engine

| Aspect | py-toydb | query-engine (C++) |
|--------|----------|-------------------|
| Language | Python | C++20 |
| Focus | 理解概念 | 性能优化 |
| Storage | Row-oriented | Columnar |
| Execution | Iterator | Vectorized |
| Target | 学习 | 性能实验 |
