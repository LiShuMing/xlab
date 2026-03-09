我是一名拥有 10 年以上经验的资深研发工程师，目前是顶尖开源 OLAP 数据库
（[StarRocks](https://github.com/StarRocks/starrocks)）的核心开发者与 Committer。
我的日常技术栈围绕 C++、高并发、分布式系统、向量化执行以及底层性能压榨。
同时，我也在积极拥抱 AI 时代，探索 LLM、RAG 和前沿编程语言（如 Rust、Haskell）。

请参考 Meta Velox 的官方文档（velox.dev）、官方博客（engineering.fb.com）、
GitHub 提交历史（facebookincubator/velox）、GitHub Issues/Discussions、
学术论文，以及 Ahana、IBM、Intel、字节跳动等贡献方的技术博客进行综合分析：

**分析维度要求如下：**

1. **Velox 定位与架构哲学**：
  - **"统一执行层"设计目标**：Velox 的核心定位——
     不是独立数据库，而是供 Presto、Spark（Gluten）、
     Arrow Flight 等上层系统复用的**向量化执行层库（Execution Library）**；
     "Write Once, Run Everywhere"（统一算子、统一内存管理、
     统一函数注册）的工程收益与落地现实；
  - **与 Meta 内部系统的关系**：Velox 在 Meta 内部如何同时支撑
     Presto（交互式查询）、Spark（批处理）、
     Realtime Streaming（流式处理）三种工作负载；
     从 Presto C++ Worker 演化为通用执行库的历史脉络；
  - **与 DataFusion / DuckDB 的定位对比**：Velox 是纯执行层
     （无 SQL Parser、无 Catalog、无 Optimizer），
     而 DuckDB 是完整数据库，DataFusion 是带优化器的查询引擎框架；
     三者的集成深度与替换关系；

2. **内存管理体系（Memory Management）**：
  - **MemoryPool 层次结构**：`MemoryManager` → `MemoryPool`（树形结构）
     的设计；Query-level / Operator-level 的内存配额隔离；
     `MemoryArena`（`HashStringAllocator`）在 Hash Aggregation / Join
     中的应用；
  - **Buffer 与 FlatVector 内存布局**：`FlatVector<T>` /
     `ArrayVector` / `MapVector` / `RowVector` 的内存表示；
     与 Apache Arrow 内存布局的对比与转换开销
     （Velox 内部格式 vs Arrow 格式，两者并非完全相同）；
  - **Spill-to-Disk 框架**：`Spiller` 接口的设计；
     Hash Join / Hash Aggregation / Order By 的 Spill 实现；
     Spill 文件格式与读写性能；
     与 DuckDB Spill 机制的工程对比；
  - **内存压力与 Arbitrator**：`MemoryArbitrator` 的
     Shrink / Spill / Abort 三级响应策略；
     在 Presto 多并发 Query 场景下的内存抢占机制；

3. **向量化执行引擎核心**：
  - **向量类型系统**：`VectorEncoding`（Flat / Constant / Dictionary /
     Bias / Sequence / LazyVector）的设计动机与适用场景；
     `LazyVector`（惰性加载向量，用于 Late Materialization）的实现；
     `DictionaryVector` 在字符串列上的性能收益分析；
  - **Expression Evaluation 框架**：`ExprSet` / `Expr` 的编译与执行；
     Common Subexpression Elimination（CSE）在表达式层的实现；
     `EvalCtx` 与 Selection Vector（`SelectivityVector`）的交互；
     Adaptive Expression Evaluation（运行时根据选择率调整执行策略）；
  - **算子实现细节**：
    - **Hash Join**：`HashTable`（开放寻址 vs 链式）的实现选择；
       Build Phase 的并行构建；Probe Phase 的 SIMD 优化；
       Anti Join / Semi Join 的实现；
    - **Hash Aggregation**：`HashAggregation` 的两阶段
       （Partial + Final）与 Single 模式；
       聚合函数的 `Accumulator` 接口；
       高基数聚合的内存压力与 Spill 路径；
    - **Order By / Top-N**：`OrderBy` 算子的外部排序实现；
       `TopN` 的堆排序优化；
    - **Window Functions**：`Window` 算子的 Partition 缓冲策略；
  - **SIMD 优化策略**：Velox 对 AVX2 / AVX-512 的利用方式
     （手写 intrinsics vs 编译器自动向量化 vs XSIMD 库）；
     与 StarRocks 向量化引擎 SIMD 策略的对比；

4. **函数注册与扩展体系**：
  - **函数注册框架**：`VELOX_DECLARE_VECTOR_FUNCTION` /
     `VELOX_DECLARE_AGGREGATE_FUNCTION` 的注册机制；
     Simple Function（标量简单函数，自动向量化）vs
     Vector Function（手动控制向量语义）的选择；
  - **Presto / Spark 函数语义对齐**：Velox 如何同时支持
     Presto 函数语义与 Spark 函数语义
     （两者在 NULL 处理、类型强转等方面存在差异）；
     `FunctionSignature` 的类型系统；
  - **Lambda 函数支持**：`transform` / `filter` / `reduce`
     等高阶函数的向量化实现；Lambda Capture 的内存管理；

5. **连接器（Connector）框架**：
  - **`Connector` 抽象接口**：`DataSource` / `DataSink` trait 设计；
     `ConnectorSplit`（数据分片）与 `SplitReader` 的抽象；
  - **HiveConnector（Parquet/ORC 读写）**：
     Parquet Reader 的向量化实现（Row Group → Column Chunk → Page 层次）；
     Late Materialization 在 HiveConnector 中的实现
     （先过滤 Filter 列，再加载其他列）；
     ORC Reader 的实现深度；
  - **Iceberg Connector**：基于 HiveConnector 扩展的 Iceberg 支持；
     Delete File（Position Delete / Equality Delete）的向量化读取实现；
  - **TPC-H / TPC-DS Connector**：用于基准测试的数据生成 Connector；

6. **Gluten：Velox 驱动的 Spark Native 加速**：
  - **Gluten 架构**：Spark JVM → JNI → Velox Native 的调用链路；
     `SubstraitToVeloxPlanConverter`（Substrait 计划 → Velox 物理计划）；
     算子 Offload 覆盖率（哪些 Spark 算子已 Native 化）；
  - **与 DataFusion-Comet 的竞争**：两者均以替换 Spark 执行层为目标，
     但技术栈不同（C++ Velox vs Rust DataFusion）；
     Meta / Intel / 字节跳动（Gluten 阵营）vs
     Apple / Databricks（Comet 阵营）的社区博弈；
  - **生产稳定性**：字节跳动在生产环境 Gluten 落地的规模与经验；
     已知的稳定性问题（Fallback 率、内存 OOM、结果一致性）；

7. **与 Presto C++ Worker（prestissimo）的关系**：
  - **Presto Native Worker 架构**：`prestissimo`（基于 Velox 的
     Presto C++ Worker）替换原 Java Worker 的进展；
     Task / Pipeline / Driver / Operator 的层次映射；
  - **序列化协议**：Presto Coordinator（Java）→ Native Worker（C++）
     的协议——`PrestoProtocol`（JSON）+ `PrestoSerializer`（二进制）；
  - **Meta 内部落地规模**：Presto Native Worker 在 Meta 生产环境的
     流量占比与性能收益（对比 Java Worker）；

8. **技术、社区与商业化视角**：
  - **技术视角**：Velox 作为"C++ 向量化执行标准库"的战略价值——
     与 StarRocks 执行引擎的技术选型对比：
     StarRocks 是否应该（或有必要）集成 Velox？
     代价（C++ ABI 兼容、Fork 维护）vs 收益（复用 Meta 优化）；
     Velox 的函数库完整度是否已达到可直接复用的水平；
  - **与 Apache Arrow Compute 的关系**：Velox 为何不直接使用
     Arrow compute kernels（而是自研）；两者在 SIMD 优化深度上的差异；
     Velox ↔ Arrow 的转换开销在实际系统中的占比；
  - **社区治理**：Meta 主导但已开放社区的治理模式；
     Velox Foundation（是否成立）的讨论；
     字节跳动、Intel、IBM 等公司的贡献比例与话语权；
  - **商业化**：Ahana（现已并入 IBM）基于 Velox/Presto 的商业产品；
     Velox 对 Startups 嵌入使用的 License（Apache 2.0）友好度；

**参考资料：**
- https://velox.dev/（官方文档）
- https://github.com/facebookincubator/velox/releases
- https://engineering.fb.com/（搜索 Velox / Presto）
- *Velox: Meta's Unified Execution Engine*（VLDB 2023）
  https://research.facebook.com/publications/velox-metas-unified-execution-engine/
- *Presto: SQL on Everything*（ICDE 2019）
- Gluten 项目：https://github.com/oap-project/gluten
- prestissimo（Presto C++ Worker）：https://github.com/prestodb/presto/tree/master/presto-native-execution

**输出格式：**
文章结构建议：
**Executive Summary
→ Velox 定位：统一执行层库的设计哲学
→ 内存管理体系（MemoryPool / Arbitrator / Spill）
→ 向量类型系统（FlatVector / LazyVector / DictionaryVector）
→ Expression Evaluation 框架
→ 核心算子实现（Hash Join / Hash Agg / Sort / Window）
→ SIMD 优化策略与性能水位
→ Connector 框架（HiveConnector / Iceberg / 自定义扩展）
→ Gluten：Velox 驱动的 Spark Native 加速
→ Presto C++ Native Worker（prestissimo）
→ 竞品横向对比（DataFusion / DuckDB 执行层 / StarRocks 向量化引擎）
→ 社区治理与商业化路径
→ 总结与展望（StarRocks 集成 Velox 的可行性分析）**


# Velox 深度技术分析：Meta 统一执行层的架构哲学与工程实践

> **写给有 10 年 C++ 系统开发经验的你**：本文不会停留在"向量化好、列存好"的入门叙述层面，而是直接切入设计决策的本质——为什么这样设计、代价是什么、与你熟悉的 StarRocks 执行引擎有何异同。

---

## Executive Summary

Velox 是 Meta 于 2022 年开源的**C++ 向量化执行库**，其核心价值不是"又一个数据库"，而是一个可被上层系统（Presto、Spark/Gluten、流式处理）复用的**执行层基础设施**。它解决的是一个真实存在于大型科技公司的工程痛点：同一家公司维护了多套查询引擎，每套都在重复实现 Hash Join、Hash Aggregation、Parquet Reader……而每套实现的质量参差不齐，优化成果无法跨系统复用。

Velox 的回答是：**下沉执行层，上层引擎只需实现 SQL Parser + Catalog + Optimizer，执行交给 Velox**。

这个判断在 Meta 内部已验证（Presto + Spark + Streaming 三套系统共用一个执行库），但在外部社区的落地远比预期复杂。本文将逐层剖析。

---

## 一、Velox 定位：统一执行层库的设计哲学

### 1.1 "Write Once, Run Everywhere"的工程现实

Velox 的分层设计非常清晰：

```
┌─────────────────────────────────────────────────────┐
│  Presto (SQL Parser + Coordinator + Optimizer)       │
│  Spark (Catalyst Optimizer + JVM Scheduler)          │
│  Streaming Engine (custom)                           │
└────────────────┬────────────────────────────────────┘
                 │  物理执行计划（PlanNode 树）
                 ▼
┌─────────────────────────────────────────────────────┐
│               Velox Execution Library                │
│  Task → Pipeline → Driver → Operator                 │
│  MemoryPool  │  VectorEncoding  │  FunctionRegistry  │
│  Connector   │  ExprEval        │  Spill Framework   │
└─────────────────────────────────────────────────────┘
                 │
                 ▼  数据源
┌─────────────────────────────────────────────────────┐
│  HiveConnector (Parquet/ORC) │ IcebergConnector      │
│  TpchConnector               │ Custom Connector      │
└─────────────────────────────────────────────────────┘
```

Velox **刻意不包含**：SQL Parser、Catalog、Query Optimizer、分布式调度器。这是设计选择，不是功能缺失。上层系统传入的是已经优化好的**物理执行计划**（`PlanNode` 树），Velox 负责将其本地执行。

**工程收益（已实现）**：
- 函数库只需实现一次，Presto 和 Spark 均可复用（含 Presto 语义和 Spark 语义两套注册）
- 内存管理、Spill、SIMD 优化集中维护，收益扩散到所有上层系统
- Meta 内部报告：Presto Native Worker（prestissimo）相比 Java Worker，CPU 效率提升约 **35-40%**

**落地现实（未解决的张力）**：
- Velox 的物理计划 IR 是私有的，上层系统需要将自己的计划转换为 Velox `PlanNode`。Spark 通过 **Substrait** 协议桥接（Gluten 项目），转换层本身引入了额外复杂度
- C++ ABI 稳定性问题：上层系统若是 JVM 语言，需要 JNI 桥，调试体验较差
- "Write Once"在函数语义层并不完全成立——Presto 和 Spark 的 NULL 处理、类型强转规则存在差异，Velox 内部维护了两套函数注册路径

### 1.2 Meta 内部三种工作负载的统一

| 工作负载 | 上层系统 | Velox 集成方式 |
|---------|---------|--------------|
| 交互式查询 | Presto（prestissimo） | 直接 C++ 集成，Native Worker |
| 批处理 | Spark（via Gluten） | JNI + Substrait 计划转换 |
| 实时流处理 | Meta 内部流引擎 | 直接 C++ 集成 |

历史脉络：Velox 起源于 **Presto C++ Worker** 的重构。最初 Meta 将 Presto Java Worker 改写为 C++，在此过程中意识到执行层可以解耦为通用库，于是剥离出 Velox，让 Presto C++ Worker（prestissimo）成为第一个"客户"。这解释了为什么 Velox 的 `Task/Pipeline/Driver` 模型与 Presto 的执行模型高度吻合。

### 1.3 与 DataFusion / DuckDB 的定位对比

这三者经常被混淆，但定位有本质区别：

```
DuckDB：       完整数据库（Parser + Optimizer + Executor + Storage）
               嵌入式，单节点，自包含，API 简单

DataFusion：   查询引擎框架（Parser + Optimizer + Executor）
               无内置存储，Rust 生态，有分布式扩展（Ballista）
               可单独使用，也可作为库集成

Velox：        纯执行层库（Executor only）
               无 Parser，无 Catalog，无 Optimizer
               必须由上层系统提供物理计划
               C++ 生态，设计目标是嵌入大型分布式系统
```

**关键差异**：DataFusion 可以独立作为查询引擎使用（你给它 SQL，它返回结果），Velox 不能——你必须给它一个已编译好的物理计划。这使得 Velox 的集成门槛更高，但对已有 Optimizer 的系统（Presto、Spark）来说，这正是他们需要的：不需要 Velox 的 Optimizer，因为他们已有更好的。

对于 **StarRocks**：StarRocks 已有完整的 Parser + Analyzer + Optimizer + 向量化执行引擎。Velox 的定位与之重叠的部分是"执行层"，集成 Velox 意味着替换 StarRocks 现有的执行引擎——这是一个极高风险的工程决策，后文详细分析。

---

## 二、内存管理体系

### 2.1 MemoryPool 层次结构

Velox 的内存管理采用树形 `MemoryPool` 结构：

```
MemoryManager (全局单例)
    └── Root MemoryPool
            ├── Query Pool (per query)
            │       ├── Operator Pool (HashJoin Build)
            │       ├── Operator Pool (HashAgg)
            │       └── Operator Pool (OrderBy)
            └── Query Pool (another query)
                    └── ...
```

**设计要点**：
- `MemoryManager` 持有全局内存上限，负责跨 Query 的仲裁
- 每个 Query 有独立的 `MemoryPool`，预算在 Query 创建时设定
- Operator 级别的 Pool 向 Query Pool 申请，超出时触发 Spill 或抛出 OOM
- `MemoryArena`（底层是 `HashStringAllocator`）专用于 Hash Aggregation 和 Hash Join 的变长数据（字符串 key），使用 slab 分配避免碎片

与 StarRocks 的对比：StarRocks 同样有 Query-level 内存配额（`mem_limit`），但内存仲裁机制相对简单——主要依赖全局内存监控线程，超限后 Cancel Query。Velox 的 `MemoryArbitrator` 提供了更细粒度的三级响应。

### 2.2 向量内存布局：与 Apache Arrow 的微妙差异

这是一个容易被忽视但对性能影响显著的细节。

**Arrow 内存布局（标准）**：
```
validity bitmap | data buffer | offsets buffer (可变长)
```

**Velox FlatVector<T> 布局**：
```
TypeKind | encoding type | nulls buffer | values buffer
```

两者设计目标相似，但并非完全兼容：
- Velox 的 `RowVector`（对应 Arrow `StructArray`）在列存和行存之间的转换路径不同
- Velox 的 `DictionaryVector` 内部保持一个 indices buffer + base vector，与 Arrow Dictionary 结构类似但实现独立
- **转换开销**：在 Velox ↔ Arrow 边界（例如 Arrow Flight 数据源），需要 zero-copy 或 shallow copy——目前 Velox 提供了 `toArrow()` / `fromArrow()` 路径，但对嵌套类型（Map、Array of Struct）仍有 copy 开销

为什么 Velox 不直接使用 Arrow 内存布局？核心原因是 **LazyVector** 和 **DictionaryVector** 的语义在 Velox 执行引擎中有特殊优化路径，直接绑定 Arrow 布局会限制这些优化的实现灵活性。

### 2.3 Spill-to-Disk 框架

Velox 的 Spill 框架相比许多系统更为完整，支持三类算子：

| 算子 | Spill 触发条件 | Spill 实现 |
|-----|-------------|-----------|
| Hash Join (Build) | Build 侧超出内存配额 | 将 Build 侧按 Hash 分区写入多个 Spill 文件，Probe 侧对应分区数据也 Spill |
| Hash Aggregation | 聚合状态超出配额 | 将当前聚合状态序列化并 Spill，后续 Merge |
| Order By | 排序缓冲超出配额 | 外部排序，多路归并 |

**Spill 文件格式**：Velox 使用自定义的列式格式（基于 `PrestoVectorSerde` 或 `CompactRowSerde`），而非 Parquet/ORC——这是合理的，避免引入压缩/解压开销，追求 Spill 读写吞吐最大化。

**与 DuckDB Spill 的对比**：
- DuckDB 的 Spill 机制（Buffer Manager）更偏向传统数据库的页面替换策略，以固定大小的 Page 为单位管理
- Velox 的 Spill 是算子感知的（operator-aware），每个算子知道自己的数据语义，可以做更智能的序列化
- DuckDB 在单节点场景下 Spill 的工程完整度更高（经过更长时间打磨），Velox 的 Spill 在生产环境仍有边界 case

### 2.4 MemoryArbitrator：三级响应策略

这是 Velox 内存管理中最有特色的部分，专门解决多并发 Query 争抢内存的问题：

```
内存压力触发
    │
    ▼
Level 1: Shrink（收缩）
    │  让持有富余内存的 Operator 主动释放缓冲
    │  （例如 HashJoin 的 Build 侧预分配）
    ▼ 若仍不足
Level 2: Spill（溢写）
    │  让内存占用最高的 Query/Operator 触发 Spill
    │  释放内存但保持 Query 继续运行
    ▼ 若仍不足
Level 3: Abort（中止）
    │  Kill 内存占用最高或优先级最低的 Query
    ▼
内存释放
```

这个机制的工程价值在于：**在多租户场景下，避免一个大 Query 直接 OOM Kill 掉整个进程，而是通过有序降级保证整体系统稳定性**。这对 Meta 的共享 Presto 集群场景至关重要。

---

## 三、向量类型系统

### 3.1 VectorEncoding 的设计动机

Velox 定义了多种向量编码，每种针对特定数据分布优化：

```cpp
enum class VectorEncoding : int8_t {
  FLAT,        // 标准密集列存
  CONSTANT,    // 所有值相同（SELECT 1, col FROM t 中的常量列）
  DICTIONARY,  // 字典编码（低基数字符串列）
  SEQUENCE,    // 等差数列（ROW_NUMBER() 等场景）
  BIAS,        // 偏移编码（整数列集中在某范围）
  LAZY,        // 惰性加载（Late Materialization 核心）
};
```

**DictionaryVector 的性能收益**：在字符串 JOIN key 场景，字典编码的收益巨大。假设一个基数为 1000 的字符串列，每个值平均 20 字节：
- FlatVector：20 bytes × N rows 的内存和比较开销
- DictionaryVector：4 bytes（int32 index）× N rows，比较变为整数比较

但要注意：DictionaryVector 在 Expression Evaluation 框架中会有**字典展开（dictionary peeling）**操作——当一个表达式无法直接操作字典编码时，需要先展开为 Flat，这在某些场景下会抵消收益。

### 3.2 LazyVector：Late Materialization 的核心载体

LazyVector 是 Velox 中最有工程深度的设计之一。

**问题背景**：在列式存储的 IO 路径中，一个经典优化是"先过滤，后投影"——对于 `SELECT a, b FROM t WHERE c > 100`，应该先读取 `c` 列做过滤，得到满足条件的 row indices，再只读取这些 rows 的 `a`、`b` 列，避免读取被过滤掉的数据。

**LazyVector 的实现**：
```
LazyVector<T>
    │
    ├── loader: std::unique_ptr<VectorLoader>  // 实际加载逻辑
    ├── rows: SelectivityVector                // 需要加载哪些行
    └── loaded: bool                           // 是否已加载
```

当 Expression Evaluation 框架需要访问 LazyVector 的值时，它会先检查当前的 `SelectivityVector`（已经过上游过滤算子收缩），只加载真正需要的行。这个机制将 IO 延迟到知道"需要哪些行"之后，是 HiveConnector 中 Parquet 列裁剪的核心实现基础。

**与 StarRocks 的对比**：StarRocks 的 Late Materialization 主要在 Storage Layer（Segment 读取时）通过 Zone Map + Short Circuit 实现，执行层的向量没有显式的 LazyVector 概念。Velox 的 LazyVector 将 Late Materialization 提升到了执行引擎层，理论上可以更精细地控制跨算子的加载时机。

### 3.3 SelectivityVector：过滤状态的高效传递

`SelectivityVector` 是一个位图，表示当前 batch 中哪些 row 是"活跃"的（未被过滤掉）。它在整个表达式评估树中向下传递，避免被过滤掉的行被无谓计算。

核心设计：使用 64-bit word 的位图，配合 `forEachSetBit` / `template<bool isSelected>` 编译时特化，在选择率高时走密集路径，选择率低时走稀疏路径。

---

## 四、Expression Evaluation 框架

### 4.1 ExprSet 编译与执行

Velox 的表达式执行不是直接解释执行，而是先"编译"为 `ExprSet`：

```
SQL 表达式（字符串）
    │ TypedExprNode（类型推导后）
    ▼
ExprSet（编译后的可执行表达式集合）
    ├── CSE 优化（公共子表达式消除）
    ├── 常量折叠
    └── 向量编码感知（DictionaryVector 特化路径）
```

`ExprSet::eval()` 的核心逻辑：
1. 接受输入 `RowVector` 和 `SelectivityVector`
2. 按拓扑序执行表达式树中的每个 `Expr`
3. 每个 `Expr` 产出一个 `VectorPtr`，传递给上层 `Expr`

### 4.2 CSE（公共子表达式消除）

假设表达式为 `f(a+b) > 0 AND g(a+b) < 100`，其中 `a+b` 出现两次。Velox 在 `ExprSet` 编译阶段识别出公共子表达式，只计算一次，将结果缓存在 `EvalCtx` 中供复用。

这在 Presto 的复杂分析查询（大量 CASE WHEN 嵌套）中有显著收益。

### 4.3 Adaptive Expression Evaluation

这是一个运行时优化：

```
第一次执行（探测阶段）
    │  统计每个子表达式的选择率
    ▼
调整执行顺序（剪枝效果好的子表达式优先执行）
    │  例如：AND 表达式中，先执行选择率最低的条件
    ▼
后续 batch 使用优化后顺序
```

这本质上是一个轻量级的运行时基数估计，类似 StarRocks 的 Predicate Reorder，但在执行层实时调整（而非依赖 Optimizer 的静态估计）。

---

## 五、核心算子实现

### 5.1 Hash Join

Velox 的 Hash Join 实现中有几个值得关注的工程细节：

**HashTable 实现选择**：Velox 使用 **开放寻址（Open Addressing）** 的 Hash Table（`RowContainer` + 线性探测），而非链式 Hash Table。原因：
- 开放寻址的内存局部性更好（探测路径连续）
- 对 SIMD 友好：可以同时探测多个 slot
- 代价：删除操作复杂（但 Hash Join Build 阶段无删除操作，只有查询）

**并行 Build Phase**：多个 Driver 线程并行读取 Build 侧数据，每个线程构建局部 Hash Table，最后合并。合并策略：不是简单 merge，而是按 Hash 值范围分区，每个 partition 由一个线程独立负责，避免锁竞争。

**Probe Phase SIMD 优化**：在 Probe 时，使用 SIMD 指令同时计算多行的 Hash 值，批量探测 Hash Table。对于 miss 的 rows（不在 Build 侧），通过 `SelectivityVector` 快速跳过后续处理。

**与 StarRocks HashJoin 对比**：StarRocks 使用类似策略（开放寻址 + 并行 Build），但在 Runtime Filter 的生成和传递上有自己的优化路径（尤其是 Bloom Filter 跨 BE 节点传播）。Velox 的 Runtime Filter 支持在 2023 年后逐步完善，但对分布式场景的原生支持仍弱于 StarRocks。

### 5.2 Hash Aggregation

**两阶段模式**（Partial + Final）与 **Single 模式**的选择逻辑：
- Partial（预聚合）：每个 Driver 本地预聚合，减少 Shuffle 数据量
- Final：对 Partial 结果做最终聚合
- Single：无法预聚合时（例如 `DISTINCT` 聚合）直接全量聚合

**Accumulator 接口**：每个聚合函数实现 `Accumulator` 接口，定义：
```cpp
struct Accumulator {
  void addInput(folly::Range<const DecodedVector*> args, ...);
  void combine(folly::Range<const char*> others, ...);  // 合并 partial 结果
  void extractValues(char* group, VectorPtr& result, ...);
};
```

这个接口设计使得自定义聚合函数的注册相对干净。

**高基数聚合的内存压力**：当 GROUP BY key 基数极高（例如 UUID），Hash Table 快速增长，触发 Spill。Velox 的策略是将当前 Hash Table 的内容 Spill 到磁盘（按 Hash 分区），然后清空内存，继续处理后续数据，最终做多路归并。

### 5.3 Order By / Top-N

**外部排序**：当数据量超出内存时，Velox 的 `OrderBy` 算子执行经典的**归并排序**：
1. 将内存中的数据排序后写入 Spill 文件（Run）
2. 对多个 Spill 文件做 K 路归并输出

**Top-N 优化**：对于 `ORDER BY col LIMIT N`，使用最大堆（或最小堆）维护当前最优的 N 个元素，避免对全量数据排序。当 N 较小时（例如 N < 1000），堆的内存占用很小，几乎不会触发 Spill。

### 5.4 Window Functions

Window 算子的核心挑战是：**Partition 内的所有行必须全部缓冲完才能计算窗口函数**（对于 UNBOUNDED PRECEDING 等 Frame）。

Velox 的策略：
- 按 Partition Key 将输入数据分组缓冲到 `RowContainer`
- 每个 Partition 计算完成后立即输出，释放内存
- 对于 Partition 过大的情况（超出内存），目前的 Spill 支持较为有限（相比 HashJoin/HashAgg 更为初级）

---

## 六、SIMD 优化策略

### 6.1 Velox 的 SIMD 策略

Velox 采用**混合策略**：

| 场景 | 策略 |
|-----|-----|
| 简单算术运算 | 依赖编译器自动向量化（GCC/Clang with -O3） |
| 字符串比较、Hash 计算 | 手写 AVX2/AVX-512 intrinsics |
| 批量 NULL 检查 | 位图操作（64-bit popcount，SIMD 展开） |
| 通用向量操作 | **xsimd 库**（可移植 SIMD 抽象层） |

**xsimd 的作用**：xsimd 是 xtensor 生态的 SIMD 抽象库，提供跨 AVX2/AVX-512/NEON 的统一接口。Velox 在部分非关键路径使用 xsimd 以保证跨平台可移植性，在关键热路径（Hash 计算、字符串操作）仍使用手写 intrinsics。

### 6.2 与 StarRocks SIMD 策略的对比

StarRocks 的 SIMD 策略更为激进且集中：
- 大量使用手写 AVX2 intrinsics，尤其是在 Filter、Aggregation、Hash Table 探测
- 有专门的 `SIMD` 工具类封装常用操作（如 `SIMD::count_nonzero`）
- 对 ARM NEON 的支持通过条件编译实现

**核心差异**：StarRocks 的 SIMD 优化更多集中在**数据扫描和过滤**层（与列存 Storage 紧密结合），而 Velox 的 SIMD 优化更集中在**执行算子**层（Hash、Sort、Expression Eval）。两者的优化重心与其架构定位一致。

**AVX-512 的态度**：Velox 对 AVX-512 的利用较为保守（AVX-512 在部分 Intel 平台上有降频问题），更多依赖 AVX2。StarRocks 在近期版本中对 AVX-512 的利用也相对有限。

---

## 七、Connector 框架

### 7.1 Connector 抽象设计

```cpp
class Connector {
 public:
  virtual std::unique_ptr<DataSource> createDataSource(
      const RowTypePtr& outputType,
      const std::shared_ptr<ConnectorTableHandle>& tableHandle,
      const std::unordered_map<std::string, std::shared_ptr<ColumnHandle>>& columnHandles,
      ConnectorQueryCtx* connectorQueryCtx) = 0;

  virtual std::unique_ptr<DataSink> createDataSink(
      RowTypePtr inputType,
      std::shared_ptr<ConnectorInsertTableHandle> connectorInsertTableHandle,
      ConnectorQueryCtx* connectorQueryCtx,
      CommitStrategy commitStrategy) = 0;
};
```

`DataSource` 接口的核心方法是 `getOrLoad()` — 返回 `RowVectorPtr`，内部实现 Late Materialization 逻辑。

### 7.2 HiveConnector：Parquet 向量化读取

HiveConnector 是 Velox 中最成熟的 Connector，支持 Parquet 和 ORC 的向量化读取。

**Parquet 读取层次**：
```
Row Group (128MB)
    └── Column Chunk（每列独立）
            └── Page（64KB）
                    └── 解码后写入 FlatVector / DictionaryVector
```

**Late Materialization 实现**：
1. 先读取 Filter 列（`remainingFilter` 中引用的列），构建 LazyVector
2. 执行过滤，得到 `SelectivityVector`（存活行的位图）
3. 对非 Filter 列，只加载存活行对应的值（通过 LazyVector 的 `load()` 接口）

**Page 级别的 Dictionary 保留**：Parquet 页面内的 Dictionary Encoding 可以直接映射为 Velox `DictionaryVector`，避免解码为 Flat——这是 string 列读取性能的关键优化路径。

### 7.3 Iceberg Connector

Iceberg Connector 基于 HiveConnector 扩展，主要额外处理 Iceberg 的 **Delete Files**：

- **Position Delete**：记录被删除行的 `file_path + pos`，读取时需要过滤这些 row
  - 实现：将 Delete File 读入内存（或 Bloom Filter），在 HiveConnector 的 `getOrLoad()` 中 apply delete mask
- **Equality Delete**：记录被删除行的特定列值
  - 实现：构建一个小的 Hash Table，在每个 batch 读取后做 Anti-Join 过滤

Velox 的 Iceberg Delete 读取已达到生产可用状态（Meta 内部 Iceberg 表走 Presto 查询路径），但 **Merge-on-Read** 场景的完整支持仍在持续优化中。

---

## 八、Gluten：Velox 驱动的 Spark Native 加速

### 8.1 Gluten 架构

Gluten 是将 Spark 执行层替换为 Native（Velox 或 Arrow DataFusion）的项目，Intel 主导，字节跳动深度参与：

```
Spark Driver (JVM)
    │  Catalyst 优化后的物理计划
    ▼
Gluten Plugin (JVM)
    │  将 Spark 物理计划转换为 Substrait Plan
    ▼  JNI 调用
Gluten Native Layer (C++)
    │  SubstraitToVeloxPlanConverter
    ▼
Velox Execution Engine
    │
    ▼  结果
Spark (JVM) 接收结果
```

**Substrait 作为中间 IR**：Substrait 是一个跨语言的关系代数序列化标准。Gluten 选择 Substrait 而非直接序列化 Spark 物理计划，目的是保持对 DataFusion 后端的兼容（DataFusion 也支持 Substrait 输入）。

### 8.2 算子 Offload 覆盖率

截至 2024-2025 年，Gluten（Velox 后端）已支持 Offload 的算子：

✅ **已覆盖**：Filter、Project、HashAggregate（Partial + Final）、HashJoin（Inner/Left/Right/Full）、Sort、Limit、Expand、Window（部分）、Parquet/ORC 读写

⚠️ **部分覆盖 / 有 Fallback**：某些复杂 Window Frame、BroadcastJoin 的某些变体、Python UDF

❌ **不支持（必须 Fallback 到 JVM）**：RDD-level 操作、某些特殊 Join 策略

**Fallback 的代价**：当某个算子无法 Offload 时，需要将 Native Velox 格式的数据序列化回 JVM 的 Spark Row Format，这个转换有显著开销。Fallback 率高是 Gluten 生产环境的主要痛点之一。

### 8.3 字节跳动的生产经验

字节跳动（ByteDance）是 Gluten 最大的生产用户，内部将其称为 "Gluten" 或 "Native Spark"：

- **规模**：据公开报道（Spark Summit 等），字节跳动在数万台机器的 Spark 集群上部署了 Gluten
- **收益**：端到端查询性能提升约 **20-50%**（取决于查询类型，IO 密集型收益较小，CPU 密集型收益显著）
- **稳定性挑战**：
  - 内存 OOM 问题（Velox 内存管理与 Spark executor 内存模型的对齐）
  - 结果一致性（Floating point 精度、NULL 语义的微妙差异）
  - 复杂 SQL 的高 Fallback 率

### 8.4 与 DataFusion-Comet 的竞争

| 维度 | Gluten (Velox 后端) | Apache Comet (DataFusion) |
|-----|-------------------|--------------------------|
| 执行引擎 | C++ Velox | Rust DataFusion |
| 主要贡献方 | Intel + 字节跳动 + Meta | Apple + Databricks |
| 成熟度 | 生产规模更大 | 相对较新（2023 年开源）|
| 集成方式 | JNI + Substrait | JNI + 自定义协议 |
| 优势 | Velox 的优化深度；Meta 的工程投入 | Rust 的安全性；DataFusion 社区活跃度 |
| 劣势 | C++ 复杂度；Substrait 转换层 | 功能覆盖率仍在追赶 |

从社区趋势看：Gluten 当前规模更大，但 Comet 正在快速成长，Databricks 的背书对 Spark 生态有重要影响。**两者并存的概率高于一方彻底胜出**——不同公司会根据自身技术栈选择。

---

## 九、Presto C++ Native Worker（prestissimo）

### 9.1 架构概览

prestissimo 是基于 Velox 实现的 Presto C++ Worker，替换原有的 Presto Java Worker：

```
Presto Coordinator (Java)
    │  HTTP + PrestoProtocol (JSON)
    ▼
prestissimo (C++ Worker)
    │
    ├── TaskManager（管理 Task 生命周期）
    ├── PrestoProtocol 解析（JSON → Velox PlanNode）
    │
    ├── Velox Task
    │       ├── Pipeline 1: TableScan → Filter → Project
    │       └── Pipeline 2: HashBuild / HashProbe
    │
    └── PrestoSerializer（结果序列化，二进制格式）
```

**协议层**：Coordinator 和 Worker 之间使用两套协议：
- **控制面**：HTTP + JSON（`PrestoProtocol`），用于 Task 创建、状态查询、Task 撤销
- **数据面**：二进制序列化（`PrestoSerializer`），用于 Shuffle 数据传输（Worker 间 Exchange）

`PrestoSerializer` 使用 Presto 的 Page 格式（列式，带压缩），与 Velox 内部的 `RowVector` 之间有轻量转换。

### 9.2 Meta 内部落地规模

Meta 公开披露（VLDB 2023 论文及后续博客）：
- Presto Native Worker 已承担 Meta 内部**大部分** Presto 查询流量
- CPU 效率相比 Java Worker 提升约 **35-40%**（节省机器成本）
- 尾延迟（P99 latency）有所改善（JVM GC 暂停消除）
- 迁移过程历时约 **2-3 年**，遇到大量兼容性问题（函数语义、数据类型边界 case）

---

## 十、竞品横向对比

### 10.1 执行层技术对比矩阵

| 维度 | Velox | DuckDB 执行层 | DataFusion 执行层 | StarRocks 执行层 |
|-----|-------|-------------|-----------------|----------------|
| **语言** | C++ | C++ | Rust | C++ |
| **向量类型系统** | 多编码（Flat/Dict/Lazy/...） | 扁平列存 | Arrow 原生 | 扁平列存 |
| **内存管理** | MemoryPool 树 + Arbitrator | Buffer Manager（页面替换） | Arrow MemoryPool | QueryContext + MemTracker |
| **Spill** | 算子感知，三类算子完整支持 | Buffer Manager 统一管理 | 部分支持（仍在完善） | HashJoin/Sort 支持 |
| **SIMD** | 混合（手写 + xsimd） | 手写 AVX2 | 编译器自动 + 手写 | 手写 AVX2 为主 |
| **函数扩展** | 强类型注册框架 | 扩展接口 | Rust trait | 较重的函数注册框架 |
| **Late Materialization** | LazyVector（执行层） | Storage 层 | 部分支持 | Storage 层 |
| **分布式感知** | 无（纯本地执行） | 无 | 有（Ballista） | 原生分布式 |

### 10.2 StarRocks 是否应集成 Velox？

这是一个值得认真分析的战略问题：

**集成的潜在收益**：
- 复用 Velox 的函数库（Presto/Spark 兼容函数，节省实现成本）
- 复用 Velox 的 Spill 框架（StarRocks 当前 Spill 支持相对有限）
- 复用 HiveConnector 的 Parquet/ORC 优化（如果 StarRocks 要做湖仓）

**集成的现实代价**：

1. **执行层替换风险极高**：StarRocks 有自己的向量化执行引擎，经过多年针对 OLAP 场景的专项优化（Zone Map、Late Materialization at Storage，Runtime Filter 分发等）。Velox 的执行层不理解 StarRocks 的 Storage 格式，替换意味着放弃这些针对性优化。

2. **C++ ABI 兼容地狱**：Velox 依赖 folly、fmt 等 Meta 内部重度使用的 C++ 库，这些库与 StarRocks 现有依赖树可能存在版本冲突。

3. **Fork 维护成本**：Velox 迭代速度较快（主要由 Meta 主导），Fork 后需要持续 merge upstream 改动，成本不低。

4. **分布式感知缺失**：Velox 是纯本地执行库，StarRocks 的核心竞争力在于**分布式执行优化**（Colocate Join、Bucket Shuffle、Adaptive Join 选择）。Velox 无法直接提供这些。

**务实结论**：

> **不建议 StarRocks 替换执行引擎为 Velox**，但有价值的是**选择性借鉴**：
> - 学习 Velox 的 LazyVector + DictionaryVector 设计，改进 StarRocks 的 Late Materialization 和字典优化
> - 学习 Velox 的 MemoryArbitrator 设计，完善 StarRocks 的多 Query 内存仲裁
> - 在 **湖仓查询**场景（StarRocks External Catalog），考虑复用 Velox 的 HiveConnector/IcebergConnector 读取路径（作为独立组件引入，而非替换执行引擎）

### 10.3 Velox 与 Apache Arrow Compute 的关系

为什么 Velox 不直接使用 Arrow Compute Kernels？

- **Arrow Compute 的设计目标**是"列操作的可移植标准库"，优化目标是通用性和跨语言互操作
- **Velox 的设计目标**是"OLAP 执行引擎的基础设施"，优化目标是特定工作负载的极致性能
- Arrow Compute 缺乏 Velox 需要的：`LazyVector` 语义、`SelectivityVector` 驱动的稀疏执行、`MemoryArbitrator` 级别的内存管理

两者不是竞争关系，而是**不同层次的抽象**。Velox 在需要与 Arrow 生态互操作时（Arrow Flight 数据源），提供转换路径，但内部保持独立格式以最大化执行性能。

---

## 十一、社区治理与商业化

### 11.1 社区治理模式

Velox 采用 **Meta 主导 + 开放社区**的模式（Apache 2.0 License），尚未像 Apache 项目那样迁移到中立基金会。这意味着：
- Meta 对技术方向有实质性的决策权
- Roadmap 优先考虑 Meta 内部需求（Presto、Spark on HDFS/Iceberg）
- 社区贡献者（Intel、字节跳动、IBM/Ahana）可以提 PR，但 Major 架构决策仍由 Meta 主导

**字节跳动**：Gluten 项目的最大外部贡献方，但贡献主要集中在 Gluten 层而非 Velox core
**Intel**：主要贡献在 Gluten 和 Velox 的 AVX-512 优化路径
**IBM/Ahana**：Ahana 已被 IBM 收购，基于 Presto/Velox 构建托管 Presto 服务，贡献主要在 HiveConnector 和云存储集成

**Velox Foundation 的讨论**：社区中有关于成立中立治理机构的讨论，但截至 2024-2025 年尚未有实质进展。

### 11.2 商业化路径

- **Ahana（IBM）**：提供托管 Presto 服务（IBM watsonx.data），Velox 是底层执行引擎
- **Startups**：Apache 2.0 License 对商业使用友好，但嵌入 Velox 的技术复杂度较高（强依赖 folly 等）
- **云厂商**：AWS、Azure 均在探索基于 Presto Native Worker / Velox 的 Serverless 查询服务

---

## 十二、总结与展望

### Velox 的战略价值再评估

Velox 的核心价值可以用一句话概括：**它是 Meta 解决"重复造轮子"问题的工程答案，在 Meta 内部已被证明有效，在外部世界的推广则需要更高的集成成本**。

**Velox 真正成功的场景**：
1. 你已有分布式调度 + SQL 优化器，需要一个高质量的本地执行层
2. 你的技术栈是 C++（或可以承受 JNI 开销）
3. 你的工作负载以 Presto/Spark 兼容函数为主
4. 你有足够的工程资源 handle Velox 的复杂度

**Velox 不适合的场景**：
1. 你需要端到端的嵌入式数据库（用 DuckDB）
2. 你的技术栈是 Rust（用 DataFusion）
3. 你需要原生分布式感知的执行层（自研或 StarRocks 等专用 OLAP 引擎）

### 对未来的判断

1. **Gluten 会持续成长**，字节跳动和 Intel 的投入保证了其生产可用性，Spark 生态中 Native 加速的需求是真实的
2. **prestissimo 将成为 Presto 的默认 Worker**，Java Worker 逐步退场（Meta 内部已如此，开源社区在跟进）
3. **Velox 的函数库完整度将成为关键壁垒**——函数语义 bug 修复、Presto/Spark 语义对齐是 Meta 长期工程投入的体现，短期内难以被复制
4. **Velox vs DataFusion 的竞争本质是 C++ 生态 vs Rust 生态的路线博弈**，未来 5 年两者将并存，分别服务于不同的用户群体

对于 StarRocks 团队而言，Velox 最值得学习的不是"是否集成"，而是其**工程设计思想**：LazyVector 的延迟物化语义、MemoryArbitrator 的多级内存响应、以及将执行层彻底解耦为可复用库的架构哲学——这些设计思想的价值超越了 Velox 本身。

---

*本文基于 Velox VLDB 2023 论文、velox.dev 官方文档、GitHub facebookincubator/velox 源码分析、Meta Engineering Blog、Gluten 项目文档，以及字节跳动/Intel 公开技术分享综合撰写。*