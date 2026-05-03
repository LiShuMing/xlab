# 第 16 章：Sort & Window 算子 — 排序与窗口的物理实现

## 设计动机

排序（Sort）和窗口（Window）是 SQL 中两簇紧密相关但却有本质区别的操作。

Sort 是单向操作——输入一堆行，输出按某列排序的行集合。它的核心挑战是 **内存不足时的溢写（Spill）**——如果数据是 100GB 而内存只有 4GB，你必须做 External Sort（外部排序）。

Window 是"带分组的成组计算"——输入按 partition key 分组，组内按 order key 排序，然后在每组内对每行计算一个窗口函数值。典型的 `ROW_NUMBER() OVER (PARTITION BY dept ORDER BY salary)` 需要: 分组（PARTITION BY）+ 排序（ORDER BY）+ 逐行编号。Window 的挑战不在于排序本身（排序可以复用 SortExec），而在于 **Frame（窗口框架）的高效求值**——"当前行与前 2 行和后 1 行之间的 SUM"这种动态边界，朴素实现是 O(N³)。

Spark 将 Sort 和 Window 设计为两个独立的物理算子——`SortExec` 和 `WindowExec`。SortExec 依赖 Tungsten 的外部排序基础设施（`UnsafeExternalRowSorter`），WindowExec 依赖 SortExec 保证输入有序，再通过一簇 `WindowFunctionFrame` 实现来高效处理各种窗口框架。

本章先讨论 SortExec 的排序机制（含 prefix 优化和 radix sort），然后深入 WindowExec 的五种 Frame 类型和求值策略，最后从硬件视角审视两者的 I/O 行为。

## 核心原理

### 16.1 SortExec — 外部排序的物理算子

SortExec 是排序的物理算子。它的核心结构很简单——创建 sorter，喂入所有行，取出有序行：

```scala
// SortExec.scala:40
case class SortExec(
    sortOrder: Seq[SortOrder],
    global: Boolean,          // true = 全局排序 (需要 Shuffle)
    child: SparkPlan,
    testSpillFrequency: Int = 0)
  extends UnaryExecNode with BlockingOperatorWithCodegen {

  override def outputOrdering: Seq[SortOrder] = sortOrder
  override def outputPartitioning: Partitioning = child.outputPartitioning

  override def requiredChildDistribution: Seq[Distribution] =
    if (global) OrderedDistribution(sortOrder) :: Nil
    else UnspecifiedDistribution :: Nil
}
```

`global=true` → 声明 `OrderedDistribution(sortOrder)` → `EnsureRequirements` 会插入 Range Partitioning 的 Shuffle（或识别已有的 RangePartitioning）。`global=false` → 仅在 partition 内部排序，不需要任何 Shuffle。

**外部排序的核心——UnsafeExternalRowSorter**：

```scala
// SortExec.scala:76
def createSorter(): UnsafeExternalRowSorter = {
  val ordering = RowOrdering.create(sortOrder, output)

  // Prefix 优化: 对排序列的前缀做快速比较
  val boundSortExpression = BindReferences.bindReference(sortOrder.head, output)
  val prefixComparator = SortPrefixUtils.getPrefixComparator(boundSortExpression)

  // 判断能否使用 Radix Sort
  val canUseRadixSort = enableRadixSort && sortOrder.length == 1 &&
    SortPrefixUtils.canSortFullyWithPrefix(boundSortExpression)

  // Prefix 计算器: 从每行提取排序键的二进制前缀
  val prefixExpr = SortPrefix(boundSortExpression)
  val prefixProjection = UnsafeProjection.create(Seq(prefixExpr))
  val prefixComputer = ...

  rowSorter = UnsafeExternalRowSorter.create(
    schema, ordering, prefixComparator, prefixComputer, pageSize, canUseRadixSort)
}
```

**Sort Prefix 优化**：

`SortPrefix` 将排序键（如 `BIGINT` 列）转换为一个 8 字节的"可比较前缀"——对于数值类型，它在二进制层面已经是可比较的（double 需要翻转符号位）。对于 String 类型，取前 8 字节作为 prefix。

