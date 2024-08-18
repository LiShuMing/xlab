# 第 22 章：Iceberg & Delta Lake — 表格式的现代进化

## 设计动机

Hive 表格式统治了大数据十年——一个 `_SUCCESS` 文件标记写入完成，一个 `part-00000.parquet` 文件代表数据，目录结构（`/data/date=2024-01-01/`）决定分区。这个模型简单、可扩展，但有三个使得"表"退化为"一堆文件的集合"的问题：

1. **无 ACID 事务**：并发读写可能读到不完整的文件（Reader 看到 Writer 写了 3 个文件但第 4 个还没 rename）。没有任何"原子性"保证。

2. **分区不可演化**：Hive 的 partition 是物理目录结构——如果想从 `date` 改为 `hour` 分区，必须重写所有数据（ALTER TABLE 改 partition column → 全量重写）。一张 100TB 的表改个分区粒度 → 100TB 写入开销。

3. **Schema 演进不支持**：添加/删除/修改列需要重写整个数据集。即使 Parquet 本身支持 schema evolution，Hive catalog 的 rigid schema 使这个能力无法发挥。

Iceberg 和 Delta Lake 就是为解决这三个问题而生的 **表格式（Table Format）**。它们不是新的文件格式（仍然使用 Parquet/ORC 作为底层存储），而是一个 **在文件系统之上的元数据管理层**——定义：
- 一组数据文件如何组成一张表的某个版本（Snapshot）
- 并发写入者如何在文件系统中协调提交（Commit Protocol）
- 历史版本如何被保留和检索（Time Travel）

用一句话概括："表格式之于数据湖 ≈ MVCC 之于 PostgreSQL"。它们把文件系统的"无事务、文件粒度"接口封装成"有事务、表粒度"接口。

## 核心原理

### 22.1 三层元数据架构

Iceberg 和 Delta 的核心架构都遵循类似的"三层元数据"模式：

```
Iceberg 的三层模型:
  catalog (HMS/Glue/JDBC)
    └── metadata.json (或 table-metadata)
          ├── schema
          ├── partition spec
          ├── snapshot log (current + history)
          └── current snapshot → manifest list
    
          ↓
    
  manifest list (avro file)
    └── for each manifest:
          ├── partition range (e.g. date=2024-01-01 ~ 2024-01-31)
          ├── data file count
          └── manifest file path
    
          ↓
  
  manifest file (avro file)
    └── for each data file:
          ├── file path
          ├── file format (parquet/orc/avro)
          ├── partition values
          ├── column stats (min/max/nullCount per column)
          └── row count / file size / record count


Delta Lake 的三层模型:
  _delta_log/
    └── <version>.json (commit log, one per transaction)
          ├── add(path, partitionValues, stats, size, modificationTime)
          ├── remove(path, deletionTimestamp)
          ├── metaData(schema, partitionColumns, configuration)
          └── commitInfo(timestamp, operation, readVersion, isolationLevel)

  内存中的 Snapshot 状态:
    → 从最近的 checkpoint.parquet 恢复 (Spark 内部 Log Replay)
    → 增量 replay 自 checkpoint 到最新 version 的 commit log
```

两者的核心差异：
- **Iceberg** 用 snapshot 引用链（每次写入创建新的 manifest list + manifest files），显式的 OCC（Optimistic Concurrency Control）通过 catalog 中的 metadata file 原子 swap
- **Delta** 用 commit log（按版本增长的 JSON 文件），commit 通过 `_delta_log/` 目录下的原子文件命名实现（文件名 = 版本号）

### 22.2 ACID 事务 — 乐观并发控制

两个表格式都通过 **乐观并发控制（OCC）** 实现原子性——不是在写入期间加锁，而是在提交时检查是否有冲突：

```
Iceberg OCC:

Writer-1 (写入 INSERT):
  1. 读取当前 metadata.json → snapshot S0 (基础)
  2. 写数据文件到 data/ 目录
  3. 写 manifest 文件到 metadata/
  4. 写 manifest list 文件
  5. 创建新的 metadata.json (引用新的 manifest list)
  6. 向 Catalog 提交: 
     CATALOG.COMMIT(table, S0 → S1)
     - 如果 Catalog 中当前 metadata 仍指向 S0 → 成功
     - 如果 Catalog 中当前 metadata 已变为 S0'(别的 Writer 提交了) → 失败 → 重试


Delta Lake OCC:

Writer-1 (写入 INSERT):
  1. 读取最新的 transaction log → version=N
  2. 写数据文件到 data/ 目录
  3. 提交: 写 _delta_log/00000<N+1>.json
     - 包含: add(path, ...) + commitInfo(readVersion=N)
  4. 如果 00000<N+1>.json 已存在（别的 Writer 已提交） → 冲突 → 失败 → 重试
```

