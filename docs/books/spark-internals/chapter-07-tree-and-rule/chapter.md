# 第 7 章：Tree 与 Rule — Catalyst 的设计哲学

## 设计动机

2007 年，Michael Stonebraker 在《The End of an Architectural Era》中提出：数据库系统的代码量中，优化器占了约 90%。这不是因为优化器代码多，而是因为**优化规则之间以不可预料的方式相互作用**——一个规则生效后，可能为另一个规则创造了生效条件，而这个"二次应用"又可能为第三个规则创造条件，以此类推。

这个观察催生了 Catalyst 的核心设计问题：**如何让数百条优化规则以可控的方式组织在一起，而不是变成一堆互相冲突的 if-else？**

Catalyst 的答案是：**把一切建模为树，把一切变化建模为规则**。

这个答案简洁得几乎不像一个答案。但它的力量在于，一旦你接受了"一切都是树"这个前提，你就获得了一个可组合的、可测试的、可理解的优化器架构。数十条规则以互相独立的 PartialFunction 存在，RuleExecutor 负责按批次调度它们，TreeNode 负责在树上传播变化。

这是我们在本书中第一次遇到"第一性原理设计"——**不是解决具体问题，而是建立一个足够简单的抽象，让具体问题自动消解**。

## 核心原理

### 7.1 TreeNode：为什么一切数据都是树

打开 `TreeNode.scala`，第一行有意义的代码是这行：

```scala
// sql/catalyst/src/main/scala/org/apache/spark/sql/catalyst/trees/TreeNode.scala:70
abstract class TreeNode[BaseType <: TreeNode[BaseType]]
  extends Product
  with TreePatternBits
  with WithOrigin {
  self: BaseType =>
```

两个关键设计选择在这里就定下了：

1. **`extends Product`**：每个 TreeNode 都是一个 case class（或行为类似 case class），拥有 `productArity`、`productElement` 等结构性方法。这让 Spark 可以通过反射访问任意节点的子字段——包括但不限于 `children`。

2. **`self: BaseType`**：这是一个 self-type annotation，强制 `this` 的类型为 `BaseType`。它保证了所有在 `children` 中返回的子节点与当前节点是同一基类型，实现了类型安全的递归。

`children` 方法是 tree 的核心：

```scala
// TreeNode.scala:221
def children: Seq[BaseType]
```

对于 LeafNode：`children = Seq.empty`
对于 UnaryNode：`children = Seq(child)`
对于 BinaryNode：`children = Seq(left, right)`
对于 TreeNode 含多个子节点：直接返回所有子节点

以 Join 为例，在 `sql/catalyst/src/main/scala/org/apache/spark/sql/catalyst/plans/logical/basicLogicalOperators.scala` 中：

```scala
case class Join(
    left: LogicalPlan,
    right: LogicalPlan,
    joinType: JoinType,
    condition: Option[Expression],
    hint: JoinHint)
  extends BinaryNode with JoinPlan {
  // children = Seq(left, right)
  // productElements = (left, right, joinType, condition, hint)
}
```

这里有一个值得注意的微妙之处：`children` 只包含树形子节点（left 和 right），而不包含 condition 表达式。condition 不实现 TreeNode，因此不是树结构的一部分。这引出了 Catalyst 的一个重要区分：

- **Query Plan Tree**：由 LogicalPlan 节点组成，表示查询的操作顺序
- **Expression Tree**：由 Expression 节点组成，表示计算表达式
- 两者在 transform 操作中是分离的——`transformDown` 遍历 Plan Tree，而 Plan 内部的 Expression 需要单独遍历

### 7.2 树遍历：transformDown / transformUp

`transformDown` 和 `transformUp` 是 TreeNode 最核心的两个方法。它们的语义区别仅在于规则的**应用顺序**：

**transformDown (前序遍历)**：

```scala
// TreeNode.scala:470-471
def transformDown(rule: PartialFunction[BaseType, BaseType]): BaseType = {
  transformDownWithPruning(AlwaysProcess.fn, UnknownRuleId)(rule)
}
```

`transformDown` 的核心实现：

