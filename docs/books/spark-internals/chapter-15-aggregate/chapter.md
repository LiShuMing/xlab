# 第 15 章：Aggregate 算子 — Hash 与 Sort 的双模聚合引擎

## 设计动机

聚合（Aggregation）是 SQL 中仅次于 Join 的第二大计算密集型操作。一条 `SELECT region, COUNT(*), SUM(amount) FROM orders GROUP BY region` 需要在所有行之间按 key 分组，然后在每组内执行计算——这是一个天然的"分而治之"问题。

Spark 的聚合算子面临一个独特的挑战：**聚合函数类型的两极化**。

一方面，我们有 `COUNT(*), SUM(col), AVG(col), MIN(col), MAX(col)`——这些是"表达式型"聚合（DeclarativeAggregate），它们的更新逻辑可以用 Catalyst 表达式描述，因此可以参与 WholeStageCodegen。另一方面，我们有 `COLLECT_LIST(col), histogram(col)` 以及用户自定义的 UDAF——它们的中间状态是任意 Java 对象（`java.util.ArrayList`, 自定义 class），无法用 UnsafeRow 表示，无法 codegen。

这种分裂导致 Spark 不能只有一个聚合算子。它需要三套：

| 算子 | 内部结构 | 适用场景 |
|------|---------|---------|
| HashAggregateExec | UnsafeFixedWidthAggregationMap (Tungsten) | 所有聚合函数都支持 UnsafeRow buffer(DeclarativeAggregate) |
| ObjectHashAggregateExec | ObjectAggregationMap (Java HashMap) | 包含 TypedImperativeAggregate(UDAF 等) |
| SortAggregateExec | 外部排序 + 归并聚合 | 排序输入可用 或 强制 fallback |

三条路径的共同抽象在 `AggregationIterator`——它定义了 `processRow`（如何更新聚合 buffer）和 `generateOutput`（如何输出最终结果）的生成逻辑。但每条路径的"分组"机制完全不同：Hash 用散列，Sort 用排序。

本章从**执行模式**（Partial↔Final 的分阶段设计）、**内存结构**（Tungsten hash map 的聚合 buffer 布局）、**双模切换**（Hash 溢出到 Sort 的回退）以及 **Codegen 的聚合路径**四个维度，逐层拆解。

## 核心原理

### 15.1 AggregateMode — 聚合执行的四种模式

在 physical planning 阶段，`AggUtils.planAggregateWithoutDistinct` 将一个 Logical Aggregate 拆为两个物理算子——Partial 和 Final，中间用 Shuffle 连接：

```scala
// AggUtils.scala:126
def planAggregateWithoutDistinct(...): Seq[SparkPlan] = {
  // 1. Partial Aggregation: 在各 partition 内预聚合
  val partialAggregateExpressions = aggregateExpressions.map(_.copy(mode = Partial))
  val partialAggregate = createAggregate(
    groupingExpressions = groupingExpressions,
    aggregateExpressions = partialAggregateExpressions, ...)

  // 2. Final Aggregation: 合并 Partial 输出，计算最终结果
  val finalAggregateExpressions = aggregateExpressions.map(_.copy(mode = Final))
  val finalAggregate = createAggregate(
    requiredChildDistributionExpressions = Some(groupingAttributes),
    groupingExpressions = groupingAttributes,
    aggregateExpressions = finalAggregateExpressions, ...)
}
```

这意味着每条聚合函数在生命周期中经历不同的 `AggregateMode`：

| Mode | 输入来源 | 做什么 | Buffer 内容 | 输出 |
|------|---------|--------|------------|------|
| **Partial** | 原始表数据 | 初次聚合 | 部分聚合状态 (e.g. partial_sum, partial_count) | Partial buffer + grouping key |
| **PartialMerge** | 多个 Partial 输出 | 合并同 key 的 Partial buffer | 合并后的部分聚合状态 | 合并后的 Partial buffer + grouping key |
| **Final** | PartialMerge 输出 | 计算最终结果 | 最终聚合结果 (e.g. sum/count → avg) | 最终结果列 |
| **Complete** | 原始表数据 | 一步到位 | 完整聚合结果 | 最终结果列 |

