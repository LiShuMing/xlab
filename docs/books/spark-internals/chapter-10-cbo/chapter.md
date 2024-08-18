# 第 10 章：Cost-Based Optimization — 统计信息驱动的优化决策

## 设计动机

第 9 章的启发式优化器（Rule-Based Optimizer，简称 RBO）有一个根本的局限：**它不考虑数据分布**。

启发式规则"谓词下推总是好的"在大多数情况下成立。但考虑以下场景：

```sql
SELECT * FROM orders JOIN customers ON orders.cust_id = customers.id
WHERE orders.amount > 10000
```

假设 `orders` 表有 10 亿行，`customers` 表有 100 万行，且 `orders.amount > 10000` 过滤掉了 99.9% 的行。启发式规则会把 `amount > 10000` 下推到 orders 侧——这是对的。但它无法回答一个更根本的问题：

**Join 应该先用 orders 还是先用 customers？** 如果先 Join orders（过滤后 100 万行），结果是 100 万 × 100 万的 Hash Join。但如果先把 customers 复制到所有节点（Broadcast），成本可能完全不同。

这就是 CBO（Cost-Based Optimization）要回答的问题：**哪一个等价计划更便宜？**

CBO 的核心直觉很简单：**如果我能估算每个中间结果的"大小"（行数、字节数），我就能用代价模型选出最优计划**。但实现这个直觉需要三要素：

1. **统计信息**（Statistics）：表的大小、列的基数分布、直方图
2. **估算推导**（Estimation）：给定统计信息，推导谓词过滤、Join、聚合后的大小变化
3. **搜索算法**（Search）：在指数级的计划空间中高效找到代价最低的计划

Spark CBO 的设计哲学是 **"实用优先"**。它在 2017 年（Spark 2.2）引入时做出的关键决定是：
- **不做完全的 Cost Model**（像 ORCA 那样计算 CPU/I/O/Network）
- **只做 Join Reorder**——因为 Join 顺序是基数估算误差导致的最昂贵的错误
- **统计信息可选**——没有统计信息时退化为纯 RBO

## 核心原理

### 10.1 Statistics 数据模型

整个 CBO 的基石是 `Statistics` case class：

```scala
// Statistics.scala:55
case class Statistics(
    sizeInBytes: BigInt,
    rowCount: Option[BigInt] = None,
    attributeStats: AttributeMap[ColumnStat] = AttributeMap(Nil),
    isRuntime: Boolean = false)
```

为什么 `rowCount` 是 `Option[BigInt]`？因为统计信息可能不存在（表从 ANALYZE TABLE 获取，但这不是必须的）。没有 `rowCount` 时，CBO 退化为仅用 `sizeInBytes`。

`ColumnStat` 是列级统计信息：

```scala
// Statistics.scala:95
case class ColumnStat(
    distinctCount: Option[BigInt] = None,  // 去重值的数量
    min: Option[Any] = None,               // 最小值
    max: Option[Any] = None,               // 最大值
    nullCount: Option[BigInt] = None,      // NULL 的数量
    avgLen: Option[Long] = None,           // 平均长度
    maxLen: Option[Long] = None,           // 最大长度
    histogram: Option[Histogram] = None,   // 等高峰直方图
    version: Int = CatalogColumnStat.VERSION)
```

`Histogram` 是等高峰（Equi-height）直方图：

```scala
// Statistics.scala:146
case class Histogram(height: Double, bins: Array[HistogramBin])
case class HistogramBin(lo: Double, hi: Double, ndv: Long)
```

每个 bin 包含约 `height` 行，[lo, hi] 是值的范围，ndv 是 bin 内的去重值数量。等高峰直方图的基本性质是：每个 bin 内的行数大致相同，这使得过滤选择性计算变得简单（过滤落在 3 个 bin 内 ≈ 选 3/n 的行）。

**统计信息的来源**有两种：
1. **Catalog 元数据**（Hive Metastore 或表属性）：通过 `ANALYZE TABLE t COMPUTE STATISTICS` 获得
2. **AQE 运行时统计**（isRuntime = true）：在执行过程中测量的实际大小

### 10.2 Statistics 的传播机制

`LogicalPlanStats` trait 定义了统计信息的懒加载和缓存：

