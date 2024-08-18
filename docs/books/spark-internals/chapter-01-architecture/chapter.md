# 第 1 章：Spark 的架构基因 — RDD、DAG 与 Driver-Executor 模型

## 设计动机

2009 年，Matei Zaharia 在 UC Berkeley 的 AMPLab 面临一个问题：Hadoop MapReduce 可以处理 PB 级数据，但每次 MapReduce 操作后，中间结果必须写回 HDFS，下一个 Job 再从 HDFS 读取。这在迭代计算（K-means、PageRank、Logistic Regression）中导致 90% 的时间都花在 HDFS 读写上——而不是真正的计算。

Spark 的第一个洞察是：**内存中保留是值得付出的代价**。如果一个分布式程序可以把中间数据留在 Executor 的内存中（而不写回 HDFS），迭代计算就能加速 10-100×。这个简单的直觉定义了 Spark 的前 10 年——以及它从那之后的所有设计。

但"内存中保留"听起来简单，实则提出了一大串分布式系统问题：如果内存出问题了，谁来重新计算？如果节点故障了，已经有 3 个 partition 在内存中——第 4 个怎么办？什么触发计算、什么缓存、什么抛弃？这些问题的答案汇聚成了 Spark 的**核心架构基因**——RDD → DAGScheduler → TaskScheduler。

## 核心原理

### 1.1 RDD — 分布式的"可恢复数据集"

RDD（Resilient Distributed Dataset）是 Spark 的第一个也是最重要的抽象。它的定义很简洁：

```
RDD[T]:
  ├── partitions: Array[Partition]      ← 数据如何被分片
  ├── dependencies: Seq[Dependency]     ← 这个 RDD 从哪些父 RDD 推导出来
  ├── compute(partition, context): Iterator[T]  ← 如何计算一个分片的数据
  ├── partitioner: Option[Partitioner]  ← 数据是否按 key 分区（Hash/Range）
  └── preferredLocations(partition): Seq[String] ← 该分片的数据在哪个节点上
```

RDD 的关键特性是 **Lineage（血统）**——每个 RDD 知道它是从哪些父 RDD 通过什么操作生成的。如果 RDD 的某个 partition 丢失（节点故障、内存不足被驱逐），Spark 可以根据 lineage 重新计算该 partition——不需要全量重来，只需要沿着 dependency 回溯。

```
Lineage 图:
  RDD-A (HDFS file, 100 partitions)
    └── .map(x => x * 2) → RDD-B (100 partitions, NarrowDependency)
          └── .filter(x => x > 0) → RDD-C (90 partitions, NarrowDependency)
                └── .groupBy(x => x % 10) → RDD-D (10 partitions, WideDependency)

如果 RDD-D 的 partition 5 丢失:
  → 回溯 lineage: RDD-D.part5 ← RDD-C 的哪些 partition? → .compute()
  → WideDependency: 需要 RDD-C 的所有 partition → 重新 groupBy 到 partition 5
  → NarrowDependency: RDD-C 每个 partition 可以独立被重新计算
```

Lineage 解决了"在分布式环境中如何可靠地保留中间数据"的核心问题。内存不够可以驱逐 → 不永久丢失数据 → 需要时重新计算。不需要完整的检查点（checkpoint），不需要写回 HDFS。

### 1.2 Dependency — Narrow vs Wide 的根本区别

Spark 区分两种依赖关系，这是 Shuffle 和 Stage 分界的根基：

```
NarrowDependency:
  - 子 partition 只依赖父 partition 的一个子集
  - 类型: OneToOneDependency (map, filter), RangeDependency (union), PruneDependency
  - 可 pipeline: 同 Task 内连续执行 (不需要 Shuffle)
  
  Example: RDD-B = RDD-A.map(x => x * 2)
    partition_A[0] → partition_B[0]
    partition_A[1] → partition_B[1]
    ...

WideDependency (ShuffleDependency):
  - 子 partition 依赖父 partition 的所有（或过多数）
  - 类型: ShuffleDependency (groupByKey, reduceByKey, join)
  - 需要 Shuffle: 父数据必须按 key 重新分布到子 partition 的节点
  
  Example: RDD-B = RDD-A.groupByKey()
    partition_A[0] → (key % 10 distributes to B[0..9])
    partition_A[1] → (key % 10 distributes to B[0..9])
    ...
```