典型的两阶段聚合数据流：

```
Partial HashAggregate          Shuffle (HashPartitioning by key)        Final HashAggregate
[part1: {A: (sum=10,cnt=2)}]   --->  [partition for key A]  --->       [A: sum=10+15=25, cnt=2+3=5 → avg=5]
[part2: {A: (sum=15,cnt=3)}]          [all A rows arrive]               [A: avg=5]
```

**为什么需要 Partial 模式？** 因为 Shuffle 的数据量通常远大于聚合后的数据量。如果在 Shuffle 前先做一次预聚合，可以将 Shuffle 的数据量降低 10-1000 倍。这就是经典的"先 map 端聚合，再 reduce 端聚合"——和 MapReduce 的 Combiner 完全等价。

**Complete 模式**用于无法拆分的聚合函数（如 `COLLECT_LIST`）——SortAggregateExec 中的 `CollectList` 必须看到所有输入行才能返回完整列表，不能分 Partial/Final 两步。

### 15.2 DeclarativeAggregate vs ImperativeAggregate

`AggregateFunction` 的两个子类定义了完全不同的执行路径：

**DeclarativeAggregate**（声明式聚合）——用表达式声明行为：

```scala
// interfaces.scala
trait DeclarativeAggregate extends AggregateFunction {
  def initialValues: Seq[Expression]   // buffer 的初始值表达式
  def updateExpressions: Seq[Expression]  // 如何处理新行
  def mergeExpressions: Seq[Expression]   // 如何合并两个 buffer
  def evaluateExpression: Expression       // 如何计算最终结果
}
```

例如 `Average`（AVG）的实现：
```
initialValues:    [sum=0L, count=0L]
updateExpressions: [sum + input, count + 1]
mergeExpressions:  [sum1 + sum2, count1 + count2]
evaluateExpression: sum / count  // 仅当 mode=Final/Complete 时才计算
```

`Count`、`Sum`、`Min`、`Max` 等内置聚合全是 DeclarativeAggregate。关键优势：**update/merge 表达式可以 inline 到 WholeStageCodegen 生成的 Java 代码中**——没有虚函数调用。

**ImperativeAggregate**（命令式聚合）——用 Java 方法实现：

```scala
trait ImperativeAggregate extends AggregateFunction {
  def initialize(buffer: InternalRow): Unit  // 初始化 buffer
  def update(buffer: InternalRow, input: InternalRow): Unit // 处理新行
  def merge(buffer: InternalRow, input: InternalRow): Unit // 合并 buffer
  def eval(buffer: InternalRow): Any  // 计算最终结果
}
```

`CollectList`、`CollectSet`、所有 `UserDefinedAggregateFunction`（UDAF）都是 ImperativeAggregate。它们的 buffer 可能包含 `java.util.ArrayList`——不能被 UnsafeRow 直接表示，无法 codegen，只能通过 Java 对象操作。

**TypedImperativeAggregate** 进一步加剧了问题——它的中间状态是泛型对象 `T`，需要序列化才能通过 Shuffle 传输：

```scala
// TypedImperativeAggregate.scala
trait TypedImperativeAggregate[T] extends ImperativeAggregate {
  def createAggregationBuffer(): T       // 创建泛型状态对象
  def serialize(buffer: T): Array[Byte]  // Shuffle Write 前序列化
  def deserialize(bytes: Array[Byte]): T  // Shuffle Read 后反序列化
}
```

这就是为什么 Spark 需要 ObjectHashAggregateExec——当聚合中包含 TypedImperativeAggregate 时，buffer 不能是 UnsafeRow，只能用 Java 对象存。

