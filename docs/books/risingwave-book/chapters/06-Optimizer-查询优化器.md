# 第 6 章 · Optimizer——查询优化器

> **核心源码**：`src/frontend/src/optimizer/`
> **关键子模块**：`rule/`（优化规则）、`plan_node/`（逻辑/物理算子）、`property/`（物理属性）、`plan_rewriter/`（计划重写）
> **优化架构**：Rule-based Heuristic Optimizer + Logical Rewrite

---

## 6.1 Optimizer 的定位与架构

RisingWave 的 Optimizer 采用 **Rule-based（启发式规则）** 架构，这与 Spark Catalyst 的基于规则的优化器在理念上相似。优化通过一系列有序的 `OptimizationStage` 进行，每个阶段包含一组 `Rule`，按 `BottomUp` 或 `TopDown` 顺序应用。

```
Logical Plan → Stage1 → Stage2 → ... → StageN → Optimized Logical Plan
                                                    │
                                          ┌─ Batch ─┤→ BatchPhysical Plan
                                          │         │
                                          └─ Stream─┘→ StreamPhysical Plan
```

> **第一性原理思考**：为什么需要优化器？SQL 是声明式语言，用户描述"要什么"，不描述"怎么做"。同一个查询有无数种等价的执行方案。优化器的工作是在这个巨大的搜索空间中，找到一个执行成本足够低的方案。RisingWave 选择启发式规则而非 Cascades 等代价模型，是因为流式查询的代价估算远比批处理复杂——状态大小、更新频率、watermark 延迟等都是动态的，精准的代价模型几乎不可能。用一组可靠的启发式规则，反而更高效和可预测。

---

## 6.2 OptimizationStage——优化管道的基本单元

```rust
// logical_optimization.rs:91-108
pub struct OptimizationStage<C: ConventionMarker = Logical> {
    stage_name: String,
    rules: Vec<BoxedRule<C>>,
    apply_order: ApplyOrder,     // TopDown | BottomUp
}
```

每个 `OptimizationStage` 对应一组语义相关的优化，通过 `LazyLock` 静态定义。例如：

```rust
// logical_optimization.rs:139-160
static TABLE_FUNCTION_CONVERT: LazyLock<OptimizationStage> = LazyLock::new(|| {
    OptimizationStage::new(
        "Table Function Convert",
        vec![
            TableFunctionToFileScanRule::create(),
            TableFunctionToInternalBackfillProgressRule::create(),
            TableFunctionToPostgresQueryRule::create(),
            TableFunctionToProjectSetRule::create(),
            // ...
        ],
        ApplyOrder::TopDown,
    )
});
```

规则的执行通过 `optimize_by_rules` 方法触发（`logical_optimization.rs:62-71`）：

```rust
pub(crate) fn optimize_by_rules(self, stage: &OptimizationStage<C>) -> Result<PlanRef<C>> {
    self.optimize_by_rules_inner(
        &mut HeuristicOptimizer::new(stage.apply_order, &stage.rules),
        &stage.stage_name
    )
}
```

支持两种迭代模式：
- **单次应用**（`optimize_by_rules`）：遍历一次计划树即可
- **不动点迭代**（`optimize_by_rules_until_fix_point`）：重复应用直到没有规则再被触发

---

## 6.3 HeuristicOptimizer——规则执行引擎

```rust
// heuristic_optimizer.rs:38-43
pub struct HeuristicOptimizer<'a, C: ConventionMarker> {
    apply_order: &'a ApplyOrder,
    rules: &'a [BoxedRule<C>],
    stats: Stats,
}
```

优化器核心是两个方法的交替递归（`heuristic_optimizer.rs:53-68`）：

```rust
fn optimize_node(&mut self, mut plan: PlanRef<C>) -> Result<PlanRef<C>> {
    for rule in self.rules {
        match rule.apply(plan.clone()) {
            ApplyResult::Ok(applied) => {
                plan = applied;
                self.stats.count_rule(rule);
            }
            ApplyResult::NotApplicable => {}
            ApplyResult::Err(error) => return Err(error),
        }
    }
    Ok(plan)
}
```

**BottomUp** 模式：先递归优化子节点，再优化当前节点。

```
    optimize(node):
        for child in node.children:
            child = optimize(child)
        node = optimize_node(node)
        return node
```

**TopDown** 模式：先优化当前节点，再递归优化子节点。

```
    optimize(node):
        node = optimize_node(node)
        for child in node.children:
            child = optimize(child)
        return node
```

每个 `Rule` 的 `apply` 返回三种结果：
- `ApplyResult::Ok(applied)`：规则匹配并成功应用，返回新计划
- `ApplyResult::NotApplicable`：规则不匹配当前节点
- `ApplyResult::Err(error)`：匹配但应用失败

---

## 6.4 核心优化规则分类

### 6.4.1 子查询非嵌套化（Subquery Unnesting）

这是最重要的逻辑优化。相关子查询存在时执行效率极差（嵌套循环），必须扭转为 Join 或 Apply。

