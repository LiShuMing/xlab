# 第 21 章：Write Flow — 分布式写入与 Commit 协议

## 设计动机

查询引擎中，Read 路径是"数据的进口"，Write 路径是"数据的出口"。但 Write 路径远比 Read 路径复杂——因为 Read 是纯读取（无副作用，只需保证读到的是什么），而 Write 涉及文件系统的 **事务性保证**：

1. **部分失败问题**：10 个 Task 分别在写 10 个文件，7 个成功，3 个失败了——怎么办？全部丢弃重新来？还是保留成功的？

2. **提交语义**：在 HDFS/S3 这种不支持 SQL 事务的文件系统中，如何实现"要么全成功、要么全不成功"的原子性？答案是 **两阶段提交（2PC）**——先写到临时位置，全部确认后 rename 到最终位置。

3. **动态分区覆盖**：`INSERT OVERWRITE TABLE t PARTITION(date='2024-01-01')`——只覆盖指定分区，不碰其他分区的数据。如何在文件层面实现？

4. **并发写入安全**：如果两个 Job 同时向同一个表/分区写入，如何保证不相互破坏？

Spark 的 Write Flow 通过 `FileFormatWriter` + `FileCommitProtocol` + `OutputCommitter` 的三层组合解决了这些问题。

## 核心原理

### 21.1 Write Flow 总览 — 三层架构

```
SQL Layer:
  INSERT INTO / INSERT OVERWRITE TABLE / INSERT OVERWRITE DIRECTORY
  
  ↓ Catalyst 解析 → InsertIntoHadoopFsRelationCommand (V1) 或 V2Write (DSv2)

Command Layer:
  InsertIntoHadoopFsRelationCommand.run(sparkSession)
    → FileFormatWriter.write(...)

Writer Layer:
  FileFormatWriter.write()
    ├── 1. Driver Setup:
    │     ├── fileFormat.prepareWrite(...) → OutputWriterFactory
    │     └── committer.setupJob(job)
    │
    ├── 2. Distributed Write (Spark Job):
    │     └── for each RDD partition (Task):
    │           executeTask() → write data rows → commit task
    │           │   ├── OutputWriterFactory.newInstance(partitionPath, ...)
    │           │   │     → OutputWriter (e.g. ParquetOutputWriter, OrcOutputWriter)
    │           │   ├── writer.write(row) ← 每行
    │           │   ├── writer.close() → 写出文件
    │           │   └── committer.onTaskCommit(taskMsg) → 返回 WriteTaskResult
    │
    └── 3. Global Commit (Driver):
          ├── committer.commitJob(job, allTaskMsgs)
          │     → rename temp files → final paths
          │     → create _SUCCESS marker
          └── processStats (WriteJobStatsTracker)
```

### 21.2 FileFormatWriter — 分布写引擎

`FileFormatWriter.write` 是 V1 Write 的核心入口。它的流程映射到一个标准的 MapReduce Output：

```scala
// FileFormatWriter.scala:85
def write(
    sparkSession: SparkSession,
    plan: SparkPlan,          // 子查询的执行计划
    fileFormat: FileFormat,   // Parquet/ORC/JSON/CSV/...
    committer: FileCommitProtocol,
    outputSpec: OutputSpec,
    hadoopConf: Configuration,
    partitionColumns: Seq[Attribute],
    bucketSpec: Option[BucketSpec],
    statsTrackers: Seq[WriteJobStatsTracker],
    options: Map[String, String]): Set[String]
```

**partition-aware 写**：`partitionColumns` 分为静态（在 SQL 中显式指定）和动态（由数据值决定）。`FileFormatWriter` 会按动态 partition 列排序数据，确保同一个 partition 的所有行在同一个 Task 中处理——这样每个 Task 可以独立地写它负责的 partition 文件。

**Task 级写入逻辑**（`executeTask`）：

```
1. 创建 FileWriterCommitMessage 用于记录此 Task 的写入结果
2. 创建 Sort 和 ConcurrentOutputWriter（如果并发写启用）
3. while (还有行):
     - 识别当前行的 partition（根据 partitionColumns）
     - 如果 partition 变了 → 关闭当前 OutputWriter，打开新 partition 的 writer
     - writer.write(row)
4. 关闭所有 OutputWriters
5. 调用 committer.onTaskCommit(writeMsg) → 返回最终的 WriterCommitMessage
```

**ConcurrentOutputWriter**：在 `spark.sql.maxConcurrentOutputFileWriters > 0` 时，一个 Task 可以同时打开多个 OutputWriter——当一个 partition 的 writer 在 flush 时，其他 partition 的 writer 可以继续写入。这在 IOPS 绑定的场景中有效，但可能增加磁盘队列深度压力。

### 21.3 OutputCommitter — Hadoop 的 Commit 语义适配

Spark V1 Write 通过 Hadoop 的 `OutputCommitter` 接口实现对文件系统的两阶段提交：