```scala
// LogicalPlanStats.scala:25
trait LogicalPlanStats { self: LogicalPlan =>
  def stats: Statistics = statsCache.getOrElse {
    if (conf.cboEnabled) {
      statsCache = Option(BasicStatsPlanVisitor.visit(self))
    } else {
      statsCache = Option(SizeInBytesOnlyStatsPlanVisitor.visit(self))
    }
    statsCache.get
  }
  protected var statsCache: Option[Statistics] = None
}
```

注意这是 **懒加载**（lazy-cache-once）策略——统计信息只在第一次访问时计算，之后缓存。当 CBO 禁用时，`SizeInBytesOnlyStatsPlanVisitor` 只计算 `sizeInBytes`，跳过更昂贵的 `rowCount` 和列级 stats。

`BasicStatsPlanVisitor` 是 CBO 启用时的统计信息估算入口：

```scala
// BasicStatsPlanVisitor.scala:25
object BasicStatsPlanVisitor extends LogicalPlanVisitor[Statistics] {
  override def default(p: LogicalPlan): Statistics = p match {
    case p: LeafNode => p.computeStats()   // 叶子节点：从 Catalog 读取或估算
    case _: LogicalPlan =>
      val stats = p.children.map(_.stats)
      val rowCount = if (stats.exists(_.rowCount.isEmpty)) None
        else Some(stats.map(_.rowCount.get).filter(_ > 0L).product)
      Statistics(sizeInBytes = stats.map(_.sizeInBytes).filter(_ > 0L).product, rowCount = rowCount)
  }

  override def visitFilter(p: Filter): Statistics =
    FilterEstimation(p).estimate.getOrElse(fallback(p))

  override def visitJoin(p: Join): Statistics =
    JoinEstimation(p).estimate.getOrElse(fallback(p))

  override def visitAggregate(p: Aggregate): Statistics =
    AggregateEstimation.estimate(p).getOrElse(fallback(p))

  override def visitProject(p: Project): Statistics =
    ProjectEstimation.estimate(p).getOrElse(fallback(p))
}
```

默认行为是 **乘法传播**：子节点的 `rowCount` 相乘。这对应"上层算子不改变行数"的假设（例如 Project、Sort 不改变行数，但 Filter 通过 FilterEstimation 修正，Aggregate 通过 AggregateEstimation 修正）。

### 10.3 Filter 选择性估算

`FilterEstimation` 是 CBO 中最核心的统计推导规则——它回答"一个谓词过滤掉多少行"：

```scala
// FilterEstimation.scala:30
case class FilterEstimation(plan: Filter) {
  private val childStats = plan.child.stats
  private val colStatsMap = ColumnStatsMap(childStats.attributeStats)

  def estimate: Option[Statistics] = {
    if (childStats.rowCount.isEmpty) return None
    val filterSelectivity = calculateFilterSelectivity(plan.condition).getOrElse(1.0)
    val filteredRowCount = ceil(BigDecimal(childRowCount) * filterSelectivity)
    // 计算过滤后的列统计信息
    val newColStats = colStatsMap.outputColumnStats(
      rowsBeforeFilter = childRowCount, rowsAfterFilter = filteredRowCount)
    // sizeInBytes 取 "output attr 算出的大小" 和 "按行数等比例缩放" 中的最小值
    val filteredSizeInBytes = sizeByOutputAttrs.min(sizeByChildScaling)
    Some(childStats.copy(sizeInBytes = filteredSizeInBytes,
      rowCount = Some(filteredRowCount), attributeStats = newColStats))
  }
}
```

选择性计算的核心是 `calculateFilterSelectivity`：

```scala
def calculateFilterSelectivity(condition: Expression, update: Boolean = true): Option[Double] = {
  condition match {
    case And(cond1, cond2) =>
      // AND: 连续计算并更新统计（因为 a>10 AND a<100 需要依赖更新后的统计）
      Some(percent1 * percent2)
    case Or(cond1, cond2) =>
      // OR: 不更新统计，独立计算（因为两路是独立的分支）
      Some(percent1 + percent2 - (percent1 * percent2))
    case Not(cond) =>
      Some(1.0 - percent)
    // 等值条件: col = value
    case EqualTo(ar: AttributeReference, Literal(v, _)) =>
      Some(if hasHistogram then histogram.selectivity(v)
           else 1.0 / distinctCount)   // 均匀假设
    // 范围条件: col < value, col > value
    case LessThan(ar: AttributeReference, Literal(v, _)) =>
      Some(if hasHistogram then histogram.selectivity(lessThan=v)
           else (value - min) / (max - min))  // 均匀假设
    ...
  }
}
```