```rust
// logical_optimization.rs:221-229
static SIMPLE_UNNESTING: LazyLock<OptimizationStage> = LazyLock::new(|| {
    OptimizationStage::new("Simple Unnesting", vec![
        PullUpCorrelatedPredicateRule::create(),      // 将相关谓词上拉到 Apply
        PullUpCorrelatedProjectValueRule::create(),    // 标量子查询内联
        ApplyProjectRemoveRule::create(),              // 清理 Apply 上的投影
        ApplyTopNTransposeRule::create(),              // Apply + TopN 重排
        ApplyLimitTransposeRule::create(),             // Apply + Limit 重排
        ApplyFilterScanRule::create(),                 // 将 Apply 转为 Semi/Anti Join
    ], ApplyOrder::TopDown)
});
```

### 6.4.2 谓词下推（Predicate Pushdown）

将 Filter 尽可能推到数据源附近，减少中间数据量。

```rust
// logical_optimization.rs:431-438
static PREDICATE_PUSHDOWN: LazyLock<OptimizationStage> = LazyLock::new(|| {
    OptimizationStage::new("Predicate Push Down", vec![
        FilterMergeRule::create(),
        PredicatePushdownRule::create(),
    ], ApplyOrder::TopDown)
});
```

### 6.4.3 列剪枝（Column Pruning）

去掉不需要的列，减少数据传输和内存占用。

```rust
// logical_optimization.rs:449-454
static COLUMN_PRUNING: LazyLock<OptimizationStage> = LazyLock::new(|| {
    OptimizationStage::new("Column Pruning", vec![
        ColumnPruningRule::create(),
    ], ApplyOrder::TopDown)
});
```

### 6.4.4 流式特有优化

除了通用优化，RisingWave 还有流式独有的优化规则：

- **Delta Join Rewrite**（`IndexDeltaJoinRule`）：多个 Join 共享相同的连接键且需要维护状态索引时，重写为 Delta Join，减少状态冗余
- **Logstore Insertion**（`AddLogstoreRule`）：对 Unaligned Join 插入同步 KV Log Store，用于对齐不同输入流的 barrier
- **Backfill 策略选择**：根据配置和数据特征，选择 `SnapshotBackfill`、`ArrangementBackfill` 或标准 `Backfill`
- **Locality Provider**：利用数据本地性信息的优化，减少跨节点数据传输
- **Project Merge**（`StreamProjectMergeRule`）：合并相邻的 Project 节点，减少投影层数

---

## 6.5 计划阶段转换——PlanPhase 体系

Optimizer 通过 `PlanPhase` 体系跟踪计划的转换阶段（`mod.rs:126-151`）：

```rust
pub trait PlanPhase {
    type Convention: ConventionMarker;
}

// 五个阶段
{ Logical, Convention = Logical }         // 初始逻辑计划
{ BatchOptimizedLogical, Convention = Logical }  // 批优化后的逻辑计划
{ StreamOptimizedLogical, Convention = Stream }  // 流优化后的流计划
{ Batch, Convention = Batch }             // 批物理计划
{ Stream, Convention = Stream }           // 流物理计划
```

典型转换路径：

```
LogicalPlanRoot          → gen_optimized_logical_plan_for_stream()
StreamOptimizedLogicalPlanRoot → gen_stream_plan()
StreamPlanRoot            → gen_optimized_stream_plan_inner()
  │
  ├─ gen_materialize_plan()  → StreamMaterialize
  ├─ gen_sink_plan()         → StreamSink
  └─ gen_table_plan()        → StreamMaterialize (for table)
```

```rust
// mod.rs:306-309
pub fn gen_optimized_logical_plan_for_stream(mut self) -> Result<LogicalPlanRoot> {
    self.plan = LogicalOptimizer::gen_optimized_logical_plan_for_stream(self.plan.clone())?;
    Ok(self)
}
```

每条路径最终得到的都是具体的**物理算子**（StreamMaterialize / StreamSink），它们包含了分布信息、并行度、状态存储需求等运行时约束。

---

## 6.6 LogicalOptimizer 的全量优化 Pipeline

对于流计算场景，`LogicalOptimizer::gen_optimized_logical_plan_for_stream` 执行的完整优化管道如下：

```rust
// logical_optimization.rs:685-732 (简化)
fn gen_optimized_logical_plan_for_stream(plan: LogicalPlanRef) -> Result<LogicalPlanRef> {
    plan
        .optimize_by_rules(&DAG_TO_TREE)?                          // 1. DAG→Tree
        .optimize_by_rules(&STREAM_GENERATE_SERIES_WITH_NOW)?      // 2. generate_series特殊处理
        .optimize_by_rules(&TABLE_FUNCTION_CONVERT)?               // 3. 表函数转换
        .optimize_by_rules(&VALUES_EXTRACT_PROJECT)?               // 4. Values提取
        .optimize_by_rules(&SIMPLE_UNNESTING)?                     // 5. 子查询非嵌套
        // ... Apply优化 ...
        .optimize_by_rules_until_fix_point(&PREDICATE_PUSHDOWN)?   // 6. 谓词下推(不动点)
        .optimize_by_rules(&UNION_MERGE)?                          // 7. Union合并
        .optimize_by_rules(&COLUMN_PRUNING)?                       // 8. 列剪枝
        .optimize_by_rules(&GROUP_BY_PUSHDOWN)?                    // 9. GroupBy下推
        // ... 流式特有优化 ...
}
```

