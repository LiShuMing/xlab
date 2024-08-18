# 第 11 章：Physical Planning — 从逻辑计划到可执行计划

## 设计动机

Logical Optimization 产出的是最优的 **Logical Plan**——但它仍然是一个"抽象"的计划。`Join` 是一个 LogicalPlan 节点，但它不能被执行——它不知道是应该用 Broadcast Hash Join 还是 Sort Merge Join，不知道数据应该如何在节点间分布，也不知道哪些列需要 Shuffle。

Physical Planning 的职责就是将 Logical Plan 转换为 **SparkPlan**——一个可以被执行的物理计划树。这涉及三个核心任务：

1. **Strategy 选择**：为每个逻辑算子选择物理执行策略（例如 Join → BHJ/SMJ/SHJ）
2. **Distribution 保证**：在需要的地方插入 Shuffle（Exchange）算子以满足数据分布要求
3. **Preparation**：在最终执行前对物理计划进行清理和微调

如果说 Logical Optimization 问的是"什么计划更小？"，Physical Planning 问的是"**这个计划怎么执行？**"

Catalyst 中 Physical Planning 的设计是最"不典型"的部分——它不是 Rule-based（Analyzer, Optimizer 都是 RuleExecutor），而是 **Strategy-based**。这是两种不同的抽象：

- **Rule-based**：遍历树，匹配 pattern，做变换（transform）
- **Strategy-based**：匹配逻辑节点，生成零个或多个物理计划候选

通常 Strategy 只返回一个候选（因为 Spark 的代价模型在 Physical Planning 阶段比较粗），但 `QueryPlanner` 的设计允许返回多个候选——未来如果有更精细的物理代价模型，可以从多个候选中选择最优。

## 核心原理

### 11.1 QueryPlanner 与 Strategy 体系

Physical Planning 的入口是 `QueryPlanner[PhysicalPlan]`，它使用 `Strategy` 将 LogicalPlan 转换为 SparkPlan：

```scala
// sql/catalyst/src/main/scala/org/apache/spark/sql/catalyst/planning/QueryPlanner.scala
abstract class QueryPlanner[PhysicalPlan <: TreeNode[PhysicalPlan]] {
  /** A sequence of strategies for planning. */
  def strategies: Seq[GenericStrategy[PhysicalPlan]]

  def plan(plan: LogicalPlan): Iterator[PhysicalPlan] = {
    // 对每个 logical plan 节点，依次尝试每个 strategy
    val iter = strategies.view.flatMap(_(plan)).toIterator
    assert(iter.hasNext, s"No plan for $plan")
    iter
  }
}
```

`plan` 方法对 LogicalPlan 根节点调用每个 Strategy，返回第一个匹配的物理计划。Spark 默认使用 `SparkStrategies`：

```scala
// SparkStrategies.scala:75
abstract class SparkStrategies extends QueryPlanner[SparkPlan] {
  override def plan(plan: LogicalPlan): Iterator[SparkPlan] = {
    super.plan(plan).map { p =>
      p.setLogicalLink(plan)  // 在物理节点上打上"来源逻辑节点"的标记
      p
    }
  }
}
```

**PlanLater 与延迟规划**（Lazy Planning）：

Strategy 使用 `planLater` 处理子节点——不是立即规划，而是创建一个 `PlanLater` placeholder：

```scala
// SparkStrategies.scala:61
abstract class SparkStrategy extends GenericStrategy[SparkPlan] {
  override protected def planLater(plan: LogicalPlan): SparkPlan = PlanLater(plan)
}

case class PlanLater(plan: LogicalPlan) extends LeafExecNode {
  override def output: Seq[Attribute] = plan.output
  protected override def doExecute(): RDD[InternalRow] =
    throw SparkUnsupportedOperationException()  // 永远不应该被执行
}
```

`PlanLater` 是一个未解决的 placeholder。它的规划在 `QueryPlanner.plan` 中完成——规划器递归地将每个 PlanLater 替换为实际的物理计划（再从 Strategy 列表中选择）。

这个设计的妙处在于 **自上而下的决策 + 自下而上的组装**：
1. Top-down：Strategy 决定"Join 用什么物理算法"——这是全局决策
2. Bottom-up：子节点用 `planLater` 占位，后续被自动填充——这是局部填充

### 11.2 SparkPlan — 物理计划基类

`SparkPlan` 继承 `QueryPlan[SparkPlan]`，是可序列化的物理执行单元：

