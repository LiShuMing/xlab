# 第 13 章：Whole-Stage Code Generation — 从解释到编译

## 设计动机

在第 12 章中，Tungsten 解决了"数据如何表示"的问题——用 UnsafeRow 替换 Java 对象，消除对象头和 GC 压力。但这只解决了一半问题。另一半是 **"数据如何被处理"**。

传统数据库使用 Volcano 迭代器模型（Volcano Iterator Model）：每个算子实现 `open()` → `next()` → `close()` 接口。一个简单的 `SELECT a+1 FROM t WHERE b > 10` 在执行时会形成这样的调用链：

```
ProjectExec.next()
  → FilterExec.next()
    → ScanExec.next()
```

每次 `next()` 都是一个虚函数调用（virtual dispatch）。对于 1000 万行数据，这意味着 3000 万次虚函数调用。在现代 CPU 上，虚函数调用的代价不是函数调用本身（几个 cycle），而是 **分支预测失败**（branch misprediction）——CPU 无法预测 `next()` 的目标地址，导致 pipeline flush（约 15-20 个 cycle 的惩罚）。

Whole-Stage Code Generation（全阶段代码生成）用一句口号总结了它的解决方案：**"把 Volcano 模型的虚函数调用链，融合为单条手写 for 循环"**。

更准确地说：不是让算子互相调用，而是让每个算子"写出"自己会怎么做，然后在编译时**拼接成一个大函数**，最后由 Janino（Java 轻量级编译器）编译为字节码。

这类似于：解释型语言 → JIT 编译型语言。只不过 Spark 在 query 级别做 JIT——不是在 VM 级别。

## 核心原理

### 13.1 Volcano 模型 vs 代码生成

以 `SELECT a+1 FROM t WHERE b > 10` 为例。

**Volcano 模型**的执行流：

```java
// 每行数据经过 3 次虚函数调用
class ProjectExec {
  def next(): Row = {
    val row = child.next()  // 虚调用 → FilterExec.next()
    Row(row.getInt(0) + 1)
  }
}
class FilterExec {
  def next(): Row = {
    while (true) {
      val row = child.next()  // 虚调用 → ScanExec.next()
      if (row.getInt(1) > 10) return row
    }
  }
}
```

**Whole-Stage Codegen** 生成的等价代码：

```java
// 全部融合为一个函数
protected void processNext() {
  while (scan_input.hasNext()) {
    InternalRow row = (InternalRow) scan_input.next();
    // Filter: b > 10
    if (!row.isNullAt(1) && row.getInt(1) > 10) {
      // Project: a + 1
      int projectValue = row.getInt(0) + 1;
      // append 到输出 buffer
      append(unsafeRow);
    }
  }
}
```

虚函数调用从 **3 次/行** → **0 次/行**。循环从 3 层嵌套 → 1 层。JIT 编译器可以对这个单一循环做 **循环展开**（loop unrolling）、**SIMD 向量化**（auto-vectorization）、**逃逸分析**（escape analysis）——这些优化在虚函数调用链上都不可能。

### 13.2 produce/consume 代码生成模型

WholeStageCodegen 的核心是一对方法：`produce()` 和 `consume()`。

- **produce()**：生成该算子"生产行"的代码。父算子调用子算子的 produce 来获取数据处理代码。
- **consume()**：生成该算子"消费行"的代码。子算子调用父算子的 consume 来传递结果。

```scala
// WholeStageCodegenExec.scala:94
final def produce(ctx: CodegenContext, parent: CodegenSupport): String = {
  this.parent = parent
  ctx.freshNamePrefix = variablePrefix
  s"""
     |${ctx.registerComment(s"PRODUCE: ${this.simpleString}")}
     |${doProduce(ctx)}
   """.stripMargin
}

// WholeStageCodegenExec.scala:153
final def consume(ctx: CodegenContext, outputVars: Seq[ExprCode], row: String = null): String = {
  val inputVars = ...
  val rowVar = prepareRowVar(ctx, row, outputVars)
  ctx.currentVars = inputVars
  ctx.freshNamePrefix = parent.variablePrefix
  parent.doConsume(ctx, inputVars, rowVar)
}
```

不同算子重写 `doProduce` 和 `doConsume` 来定义它们在该模型中的行为：

**FilterExec** 的 `doConsume`：

