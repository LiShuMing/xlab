# 第 9 章：Logical Optimization — 从解析计划到最优逻辑计划

## 设计动机

在 Analysis 完成后，我们得到了一个 **Resolved Logical Plan**——所有表、列、函数都已经与 Catalog 中的元数据绑定。但这是一个"字面翻译"的计划：用户写了什么，它就长什么样。

考虑这条 SQL：

```sql
SELECT a, b, c
FROM (SELECT * FROM t1 JOIN t2 ON t1.id = t2.id)
WHERE a > 10 AND b < 100
```

Analysis 之后，计划可能是：

```
Project [a, b, c]
+- Filter ((a > 10) AND (b < 100))
   +- Project [a, b, c, d, e, f, g, h]    ← 子查询的 SELECT *
      +- Join (t1.id = t2.id)
         +- Relation t1 [a, b, c, d]
         +- Relation t2 [e, f, g, h]
```

这个计划"正确"——它能算出正确的答案。但它做了一些**不必做的事**：

1. t1 和 t2 一共有 8 列，但外层只需要 3 列。为什么要在 Join 两侧传输所有列？——**列裁剪**
2. `a > 10` 只涉及 t1 的列。为什么不在 Join 之前就把不满足条件的行过滤掉？——**谓词下推**
3. `SELECT *` 之后跟着 `SELECT a, b, c`——这两个 Project 能不能合并成一个？——**算子合并**

这些问题不会改变查询结果，但会改变查询成本。在最极端的情况下，一个未经优化的计划可能扫描 100 倍于必要的数据。

**这就是 Optimizer 的职责：把一个"字面正确"的计划转化为"等价但更廉价"的计划。**

关键约束是**等价性**：Optimizer 只能应用"保证等价"的变换。这是一个形式语义问题——但也因此，Optimizer 的每条规则都可以独立验证、独立编码、独立测试。

这种设计哲学直接来自 Catalyst 的 Tree + Rule 架构（第 7 章）。Optimizer 不是一个大函数，而是约 70 条规则的有序列集合，按批次编排，由 RuleExecutor 调度。

Optimizer 的代码量约 3000 行（主文件）加上约 20 个子文件（pushdown、join、subquery、expression 等），总共约 70 条规则。这是 Catalyst 中最大的单一模块。

## 核心原理

### 9.1 Optimizer 的批次编排全景

`Optimizer` 继承 `RuleExecutor[LogicalPlan]`，通过 `defaultBatches` 方法定义了批次序列：

```scala
// Optimizer.scala:100
def defaultBatches: Seq[Batch] = {
  val operatorOptimizationRuleSet = Seq(
    // Operator push down
    PushProjectionThroughUnion,
    ReorderJoin,
    EliminateOuterJoin,
    PushDownPredicates,
    PushDownLeftSemiAntiJoin,
    LimitPushDown,
    ColumnPruning,
    GenerateOptimization,
    // Operator combine
    CollapseRepartition,
    CollapseProject,
    OptimizeWindowFunctions,
    CollapseWindow,
    EliminateLimits,
    CombineUnions,
    // Constant folding and strength reduction
    NullPropagation,
    ConstantPropagation,
    FoldablePropagation,
    OptimizeIn,
    ConstantFolding,
    BooleanSimplification,
    SimplifyConditionals,
    PruneFilters,
    SimplifyCasts,
    ...) ++ extendedOperatorOptimizationRules

  val operatorOptimizationBatch: Seq[Batch] = Seq(
    Batch("Operator Optimization before Inferring Filters", fixedPoint,
      operatorOptimizationRuleSet: _*),
    Batch("Infer Filters", Once,
      InferFiltersFromGenerate,
      InferFiltersFromConstraints),
    Batch("Operator Optimization after Inferring Filters", fixedPoint,
      operatorOptimizationRuleSet: _*),
    Batch("Push extra predicate through join", fixedPoint,
      PushExtraPredicateThroughJoin,
      PushDownPredicates))
```