```scala
// SparkPlan.scala:65
abstract class SparkPlan extends QueryPlan[SparkPlan] with Logging with Serializable {
  val id: Int = SparkPlan.newPlanId()  // 单调递增的全局唯一 ID

  def output: Seq[Attribute]

  // 执行入口——所有 SparkPlan 实现必须实现的抽象方法
  protected def doExecute(): RDD[InternalRow]
  final def execute(): RDD[InternalRow] = executeQuery { doExecute() }

  // 列式执行（可选）
  def supportsColumnar: Boolean = false
  protected def doExecuteColumnar(): RDD[ColumnarBatch] = ...
  final def executeColumnar(): RDD[ColumnarBatch] = ...

  // Broadcast 执行（用于 Broadcast Hash Join）
  protected def doExecuteBroadcast[T](): broadcast.Broadcast[T] = ...
  final def executeBroadcast[T](): broadcast.Broadcast[T] = ...

  // 数据分布属性（在 Preparation 阶段才被正确设置）
  def outputPartitioning: Partitioning = UnknownPartitioning(0)

  // 子节点的数据分布需求
  def requiredChildDistribution: Seq[Distribution] = Seq.fill(children.size)(UnspecifiedDistribution)
  def requiredChildOrdering: Seq[Seq[SortOrder]] = Seq.fill(children.size)(Nil)
}
```

`doExecute()` 是核心契约——它将一个物理算子实现为一个 RDD 变换。例如 `ProjectExec` 的 `doExecute()` 产生 `child.execute().mapPartitions(iter => ...)` 的 RDD 变换链。

`requiredChildDistribution` 和 `requiredChildOrdering` 是 **声明式约束**——它们不直接改变计划，而是告诉 `EnsureRequirements` preparation 规则："这个算子要求左子按 `a, b` 聚类（Hash 分区）"。

### 11.3 关键 Strategy 的选择逻辑

#### JoinSelection — 最复杂的 Strategy

JoinSelection 是物理规划中最复杂的 Strategy，因为需要在 5 种 Join 算法中选择效率最高的一种：

**Equi-Join 的决策树**（有等值连接条件）：

1. **Broadcast Hash Join (BHJ)**：如果一侧 ≤ `broadcastThreshold`（默认 10MB），选择广播
2. **Shuffle Hash Join (SHJ)**：如果一侧 ≤ `buildSideThreshold` 且远小于另一侧，且 `preferSortMergeJoin=false`
3. **Sort Merge Join (SMJ)**：Join 键可排序 → 默认回退方案
4. **Cartesian Product**：Inner Join 无等值条件
5. **Broadcast Nested Loop Join (BNLJ)**：最终的兜底方案

**Non-Equi-Join 的决策树**（如 `ON t1.a > t2.b`）：

1. **Broadcast Nested Loop Join**：一侧 ≤ broadcastThreshold
2. **Cartesian Product**：Inner Join
3. **Broadcast Nested Loop Join**：无论如何都要执行

```scala
// SparkStrategies.scala:181
object JoinSelection extends Strategy with JoinSelectionHelper {
  // 1. 先检查 Join Hint
  // 2. 没有 Hint 时按大小阈值判断
  def createJoinWithoutHint() = {
    createBroadcastHashJoin(false)        // broadcast threshold check
      .orElse(createShuffleHashJoin(false)) // build side size check
      .orElse(createSortMergeJoin())        // fallback: SMJ
      .orElse(createCartesianProduct())     // inner join fallback
      .getOrElse {
        // 最后的兜底：BNLJ，可能 OOM
        Seq(joins.BroadcastNestedLoopJoinExec(...))
      }
  }
}
```

Join Hint 的处理优先级更高：`BROADCAST` → `SHUFFLE_MERGE` → `SHUFFLE_HASH` → `SHUFFLE_REPLICATE_NL`。

**为什么 SMJ 是默认回退而不是 SHJ？** SHJ 需要在内存中构建完整的 Hash Table——如果 build 侧很大，可能 OOM。SMJ 是 **外部排序**（External Sort），溢写到磁盘。所以 SMJ 是更安全的默认选择（用 `spark.sql.join.preferSortMergeJoin` 控制）。

#### Aggregation — 聚合的实现选择