```scala
// FilterExec 消费子节点生产的行
override def doConsume(ctx: CodegenContext, input: Seq[ExprCode], row: ExprCode): String = {
  // 生成过滤条件的求值代码
  val eval = BindReferences.bindReference(condition, child.output).genCode(ctx)
  s"""
     |${eval.code}
     |if (!${eval.isNull} && ${eval.value}) {
     |  ${consume(ctx, input)}  // 通过 → 传递给父节点
     |}
   """.stripMargin
}
```

**ProjectExec** 的 `doConsume`：

```scala
// ProjectExec 消费子节点生产的行，计算投影表达式
override def doConsume(ctx: CodegenContext, input: Seq[ExprCode], row: ExprCode): String = {
  // 对每个投影表达式生成求值代码
  val exprs = projectList.map { expr =>
    BindReferences.bindReference(expr, child.output).genCode(ctx)
  }
  consume(ctx, exprs)  // 传递给父节点
}
```

**ScanExec**（叶子节点）的 `doProduce`：

```scala
// ScanExec 生产行（从 RDD 读取）
override def doProduce(ctx: CodegenContext): String = {
  val input = ctx.freshName("input")
  ctx.addMutableState("scala.collection.Iterator", input, "input = inputs[0];")
  s"""
     |while ($limitNotReachedCond $input.hasNext()) {
     |  InternalRow $row = (InternalRow) $input.next();
     |  ${consume(ctx, outputVars, row)}  // 生产出 row → 传递给子节点(下行消费者)
     |  if (shouldStop()) return;
     |}
   """.stripMargin
}
```

**关键洞察**：produce/consume 模型实现了 **代码的延迟拼接**。每个算子不确定自己的最终位置，它只生成代码片段。在 `CollapseCodegenStages` 规则中，这些片段被拼接为一个完整函数。

### 13.3 Janino 编译器与 CodegenContext

WholeStageCodegen 生成的是 **Java 源代码字符串**。它需要被编译为可执行的字节码。Spark 使用 **Janino**——一个运行时 Java 源码编译器：

```scala
// WholeStageCodegenExec.scala:731
override def doExecute(): RDD[InternalRow] = {
  val (ctx, cleanedSource) = doCodeGen()
  val (_, compiledCodeStats) = try {
    CodeGenerator.compile(cleanedSource)  // Janino 编译
  } catch {
    case NonFatal(_) if !Utils.isTesting && conf.codegenFallback =>
      logWarning("Whole-stage codegen disabled, falling back to Volcano")
      return child.execute()  // 回退到解释执行
  }
  ...
}
```

**CodegenContext** 是代码生成的上下文——管理变量名唯一性、可变状态注册、函数定义等：

```scala
class CodegenContext {
  val mutableStates: mutable.ArrayBuffer[String] = ...  // 可变状态声明
  val references: mutable.ArrayBuffer[Any] = ...        // 引用对象（广播到 Executor）
  var currentVars: Seq[ExprCode] = ...                  // 当前正在处理的列变量
  var INPUT_ROW: String = ...                           // 当前行变量名

  def addMutableState(javaType: String, name: String, init: String): String  // 声明可变状态
  def addNewFunction(name: String, code: String): String                     // 注册新函数
  def freshName(prefix: String): String                                     // 生成唯一变量名
  def addReferenceObj(name: String, obj: Any): String                       // 注册引用对象
}
```

**变量名前缀**在每个算子的 produce/consume 中会切换：

```scala
private def variablePrefix: String = this match {
  case _: HashAggregateExec => "hashAgg"
  case _: BroadcastHashJoinExec => "bhj"
  case _: SortMergeJoinExec => "smj"
  case _: DataSourceScanExec => "scan"
  ...
}
```

这确保了不同算子生成的变量不会冲突——`hashAgg_map`、`bhj_map`、`smj_map` 各不干扰。

### 13.4 CollapseCodegenStages — 合并策略

`CollapseCodegenStages` 规则负责将物理计划树中的算子合并为 WholeStageCodegen 流水线：

```scala
// WholeStageCodegenExec.scala:907
case class CollapseCodegenStages(codegenStageCounter: AtomicInteger)
  extends Rule[SparkPlan] {

  private def supportCodegen(plan: SparkPlan): Boolean = plan match {
    case plan: CodegenSupport if plan.supportCodegen =>
      val willFallback = plan.expressions.exists(_.exists(e => !supportCodegen(e)))
      val hasTooManyOutputFields = WholeStageCodegenExec.isTooManyFields(conf, plan.schema)
      val hasTooManyInputFields = plan.children.exists(
        p => WholeStageCodegenExec.isTooManyFields(conf, p.schema))
      !willFallback && !hasTooManyOutputFields && !hasTooManyInputFields
    case _ => false
  }
}
```