Narrow vs Wide 的区别不是一个实现细节——它决定了**物理计划的结构**。每个 Wide Dependency 引入一个 Stage 边界。每个 Stage 内部的所有 Narrow Dependency 可以 pipeline 到一起——作为一个连续的 Task 执行。

### 1.3 DAGScheduler — Stage 分界与 DAG 的拓扑执行

`DAGScheduler` 是 Spark 在 Driver 端的"任务计划器"。它的核心任务是：
1. 接收 RDD action（如 `.collect()`、`.count()`、`.saveAsTextFile()`）
2. 从这个 action 回溯 RDD 的 lineage → 构建 Stage DAG
3. 按拓扑顺序提交 Stage 给 `TaskScheduler`

```
DAGScheduler 的工作流程:
  Action: rdd-D.count()
  
  1. 回溯 lineage 构建 DAG:
     RDD-A.map → RDD-B.filter → RDD-C.groupBy → RDD-D → count
  
  2. 识别 Stage 边界:
     - groupBy 是 WideDependency → Stage 边界
     - map, filter 是 NarrowDependency → 同一 Stage 内 pipeline
     
     Stage-0: RDD-A.map → RDD-B.filter (无 Shuffle)
     Stage-1: RDD-C.groupBy (Shuffle Write side)
     Stage-2: RDD-D.count (Shuffle Read side + action)
  
  3. 提交执行:
     提交 Stage-0 → (Stage-0 的所有 Task 完成) → 提交 Stage-1
     → (Stage-1 完成) → 提交 Stage-2 → (完成) → Report result
  
  4. 容错:
     如果 Stage-0 的 Task-3 失败 → DAGScheduler 重新提交 Task-3
     如果 Stage-0 的 Task-3 连续失败 4 次 → 整个 Stage-0 标记为 failed
     → abort 依赖它的所有后续 Stage
```

DAGScheduler 处理 Shuffle 的 Map 端和 Reduce 端的分离——一个 Stage 的 **ShuffleMapTask** 写入 shuffle 文件 → 下一 Stage 的 **ResultTask** 从这些文件中读取。

### 1.4 TaskScheduler — Task 的物理分配与执行

`TaskScheduler` 处理 "把 Task 分配到 Executor 上" 的物理问题：

```
TaskScheduler 的职责:
  1. 接收 Stage 的 Task 集合 (从 DAGScheduler)
  2. 匹配 Task 的 preferredLocation → 分配 Executor
       - 数据本地性: PROCESS_LOCAL > NODE_LOCAL > RACK_LOCAL > ANY
       - 等待: 如果本地 Executor 忙 → 等待 spark.locality.wait 再推迟
  3. 序列化 Task → 通过网络发送到 Executor
  4. 监控 Task 状态 (running / success / failed)
  5. 处理失败: 重新提交 (最多 spark.task.maxFailures 次)
  6. 处理 Speculative Execution: 慢 Task 启动第二个副本
  7. 向 DAGScheduler 报告 Stage 完成
```

核心是 **数据本地性（Data Locality）**——将 Task 分配到拥有数据本地副本的 Executor 上。这减少了网络传输（对 HDFS 扫描）并使缓存读取（对 RDD cache）更快。