```scala
// SparkStrategies.scala:584
object Aggregation extends Strategy {
  def apply(plan: LogicalPlan): Seq[SparkPlan] = plan match {
    case PhysicalAggregation(groupingExpressions, aggExpressions, resultExpressions, child) =>
      if (functionsWithDistinct.isEmpty) {
        // 无 DISTINCT: HashAggregate(sort=false)
        AggUtils.planAggregateWithoutDistinct(...)
      } else {
        // 有 COUNT(DISTINCT): 两阶段聚合（已在 RewriteDistinctAggregates 中展开）
        AggUtils.planAggregateWithOneDistinct(...)
      }
  }
}
```

对于 Python UDAF，Spark 生成 `ArrowAggregatePythonExec`，通过 Arrow 协议将数据从 JVM 传输到 Python 进程执行。

#### BasicOperators — 简单的一对一映射

对大部分简单的 LogicalPlan 节点，物理映射是一对一的：

| Logical Plan | Physical Plan |
|-------------|---------------|
| `Project` | `ProjectExec` |
| `Filter` | `FilterExec` |
| `Sort` | `SortExec` |
| `Union` | `UnionExec` |
| `LocalLimit` | `LocalLimitExec` |
| `Repartition` | `ShuffleExchangeExec` or `CoalesceExec` |
| `OneRowRelation` | `OneRowRelationExec` |
| `Range` | `RangeExec` |
| `Generate` | `GenerateExec` |

`BasicOperators` 也包含了 **安全性检查**——如果某些 LogicalPlan 节点出现在物理规划阶段但不应该出现（如 `Distinct`，它应该在 Optimizer 中被 `ReplaceDistinctWithAggregate` 改写），则抛出 Internal Error。

### 11.4 Distribution 与 Partitioning 类型体系

Physical Planning 中定义了两套相关的类型体系：

**Distribution**（数据分布需求——"我想要什么方式分布数据"）：

```scala
// partitioning.scala:39
sealed trait Distribution
case object UnspecifiedDistribution extends Distribution     // 无要求
case object AllTuples extends Distribution                   // 所有数据在一个分区
case class ClusteredDistribution(clustering: Seq[Expression], numPartitions: Int)
    extends Distribution                                      // 按表达式 Hash 分区
case class StatefulOpClusteredDistribution(...) extends Distribution  // 有状态算子分区
case class OrderedDistribution(ordering: Seq[SortOrder]) extends Distribution  // 按序分区
case class BroadcastDistribution(mode: BroadcastMode) extends Distribution    // 广播
```

**Partitioning**（数据分区方式——"实际数据是如何分布在各分区上的"）：

```scala
// partitioning.scala:250
sealed trait Partitioning
case class UnknownPartitioning(numPartitions: Int) extends Partitioning  // 未知
case class RoundRobinPartitioning(numPartitions: Int) extends Partitioning  // 轮询
case object SinglePartition extends Partitioning  // 单分区
case class HashPartitioning(expressions: Seq[Expression], numPartitions: Int)
    extends Partitioning  // Hash 分区
case class KeyedPartitioning(...) extends Partitioning  // 键分区（含多列簇）
case class RangePartitioning(ordering: Seq[SortOrder], numPartitions: Int)
    extends Partitioning  // 范围分区
case class PartitioningCollection(partitionings: Seq[Partitioning])
    extends Partitioning  // 多分区组合（Union 场景）
case class BroadcastPartitioning(mode: BroadcastMode) extends Partitioning  // 广播
```

**Distribution vs Partitioning** 的关系：
- Distribution 表达的是 **需求**（"我需要数据按某列 Hash 分布"）
- Partitioning 表达的是 **事实**（"数据实际是按某列 Hash 分布的"）
- `EnsureRequirements` 比较需求与事实，如果不匹配，插入 `ShuffleExchangeExec`

### 11.5 Preparation Rules（执行前准备规则）

Logical Plan → SparkPlan 的转换完成后，还需要一组 **Preparation Rules** 来处理物理计划——这仍然是一种 Rule-based 的变换，但操作在 SparkPlan 上而非 LogicalPlan 上：

```scala
// QueryExecution.scala:621
private[execution] def preparations(
    sparkSession: SparkSession,
    adaptiveExecutionRule: Option[InsertAdaptiveSparkPlan] = None,
    subquery: Boolean): Seq[Rule[SparkPlan]] = {
  adaptiveExecutionRule.toSeq ++ Seq(
    CoalesceBucketsInJoin,
    PlanDynamicPruningFilters(sparkSession),
    PlanSubqueries(sparkSession),
    RemoveRedundantProjects,
    EnsureRequirements(),          // ★ 插入 Shuffle、确保数据分布
    InsertSortForLimitAndOffset,
    ReplaceHashWithSortAgg,
    RemoveRedundantSorts,
    RemoveRedundantWindowGroupLimits,
    DisableUnnecessaryBucketedScan,
    ApplyColumnarRulesAndInsertTransitions(...),  // 列式→行式转换
    CollapseCodegenStages(),       // 合并全阶段代码生成
  ) ++ (if (!subquery) Seq(ReuseExchangeAndSubquery) else Nil)
}
```

