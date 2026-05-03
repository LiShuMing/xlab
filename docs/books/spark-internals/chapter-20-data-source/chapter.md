# 第 20 章：Data Source V1/V2 — 外部数据的统一接入层

## 设计动机

数据库系统有一个经典的"内外边界"问题：优化器知道如何优化 Join、Aggregate、Filter——但如果数据来自一个外部系统（HDFS、S3、JDBC、Kafka），优化器必须"尊重"外部系统的能力边界。不是所有数据源都能处理任意 Filter，也不是所有数据源都支持列裁剪。

Spark SQL 的 Data Source 接口就是这一"内外边界"的翻译器。它经历了两个主要版本：

- **Data Source V1**（Spark 1.3+）：一套 simple 但有限的接口。核心是 `RelationProvider` + `PrunedFilteredScan`。问题是它 **跟 Spark 的优化器没有清晰的边界**——filter pushdown 是 ad-hoc 的，数据源无法声明"我能 push 什么"，也无法参与物理计划的构建。

- **Data Source V2**（Spark 2.3+，3.0 稳定）：一套完整的、模块化的接口体系。核心思想是"能力声明"（Capability Declaration）——每个 Table 声明自己 `capabilities()`，然后 Scan/Write 实现相应的接口（`SupportsPushDownFilters`、`SupportsPushDownAggregates` 等）。优化器通过 capability 检测来决策"要不要把这段计划下推到数据源"。

这种设计可以类比为 REST API 的 Content Negotiation——客户端（Spark）主动查询服务器（DataSource）"你能接受什么"，然后发送匹配的请求。而不是"我直接发你一个操作，你做不做随你"（V1 的模式）。

## 核心原理

### 20.1 Data Source V1 — 基础接口族

V1 接口的核心在 `org.apache.spark.sql.sources` 包中。入口是 `RelationProvider`（或 `HadoopFsRelationProvider`）：

```
Read 路径:
  RelationProvider.createRelation(sqlContext, parameters)
    → BaseRelation  ← 代表一个逻辑表
      ├── PrunedScan: 列裁剪
      ├── PrunedFilteredScan: 列裁剪 + Filter pushdown
      ├── CatalyzedScan: 接收 Expression（而非 Filter），参与 Catalyst
      └── InsertableRelation: 可写入

Write 路径:
  CreatableRelationProvider.createRelation(sqlContext, mode, parameters, data)
    → 返回 BaseRelation（写入后的关系）

底层的 FileFormat 接口:
  FileFormat
    ├── buildReader(sparkSession, dataSchema, partitionSchema, requiredSchema, filters, options, hadoopConf)
    ├── buildReaderWithPartitionValues(...)  ← 带 partition 值
    ├── write/prepareWrite
    └── supportBatch / isSplitable
```

V1 的 Filter Pushdown 通过 `Filter` 类的简单层次结构工作：

```
Filter (抽象)
  ├── EqualTo(attribute, value)
  ├── GreaterThan(attribute, value)
  ├── In(attribute, values)
  ├── IsNull(attribute)
  ├── StringStartsWith(attribute, value)
  ├── And(left, right) / Or(left, right) / Not(child)
  └── ...
```

数据源的 `buildReader` 接受一个 `Array[Filter]`——它可以选择性地应用这些 filter（例如 Parquet 的 row group statistics filter）。如果 filter 未被应用，Spark 在数据返回后会再次执行过滤。

**V1 的局限性**：

1. **不精确的 Filter Pushdown**：Filter 是"尽力而为"的——数据源不保证 filter 被完全应用。Spark 必须在返回路径上做额外的重复过滤（double-filtering）

2. **无 Aggregate / Join Pushdown**：V1 不支持将 Aggregation 或 Join 下推到数据源

3. **无 Partitioning 感知**：数据源无法告知 Spark "我按哪些列分了区"，Spark 只能通过 Hadoop 的 partition 目录结构来推断

4. **Write 路径 高度 local**：写入基于 "Spark 多任务分别写各自的文件"，缺乏分布式事务或 commit 协议

### 20.2 Data Source V2 — 能力的层次化声明