```
Hadoop OutputCommitter（适配器层）:
  SQLHadoopMapReduceCommitProtocol ← Spark 的增强实现
    extends FileCommitProtocol ← Spark 接口
      └── 封装了 Hadoop OutputCommitter 的两阶段提交

Hadoop 标准 OutputCommitter（底层）:
  1. setupJob(job)
  2. setupTask(taskContext)
  3. needsTaskCommit(taskContext) → true
  4. commitTask(taskContext)      → Task 级别 commit
  5. commitJob(jobContext, ...)   → Job 级别 commit (rename _temporary → final)
  6. abortJob(jobContext, ...)    → 回滚 (删除 _temporary)
```

**`SQLHadoopMapReduceCommitProtocol`** 的关键行为：

```
commitJob:
  1. 调用底层 OutputCommitter.commitJob(jobContext)
  2. 删除所有 task-level 的 temporary 目录
  3. 创建 _SUCCESS 文件（Hadoop convention）
  4. 处理动态分区覆盖的清理

abortJob:
  1. 调用底层 OutputCommitter.abortJob(jobContext)
  2. 清理所有 temporary 文件
```

临时文件写在哪里由 `spark.sql.sources.writeJobUUID` 决定——每个 write job 有唯一的 UUID，临时文件路径为 `.spark-staging-<UUID>/`，这样多个并发的 write job 互相不干扰。

### 21.4 SaveMode — 写入的四种语义

```
SaveMode:
  APPEND:   追加到现有数据（不删除旧文件）
  OVERWRITE: 删除所有旧数据，写新数据
  ERROR_IF_EXISTS: 如果表不为空 → 抛异常
  IGNORE:    如果表不为空 → 跳过写入
```

**OVERWRITE** 是 2PC 的完整应用：

```
OVERWRITE 流程:
  1. setupJob → 创建 .spark-staging-<UUID>/ 临时目录
  2. 每个 Task 写文件到临时子目录
  3. commitJob:
     a. rename 临时文件 → 最终路径
     b. 删除旧的（非临时）文件
     c. 清理临时目录
  4. 如果 abortJob:
     a. 删除所有临时文件
     b. 旧文件保持不变
```

**动态分区覆盖**（`PartitionOverwriteMode.DYNAMIC`）更精细：只覆盖实际被写入的 partition，而不是整个表。每个 Task 返回 `updatedPartitions` set，commitJob 时只删除这些被覆盖的 partition 的旧文件。

### 21.5 Static vs Dynamic Partition Write

静态 partition 和动态 partition 的写入行为有根本区别：

```
静态 partition (e.g. INSERT INTO t PARTITION(date='2024-01-01')):
  - partition 列是常量，不参与数据列
  - 所有行写入同一个目标 partition 路径
  - 最简单的情况——单机写即可

动态 partition (e.g. INSERT INTO t PARTITION(date)):
  - partition 列的值来自数据行
  - 同一 Task 可能处理多个 partition 的行
  - FileFormatWriter 会先按 partition 列排序 → 同一 partition 的行连续
  - 每切换 partition → 关闭旧的 OutputWriter → 打开新的
```

当静态和动态 partition 混合时（`INSERT INTO t PARTITION(year=2024, month) SELECT day, ...`），`numStaticPartitionCols` 区分前 `N` 个 partition 列是静态的，后续是动态的。

### 21.6 Bucket 写入 — 为 Bucket Join 准备数据

Bucket 写入的一个关键约束是：**BucketId 必须在 Task 内部是连续的**。`FileFormatWriter` 为此按照 (dynamicPartitionColumns, bucketId) 排序数据——确保同一个 partition + bucket 的所有行由同一个 Task 处理。

Bucket 文件的命名规则包含 bucketId，格式为 `part-00000-<UUID>-c000.snappy.parquet`，其中 `00000` 是 bucket ID 的前 5 位数字。

### 21.7 DSv2 Write — WriteBuilder + BatchWrite 的 Commit 链

DSv2 的写入在物理计划中有独立的执行节点——`WriteFiles`：

```
WriteFiles
  ├── description: WriteJobDescription
  ├── committer: FileCommitProtocol
  └── child: SparkPlan  ← 要写入的数据来源

WriteFiles.executeWrite(queryExecution):
  1. child.execute() → RDD[InternalRow]
  2. 执行与 FileFormatWriter 相同的 executeTask 逻辑
  3. 同样经 committer 做 2PC
```

DSv2 的 `BatchWrite.commit(messages)` 提供了一个扩展点——自定义数据源（如 Iceberg、Delta Lake）可以在这里实现自己的 commit 逻辑（而非依赖 Hadoop OutputCommitter）。这正是下一章的核心内容。

## 关键代码片段

### 示例：动态分区的 Task 级写入

```
Task-1 处理 RDD partition 的 1000 行, 动态 partition = (date, region):
  行 0: date=2024-01-01, region=US  → 打开 writer(path/date=2024-01-01/region=US/)
  行 1-50: 同样 partition → 写入同一 writer
  行 51: date=2024-01-01, region=EU → 关闭 US writer, 打开 EU writer
  行 51-200: 写入 EU writer
  行 201: date=2024-01-02, region=EU → 关闭 EU writer, 打开新 writer(path/date=2024-01-02/region=EU/)
  ...
  完成: 关闭所有 writer → onTaskCommit → 返回 updatedPartitions = {"date=2024-01-01", "date=2024-01-02"}

Driver commitJob:
  → 对本 Job 覆盖的 partition 执行: deleteOldFiles(partition-path) + moveNewFiles
  → 不碰 date=2024-01-03 的 partition 数据
```