**不能合并的情况**：
1. **表达式不支持代码生成**（如 `CodegenFallback`）：某些复杂表达式（如 Python UDF）只实现了 `eval`，没有 `genCode`
2. **字段过多**：`wholeStageMaxNumFields`（默认 100）——生成的代码会过大
3. **SortMergeJoin / ShuffledHashJoin 的子节点**：Join 的两个子必须各自独立的 Codegen Stage，通过 Shuffle 分开

**合并算法**（后序遍历）：

```scala
private def insertWholeStageCodegen(plan: SparkPlan): SparkPlan = plan match {
  case plan: CodegenSupport if supportCodegen(plan) =>
    WholeStageCodegenExec(insertInputAdapter(plan))(codegenStageCounter.incrementAndGet())
  case other =>
    other.withNewChildren(other.children.map(insertWholeStageCodegen))
}
```

`insertInputAdapter` 在支持和不支持代码生成的边界处插入 `InputAdapter`：

```
WholeStageCodegen
  +- FilterExec (支持 codegen)
     +- ProjectExec (支持 codegen)
        +- InputAdapter  ← 边界: 下面的算子不支持 codegen
           +- ShuffleExchangeExec (不支持 codegen → 从 child.execute() 读 RDD)
```

### 13.5 代码拆分 — 防止超大函数

当合并太多算子时，生成的 `processNext()` 函数可能超过 JVM 的方法大小上限（默认 8000 字节码指令）。Spark 使用两种对抗措施：

**1. consume 函数拆分**（`wholeStageSplitConsumeFuncByOperator`）：

```scala
// WholeStageCodegenExec.scala:185-201
// 当启用 split 时，每个算子的 doConsume 会生成一个独立的函数
// 而不是 inline 到父算子的 consume 中
val consumeFunc = if (confEnabled && requireAllOutput
    && CodeGenerator.isValidParamLength(paramLength)) {
  constructDoConsumeFunction(ctx, inputVars, row)
} else {
  parent.doConsume(ctx, inputVars, rowVar)
}
```

**2. hugeMethodLimit 检查**：

```scala
// WholeStageCodegenExec.scala:746
if (compiledCodeStats.maxMethodCodeSize > conf.hugeMethodLimit) {
  logInfo("Found too long generated codes, falling back to Volcano")
  return child.execute()  // 回退
}
```

### 13.6 代码生成的范围：谁参与，谁不参与

| 算子 | 支持 WSCG？ | 原因 |
|------|-----------|------|
| ProjectExec / FilterExec | 是 | 纯表达式计算 |
| HashAggregateExec | 是 | Tungsten HashMap + 表达式 |
| BroadcastHashJoinExec | 是 | Hash Table 流式探测（streaming probe） |
| SortMergeJoinExec | 分开成两根 pipeline | Shuffle 是界线 |
| ShuffleExchangeExec | 否 | 需要网络 I/O，不适合同步循环 |
| SortExec | 是 | 排序后顺序读取 |
| WindowExec | 是 | 分区内窗口计算 |
| GenerateExec | 是 | 一行变多行 |
| BatchEvalPythonExec | 否 | Python UDF 不在 JVM 内 |
| UnionExec | 否 | 结构上不适合合并成单循环 |
| SubqueryExec | 否 | 独立的子查询执行 |

`Explain` 输出中，`*` 标记表示该节点处于 WholeStageCodegen 中：

```
*(1) Project [a#0]
+- *(1) Filter (b#1 > 10)
   +- *(1) ColumnarToRow
      +- FileScan parquet [a#0,b#1]
```

注意 FileScan 前有 `ColumnarToRow`——列式扫描输出列式数据，WholeStageCodegen 需要行式数据，所以插入一个 row↔columnar 转换。

### 13.7 对标：Velox / Gluten Native Engine

Velox（Meta 开源）和 Gluten（Intel 开源）代表了与 WholeStageCodegen 截然不同的路线：**不使用代码生成，而是使用 C++ 的 SIMD 和模板元编程**。

| 维度 | Spark WholeStageCodegen | Velox (C++ Native Engine) |
|------|------------------------|--------------------------|
| 语言 | Java + Janino 编译为字节码 | C++17 → 编译为原生指令 |
| 向量化 | 依赖 JIT 自动 SIMD 化 | 手写 SIMD (x86 SSE/AVX) |
| 内存管理 | Unsafe on-heap/off-heap | C++ malloc + 线程级 pool |
| 编译开销 | 每次查询编译 Java → bytecode（ms 级） | 预编译的 shared library（0ms） |
| 回退策略 | hugeMethod → Volcano 解释执行 | 不需要回退（全 C++） |
| 调试 | 生成的 Java 代码难以调试 | C++ 代码直接可用 GDB |