### 15.3 HashAggregateExec — Tungsten 哈希聚合

HashAggregateExec 是 Spark 的主力聚合算子——当所有聚合函数都是 DeclarativeAggregate 时使用。

```scala
// HashAggregateExec.scala:51
case class HashAggregateExec(
    requiredChildDistributionExpressions: Option[Seq[Expression]],
    isStreaming: Boolean,
    numShufflePartitions: Option[Int],
    groupingExpressions: Seq[NamedExpression],
    aggregateExpressions: Seq[AggregateExpression],
    aggregateAttributes: Seq[Attribute],
    initialInputBufferOffset: Int,
    resultExpressions: Seq[NamedExpression],
    child: SparkPlan) extends AggregateCodegenSupport
```

**核心数据结构：UnsafeFixedWidthAggregationMap**

这是 Tungsten 为聚合专门设计的哈希表——键是 grouping key（UnsafeRow），值是聚合 buffer（固定宽度 UnsafeRow）：

```scala
// HashAggregateExec.scala:161
def createHashMap(): UnsafeFixedWidthAggregationMap = {
  val initExpr = declFunctions.flatMap(f => f.initialValues)
  val initialBuffer = UnsafeProjection.create(initExpr)(EmptyRow)
  new UnsafeFixedWidthAggregationMap(
    initialBuffer,          // 模板: 初始聚合 buffer
    bufferSchema,           // 聚合 buffer 的 schema (固定宽度)
    groupingKeySchema,      // Grouping key 的 schema
    TaskContext.get(),
    1024 * 16,              // initial capacity: 16K entries
    TaskContext.get().taskMemoryManager().pageSizeBytes
  )
}
```

关键设计：**固定宽度 buffer**。因为 `UnsafeRow` 的 fixed-length 部分是每个字段占 8 字节，所有 DeclarativeAggregate 的 buffer 字段（sum、count、min、max）都是固定宽度——所以哈希表的 value 区域是等宽的，支持原地更新（in-place update）。

**内存布局**：

```
UnsafeFixedWidthAggregationMap 的一个 page:
[page header]
[key1 (UnsafeRow)] [padding to 8 bytes] [buffer1 (fixed-width UnsafeRow)]
[key2 (UnsafeRow)] [padding to 8 bytes] [buffer2 (fixed-width UnsafeRow)]
...
```

查找流程（在 WholeStageCodegen 生成的 `doConsumeWithKeys` 中）：

```java
// 生成的代码: 处理每行输入
// 1. 计算 grouping key 和 hash
int unsafeRowKeyHash = groupingKey.hashCode();

// 2. 在 hash map 中查找或插入
unsafeRowBuffer = hashMap.getAggregationBufferFromUnsafeRow(groupingKey, unsafeRowKeyHash);

// 3. 更新 buffer (in-place)
// buffer 在 hash map 内部内存中, update 在原地修改
sumColumn = buffer.getLong(sumOffset) + input.getLong(colOffset);
buffer.setLong(sumOffset, sumColumn);
countColumn = buffer.getLong(countOffset) + 1;
buffer.setLong(countOffset, countColumn);
```

**两级 HashMap 优化**（`spark.sql.execution.enableTwoLevelAggMap`）：

对于 Partial 模式且 key 是原始类型（int、long、string），Spark 会在 Tungsten HashMap 前插入一个 **Fast HashMap**：

1. Fast HashMap（RowBasedHashMapGenerator）：针对原始类型 key 的手写 row-based hash map，避免 UnsafeRow 序列化开销。key 直接以原始类型存储，不经过 UnsafeProjection
2. 当 Fast HashMap 中找不到时，回退到标准的 `UnsafeFixedWidthAggregationMap`