这种机制的正确性基于文件系统的一个保证：**同一路径的原子文件创建**。在 HDFS 中，`create(path, overwrite=false)` 如果文件已存在会失败。在 S3 中虽然没有原生原子性，但 Iceberg 通过向 Catalog（HMS/Glue）提交 metadata 路径变更来实现等价原子性。

### 22.3 Snapshot 与时间旅行

每次成功的 commit 都创建一个新的 **Snapshot**——包含该时刻表的完整状态（所有有效的 data files）。这是时间旅行的基础：

```sql
-- Iceberg time travel:
SELECT * FROM prod.db.orders VERSION AS OF '2024-06-01 10:00:00'
SELECT * FROM prod.db.orders FOR SYSTEM_TIME AS OF '2024-06-01'

-- Delta time travel:
SELECT * FROM delta.`/data/orders` VERSION AS OF 5
SELECT * FROM delta.`/data/orders` TIMESTAMP AS OF '2024-06-01'
```

Snapshot 不是数据副本——它只记录"这个版本包含哪些 data files"。多个 snapshot 共享 data files，不产生存储冗余。时间旅行的代价是"额外的 metadata lookup"，不是"额外的数据存储"。

Snapshot 的保留有两种策略：
- **保留最近 N 个 snapshot**（默认）
- **基于时间窗口保留**（保留 7 天内所有快照，自动 expire 旧快照）
- Expire 旧 snapshot → 删除不再被任何 snapshot 引用的 data files

### 22.4 Partition Evolution — 分区的隐式演化

这是 Iceberg 最被低估的创新。Hive 的分区是"显式目录"：`date=2024-01-01/`。Iceberg 的分区是"隐式转换"：

```
表初始创建: PARTITIONED BY (days(timestamp))
  → timestamp=2024-01-01T10:00:00 → partition value = days("2024-01-01") = 19724

元数据 (manifest file):
  partition spec: (days(timestamp))
  manifest 文件记录每个 data file:
    file=00000.parquet, partition={timestamp_day=19724}, stats={timestamp: [2024-01-01T00:00, 2024-01-02T00:00)}

生产演变: ALTER TABLE ... SET PARTITION SPEC (hours(timestamp))
  → 不需要重写任何旧数据！
  → 只有新写入的文件使用新的 partition spec
  → 查询时 Iceberg 根据 partition spec 的版本做 plan 合并

一个表同时有两个 partition specs:
  spec-0: days(timestamp)  ← 旧文件
  spec-1: hours(timestamp) ← 新文件

查询: SELECT * WHERE timestamp = '2024-06-15T14:00:00'
Iceberg Planner:
  → spec-0: days('2024-06-15T14:00:00') = 19890 → scan manifest for {day=19890}
  → spec-1: hours('2024-06-15T14:00:00') = 477360 → scan manifest for {hour=477360}
  → 合并两者, 识别匹配的 data files
```

这个设计优雅地解决了"分区粒度变更"的数据工程 DBA 噩梦。

### 22.5 Deletion Vectors & Merge-on-Read

传统的数据湖更新（`UPDATE`/`DELETE`/`MERGE INTO`）必须重写整个 Parquet 文件——即使只改了其中 1% 的行。Deletion Vectors 改变了这个范式，实现了"Merge-on-Read"：

```
传统 COPY-ON-WRITE MERGE:
  MERGE INTO table t USING source s ON t.id = s.id
  WHEN MATCHED THEN UPDATE SET t.amount = s.amount
  → 扫描 table 的所有 data files → 逐行 check 是否在 source 中
  → 将匹配行更新，未匹配行保留 → 写入全新文件
  → I/O: 读取整个表 + 写入整个表

Deletion Vectors MERGE:
  MERGE INTO table t USING source s ON t.id = s.id
  WHEN MATCHED THEN UPDATE SET t.amount = s.amount
  → 维护一张 deletion vector (bitmap 或 RoaringBitmap)
    → file_001.parquet: deleted_rows = {5, 12, 3002}
  → 写入更新后的行到新的小文件
  → 读取时: file_001.parquet + filter out deleted rows + merge 更新行
  → I/O: 只写入变更的行 (可能 <1% 的文件大小)
```

Deletion Vector 的关键权衡：
- **存储节省**：不必重写完整文件
- **读取代价增加**：scan 时需要读取 deletion vectors + filter 删除行
- **Compaction**：后台定期合并 deletion vectors → 重写那些删除率 > 阈值（如 30%）的文件 → 摊销 I/O 成本

### 22.6 文件级统计与 Data Skipping

Iceberg/Delta 的 manifest 文件对每个 data file 记录了全面的列级统计（min/max/null count）：