**EnsureRequirements** 是整个 Preparation 阶段的核心。它的工作流程：

1. 对每个算子，检查其子节点的实际 `outputPartitioning` 是否满足该算子的 `requiredChildDistribution`
2. 如果不满足，在父子之间插入 `ShuffleExchangeExec` 或 `BroadcastExchangeExec`
3. 类似地检查排序需求（`requiredChildOrdering` vs 实际 `outputOrdering`）

例如对于 `SortMergeJoinExec`：
- `requiredChildDistribution` = `[ClusteredDistribution(leftKeys), ClusteredDistribution(rightKeys)]`
- 如果左子的 `outputPartitioning` 不是按 leftKeys 的 HashPartitioning → 插入 ShuffleExchangeExec
- 如果左子的 `outputOrdering` 不满足 leftKeys 的序 → 插入 SortExec

**为什么 Preparation 不放在 Optimizer 中？** 因为 Preparation 操作在物理层级——涉及 `ShuffleExchangeExec`（物理 Shuffle）和 `BroadcastExchangeExec`（物理广播），这些都是具体的执行算子。LogicalPlan 不知道也不该知道"Shuffle"这个概念。

### 11.6 QueryExecution — 完整的执行流水线

`QueryExecution` 是整个查询执行状态机的管理器：

```scala
// QueryExecution.scala:65
class QueryExecution(val sparkSession: SparkSession, val logical: LogicalPlan) {
  // 4 个核心阶段的 pipeline（懒加载）
  def analyzed: LogicalPlan = ...       // 阶段1: Analysis
  def optimizedPlan: LogicalPlan = ...  // 阶段2: Logical Optimization
  def sparkPlan: SparkPlan = ...        // 阶段3: Physical Planning (Strategy-based)
  def executedPlan: SparkPlan = ...     // 阶段4: Preparation

  def toRdd: RDD[InternalRow] = ...     // 执行入口

  // 每个阶段都经过 executePhase + tracker.measurePhase —— 收集耗时数据
}
```

4 个阶段的依赖关系：

```
logical (Unresolved)
  ↓ lazyAnalyzed
analyzed (Resolved LogicalPlan)
  ↓ lazyOptimizedPlan
optimizedPlan (Optimized LogicalPlan)
  ↓ lazySparkPlan (planner.plan)
sparkPlan (SparkPlan with PlanLater)
  ↓ lazyExecutedPlan (preparations)
executedPlan (SparkPlan ready for execution)
  ↓ toRdd
RDD[InternalRow]
```

每个阶段都是懒加载（lazy val）——只有被访问时才执行，且结果缓存。这允许在调试时逐个检查各阶段的输出（例如通过 `df.queryExecution.optimizedPlan` 检查优化后的逻辑计划）。

### 11.7 从 LogicalPlan 到 SparkPlan 的完整示例

以 `SELECT a, COUNT(*) FROM t WHERE b > 10 GROUP BY a` 为例：

```
阶段1 — Analysis:
  Project [a, count(*)]
  +- Aggregate [a], [count(*) as c]
     +- Filter (b > 10)
        +- UnresolvedRelation t

阶段2 — Optimized:
  Aggregate [a], [count(1) as c]           ← count(*) → count(1) 常量折叠
  +- Filter (b > 10)
     +- Relation t [a, b]

阶段3 — Physical Planning:
  HashAggregateExec(keys=[a], functions=[count(1)])
  +- ShuffleExchangeExec(HashPartitioning(a))  ← Aggregation Strategy 插入
     +- HashAggregateExec(keys=[a], functions=[partial_count(1)])
        +- FilterExec(b > 10)
           +- FileSourceScanExec(t, [a, b])

阶段4 — Preparation:
  EnsureRequirements 检查并确认 HashAggregateExec 的 requiredChildDistribution
  与 ShuffleExchangeExec 的 outputPartitioning 一致
  → 不需要额外修改
  CollapseCodegenStages 合并 FilterExec + 下层 HashAggregate → WholeStageCodegenExec
```