**性能差异的本质来源**：
- **分支预测**：WholeStageCodegen 消除了解释器开销，但仍然是分支密集型（null check、type check）。C++ Native Engine 通过 `velox::Vector` 批量处理和 null-tracking 位图一次性判断消除分支。
- **SIMD**：JVM JIT 的 auto-vectorization 是机会主义的，C++ 是确定性的——Velox 对 Arrow 格式的批量处理可以确定性地使用 AVX-512。
- **编译开销**：Janino 每次查询编译 Java 源码到字节码。对于短查询，编译耗时（1-10ms）可能占查询总时间的 10-30%（Spark 默认对小查询禁用 WSCG）。

**WholeStageCodegen 的优势**：
- **UDF 友好**：Scala/Java UDF 可以直接 inline 到生成的代码中。Native Engine 需要 JNI 回退来处理 UDF。
- **灵活性**：代码修改后不需要重新编译 Spark。
- **成熟度**：在 Spark 中经历了 10 年生产验证。

## 关键代码片段

### 示例：手写 vs 生成的代码对比

用户 SQL：`SELECT a+1, b*2 FROM t WHERE c > 0`

**生成的 Java 代码**（简化版）：

```java
final class GeneratedIterator extends BufferedRowIterator {
  private UnsafeRow[] hashAgg_map;
  private scala.collection.Iterator[] inputs;

  public void init(int index, scala.collection.Iterator[] inputs) {
    this.inputs = inputs;
  }

  protected void processNext() throws java.io.IOException {
    scala.collection.Iterator scan_input = inputs[0];
    while (scan_input.hasNext()) {
      InternalRow scan_row = (InternalRow) scan_input.next();
      // Filter: c > 0
      boolean scan_isNull = scan_row.isNullAt(2);
      int scan_value = scan_row.getInt(2);
      if (!scan_isNull && scan_value > 0) {
        // Project: a+1, b*2
        int proj_value1 = scan_row.getInt(0) + 1;
        int proj_value2 = scan_row.getInt(1) * 2;
        // 写 UnsafeRow
        addRow(proj_value1, proj_value2);
      }
      if (shouldStop()) return;
    }
  }
}
```

### 示例：HashAggregate 的 Codegen 流程

```scala
// HashAggregateExec 的 doProduce 生成:
// 1. 初始化 hash map
//    if (!initialized) {
//      hashAgg_map = new BytesToBytesMap(...);
//      // 调用子算子的 produce() 来生成"读取并聚合数据"的代码
//      child.asInstanceOf[CodegenSupport].produce(ctx, this)  // 这会 push 数据到 hash map
//      initialized = true;
//    }
// 2. 迭代 hash map 输出结果
//    BytesToBytesMap.Entry hashAgg_entry = hashAgg_map.next();
//    while (hashAgg_entry != null) {
//      // 从 entry 中读取 key 和 aggregation buffer
//      // 计算最终结果表达式 (e.g. CAST(count AS BIGINT))
//      // 调用 consume() 传递给父节点
//      hashAgg_entry = hashAgg_map.next();
//    }
```

## 硬件视角

WholeStageCodegen 本质上是对 CPU 流水线（pipeline）的一种"优化适配"。

**分支预测**：

Volcano 模型的 `next()` 是虚调用——这是 CPU 的"间接分支"（indirect branch）。现代 CPU 的间接分支预测器（如 Intel 的 ITTAGE）在 4-8 个不同的目标之间学习。当 `next()` 的目标在多个算子间切换时（Project → Filter → Scan → Project → ...），预测失败率可能高达 20-30%。每次失败 = pipeline flush = 15-20 cycle 浪费。

WholeStageCodegen 把虚调用替换为 **直接条件跳转**（`if (!isNull && value > 0)`）。现代 CPU 的条件分支预测器准确率 >95%。循环本身的"是否继续"用 `loop` 指令或 `dec/jnz` 对，CPU 的 loop predictor 对此类分支的准确率接近 100%。

**指令 Cache**：

Volcano 模型的 3 个算子在内存中的代码分散在 3 个不同的 class 中——横跨多个 4KB 页。I-cache miss 率较高。

WholeStageCodegen 将所有逻辑放在一个 `processNext()` 中——连续约 1-5KB 的代码。L1 I-cache (32KB) 可以完整容纳。I-cache miss 基本为零。