比较两行时：
1. **先比 prefix**（8 字节整数比较，1-2 cycle）
2. 只有 prefix 相等时，才回退到完整的 `RowOrdering.compare`（包含 null check、类型转换）

在 key 分布均匀的场景下，prefix 比较可以消除 >99% 的完整比较。

**Radix Sort 的条件**：

```scala
val canUseRadixSort = enableRadixSort && sortOrder.length == 1 &&
  SortPrefixUtils.canSortFullyWithPrefix(boundSortExpression)
```

Radix Sort 要求：
1. 只在单列排序时可用
2. 列的类型支持"prefix 完全决定排序结果"——例如 `BIGINT`、`INT`、`DATE`（本质是 int），但不适用于 `DECIMAL(38,18)`（128-bit，8 字节 prefix 不够）
3. `enableRadixSort = true`（默认 true）

当条件满足时，排序复杂度从 O(N log N)（TimSort）降为 O(N)（Radix Sort）——在 1 亿行输入上约 3-5 倍提速。

**Codegen 中的 SortExec**：

SortExec 作为 BlockingOperatorWithCodegen，在 WholeStageCodegen 中的行为是"先收集，再排序，再输出"：

```java
// 生成的代码伪码：
if (needToSort) {
  // 第 1 遍: 收集所有子节点输出到 sorter
  addToSorter();  // 调用 child.produce() → 每行 insertRow(sorter)
  // 第 2 遍: 排序
  sortedIterator = sorter.sort();
  needToSort = false;
}
// 输出有序行
while (sortedIterator.hasNext()) {
  UnsafeRow outputRow = sortedIterator.next();
  consume(outputRow);  // 传递给父节点
}
```

注意 SortExec 的 `doConsume` 极其简单——只做 `sorter.insertRow(row)`。排序逻辑完全封装在 `UnsafeExternalRowSorter` 中。

### 16.2 外部排序的 Spill 机制

当数据量超过内存时，`UnsafeExternalRowSorter` 将数据溢写到磁盘——这就是 External Sort（外部排序）：

```
阶段 1: 内存中累积行 → 构建排序 run
阶段 2: 当内存满时:
    - 对内存中的行排序 (TimSort)
    - 将排序后的 run 写入磁盘 (spill file)
    - 清空内存
阶段 3: 重复 1-2 直到所有输入处理完毕
阶段 4: 对所有 spill files 做 k-way merge
    - 每个 file 打开一个 reader
    - 使用 PriorityQueue 归并输出
```

这与数据库教科书的 External Merge Sort 完全一致。关键参数：
- **page size**：单次内存分配的单位（默认 64MB）
- **spill file 数量**：100GB 数据 / 4GB 内存 ≈ 25 个 spill files
- **k-way merge 的 k**：25，一个 PriorityQueue 完全可以高效处理

### 16.3 WindowExec — 窗口函数的物理执行

WindowExec 是"半阻塞"（semi-blocking）算子——它在一个 Window Partition 内收集所有行、构建 Frame 并计算，然后才输出该 Partition 的结果：

```scala
// WindowExec.scala:87
case class WindowExec(
    windowExpression: Seq[NamedExpression],
    partitionSpec: Seq[Expression],
    orderSpec: Seq[SortOrder],
    child: SparkPlan) extends WindowExecBase
```

**执行流程**：

```
对于每个 RDD partition（物理 partition）:
  while (还有输入行) {
    1. 识别下一个 Window Partition (partitionSpec 相同的行)
    2. 将该 Window Partition 的所有行收集到 buffer (ExternalAppendOnlyUnsafeRowArray)
    3. 对该 Partition 的所有 Frame 调用 prepare(buffer)
    4. 逐行迭代:
       for (rowIndex = 0; rowIndex < buffer.length; rowIndex++)
         - 对每个 Frame 调用 write(rowIndex, currentRow)
         - resultProjection.join(currentRow, windowFunctionResult) → 输出
    5. clear buffer
  }
```

