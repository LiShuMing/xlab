# 第 17 章：Adaptive Query Execution — 运行时自适应的查询执行

## 设计动机

传统的查询优化是一次性的——在查询执行之前，优化器根据统计信息选出一个"最优"的物理计划，然后完整执行。这个模型在两种情况下崩溃：

1. **统计信息缺失或过时**：生产环境中大量表没有运行 ANALYZE，或者统计信息在最后一次 ANALYZE 后已过时。没有准确的统计信息，CBO 无法做出正确决策。

2. **中间结果的不可预测性**：即初始统计信息准确，多表 Join + 过滤后的中间结果大小也很难预测——8 次独立过滤的累计误差可能达到几个数量级。

Adaptive Query Execution（AQE）用一个根本不同的范式来解决这个问题：**先部分执行，收集真实数据统计，再优化剩余部分，然后继续执行**。它不是"预测→执行"，而是"执行→观察→优化→再执行"。

```
传统查询执行:
  Plan → Execute(全部)

AQE 查询执行:
  Plan → Execute(Stage 1) → Observe(Stats) → Re-optimize(Stage 2+) → Execute(Stage 2) → ...
```

AQE 把物理计划切分成多个 **Query Stage**——以 Exchange（Shuffle/Broadcast）为边界。每个 Stage 物化后，Spark 测量它的实际输出大小和行数。这些"运行时统计信息"（isRuntime = true）比任何预估算都准确，因为它们来自真实数据。

```
物理计划中的 Stage 分割:
  Stage 0: Scan → Filter → HashAggregate(Partial) → ShuffleWrite  ← ShuffleQueryStage
  Stage 1: ShuffleRead → HashAggregate(Final) → BroadcastHashJoin → ...
  ↑ 此时已知 Stage 0 Shuffle 输出的实际 partition 大小和行数
```

本章聚焦 AQE 的三个核心优化：**动态 Join 策略切换**、**Shuffle Partition 合并**、**倾斜 Join 处理**——以及 AQE 的框架架构（Stage 的生命周期）和它的局限性（与 Streaming 的根本冲突）。

## 核心原理

### 17.1 AdaptiveSparkPlanExec — AQE 的执行框架

AQE 的入口是 `AdaptiveSparkPlanExec`，它是一个包装了整个物理计划的叶子节点：

```scala
// AdaptiveSparkPlanExec.scala:69
case class AdaptiveSparkPlanExec(
    inputPlan: SparkPlan,
    @transient context: AdaptiveExecutionContext,
    @transient preprocessingRules: Seq[Rule[SparkPlan]],
    @transient isSubquery: Boolean) extends LeafExecNode
```

它是通过 `InsertAdaptiveSparkPlan` 规则在 Preparation 阶段插入的——替换原来的顶层物理计划：

```
物理计划 → InsertAdaptiveSparkPlan → AdaptiveSparkPlanExec(原始计划)
```

**执行流程**：

```
1. 应用 queryStagePreparationRules → 确保所有的 Shuffle/Sort 等已到位
2. 创建 Query Stages (以 Exchange 为边界, 自底向上):
   - 遇到 Exchange 节点 → 创建相应的 QueryStageExec
   - Broadcast 侧 → BroadcastQueryStageExec (异步 broadcast job)
   - Shuffle 侧 → ShuffleQueryStageExec (等待上游 Stage 完成)
3. 启动所有 Stage 的物化 (异步), Broadcast 优先
4. 等待 Stage 完成:
   - 收集真实统计信息 (map output sizes)
   - Re-optimize 逻辑计划 (AQEOptimizer)
   - Re-plan 物理计划
   - 比较新旧计划的代价 (costEvaluator)
   - 如果新计划代价更低 → 采用新计划
5. 创建更多 Stages (回到步骤 2)
6. 所有 Stages 完成后 → 执行 final plan
```

```scala
// AdaptiveSparkPlanExec.scala:282
while (!result.allChildStagesMaterialized) {
  currentPhysicalPlan = result.newPlan
  // 启动所有新 Stage 的物化 (异步)
  reorderedNewStages.foreach { stage =>
    stage.materialize().onComplete { res =>
      if (res.isSuccess) events.offer(StageSuccess(stage, res.get))
      else events.offer(StageFailure(stage, res.failed.get))
    }(AdaptiveSparkPlanExec.executionContext)
  }
  // 等待下一个 Stage 完成
  val nextMsg = events.take()
  // 用新统计信息 Re-optimize + Re-plan
  if (!currentPhysicalPlan.isInstanceOf[ResultQueryStageExec]) {
    val afterReOptimize = reOptimize(logicalPlan)
    if (afterReOptimize.isDefined) {
      val (newPhysicalPlan, _) = afterReOptimize.get
      if (newCost < origCost) {
        currentPhysicalPlan = newPhysicalPlan  // 采用新计划
      }
    }
  }
  // 继续创建 Stages
  result = createQueryStages(fun, currentPhysicalPlan, firstRun = false)
}
```