```scala
// HashAggregateExec.scala:689
val findOrInsertHashMap: String = {
  if (isFastHashMapEnabled) {
    s"""
       |// 先探测 Fast HashMap
       |fastRowBuffer = fastHashMap.findOrInsert(key1, key2, ...);
       |if (fastRowBuffer == null) {
       |  // 回退到标准 Tungsten HashMap
       |  ${findOrInsertRegularHashMap}
       |}
     """
  } else {
    findOrInsertRegularHashMap
  }
}
```

Fast HashMap 可选的还有一个向量化版本（`VectorizedHashMapGenerator`），内部使用 `ColumnVector` 批量存储——但目前默认为 row-based。

### 15.4 Hash → Sort 的回退机制

哈希聚合有一个根本的限制：当 grouping key 的基数很高时，哈希表可能超过内存。Spark 的处理策略不是直接 OOM——而是 **Hash Map Spill → External Sort → Sort-Based Merge Aggregation**。

详细流程在 `TungstenAggregationIterator` 中：

```
阶段 0: 创建 hash map，开始 Hash-based aggregation
阶段 1: 当 hash map 无法分配新内存时：
    - destructAndCreateExternalSorter()：将 hash map 内容按键排序，溢写到磁盘
    - 清空 hash map，继续处理剩余行
    - 重复阶段 1 直到所有输入处理完毕
阶段 2: 合并所有 spill files → 得到全局有序的 KVIterator
阶段 3: 在有序迭代器上做 Sort-based aggregation
```

```scala
// TungstenAggregationIterator.scala:184
private def processInputs(fallbackStartsAt: (Int, Int)): Unit = {
  while (inputIter.hasNext) {
    val groupingKey = groupingProjection.apply(newInput)
    var buffer = hashMap.getAggregationBufferFromUnsafeRow(groupingKey)
    if (buffer == null) {
      // 内存不够！Spill 当前 hash map
      val sorter = hashMap.destructAndCreateExternalSorter()
      if (externalSorter == null) externalSorter = sorter
      else externalSorter.merge(sorter)
      // 重试分配
      buffer = hashMap.getAggregationBufferFromUnsafeRow(groupingKey)
    }
    processRow(buffer, newInput)
  }
}
```

回退的关键——模式重写：

```scala
// TungstenAggregationIterator.scala:251
private def switchToSortBasedAggregation(): Unit = {
  // 重写 AggregateMode: 因为外部排序后,来自 spill file 的行已经是 Partial 聚合结果
  // Partial → PartialMerge: 需要 merge 而不是 update
  // Complete → Final: 需要用 evaluateExpression 计算最终结果
  val newExpressions = aggregateExpressions.map {
    case agg @ AggregateExpression(_, Partial, _, _, _) => agg.copy(mode = PartialMerge)
    case agg @ AggregateExpression(_, Complete, _, _, _) => agg.copy(mode = Final)
    case other => other
  }
}
```

这种"双模"架构是 Spark 聚合算子的精髓：**Hash 模式快但有内存风险，Sort 模式慢但内存安全**。它在两者之间自动切换，用户透明。

### 15.5 SortAggregateExec — 排序聚合

SortAggregateExec 依赖输入已按 grouping key 排好序——等值 key 的行在输入流中连续出现：

```scala
// SortAggregateExec.scala:34
case class SortAggregateExec(...) extends AggregateCodegenSupport
  with OrderPreservingUnaryExecNode {

  override def requiredChildOrdering: Seq[Seq[SortOrder]] = {
    groupingExpressions.map(SortOrder(_, Ascending)) :: Nil
  }
}
```

SortAggregateExec 声明 `requiredChildOrdering = groupingExpressions`——`EnsureRequirements` 会在子节点不满足排序时插入 `SortExec`。

**执行流程**在 `SortBasedAggregationIterator`：

```
while (inputIter.hasNext) {
  // 读取下一个 group 的所有行
  // 因为已排序，同一个 key 的行连续出现
  processCurrentSortedGroup()
  // → processRow 累积同一 key 的所有行
  // → 输出一行结果
  // → 重置 buffer 为初始值
  next()
}
```