```scala
// TreeNode.scala:488-511
def transformDownWithPruning(cond: TreePatternBits => Boolean,
  ruleId: RuleId = UnknownRuleId)(rule: PartialFunction[BaseType, BaseType]): BaseType = {
  // 1. 检查剪枝条件：如果不满足 cond，直接返回自身
  if (!cond.apply(this) || isRuleIneffective(ruleId)) {
    return this
  }
  // 2. 在当前节点上应用规则
  val afterRule = CurrentOrigin.withOrigin(origin) {
    rule.applyOrElse(this, identity[BaseType])
  }
  // 3. 如果规则未改变当前节点，则在子节点上递归
  if (this fastEquals afterRule) {
    val rewritten_plan = mapChildren(_.transformDownWithPruning(cond, ruleId)(rule))
    if (this eq rewritten_plan) {
      markRuleAsIneffective(ruleId)  // 整个子树无变化 → 标记该规则无效
      this
    } else {
      rewritten_plan
    }
  } else {
    // 4. 如果规则改变了当前节点，使用新节点并在子节点上递归
    afterRule.copyTagsFrom(this)
    afterRule.mapChildren(_.transformDownWithPruning(cond, ruleId)(rule))
  }
}
```

**transformUp (后序遍历)**：

```scala
// TreeNode.scala:521-522
def transformUp(rule: PartialFunction[BaseType, BaseType]): BaseType = {
  transformUpWithPruning(AlwaysProcess.fn, UnknownRuleId)(rule)
}
```

`transformUp` 的核心区别在于：**先处理子节点，再处理当前节点**：

```scala
// TreeNode.scala:540-563
def transformUpWithPruning(...): BaseType = {
  // 1. 先在子节点上递归
  val afterRuleOnChildren = mapChildren(_.transformUpWithPruning(cond, ruleId)(rule))
  // 2. 然后在当前节点（或已变换的子节点）上应用规则
  val newNode = if (this fastEquals afterRuleOnChildren) {
    rule.applyOrElse(this, identity[BaseType])
  } else {
    rule.applyOrElse(afterRuleOnChildren, identity[BaseType])
  }
  // ...
}
```

**何时用 Down，何时用 Up？** 一个经验法则：**如果你需要"先看到大图再处理细节"，用 Down；如果你需要"先处理细节再合并到大图"，用 Up。** 例如：

- 谓词下推（PushPredicateThroughJoin）用 `transformDown`：先从顶层 Join 看到谓词，才能决定把谓词推到哪一侧
- 列裁剪（ColumnPruning）用 `transformDown`：知道顶层需要哪些列，才能决定底层不需要哪些列
- 子查询消除（EliminateSubqueryAliases）用 `transformUp`：先消除内层子查询别名，再处理外层

### 7.3 RuleExecutor：定点迭代与批次编排

`RuleExecutor` 是规则引擎的调度器。它的核心数据结构是 `Batch`：

```scala
// sql/catalyst/src/main/scala/org/apache/spark/sql/catalyst/rules/RuleExecutor.scala:162
protected[catalyst] case class Batch(name: String, strategy: Strategy, rules: Rule[TreeType]*)
```

一个 Batch 包含：
- **name**：人类可读的名称，用于日志和调试
- **strategy**：执行策略——`Once`（一次执行）或 `FixedPoint(n)`（定点迭代最多 n 次）
- **rules**：这个批次包含的规则列表，**按顺序执行**

执行逻辑的核心在 `execute` 方法：

```scala
// RuleExecutor.scala:215
def execute(plan: TreeType): TreeType = {
  var curPlan = plan
  // ...
  for (batch <- batches) {
    // batch 内的规则按顺序执行
    val batchStartPlan = curPlan
    var iteration = 1
    var lastPlan = curPlan
    var continue = true
    while (continue) {
      curPlan = batch.rules.foldLeft(curPlan) {
        case (plan, rule) =>
          val startTime = System.nanoTime()
          val result = rule(plan)  // 每个规则是一个 TreeType => TreeType 函数
          // ...
          result
      }
      iteration += 1
      // FixedPoint: 如果 plan 不再变化，结束迭代
      if (curPlan.fastEquals(lastPlan)) {
        continue = false
      }
      lastPlan = curPlan
    }
  }
  curPlan
}
```

**为什么有些 Batch 需要 FixedPoint？** 因为规则之间有"唤醒效应"。一个简单的例子：