注意一个关键设计：**operatorOptimizationRuleSet 被执行了两次**——一次在 Infer Filters 之前，一次在之后。这是因为 InferFiltersFromConstraints 能从 Join 条件中推断出新的 Filter，而这些新 Filter 又可以触发新一轮的谓词下推。

Optimizer 的完整批次序列（按执行顺序）可以分为几个逻辑阶段：

| 阶段 | Batch 名称 | 策略 | 职责 |
|------|-----------|------|------|
| 收尾 Analysis | Finish Analysis | FixedPoint(1) | 消除子查询别名、View、替换表达式 |
| CTE 内联 | Inline CTE | Once | 将 CTE 引用内联展开 |
| Union 合并 | Union | fixedPoint | 合并相邻 Union、移除 NoopUnion |
| 空关系早处理 | LocalRelation early | fixedPoint | 将可静态求值的关系转化为 LocalRelation |
| 相关表达式上拉 | Pullup Correlated Expressions | Once | 将子查询中的相关谓词上拉 |
| 子查询 | Subquery | FixedPoint(1) | 递归地对子查询应用 Optimizer |
| 算子替换 | Replace Operators | fixedPoint | Except/Intersect/Distinct → Join/Aggregate |
| 聚合预处理 | Aggregate | fixedPoint | 从 GroupBy 中移除 Literal 和重复表达式 |
| **算子优化 ×2** | Operator Optimization | fixedPoint | 核心优化：下推、裁剪、折叠、合并 |
| 过滤器推断 | Infer Filters | Once | 从 Constraints 推断新 Filter |
| 预 CBO | Pre CBO Rules | Once | CBO 前的准备规则 |
| **扫描下推** | Early Filter and Projection Push-Down | Once | 将 Filter/Project 下推到 Scan 节点 |
| Join 重排序 | Join Reorder | FixedPoint(1) | Cost-Based Join Reorder |
| **算子优化（第三次）** | Push extra predicate through join | fixedPoint | 下推 Join 中产生的额外谓词 |
| 排序消除 | Eliminate Sorts | Once | 消除冗余 Sort |
| 去重聚合重写 | Distinct Aggregate Rewrite | Once | 将 `count(distinct)` 展开为两阶段聚合 |
| 笛卡尔积检查 | Check Cartesian Products | Once | 检测缺少 Join 条件的 Cross Join |

这个编排背后有几个设计原则：

1. **重排、预处理先行**：CTE 内联、算子替换（Except→Anti Join）必须在核心优化前完成
2. **核心优化可反复执行**：operatorOptimizationRuleSet 内包含约 50 条规则，每个都以 FixedPoint 迭代，直到 plan 稳定
3. **Filter 推断需要"穿插"**：InferFiltersFromConstraints 需要核心优化先运行以暴露约束，运行后又需要再次核心优化以下推新 Filter
4. **统计敏感的优化（CBO, Join Reorder）必须靠后**：只有在 Scan 下推完成后，V2 数据源才会报告准确的统计信息

### 9.2 谓词下推（Predicate Pushdown）

谓词下推是 Optimizer 中最具"杠杆效应"的优化。它的思路很简单：**过滤条件越早应用，要处理的数据越少**。但实现上，不同算子有不同的下推规则。

核心入口是 `PushDownPredicates`：

```scala
// Optimizer.scala:2065
object PushDownPredicates extends Rule[LogicalPlan] {
  def apply(plan: LogicalPlan): LogicalPlan = plan.transformWithPruning(
    _.containsAnyPattern(FILTER, JOIN)) {
    CombineFilters.applyLocally
      .orElse(PushPredicateThroughNonJoin.applyLocally)
      .orElse(PushPredicateThroughJoin.applyLocally)
  }
}
```

三条子规则分工明确：

- **CombineFilters**：将 `Filter(a, Filter(b, child))` 合并为 `Filter(a AND b, child)`
- **PushPredicateThroughNonJoin**：处理 Project、Aggregate、Window、Union 等非 Join 算子
- **PushPredicateThroughJoin**：处理 Join 算子的谓词拆分与下推