SortAggregateExec 的独特优势是 **不构建哈希表**——它的"分组"靠的是排序后的自然边界。这意味着：
- 内存占用恒定（只需一个 aggregation buffer + 当前 group 的行）
- 不会有哈希冲突导致的性能退化
- 天然支持 Complete 模式（COLLECT_LIST 必须看到所有行→按排序可以一次处理完成）

**Codegen 限制**：SortAggregateExec 目前只支持无 key 的聚合（`groupingExpressions.isEmpty`）进行 codegen。有 key 时使用解释执行（`SortBasedAggregationIterator`）。

### 15.6 ObjectHashAggregateExec — 对象哈希聚合

当聚合中包含 TypedImperativeAggregate 时，buffer 不是 UnsafeRow 而是 `SpecificInternalRow`（包装了 Java 对象）。`ObjectHashAggregateExec` 使用 `ObjectAggregationMap`——基于 Java `HashMap` 但 key 使用 UnsafeRow（为了快速比较）：

```scala
// ObjectHashAggregateExec.scala:60
// 关键差异 vs HashAggregateExec:
// 1. buffer 是 safe row (GenericInternalRow), 不是 UnsafeRow
// 2. 按 entry 数量而非 byte size 判断 spill 阈值
// 3. 一触发 spill 就将所有剩余行都走 sort-based (不构建新 hash map)
// 4. 不支持 CodeGen
```

为什么 spill 一次就全部走 sort？注释解释了——"having too many JVM object aggregation states floating there can be dangerous for GC"。包含 Java 对象的 buffer 被 GC 追踪，如果反复 spill、重建 hash map，GC 可能频繁 Full GC。

**fallback 阈值**由 `spark.sql.objectHashAggregate.sortBased.fallbackThreshold` 控制——按 hash map entry 数量，而非内存字节数。因为"估算任意 JVM 对象的大小"本身就是一件昂贵的事。

### 15.7 聚合 Buffer 的 Codegen 流程

HashAggregateExec 的 WholeStageCodegen 走两条不同的生成路径：有 key 和无 key。

**有 Key 聚合**（`doProduceWithKeys`）：

```
doProduceWithKeys 生成:
  1. 如果启用 Fast HashMap → 创建 Fast HashMap 实例
  2. 创建 UnsafeFixedWidthAggregationMap
  3. 调用 child.produce() → 触发 doConsumeWithKeys 处理每行
     doConsumeWithKeys:
       a. 计算 grouping key (UnsafeProjection)
       b. hashMap.getAggregationBufferFromUnsafeRow(key, hash)
       c. 如果 buffer==null → spill → 重试分配
       d. 更新 buffer (update 表达式, 原地修改)
  4. 调用 finishAggregate() → 获取迭代器并输出

  输出阶段:
    - 如果是 Final/Complete: 对每个 entry 计算 evaluateExpression → 输出
    - 如果是 Partial/PartialMerge: 输出 grouping key + buffer
```

**无 Key 聚合**（`doProduceWithoutKeys`）：

更简单——全局只有一个 aggregation buffer。所有输入行累积到这个 buffer 中，最后输出：

```
doProduceWithoutKeys 生成:
  1. 创建 aggregation buffer 并初始化
  2. 调用 child.produce() → 每行 update 同一 buffer
  3. 计算 evaluateExpression → 输出一行
```

### 15.8 Aggregation Strategy 的决策树

`AggUtils.createAggregate` 是决定使用哪种聚合算子的核心逻辑：