**代价比较器**（costEvaluator）：

```scala
// 默认使用 SimpleCostEvaluator:
val newCost = costEvaluator.evaluateCost(newPhysicalPlan)
val origCost = costEvaluator.evaluateCost(currentPhysicalPlan)
if (newCost < origCost || (newCost == origCost && currentPhysicalPlan != newPhysicalPlan)) {
  // 采用新计划。当代价相等但计划不同时也采用新计划,
  // 因为新计划可能在其他方面更优 (e.g., 使用运行时统计信息)
  currentPhysicalPlan = newPhysicalPlan
}
```

### 17.2 QueryStage — Stage 的物化与统计收集

`QueryStageExec` 是 AQE 中 Stage 的抽象：

```
QueryStageExec
  ├── ShuffleQueryStageExec: 对应 ShuffleExchangeExec (物化为 map output statistics)
  ├── BroadcastQueryStageExec: 对应 BroadcastExchangeExec (物化为 broadcast variable)
  └── ResultQueryStageExec: 最终结果 Stage
```

每个 Stage 物化后将统计信息传入系统：

```scala
// ShuffleQueryStageExec 物化完成后:
// → MapOutputStatistics (各 partition 的大小)
// → 用于 CoalesceShufflePartitions (合并小 partition)
// → 用于 OptimizeSkewedJoin (检测倾斜 partition)
```

Broadcast 的物化优先级更高——BroadcastQueryStage 先提交，因为它可能决定下游 Join 是否能用 BHJ：

```scala
// AdaptiveSparkPlanExec.scala:293
// Broadcast stages 先行:
val reorderedNewStages = result.newStages.sortWith {
  case (_: BroadcastQueryStageExec, _: BroadcastQueryStageExec) => false
  case (_: BroadcastQueryStageExec, _) => true
  case _ => false
}
```

### 17.3 动态 Join 策略切换 — SMJ → BHJ

AQE 最关键的能力是**运行时切换 Join 算法**。最常见的场景是：编译时一张表超过 `broadcastThreshold`（默认 10MB），选择 SMJ。但执行时上游过滤后实际只有 5MB——此时应切换为 BHJ。

这个决策发生在 Re-Optimize 阶段。当 BroadcastQueryStage 物化完成后，实际的 broadcast 大小（`broadcast.sizeInBytes`）被传回优化器。Re-Optimize 期间，`JoinSelection` 重新运行——这次使用运行时统计信息——如果 build 侧 ≤ broadcastThreshold，选择 BHJ：

```
Timeline:
  t0: 编译时 → 选择 SMJ (表 A 在 Catalog 中是 100MB, 超过 10MB 广播阈值)
  t1: Stage 0 执行 (Scan → Filter → Partial Agg) → 实际 Shuffle 输出 = 2GB
  t2: Stage 1 执行 (Scan B → Filter) → 实际 B 侧 Builder = 5MB
  t3: AQE Re-Optimize → 5MB ≤ 10MB → 切换为 BHJ (不再做 SMJ)
  t4: 广播 B 的 HashedRelation 到所有 executor
  t5: 执行 BHJ
```

同样，符合条件时也可以 SMJ → SHJ 切换：

```
编译时: enableTwoLevelAggMap → preferSortMergeJoin=true → SMJ
运行时: build 侧 < buildSideThreshold → 切换 SHJ
```

动态切换的重要性：BHJ 的广播网络开销是 O(build × executors)，但 probe 速度极快（O(build) hash table lookup）。SMJ 需要两侧 Shuffle + Sort，I/O 开销大得多。从 SMJ 切换到 BHJ 在 TPC-DS 的某些查询中可以节省 30-60% 的执行时间。

### 17.4 CoalesceShufflePartitions — 合并小 Shuffle Partition

这是 AQE 中最简单也最有效的优化——减少 reduce task 数量。

**问题**：Spark 默认的 `spark.sql.shuffle.partitions = 200`。对于 10TB 的 Shuffle，200 个 partition 意味着每个 task 处理 50GB——太大。对于 10MB 的 Shuffle，200 个 partition 意味着每个 task 处理 50KB——太小，task 启动开销占主导。

