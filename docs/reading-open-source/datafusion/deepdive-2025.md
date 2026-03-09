我是一名拥有 10 年以上经验的资深研发工程师，目前是顶尖开源 OLAP 数据库
（[StarRocks](https://github.com/StarRocks/starrocks)）的核心开发者与 Committer。
我的日常技术栈围绕 C++、高并发、分布式系统、向量化执行以及底层性能压榨。
同时，我也在积极拥抱 AI 时代，探索 LLM、RAG 和前沿编程语言（如 Rust、Haskell）。

请参考 Apache DataFusion 的官方文档、官方博客（arrow.apache.org/blog）、
GitHub 提交历史（apache/datafusion）、GitHub Issues/Discussions、
以及 InfluxData、Coralogix、Dask 等核心贡献方的技术博客进行综合分析：

**分析维度要求如下：**

1. **DataFusion 定位与架构哲学**：
  - **"可嵌入查询引擎"定位**：DataFusion 作为 Rust 生态中
     "可定制化 SQL/DataFrame 执行内核"的设计哲学——
     与 DuckDB（嵌入式但封闭内核）、Velox（C++ 执行层库）的定位对比；
     `ExecutionContext` / `SessionContext` 的扩展点设计；
  - **与 Apache Arrow 生态的深度绑定**：DataFusion 以 Arrow 列式内存
     格式为唯一内部数据表示的工程决策；与 Arrow Flight / ADBC 的集成；
     `RecordBatch` 作为算子间数据单元的优势与局限
     （固定 batch size vs 动态 morsel）；
  - **DataFusion 家族**：DataFusion（SQL 引擎核心）、
     DataFusion-Comet（Spark 原生执行替代，基于 DataFusion）、
     DataFusion-Ray（分布式扩展）、Ballista（分布式调度，现状）、
     Lance（向量数据库存储格式，早期基于 DataFusion）的生态关系图；

2. **执行引擎架构深度**：
  - **物理执行模型**：DataFusion 的 Push-based 执行模型
     （`ExecutionPlan` trait 的 `execute()` 返回 `SendableRecordBatchStream`）；
     与 DuckDB Push-based 模型的对比——两者均为 Push，但
     DataFusion 基于 Rust async/await + `futures::Stream`，
     天然支持异步 I/O；Morsel-driven vs Stream-driven 的调度差异；
  - **向量化算子实现**：基于 `arrow-rs` 的 SIMD 计算内核
     （`arrow::compute` crate）；DataFusion 算子如何调用
     Arrow compute kernels（`filter` / `take` / `sort_to_indices`）；
     与 Velox 的对比：DataFusion 依赖 Arrow 标准 kernels
     vs Velox 自研高度优化的向量化原语；
  - **内存管理**：`MemoryPool` trait 的实现（`UnboundedMemoryPool` /
     `FairSpillPool` / `GreedyMemoryPool`）；Hash Join / Sort 算子的
     Spill-to-Disk 实现；`DiskManager` 的临时文件管理；
  - **并行执行**：`RepartitionExec` 算子（Hash / RoundRobin / Random）
     的实现；Tokio 多线程运行时与 DataFusion 线程模型的关系；
     `target_partitions` 配置与实际并行度的关系；

3. **查询优化器（基于 Datafusion Optimizer）**：
  - **逻辑优化 Pass 体系**：`OptimizerRule` trait 的注册机制；
     内置规则列表（Predicate Pushdown、Projection Pushdown、
     Common Subexpression Elimination、Limit Pushdown 等）；
     自定义规则注入的扩展接口；
  - **物理优化 Pass**：`PhysicalOptimizerRule` 体系；
     Join 策略选择（Hash Join vs Sort Merge Join vs
     Nested Loop Join）的 Cost 估算；
     `EnforceDistribution` / `EnforceSorting` 规则的作用；
  - **统计信息框架**：`Statistics` 结构（`row_count` /
     `column_statistics`）；TableProvider 如何提供统计信息；
     CBO 的成熟度评估（目前 DataFusion 的 CBO 相对基础）；
  - **用户自定义扩展**：`UserDefinedFunction`（标量/聚合/窗口）；
     自定义 `TableProvider`（实现 External Data Source）；
     自定义 `OptimizerRule` 与 `ExecutionPlan` 的工程实践；

4. **SQL 功能完备性与 PostgreSQL 兼容**：
  - **SQL 方言**：DataFusion SQL 对 ANSI SQL / PostgreSQL 方言的覆盖度；
     `sqlparser-rs` 作为 SQL 解析器的能力边界；
     已知不支持的 SQL 特性（如 `LATERAL` 支持程度、
     `WITH RECURSIVE` 的现状）；
  - **窗口函数**：Window Function 的实现（`WindowAggExec` /
     `BoundedWindowAggExec`）；Bounded Window（支持流式处理）
     与 Unbounded Window（需全量物化）的区分；
  - **Substrait 集成**：DataFusion 对 Substrait（跨引擎查询计划交换格式）
     的支持现状；与 Velox、DuckDB 的 Substrait 互操作实践；

5. **生态集成与上游项目**：
  - **DataFusion-Comet（Spark 加速）**：用 DataFusion 替换 Spark 的
     JVM 执行层（类似 Databricks Photon 的开源替代）；
     算子覆盖率（哪些算子已 Native 化，哪些仍 Fallback 到 JVM）；
     与 Gluten（Velox-based Spark Native）的竞争关系；
  - **Delta Lake / Iceberg 集成**：`delta-rs`（Rust Delta Lake 实现）
     以 DataFusion 为查询引擎；`iceberg-rust` 的 DataFusion 集成进度；
  - **InfluxDB IOx**：InfluxData 以 DataFusion 为核心构建新一代
     时序数据库（IOx）的架构——DataFusion 的高度定制化扩展实践；
  - **GlareDB / Coralogix 等商业应用**：DataFusion
     作为嵌入式引擎的商业落地案例分析；

6. **Rust 语言特性对引擎设计的影响**：
  - **Async/Await 与流式执行**：`SendableRecordBatchStream`
     （`Pin<Box<dyn Stream<Item=Result<RecordBatch>>>>`）如何天然支持
     异步 Parquet / S3 读取，避免阻塞线程；
     与 C++ 同步执行模型（Velox / DuckDB）的工程对比；
  - **所有权与 Zero-Copy**：Arrow `Buffer` 的引用计数（`Arc<Buffer>`）
     实现算子间 Zero-Copy 数据传递；与 C++ 的 `shared_ptr` 对比；
  - **Trait 扩展体系**：`TableProvider` / `ExecutionPlan` /
     `OptimizerRule` 等 trait 的设计使 DataFusion 成为真正可扩展的
     "查询引擎框架"而非封闭系统；
  - **编译时代价**：DataFusion 项目的编译时间问题（大型 Rust 项目的通病）；
     对下游用户构建速度的影响；

7. **技术、社区与商业化视角**：
  - **技术视角**：DataFusion 作为"Rust 系查询引擎基础设施"的战略价值——
     为什么越来越多的新型数据库（InfluxDB IOx、GlareDB、Databend、
     CeresDB 等）选择 DataFusion 而非从零实现执行层；
     与 Velox（C++ 生态）的生态位差异；
  - **性能现状**：DataFusion 在 TPC-H / ClickBench 上的性能水位——
     与 DuckDB、Polars 的基准对比；当前主要性能瓶颈
     （如 Hash Join 性能、字符串处理开销）；
  - **社区治理**：DataFusion 从 InfluxData 捐赠给 Apache Arrow 项目
     的治理演变；与 arrow-rs / arrow-flight 的 PMC 重叠；
     商业公司（InfluxData / Coralogix）贡献比例分析；

**参考资料：**
- https://datafusion.apache.org/
- https://github.com/apache/datafusion/releases
- https://arrow.apache.org/blog/
- *DataFusion: A Fast, Embeddable, Modular Analytic Query Engine*
  （SIGMOD 2024 论文草稿，如可获取）
- InfluxDB IOx 技术博客：https://www.influxdata.com/blog/
- `delta-rs` 文档：https://delta-io.github.io/delta-rs/

**输出格式：**
文章结构建议：
**Executive Summary
→ DataFusion 定位：可嵌入查询引擎框架的设计哲学
→ 执行引擎架构（Push-based + async Stream + Arrow Kernels）
→ 内存管理与 Spill-to-Disk
→ 查询优化器（RBO 体系 + CBO 现状 + 自定义扩展）
→ SQL 功能完备性与 Substrait 集成
→ DataFusion 家族生态（Comet / Ballista / IOx / delta-rs）
→ Rust 语言特性对引擎设计的深层影响
→ 竞品横向对比（DuckDB / Velox / Polars）
→ 社区治理与商业落地案例
→ 总结与展望**

# Apache DataFusion 深度全景分析
## 可嵌入查询引擎框架的设计哲学与工程实践

> **面向读者**：具备分布式 OLAP 数据库研发背景的资深工程师（C++/Rust，熟悉向量化执行、优化器设计）

---

## Executive Summary

Apache DataFusion 是一个用 Rust 编写、以 Apache Arrow 为内存模型的**可嵌入、可扩展查询引擎框架**。它于 2024 年 4 月从 Apache Arrow 子项目升级为 Apache 顶级项目（TLP），标志着其从"InfluxData 内部基础设施"演变为整个 Rust 数据生态的公共基础设施。

DataFusion 的核心价值主张不是"又一个高性能单机 OLAP 数据库"——那是 DuckDB 的赛道——而是"**数据库构建套件**"：一套提供超过 10 个扩展点、开箱即用但又可深度定制的查询引擎内核。它的战略定位类比于 LLVM 之于编译器生态：当你要构建一个新的分析型数据库时，你不必从零实现 SQL 解析器、逻辑优化器、物理执行层、Parquet/CSV 读取器——DataFusion 全部提供，你只需覆写你关心的部分。

2024 年 11 月，DataFusion 在 ClickBench（Parquet 文件查询）上超越 DuckDB，成为**同类测试中最快的单节点引擎**，且这是 Rust 系引擎首次登顶，具有里程碑意义。

---

## 一、DataFusion 定位：可嵌入查询引擎框架的设计哲学

### 1.1 "Deconstructed Database"：为什么需要这个赛道

传统 OLAP 数据库是一个高度耦合的整体（Vertica、Spark、ClickHouse），其性能红利来自各层深度协同优化，代价是无法复用、无法定制。近年来，行业逐渐认识到"最佳子系统边界"是可以被明确划定的：文件格式（Parquet/Arrow）、内存布局、执行引擎、Catalog 管理、查询语言前端——这些可以解耦。

DataFusion 和 Apache Calcite（Java 生态）、Velox（C++ 生态）都是这一趋势的代表。SIGMOD 2024 的 DataFusion 论文将其定性为：**提供竞争性性能的同时，提供开放架构，允许通过超过 10 个主要扩展 API 进行定制**。

### 1.2 与 DuckDB、Velox 的定位对比

| 维度 | DataFusion | DuckDB | Velox |
|------|-----------|--------|-------|
| **语言** | Rust | C++ | C++ |
| **目标用户** | 数据库构建者（开发者） | 终端用户（分析师） | 数据库构建者（开发者） |
| **扩展性** | 高（10+ 扩展点，trait 体系） | 低（封闭内核，Plugin API 有限） | 中（需深入 C++ 代码库） |
| **内存格式** | Arrow（标准化，跨系统） | DuckDB 内部格式（高度优化） | Velox Vector（自研，SIMD 极优化）|
| **异步 I/O** | 原生（Tokio async/await） | 无（同步，线程池） | 无（同步） |
| **生态** | Apache/Rust 生态 | 独立生态，Python/R 友好 | Meta 主导，C++ 生态 |
| **典型用途** | InfluxDB 3.0、Comet、delta-rs | 嵌入式 OLAP 查询 | Presto/Velox、Spark Gluten |
| **开源许可** | Apache 2.0 | MIT（核心开放，格式非标） | Apache 2.0 |

**核心差异**：DuckDB 是一个**面向用户**的完整产品，内核封闭但用户体验极佳；Velox 是**面向构建者**的 C++ 执行层库，向量化原语极度优化但缺乏标准化内存格式；DataFusion 是**面向构建者**的完整引擎框架，提供从 SQL 解析到物理执行的全栈，且基于 Arrow 标准格式，天然跨系统互操作。

### 1.3 SessionContext：扩展点的入口

`SessionContext` 是 DataFusion 对外暴露的顶层会话对象（对应 Spark 的 `SparkSession`），汇聚了：
- **Catalog 注册**：`register_table()` / `register_catalog()`，支持插入自定义 `TableProvider`
- **UDF 注册**：`register_udf()` / `register_udaf()` / `register_udwf()`
- **优化规则定制**：通过 `SessionConfig` 注入自定义 `OptimizerRule` 和 `PhysicalOptimizerRule`
- **运行时配置**：内存池、磁盘管理器、目标并行度

这个设计让下游系统（如 InfluxDB IOx）可以将自己的 Schema 管理、partition pruning 逻辑、自定义函数无缝注入，而无需 fork DataFusion 源码。

### 1.4 DataFusion 家族生态图

```
Apache DataFusion（SQL 引擎核心，Rust）
├── DataFusion-Python（Python 绑定）
├── DataFusion-Comet（Spark Native 执行加速，Apple→ASF 捐赠，2024）
├── DataFusion-Ballista（分布式调度扩展，现状：活跃但成熟度不及 Comet）
└── 生态集成
    ├── delta-rs（Rust Delta Lake，以 DataFusion 为查询引擎）
    ├── iceberg-rust（Apache Iceberg Rust 实现，DataFusion 集成进行中）
    ├── InfluxDB IOx / InfluxDB 3.0（FDAP 栈：Flight+DataFusion+Arrow+Parquet）
    ├── GlareDB、Coralogix、GreptimeDB、Databend（商业落地）
    └── RisingWave（流批一体，DataFusion 作为批处理 OLAP 核）
```

---

## 二、执行引擎架构

### 2.1 执行模型：Pull-based 流式执行

DataFusion 官方文档将其称为"Streaming Query Engine"，实现上是**基于 Volcano/Iterator 模型的拉取式流式执行**。每个 `ExecutionPlan`（物理算子）实现 `execute()` 方法，返回一个 `SendableRecordBatchStream`：

```rust
// 物理算子接口的简化抽象
pub trait ExecutionPlan {
    fn execute(&self, partition: usize, context: Arc<TaskContext>)
        -> Result<SendableRecordBatchStream>;
}

// SendableRecordBatchStream 本质上是：
// Pin<Box<dyn Stream<Item = Result<RecordBatch>> + Send>>
```

**关键特性**：
- 消费者调用 `stream.next().await`，触发整个执行树的推进
- 每次 `poll_next` 返回一个 `RecordBatch`（默认 8192 行）
- Pipeline breaker（全排序、Hash 聚合）必须完整消费输入才能产出，非 Pipeline breaker（Filter、Projection）以单 batch 为粒度流式处理

**与 DuckDB Push-based 的对比**：DataFusion 文档明确指出，尽管学术上 Morsel-Driven 并行模型批评 Volcano 的拉取模式在 NUMA 架构下存在问题，但**DataFusion 在实践中取得了与 DuckDB（推模型）相当的可扩展性**。根本原因是 Tokio 的任务调度机制和 `RepartitionExec` 的 Exchange 操作共同提供了足够的并行性。DataFusion 的 "Push" 来自于 Tokio：每个分区的 Stream 在独立的异步任务中运行，任务间通过 channel 传递 `RecordBatch`，这让拓扑上是 Pull 的 API 在调度上具有 Push 的效果。

### 2.2 并行执行：Partition + Repartition

DataFusion 的并行单元是**分区（Partition）**。每个 `ExecutionPlan` 可以有多个输出分区，对应多个并发执行的 Stream。`target_partitions` 配置默认与 CPU 核数相同（如 32 核则默认 32 路并行）。

`RepartitionExec` 实现了 Exchange 算子，支持三种重分布策略：
- **Hash**：按指定列 Hash 分发，用于 Hash Join / Hash Aggregate 的数据对齐
- **RoundRobin**：轮询分发，用于均衡负载
- **Random**：随机分发

Tokio 多线程运行时承担调度，DataFusion 的异步 Stream 天然适配 Tokio 的任务模型。值得注意的是：由于 Tokio 是通用异步运行时而非专为数据库 CPU 密集型负载设计，DataFusion 社区持续在研究如何在 Tokio 框架内更好地利用 CPU 局部性——这是对比 DuckDB 专有线程调度器的一个已知差距。

### 2.3 向量化执行：依赖 arrow-rs 的 SIMD 内核

DataFusion 的向量化执行能力来自 `arrow-rs`（Rust Arrow 实现）的 `arrow::compute` 模块，而非自研。算子调用路径：

```
FilterExec → arrow::compute::filter(batch, boolean_array)
SortExec   → arrow::compute::sort_to_indices(array, options) + take()
HashJoinExec → arrow::compute::take() 应用 probe side 匹配索引
```

**与 Velox 的对比**：Velox 自研了高度优化的向量化原语，针对不同硬件（AVX-512 等）有专属实现路径；DataFusion 依赖 Arrow 社区维护的标准 compute kernels，SIMD 利用率取决于 arrow-rs 的优化深度。在字符串处理密集型查询上，DataFusion 曾落后，2024 年通过引入 `StringView`（German-style strings）大幅改善——这也是其拿下 ClickBench 第一的关键优化之一。

### 2.4 内存管理：MemoryPool trait 体系

DataFusion 通过 `MemoryPool` trait 实现内存使用的跟踪与限制：

**三种内置实现**：
- **`UnboundedMemoryPool`**：不限制内存使用，适合内存充裕的开发调试
- **`GreedyMemoryPool`**：设置全局上限，单个消费者独占到失败，适合单个大算子的场景
- **`FairSpillPool`**：在多个可 Spill 算子间公平分配内存，是生产环境推荐选项

**算子接入方式**：内存密集型算子（Hash Join、Sort、Hash Aggregate）在分配内存前必须向 `MemoryPool` 申请：

```rust
// 算子尝试申请内存，失败则触发 Spill
match reservation.try_grow(additional_bytes) {
    Ok(()) => { /* 继续分配 */ },
    Err(_) => { self.spill_to_disk()?; }
}
```

**注意**：`MemoryPool` 只追踪算子**主动申请**的中间状态内存（如 Hash 表、Sort buffer），不追踪 RecordBatch 在算子间流动时占用的内存。这是 DataFusion 内存模型的一个设计取舍，有时会导致实际内存使用超出 `FairSpillPool` 的限制（RisingWave 集成 DataFusion 时遭遇了 join-heavy 查询 OOM 问题，根源之一即在此）。

### 2.5 Spill-to-Disk

Sort 和 Hash Aggregate 算子实现了 Spill 支持。`DiskManager` 负责创建和管理引用计数的临时文件（`RefCountedTempFile`），确保文件在不再需要时自动清理。`FairSpillPool` 触发 Spill 的条件是总预留内存超过配置上限，Spill 后算子释放预留、将中间结果写入本地磁盘、继续处理后续数据，最终做外排归并。

值得关注的局限：**Hash Join 的 Spill 支持相对较晚才加入**，且在复杂多 join 场景下的稳健性仍是社区持续改进的方向。这对 StarRocks 等工程师而言是一个值得关注的对比点——StarRocks 的 Spill 框架在多算子协同上已相当成熟。

---

## 三、查询优化器

### 3.1 优化器整体架构

DataFusion 优化器分三个阶段：

```
SQL Text
  → [sqlparser-rs 解析] → AST
  → [SqlToRel] → 未分析的 LogicalPlan
  → [Analyzer（AnalyzerRule）] → 类型检查/类型推导后的 LogicalPlan
  → [Optimizer（OptimizerRule）] → 优化后的 LogicalPlan
  → [QueryPlanner] → PhysicalPlan（ExecutionPlan 树）
  → [PhysicalOptimizer（PhysicalOptimizerRule）] → 最终物理计划
```

### 3.2 逻辑优化：RBO 体系

DataFusion `datafusion-optimizer` crate 内置了约 30+ 条 `OptimizerRule`，典型的包括：

- **`PushDownFilter`**：谓词下推，将 Filter 尽量推到 Scan 层（对 Parquet 的 row group pruning 至关重要）
- **`PushDownProjection`**：投影下推，裁剪不需要的列
- **`CommonSubexprEliminate`**：公共子表达式消除
- **`PushDownLimit`**：Limit 下推
- **`SimplifyExpressions`**：表达式化简（`1 + 1 → 2`、`NOT NOT x → x`）
- **`EliminateCrossJoin`**：若 Cross Join 存在等值谓词，改写为 Inner Join
- **`ReplaceDistinctWithAggregate`**：`DISTINCT` 改写为 `GROUP BY`

规则按固定顺序应用，支持多轮迭代（默认最多 10 轮），直到计划不再改变或达到迭代上限。用户可通过 `SessionConfig::add_optimizer_rule()` 注入自定义规则。

**CBO 现状**：DataFusion 的 CBO 能力相对基础。优化器有 `Statistics` 结构（`row_count`、`column_statistics`，每个列统计量有 `Precision::Exact` / `Estimated` 标注），支持基于基数估计的 Join 策略选择和 Join 顺序启发式调整。但缺乏完整的代价模型（如 CPU/IO 代价公式）和全局 Join 枚举（Selinger 算法），更多依赖启发式规则。**对于多表 Join 的复杂查询，DataFusion 的优化质量与 StarRocks / DuckDB 有明显差距**——这是最常被提及的生产痛点之一。

### 3.3 物理优化：PhysicalOptimizerRule

物理优化阶段处理执行层面的决策，关键规则包括：

- **`EnforceDistribution`**：根据算子对输入数据分布的要求，插入必要的 `RepartitionExec`
- **`EnforceSorting`**：根据算子对输入排序的要求，插入必要的 `SortExec`，并尽量复用已有排序
- **`JoinSelection`**：基于统计信息选择 Hash Join / Sort Merge Join / Nested Loop Join，并决定 Build side（小表为 Build side）

**Join 算法选择**：DataFusion 支持 Hash Join、Sort Merge Join、Nested Loop Join（用于非等值 Join）、Symmetric Hash Join（用于流式无界数据）。`JoinSelection` rule 基于 `row_count` 统计决定是否广播小表（Broadcast Hash Join），以及 build/probe 侧的分配。

### 3.4 自定义扩展实践

DataFusion 的可扩展性是其最大卖点，四类扩展最常用：

**自定义 TableProvider**：实现外部数据源。需实现 `schema()`、`scan()` 等方法，`scan()` 返回 `ExecutionPlan`。InfluxDB IOx 通过此机制将时序数据的 partition 管理、cache 层对接到 DataFusion 的查询路径。

**自定义 UDF/UDAF/UDWF**：标量函数、聚合函数、窗口函数均可注册。InfluxDB IOx 通过此机制注入了时序领域函数（`time_window()`、`derivative()` 等）。

**自定义 OptimizerRule**：注入领域特定的优化逻辑。如时序数据库可注入"时间范围谓词→分区裁剪"规则。

**自定义 ExecutionPlan**：实现完全自定义的物理算子，可嵌入 GPU 算子、特殊格式读取器等。

---

## 四、SQL 功能完备性与 Substrait 集成

### 4.1 SQL 方言：基于 sqlparser-rs

DataFusion 使用 `sqlparser-rs` 作为 SQL 解析器，支持 ANSI SQL 和 PostgreSQL 方言的大部分特性，覆盖：CTEs、窗口函数、子查询、UNION/INTERSECT/EXCEPT、CASE WHEN、JSON 操作、日期时间函数等。

**已知局限与现状**：
- **`WITH RECURSIVE`（递归 CTE）**：长期讨论中，截至 2025 年初支持仍不完整
- **`LATERAL` join**：部分支持（`LATERAL` 子查询），完整语义支持仍在演进
- **存储过程 / DDL**：DataFusion 是查询引擎而非完整数据库，不原生支持 DDL
- **写操作（INSERT/UPDATE/DELETE）**：通过 `LogicalPlan::Dml` 支持基础写操作，但完整的事务语义需下游系统自行实现

### 4.2 窗口函数：Bounded vs Unbounded

DataFusion 的窗口函数实现分两类：

- **`WindowAggExec`**：全量物化方式，需将所有输入读完后计算，适合传统批处理场景
- **`BoundedWindowAggExec`**：增量流式计算，适合有界 Frame 定义（如 `ROWS BETWEEN 1 PRECEDING AND 1 FOLLOWING`）的场景

DataFusion 的排序感知（ordering-aware）优化会分析输入的已有排序属性，尽量避免不必要的 `SortExec`，最大化窗口函数的流式处理能力。

### 4.3 Substrait 集成

DataFusion 支持将 `LogicalPlan` 序列化/反序列化为 Substrait 格式（跨引擎查询计划交换协议），用于：
- 跨语言传递查询计划（如 Python 前端生成计划，Rust 后端执行）
- 跨引擎互操作（将 DataFusion 计划提交给 Velox 执行，反之亦然）

官方支持通过 `datafusion-substrait` crate 实现。互操作的实际完整性取决于算子覆盖率——Substrait 规范中的每个算子都需要双方独立实现，目前常见算子（Scan、Filter、Project、Join、Aggregate）均已覆盖，但边界算子和复杂表达式仍有缺口。

---

## 五、DataFusion 家族生态深度分析

### 5.1 DataFusion-Comet：Spark 的 Native 执行加速

**背景**：Comet 由 Apple 工程师开发（这些工程师同时也是 Arrow/DataFusion 的核心贡献者），于 2024 年 3 月捐赠给 ASF，目标是**无需任何代码修改，作为 Spark Plugin 加速 Spark 执行**。

**原理**：Comet 作为 Spark Plugin 截获 Spark 的 `QueryExecution`，将 Spark 物理计划（Java 对象）翻译为 DataFusion 物理计划，在 Rust 端执行后将结果回传 JVM。

**性能数据**：对 100 GB TPC-H 数据的 22 条查询，整体运行时间从 687 秒降至 302 秒，约 **2.2x 加速**。

**算子覆盖率**：目前 Scan（含 Parquet 解码）、Filter、Project、HashAggregate、HashJoin、Sort、Window 的主要路径已 Native 化。对于尚未覆盖的算子，Comet 回退（Fallback）到 JVM 执行，整体执行为混合模式。

**与 Gluten（Velox-based）的竞争**：Databricks Gluten 也是类似的 Spark Native 执行加速，基于 Velox 的 C++ 执行层。对比：Comet 是 Rust/Arrow 原生、Apache 治理；Gluten 是 C++/Velox 原生、有 Databricks/Meta 商业背景。两者目前的算子覆盖率和成熟度仍在快速演进。

### 5.2 InfluxDB IOx / InfluxDB 3.0：深度定制的标杆案例

InfluxData 是 DataFusion 最重要的商业推手。InfluxDB 3.0 完全基于"FDAP 栈"（Arrow **F**light + **D**ataFusion + **A**rrow + **P**arquet）构建，是 DataFusion 高度定制化的标杆实践：

- **自定义查询语言**：除 SQL 外，还支持 InfluxQL（时序领域 DSL），通过自定义 `LogicalPlan` 前端对接 DataFusion 执行层
- **时序分区**：自定义 `TableProvider` 实现基于时间范围的 partition pruning
- **实时数据路径**：内存中的热数据（WAL）与 Parquet 冷数据统一由 DataFusion 查询，通过自定义 `ExecutionPlan` 融合

**工程意义**：InfluxDB IOx 证明了 DataFusion 可以支撑 10 亿行/秒量级的生产时序查询负载，同时通过 ASF 社区模式持续回馈改进，避免了维护私有 fork 的工程债。

### 5.3 delta-rs 与 iceberg-rust

**delta-rs**：Rust 实现的 Delta Lake，以 DataFusion 为查询引擎。用户可以用 Python / Rust 直接在 Delta 表上执行 SQL，底层由 DataFusion 负责 Parquet 读取、谓词下推、执行。Arrow RecordBatch 作为唯一数据格式，delta-rs 与 DataFusion 之间无格式转换开销。

**iceberg-rust**：Apache Iceberg 的 Rust 实现，DataFusion 集成正在积极推进。Comet 0.12.0 已引入基于 `iceberg-rust` 的实验性 Native Iceberg Scan，将 Java 侧的 Catalog 管理（partition pruning 等）与 Rust 侧的 DataFusion 原生执行结合，代表了 Lakehouse 架构下 JVM→Rust 执行层迁移的前沿实践。

### 5.4 Ballista：分布式扩展的现状

Ballista 是 DataFusion 的分布式调度扩展，实现了类 Spark 的分布式执行框架。现状：功能上可以运行分布式查询，但成熟度和特性完备性远不及 Comet，社区活跃度也相对较低。对于需要分布式执行的场景，目前更常见的做法是在 DataFusion 之上自建分布式层（如 InfluxDB IOx 的做法），而非直接使用 Ballista。

---

## 六、Rust 语言特性对引擎设计的深层影响

### 6.1 Async/Await：天然的异步 I/O 适配器

`SendableRecordBatchStream`（`Pin<Box<dyn Stream<Item=Result<RecordBatch>> + Send>>`）让异步 Parquet/S3 读取与同步计算算子无缝融合：

```rust
// Parquet 远程读取时，.await 让出线程给其他任务
while let Some(batch) = parquet_stream.next().await {
    // batch 到达后，同步向量化计算
    let filtered = arrow::compute::filter(&batch, &mask)?;
    yield filtered;
}
```

与 C++ 的对比：DuckDB 和 Velox 的异步 I/O 需要通过回调、Future 库或专用的 I/O 线程池实现，代码复杂度高且与核心执行路径耦合度高。Rust 的 `async/await` 让两者自然融合，这也是 DataFusion 在云原生（S3 数据湖）场景下 I/O 效率的重要来源。

**查询取消**：由于整个执行树是 Stream 组成的 DAG，取消查询只需 drop 顶层 Stream，整个执行树通过 Rust 所有权机制自动回收资源，无需显式的取消信号传播——这是 C++ 同步执行模型需要额外实现的复杂功能。

### 6.2 所有权与 Zero-Copy：Arrow Buffer 的引用计数

Arrow `Buffer` 通过 `Arc<Vec<u8>>` 实现引用计数，算子间传递 `RecordBatch` 是零拷贝的：Filter 算子产出的 `RecordBatch` 与输入共享底层 Buffer（通过 `BooleanBuffer` mask + `take` 实现选择性列视图），没有数据复制。

与 C++ 的 `shared_ptr<Buffer>` 类比：语义相同，但 Rust 的所有权系统在**编译期**保证不会出现 use-after-free 和数据竞争，消除了 C++ 中此类 Bug 的可能性。

### 6.3 Trait 体系：真正的开放架构

DataFusion 的核心扩展点全部通过 Trait 定义：

```rust
pub trait TableProvider: Send + Sync {
    fn schema(&self) -> SchemaRef;
    fn scan(&self, ...) -> Result<Arc<dyn ExecutionPlan>>;
}

pub trait ExecutionPlan: Debug + Send + Sync {
    fn execute(&self, partition: usize, ...) -> Result<SendableRecordBatchStream>;
}

pub trait OptimizerRule: Send + Sync {
    fn try_optimize(&self, plan: &LogicalPlan, ...) -> Result<Option<LogicalPlan>>;
}
```

这种设计让 DataFusion 成为真正的**框架**而非封闭系统：用户实现的 `TableProvider` 与内置的 `ListingTable` 走完全相同的查询路径，没有"内部接口"与"外部接口"的割裂。

### 6.4 编译时代价

大型 Rust 项目的通病在 DataFusion 上同样存在。DataFusion 本体（含依赖）的全量编译时间在现代硬件上仍需 5-15 分钟，对下游用户构建速度有实质影响。社区通过 workspace 分 crate（`datafusion-common`、`datafusion-expr`、`datafusion-optimizer`、`datafusion-physical-plan` 等）和 `cargo` 增量编译缓解，但对于需要频繁迭代的下游项目仍是摩擦点。

---

## 七、竞品横向对比

### 7.1 DataFusion vs DuckDB

| 维度 | DataFusion | DuckDB |
|------|-----------|--------|
| **定位** | 引擎框架（面向构建者） | 完整产品（面向终端用户） |
| **ClickBench（Parquet）2024** | **第一**（超越 DuckDB） | 第二 |
| **TPC-H 综合** | 接近 DuckDB，略慢 | 领先 |
| **Join-heavy 查询** | 相对弱（CBO 不成熟，Spill 鲁棒性待提升） | 强（自研 Hash Join 优化深） |
| **字符串处理** | 2024 年后大幅改善（StringView） | 强 |
| **扩展性** | 极高（10+ Trait 扩展点） | 低（封闭内核） |
| **异步 I/O** | 原生支持 | 无 |
| **核心语言** | Rust | C++ |
| **生态集成** | Arrow 标准格式，跨系统零拷贝 | 私有格式，跨系统需转换 |

**结论**：用 DataFusion 构建的专用系统（如 InfluxDB IOx）**在特定工作负载上可以超越 DuckDB**，因为可以针对性优化；但 DuckDB 作为通用嵌入式 OLAP 的开箱即用体验和综合优化深度仍优于 DataFusion 默认配置。

### 7.2 DataFusion vs Velox

| 维度 | DataFusion | Velox |
|------|-----------|-------|
| **语言** | Rust | C++ |
| **内存格式** | Arrow（标准化） | Velox Vector（自研，高性能） |
| **SIMD 优化深度** | arrow-rs 提供，一般 | 自研原语，极深 |
| **异步 I/O** | 原生 async/await | 无 |
| **内存安全** | 编译时保证 | 运行时（需 ASAN 辅助） |
| **扩展机制** | Trait（Rust 类型安全） | 虚函数/继承（C++ 传统方式） |
| **跨系统互操作** | Arrow 标准格式 | 依赖 Arrow-Velox bridge |
| **生态** | Rust/Apache 生态 | Meta + C++ 生态（Presto、Gluten） |
| **成熟度（生产）** | InfluxDB IOx、Coralogix 等 | Meta Presto/Spark、大规模生产 |

**结论**：Velox 在纯 CPU 密集型 OLAP 场景的执行性能上仍有优势（自研向量化原语更深度优化），但 DataFusion 的 Arrow 标准化、Rust 内存安全、原生异步 I/O 在云原生场景下优势明显。生态位上，Velox 面向 C++ 工程师和 Meta 系架构，DataFusion 面向 Rust 工程师和 Apache 生态。

### 7.3 DataFusion vs Polars

Polars 是面向 DataFrame 操作的 Python/Rust 库，更接近 pandas 的替代品。DataFusion 是 SQL 引擎框架，两者定位差异显著。性能上：TPC-H 小数据集（10-100 GB 内存），Polars 与 DuckDB 接近；大数据集（超内存），DataFusion 的 Spill 机制比 Polars 流式引擎更成熟，约快 3x。DataFusion 从设计之初就面向分布式扩展（Ballista），而 Polars 起源于单机 DataFrame。

---

## 八、社区治理与商业落地

### 8.1 社区治理演变

DataFusion 的历史：
- **2019 年**：Andy Grove 个人项目，捐赠给 Apache Arrow 项目
- **2019-2023 年**：作为 Arrow 子项目发展，InfluxData 成为主要商业赞助商
- **2024 年 4 月**：升级为 Apache 顶级项目（TLP），独立 PMC 成立

升级为 TLP 的意义：DataFusion 拥有自己的 PMC（Project Management Committee），与 Arrow PMC 有大量人员重叠（Andrew Lamb 等），但治理独立，能更快地响应社区需求、发布节奏更自主。

### 8.2 商业公司贡献分析

DataFusion 的开源模式颇为健康，贡献来自多个商业实体：
- **InfluxData**：最大单一贡献者，Andrew Lamb（Staff Engineer）是核心维护者，驱动了大量性能优化和架构演进
- **Apple**：Comet 项目的原始作者，捐赠后持续贡献
- **Databend Labs**：中国 Rust 数据库公司，贡献了 StringView 等关键优化
- **Coralogix**：可观测性平台，以 DataFusion 为核心，活跃贡献 Filter/Aggregation 优化
- **个人贡献者**：来自 350+ 独立开发者的贡献（SIGMOD 2024 论文致谢）

这种多方商业公司贡献的模式使 DataFusion 避免了单点依赖风险，且各公司的不同应用场景（时序/可观测性/Spark 加速）共同驱动了功能的全面提升。

### 8.3 商业落地案例

- **InfluxDB 3.0**：生产级时序数据库，FDAP 栈核心
- **Coralogix**：全栈可观测平台，实时日志分析引擎
- **GreptimeDB**：时序+分析混合数据库
- **Databend**：云原生数仓，兼容 Snowflake API
- **RisingWave**：流批一体数据库，DataFusion 作为 Iceberg 批查询核
- **GlareDB**：嵌入式 SQL 分析引擎
- **Apple**（通过 Comet）：内部 Spark 加速基础设施

---

## 九、总结与展望

### 战略价值

DataFusion 已经成为 **Rust 生态中查询引擎基础设施的事实标准**。其价值类比于：
- LLVM 之于编译器：你不必从零实现代码生成，只需实现自己的前端和后端
- Linux 内核之于操作系统：共享维护成本最高的公共组件，在差异化特性上投入资源

对于任何考虑构建专用数据系统（时序数据库、可观测性平台、Lakehouse 查询层、向量数据库查询引擎）的团队，DataFusion 提供了一条"**从工作的基础到专用的卓越**"的路径，将数月的执行层研发压缩到数周。

### 当前主要局限

1. **CBO 成熟度**：多表 Join 的优化质量有待提升，缺乏完整的代价模型
2. **内存管理精确性**：`MemoryPool` 只追踪部分内存，OOM 在 join-heavy 大查询下仍有风险
3. **Tokio 与 NUMA/CPU 亲和性**：通用异步运行时在 CPU 密集型工作负载的调度效率不及专用线程调度器
4. **编译时间**：大型 Rust 项目的固有问题，下游集成摩擦较大

### 2025 年展望

DataFusion 社区在 2025 年的重点方向包括：远程对象存储查询优化（减少 S3 往返延迟）、更完善的 Iceberg 原生集成（`iceberg-rust`）、CBO 的持续改进（动态过滤器、运行时统计反馈）、Comet 的算子覆盖率提升。2024 年底突破 ClickBench 第一后，社区信心大增，用 InfluxData 工程师的话说："**2025 年将是 1000 个 DataFusion 系统之年**"——这一判断正在加速成为现实。

---

*参考资料：Apache DataFusion SIGMOD 2024 论文、datafusion.apache.org 官方文档、Apache DataFusion Blog、InfluxData 技术博客、RisingWave 技术博客、ASF DataFusion TLP 公告（2024.06.11）*