#### PushPredicateThroughJoin — Join 上的谓词拆分

这是谓词下推中最复杂的部分，因为外层 WHERE 中的谓词可能需要"拆分"到 Join 的两侧：

```scala
// Optimizer.scala:2342
object PushPredicateThroughJoin extends Rule[LogicalPlan] with PredicateHelper {
  // 将条件拆分为三组
  private def split(condition: Seq[Expression], left: LogicalPlan, right: LogicalPlan) = {
    val (pushDownCandidates, stayUp) =
      condition.partition(cond => cond.deterministic && !cond.throwable)
    val (leftEvaluateCondition, rest) =
      pushDownCandidates.partition(_.references.subsetOf(left.outputSet))
    val (rightEvaluateCondition, commonCondition) =
        rest.partition(expr => expr.references.subsetOf(right.outputSet))
    (leftEvaluateCondition, rightEvaluateCondition, commonCondition ++ stayUp)
  }
}
```

对于 Inner Join：

```
Filter(a > 10 AND b < 100 AND t1.id = t2.id, Join(t1, t2))
```

被拆分为：
- `leftEvaluateCondition`: `a > 10`（只涉及 t1 的列）→ 下推到 t1 侧
- `rightEvaluateCondition`: `b < 100`（只涉及 t2 的列）→ 下推到 t2 侧
- `commonCondition`: `t1.id = t2.id`（涉及两侧）→ 留在 Join condition 中

对于 Outer Join，规则更复杂。例如 `LEFT OUTER JOIN`：
- 只涉及右表列的谓词不能下推（因为右表可能输出 NULL 行）
- 只涉及左表列的谓词可以下推

**投影上的下推**（PushPredicateThroughNonJoin）也需要特殊处理。考虑：

```sql
SELECT a+1 AS x FROM t WHERE x > 10
```

这里的 `x > 10` 引用的是 Project 中定义的别名。如果盲目下推到 Project 之前，`x` 还未被定义。Spark 3.x 时代对此的简单处理是"如果引用了别名就不下推"——但这导致很多本可下推的谓词被阻止。

Spark 4.2 引入了一个更精细的策略：

```scala
// Optimizer.scala:2089-2100
// 将 Filter 按 && 拆分为独立组件
// 1) Filter 不引用任何 Project 中的列：直接下推
// 2) Filter 引用了"廉价"的 Project 表达式：解析引用后下推（允许局部双重求值）
// 3) Filter 引用了"昂贵"的 Project 表达式：留在 Project 之上
```

关键启发式判断是 `expensive` 标记——表达式是否包含子查询、UDF、正则匹配等高成本操作。

#### 谓词下推到 Aggregate

谓词下推到 Aggregate 之下有一个严格的前提：谓词必须只引用 Grouping Key 或常量。因为 Aggregate 改变了行与列的关系——在 GroupBy 之后，"`age > 10`"这个条件无法在原始行上求值。

```scala
// Optimizer.scala:2169
case filter @ Filter(condition, aggregate: Aggregate)
  if aggregate.aggregateExpressions.forall(_.deterministic)
    && aggregate.groupingExpressions.nonEmpty =>
  val (pushDown, stayUp) = splitConjunctivePredicates(condition).partition { cond =>
    val replaced = replaceAlias(cond, aliasMap)
    cond.deterministic && cond.references.nonEmpty &&
      replaced.references.subsetOf(aggregate.child.outputSet)
  }
```

能下推的谓词成为 `Filter(before_agg) → Aggregate → Filter(after_agg)`；不能下推的留在原地。

### 9.3 列裁剪（Column Pruning）

列裁剪解决的是 SELECT * 问题：**如果上层只需要 3 列，没必要在底层传输 100 列**。

`ColumnPruning` 以 `transformDown` 方式从顶层向底层传播"需要的列"：