```
TaskScheduler 的调度策略:
  1. FIFO (默认): 按 Job 提交顺序依次执行
  2. FAIR:  多个 Job 公平共享 pool 资源 (通过 FairSchedulableBuilder 配置)
  3. Custom: 用户自定义
  
  FAIR 调度器的 pool 配置:
    <pool name="production">
      <schedulingMode>FAIR</schedulingMode>
      <weight>10</weight>               ← 权重: 分配更多资源
      <minShare>5</minShare>            ← 最少保证的 Task 并发数
    </pool>
    <pool name="ad_hoc">
      <schedulingMode>FAIR</schedulingMode>
      <weight>1</weight>
      <minShare>0</minShare>            ← 如果没有资源 → 零并发
    </pool>
```

### 1.5 Driver-Executor 模型 — 主从式的工作分配

```
Driver (SparkContext):           Executor (CoarseGrainedExecutorBackend):
───────────────                  ─────────────────────────────────
1. 解析 user code → DAG         │
2. DAGScheduler → Stages        │  3. 接收序列化的 Task
4. TaskScheduler → 分配 Task     │  5. 反序列化 Task
                                 │  6. 运行 Task (在 JVM thread pool 中)
                                 │  7. 将结果返回 Driver (或写 HDFS)
                                 │
8. 收集结果 → 返回用户           │
```

Executor 的路由是通过 RPC（第 2 章详细展开）。Driver 向 Executor 发送 `LaunchTask` 消息，Executor 执行并返回 `StatusUpdate`。

### 1.6 架构设计的核心取舍

Spark 的设计不是凭空产生的——它是在当年的"MapReduce 的处境"和对"未来计算模式"的愿景之间做的选择：

| 设计选择 | 替代方案 | 选择的理由 |
|---------|--------|----------|
| 内存保留 + 重新计算 | 检查点每次写磁盘 (MR) | 内存成本远低于 I/O 成本 (2009 年) |
| DAG 延迟求值 | Eager evaluation | 优化器可以全局 view 整个计算 DAG |
| Lineage 容错 | 完全不保留中间状态 | 重算比存盘快 (对 map/filter 等简单算子) |
| Driver-Executor 集中调度 | Peer-to-peer | 简化全局优化决策 |
| JVM 作为 Executor 运行时 | C++ (类似 ByteMQ/MR) | 快速迭代、大量库 (Java 生态) |

## 关键代码片段

### 示例：RDD Lineage 的追溯

```scala
// RDD.scala: getDependencies 为每个 RDD 子类定义 dependency
// NarrowDependency: 子 partition 的一个作业式映射到父 partition
class OneToOneDependency[T](rdd: RDD[T]) extends NarrowDependency[T](rdd) {
  override def getParents(partitionId: Int): List[Int] = List(partitionId)
  // partition i → parent partition i (1:1 映射)
}

// WideDependency: 每个子 partition 需要父 RDD 中所有的 partition
class ShuffleDependency[K, V, C](
    rdd: RDD[_ <: Product2[K, V]],
    partitioner: Partitioner) extends Dependency(rdd) {
  // 每个 Reducer partition 需要所有 Mapper partitions
}
```

### 示例：DAGScheduler 的 Stage 提交

```scala
// DAGScheduler: 处理 Job 提交
def handleJobSubmitted(jobId, finalRDD, func, partitions, ...) {
  // 1. 从 finalRDD 构建完整的 Stage DAG
  val finalStage = createResultStage(finalRDD, func, partitions, jobId, ...)
  
  // 2. 提交这个 Stage → 也提交它依赖的 parent Stages
  submitStage(finalStage)
}

def submitStage(stage: Stage) {
  if (!isWaitingOrRunningOrFailed(stage)) {
    val missing = getMissingParentStages(stage)
    if (missing.isEmpty) {
      submitMissingTasks(stage)  // 没有未完成的依赖 → 直接执行
    } else {
      for (parent <- missing) submitStage(parent)  // 先执行依赖
    }
  }
}
```

## 硬件视角

**JVM 进程模型下的 CPU 亲和性困境**：

Driver-Executor 模型中的每个 Executor 是一个独立的 JVM 进程。操作系统不保证 JVM 线程固定在同一个 CPU core 上——线程可能在 CPU-0 上运行一段，然后被调度到 CPU-31 上（L1/L2 cache 变冷）。对计算密集型 task，CPU 亲和性（pinning）的缺失可达 15-30% 的性能退化，因为 cache 在 core 之间迁移时完全失效。