**为什么 AND 更新统计而 OR 不更新？** 因为 AND 的本质是"数据同时满足两个条件"——筛选是累积的。对于 `a > 10 AND a < 100`，先应用 `a > 10` 缩减了 `a` 的有效范围，再应用 `a < 100` 在这个缩减后的范围内计算，结果更准确。

没有直方图时，Spark 使用 **均匀分布假设**（Uniform Distribution Assumption）：列的取值范围是 [min, max]，每个值出现的概率均等。这是最简单的统计模型——也是误差最大的模型。数据倾斜（skew）是它最主要的失效场景。

### 10.4 Join 基数估算

`JoinEstimation` 估算 Join 后的行数和大小：

```scala
// JoinEstimation.scala:52
private def estimateInnerOuterJoin(): Option[Statistics] = join match {
  case ExtractEquiJoinKeys(joinType, leftKeys, rightKeys, _, _, left, right, _) =>
    // 1. 计算 Join 选择性
    // 对于等值连接: selectivity = 1 / max(ndv(leftKey), ndv(rightKey))
    // 这就是"取去重值更大的一侧"——Join 的输出行数由"匹配最多的一侧"决定
    val joinSelectivity = leftKeys.zip(rightKeys).map { case (lk, rk) =>
      1.0 / BigDecimal(max(ndv(lk), ndv(rk)))
    }.product

    // 2. 输出行数 = 笛卡尔积行数 × Join 选择性
    val outputRowCount = leftRowCount * rightRowCount * joinSelectivity

    // 3. 输出大小 = 左输出列大小 + 右输出列大小（按行数缩放）
    ...
}
```

等值连接的经典公式：
```
|R ⨝ S| = |R| × |S| × selectivity
selectivity = 1 / max(NDV(R.key), NDV(S.key))
```

为什么是 `max` 而不是 `min`？含义是"在更大去重值的一侧，平均每个 key 匹配的行数更少"。例如 `orders(1000 行, 500 个不同 cust_id)` ⨝ `customers(100 行, 100 个不同 id)`。对 orders，平均每个 cust_id 匹配 1000/500=2 行；对 customers，平均每个 id 匹配 1 行。Join 后大约输出 1000 行（orders 的行数），而不是 100 行。

对于 Cross Join / 无 Join 条件的情况，选择性 = 1.0（输出行数 = 笛卡尔积）。对于多列 Join 条件，选择性是各列独立的积（独立性假设）——这又是一处可能产生系统性误差的地方。

### 10.5 Cost-Based Join Reorder — DP 算法

Spark 的 CBO 目前主要应用于 **Join 重排序**——这是基数估算误差最昂贵的场景。如果你把 100G 的表和 10M 的表 Join 反了，中间结果会多出几个数量级。

核心入口是 `CostBasedJoinReorder`：

```scala
// CostBasedJoinReorder.scala:36
object CostBasedJoinReorder extends Rule[LogicalPlan] with PredicateHelper {
  def apply(plan: LogicalPlan): LogicalPlan = {
    if (!conf.cboEnabled || !conf.joinReorderEnabled) {
      plan
    } else {
      val result = plan.transformDownWithPruning(_.containsPattern(INNER_LIKE_JOIN), ruleId) {
        case j @ Join(_, _, _: InnerLike, Some(cond), JoinHint.NONE) =>
          reorder(j, j.output)
      }
      result transform {
        case OrderedJoin(left, right, jt, cond) => Join(left, right, jt, cond, JoinHint.NONE)
      }
    }
  }
}
```

调用了 `reorder`，逻辑是：
1. 从 Join 树中提取所有 Inner Join（`extractInnerJoins`）——得到 items（表/子查询）和 conditions（Join 条件）
2. 如果 item 数量 ≤ `joinReorderDPThreshold`（默认 12），运行 DP 搜索
3. 返回重排后的计划

**DP 搜索算法**（`JoinReorderDP`）基于 Selinger 1979 年的 System R 优化器经典论文：

