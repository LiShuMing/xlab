# 第 14 章：Join 算子 — 五路算法的全链路实现

## 设计动机

Join 是关系型查询中最重要的操作——没有之一。一个典型的 TPC-DS 查询 99.8% 的执行时间花在 Join 上。优化 Join 等价于优化整个查询。

Spark 支持 5 种 Join 物理算法：

| 算法 | 缩写 | 核心机制 | 适用场景 |
|------|------|---------|---------|
| Broadcast Hash Join | BHJ | 广播小表 + Hash 探测 | 一侧表很小 |
| Shuffle Hash Join | SHJ | 两侧 Shuffle + Hash 探测 | 一侧较小但不够广播 |
| Sort Merge Join | SMJ | 两侧 Shuffle + 排序 + Merge | 大表 Join，默认回退 |
| Broadcast Nested Loop Join | BNLJ | 广播一侧 + 嵌套循环 | 非等值 Join |
| Cartesian Product (Shuffle-and-Replicate NLJ) | CP | 两侧复制 + 嵌套循环 | 无条件 Inner Join |

每条算法有自己的适用条件和性能瓶颈。第 11 章讨论了 JoinSelection Strategy 如何在它们之间决策。本章聚焦于每条算法**实际如何执行**——数据流动、内存结构、CPU 行为。

五条算法可以归为两大家族：
- **Hash Join 家族**（BHJ、SHJ）：Build 侧建 Hash Table，Stream 侧逐行探测
- **Nested Loop 家族**（BNLJ、CP）：外层逐行驱动，内层全量匹配
- **Merge 家族**（SMJ）：两侧已排好序，归并扫描

## 核心原理

### 14.1 Broadcast Hash Join (BHJ)

BHJ 是最快的 Join 算法——当一侧表小到可以广播时。

**执行流程**：

```
阶段 0: Build 侧表被 broadcast 到所有 Executor
阶段 1: 每个 Executor 收到 broadcast 后，将 build 侧构建为 HashedRelation (Hash Table)
阶段 2: Stream 侧逐行探测 Hash Table，匹配的行拼接输出
```

```scala
// BroadcastHashJoinExec.scala:40
case class BroadcastHashJoinExec(
    leftKeys: Seq[Expression],
    rightKeys: Seq[Expression],
    joinType: JoinType,
    buildSide: BuildSide,
    condition: Option[Expression],
    left: SparkPlan,
    right: SparkPlan,
    isNullAwareAntiJoin: Boolean = false,
    isSkewJoin: Boolean = false) extends HashJoin
```

**数据分布需求**：

```scala
override def requiredChildDistribution: Seq[Distribution] = {
  val mode = HashedRelationBroadcastMode(buildBoundKeys, isNullAwareAntiJoin)
  buildSide match {
    case BuildLeft =>
      BroadcastDistribution(mode) :: UnspecifiedDistribution :: Nil
    case BuildRight =>
      UnspecifiedDistribution :: BroadcastDistribution(mode) :: Nil
  }
}
```

Build 侧要求 `BroadcastDistribution`，Stream 侧无需任何分布（`UnspecifiedDistribution`）。`EnsureRequirements` 会将 Build 侧包装在 `BroadcastExchangeExec` 中——触发异步 broadcast job。

**Hash Table 的物理实现**：

`HashedRelation` 是 Hash Table 的抽象。BHJ 使用 `HashedRelationBroadcastMode` 将 build 侧表序列化为 `HashedRelation`：

```scala
// BroadcastHashJoinExec 的内部
val relation = HashedRelation(buildIter, buildKeys, ...)
// HashedRelation 内部是 BytesToBytesMap — 开放寻址线性探测 Hash Table
// key = Join Key (UnsafeRow), value = matched rows (连续存储)
```

探测过程（在 WholeStageCodegen 中）：

```java
// 生成的代码伪码：
while (streamInput.hasNext()) {
  InternalRow streamRow = streamInput.next();
  // 计算 join key 的 hash，在 BytesToBytesMap 中查找
  BytesToBytesMap.Location loc = relation.probe(streamKey);
  if (loc.isDefined) {
    // 找到匹配，输出组合行
    appendRow(streamRow, loc.getValueRow());
  }
}
```

**Outer Join 的特殊处理**：