```scala
// Optimizer.scala:1071
object ColumnPruning extends Rule[LogicalPlan] {
  def apply(plan: LogicalPlan): LogicalPlan = removeProjectBeforeFilter(
    plan.transformWithPruning(AlwaysProcess.fn, ruleId) {
    // Project → Project: 内层 Project 只保留外层引用的列
    case p @ Project(_, p2: Project) if !p2.outputSet.subsetOf(p.references) =>
      p.copy(child = p2.copy(projectList = p2.projectList.filter(p.references.contains)))
    // Project → Aggregate: Aggregate 只计算外层引用的聚合函数
    case p @ Project(_, a: Aggregate) if !a.outputSet.subsetOf(p.references) =>
      p.copy(
        child = a.copy(aggregateExpressions = a.aggregateExpressions.filter(p.references.contains)))
    // Join (Left Existence): 右子不需要任何输出列
    case j @ Join(_, right, LeftExistence(_), _, _) =>
      j.copy(right = prunedChild(right, j.references))
    // 通用：为任意子节点注入 Project 以裁剪无用列
    case p @ Project(_, child) if !child.isInstanceOf[Project] =>
      val required = child.references ++ p.references
      if (!child.inputSet.subsetOf(required)) {
        val newChildren = child.children.map(c => prunedChild(c, required))
        p.copy(child = child.withNewChildren(newChildren))
      } else { p }
  })
}
```

列裁剪有一个精妙之处：**它不是从上到下遍历一次就结束的**。因为 `operatorOptimizationRuleSet` 是 FixedPoint 策略，列裁剪会与别的规则交互。例如：

1. 列裁剪移除了 Project 中的无用列
2. CollapseProject 将相邻 Project 合并
3. 合并后，新的 Project 可能暴露了更多无用列
4. FixedPoint 迭代再次运行列裁剪

### 9.4 常量折叠与常量传播

这一组规则的目标是"在编译时消除运行时计算"。

**ConstantFolding**（常量折叠）：

```scala
// expressions.scala:50
object ConstantFolding extends Rule[LogicalPlan] {
  def apply(plan: LogicalPlan): LogicalPlan = plan.transformWithPruning(AlwaysProcess.fn, ruleId) {
    case q: LogicalPlan => q.mapExpressions(constantFolding(_))
  }

  private def constantFolding(e: Expression, isConditionalBranch: Boolean = false): Expression = {
    e match {
      case l: Literal => l  // 跳过 Literal，避免创建新对象和重复 eval
      case e if e.containsTag(FAILED_TO_EVALUATE) => e  // 不再尝试失败的折叠
      case e if e.foldable => tryFold(e, isConditionalBranch)  // foldable → 执行并替换为 Literal
      case other => other.mapChildren(constantFolding(_, isConditionalBranch))
    }
  }
}
```

`tryFold` 的核心是 `Literal.create(expr.eval(EmptyRow), expr.dataType)`——在 Driver 端执行表达式，将结果封装为 Literal。这等价于"编译时求值"。

注意 `isConditionalBranch` 标记：当折叠发生在 `CASE WHEN` 的分支内时（`case _: ConditionalExpression => mapChildren(constantFolding(_, true))`），求值失败不算错误——因为运行时可能根本不会执行这个分支。

**ConstantPropagation**（常量传播）：

```
FROM t WHERE i = 5 AND j = i + 3
→ FROM t WHERE i = 5 AND j = 8
```

这条规则在 `EqualTo` 谓词中发现 `Attribute = Literal` 的映射关系，然后在同级 AND 树的其他分支中用 Literal 替换这些 Attribute：

```scala
// expressions.scala:135
object ConstantPropagation extends Rule[LogicalPlan] {
  def apply(plan: LogicalPlan): LogicalPlan = plan.transformUpWithPruning(
    _.containsAllPatterns(LITERAL, FILTER, BINARY_COMPARISON), ruleId) {
    case f: Filter =>
      val (newCondition, _) = traverse(f.condition, replaceChildren = true, nullIsFalse = true)
      if (newCondition.isDefined) f.copy(condition = newCondition.get) else f
  }
}
```