```scala
// CostBasedJoinReorder.scala:143
object JoinReorderDP extends PredicateHelper with Logging {
  def search(conf: SQLConf, items: Seq[LogicalPlan],
    conditions: ExpressionSet, output: Seq[Attribute]): LogicalPlan = {

    // Level 0: 每个表作为一个 JoinPlan，成本为 0
    val foundPlans = mutable.Buffer[JoinPlanMap]({
      itemIndex.map { case (item, id) =>
        Set(id) -> JoinPlan(Set(id), item, ExpressionSet(), Cost(0, 0))
      }.toMap
    })

    // Level 1 → Level n: 从已找到的低层计划构建更高层的 Join
    while (foundPlans.size < items.length) {
      foundPlans += searchLevel(foundPlans.toSeq, conf, conditions, topOutputSet, filters)
    }
    foundPlans.last.head._2.plan  // 最后 level 只有 1 个计划
  }
}
```

DP 算法的核心：
- **Level k** 包含所有可能的 k-item Join 组合
- 从 Level k 和 Level (lev - k) 中各取一个不相交的 `JoinPlan`，尝试构建一个新的 Join
- 对于同一个 item set，只保留**代价最低**的计划
- **过滤笛卡尔积**：如果没有 Join 条件涉及左右两侧，直接跳过（避免生成爆炸性的 Cross Join）

```scala
private def buildJoin(oneJoinPlan: JoinPlan, otherJoinPlan: JoinPlan, ...): Option[JoinPlan] = {
  if (oneJoinPlan.itemIds.intersect(otherJoinPlan.itemIds).nonEmpty) return None
  // 过滤笛卡尔积
  val joinConds = conditions.filter(e => e.references.subsetOf(onePlan.outputSet ++ otherPlan.outputSet))
  if (joinConds.isEmpty) return None
  // 更深的一侧放左边（倾向于左深树）
  val (left, right) = if (oneJoinPlan.itemIds.size >= otherJoinPlan.itemIds.size)
    (onePlan, otherPlan) else (otherPlan, onePlan)
  val newJoin = Join(left, right, Inner, joinConds.reduceOption(And), JoinHint.NONE)
  // 代价 = 两侧已累计的代价 + 当前 Join 的代价
  val newPlanCost = oneJoinPlan.planCost + oneJoinPlan.rootCost(conf) +
    otherJoinPlan.planCost + otherJoinPlan.rootCost(conf)
  Some(JoinPlan(itemIds, newPlan, collectedJoinConds, newPlanCost))
}
```

**代价函数**（`betterThan`）：

```scala
// CostBasedJoinReorder.scala:370
def betterThan(other: JoinPlan, conf: SQLConf): Boolean = {
  val relativeRows = BigDecimal(this.planCost.card) / BigDecimal(other.planCost.card)
  val relativeSize = BigDecimal(this.planCost.size) / BigDecimal(other.planCost.size)
  // 加权几何平均
  Math.pow(relativeRows.doubleValue, conf.joinReorderCardWeight) *
    Math.pow(relativeSize.doubleValue, 1 - conf.joinReorderCardWeight) < 1
}
```

关键观察：使用**加权几何平均**而非算术平均。原因在注释中解释了——算术平均对 ratio > 1 的情况偏重（ratio 10 和 0.1 在几何平均中对称，但在算术平均中不对称）。`joinReorderCardWeight` 默认 0.7，即基数占比重的权重大于字节大小。

### 10.6 Star Schema 检测

Star Schema 是数据仓库中最常见的模型：一张 Fact 表被多张 Dimension 表环绕。例如 `sales(fact) JOIN date_dim JOIN product_dim JOIN store_dim`。

`StarSchemaDetection` 检测这种模式：

```scala
// StarSchemaDetection.scala
// 检测条件: Dimension 表有外键约束 (Referential Integrity)
// → Dimension 表与 Fact 表的 Join 不会丢失/复制行
// → Dimension-Dimension 的 Join 应该延后到 Fact Join 之后
```

在 DP 搜索中，`JoinReorderDPFilters.starJoinFilter` 确保 star 表之间先 Join 完，再与 non-star 表 Join。这利用了 RI 约束的事实：Fact-Dimension Join 是"无损"的（不会膨胀也不会缩水）。

### 10.7 CBO 的局限性

Spark CBO 的实用主义带来了明确的局限：

1. **只做 Join Reorder**：不用于选择 Join 算法（Hash vs SortMerge vs Broadcast）——这些在 Physical Planning 中通过大小阈值决定
2. **统计信息可选**：大量生产环境中表没有 ANALYZE，此时 CBO 完全退化为 RBO
3. **独立性假设**：Filter 选择性和 Join 选择性都假设列之间独立，这在实际数据中经常被违反
4. **均匀分布回退**：没有直方图时使用均匀假设，对于 Zipf 分布（重尾分布）误差可达数个数量级
5. **没有 Cost Model**：只比较 rowCount 和 sizeInBytes，不考虑 CPU、I/O、网络成本