注意 Physical Planning 阶段 Aggregation Strategy 生成了两阶段 HashAggregate（partial + final），中间用 Shuffle 连接。这是标准的两阶段聚合模式——但不是 Preparation 阶段插入的，而是 Strategy 自己的决策。

## 关键代码片段

### 示例：一个完整 Strategy 的实现

```scala
// 以 Window Strategy 为例
object Window extends Strategy {
  def apply(plan: LogicalPlan): Seq[SparkPlan] = plan match {
    case PhysicalWindow(
      WindowFunctionType.SQL, windowExprs, partitionSpec, orderSpec, child) =>
      execution.window.WindowExec(
        windowExprs, partitionSpec, orderSpec, planLater(child)) :: Nil

    case PhysicalWindow(
      WindowFunctionType.Python, windowExprs, partitionSpec, orderSpec, child) =>
      execution.python.ArrowWindowPythonExec(
        windowExprs, partitionSpec, orderSpec, planLater(child)) :: Nil

    case _ => Nil  // 不匹配 = 不处理，由下一个 Strategy 处理
  }
}
```

### 示例：EnsureRequirements 的核心逻辑

```scala
// EnsureRequirements.scala
// 核心逻辑简化版：
private def ensureDistributionAndOrdering(operator: SparkPlan): SparkPlan = {
  // 1. 对每个子节点，检查分布需求
  val newChildren = operator.children.zip(operator.requiredChildDistribution).map {
    case (child, BroadcastDistribution(mode)) =>
      // 广播：插入 BroadcastExchangeExec
      BroadcastExchangeExec(mode, child)
    case (child, ClusteredDistribution(clustering, numPartitions)) =>
      child.outputPartitioning match {
        case h: HashPartitioning if h.satisfies(clustering) => child  // 已满足
        case _ => ShuffleExchangeExec(HashPartitioning(clustering, numPartitions), child)  // 插入 Shuffle
      }
    case (child, _) => child  // UnspecifiedDistribution: 不需要改变
  }

  // 2. 对每个新子节点，检查排序需求
  val newSortedChildren = newChildren.zip(operator.requiredChildOrdering).map {
    case (child, requiredOrder) if requiredOrder.nonEmpty =>
      child.outputOrdering match {
        case o if o.satisfies(requiredOrder) => child  // 已满足
        case _ => SortExec(requiredOrder, global = false, child)  // 插入 Sort
      }
    case (child, _) => child
  }

  operator.withNewChildren(newSortedChildren)
}
```

## 硬件视角

Physical Planning 阶段的硬件影响不再是"优化器自身的 GC"（因为它只遍历一次树，不像 Optimizer 那样有 10+ 次迭代），而是 **它生成的物理计划的效率**。

从硬件角度看，Physical Planning 做的最重要决定是 **数据本地性**（Data Locality）和 **数据移动**（Data Movement）。

以 Join 为例，不同的物理算法对应不同的数据移动模式：

| Join 算法 | 数据移动 | 网络 I/O | 内存占用 |
|-----------|---------|---------|---------|
| Broadcast Hash Join | 广播小表到所有节点 | 小表大小 × (节点数 - 1) | 小表的 Hash Table |
| Shuffle Hash Join | 两侧都 Shuffle | 两侧的数据大小 | Build 侧的 Hash Table |
| Sort Merge Join | 两侧都 Shuffle | 两侧的数据大小 | 仅排序内存（可溢写） |
| Broadcast Nested Loop Join | 广播一侧 | 广播侧大小 × (节点数 - 1) | 广播侧的缓存 |

`JoinSelection` 中的 `canBroadcastBySize` 阈值（默认 10MB）直接影响网络流量。如果阈值设得过高，广播会成为网络风暴——100 个 executor × 10MB 表 = 1GB 网络流量，这可能比 Shuffle 两侧各 500MB 更昂贵（因为广播是 n×1 对多，Shuffle 是多对多）。

同样，`EnsureRequirements` 中的 Shuffle 插入也直接影响磁盘 I/O——Shuffle Write 是落盘的（不是纯内存），这是第 3-4 章深入讨论的主题。

**Physical Planning 最关键的硬件决策**是 Whole-Stage Code Generation 的范围（通过 `CollapseCodegenStages`）：哪些算子可以合并成一个 JIT 编译的 pipeline。一章 `WholeStageCodegenExec`（第 13 章会详细讨论）的本质是 **消除虚函数调用**——将多个算子的处理逻辑合并为一个紧凑的 for 循环，让数据保持在 CPU 寄存器而非内存中。但这个合并不总是有利的——Volcano 式的逐个算子调用比代码生成循环更容易调试和扩展。

