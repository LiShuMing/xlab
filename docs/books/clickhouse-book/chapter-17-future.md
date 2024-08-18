# Chapter 17: 面向未来 — ClickHouse 在 AI/LLM Agent 时代的定位

## 17.1 ClickHouse 的本质：极致的列式扫描引擎

回溯全书，ClickHouse 的核心竞争力始终是：

```
列式存储 + 向量化执行 + 稀疏索引 + MergeTree 合并
```

这个组合在 **大规模扫描聚合** 场景下几乎无敌——单节点 10 亿行/秒的扫描速度不是偶然，而是每一层架构决策的共同结果：
- `PaddedPODArray` 的 SIMD 对齐 → 硬件友好
- `IColumn::filter()` 的向量化过滤 → 减少 CPU 分支
- `MergeTree` 的稀疏索引 → 最小化 I/O
- `ActionsDAG` 的公共子表达式消除 → 减少重复计算
- JIT 编译 → 消除虚函数开销

## 17.2 AI 时代的三个交汇点

### 1. 向量搜索 — LLM 的检索增强

ClickHouse 已经支持向量搜索：

```sql
CREATE TABLE embeddings (
    id UInt64,
    vector Array(Float32),
    INDEX vec_idx vector TYPE vector_similarity('hnsw', 'cosine', 512)
) ENGINE = MergeTree ORDER BY id;

SELECT id, cosineDistance(vector, [0.1, 0.2, ...]) AS dist
FROM embeddings ORDER BY dist LIMIT 10;
```

**与专业向量数据库的对比**：

| 维度 | ClickHouse | Pinecone / Milvus |
|------|-----------|-------------------|
| 向量索引 | HNSW (实验) | HNSW / IVF / DiskANN |
| 过滤 + 向量 | 原生支持（WHERE + ORDER BY dist） | 有限支持 |
| 聚合 + 向量 | 原生支持 | 不支持 |
| 写入吞吐 | 极高 | 中等 |
| 纯向量性能 | 中等 | 高 |

**本质洞察**：ClickHouse 的优势不在纯向量搜索速度，而在 **结构化数据 + 向量搜索的联合查询**。例如："找到与我文档向量最相似的 10 篇文档，且这些文档的标签包含 'AI' 且发布时间在最近一年内"。这类查询对专业向量数据库来说非常困难（需要先向量搜索再过滤），对 ClickHouse 来说自然表达。

### 向量搜索的源码实现

```
向量索引 (HNSW):
  src/Storages/MergeTree/MergeTreeIndexVectorSimilarity.h
  → 在 Merge 时构建 HNSW 图
  → 图节点 = 每个 Granule 的向量
  → 边 = 近邻关系

距离函数:
  cosineDistance  → 余弦距离
  L2Distance      → 欧几里得距离
  dotProduct      → 点积 (PR #102254 新增)

SIMD 加速:
  SimSIMD 库 (PR #101571)
  → 利用 AVX2 / AVX-512 加速向量距离计算
  → 支持 float16 / float32 / float64

多 Part 搜索 (PR #101880):
  → 支持在多个 Data Part 上执行向量搜索
  → 每个Part独立搜索，结果合并
  → 生产场景的关键能力
```

### 2. LLM 推理的观测 — Trace Log / Metrics

LLM 推理系统（vLLM、TGI、TensorRT-LLM）产生大量可观测性数据：
- 请求延迟分布（P50/P95/P99）
- Token 生成吞吐
- KV Cache 命中率
- GPU 利用率

ClickHouse 是这些数据的天然归宿——高吞吐写入 + 低延迟聚合查询。OpenAI、LangChain、Mlflow 都使用 ClickHouse 存储推理指标。

**典型的 LLM 可观测性架构**：

```
LLM 推理引擎 → OTLP Exporter → ClickHouse
                                  │
                                  ├── 实时仪表盘 (Grafana)
                                  ├── 延迟 P99 告警
                                  ├── Token 吞吐趋势
                                  └── 异常检测

表设计:
  CREATE TABLE llm_metrics (
      timestamp DateTime64(3),
      request_id String,
      model String,
      prompt_tokens UInt32,
      completion_tokens UInt32,
      latency_ms Float32,
      ttft_ms Float32,          ← Time To First Token
      kv_cache_hit_rate Float32,
      gpu_utilization Float32
  ) ENGINE = MergeTree
  ORDER BY (model, timestamp)
  TTL timestamp + INTERVAL 30 DAY;
```

### 3. Agent 工作流的状态存储

LLM Agent 的工作流产生：
- 对话历史（时间序列）
- 工具调用记录（半结构化 JSON）
- 决策日志（嵌套结构）
- RAG 检索结果（向量 + 元数据）