```scala
// WindowEvaluatorFactory.scala:99
private[this] def fetchNextPartition(): Unit = {
  val currentGroup = nextGroup.copy()
  buffer.clear()

  // 收集当前 Window Partition 的所有行
  while (nextRowAvailable && groupEqualityCheck(nextGroup, currentGroup)) {
    buffer.add(nextRow)
    fetchNextRow()
  }

  // 准备所有 Frame
  var i = 0
  while (i < numFrames) {
    frames(i).prepare(buffer)
    i += 1
  }

  rowIndex = 0
  bufferIterator = buffer.generateIterator()
}
```

**buffer 的 Spill**：`ExternalAppendOnlyUnsafeRowArray` 是一个支持溢写的行数组——它在内存中维护一个 `ArrayBuffer[UnsafeRow]`，当行数超过阈值时溢写到磁盘。这与 HashAggregate 的 spill 机制类似，但更简单（因为 Window 只需要按索引随机访问行，不需要按 key 查找）。

```
ExternalAppendOnlyUnsafeRowArray:
  - inMemoryThreshold: 内存中最多保留行数 (spark.sql.windowExec.buffer.in.memory.threshold, 默认 4096)
  - 超过阈值: 将当前 buffer 溢写到 disk，清空内存，继续追加
  - generateIterator(): 返回一个合并了内存和磁盘数据的迭代器
```

### 16.4 WindowFunctionFrame — 五种框架的求值策略

`WindowFunctionFrame` 是窗口框架计算的抽象——它将"窗口框架的求值策略"从"窗口算子的调度逻辑"中分离：

```scala
// WindowFunctionFrame.scala:39
abstract class WindowFunctionFrame {
  def prepare(rows: ExternalAppendOnlyUnsafeRowArray): Unit
  def write(index: Int, current: InternalRow): Unit
}
```

窗口框架类型由上下界（lower bound / upper bound）定义。一条 `SUM(amount) OVER (PARTITION BY dept ORDER BY date ROWS BETWEEN 1 PRECEDING AND 1 FOLLOWING)` 包含了 partition（dept）、order（date）和 frame（ROWS 1 PRECEDING AND 1 FOLLOWING）。Spark 将帧分为五种，每种有不同的优化策略：

#### 1. UnboundedWindowFunctionFrame（整个 Partition）

```sql
-- BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
-- 或者没有 ORDER BY（默认就是整个 partition）
```

策略：**在 prepare 阶段一次性计算**。遍历 partition 的所有行一次，调用 `processor.update(row)`，最后 `processor.evaluate(target)`。`write()` 是空操作——因为所有行的计算结果相同。

时间复杂度：O(N)，N = partition 行数。最优情况。

#### 2. UnboundedPrecedingWindowFunctionFrame（累积框架）

```sql
-- ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
-- 最常见的场景: ROW_NUMBER(), running SUM
```

策略：**流式累积（streaming evaluation）**。每次 `write()` 只添加新进入框架的行到 processor（不需要删除）。无需维护 buffer。利用聚合函数的可加性（additivity），增量更新。

时间复杂度：O(N)。同样是 N，但比 Unbounded 需要 N 次 evaluate（每行一次）。

#### 3. UnboundedFollowingWindowFunctionFrame（递减框架）

```sql
-- ROWS BETWEEN CURRENT ROW AND UNBOUNDED FOLLOWING
```

策略：**反向流式剪裁**。每次 `write()` 从 processor 中移除已离开框架的行。但因为聚合函数不总是支持"减法"（如 `MAX` 不能在移除一行后恢复前一个 MAX），所以需要 **完全重算**——O(N²/2)。

这是最贵的框架类型之一，注释中明确写了 "This is a very expensive operator to use, O(n * (n - 1) / 2)"。

#### 4. SlidingWindowFunctionFrame（滑动框架）

```sql
-- ROWS BETWEEN 1 PRECEDING AND 1 FOLLOWING
-- ROWS BETWEEN 2 PRECEDING AND 1 PRECEDING
```