**FoldablePropagation** 是其扩展：不仅传播 `EqualTo` 的常量，还传播任意 `foldable` 表达式（如 `Literal` + `Literal`）。

**NullPropagation** 和 **NullDownPropagation** 处理 "NULL 的传染性"：`AND false = false`，`NULL AND true → NULL`，`NULL OR true → true`。但 `NULL AND false → false`，因为 AND 在 false 上短路。

### 9.5 简化与合并（Simplification & Collapse）

**BooleanSimplification** 应用布尔代数规则：

```
true AND a → a
false AND a → false
a OR false → a
NOT true → false
a = a → true (且不是 nullable)
a AND (NOT a) → false
```

**SimplifyConditionals** 消除已知条件的分支：
```
IF(true, a, b) → a
IF(false, a, b) → b
CASE WHEN true THEN v END → v
```

**SimplifyCasts** 消除冗余类型转换：
```
CAST(a AS INT) → a  (如果 a 已经是 INT)
CAST(CAST(a AS LONG) AS INT) → CAST(a AS INT)
```

**CollapseProject** 合并相邻 Project：
```
Project[x+1 as y, ...](Project[x as a+1, ...](child))
→ Project[(a+1)+1 as y, ...](child)
```

其中关键的复杂度在于 `mergeProjectExpressions` 的别名替换——一个表达式引用另一个表达式时，要能用 `ReplaceAlias` 替换为具体定义。

**PruneFilters** 移除被约束"覆盖"的 Filter：
```
Filter(a > 10, Filter(a > 5, child)) → Filter(a > 10, child)
```
因为 `a > 10` 已经隐含了 `a > 5`。

**EliminateOuterJoin** 利用 Filter 中的 `IS NOT NULL` 条件将 Outer Join 简化为 Inner Join：

```scala
// joins.scala:158
object EliminateOuterJoin extends Rule[LogicalPlan] with PredicateHelper {
  private def buildNewJoinType(filter: Filter, join: Join): JoinType = {
    val conditions = splitConjunctivePredicates(filter.condition) ++ filter.constraints
    val leftHasNonNullPredicate = leftConditions.exists(canFilterOutNull)
    val rightHasNonNullPredicate = rightConditions.exists(canFilterOutNull)
    join.joinType match {
      case RightOuter if leftHasNonNullPredicate => Inner
      case LeftOuter if rightHasNonNullPredicate => Inner
      case FullOuter if leftHasNonNullPredicate && rightHasNonNullPredicate => Inner
      ...
    }
  }
}
```

例如 `SELECT * FROM t1 LEFT JOIN t2 ON ... WHERE t2.col IS NOT NULL`，因为 WHERE 条件已经保证了 t2 不会有 NULL 行，LEFT JOIN 可以降级为 INNER JOIN。

### 9.6 Filter 推断（Infer Filters from Constraints）

这是最"AI 式"的优化：**从已知约束中推断未知谓词**。

```scala
// Optimizer.scala:1758
object InferFiltersFromConstraints extends Rule[LogicalPlan]
  with PredicateHelper with ConstraintHelper {
  private def inferFilters(plan: LogicalPlan): LogicalPlan = plan.transformWithPruning(
    _.containsAnyPattern(FILTER, JOIN)) {
    case filter @ Filter(condition, child) =>
      val newFilters = filter.constraints --
        (child.constraints ++ splitConjunctivePredicates(condition))
      if (newFilters.nonEmpty) Filter(And(newFilters.reduce(And), condition), child)
      else filter

    case join @ Join(left, right, joinType, conditionOpt, _) =>
      joinType match {
        case _: InnerLike | LeftSemi =>
          val allConstraints = getAllConstraints(left, right, conditionOpt)
          val newLeft = inferNewFilter(left, allConstraints)
          val newRight = inferNewFilter(right, allConstraints)
          join.copy(left = newLeft, right = newRight)
        ...
      }
  }
}
```

例：`SELECT * FROM t1 JOIN t2 ON t1.id = t2.id WHERE t1.id = 5`。