```
Iceberg manifest entry for file=00000-xxx.parquet:
  column_stats:
    order_date:    min=2024-01-01, max=2024-01-31, null_count=0
    amount:        min=0.01, max=9999.99, null_count=0
    customer_id:   min=100000, max=999999, null_count=0

Query: SELECT * FROM orders WHERE order_date = '2024-01-15' AND amount > 1000

Iceberg Planner:
  1. order_date = '2024-01-15' → partition filtering → select matching manifests
  2. 对每个 data file 的 stats 做 filter:
     - 如果 file stats: order_date.max < '2024-01-15' → skip
     - 如果 file stats: order_date.min > '2024-01-15' → skip
     - 如果 file stats: amount.max < 1000 → skip
  3. 返回剩余的 data files → 真正的 I/O 只发生在这些文件上
```

这个被称为 "data skipping" 的技术能将很多查询的 I/O 降低 10-100 倍——特别是在有序数据（sorted by date）上，min/max 过滤的命中率很高。

### 22.7 与 Spark DSv2 的集成

Iceberg 和 Delta 都是 Spark DataSourceV2 的**参考实现**：

```
Read 路径:
  IcebergSource extends TableProvider with DataSourceRegister
  → IcebergTable extends Table with SupportsRead
    → newScanBuilder(options) → IcebergScanBuilder
      → implements SupportsPushDownFilters
      → implements SupportsPushDownRequiredColumns
      → implements SupportsReportStatistics
      → build() → SparkScan
        → toBatch() → SparkBatch
          → planInputPartitions() → 基于 manifest file 划分的 InputPartition[]
          → createPartitionReaderFactory() → PartitionReader[ColumnarBatch]  ← 列式向量读取

Write 路径:
  IcebergTable extends Table with SupportsWrite
    → newWriteBuilder(options) → IcebergWriteBuilder
      → buildForBatch() → 实现 BatchWrite
        → DataWriter.write(row) → 写入 Parquet 文件
        → DataWriter.commit() → WriterCommitMessage (文件路径 + partition)
        → BatchWrite.commit(messages) → OCC commit to Catalog
        → BatchWrite.abort(messages) → delete temp files
```

两者的实现非常相似——它们证明了 DSv2 的 capability 声明模型可以有效支持"外部表格式"的全部事务操作。

### 22.8 Iceberg vs Delta vs Hudi — 选择框架

| 维度 | Iceberg | Delta Lake | Apache Hudi |
|------|---------|------------|-------------|
| 架构重点 | 通用表格式、partition evolution | Spark-centric、简单配置 | 流式 upsert、incremental pipeline |
| Snapshots | 显式 snapshot 引用 | Commit log 回放 | Timeline + Instant |
| Partition Evolution | 原生支持 | 重写数据 | 原生支持 |
| 并发控制 | 乐观基于 Catalog swap | 乐观基于文件命名 | 乐观基于 Timeline |
| Manifest 格式 | Avro | JSON（checkpoint 用 Parquet） | Avro |
| Column Stats | 全列 min/max/null | 全列（前 32 列） | 仅索引列 |
| Deletion Vectors | 文档化，生产中 | Deletion Vectors + ColumnMapping | Merge-on-Read tables |
| Spark 集成 | DSv2 | 自有 Catalog + DSv2 | DSv2 |
| 非 Spark 引擎 | Flink, Trino, Presto, Hive, Impala | 少量支持 | Flink, Presto, Hive |
| 写入吞吐 | 高（不维护索引） | 高 | 中（维护索引 overhead） |
| 读取性能 | 极高（predicate pushdown） | 高 | 高 |

## 关键代码片段

### 示例：Delta Lake Commit 的简化逻辑

```scala
// 简化的 Delta OptimisticTransaction.commit():
def commit(): Unit = {
  val currentVersion = getLatestVersion()  // 读取 _delta_log 最新版本号
  
  // Phase 1: 写数据文件到 data/ 目录
  val newFiles: Seq[AddFile] = writeDataFiles()

  // Phase 2: 构建 commit entry
  val commitEntry = CommitInfo(
    version = currentVersion + 1,
    timestamp = System.currentTimeMillis(),
    operation = "WRITE",
    readVersion = currentVersion
  )
  
  // Phase 3: 原子提交 (关键一步)
  val commitFile = s"_delta_log/${formatVersion(currentVersion + 1)}.json"
  try {
    // 如果文件已存在 (另一个 writer 先提交) → 抛异常 → OCC 冲突
    writeAtomicJson(commitFile, newFiles ++ commitEntry)
  } catch {
    case _: FileAlreadyExistsException =>
      // 冲突 → 检查是否可以 resolve：
      //   如果两个写入没有重叠 → 自动 resolve
      //   如果两个写入有重叠 → 报告冲突 → 用户/上层重试
      throw new ConcurrentWriteException(...)
  }
}
```

## 硬件视角