策略：**双端队列（Deque）维护滑动窗口**。每行：
1. 从 buffer 的前端移除已离开下界的行（`buffer.remove()`）
2. 在 buffer 的后端追加新进入上界的行（`buffer.add(row)`）
3. 如果 buffer 有变化 → 重算 processor（遍历 buffer 中的所有行）

时间复杂度：O(N × W)，其中 W = 平均 window 宽度。当 W 远小于 N 时高效；如果窗口接近整个 partition → 近似 O(N²)。

#### 5. OffsetWindowFunctionFrame（偏移框架）

```sql
-- LEAD(col, 2), LAG(col, 1), NTH_VALUE(col, 3)
```

策略：**单行偏移**。没有"框架"概念——只定位到 offset 行并取其值。

```scala
// WindowFunctionFrame.scala:236
// FrameLessOffsetWindowFunctionFrame:
// 对于 LEAD(expr, offset): 读取 input[inputIndex + offset] 的值
// 对于 LAG(expr, offset): 读取 input[inputIndex - offset] 的值
// 超出范围 → 使用 default 值 (NULL 或用户指定)
```

四种子变体：
- `FrameLessOffsetWindowFunctionFrame`：LEAD/LAG 的基础版本
- `UnboundedOffsetWindowFunctionFrame`：NTH_VALUE + UNBOUNDED FOLLOWING（所有行结果相同，prepare 一次计算）
- `UnboundedPrecedingOffsetWindowFunctionFrame`：NTH_VALUE + UNBOUNDED PRECEDING + CURRENT ROW
- IGNORE NULLS 变体：LEAD/LAG IGNORE NULLS 需要跳过 NULL 行—这是更复杂的逻辑

**BoundOrdering — Row vs Range**：

框架边界有两种语义。`RowBoundOrdering` 按行号比较（position-based），`RangeBoundOrdering` 按 ORDER BY 表达式的实际值比较（value-based）：

```sql
-- ROW based: 1 PRECEDING = 前 1 行（不管值大小）
-- RANGE based: 1 PRECEDING = 当前行 ORDER BY 值 - 1（可能有 0 行或多行）
```

Range 模式要求 ORDER BY 只有一个数值列——因为它需要做"值 - offset"计算来确定边界。Range 模式下，同一 ORDER BY 值的多行共享相同的框架边界。

### 16.5 WindowExec 与 SortExec 的协作

WindowExec 依赖子节点（child）提供已排序和分区的数据：

```
物理计划中的典型结构:
WindowExec(PARTITION BY dept ORDER BY salary)
+- SortExec(sortOrder=[dept ASC, salary ASC])
   +- ShuffleExchangeExec(HashPartitioning(dept))
      +- <upstream>
```

排序和分区通过两个层面保证：
1. **Partitioning**：`EnsureRequirements` 为 `PARTITION BY dept` 插入 `HashPartitioning(dept)` 的 Shuffle
2. **Ordering**：`SortExec` 提供 `outputOrdering = [dept ASC, salary ASC]`

WindowExec 不需要再排序——它只需按排好的顺序扫描，当 partition key 变化时标识"下一个 Window Partition 的边界"。

### 16.6 Window Group Limit (Window Top-K)

`WindowGroupLimitExec` 是 Spark 4.0 引入的优化——处理 `ROW_NUMBER() ... WHERE rn <= N` 的模式：

```
WindowGroupLimitExec(partitionSpec=[dept], orderSpec=[salary DESC], limit=3)
```

它的优化点是：**不需要对整个 partition 排序**。只需维护一个优先队列（大小为 N），在扫描过程中保留前 N 个元素——类似 Top-K 堆算法。这比"全量排序 + 复制后筛选"省了 O(K log N) → O(K log K) 的排序开销（K = 行数，N = limit）。

## 关键代码片段

### 示例：RowOrdering 的生成

```scala
// RowOrdering 将 SortOrder 序列编译为比较器
val ordering = RowOrdering.create(
  Seq(SortOrder(colA, Ascending), SortOrder(colB, Descending)),
  childOutput)
// 生成的比较逻辑 (伪码):
// int cmp = compareNullFirst(colA1, colA2, Ascending)
// if (cmp != 0) return cmp
// return compareNullLast(colB1, colB2, Descending)
```