对于 LEFT OUTER JOIN (BuildRight)：如果 Stream 侧某行在 Hash Table 中没有匹配，输出 Stream 行 + NULL 列。
对于 RIGHT OUTER JOIN (BuildRight)：Build 侧被广播，但 Stream 侧缺失——无法直接执行（因为广播侧不能有"不匹配"行）。实际上，`RIGHT OUTER JOIN` 被 `JoinSelection` 重写为 `LEFT OUTER JOIN BuildLeft`。

**Null-Aware Anti Join (NAAJ)**：

Spark 3.4 引入的特殊优化：

```scala
// 处理 NOT IN (subquery) 中包含 NULL 的情况
// SELECT * FROM t WHERE t.id NOT IN (SELECT id FROM s)
// 如果 s.id 存在 NULL，标准的 Anti Join 会返回空集（因为 NULL != anything 是 unknown）
// NAAJ 使用特殊探测逻辑确认 s 中确实没有 NULL 行
```

### 14.2 Shuffle Hash Join (SHJ)

SHJ 与 BHJ 的区别是：两侧都需要 Shuffle（按 Join Key 分区），但 Build 侧在内存中构建 Hash Table。

```scala
// ShuffledHashJoinExec.scala
case class ShuffledHashJoinExec(
    leftKeys: Seq[Expression],
    rightKeys: Seq[Expression],
    joinType: JoinType,
    buildSide: BuildSide,
    condition: Option[Expression],
    left: SparkPlan,
    right: SparkPlan) extends HashJoin {
```

**当 SHJ，而不是 SMJ？** `JoinSelection` 中的条件：
1. `spark.sql.join.preferSortMergeJoin = false`
2. Build 侧 ≤ `buildSideThreshold`（默认 10x shuffle partitions × avg row size）
3. Build 侧远小于 Stream 侧（至少 3× 大小差距）

**SHJ 的 OOM 风险**：Build 侧必须完整放入内存——如果估算错了，就 OOM。这是为什么 SMJ 是更安全的默认：排序可以落盘。

### 14.3 Sort Merge Join (SMJ)

SMJ 是 Spark 的默认 Join 算法（当没有广播条件时）。它的核心是两阶段：Sort（两侧各自排序）+ Merge（归并扫描）。

```scala
// SortMergeJoinExec.scala:39
case class SortMergeJoinExec(
    leftKeys: Seq[Expression],
    rightKeys: Seq[Expression],
    joinType: JoinType,
    condition: Option[Expression],
    left: SparkPlan,
    right: SparkPlan,
    isSkewJoin: Boolean = false) extends ShuffledJoin
```

**执行流程**：

```
阶段 1: EnsureRequirements 为两侧各插入 SortExec + ShuffleExchangeExec
    left:  <upstream> → ShuffleExchangeExec(HashPartitioning(joinKeys)) → SortExec(joinKeys)
    right: <upstream> → ShuffleExchangeExec(HashPartitioning(joinKeys)) → SortExec(joinKeys)

阶段 2: SortMergeJoinExec.doExecute()
    - 打开左右两个已排好序的迭代器
    - 归并扫描：
        while (leftRow != null && rightRow != null) {
          cmp = compare(leftKey, rightKey)
          if (cmp < 0) leftRow = advance left
          else if (cmp > 0) rightRow = advance right
          else {  // = 匹配，输出 left × right（所有匹配组合）
            ...
          }
        }
```

**归并扫描的复杂度**：O(N+M) 时间，O(1) 空间（只需存当前行）。排序阶段需要 O(sortBuffer) 内存 → 溢写到磁盘。

**SMJ 的 Spill 行为**：排序阶段使用 `UnsafeExternalSorter`——在内存满时溢写到磁盘。每个文件是已排序的 run，最终多路归并。对于 100GB 的输入和 4GB 内存：产生约 25 个 sorted runs，最后读取 25 个并发文件做 k-way merge。

### 14.4 Broadcast Nested Loop Join (BNLJ)

BNLJ 是"最慢且最通用"的 Join——不需要等值条件，但代价是嵌套循环。

```scala
// BroadcastNestedLoopJoinExec.scala
case class BroadcastNestedLoopJoinExec(
    left: SparkPlan,
    right: SparkPlan,
    buildSide: BuildSide,
    joinType: JoinType,
    condition: Option[Expression]) extends BaseJoinExec with JoinCodegenSupport
```

执行方式：将 Build 侧广播到所有 Executor，Stream 侧逐行遍历 Build 侧全集，对满足条件的组合输出。