每个阶段的顺序是经过审慎设计的：
- **DAG→Tree 放最前**：将共享算子（CTE/Shared View）展开为独立子树，使后续规则能在各子树上独立工作
- **子查询非嵌套在谓词下推之前**：不先解开子查询，下推就无从谈起
- **谓词下推用不动点迭代**：过滤条件可能需要多轮传播才能到达最优位置
- **列剪枝在最后**：所有算子变换稳定后，才能精确确定哪些列最终需要

---

## 6.7 Rule trait——规则的统一接口

```rust
// rule/mod.rs (简化)
pub trait Rule<C: ConventionMarker>: Send + Sync {
    fn apply(&self, plan: PlanRef<C>) -> ApplyResult<C>;
    fn description(&self) -> &str;
}

pub type BoxedRule<C> = Box<dyn Rule<C>>;
```

每条 `Rule` 是一个策略模式实现。`apply` 接收计划节点，检查是否匹配规则模式，若匹配则返回变换后的新计划。

典型的 Rule 实现模式：

```
MyRule::apply(plan):
    match plan.node_type() {
        // 检查模式：Filter(Join(left, right))
        LogicalFilter if plan.input is LogicalJoin =>
            // 提取 join 条件
            let join_cond = plan.input.condition
            let filter_cond = plan.condition
            // 尝试将 filter_cond 合并到 join_cond 中
            // 生成新的 Join(left, right, merged_condition)
            return ApplyResult::Ok(new_plan)
        _ =>
            return ApplyResult::NotApplicable
    }
```

---

## 6.8 流计划的物理转换——to_stream

逻辑计划到流物理计划的核心方法是 `to_stream_with_dist_required`（在 `plan_node` 各算子的 `ToStream` trait 实现中）。它处理几个关键转换：

1. **TableScan → ChainExecutor + Backfill**：从静态表扫描变为流式 changelog 消费
2. **Join → StreamHashJoin**：带上状态存储（Hummock 中的 Join State Table）
3. **Agg → StreamHashAgg**：带上聚合状态（Agg State Table，多版本增量维护）
4. **插入 Exchange**：根据分布要求插入 `StreamExchange` 节点，确保数据正确分区

例如，一个简单的 `SELECT count(*) FROM t` 在 `to_stream` 后的物理计划是：

```
StreamMaterialize
  └── StreamHashAgg (stateful)
        └── StreamExchange (hash-distributed)
              └── StreamTableScan (backfill + changelog)
```

---

## 6.9 与 DataFusion 的关系

RisingWave 在 `datafusion` feature gate 下支持将优化后的逻辑计划导出为 DataFusion 逻辑计划（`mod.rs:391-446`）。这是因为 RisingWave 利用 DataFusion 执行 Iceberg 表的批查询。

```rust
#[cfg(feature = "datafusion")]
pub fn gen_datafusion_logical_plan(&self) -> Result<Arc<datafusion::logical_expr::LogicalPlan>> {
    let mut plan = inline_session_timezone_in_exprs(ctx, self.plan.clone())?;
    plan = const_eval_exprs(plan)?;
    let mut df_plan = plan.to_datafusion_logical_plan()?;
    // ... 添加排序和投影
    Ok(df_plan)
}
```

这种混合引擎设计使得 RisingWave 能同时提供**低延迟的行存查询**（通过自己的流/批引擎）和**开放格式的分析查询**（通过 DataFusion over Iceberg）。

---

## 6.10 小结

RisingWave 的 Optimizer 展示了一个面向流计算场景的实用主义优化架构：

- **Heuristic Optimizer** 提供可组合的规则执行框架，支持 BottomUp/TopDown 遍历
- **OptimizationStage** 将规则按语义分组，按严格顺序执行
- **Rule 体系** 覆盖了通用 SQL 优化（谓词下推、列剪枝、子查询非嵌套）和流式特有优化（Delta Join、Logstore、Backfill 策略）
- **PlanPhase** 体系跟踪计划的转换阶段，从逻辑计划逐步走向物理计划
- 对 DataFusion 的集成实现了"流计算引擎 + 开放格式分析引擎"的混合架构

从下一章开始，我们将深入物理计划和 Fragment Graph，看优化后的计划如何被切分为可调度执行的 Actor 拓扑。

---

*本章完成。下一章：[第 7 章 · 物理计划到 Fragment Graph](../chapters/07-物理计划到Fragment-Graph.md)*