```scala
// AggUtils.scala:69
private def createAggregate(...): SparkPlan = {
  val useHash = Aggregate.supportsHashAggregate(
    aggregateExpressions.flatMap(_.aggregateFunction.aggBufferAttributes),
    groupingExpressions)

  if (useHash && !forceSortAggregate && !forceObjHashAggregate) {
    HashAggregateExec(...)   // 优先: Tungsten Hash
  } else {
    val useObjectHash = Aggregate.supportsObjectHashAggregate(...)
    if (forceObjHashAggregate || (objectHashEnabled && useObjectHash && !forceSortAggregate)) {
      ObjectHashAggregateExec(...)  // 次选: 对象 Hash
    } else {
      SortAggregateExec(...)  // 兜底: Sort 聚合
    }
  }
}
```

决策树：

1. **HashAggregateExec**（首选）：所有聚合函数是 DeclarativeAggregate，且 grouping key 支持 UnsafeRow 固定宽度
2. **ObjectHashAggregateExec**（含 Imperative 时）：`useObjectHashAggregation=true`（默认 false）时使用
3. **SortAggregateExec**（兜底）：以上都不满足时

还有一个 Preparation 阶段的 `ReplaceHashWithSortAgg` 规则——它将无法正确执行 codegen 的 HashAggregateExec 替换为 SortAggregateExec。

### 15.9 Session Window 聚合

Session Window 是一种特殊的聚合——grouping key 中包含一个"session"列，其值不是预先固定的，而是根据时间间隔动态计算。例如：同一个用户的两条记录时间差 < 30 分钟 → 属于同一个 session。

Spark 在 batch 模式使用 `MergingSessionsExec`，在 streaming 模式使用 `UpdatingSessionsExec` + `MergingSessionsExec`：

```scala
// AggUtils.scala:552
private def mayAppendMergingSessionExec(...): SparkPlan = {
  groupingExpressions.find(_.metadata.contains(SessionWindow.marker)) match {
    case Some(sessionExpression) =>
      MergingSessionsExec(
        requiredChildDistributionExpressions = Some(groupingWithoutSessionsAttributes),
        groupingExpressions = groupingAttributes,
        sessionExpression = sessionExpression,
        aggregateExpressions = aggExpressions,
        child = partialAggregate)
    case None => partialAggregate
  }
}
```

Session Window 的关键复杂性：同一 partition 中的两条行可能属于不同 session，而排序后的相邻行需要通过 `SessionWindow.marker` 元数据来动态判断是否合并——这超出了标准 Sort Aggregate 的能力，需要专门的 Session 算子。

## 关键代码片段

### 示例：Partial + Final 两阶段聚合的物理计划

```
用户 SQL: SELECT region, SUM(amount), COUNT(*) FROM orders GROUP BY region

Physical Plan:
*(3) HashAggregate(keys=[region#0], functions=[sum(amount#1), count(1)],
     output=[region#0, sum#5, count#6])
+- ShuffleExchangeExec(HashPartitioning([region#0]), ENSURE_REQUIREMENTS)
   +- *(2) HashAggregate(keys=[region#0],
        functions=[partial_sum(amount#1), partial_count(1)],
        output=[region#0, sum#3, count#4])
      +- *(1) Project [region#0, amount#1]
         +- *(1) FileScan parquet [region#0, amount#1]
```

注意 `*(2)` → `Shuffle` → `*(3)` 的结构。`*(2)` 是 Partial，`*(3)` 是 Final。在 Shuffle 中，数据量从原始的 `amount` 和 `region` 所有列缩减为 `region + sum + count` 三列——这就是 Partial 聚合的价值。

### 示例：聚合 Buffer 的初始化与更新

```scala
// AggregationIterator.scala:302
// 初始化 buffer: 声明式 + 命令式两阶段
protected def initializeBuffer(buffer: InternalRow): Unit = {
  // 1. 声明式聚合: 通过 Projection 计算初始值
  expressionAggInitialProjection.target(buffer)(EmptyRow)
  // 2. 命令式聚合: 调用 initialize(buffer)
  var i = 0
  while (i < allImperativeAggregateFunctions.length) {
    allImperativeAggregateFunctions(i).initialize(buffer)
    i += 1
  }
}
```

