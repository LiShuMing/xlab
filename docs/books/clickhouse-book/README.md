# ClickHouse 内核深度研究 — 源码级实现原理

## 章节目录

### Part I: 总览 — 查询的一生

- [Chapter 1: 架构全景 — 从 Server 启动到查询响应全链路](chapter-01-architecture.md)
- [Chapter 2: 核心数据结构 — 列式内存模型](chapter-02-columnar-memory-model.md)

### Part II: SQL 编译管线

- [Chapter 3: Parser — 递归下降解析器与 AST 构建](chapter-03-parser.md)
- [Chapter 4: Analyzer v2 — QueryTree 与 Pass 管理器](chapter-04-analyzer-v2.md)
- [Chapter 5: Planner — 从 QueryTree 到 QueryPlan（含 Join Reorder CBO）](chapter-05-planner.md)

### Part III: MergeTree 存储引擎

- [Chapter 6: MergeTree 数据结构 — Parts / Marks / Granules / Skip Index](chapter-06-mergetree-data-structures.md)
- [Chapter 7: MergeTree 写入路径 — Insert → Parts → Merge/Mutation](chapter-07-mergetree-write-path.md)
- [Chapter 8: MergeTree 读取路径 — Mark Ranges → Read Pool → 向量化读取](chapter-08-mergetree-read-path.md)
- [Chapter 9: ReplicatedMergeTree — ZooKeeper/Keeper 协调下的分布式一致性](chapter-09-replicated-mergetree.md)

### Part IV: 向量化查询执行

- [Chapter 10: Processors 流水线模型](chapter-10-processors-pipeline.md)
- [Chapter 11: 向量化表达式求值 — ActionsDAG / JIT / SIMD](chapter-11-vectorized-execution.md)
- [Chapter 12: HashJoin 实现 — 并行 Hash / Grace Hash / Merge Join](chapter-12-hash-join.md)

### Part V: 现代 ClickHouse — 分布式与存算分离

- [Chapter 13: DistributedTable 与协调器节点模型](chapter-13-distributed-table.md)
- [Chapter 14: Parallel Replicas — 动态 Mark Range 分发的无状态计算层](chapter-14-parallel-replicas.md)
- [Chapter 15: DiskObjectStorage 架构 — 元数据策略与多后端支持](chapter-15-disk-object-storage.md)
- [Chapter 16: Lakehouse 集成 — Iceberg / DeltaLake / Paimon 原生支持全链路](chapter-16-lakehouse.md)
- [Chapter 17: 面向未来 — ClickHouse 在 AI/LLM Agent 时代的定位](chapter-17-future.md)

---

## 写作原则

- 每章从源码导航表开始，标注关键文件和行号
- 对比侧边栏：Spark / StarRocks / MaxCompute 的等价设计
- 第一性原理标注：为什么这样设计而非另一种方式
- 关键文件地图：每章结尾列出核心源码路径