从 `t1.id = 5` 和 `t1.id = t2.id`，Constraints 引擎推断出 `t2.id = 5`。InferFilters 将这个推断结果转换为 t2 侧的 `Filter(t2.id = 5)`——这可以在 Join 之前大幅减少 t2 的输入行。

Constraints 的底层是一个基于 `ExpressionSet` 的等价类管理器（`ConstraintHelper`），它跟踪 "哪些属性等于哪个常量" 和 "哪些属性等于哪些属性"。

### 9.7 子查询优化

**RewritePredicateSubquery** 将 `EXISTS`、`IN`、`ScalarSubquery` 重写为 Join 或 Aggregate：

```
WHERE col IN (SELECT a FROM t2)  →  LeftSemi Join(t1, Aggregate(t2))
WHERE col NOT IN (SELECT a FROM t2)  →  LeftAnti Join(t1, Aggregate(t2))
```

半连接/反连接的引入使得后续的谓词下推和 Join 优化规则可以"看到"并优化这些子查询。

**PullupCorrelatedPredicates** 处理相关子查询（Correlated Subquery）：将内层子查询中引用外层的谓词"上拉"到 Join 条件中：

```scala
// subquery.scala:462
object PullupCorrelatedPredicates extends Rule[LogicalPlan] with PredicateHelper {
  // 内层: Filter(a > outer.x) → 提取 outer.x 引用
  // 上拉: Join(t1, subquery, LeftSemi, Some(a > outer.x))
}
```

### 9.8 Join 重排序 — 启发式方法

在 CBO 禁用的默认模式下，`ReorderJoin` 使用启发式方法重排 Join 顺序：

```scala
// joins.scala:45
object ReorderJoin extends Rule[LogicalPlan] with PredicateHelper {
  @tailrec
  final def createOrderedJoin(input: Seq[(LogicalPlan, InnerLike)],
    conditions: Seq[Expression]): LogicalPlan = {
    // 贪心策略：优先选择"至少有 1 个 Join 条件"的 plan
    val conditionalJoin = rest.find { planJoinPair =>
      val plan = planJoinPair._1
      val refs = left.outputSet ++ plan.outputSet
      conditions.filterNot(canEvaluate).exists(_.references.subsetOf(refs))
    }
    val (right, innerJoinType) = conditionalJoin.getOrElse(rest.head)
    ...
  }
}
```

这是一个贪心算法（Greedy）：从左到右扫描，优先选择与当前 Join 图有连接条件（edge）的表。这避免了生成 Cross Join——在真正关系，Cross Join 是爆炸性的。

当 `starSchemaDetection` 开启且 CBO 禁用时，Spark 还会检测星形模式（Star Schema）：一张 Fact 表被多张 Dimension 表环绕，并优先与 Dimension 表 Join。

注意 `extendedOperatorOptimizationRules` 钩子——外部 Catalog 实现可以注入自定义规则。例如 Delta Lake 可以通过这个钩子注入自己的 Mark 修剪规则。

## 关键代码片段

### 示例：Select * 的终极优化路径

```scala
// 原始 SQL: SELECT a FROM (SELECT * FROM t1 JOIN t2 ON t1.id = t2.id) WHERE a > 10

// 输入（Resolved Logical Plan）:
// Project [a#0]
// +- Filter (a#0 > 10)
//    +- Project [a#0, b#1, c#2, d#3, e#4, f#5, g#6, h#7]
//       +- Join (id#0 = id#4)
//          +- Relation t1 [a#0, b#1, c#2, id#0]
//          +- Relation t2 [d#3, e#4, f#5, g#6, h#7, id#4]

// 第1步: PushDownPredicates 将 a > 10 下推到 Join 之下
// Filter(a>10) 引用只涉及 t1 → 下推到 left 侧
// → Project [a] +- Project [a,b,c,d,e,f,g,h] +- Join +- Filter(a>10) +- Relation t1

// 第2步: ColumnPruning 发现内层 Project 只需要 t1 的 a, id 和 t2 的 id
// → 裁剪 Join 两侧的输出列

// 第3步: CollapseProject 合并两层 Project

// 输出（Optimized Logical Plan）:
// Project [a#0]
// +- Join (id#0 = id#4)
//    +- Filter (a#0 > 10) +- Project [a#0, id#0] +- Relation t1
//    +- Project [id#4] +- Relation t2
```