### 10.8 对标：StarRocks CBO

作为对比，StarRocks CBO 的设计差异值得讨论：

**统计信息方面**：
- StarRocks 在每次导入和 Compaction 时**自动收集**统计信息，不需要手动 ANALYZE
- 使用 HyperLogLog 密度图代替等高峰直方图，内存占用固定

**Cascade 架构**：
- StarRocks CBO 基于 **Cascades 框架**（哥伦比亚大学优化器），执行完全的 Memo 结构搜索
- 搜索涉及 Join Ordering、Join Algorithm Selection、Aggregation Strategy 等多个维度
- Spark 没有 Memo 结构——只有一个 Operator Optimization 的 FixedPoint 规则链加 DP Join Reorder

**代价模型**：
- StarRocks 的 Cost Model 更细化：考虑了 I/O、CPU、网络、内存占用
- 代价 = `(I/O cost) + (CPU cost) × cpuCostWeight + (MEM cost) × memCostWeight + (NET cost) × netCostWeight`

**为什么 Spark 不做一个完整的 Cascades CBO？** 根本原因是引擎定位不同：
- Spark 是通用计算引擎，表可能来自任意数据源（Parquet、JDBC、Kafka），很多数据源不提供统计信息
- StarRocks 是 OLAP 数据库，存储引擎完全可控，统计信息天然齐全
- Spark 的灵活性代价就是 CBO 必须能优雅降级（degrade gracefully）

## 关键代码片段

### 示例：一条统计信息流

```scala
// 从 ANALYZE TABLE 到 Join Reorder 的统计信息全流程

// 1. ANALYZE TABLE t COMPUTE STATISTICS → 写入 Catalog
// → CatalogTable.stats = Some(CatalogStatistics(
//      sizeInBytes = ..., rowCount = Some(...),
//      colStats = Map("id" -> CatalogColumnStat(...))))

// 2. 查询时，Relation 节点使用 Catalog 中的统计信息
// Relation t → computeStats() → 返回 Catalog 中存储的 Statistics

// 3. Filter 节点通过 FilterEstimation 推导新统计
// Filter(a > 10, Relation t)
// → FilterEstimation.estimate → rowCount * selectivity(histogram, a>10)
// → 新 Statistics(rowCount = filtered, attributeStats = updated)

// 4. JoinEstimation 推导 Join 后的统计
// Join(Filter, Relation t2, Inner, t1.id = t2.id)
// → outputRowCount = leftRowCount * rightRowCount / max(ndv(left.id), ndv(right.id))

// 5. DP 搜索使用 Cost(card, size) 比较不同 Join Plan
// → betterThan 使用加权几何平均选择最低代价的计划
```

## 硬件视角

CBO 的统计信息传播是一个"数据密集但计算稀疏"的操作链。对于每个 LogicalPlan 节点，统计信息计算涉及：

- `statsCache.getOrElse`：1 次 HashMap lookup
- `BasicStatsPlanVisitor.visit`：1 次虚函数调用（case match）
- `FilterEstimation.estimate`：遍历条件树（约 2-5 个表达式节点），每次涉及直方图查找（二分搜索在约 254 个 bin 上 ≈ 8 次比较）
- DP 搜索的 `betterThan`：2 次 `BigDecimal` 除法和 2 次 `Math.pow`（浮点运算）

这些全是 **CPU-bound 的标量计算**——没有并行。对于 5 表 Join 的 DP 搜索，可能有约 20 个 `JoinPlan` 候选，每对比一次 `betterThan`。整个 CBO 增加的开销在微秒到毫秒级别——与查询执行本身的秒/分钟级别相比微不足道。

但有一个微妙的硬件影响：**统计信息缓存的局部性**。`statsCache` 是直接存在 `LogicalPlan` 对象中的——这意味着每次访问 stats 时，JVM 已经将对象拉入了 cache line。这比"从外部 metadata store 查询"快得多，也是为什么 Spark 不用每次重新查询 Metastore。

然而，`invalidateStatsCache()` 的递归行为可能导致性能波动：当 AQE 更新统计信息时（isRuntime = true），整个子树的缓存被清除，下次 `stats` 访问需要重新计算整棵树。对于 deep plan，这是一种延迟 spike。

## AI 时代反思