## 硬件视角

**HashAggregateExec 的内存访问模式**：

聚合是内存带宽密集型操作。对于 `SELECT key, COUNT(*), SUM(val1), AVG(val2) FROM t GROUP BY key`（10 亿行输入，1000 万唯一 key），内存行为：

1. **Hash Map 构建阶段**：每行输入 → 计算 key hash（Murmur3: ~15 cycles）→ probing UnsafeFixedWidthAggregationMap（1-2 cache miss if cold, 0 if hot key）→ 原地修改 buffer（1-2 cache line write）
2. **热点 Key 效应**：如果 grouping key 分布服从 Zipf 定律（如用户 ID），前 20% 的 key 占 80% 的行。这些热点 key 的 buffer 长期驻留在 L2/L3 cache，其更新几乎是 L1 hit
3. **冷 Key 效应**：长尾 key（1000 万个 key 中的长尾 500 万个）每个只出现 1-2 次——快速创建、填值、不再访问。这些 slot 只被访问一次→不会受益于 cache

**Profiling 对比**：

```
Per-key 开销 (HashAggregateExec, Partial mode, 2 agg functions):
  - Key hash (Murmur3):        ~15 cycles
  - Hash map lookup (1-2 probes): ~30-60 cycles (cold: L3 miss)
  - Buffer update (in-place):   ~10 cycles
  - Total per row:             ~55-85 cycles (hot key < 30 cycles)

Per-key 开销 (SortAggregateExec):
  - SortExec (External sort):  ~100-200 cycles per row (amortized, spill dependent)
  - Merge scan:               ~10 cycles per row
  - Buffer update:            ~10 cycles per row
  - Total per row:            ~120-220 cycles
```

HashAggregate 在 key 紧致（能放入 L3）时比 Sort 快 2-4 倍。但如果 key 极多（> 5000 万），Hash map 所在的内存超过 L3，每次 lookup 都是 DRAM access（~100ns = ~300 cycles）→ HashAggregate 可能比 Sort 更慢。这就是 AQE 统计信息能帮助判断的地方。

**Fast HashMap 的 L1 优化**：

两级 Hash Map 的最大优势不是"减少内容占用"（因为 Tungsten HashMap 已经很紧凑），而是 **减少 UnsafeProjection 的序列化开销**。Fast HashMap 对原始类型 key（int, long）直接用原始值做 key（无序列化）→ grouping key 的 UnsafeProjection 只对 miss 的行才执行。当 key 分布均匀时，每个新 key 只触发一次 serialize + fallback→Tungsten HashMap——fast path hit 的延迟接近 10 cycles。

**Spill I/O 的批量化**：

Hash→Sort 回退时的 spill 是批量的——一个满的 hash map（约 128MB 页）一次溢写。这是连续的大块写入（128MB sequential write）→ NVMe SSD 上只需约 40ms。同时后续读取这些 spill files 做 merge 时，OS read-ahead 自动预取→ merge 速度接近内存带宽。

## AI 时代反思

聚合是 LLM Agent 与数据库交互时最常失败的操作之一。因为"自然语言问题→SQL 聚合"的映射非常微妙：

- 用户问"每个类别的平均销售额" → `SELECT category, AVG(sales) FROM ...` → 这个很直接
- 用户问"销售额最高的前 3 个类别" → 看似简单，实际需要 `GROUP BY ... ORDER BY ... LIMIT 3`——聚合 + 排序组合
- 用户问"哪些用户的购买频率在上升？" → 需要窗口函数 (`LAG`) + 聚合 + 时间范围——LLM 几乎一定写错

LLM 在聚合上的失败有一个清晰的模式：**它擅长写"聚合函数的数学定义"，但不擅长写"聚合的执行步骤"**。`AVG = SUM/COUNT` 是 LLM 能写出来的，但 `AVG(DISTINCT ...) = SUM(DISTINCT ...)/COUNT(DISTINCT ...)` 就经常错——因为 DISTINCT 改变了"分组"的语义，而 LLM 对这种语义变化的推理不精确。