### 示例：一条简化规则的实现

从 `booleanSimplification` 中提取简化 OR 的例子：

```scala
// expressions.scala
// 简化 a OR (a AND b) → a
// 简化 a OR (b AND a) → a
case Or(left, right @ And(_, _)) if canSimplifyOrWithLeftCond(left, right) => left
case Or(left @ And(_, _), right) if canSimplifyOrWithLeftCond(right, left) => right
```

这对应布尔代数中的 **吸收律**：`A ∨ (A ∧ B) ≡ A`。

## 硬件视角

Optimizer 的一个微妙悖论：**它是纯逻辑的——不处理任何数据——但它的输出决定了数据处理的物理效率**。

更具体地说，Optimizer 在 JVM 上运行（大量小对象分配），而它的"客户"——执行引擎——可能在 100 台机器的集群上运行。这意味着 Optimizer 上的 1KB 额外分配（用于构建 LogicalPlan），在优化成功后，可能节省集群上 1GB 的数据传输。

但这里有一个 **间接开销** 值得量化。operatorOptimizationRuleSet 被执行 2 次（Infer Filters 前后），每次 FixedPoint 迭代可能遍历树 3-5 次。假设一个 200 节点的 LogicalPlan：

- 每次遍历 = 200 次 Rule 匹配尝试
- 约 50 条规则 × 200 节点 = 10,000 次 `PartialFunction.applyOrElse` 检查
- 2 次 batch × 3 次 FixedPoint 迭代 = 6 次全遍历
- **总计: 6 × 50 × 200 = 60,000 次规则评估**

大部分评估只是 case match 失败——十几个 CPU 周期。但少数成功的规则会触发 `mapChildren`（构建新节点），产生对象分配。这个 GC 开销就是第 8 章讨论的"不可变树模型"代价。

**Optimizer 本身适合 GPU 加速吗？** 不适合。树遍历是 **control-flow intensive** 的工作负载——每个节点的下一步取决于 pattern match 的动态结果。GPU 擅长的 data-parallel 模式在这里找不到匹配——70 条规则，每条有不同的匹配模式，且上一条规则的结果决定下一条规则看到什么树。

更好的硬件适配方向是 **减少迭代次数**——这与 HybridAnalyzer（第 8 章）的单趟思想一致。如果能在一遍遍历中同时做下推、裁剪和折叠，就能把 6 次遍历合并为 1-2 次。

## AI 时代反思

如果把数据库优化器看作一个 **自动定理证明器**（它证明两个 LogicalPlans 是等价的），那么 LLM 在 Optimizer 面前的角色是什么？

一种简单的答案是：**LLM 远不如 Optimizer。** LLM 不能严格证明两个计划的等价性——它只能生成"看起来正确"的 SQL。将 LLM 输出交给不具备验证能力的系统是危险的。

但另一种更微妙的答案是：**LLM 可以发现数据库学术圈还没有发表的优化规则。** 考虑以下场景：

- 在 10 万条真实查询日志上观察"慢查询"的模式
- LLM 分析这些模式，提出候选规则：例如"在特定数据分布下，将 `(a > 10) OR (a = 5)` 重写为 `a >= 5` 能触发更好的索引利用"
- 自动定理证明器（如 Z3）验证这条规则的形式等价性
- 验证通过 → 规则自动注入 Operator Optimization Rule Set

这条路径将 **AI 的创造力**（规则发现）与 **形式方法的可靠性**（等价性证明）结合起来。它比 "LLM 直接写 SQL" 安全得多——因为输出是优化规则，不是最终结果。