对于 10 亿行 Stream × 10 万行 Build = 1014 次条件检查——非常慢。但这是处理非等值 Join（如 `ON t1.a BETWEEN t2.start AND t2.end`）的唯一方式。

**优化**：WholeStageCodegen 将嵌套循环融合为单循环，条件检查被 inline，没有虚函数开销。但即使如此，N2 的内存扫描无法避免。

### 14.5 Cartesian Product (CP, Shuffle-and-Replicate NLJ)

CP 是 BNLJ 的分布式变体——不需要广播一侧。两侧被复制到所有节点（通过 Shuffle），然后每个节点对子集做嵌套循环。

仅支持 InnerLike Join。占用最大的网络带宽和内存开销——只作为最后回退。

### 14.6 HashedRelation — Hash Table 的内部机制

五条算法中有三条（BHJ、SHJ、部分 BNLJ）依赖 Hash Table。Spark 在 `HashedRelation` 中统一了这个概念：

```scala
// HashJoin.scala
trait HashJoin {
  // Build 侧建立 Hash Table
  protected def buildHashedRelation(iter: Iterator[InternalRow]): HashedRelation = ...

  // Stream 侧在 Hash Table 中探测（WholeStageCodegen 调用）
  protected def join(streamIter: Iterator[InternalRow], hashedRelation: HashedRelation, ...)
}
```

Hash Table 的物理存储是 `BytesToBytesMap`（第 12 章讨论过）。关键特征：

1. **开放寻址**（open addressing）：无链表指针追逐，探测在连续内存中
2. **线性探测**（linear probing）：hash 冲突 → 检查相邻 slot
3. **连续存储**：key 和 value 在同一个 page 中相邻存储，一次 cache line 可以读入 key+value
4. **Bloom Filter**（可选）：如果 Join Key 选择性很高（很多 keys 不匹配），在 Hash Table 前加一个 Bloom Filter，快速跳过不匹配行

Hash Table 对 **数据倾斜** 敏感——如果某些 Join Key 有极多匹配行，线性探测在这些区域产生长链。AQE 可以检测到倾斜并在 Physical Planning 中启用 `isSkewJoin = true`，将倾斜 key 的行拆分到多个 task。

## 关键代码片段

### 示例：SMJ 的归并循环核心

```scala
// SortMergeJoinScanner (SortMergeJoinExec 的内部类)
// 简化版归并逻辑：
while (leftIter.hasNext && rightIter.hasNext) {
  val cmp = leftKeyOrdering.compare(leftRow, rightRow)
  if (cmp < 0) {
    processLeftRow(leftRow)  // joinType 决定行为
    leftIter.next()
  } else if (cmp > 0) {
    processRightRow(rightRow)  // joinType 决定行为
    rightIter.next()
  } else {
    // 匹配！输出所有匹配的组合
    // 因为可能有重复 key，需要输出左组 × 右组
    matched = true
    joinType match {
      case Inner | LeftOuter | RightOuter | FullOuter =>
        outputAllMatches(leftGroup(), rightGroup())
      case LeftSemi => outputOneMatch(leftRow)
      ...
    }
    leftIter.next(); rightIter.next()
  }
}
```

### 示例：BHJ 的异步广播

```scala
// BroadcastExchangeExec 的核心
override def doExecuteBroadcast[T](): broadcast.Broadcast[T] = {
  // 在 DAGScheduler 的 job 中异步执行
  val relation = HashedRelation(iter, buildKeys, ...)
  // 序列化并广播到所有 Executor
  sparkContext.broadcast(relation.asInstanceOf[T])
}
```

## 硬件视角

**BHJ 的 Cache 效率**：

Hash Table 探测是这个行星上最 hot 的代码路径。每次探测：
1. 对 Stream Row 的 Join Key 计算 hash（Murmur3）：约 10-20 cycle
2. 定位到 page + offset：1 次数组访问
3. 比较 key bytes（`memcmp`）：4-8 bytes 比较 = 1-2 cycle

对于典型的 BHJ（1GB Hash Table, 10 亿行 Stream）：
- L3 cache 约 40MB——Hash Table 只部分在缓存中
- 对 L3 的命中率取决于 Join Key 的 "引用局部性"（热度分布）
- 80-20 定律：Hash Table 中 20% 的热点 key 占了 80% 的探测，这些热点 key 在 L2/L3 中 → 低延迟
- 但剩余的 80% 的 key 分散在 1GB → 40MB L3 中 → 每次探测可能 miss