在启用了 HugePages 的 K8s 集群中，使用 `taskset` 或 `sched_setaffinity` 将 Executor 线程固定到 core 4-7（一个 4-core complex）上可能提高 10-25% 的吞吐——但这很少在生产中配置。Native Engine（第 28 章）会将这个问题部分解决，因为 C++ 线程可以在 Velox internal 中管理自己的 CPU 绑定。

**数据本地性的极限**：

数据本地性在 HDFS（3 副本分布在 3 个物理节点上）上是有价值的——优先调度到有副本的节点。但在 S3 这样的对象存储中，没有"数据位置"的概念（S3 的抽象隐藏了物理位置）——所有 Task 的数据本地性都是 `ANY`。这意味着 S3 环境中的 `spark.locality.wait` 应设为 0——否则 Task 白白等待一个永远不会出现的本地 Executor。

## AI 时代反思

RDD 的 lineage 概念和 DAG 的拓扑执行是 Spark 的"基因"——但从 2026 年的 AI 时代目光回头看，这个基因有一个很有趣的特质：**它是为"人类理解数据流"而设计的，不是为"AI 理解数据流"**。

人对数据流的理解是顺序的——写一个 RDD chain → 读 lineage 的追溯顺序。AI Agent 对数据流的理解是图状的——它把整个 DAG 看作一个图（类似 neural network 的 computation graph），然后做全局优化、节点融合、并行化决策。

这意味着**Spark 的未来方向不是让 AI 适应 Lineage，而是让 Lineage 暴露为 AI 可以理解的形式**。具体来说：
- 从 RDD lineage 构建一个 protobuf `Plan` 消息（Spark Connect 已经在做）
- AI Agent 读取 proto plan → 做全局优化（类似 TensorFlow 的 Grappler） → 将优化后的 plan 发回 Driver
- Driver 执行这个 AI-optimized plan，而非默认的 lineage-based plan

这种编排分离可能让 Spark 在 2030 年代获得一种全新的"AI 感知优化"——不是基于 CBO 的成本模型（第 10 章），而是基于 AI 的全局图推理。但这是后 Spark 5.0 的议题。

## 源码导航

| 文件 | 关键内容 | 行号参考 |
|------|---------|---------|
| `core/src/main/scala/org/apache/spark/rdd/RDD.scala` | RDD 基础抽象，partitions, dependencies, compute, getDependencies, iterator, checkpoint | ~23 (abstract class RDD) |
| `core/src/main/scala/org/apache/spark/Dependency.scala` | Dependency, NarrowDependency (OneToOneDep, RangeDep, PruneDep), ShuffleDependency | ~24 (abstract class Dependency) |
| `core/src/main/scala/org/apache/spark/scheduler/DAGScheduler.scala` | DAGScheduler, handleJobSubmitted, submitStage, createResultStage, getMissingParentStages, handleTaskCompletion | |
| `core/src/main/scala/org/apache/spark/scheduler/TaskScheduler.scala` | TaskScheduler trait, TaskSchedulerImpl (default), scheduling mode (FIFO/FAIR) | |
| `core/src/main/scala/org/apache/spark/SparkContext.scala` | SparkContext, DAGScheduler + TaskScheduler 创建, runJob 入口 | |
| `core/src/main/scala/org/apache/spark/executor/Executor.scala` | Executor, TaskRunner, launchTask 消息处理 | |
| `core/src/main/scala/org/apache/spark/scheduler/TaskSetManager.scala` | TaskSetManager, 数据本地性延迟, speculative execution | |
| `core/src/main/scala/org/apache/spark/Partition.scala` | Partition trait | ~24 (trait Partition) |
| `core/src/main/scala/org/apache/spark/Partitioner.scala` | Partitioner, HashPartitioner, RangePartitioner | |