## AI 时代反思

Physical Planning 是对离散策略空间的搜索。给定一个 Logical Plan，存在有限数量的物理计划（Join 算法选择 × Shuffle 方式 × CodeGen 合并方式）。原则上，这是一个 **组合优化（Combinatorial Optimization）** 问题。

但在实践中，Spark 用的是一个贪心/启发式的 decision tree，而不是真正的搜索——因为缺少细粒度的物理代价模型（Physical Cost Model）。如果你不知道 BHJ 和 SMJ 在 100 节点集群上的精确代价差异，你就无法做真正的搜索。

这又回到了第 10 章的 Learned Cost Model 讨论。如果有一个足够准确的物理代价预测模型（输出集群级别的 wall-clock time），Physical Planning 就可以从"贪心选择"转变为真正的 **Cost-Based Search**。

在这种 Full CBO 场景下，LLM 的角色是什么？

LLM 可以通过分析查询日志来自动发现 **物理规划的启发式规则**。例如：

- "当 build 侧表有 90% 重复值时，SHJ 的 Hash Table 冲突率极高，SMJ 更好"
- "在 NVMe SSD + RDMA 网络环境中，External Sort 的 I/O 成本低，SMJ 在 SMJ vs SHJ 中应获得更多偏好"
- "当集群已有缓存的广播表时，后续 BHJ 只需要反序列化开销，几乎免费"

这些规则涉及硬件组合、数据特征、运行时状态——编码为启发式规则几乎不可能（组合数太多）。但 LLM 的 pattern recognition 能力可能恰好是解决这个问题的。

## 源码导航

| 文件 | 关键内容 | 行号参考 |
|------|---------|---------|
| `sql/core/src/main/scala/org/apache/spark/sql/execution/SparkStrategies.scala` | SparkStrategies 类，所有 Strategy 定义（JoinSelection, Aggregation, BasicOperators, Window, SpecialLimits 等） | 75 (SparkStrategies), 92 (SpecialLimits), 181 (JoinSelection), 584 (Aggregation), 678 (Window), 905 (BasicOperators) |
| `sql/core/src/main/scala/org/apache/spark/sql/execution/SparkPlan.scala` | SparkPlan 基类，doExecute/doExecuteBroadcast/doColumnarExecute 入口 | 65 (类定义), 85 (supportsRowBased), 92 (supportsColumnar), 163 (outputPartitioning), 180 (requiredChildDistribution), 197 (execute), 214 (executeBroadcast) |
| `sql/core/src/main/scala/org/apache/spark/sql/execution/SparkPlanner.scala` | SparkPlanner，strategies 列表的组装 | |
| `sql/core/src/main/scala/org/apache/spark/sql/execution/QueryExecution.scala` | QueryExecution 执行管线，preparations，prepareForExecution，createSparkPlan | 65 (类定义), 155 (analyzed), 259 (optimizedPlan), 274 (sparkPlan), 295 (executedPlan), 621 (preparations), 659 (prepareForExecution), 677 (createSparkPlan) |
| `sql/core/src/main/scala/org/apache/spark/sql/execution/exchange/EnsureRequirements.scala` | EnsureRequirements 规则，Shuffle 和 Broadcast Exchange 的插入逻辑 | |
| `sql/catalyst/src/main/scala/org/apache/spark/sql/catalyst/plans/physical/partitioning.scala` | Distribution 和 Partitioning 类型体系定义 | 39 (Distribution), 56 (UnspecifiedDistribution), 85 (ClusteredDistribution), 167 (OrderedDistribution), 192 (BroadcastDistribution), 250 (UnknownPartitioning), 259 (SinglePartition), 309 (HashPartitioning), 622 (RangePartitioning) |
| `sql/catalyst/src/main/scala/org/apache/spark/sql/catalyst/planning/QueryPlanner.scala` | QueryPlanner 框架，Strategy 调度逻辑 | |
| `sql/core/src/main/scala/org/apache/spark/sql/execution/SparkOptimizer.scala` | SparkOptimizer，继承 Optimizer 并注入额外的优化规则 | |
| `sql/core/src/main/scala/org/apache/spark/sql/execution/WholeStageCodegenExec.scala` | Whole-Stage Code Generation 物理算子 | |