**SMJ 的 I/O 模式**：

SMJ 的性能由 **External Sort** 的 I/O 模式决定。`UnsafeExternalSorter` 产生的是 **顺序读写**——每个 spill 文件写入后顺序读取。对于 HDD（旋转磁盘），这是生命线（顺序 150MB/s vs 随机 1MB/s）。对于 NVMe SSD（混合 3000MB/s，随机 1000MB/s），差距小但仍然显著。

SMJ 的另一个微妙硬件效应：**归并扫描天然支持 I/O 预取**（prefetch）。因为两侧都顺序扫描，OS 的 read-ahead 机制自动预取后续页——排序文件 99% 的读取在 page cache 中被捕获。

**BNLJ 的指令级瓶颈**：

BNLJ 对条件求值的依赖使它成为 **指令级并行度最低** 的 Join 算法。对于 `ON t1.colA > t2.colB AND function(t1.colC) = t2.colD`——每次不等式检查都有分支（if condition），条件中有函数调用（`function`）。CPU 的分支预测在这里无法学习模式（因为嵌套循环产生的比较是无规律的）。

## AI 时代反思

Join 是"将关系连接起来"的操作——这是数据库和 LLM 之间最根本的差异。LLM 在长文本上下文中的"关联"是模糊的、in-context 的、基于相似度的，而数据库的 Join 是精确的、基于键的、确定性的。

这种差异制造了一个尴尬的场景：**LLM Agent 擅长"自然语言→理解用户想连接什么"，但生成正确的 JOIN SQL 需要精确的表元数据**。

将第 8 章的"SessionCatalog 作为 RAG"思路扩展：Agent 访问数据库时的最佳流程可能是：
1. LLM 理解用户意图 → 识别出需要连接哪些实体
2. LLM 从 SessionCatalog 中检索表结构（列名、类型、统计信息）
3. LLM 生成候选 JOIN 条件
4. 数据库优化器验证这些条件的语义（FK 约束、类型匹配、左/右侧）
5. Agent 只向用户展示验证通过的方案

这比"LLM 独立写 SQL"安全且准确。第 14 章的主题——五路 Join 算法的物理实现——在 AI 场景中的价值是：AI Agent 不需要理解 BHJ vs SMJ，它只需要理解"这两个表可以 JOIN 吗？"和"用哪个 key？"。

## 源码导航

| 文件 | 关键内容 | 行号参考 |
|------|---------|---------|
| `sql/core/src/main/scala/org/apache/spark/sql/execution/joins/BroadcastHashJoinExec.scala` | BHJ 实现，HashedRelationBroadcastMode，broadcast distribution 需求，Null-Aware Anti Join | 40 (类定义), 67 (requiredChildDistribution), 77 (outputPartitioning) |
| `sql/core/src/main/scala/org/apache/spark/sql/execution/joins/ShuffledHashJoinExec.scala` | SHJ 实现，build 侧 threshold 判断 |
| `sql/core/src/main/scala/org/apache/spark/sql/execution/joins/SortMergeJoinExec.scala` | SMJ 实现，归并扫描循环，outputOrdering 处理 | 39 (类定义), 52 (outputOrdering), 73 (getKeyOrdering) |
| `sql/core/src/main/scala/org/apache/spark/sql/execution/joins/BroadcastNestedLoopJoinExec.scala` | BNLJ 实现，嵌套循环，非等值 Join 支持 |
| `sql/core/src/main/scala/org/apache/spark/sql/execution/joins/HashJoin.scala` | HashJoin trait，HashedRelation 构建和探测抽象 |
| `sql/core/src/main/scala/org/apache/spark/sql/execution/joins/BaseJoinExec.scala` | 所有 Join 的基类 |
| `sql/core/src/main/scala/org/apache/spark/sql/execution/joins/JoinCodegenSupport.scala` | Join 的 Codegen 支持 |
| `sql/core/src/main/scala/org/apache/spark/sql/execution/exchange/BroadcastExchangeExec.scala` | 异步广播执行，HashedRelation 序列化 |
| `sql/core/src/main/scala/org/apache/spark/sql/execution/SparkStrategies.scala` | JoinSelection 规则（第 11 章已讨论） |