### 示例：窗口函数的滑动框架求值

```scala
// SlidingWindowFunctionFrame.write() 的核心:
// 1. 移除离开下界的行
while (!buffer.isEmpty && lbound.compare(buffer.peek(), lowerBound, current, index) < 0) {
  buffer.remove()
  lowerBound += 1
}
// 2. 添加上界新进入的行
while (nextRow != null && ubound.compare(nextRow, upperBound, current, index) <= 0) {
  buffer.add(nextRow.copy())
  nextRow = getNextOrNull(inputIterator)
  upperBound += 1
}
// 3. 如果 buffer 变化了 → 重算聚合
if (bufferUpdated) {
  processor.initialize(input.length)
  buffer.forEach(row => processor.update(row))
  processor.evaluate(target)
}
```

## 硬件视角

**外部排序的 I/O 模式**：

External Sort 的 I/O 是 Spark 所有操作中最"干净"的顺序读写模式：

1. **Spill 写**：每个 run 排序后顺序写入磁盘——NVMe SSD: 3000MB/s，HDD: 150MB/s
2. **Merge 读**：k 个 spill files 同时顺序读取——k-way merge 的 I/O 是带宽绑定的（bandwidth-bound），不是 IOPS 绑定的
3. **OS Page Cache 效应**：Spill files 写完后立即被读取（在 merge 阶段），此时文件内容大概率还在 page cache 中（如果没被 evict）。Page cache hit → merge 阶段实际上可能是 CPU-bound（只是 comparison + memcpy），没有物理 I/O

对于 100GB 数据 / 4GB 内存的场景：
- 约 25 个 spill runs，每个约 4GB
- 写 I/O: 100GB write / 3000MB/s ≈ 33 秒（NVMe）
- 读 I/O (merge): 如果 page cache miss → 100GB read / 3000MB/s ≈ 33 秒
- 但如果 page cache 命中（25 × 4GB > 内存 的情况下无法全部 cache），部分 spill files 会被 evict
- 实际 I/O 时间：约 50-60 秒（含 spill write + partial cache miss 的 read）

**Prefix 比较的 CPU 效益**：

对于 `SORT BY BIGINT_COL` 的 10 亿行：
- 无 Prefix: 10 亿次完整 RowOrdering.compare ≈ 10 亿次 null check + getLong + comparison ≈ 50-80 cycles/op
- 有 Prefix: 10 亿次 8-byte 整型比较 ≈ 1-2 cycles/op（Prefix 筛选掉 99%）
- 在 prefix 相等的 1% 回退到完整 compare

累计节省：~40 billion cycles ≈ 13 秒 @ 3GHz。在 10 亿行排序（总计 ~200 秒 I/O + 计算）中约 6% 提升。

**WindowExec 的内存局部性**：

Window 的 buffer (`ExternalAppendOnlyUnsafeRowArray`) 在内存中的模式：
- `prepare` 阶段：线性扫描 buffer → 所有行的所有列被顺序访问 → L1/L2 cache 高命中率
- `write` 阶段：对 buffer 的随机索引访问 → `buffer.get(rowIndex)` → 如果 buffer 在 L3 中，这是 L3 hit；如果 buffer 部分在磁盘 → 随机 I/O

这就是为什么 WindowExec 的 buffer 要尽量保持在内存中——磁盘溢出的随机访问是灾难性的（NVMe 随机读 ~50MB/s vs 顺序读 3000MB/s）。

## AI 时代反思

窗口函数是 LLM 最容易写出"语法正确但逻辑错误"的 SQL 领域。因为窗口函数涉及两个 LLM 不擅长的事情：

1. **严格的排序和分区语义**：`PARTITION BY` 决定"和哪些行比较"，`ORDER BY` 决定"以什么顺序比较"，`ROWS/RANGE BETWEEN` 决定"比较的范围"——三者交叉，14 种常用组合。LLM 在 `RANK()` vs `DENSE_RANK()` vs `ROW_NUMBER()` 之间的混淆率很高。