CBO 的根本问题是 **基数估算**——给定统计信息和查询，预测中间结果的行数。这是一个"有监督学习"问题：输入 = (柱状图, 查询条件)，输出 = 估计行数，目标是 min |est - actual|。

那么，为什么在 CBO 中用回归模型（如 XGBoost 或小型 NN）替代传统的直方图/选择性公式？

**Learned Cardinality Estimation**（学习式基数估算）是数据库研究的前沿方向。2019 年 VLDB 的 "Learned Cardinalities" 论文展示了用多集合卷积网络（MSCN）进行的基数估算，在特定 benchmark 上比传统方法减少 10× 误差。

但学习式方法的部署有两大障碍：
1. **训练数据**：需要大量 "查询 + 实际行数" 作为 label。这在生产环境中需要采样和日志收集。
2. **预测延迟**：传统的直方图查找是μs级，NN 推理通常是 ms 级——CBO 在 planning 期间可能需要数百次基数估算。用模型替代公式，planning 延迟增加 10-100 倍可能不可接受。

一个折中方案是 **混合模型**：默认用传统直方图，在检测到"数据倾斜"时切换到学习模型。或者，用 LLM 做一件事：从查询日志中发现"哪些列之间有相关性"——然后将这些相关性信息注入传统估算公式的参数（不再假设独立性）。这比"让 LLM 估算基数"更实用。

Google BigQuery 的经验表明：**消除基数估算的需要**比改善基数估算更有效。BigQuery 的 Dremel 执行引擎通过动态调度、动态分批分配资源，让执行引擎天然适应中间结果的大小变化——这消除了"必须事先知道中间结果大小才能做出好计划"的依赖。这是一种 design-out 而非 fix-forward 的思考方式。

但即使如此，Join 顺序仍然很重要——你不能让两个 10TB 的表做 Cross Join 后再筛选。CBO 保护的正是这种头部风险。而 LLM 在这里的角色可能是：**作为 CBO 的失败检测器**——当运行时发现实际行数比 CBO 估算高 10× 以上时，自动标记这个查询，将查询条件和表统计信息作为 context 喂给 LLM，让 LLM 分析"为什么估算失败了"。

## 源码导航

| 文件 | 关键内容 | 行号参考 |
|------|---------|---------|
| `sql/catalyst/src/main/scala/org/apache/spark/sql/catalyst/plans/logical/Statistics.scala` | Statistics，ColumnStat，Histogram，HistogramBin 数据模型 | 55 (Statistics), 95 (ColumnStat), 146 (Histogram), 170 (HistogramBin) |
| `sql/catalyst/src/main/scala/org/apache/spark/sql/catalyst/plans/logical/statsEstimation/LogicalPlanStats.scala` | LogicalPlanStats trait，stats 懒加载缓存逻辑 | 25 (trait 定义), 33 (stats 方法), 47 (invalidateStatsCache) |
| `sql/catalyst/src/main/scala/org/apache/spark/sql/catalyst/plans/logical/statsEstimation/BasicStatsPlanVisitor.scala` | CBO 启用时的统计信息传播入口，调度各算子的 Estimation | 25 (object 定义), 55 (visitFilter), 61 (visitJoin) |
| `sql/catalyst/src/main/scala/org/apache/spark/sql/catalyst/plans/logical/statsEstimation/FilterEstimation.scala` | Filter 选择性计算，AND/OR/NOT 分解逻辑 | 30 (case class), 94 (calculateFilterSelectivity) |
| `sql/catalyst/src/main/scala/org/apache/spark/sql/catalyst/plans/logical/statsEstimation/JoinEstimation.scala` | Join 基数估算，等值连接公式 1/max(ndv) | 31 (case class), 52 (estimateInnerOuterJoin) |
| `sql/catalyst/src/main/scala/org/apache/spark/sql/catalyst/plans/logical/statsEstimation/EstimationUtils.scala` | 统计信息更新工具方法 |
| `sql/catalyst/src/main/scala/org/apache/spark/sql/catalyst/optimizer/CostBasedJoinReorder.scala` | CBO 入口，DP 搜索算法，代价比较函数 | 36 (CostBasedJoinReorder), 143 (JoinReorderDP), 338 (JoinPlan), 370 (betterThan), 388 (Cost) |
| `sql/catalyst/src/main/scala/org/apache/spark/sql/catalyst/optimizer/StarSchemaDetection.scala` | Star Schema 检测，RI 约束利用 | |