**解决方案**：AQE 知道每个 Shuffle Map Stage 输出的**实际 partition 大小**（从 `MapOutputStatistics` 获取）。`CoalesceShufflePartitions` 规则将这些 partition 合并为"目标大小"的 partition：

```scala
// CoalesceShufflePartitions.scala:34
case class CoalesceShufflePartitions(session: SparkSession) extends AQEShuffleReadRule {
  override val supportedShuffleOrigins: Seq[ShuffleOrigin] =
    Seq(ENSURE_REQUIREMENTS, REPARTITION_BY_COL, REBALANCE_PARTITIONS_BY_NONE,
      REBALANCE_PARTITIONS_BY_COL)

  // 不合并 SinglePartition（单 partition 已经是最优）
  // 不合并用户显式指定 REPARTITION 的 Shuffle
}
```

**合并逻辑**：

```
输入: 5 个 shuffle partitions 的大小 = [1MB, 2MB, 3MB, 50MB, 4MB]
目标大小: 64MB (ADVISORY_PARTITION_SIZE_IN_BYTES)

输出: 3 个 coalesced partitions:
  Partition 0: [0+1+2] = 1+2+3 = 6MB
  Partition 1: [3] = 50MB (单独, because 50+4=54 < 64*1.2=76.8, 但 50+4+later=...)
  Partition 2: [4] = 4MB
```

合并参数由三个配置控制：
- `ADVISORY_PARTITION_SIZE_IN_BYTES`（默认 64MB）：目标 partition 大小
- `COALESCE_PARTITIONS_MIN_PARTITION_SIZE`（默认 1MB）：最小 partition 大小
- `COALESCE_PARTITIONS_PARALLELISM_FIRST`（默认 true）：优先保证并行度（不合并到少于默认并行度）

如果 `COALESCE_PARTITIONS_PARALLELISM_FIRST=true` 且默认并行度 = 200，则即使所有 partition 合并后只有 2 个 64MB 的 partition，也会保留至少 200 个 partition（向 200 个 task 的目标分布数据）。

**独立的合并组**：

Union、CartesianProduct、BHJ、BNLJ 下的子计划可以独立合并：

```scala
// Union 两侧的 Shuffle 不应合并在一起
val coalesceGroups = collectCoalesceGroups(plan)
// 每个 coalesceGroup 内独立计算合并策略
```

### 17.5 OptimizeSkewedJoin — 倾斜 Join 的拆分

Hash Join 对数据倾斜最敏感——如果某个 Join Key 占数据的 50%，负责该 Key 的 task 会处理其余 task 的 100 倍数据量，成为拖后腿的 straggler。

```scala
// OptimizeSkewedJoin.scala:57
case class OptimizeSkewedJoin(ensureRequirements: EnsureRequirements) extends Rule[SparkPlan] {
  def getSkewThreshold(medianSize: Long): Long = {
    conf.getConf(SQLConf.SKEW_JOIN_SKEWED_PARTITION_THRESHOLD)
      .max((medianSize * conf.getConf(SQLConf.SKEW_JOIN_SKEWED_PARTITION_FACTOR)).toLong)
  }
}
```

倾斜判断：一个 partition 的大小 > `skewPartitionFactor` × 中位 partition 大小，且 > `skewPartitionThreshold`。

**拆分算法**（以 SMJ 为例）：

```
原始:
  left partitions:  [L1=10MB, L2=500MB(skew), L3=10MB, L4=8MB]
  right partitions: [R1=10MB, R2=400MB(skew), R3=12MB, R4=7MB]

AQE 拆分后 9 个 tasks:
  Task 0: (L1, R1)       ← 正常
  Task 1: (L2-1, R2-1)   ← L2 拆 2, R2 拆 2 = 4 tasks (笛卡尔积!)
  Task 2: (L2-2, R2-1)
  Task 3: (L2-1, R2-2)
  Task 4: (L2-2, R2-2)
  Task 5: (L3, R3)       ← 正常
  Task 6: (L4, R4)       ← 正常
  注意 L2-1 和 L2-2 各自读取 R2-1 和 R2-2
```

两侧倾斜 → 笛卡尔积式复制。单侧倾斜 → 只在非倾斜侧复制：

```
如果只有 L2 倾斜:
  Task 1: (L2-1, R2.copy)   ← R2 完整复制
  Task 2: (L2-2, R2.copy)   ← R2 完整复制
```

对 BHJ 也支持倾斜优化。在这种情况下：
- Build 侧已经广播到所有 Executor，没有 Shuffle partition
- Stream 侧的倾斜通过将倾斜 key 的行拆分到多个 task，每个 task 读取完整的 Build 侧 Hash Table