2. **隐含的执行代价**：`RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW` 的语义是"所有 ORDER BY 值 <= 当前行的行"——如果 ORDER BY 不是唯一的，这个范围可能包含大量行。LLM 从不考虑这种"组合语义的隐含 O(N²) 代价"。

一个值得思考的方向：**LLM 最适合的窗口函数场景不是写 SQL，而是解释 SQL**。用户问"这个窗口函数为什么返回这个值？"——LLM 读取 SQL 定义，读取数据样本，逐行解释哪个行的哪些值被纳入了窗口框架——这是一个"追踪型"任务，LLM 的文本理解能力恰好适用。这比 LLM 自己生成窗口 SQL 的准确率高得多。

另一个方向：**LLM 辅助 Window Function 的优化配置**。对于复杂的大规模窗口查询（TPC-DS Q67 有 7 个窗口函数），选择合适的 `spill threshold`、`inMemoryThreshold`、是否启用 `spill` 需要考虑 partition 分布。LLM 可以从查询模式 + 列统计中推断出"这个 partition 的 size 分布"→ 推荐合理的 buffer 内存配置 → 减少 spill 次数。这是一种"ML-based 配置调优"，而 LLM 的自然语言理解能力让它能从 explain plan 文本中提取模式（而不只是从数字中）。

## 源码导航

| 文件 | 关键内容 | 行号参考 |
|------|---------|---------|
| `sql/core/src/main/scala/org/apache/spark/sql/execution/SortExec.scala` | SortExec 实现，createSorter (prefix + radix sort)，doProduce/doConsume for codegen，global vs local sorting | 40 (case class), 49 (outputOrdering), 55 (requiredChildDistribution), 76 (createSorter), 141 (doProduce), 189 (doConsume) |
| `sql/core/src/main/scala/org/apache/spark/sql/execution/window/WindowExec.scala` | WindowExec 实现，doExecute，WindowEvaluatorFactory 入口 | 87 (case class), 97 (doExecute) |
| `sql/core/src/main/scala/org/apache/spark/sql/execution/window/WindowEvaluatorFactory.scala` | WindowEvaluatorFactory，WindowPartitionEvaluator，fetchNextPartition 分组收集逻辑，buffer spill 参数 | 28 (class), 50 (eval), 99 (fetchNextPartition) |
| `sql/core/src/main/scala/org/apache/spark/sql/execution/window/WindowFunctionFrame.scala` | WindowFunctionFrame 抽象，五种 Frame 实现：OffsetWindowFunctionFrameBase (LEAD/LAG/NTH_VALUE)，SlidingWindowFunctionFrame，UnboundedWindowFunctionFrame，UnboundedPrecedingWindowFunctionFrame，UnboundedFollowingWindowFunctionFrame | 39 (abstract class), 85 (OffsetWindowFunctionFrameBase), 236 (FrameLessOffsetWindowFunctionFrame), 347 (UnboundedOffsetWindowFunctionFrame), 390 (UnboundedPrecedingOffsetWindowFunctionFrame), 422 (SlidingWindowFunctionFrame), 517 (UnboundedWindowFunctionFrame), 565 (UnboundedPrecedingWindowFunctionFrame), 644 (UnboundedFollowingWindowFunctionFrame) |
| `sql/core/src/main/scala/org/apache/spark/sql/execution/window/WindowGroupLimitExec.scala` | WindowGroupLimitExec，Top-K 堆优化，Spark 4.0 引入 | |
| `sql/catalyst/src/main/scala/org/apache/spark/sql/catalyst/expressions/SortOrder.scala` | SortOrder 定义，Ascending/Descending，NullsFirst/NullsLast | |
| `sql/core/src/main/java/org/apache/spark/sql/execution/UnsafeExternalRowSorter.java` | UnsafeExternalRowSorter，外部排序实现，spill 和 k-way merge | |
| `sql/core/src/main/scala/org/apache/spark/sql/execution/ExternalAppendOnlyUnsafeRowArray.scala` | ExternalAppendOnlyUnsafeRowArray，Window buffer 的溢写支持 | |