一个可能的 AI-native 优化是：**让 LLM 成为一个"聚合建议器"而非"聚合实现器"**。流程是：
1. LLM 分析用户的自然语言，输出 `{measure: "sales", dimension: "category", operation: "average"}`
2. 数据库的可信栈将这个结构化意图翻译为精确的 SQL（不带语义歧义）
3. 优化器（CBO）选择具体的 Partial/Final 拆分策略

这与 LLM 直接写 SQL 的区别在于**抽象层级**——LLM 做"意图识别"（它能做好的），优化器做"执行决策"（它能做好的）。相比"全交给 LLM"或"LLM 完全不参与"，这个分工利用了双方的优势。

## 源码导航

| 文件 | 关键内容 | 行号参考 |
|------|---------|---------|
| `sql/core/src/main/scala/org/apache/spark/sql/execution/aggregate/HashAggregateExec.scala` | HashAggregateExec 完整实现，doProduceWithKeys，doConsumeWithKeys，两级 HashMap（Fast+Regular），finishAggregate spill 合并逻辑 | 51 (case class), 91 (doExecute), 161 (createHashMap), 197 (finishAggregate), 386 (checkIfFastHashMapSupported), 428 (doProduceWithKeys), 627 (doConsumeWithKeys) |
| `sql/core/src/main/scala/org/apache/spark/sql/execution/aggregate/TungstenAggregationIterator.scala` | Hash→Sort 回退全链路，processInputs spill 循环，switchToSortBasedAggregation 模式重写，sort-based 归并聚合 | 85 (class), 128 (createNewAggregationBuffer), 166 (hashMap 初始化), 184 (processInputs), 251 (switchToSortBasedAggregation), 320 (processCurrentSortedGroup) |
| `sql/core/src/main/scala/org/apache/spark/sql/execution/aggregate/AggregationIterator.scala` | AggregationIterator 基类，聚合函数初始化，processRow/generateOutput 生成，Declarative/Imperative 双路径调度 | 37 (abstract class), 74 (initializeAggregateFunctions), 156 (generateProcessRow), 234 (generateResultProjection), 302 (initializeBuffer) |
| `sql/core/src/main/scala/org/apache/spark/sql/execution/aggregate/SortAggregateExec.scala` | SortAggregateExec 实现，requiredChildOrdering 排序依赖，codegen 限制（无 key 才支持） | 34 (case class), 51 (requiredChildOrdering), 59 (doExecute), 96 (supportCodegen) |
| `sql/core/src/main/scala/org/apache/spark/sql/execution/aggregate/ObjectHashAggregateExec.scala` | ObjectHashAggregateExec，支持 TypedImperativeAggregate，GC 优化的 spill 全量回退策略 | 60 (case class), 83 (doExecute) |
| `sql/core/src/main/scala/org/apache/spark/sql/execution/aggregate/AggUtils.scala` | AggUtils，planAggregateWithoutDistinct（Partial+Final 拆分），planAggregateWithOneDistinct（四阶段 DISTINCT 聚合），决策树 | 33 (object), 69 (createAggregate 决策树), 126 (planAggregateWithoutDistinct), 175 (planAggregateWithOneDistinct) |
| `sql/core/src/main/scala/org/apache/spark/sql/execution/aggregate/AggregateCodegenSupport.scala` | AggregateCodegenSupport trait，doProduce/doConsume 按 key 有无分发，doProduceWithoutKeys 全局聚合 codegen | 36 (trait), 67 (doProduce), 75 (doConsume) |
| `sql/catalyst/src/main/scala/org/apache/spark/sql/catalyst/expressions/aggregate/interfaces.scala` | DeclarativeAggregate，ImperativeAggregate，TypedImperativeAggregate 接口定义 | |