DSv2 的核心设计是一种"渐进增强接口"（Progressive Interface Enhancement）。基础接口（`Scan`、`Write`）只定义了最少的必需方法。如果一个数据源支持更多的优化，它实现对应的"Support" Mix-in 接口：

```
Table.capabilities() → Set[TableCapability]
  ├── BATCH_READ
  ├── BATCH_WRITE
  ├── MICRO_BATCH_READ
  ├── CONTINUOUS_READ
  ├── OVERWRITE_BY_FILTER (dynamic overwrite)
  ├── OVERWRITE_DYNAMIC
  ├── TRUNCATE
  └── ACCEPT_ANY_SCHEMA

ScanBuilder 可以额外实现:
  ├── SupportsPushDownRequiredColumns    ← 列裁剪
  ├── SupportsPushDownFilters            ← Filter pushdown (pre-3.5)
  ├── SupportsPushDownV2Filters          ← V2 Filter pushdown (3.5+)
  ├── SupportsPushDownAggregates         ← Aggregate pushdown
  ├── SupportsPushDownLimit              ← Limit pushdown
  ├── SupportsPushDownOffset             ← Offset pushdown
  ├── SupportsPushDownTopN               ← Top-N pushdown
  ├── SupportsPushDownTableSample        ← Table Sampling pushdown
  ├── SupportsPushDownJoin               ← Join pushdown (4.0+)
  ├── SupportsPushDownVariantExtractions ← Variant 列提取 pushdown
  ├── SupportsReportStatistics           ← 提供行数/size 统计
  ├── SupportsReportPartitioning         ← 报告数据分区方式
  ├── SupportsReportOrdering             ← 报告数据排序方式
  └── SupportsRuntimeFiltering           ← Runtime filter pushdown

WriteBuilder 可以额外实现:
  ├── SupportsOverwrite / SupportsTruncate
  ├── SupportsDynamicOverwrite
  └── RequiresDistributionAndOrdering    ← 要求特定的分区和排序

BatchWrite 的子接口:
  └── DeltaBatchWrite                    ← 支持增量写入（Spark 4.0+）
```

这种设计的好处是 **可发现性**（discoverability）：优化器在规划时调用 `scanBuilder.isInstanceOf[SupportsPushDownAggregates]`，如果否 → 不做 aggregate pushdown → 无运行时错误。每个数据源根据自己的能力"核心实现"不同的 mix-in。

### 20.3 Read 路径 — 从 Table 到 InputPartition

DSv2 的读取路径是一条清晰的管道：

```
Table
  ↓ table.newScanBuilder(options)
ScanBuilder
  ↓ optimizer 通过 Mix-in 接口传递优化信息
  │   s.pushRequiredColumns(requiredSchema)          ← SupportsPushDownRequiredColumns
  │   s.pushFilters(filters)                         ← SupportsPushDownFilters
  │   s.pushAggregation(aggregation)                 ← SupportsPushDownAggregates
  │   ...
  ↓ scanBuilder.build()
Scan (逻辑层)
  ↓ scan.toBatch()
Batch (物理层)
  ↓ batch.planInputPartitions()
InputPartition[]  ← 每个 partition → 一个 Task
  ↓ batch.createPartitionReaderFactory()
PartitionReaderFactory
  ↓ factory.createReader(inputPartition)
PartitionReader[T]
  ↓ reader.next() → next row
  ↓ reader.get()  → current row
```

每个步骤的职责非常明确：

- **ScanBuilder**：按受优化建议 + 构建逻辑 Scan
- **Scan**：提供 `readSchema()`（实际读取的 schema，可能与物理 schema 不同）+ 转为 Batch/Micro-Batch/Continuous
- **Batch**：物理执行计划——分 partition + 创建 reader factory
- **InputPartition**：表示一个数据分片——通常包含文件名 + offset range 或 key range
- **PartitionReader**：逐行或列读取——对等于 V1 的 record reader

**Columnar 优化**：`PartitionReaderFactory` 可以返回 `PartitionReader[ColumnarBatch]`（而非 `PartitionReader[InternalRow]`），Spark 就知道这个 partition 支持列式向量读取——跳过行→列转换，直接进入 ColumnarBatch pipeline。