1. 谓词下推（PushPredicateThroughJoin）将 `WHERE a=1 AND b=2` 中 `a=1` 推到左子 Join
2. 这个下推完成后，现在左子 Join 上多了一个 `WHERE a=1` 条件
3. 常量折叠（ConstantFolding）现在可以在 `WHERE a=1` 下将 `a` 替换为 1
4. 替换后，可能又触发了新的下推机会

这就是为什么 Optimizer 的核心 batch 使用 `FixedPoint(100)` —— 规则需要反复交互直到"稳定"。

### 7.4 剪枝优化：TreePattern 与 RuleId

1400 行的 TreeNode 代码中，有一个巧妙但不易察觉的性能优化。

**问题**：每次跑一个优化规则，都需要遍历整棵树。对于 100 个规则的 Optimizer，在最坏情况下要遍历 100 次。如果能在遍历前跳过"明显不需要的规则"，能节省大量时间。

**TreePattern 剪枝**（模式驱动的剪枝）：

```scala
// TreeNode.scala:96-110
protected def getDefaultTreePatternBits: BitSet = {
  val bits: BitSet = new BitSet(TreePattern.maxId)
  // 1. 收集当前节点的 patterns
  val nodePatternIterator = nodePatterns.iterator
  while (nodePatternIterator.hasNext) {
    bits.set(nodePatternIterator.next().id)
  }
  // 2. 合并子节点的 patterns
  val childIterator = children.iterator
  while (childIterator.hasNext) {
    bits.union(childIterator.next().treePatternBits)
  }
  bits
}
```

每个 TreeNode 通过 `nodePatterns` 声明自己的"模式类型"——例如 Join 节点标记 `TreePattern.JOIN`，聚合节点标记 `TreePattern.AGGREGATE`。这些模式位通过 BitSet 从叶子向上传播。

当执行一条规则时，通过 `cond` 参数检查当前子树是否包含相关模式：

```scala
plan.transformDownWithPruning(
  cond = _.containsPattern(JOIN),  // 只遍历包含 JOIN 模式的子树
  ruleId = PushPredicateThroughJoin.ruleId
) { ... }
```

如果某棵子树不包含 JOIN 模式，整个 subtraversal 被跳过。

**RuleId 剪枝**（无效规则记忆）：

如果一条规则在某棵子树上执行后发现**完全没有改变任何节点**，说明这条规则对这棵子树已经"饱和"了。下次再遍历时可以跳过：

```scala
if (this eq rewritten_plan) {
  markRuleAsIneffective(ruleId)  // 标记规则对该子树无效
  this
}
```

这个优化依赖于 query plan 的**不可变性**——既然树没有改变，那后续执行也不会有新变化。

### 7.5 计划变化的日志与追踪

`PlanChangeLogger` 提供了规则执行前后的可视化对比：

```scala
// RuleExecutor.scala:57-78
def logRule(ruleName: String, oldPlan: TreeType, newPlan: TreeType): Unit = {
  if (!newPlan.fastEquals(oldPlan)) {
    // 通过 sideBySide 展示优化前后的计划变化
    log"""
       |=== Applying Rule ${MDC(RULE_NAME, ruleName)} ===
       |${MDC(QUERY_PLAN, sideBySide(oldPlan.treeString, newPlan.treeString).mkString("\n"))}
    """.stripMargin
  }
}
```

当设置 `spark.sql.planChangeLog.level=WARN` 时，优化过程的每一步变化都会输出到日志。配合 `QueryPlanningTracker`，可以精确测量每条规则和每个 batch 的耗时，生成完整的优化剖面。

## 关键代码片段

### 示例：一条简单的优化规则

从 `Optimizer.scala` 中提取 `SimplifyConditionals` 规则：

```scala
// sql/catalyst/src/main/scala/org/apache/spark/sql/catalyst/optimizer/Optimizer.scala
object SimplifyConditionals extends Rule[LogicalPlan] {
  override def apply(plan: LogicalPlan): LogicalPlan = plan.transformDownWithPruning(
    _.containsPattern(CASE_WHEN), ruleId) {
    // 简化 IF(true, a, b) → a
    case q: LogicalPlan =>
      q.transformExpressionsDownWithPruning(_.containsPattern(CASE_WHEN), ruleId) {
        case If(Literal.TrueLiteral, trueValue, _) => trueValue
        case If(Literal.FalseLiteral, _, falseValue) => falseValue
        case CaseWhen(Seq((cond, value)), None)
          if Literal.isLiteralStringInExpression(cond) => value
      }
  }
}
```