对于 SHJ，倾斜优化同样适用——本质上与 SMJ 相同（先将 build 侧 Shuffle，然后按 partition 检测倾斜）。

### 17.6 OptimizeShuffleWithLocalRead — 本地优先读取

当 CoalesceShufflePartitions 将多个 mapper 的 partition 合并到一个 reducer task 时，正常流程是：
1. reducer 通过 ShuffleRead 从远程/本地拉取所有 mapper 的对应 partition

但通过 `OptimizeShuffleWithLocalRead`，如果所有合并的 partition 都与 reducer 在同一个节点上（例如 mapper 和 reducer 被调度到同一节点），可以完全绕过网络——直接本地读取：

```scala
// 如果数据在本地 → 使用 LocalShuffleReader 代替远程 BlockStoreShuffleReader
// → 避免网络 fetch 的反序列化开销
// → 类似"Hadoop MapReduce 中的 map output compression + local fetch"
```

### 17.7 AQE 的 Re-Optimize 与 Re-Plan

AQE 引入了一个"中间的" Optimizer 阶段——`AQEOptimizer`：

```
AdaptiveSparkPlanExec.withFinalPlanUpdate:
  1. 收集 Stage 统计
  2. replaceWithQueryStagesInLogicalPlan: 将物化的 Shuffle/Broadcast nodes 替换为 LogicalQueryStage
  3. reOptimize: 运行 AQEOptimizer (包含 CBO JoinReordering + 标准规则)
  4. rePlan: 运行 Planner 生成新 SparkPlan
  5. 代价比较 → 决定是否采用新计划
```

`AQEOptimizer` 与标准 Optimizer 的关键区别：它**包含** CBO Join Reorder。因为在编译阶段 CBO 可能因为缺少统计信息而退化为 RBO——而 AQE 有运行时统计信息，可以真正发挥 CBO 的作用。

## 关键代码片段

### 示例：AQE 的 Stage 分割

```
SELECT o.order_id, c.name
FROM orders o JOIN customers c ON o.cust_id = c.id
WHERE o.amount > 10000

编译时物理计划 (AQE enabled):
AdaptiveSparkPlanExec
+- SortMergeJoinExec [cust_id], [id]
   +- SortExec [cust_id]
      +- ShuffleExchangeExec(HashPartitioning(cust_id))
         +- FilterExec(amount > 10000)
            +- FileScan orders [order_id, cust_id, amount]
   +- SortExec [id]
      +- ShuffleExchangeExec(HashPartitioning(id))
         +- FileScan customers [id, name]

AQE 将这个计划切分为:
  Stage 0 (ShuffleQueryStage): Scan orders → Filter → ShuffleWrite
  Stage 1 (ShuffleQueryStage): Scan customers → ShuffleWrite
  Stage 2 (ResultQueryStage): ShuffleRead(orders, coalesced) + ShuffleRead(customers, coalesced) → SMJ/BHJ

如果 Stage 1 完成后 customers Shuffle 输出 < 10MB:
  → Re-optimize → 切换为 BHJ
  → Stage 2 变为: BroadcastHashJoin(ShuffleRead(orders, coalesced), broadcast(customers))
```

## 硬件视角

**AQE 的统计收集开销**：

每个 ShuffleQueryStage 需要写入 Shuffle Write，然后通过 `MapOutputTracker` 收集 partition 大小。这引入了额外的元数据开销——但可以忽略，因为：
- partition 大小从 Shuffle Write 的 `ShuffleWriteMetrics` 中直接获取（不需要额外扫描数据）
- `MapOutputTracker` 更新是异步的——不阻塞 Stage 完成

**AQE 的网络效应**：

| 优化 | 网络影响 | 典型收益 |
|------|---------|---------|
| SMJ → BHJ | +1 broadcast (小表复制) / -1 Shuffle (大表不需要 shuffle) | 减少一个 Shuffle 的写+读开销 |
| CoalesceShufflePartitions | 减少 reduce task 数量 → 减少 connection overhead | task launch 从 2000 → 20，节省 5-10 秒调度开销 |
| OptimizeSkewedJoin | +增加 network（倾斜 key 行需要复制） / 但消除 straggler | straggler 从 50× slower → 正常 |

倾斜 Join 的拆分本质上是 **用额外的网络传输换取 CPU 并行度**——将倾斜 partition 的几行复制到多台机器（额外带宽消耗 < 1% 的倾斜 partition），但这些行可以在 4 个 CPU core 上并行处理而不是 1 个。