**Runtime Filtering**：当数据源实现 `SupportsRuntimeFiltering` 时，Spark 在运行时将 BloomFilter 或 IN-list 从 Join 的 probe 侧下推到 scan 侧——减少从数据源读取的浪费数据（第 14 章覆盖）。

### 20.4 Write 路径 — 从 WriteBuilder 到 DataWriter Commit

DSv2 的写入路径是查询引擎中最复杂的操作之一，因为它涉及分布式事务语义：

```
Table
  ↓ table.newWriteBuilder(options)
WriteBuilder
  ↓ w.buildForBatch()
Write
  ↓ write.toBatch
BatchWrite
  ↓ batchWrite.createBatchWriterFactory(PhysicalWriteInfo)
DataWriterFactory
  ↓ factory.createWriter(partitionId, taskId)
DataWriter[T]
  ↓ writer.write(row)          ← 每行
  ↓ writer.commit()            ← Task 完成
  → WriterCommitMessage  ← 返回给 Driver
  ↓ Driver 收集所有 commit messages
BatchWrite.commit(messages)    ← 所有 Task 成功后，全局提交 (commit protocol)
  ↓ 或
BatchWrite.abort(messages)    ← 任何 Task 失败 → 回滚
```

`WriterCommitMessage` 是 Task 在 commit 时返回的消息——包含该 Task 写了什么文件、文件大小、统计信息等。`BatchWrite.commit` 将所有的 `WriterCommitMessage` 汇总——执行最终的文件 rename、创建元数据文件、或者调用外部系统的 commit API。

这种设计实际上实现了一个简化版的 **两阶段提交（2PC）**：
- **Phase 1**：各 Task 写入数据到临时位置 → `DataWriter.commit()` → report `WriterCommitMessage`
- **Phase 2**：所有 Task success → `BatchWrite.commit(messages)` → 最终提交（如 rename temporary files → final paths、更新 Catalog metadata）

如果任何一个 Task 失败 → `BatchWrite.abort(messages)` → 删除临时文件、回滚。

### 20.5 Pushdown 机制 — Catalyst 到 DataSource 的翻译

DSv2 pushdown 的精妙在于 **在 Catalyst Rule 层面做下推决策，在 DataSource 层面执行**。

**Filter Pushdown Example**：

```scala
// V2ScanRelationPushDown (逻辑优化规则):
// 1. 检查 Scan 是否在 V2ScanRelation 之上
// 2. 检查 ScanBuilder 是否 implements SupportsPushDownFilters
// 3. 从 Filter 节点提取 Filter predicates
// 4. 调用 scanBuilder.pushFilters(filters) → 返回 unpushed filters
// 5. 将 pushed filters 记录在 Scan 中，unpushed filters 留在计划中
```

对于 `SELECT * FROM t WHERE x > 100 AND y < 50`：

```
优化前:
  Filter(x > 100 AND y < 50)
    └── DataSourceV2ScanRelation(table=t, ...)

优化后（假设 数据源支持 x > 100 但不支持 y < 50）:
  Filter(y < 50)                        ← unpushed, Spark 执行
    └── DataSourceV2ScanRelation(table=t, pushedFilters=[x > 100], ...)
```

**Aggregate Pushdown**（`SupportsPushDownAggregates`）：

```sql
SELECT dept, COUNT(*), AVG(salary) FROM emp GROUP BY dept
```

数据源如果支持 aggregate pushdown，Spark 会将整个 `Aggregate → Scan` 子树替换为从数据源直接拉取的 "已经聚合的结果"：

```
优化前:
  Aggregate(dept, [count(1), avg(salary)])
    └── DataSourceV2ScanRelation(table=emp, ...)

优化后:
  DataSourceV2ScanRelation(table=emp, pushedAggregates=[COUNT(*), AVG(salary)], groupBy=[dept], ...)
```

对 JDBC source 来说，这意味着 Spark 可以直接生成 `SELECT dept, COUNT(*), AVG(salary) FROM emp GROUP BY dept` SQL 并下推到数据库执行——而不是拉取全量原始数据 + 在 Spark 中聚合。

### 20.6 V1 vs V2 的根源区别