**Manifest 读取的 I/O 模式**：

Iceberg 查询计划的第一步是读取 manifest list → 然后读取相关的 manifest files → 最后扫描数据。三者的 I/O 比例取决于查询类型：

```
查询: SELECT COUNT(*) FROM orders WHERE order_date = '2024-06-15'

1. Read metadata.json (1 次 read, ~2KB)
2. Read manifest list (1 次 read, ~10KB)
3. Read partition-filtered manifests (约 1-5 个, ~100-500KB each)
4. Data file stats filtering → 确定匹配的 data files (约 100-200 个)
5. Scan data files for rows matching order_date = '2024-06-15' (约 500MB)

I/O breakdown:
  metadata: 0.01%
  manifests: 0.05%
  data scan: 99.94%

Manifest I/O 在分区良好的表上是可忽略的。但在分区设计不佳+无 partition filter 的查询中，manifest 读取量可能达到 100MB-1GB——此时 manifest 读取本身就是一个瓶颈。
```

**数据文件的分布与磁盘并 行度**：

Iceberg 的 `planInputPartitions()` 会将 data files 分组为合理大小的 InputPartition。一个典型的决策：如果一个 data file 有 128MB，那就是一个 InputPartition。如果一个 partition 包含 20 个 10MB 的小文件，它们可能被合并到 2 个 InputPartition 中（每个 ~100MB）。

这种 "文件集合到 partition 的映射" 决定了 I/O 并行度：如果表只有 10 个 data files → 最多 10 个并行度 → 最多调用 10 个 Executor core → 可能的 I/O 上限 = 10 × SSD bandwidth。

## AI 时代反思

表格式的元数据模型（files → manifest → snapshot）是一个非常适合 LLM Agent 的"操作空间"，因为它们有清晰的结构，可以用自然语言解释：

```
用户: "为什么这个查询扫描了 5000 个文件但只需要 2024-06-15 一天的数据？"

Agent:
  1. Reads iceberg.scan_metrics → filtered_files=5000, matched_files=2
  2. 分析 manifest entries → 发现该表的 partition spec 是 days(event_time)
  3. 但查询条件是 WHERE date(timestamp_utc) = '2024-06-15'
     → event_time != timestamp_utc！→ partition filter 无法 push down
  4. Agent 回复:
     "该查询的 WHERE 条件使用了 `timestamp_utc` 列，但表按 `event_time` 分区。
      这导致 Iceberg 的 partition filter 无法生效，所有 5000 个文件都被扫描。
      建议: (1) 在 SELECT 中改用 `event_time` 作为过滤列，或者
           (2) 使用 `timestamp_utc` 作为新的 partition key（利用 Iceberg 的 partition evolution）"
```

这类"发现查询计划中的滤波失配"是用 LLM Agent 的典型案例——比 AI 直接写 SQL 的价值高很多，因为用户已经有了 SQL，缺的是"执行效率诊断"。

另一个有意思的方向：**LLM 如何选择 Iceberg vs Delta**。两者在功能上日趋收敛，选哪一个更多是"组织性决策"（团队熟悉度、生产经验、多引擎支持需求）。LLM 可以帮助用户分析"你的工作负载模式 + 关键需求 → 匹配度建议"，但这需要 LLM 了解 Iceberg 和 Delta 的最新特性集差异——这恰恰是 training data 截止日期之前的内容和截止后更新的内容之间的 friction point。

## 源码导航

| 文件/项目 | 关键内容 | 行号参考 |
|-----------|---------|---------|
| Apache Iceberg: `core/src/main/java/org/apache/iceberg/Table.java` | Table 接口，newScan/newAppend/newOverwrite，schema/partition spec | |
| Apache Iceberg: `core/src/main/java/org/apache/iceberg/Snapshot.java` | Snapshot 接口，allManifests()/addedDataFiles()，snapshotId/timestamp | |
| Apache Iceberg: `spark/v3.3/spark/src/main/java/org/apache/iceberg/spark/source/SparkScanBuilder.java` | SparkScanBuilder，DSv2 ScanBuilder 实现，pushAggregation/pushFilters | |
| Apache Iceberg: `core/src/main/java/org/apache/iceberg/ManifestReader.java` | ManifestReader，manifest file 解析，stats filtering | |
| Delta Lake: `core/src/main/scala/org/apache/spark/sql/delta/OptimisticTransaction.scala` | OptimisticTransaction，commit 逻辑，OCC 冲突检测 | |
| Delta Lake: `core/src/main/scala/org/apache/spark/sql/delta/DeltaLog.scala` | DeltaLog，commit log 管理，snapshot 恢复 | |
| Delta Lake: `core/src/main/scala/org/apache/spark/sql/delta/files/TransactionalWrite.scala` | TransactionalWrite，DSv2 写入集成点 | |