注意这里 `transformExpressionsDownWithPruning` 只处理表达式内的 `CASE_WHEN` 模式，而 `transformDownWithPruning` 只遍历包含 `CASE_WHEN` 的逻辑计划。两者的剪枝条件是**分离的**——Plan 遍历和 Expression 遍历是两套独立的变换管线。

## 硬件视角

Tree 和 Rule 设计的效率关键不在于"单个规则多快"，而在于**树遍历的缓存友好性**。

Scala 的 case class 存储在 JVM heap 上，对象头占 12-16 字节，引用占 4-8 字节（取决于压缩 OOP）。一个 `Join` 对象约有 8 个字段，在 heap 上大约占 80-100 字节。对于有 1000 个节点的查询计划，整个 LogicalPlan 树需要约 100KB。

这个大小可能看起来微不足道，但关键在于 100 个规则 × 1000 个节点的遍历 = 100,000 次对象访问。这些 visit 访问的 node 位置由树结构决定，而不是由内存布局决定——这意味着**缓存未命中率可能高达 30-50%**。

Catalyst 对此的应对不是改变内存布局（UnsafeRow 是 Tungsten 的事），而是通过剪枝减少不必要的访问：
- `TreePattern` 剪枝让不需要的遍历在模式检查阶段就终止
- `RuleId` 无效规则剪枝防止重复遍历已经"饱和"的子树

这在 CPU 级别上相当于一个**软件实现的 branch predictor**——在实际进入子树之前就预测这次遍历是否会有收获。

## AI 时代反思

把查询优化建模为"树 + 规则"的决定，恰好暗示了一个与现代 AI 框架的深刻差异，也是一个对话点。

在深度学习框架中，计算图的优化（如 PyTorch 的 `torch.compile`，XLA 的 HLO 优化）同样使用图变换（graph transformations）。底层的抽象也是"规则"——fuse conv + batch_norm + relu → single fused kernel；eliminate identity reshape nodes 等。

但差异在于规则的**来源**：
- Catalyst 的规则是**人工编写的**——数十年数据库研究的结晶
- AI 框架中越来越多的优化是**自动发现的**——通过学习哪些算子组合在特定硬件上更高效

我们还不清楚的是：如果让一个模型在海量查询日志和物理计划上训练，它能否自动发现"谓词下推"或"列裁剪"这类规则？如果可以，这些"自动发现的规则"是否会超越人工规则？

催化剂（Catalyst）本身是否也需要被催化？

## 源码导航

| 文件 | 关键内容 | 行号参考 |
|------|---------|---------|
| `sql/catalyst/src/main/scala/org/apache/spark/sql/catalyst/trees/TreeNode.scala` | TreeNode 基类，transformDown/transformUp/transformWithPruning | 70 (类定义), 221 (children), 470 (transformDown), 521 (transformUp) |
| `sql/catalyst/src/main/scala/org/apache/spark/sql/catalyst/rules/RuleExecutor.scala` | RuleExecutor 执行引擎，Batch/Strategy/Once/FixedPoint | 125 (类定义), 150 (Once), 156 (FixedPoint), 162 (Batch), 215 (execute) |
| `sql/catalyst/src/main/scala/org/apache/spark/sql/catalyst/trees/TreePattern.scala` | 所有 TreePattern 枚举定义 |
| `sql/catalyst/src/main/scala/org/apache/spark/sql/catalyst/rules/RuleId.scala` | RuleId / RuleIdCollection，规则标识符管理 |
| `sql/catalyst/src/main/scala/org/apache/spark/sql/catalyst/optimizer/Optimizer.scala` | Optimizer 的 batch 编排与规则列表，了解规则如何组织进 batch |
| `sql/catalyst/src/main/scala/org/apache/spark/sql/catalyst/analysis/Analyzer.scala` | Analyzer 的 batch 编排，对比 Optimizer 的结构差异 |