| 维度 | Data Source V1 | Data Source V2 |
|------|---------------|---------------|
| 接口模型 | 单体外加 mix-in（PrunedFilteredScan） | Capability 声明 + 独立接口 |
| Physical Plan 参与 | 不参与（只提供数据） | 独立物理节点（DataSourceV2ScanExec） |
| 列裁剪 | buildScan(requiredColumns) | SupportsPushDownRequiredColumns |
| Filter Pushdown | Unreliable（spark 必须 re-filter） | Reliable（pushed/unpushed 明确区分） |
| Aggregate Pushdown | 无 | SupportsPushDownAggregates |
| Join Pushdown | 无 | SupportsPushDownJoin（4.0+） |
| Write Commit | 无明确协议 | 2PC 式 commit/abort 协议 |
| Streaming | 独立的 Streaming Source 接口 | 统一的 Scan.toMicroBatch/Continuous |
| Catalog 集成 | 无（纯路径+format） | Table catalog API（SessionCatalog 整合） |

## 关键代码片段

### 示例：ScanBuilder 的 Decisions Chain

```scala
// 典型的 DSv2 Scan 创建与优化流程:
val table: Table = catalog.loadTable(ident)

val scanBuilder: ScanBuilder = table.newScanBuilder(caseInsensitiveOptions)

// Optimizer applies rules in order:
// 1. Column pruning:
if (scanBuilder.isInstanceOf[SupportsPushDownRequiredColumns]) {
  scanBuilder.asInstanceOf[SupportsPushDownRequiredColumns]
    .pruneColumns(requiredSchema)
}

// 2. Filter pushdown:
val postScanFilters = if (scanBuilder.isInstanceOf[SupportsPushDownV2Filters]) {
  scanBuilder.asInstanceOf[SupportsPushDownV2Filters].pushPredicates(predicates)
} else if (scanBuilder.isInstanceOf[SupportsPushDownFilters]) {
  scanBuilder.asInstanceOf[SupportsPushDownFilters]
    .pushFilters(filters.toV1FilterArray)
    .map(_.toV2Predicate(attrMap))
} else predicates  // 如果都不支持, 全部留作 post-scan filter

// 3. Aggregate pushdown:
// ...

val scan: Scan = scanBuilder.build()
val batch: Batch = scan.toBatch()
val partitions: Array[InputPartition] = batch.planInputPartitions()
```

## 硬件视角

**Data Source Pushdown 的 I/O 效应**：

Filter pushdown 的收益不只是"减少 Spark 内存中的行数"——更关键的是 **减少从存储系统传输到 Spark Executor 的网络/磁盘字节数**。这在云存储场景中尤为突出：

```
场景: S3 上的 10TB Parquet 表, SELECT * WHERE date = '2024-01-01'

无 pushdown (V1 unreliable):
  → 读取所有 10TB parquet 文件的页脚 → 发现 day partition = 365 个
  → 仍然读取 10TB / 365 ≈ 27GB 的数据到 Executor
  → Executor 解压 + filter → 最终保留 100MB
  → 网络浪费: 27GB - 100MB ≈ 26.9GB

有 pushdown (V2 reliable + parquet row group filter):
  → 读取 Footer: predicate date = '2024-01-01' → 只扫描匹配的 row groups
  → 实际读取: 100MB
  → 无浪费

在 10GbE 网络上: 26.9GB 约 27 秒。对于日批处理而言，如果 50 条类似查询 → 每天浪费 12 分钟的网络 I/O 容量。
```

**Partition Pushdown 的虚拟列效应**：

Hive-style partition pruning 将 partition 列视为"不在于数据文件中"的虚拟列——Spark 从文件路径中提取它们的值（如 `/data/date=2024-01-01/`）。这意味 partition pruning 完全避免了对数据文件的任何 I/O——如果只有一天的 partition 被选择，其他 364 天的文件甚至不会被 listing。Partition listing 本身（`FileIndex.listFiles`）可能是元数据密集型操作——在 S3（对象存储）场景中，列出 100 万个文件可能花费 10+ 秒。Partition pruning 减少了 list 的范围，在很大的 S3 表上是决定性优化。

## AI 时代反思