**编译开销**：

Janino 编译约 1MB 的 Java 源码需要 5-20ms。对于 TB 级查询，这是噪音。对于 `SELECT * FROM t LIMIT 10` 的小查询，编译时间可能 > 执行时间。这就是为什么 Spark 为 `LocalTableScan` / `LocalRelation` / `CommandResult` 默认**不启用** WSCG。

**内存带宽**：

对于典型表扫描（2 列 × 10 亿行），Row-based Volcano 模型可能产生 2-3 次中间结果拷贝（每层算子都创建新 Row 对象）。WholeStageCodegen 将 transform 在寄存器/L1 中完成——中间列值作为局部变量存在，不需要写回内存。这节省的内存带宽相当于原始数据大小的 2-3 倍。

## AI 时代反思

WholeStageCodegen 和 LLM 之间有一个隐含的"代码生成者"对话。

两者都是"代码生成器"。Janino 生成的是 **严格等价的 Java 代码**（必须保持语义等价）。LLM 生成的是 **"看起来正确"的代码**（无法保证等价性）。

但 LLM 在 WholeStageCodegen 中的可能角色是 **生成更"聪明"的优化代码**。当前的 WSCG 生成的代码是"直接翻译"——字符串拼接的、模板化的。但如果 LLM 能对特定算子组合生成"可能更高效"的 C-style 循环（利用特定 CPU 指令、特定数据分布），再由 Janino 编译，就形成了一个"LLM 作为 source-level optimizer"的模式。

这引出一个有趣的设计：**WSCG 的模板语言能否是 LLM 友好的？** 当前的 `doProduce` / `doConsume` 是 Scala 字符串拼接。如果替换为 LLM 能理解的语言（例如 Python DSL），LLM 可以参与"生成更优的代码模板"而不仅仅是"生成数据"。

Native Engine 的出现模糊了 WholeStageCodegen 和 AOT 编译的界线。Velox/Gluten 在 C++ 层"手写"了类似 WSCG 融合——多个算子融合为单个 pipeline，但它是预编译的原生代码。一个有趣的问题是：**LLM 能否自动生成 C++ Native Engine pipeline 模板？** 例如：给定一个 Spark Plan，LLM 生成对应的 Velox Plan 配置（哪些算子融合、mem pool 大小、hash table 类型）——这和当前 Native Engine 的手写规则映射完全相同。

可能的未来形态：
```
Spark LogicalPlan → LLM 分析 → 选择最优的 Native Pipeline 配置 → 完全不经过 WSCG/Janino
```

这将"优化器"变为 LLM 的任务。但它面临的挑战与第 10 章相同：LLM 输出不能直接执行，必须验证等价性。

## 源码导航

| 文件 | 关键内容 | 行号参考 |
|------|---------|---------|
| `sql/core/src/main/scala/org/apache/spark/sql/execution/WholeStageCodegenExec.scala` | CodegenSupport trait，WholeStageCodegenExec，CollapseCodegenStages | 47 (CodegenSupport trait), 94 (produce), 153 (consume), 345 (doConsume), 450 (InputRDDCodegen), 504 (InputAdapter), 636 (WholeStageCodegenExec), 666 (doCodeGen), 731 (doExecute), 907 (CollapseCodegenStages) |
| `sql/catalyst/src/main/scala/org/apache/spark/sql/catalyst/expressions/codegen/CodegenContext.scala` | CodegenContext 类，mutableStates，freshName，addReferenceObj | |
| `sql/catalyst/src/main/scala/org/apache/spark/sql/catalyst/expressions/codegen/CodeGenerator.scala` | CodeGenerator，Janino 编译入口，compile 方法 | |
| `sql/catalyst/src/main/scala/org/apache/spark/sql/catalyst/expressions/codegen/GenerateUnsafeProjection.scala` | UnsafeRow 构造的代码生成 | |
| `sql/core/src/main/scala/org/apache/spark/sql/execution/basicPhysicalOperators.scala` | ProjectExec，FilterExec 的 doConsume 实现 | |
| `sql/core/src/main/scala/org/apache/spark/sql/execution/aggregate/HashAggregateExec.scala` | HashAggregate 的 doProduce / doConsume 实现 | |
| `sql/core/src/main/scala/org/apache/spark/sql/execution/joins/BroadcastHashJoinExec.scala` | BHJ 的 doProduce / doConsume 实现 | |
| `sql/core/src/main/scala/org/apache/spark/sql/execution/datasources/FileSourceScanExec.scala` | 文件扫描的 doProduce 实现 | |