ClickHouse 的 `Object` / `JSON` / `Dynamic` 类型天然支持半结构化数据：

```sql
CREATE TABLE agent_logs (
    timestamp DateTime,
    session_id String,
    agent_name String,
    event_type String,
    payload JSON,
    embedding Array(Float32)
) ENGINE = MergeTree ORDER BY (session_id, timestamp);
```

**JSON 类型的优势**：

```
ClickHouse 的 JSON 类型:
  - Schemaless 写入（字段可以动态变化）
  - 强类型读取（已知字段有确定类型）
  - 支持嵌套路径查询: payload.tools[0].name
  - 支持 JSON 索引（跳数索引 on JSON path）
  - 高效存储（列式编码，相同路径的值连续存储）

适用 Agent 场景:
  - 不同 Agent 产生不同结构的日志
  - 工具调用参数动态变化
  - 需要灵活查询各种字段
```

## 17.3 存算分离的 AI 适配

AI 时代的计算模式与传统 OLAP 有本质差异：

| 维度 | OLAP | AI/LLM |
|------|------|--------|
| 查询模式 | 批量扫描聚合 | 随机点查 + 向量搜索 |
| 延迟要求 | 秒级 | 毫秒级 |
| 数据量 | TB-PB | GB-TB |
| 计算密集度 | CPU 密集 | GPU 密集 |

ClickHouse Cloud 的存算分离架构正在适配这些需求：
- **Compute-Storage Separation** → 计算节点可独立扩缩容
- **ObjectStorage (S3)** → 数据持久化在对象存储
- **FileCache** → 热数据缓存到本地 NVMe
- **Parallel Replicas** → 多计算节点并行扫描

### SharedMergeTree — 未来的存储引擎

```
ReplicatedMergeTree (当前):
  → 数据在副本的本地磁盘
  → 元数据在 ZooKeeper/Keeper
  → 副本间通过 Log + DataPartsExchange 同步
  → 计算和存储绑定

SharedMergeTree (未来):
  → 数据完全在 S3
  → 元数据在共享存储（Keeper / S3）
  → 计算节点完全无状态
  → 任意计算节点可以读取任意 Part
  → 不需要 ReplicatedMergeTree 的复制协议

演进路径:
  ReplicatedMergeTree
    → ReplicatedMergeTree + S3 (当前 Cloud)
    → SharedMergeTree (未来)
```

SharedMergeTree 的核心变化：
1. **Part 所有者**：从"拥有 Part 的副本"变为"共享存储中的 Part"
2. **Merge 协调**：从 ZooKeeper Log 驱动变为 Leader 选举 + S3 原子操作
3. **读取方式**：从本地磁盘读取变为 FileCache + S3 读取
4. **写入方式**：从本地写入 + 同步变为 S3 直接写入

## 17.4 从 ClickHouse 内核中学到的设计原则

### 1. 硬件感知是数据库性能的根基

ClickHouse 从启动时就感知硬件：
- `getMemoryAmount()` → 内存大小影响缓冲区策略
- `CPU_ID_ENUMERATE` → SIMD 指令集决定代码路径
- `mlock_executable` → 禁止代码页换出
- `remapExecutable` → 减少 iTLB miss

**启示**：在 AI 时代，硬件感知需要扩展到 GPU/NPU —— 数据库查询引擎需要知道何时将计算卸载到加速器。

### 2. 向量化是通用加速范式

ClickHouse 的向量化不是"用了 SIMD 指令"那么简单，而是一整套设计范式：
- 数据组织为列（`IColumn`）
- 函数以列为输入输出（`IFunction::executeImpl`）
- 内存布局对齐到缓存行（`PaddedPODArray`）
- 控制流外提（`filter` 先算 mask，再批量 gather）

**启示**：在 LLM 推理中，同样的范式适用——批量 Token 处理（batching）、KV Cache 的连续内存布局、Paged Attention 的内存管理。ClickHouse 的设计思路可以直接迁移。

### 3. 声明式 + 命令式的分层是演进的关键

```
声明式（QueryPlan Step）→ 命令式（Processor）
逻辑优化（QueryTree Pass）→ 物理优化（QueryPlan Optimization）
```

这种分层让 ClickHouse 可以在不影响上层的情况下替换底层实现：
- MergeTree → ReplicatedMergeTree → SharedMergeTree（存储层演进）
- Hash Join → Grace Hash → Direct Join（执行层演进）
- ExpressionAnalyzer → Analyzer v2（优化层演进）

**启示**：AI 系统也需要类似的分层——Agent 的策略层（声明式）和执行层（命令式）分离，使得底层模型替换不影响上层工作流。

### 4. Merge 思想：延迟合并胜过即时更新