**CoalesceShufflePartitions 的 disk I/O 效应**：

合并小 partition 后，每个 reduce task 处理的数据更多，disk 读取的顺序性和大小都改善：
- 合并前：200 个 tasks 各自读取 500KB → 小型随机 I/O，IOPS 绑定的
- 合并后：20 个 tasks 各自读取 5MB → 中等顺序 I/O，带宽绑定的

这减少了对 NVMe 的 IOPS 需求（从 ~200 QD 降到 ~20 QD）。

## AI 时代反思

AQE 有一件有意思的事和 LLM Agent 的思考模式相同，那就是 **"计划→执行→观察→再计划（Plan→Execute→Observe→Replan）"**。

一个 LLM Agent 处理复杂查询的模式：

```
User: "找出上季度销售额最高的前 10 个产品分类"
Agent:
  Step 1: Execute SQL → 发现结果包含了已停产的产品
  Step 2: Re-plan → 添加过滤条件 WHERE status != 'discontinued'
  Step 3: Execute → 结果正确
```

这和 AQE 的模式完全对应："先跑 Stage 1，看看实际数据是多大，再决定 Stage 2 用什么算法"。

那么，AQE 的下一步可以用 LLM Agent 的方式来思考吗？当前的 AQE 是一个"反应式（reactive）"系统——它等待数据出现，然后做决策。LLM Agent 的更进一步是 **"预测式执行（speculative execution）"**——Agent 在看到完整数据之前可以"猜测"最可能的 2-3 种结果，然后并行准备多个后续计划，最终选择匹配的那个。

这在数据库场景中是可以想象的：如果 Stage 0 的统计信息显示 3 种可能的 build 侧大小（5MB, 80MB, 200MB），Agent 可以在 Stage 0 物化期间提前启动：
- broadcast job（如果最终是 BHJ）→ pre-warm
- sort + shuffle（如果最终是 SMJ）→ pre-warm

这与 LLM 的 "speculative decoding" 类似——一次输出多个 token 候选，再在中间选择一个。

但挑战是数据库的"副作用"——启动一个 broadcast job 会消耗网络带宽和 executor 内存，如果不能确定会用上，这些资源就被浪费了。这需要一个代价模型来决定"是否值得 speculate"——而 LLM 在这里可以提供的是：**不只是基于数字做决策，还可以基于历史查询模式（"这个 WHERE 条件在过往类似查询中过滤掉的 95% 以上"）做预测**。

## 源码导航

| 文件 | 关键内容 | 行号参考 |
|------|---------|---------|
| `sql/core/src/main/scala/org/apache/spark/sql/execution/adaptive/AdaptiveSparkPlanExec.scala` | AdaptiveSparkPlanExec，AQE 主循环(createQueryStages → materialize → reOptimize)，costEvaluator 代价比较，Broadcast 优先调度 | 69 (case class), 93 (requiredDistribution), 137 (queryStageOptimizerRules), 282 (withFinalPlanUpdate 主循环), 343 (re-optimize + cost comparison) |
| `sql/core/src/main/scala/org/apache/spark/sql/execution/adaptive/CoalesceShufflePartitions.scala` | CoalesceShufflePartitions 规则，合并组分割，目标大小计算 | 34 (case class), 46 (apply), 74 (coalesceGroups) |
| `sql/core/src/main/scala/org/apache/spark/sql/execution/adaptive/OptimizeSkewedJoin.scala` | OptimizeSkewedJoin 规则，倾斜检测阈值，拆分算法 | 57 (case class), 65 (getSkewThreshold), 75 (targetSize) |
| `sql/core/src/main/scala/org/apache/spark/sql/execution/adaptive/OptimizeShuffleWithLocalRead.scala` | OptimizeShuffleWithLocalRead，本地读优化 | |
| `sql/core/src/main/scala/org/apache/spark/sql/execution/adaptive/InsertAdaptiveSparkPlan.scala` | InsertAdaptiveSparkPlan，在 Preparation 阶段插入 AQE 根节点 | |
| `sql/core/src/main/scala/org/apache/spark/sql/execution/adaptive/QueryStageExec.scala` | QueryStageExec 及子类实现（ShuffleQueryStageExec, BroadcastQueryStageExec, ResultQueryStageExec） | |
| `sql/core/src/main/scala/org/apache/spark/sql/execution/adaptive/AdaptiveRulesHolder.scala` | AQE 规则扩展点（runtimeOptimizerRules, queryStagePrepRules, queryStageOptimizerRules） | |