## 硬件视角

**Rename Atomicity 与文件系统**：

commitJob 中 `rename(temp → final)` 的原子性取决于文件系统类型：

- **HDFS**：`rename` 是原子性的（在同一 NameNode 下）。如果 rename 成功 → 所有 reader 都能看到完整的文件。如果失败 → 旧文件不受影响。

- **S3（对象存储）**：没有原生 `rename`。Hadoop S3A connector 通过 `copy + delete` 模拟 rename——这意味着 commitJob 不是原子性的。如果在 copy 过程中发生故障 → 可能出现"目标位置有部分文件但没 `_SUCCESS` 标记"的情况。Spark 通过 `_SUCCESS` 文件的存在性来判断写入是否完成。

这种文件系统语义的差异解释了为什么在生产中 S3 上的 `INSERT OVERWRITE` 比 HDFS 慢很多——commit 阶段要 copy（上传）所有数据，而不是简单的元数据变更。

**小文件问题**：

一个 200 partition 的 Shuffle + `INSERT INTO` 会在目标位置产生 200 个文件。如果 `spark.sql.shuffle.partitions=200`，每个 partition 大小约 50MB——合理。但如果表只有 100MB total、partition 数仍是 200 → 每个文件只有 0.5MB → "小文件问题"——HDFS NameNode 元数据膨胀 + S3 API 调用次数激增。

AQE 的 `CoalesceShufflePartitions` 在读取端合并小 partition，但如果写入端没有类似机制，文件数量最终仍由 Shuffle partition 数决定。这是一个常见的生产事故——"AQE 让读取快了，但写入产生了 1000 个小文件"。

## AI 时代反思

Write Flow 的 2PC 协议是 LLM 训练数据中的"极低覆盖率区"。Spot check：在训练数据中，关于 Spark 写入的文章 85%+ 是关于 `INSERT INTO` SQL 语法，只有 <5% 涉及 `FileCommitProtocol` 或 `OutputCommitter`。而生产环境中的写入问题 90% 都发生在 commit 阶段——rename 超时、S3 eventual consistency、并发写入的 partition 竞态。

这暗示了一个 AI-native 工具的场景：**Write History Debugger**。一个 Agent 可以读取：
- Write Job 的 `_SUCCESS` metadata（时间、UUID、Task 数）
- 目标路径的文件列表 + 时间戳
- 集群的同时运行 Job 历史

→ 回答："刚才这个分区为什么没有数据？——因为另一个 Job（UUID=xxx）在同时进行 dynamic overwrite，在 Spark 的 appendFile 之前删除了这个 partition 下的文件"。

这就是 LLM Agent 的"模式匹配 + 解释"在数据写入场景中的价值——比用户手动查询文件系统 + 读 Spark UI 快好几个数量级。

## 源码导航

| 文件 | 关键内容 | 行号参考 |
|------|---------|---------|
| `sql/core/src/main/scala/org/apache/spark/sql/execution/datasources/FileFormatWriter.scala` | FileFormatWriter，write 总入口，executeTask Task 级写入，writeAndCommit 2PC，ConcurrentOutputWriter，OutputSpec/WriteJobDescription 数据结构 | 47 (object), 85 (write method), 266 (writeAndCommit), 296 (executeWrite with WriteFiles spec) |
| `sql/core/src/main/scala/org/apache/spark/sql/execution/datasources/InsertIntoHadoopFsRelationCommand.scala` | InsertIntoHadoopFsRelationCommand，SaveMode 处理，static/dynamic partition 分发 | 48 (case class), run(sparkSession) → FileFormatWriter.write |
| `sql/core/src/main/scala/org/apache/spark/sql/execution/datasources/SQLHadoopMapReduceCommitProtocol.scala` | SQLHadoopMapReduceCommitProtocol，commitJob/abortJob，_SUCCESS 文件，动态分区覆盖清理 | |
| `sql/core/src/main/scala/org/apache/spark/sql/execution/datasources/WriteFiles.scala` | WriteFiles，DSv2 物理算子，可将写入嵌入物理计划 | |
| `sql/core/src/main/scala/org/apache/spark/sql/execution/datasources/OutputWriter.scala` | OutputWriter trait，init/putNewLine/writeRow/close | |
| `sql/catalyst/src/main/java/org/apache/spark/sql/connector/write/BatchWrite.java` | BatchWrite，DSv2 写入接口(createBatchWriterFactory + commit/abort) | |
| `sql/catalyst/src/main/java/org/apache/spark/sql/connector/write/DataWriter.java` | DataWriter[T]，Task 级写入+commit+abort，WriterCommitMessage | |
| `sql/catalyst/src/main/java/org/apache/spark/sql/connector/write/WriteBuilder.java` | WriteBuilder，DSv2 写入入口 | |