实用地说，未来最好的 "SQL 优化 Prompt" 可能是把 `SessionCatalog`（表、列的 schema 和统计信息）作为 RAG 上下文喂给 LLM，让 LLM 生成完全不同的、但语义等价的 SQL 文本，再由传统 Optimizer 优化和验证——双重保证：LLM 提供"人类直觉"，Optimizer 提供"数学保证"。

另一个观察：**Optimizer 的规则是"声明式"的——每条规则描述"什么情况→做什么变换"，但没有描述"为什么这个变换是好的"**。在 AI 框架中，Cost Model 提供了这个"为什么"——它评价变换后的计划比变换前更"廉价"。但 Catalyst 的 Cost Model 目前很粗（主要是 Join Reorder 用）。如果引入更细粒度的 Cost Model（类似 ORCA 的 cost-based transformation），Optimizer 的工作模式将从 "确定性应用规则" 转变为 "搜索 + 评估"——而这恰恰是 AlphaGo/强化学习擅长的范式。

## 源码导航

| 文件 | 关键内容 | 行号参考 |
|------|---------|---------|
| `sql/catalyst/src/main/scala/org/apache/spark/sql/catalyst/optimizer/Optimizer.scala` | Optimizer 类，defaultBatches，fixedPoint 策略，PushDownPredicates，ColumnPruning，CollapseProject，InferFiltersFromConstraints，PruneFilters，EliminateLimits | 51 (类定义), 73 (fixedPoint), 100 (defaultBatches), 889 (LimitPushDown), 999 (PushProjectionThroughUnion), 1071 (ColumnPruning), 1226 (CollapseProject), 1580 (CollapseRepartition), 1711 (InferFiltersFromGenerate), 1758 (InferFiltersFromConstraints), 2065 (PushDownPredicates), 2342 (PushPredicateThroughJoin) |
| `sql/catalyst/src/main/scala/org/apache/spark/sql/catalyst/optimizer/expressions.scala` | ConstantFolding，ConstantPropagation，FoldablePropagation，NullPropagation，BooleanSimplification，SimplifyConditionals，SimplifyCasts，OptimizeIn | 50 (ConstantFolding), 135 (ConstantPropagation) |
| `sql/catalyst/src/main/scala/org/apache/spark/sql/catalyst/optimizer/joins.scala` | ReorderJoin，EliminateOuterJoin，ExtractPythonUDFFromJoinCondition | 45 (ReorderJoin), 158 (EliminateOuterJoin) |
| `sql/catalyst/src/main/scala/org/apache/spark/sql/catalyst/optimizer/subquery.scala` | RewritePredicateSubquery，PullupCorrelatedPredicates，RewriteCorrelatedScalarSubquery | 56 (RewritePredicateSubquery), 462 (PullupCorrelatedPredicates), 693 (RewriteCorrelatedScalarSubquery) |
| `sql/catalyst/src/main/scala/org/apache/spark/sql/catalyst/optimizer/InlineCTE.scala` | CTE 内联策略，alwaysInline 条件 | |
| `sql/catalyst/src/main/scala/org/apache/spark/sql/catalyst/optimizer/OptimizeJoinCondition.scala` | Join 条件优化 |
| `sql/catalyst/src/main/scala/org/apache/spark/sql/catalyst/optimizer/PushDownLeftSemiAntiJoin.scala` | LeftSemi/LeftAnti Join 下推 |
| `sql/catalyst/src/main/scala/org/apache/spark/sql/catalyst/optimizer/NestedColumnAliasing.scala` | 嵌套列别名优化（VARIANT/JSON） |
| `sql/catalyst/src/main/scala/org/apache/spark/sql/catalyst/optimizer/RewriteDistinctAggregates.scala` | count(distinct) → 两阶段聚合展开 |
| `sql/catalyst/src/main/scala/org/apache/spark/sql/catalyst/optimizer/CostBasedJoinReorder.scala` | CBO Join 重排序 |
| `sql/catalyst/src/main/scala/org/apache/spark/sql/catalyst/optimizer/PushdownPredicatesAndPruneColumnsForCTEDef.scala` | CTE 定义的谓词下推和列裁剪 |