DSv2 的 capability 接口是一种"机器可读的能力声明"——`SupportsPushDownFilters`、`SupportsPushDownAggregates` 等。这种设计跟 LLM Function Calling 的 schema 声明有异曲同工之处：在 Function Calling 中，Agent 声明"我能接受这些参数"；在 DSv2 中，DataSource 声明"我能处理这些操作"。两者都是"基于能力声明的任务分发"。

这种平行关系暗示了一个有趣的可能性：**LLM Agent 作为 Data Source 的前端**。一个 Agent 可以 reads `Table.capabilities()` → 了解了这个数据源"能接受什么" → 然后在 SQL 查询规划时考虑这些能力。例如：

```
用户: "找出最近 7 天销售额最高的 5 个产品"

Agent (查询 planner):
  1. 检查 sales_table.capabilities() → [BATCH_READ, SUPPORTS_AGG_PUSHDOWN, SUPPORTS_TOP_N]
  2. 确认: 数据源支持 Agg + Top-N → 可以完全下推
  3. 生成: SELECT product, SUM(amount) FROM sales 
     WHERE date > today()-7 GROUP BY product ORDER BY SUM(amount) DESC LIMIT 5
  4. 整个查询不再需要 Spark 处理 — Data Source 返回最终 5 行
```

这与传统的 CBO 不同：CBO 依赖成本模型做决策，而 Agent 还可以利用"历史经验"——"上次这个 JDBC Source 推了 aggreg，数据库的 CPU 飙到了 90% → 这次要保守"。

## 源码导航

| 文件 | 关键内容 | 行号参考 |
|------|---------|---------|
| `sql/catalyst/src/main/java/org/apache/spark/sql/connector/read/Scan.java` | Scan 接口，toBatch/toMicroBatch/toContinuous | 46 (interface), 52 (readSchema), 79 (toBatch) |
| `sql/catalyst/src/main/java/org/apache/spark/sql/connector/read/ScanBuilder.java` | ScanBuilder 入口 | |
| `sql/catalyst/src/main/java/org/apache/spark/sql/connector/read/Batch.java` | Batch 接口，planInputPartitions/createPartitionReaderFactory | |
| `sql/catalyst/src/main/java/org/apache/spark/sql/connector/read/SupportsPushDownFilters.java` | SupportsPushDownFilters，pushFilters/unpushable filters | 30 (interface), 38 (pushFilters) |
| `sql/catalyst/src/main/java/org/apache/spark/sql/connector/read/SupportsPushDownAggregates.java` | SupportsPushDownAggregates，aggregate pushdown | |
| `sql/catalyst/src/main/java/org/apache/spark/sql/connector/read/SupportsPushDownRequiredColumns.java` | SupportsPushDownRequiredColumns，列裁剪 | |
| `sql/catalyst/src/main/java/org/apache/spark/sql/connector/write/WriteBuilder.java` | WriteBuilder 入口 | |
| `sql/catalyst/src/main/java/org/apache/spark/sql/connector/write/BatchWrite.java` | BatchWrite，createBatchWriterFactory + commit(messages) | |
| `sql/catalyst/src/main/java/org/apache/spark/sql/connector/write/DataWriter.java` | DataWriter[T]，write/commit/abort，返回 WriterCommitMessage | |
| `sql/core/src/main/scala/org/apache/spark/sql/execution/datasources/FileSourceStrategy.scala` | V1 的 FileSourceStrategy 策略，FileIndex + FileFormat 交互 | |
| `sql/core/src/main/scala/org/apache/spark/sql/execution/datasources/HadoopFsRelation.scala` | HadoopFsRelation，V1 核心类 | |
| `sql/core/src/main/scala/org/apache/spark/sql/execution/datasources/v2/DataSourceV2Relation.scala` | DataSourceV2Relation，Catalyst 中的 DSv2 逻辑节点 | |
| `sql/core/src/main/scala/org/apache/spark/sql/execution/datasources/v2/DataSourceV2ScanExec.scala` | 物理算子，转换为 RDD reader | |
| `sql/catalyst/src/main/java/org/apache/spark/sql/connector/catalog/TableCapability.java` | TableCapability 枚举(BATCH_READ, BATCH_WRITE, ...) | |