MergeTree 的核心思想是：**写入时只追加，合并延迟到后台**。这不是偷懒，而是一个深思熟虑的 trade-off：
- 写入路径极简（只创建新 Part）→ 高吞吐
- 合并路径异步（后台线程执行）→ 不阻塞查询
- 最终一致（合并后数据有序）→ 查询高效

**启示**：在 LLM Agent 中，类似的思想可以应用于知识库更新——新知识先追加（快速响应），知识整合延迟执行（后台重建索引）。

### 5. 分区裁剪是大数据的生存法则

ClickHouse 的多层裁剪（分区 → 主键索引 → Skip Index → PREWHERE → 运行时过滤）是查询性能的根基。每一层裁剪都减少了下一层需要处理的数据量。

**启示**：AI 系统的 RAG 检索也需要类似的分层裁剪——先粗粒度过滤（元数据匹配），再细粒度检索（向量搜索），而非对全量数据做向量搜索。

## 17.5 展望：ClickHouse 的下一个十年

基于源码分析的观察，ClickHouse 正在以下方向演进：

1. **SharedMergeTree** — 真正的存算分离存储引擎（当前在 ClickHouse Cloud 私有分支）
   - 无状态计算节点
   - S3 原生存储
   - 动态扩缩容

2. **Query Analyzer v2 全面迁移** — 替换旧的 ExpressionAnalyzer
   - 更好的 CBO 支持
   - 更灵活的优化 Pass
   - 更完善的 Join Reorder

3. **更完善的 CBO** — 直方图统计、更多 Join Reorder 算法、Cascades 优化器
   - 自动统计信息收集（PR #101275 已启用）
   - Runtime Filter（Anti Join / Variant 类型支持已修复）
   - Row Policy 感知优化

4. **Lakehouse 深度集成** — Iceberg 写入优化、Delta Lake 原生 C++ 实现
   - Iceberg: 更高效的 Compaction、Optimize 操作
   - Delta Lake: 考虑从 Rust FFI 迁移到 C++ 原生实现
   - Paimon: 写入支持

5. **AI 原生功能** — 向量搜索成熟、Embedding 函数内建、RAG 工作流支持
   - 向量搜索: 多 Part 搜索、更多距离函数、生产级 HNSW
   - Embedding 函数: 内建 ONNX 推理，在 SQL 中直接生成向量
   - MCP 集成: ClickHouse 作为 MCP Server，让 LLM Agent 直接查询

### MCP (Model Context Protocol) 集成

```
LLM Agent ←→ MCP Client ←→ ClickHouse MCP Server
                                        │
                                        ├── natural_language_to_sql()
                                        ├── execute_query()
                                        ├── list_tables()
                                        ├── describe_table()
                                        └── get_sample_data()

价值:
  - LLM Agent 无需编写 SQL，通过自然语言查询 ClickHouse
  - ClickHouse 成为 AI 工作流的数据基础设施
  - 实时数据分析嵌入 Agent 决策循环
```

---

## 全书总结

```
Part I  — 查询的一生:  Server 启动 → 数据结构 → 查询链路
Part II — SQL 编译:    Parser → Analyzer v2 → Planner (CBO Join Reorder)
Part III— 存储引擎:    MergeTree (Parts/Marks/Granules) → 写入 → 读取 → 复制
Part IV — 查询执行:    Processors Pipeline → 向量化/JIT → Hash Join
Part V  — 现代 ClickHouse: Distributed → Parallel Replicas → 存算分离 → Lakehouse → AI
```

ClickHouse 的内核哲学可以概括为：**在正确的抽象层次上做正确的事，然后让硬件做它最擅长的事。** 从 IColumn 的 COW 零拷贝，到 PaddedPODArray 的 SIMD 对齐，再到 MergeTree 的稀疏索引裁剪——每一个设计决策都在回答同一个问题：如何让数据从磁盘到 CPU 的路径最短、最宽、最直。

而在 AI 时代，这个问题演变为：如何让数据从存储到模型推理的路径最短、最宽、最直。ClickHouse 的存算分离架构、向量搜索能力、JSON 类型支持、以及 MCP 集成，都是对这个新问题的回答。答案的核心不变——仍然是列式存储、向量化执行、稀疏索引、延迟合并——但应用场景从 OLAP 报表扩展到了 AI 工作流的全链路。

**关键文件地图**：
```
src/Storages/MergeTree/MergeTreeIndexVectorSimilarity.h → 向量索引
src/DataTypes/DataTypeJSON.h                            → JSON 类型
src/Storages/ObjectStorage/DataLakes/                   → Lakehouse 支持
src/Disks/DiskObjectStorage/                            → 存算分离
src/Storages/MergeTree/ParallelReplicasReadingCoordinator.h → 并行副本
```
