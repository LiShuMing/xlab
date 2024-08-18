# 第 5 章 · Planner——逻辑计划生成

> **核心源码**：`src/frontend/src/planner/`
> **关键输出**：`LogicalPlanRoot` → 进入 Optimizer 的入口
> **依赖**：Binder 的 `BoundStatement`、Optimizer 的 `plan_node` 体系

---

## 5.1 Planner 的定位

在 RisingWave 的 SQL 编译链路中，Planner 是 Binder 和 Optimizer 之间的桥梁：

```
Parser → Binder → Planner → Optimizer → Fragmenter → Meta
  AST    Bound*   PlanRef    PlanRef     Fragment
```

Planner 的输入是 `BoundStatement`（语义完整的绑定结果），输出是 `PlanRef`（逻辑计划树的根节点）。它做的是**结构化翻译**——将 Binder 产生的关系-表达式树，转换为 Optimizer 能理解的算子-DAG。

> **第一性原理思考**：Planner 和 Binder 的边界在哪？Binder 回答"这段 SQL 说的是什么"，Planner 回答"这段 SQL 应该怎么算"。前者是语义分析（what），后者是逻辑计划（how）。这个分工和任何编译器前端都一样——先把名字绑定到实体，再把实体组织成执行图。区别在于，SQL 的执行图不是线性的指令序列，而是有向无环的算子图。

---

## 5.2 Planner 的结构

```rust
// planner/mod.rs:37-44
pub struct Planner {
    ctx: OptimizerContextRef,
    share_cache: HashMap<ShareId, PlanRef>,
    plan_for: PlanFor,
}

pub enum PlanFor {
    Stream,                        // MV/SINK 的流式计划
    StreamIcebergEngineInternal,   // Iceberg 引擎 Sink 的内部模式
    Batch,                         // DML 批处理
    BatchDql,                      // SELECT 查询
}
```

`share_cache` 是 Planner 的核心状态，用于缓存共享关系的计划结果。例如 CTE 首次被引用时生成 PlanRef 并存入缓存，后续引用直接复用——这避免了重复计划。

`PlanFor` 影响计划的生成策略。在 `Stream` 模式下，某些算子需要额外的状态信息（如 Materialize 的 barrier 处理）；在 `Batch` 模式下，算子可以选择不同的物理实现。

---

## 5.3 计划入口——从 BoundStatement 到 LogicalPlanRoot

`plan_statement` 是所有计划的入口（`planner/statement.rs:21`）：

```rust
pub(super) fn plan_statement(&mut self, stmt: BoundStatement) -> Result<LogicalPlanRoot> {
    match stmt {
        BoundStatement::Insert(i)    => self.plan_insert(*i),
        BoundStatement::Delete(d)    => self.plan_delete(*d),
        BoundStatement::Update(u)    => self.plan_update(*u),
        BoundStatement::Query(q)     => self.plan_query(*q),
        BoundStatement::DeclareCursor(d) => self.plan_query(*d.query),
        BoundStatement::CreateView(c)    => self.plan_query(*c.query),
        // ...
    }
}
```

`plan_query` 是查询计划的主入口（`planner/query.rs:31`）：

```rust
pub fn plan_query(&mut self, query: BoundQuery) -> Result<LogicalPlanRoot> {
    let out_names = query.schema().names();
    let BoundQuery { body, order, limit, offset, with_ties, extra_order_exprs } = query;

    // 1. 计划 SET 表达式（SELECT / VALUES / UNION / ...）
    let mut plan = self.plan_set_expr(body, extra_order_exprs, &order)?;

    // 2. LIMIT / OFFSET 处理
    if limit.is_some() || offset.is_some() {
        let order = ...; // 优化的排序键
        if order.column_orders.is_empty() {
            plan = LogicalLimit::create(plan, limit, offset);  // 无排序 → Limit
        } else {
            plan = LogicalTopN::create(plan, limit, offset, order, with_ties, ...)?; // 有排序 → TopN
        }
    }

    // 3. 包装为 PlanRoot
    PlanRoot::new_with_logical_plan(plan, RequiredDist::Any, order, out_fields, out_names)
}
```

这个流程揭示了 RisingWave 如何处理 `ORDER BY + LIMIT`：在有排序键时生成 `LogicalTopN`（可以用堆维护），无排序键时生成 `LogicalLimit`（只需截断）。这是一个典型的 **逻辑优化前置**——在计划阶段就做出算子选择决策。

---

## 5.4 plan_select——SELECT 语句的计划

`plan_select` 是 Planner 中最复杂的方法（`planner/select.rs:45-199`）。它严格遵循标准 SQL 的逻辑计算顺序生成计划：

```
FROM → WHERE → GROUP BY / HAVING → SELECT (投影)
  │       │         │                   │
  ▼       ▼         ▼                   ▼
plan_    Logical    Logical         Logical
relation  Filter    Agg / Filter    ProjectSet
```

同时穿插处理几种特殊情况：

### 5.4.1 SELECT DISTINCT

```rust
if let BoundDistinct::Distinct = distinct {
    let group_key = (0..fields.len()).collect();
    root = Agg::new(vec![], group_key, root).into();
}
```

`SELECT DISTINCT` 被 TrickyDown 为 **不带聚合函数的 Group By**。`Agg::new(vec![], group_key, root)` 表示对所有列分组，且不计算任何聚合表达式。这是经典的"DISTINCT = GROUP BY all columns"重写。

### 5.4.2 SELECT DISTINCT ON

```rust
if matches!(&distinct, BoundDistinct::DistinctOn(_)) {
    if order.is_empty() {
        root = LogicalDedup::new(root, distinct_list_index_to_select_items_index).into();
    } else {
        root = LogicalTopN::new(root, 1, 0, false, Order::new(order.to_vec()), ...).into();
    }
}
```

`DISTINCT ON` 的语义是"对于每组 DISTINCT ON 列不同的值，只保留第一行"。在没有 ORDER BY 时，使用 `LogicalDedup` 算子去重；有 ORDER BY 时，使用 `LogicalTopN`（每组取第一行）——这是 Spark 的 `ROW_NUMBER()` 窗口函数的等价转换。

### 5.4.3 子查询处理

子查询是 `plan_select` 的另一个复杂之处。RisingWave 采用两种策略处理 SELECT 列表中的子查询：

1. **Cross Join 方式**（`substitute_subqueries_in_cross_join_way`）：多个子查询通过 Cross Join 组合到 Apply 的右子树中，适用于 SELECT 中的标量子查询。

```
        Apply
       /    \
     left   CrossJoin
               /   \
       Subquery1   CrossJoin
                     /   \
             Subquery2   Subquery3
```

2. **Left Deep Tree 方式**（`substitute_subqueries_in_left_deep_tree_way`）：子查询逐个 Apply 到主查询上，逐层嵌套，适用于 WHERE 中的子查询。

```
          Apply
         /    \
       Apply  Subquery3
      /    \
    Apply  Subquery2
    /   \
  left  Subquery1
```

两种策略的选择在于性能优化：Cross Join 方式对多个标量子查询更高效（减少 Apply 的嵌套层数），而 Left Deep Tree 方式对 WHERE 中的子查询更有意义（因为通常不会在同一个 WHERE 中多次使用子查询）。

---

## 5.5 关系计划——plan_relation

`plan_relation` 将 Binder 产生的 `Relation` 枚举转换为 `PlanRef`。其核心在 `planner/relation.rs`：

```
Relation                →  PlanRef
────────────────────────────────────────
Source(Catalog)         →  LogicalSource
BaseTable(Catalog)      →  batch: LogicalSeqScan / stream: LogicalSource
SystemTable(Catalog)    →  LogicalSysSeqScan
Subquery(BoundQuery)    →  递归 plan_query
Join(Left, Right, ...)  →  LogicalJoin / LogicalApply
WindowTableFunction     →  LogicalWindowTableFunction
TableFunction           →  LogicalTableFunction
Share(ShareId)          →  从 share_cache 获取（CTE 去重）
GapFill(Input, ...)     →  LogicalGapFill
```

共享关系（CTE、Shared View）通过 `share_cache` 实现去重：

```rust
// 首次遇到 CTE → 计划并缓存
let plan = self.plan_query(cte_query)?;
self.share_cache.insert(share_id, plan.clone());

// 后续引用 → 直接复用
if let Some(plan) = self.share_cache.get(&share_id) {
    return plan.clone();
}
```

---

## 5.6 plan_set_expr——UNION 与集合操作

`planner/set_expr.rs` 处理 SQL 的集合操作：

```rust
// SET 表达式的主入口
pub(super) fn plan_set_expr(
    &mut self,
    body: BoundSetExpr,
    extra_order_exprs: Vec<ExprImpl>,
    order: &[ColumnOrder],
) -> Result<PlanRef> {
    match body {
        BoundSetExpr::Select(s) => self.plan_select(s, extra_order_exprs, order),
        BoundSetExpr::Values(v) => self.plan_values(*v, extra_order_exprs),
        BoundSetExpr::SetOperation(op) => self.plan_set_operation(op),
    }
}
```

`plan_set_operation`（`planner/set_operation.rs`）处理 `UNION / INTERSECT / EXCEPT`：

```rust
pub(super) fn plan_set_operation(
    &mut self,
    op: BoundSetOperation,
) -> Result<PlanRef> {
    match op.op {
        SetOp::Union       => LogicalUnion::create(left, right, all),
        SetOp::Intersect   => LogicalIntersect::create(left, right, all),
        SetOp::Except      => LogicalExcept::create(left, right, all),
    }
}
```

---

## 5.7 LogicalPlanRoot——进入 Optimizer 的桥梁

`PlanRoot` 是 Planner 的最终产出（`planner/query.rs:77`）：

```rust
let root = PlanRoot::new_with_logical_plan(
    plan,                    // 逻辑计划的根节点
    RequiredDist::Any,      // 分布要求（单机查询可以任意）
    order,                   // 排序要求
    out_fields,              // 输出列位图
    out_names,               // 输出列名
);
Ok(root)
```

`PlanRoot::new_with_logical_plan` 的职责是"包裹"。它将逻辑计划树的根节点与输出约束（排序、分布）打包在一起，交给 Optimizer 处理。Optimizer 拿到 `LogicalPlanRoot` 后，根据 `RequiredDist` 和排序需求，决定是否需要插入 `Exchange` 或 `Sort` 算子。

---

## 5.8 plan_node 体系概览

Planner 产出的逻辑计划由 `plan_node/` 下的算子定义。这是一个庞大的类型体系：

| 类别 | 算子 | 说明 |
|------|------|------|
| 扫描 | `LogicalSeqScan` / `LogicalSource` / `LogicalFileScan` / `LogicalIcebergScan` | 数据读取 |
| 过滤 | `LogicalFilter` | WHERE 条件 |
| 投影 | `LogicalProject` / `LogicalProjectSet` | SELECT 列 |
| 聚合 | `LogicalAgg` / `LogicalSimpleAgg` / `LogicalHashAgg` / `LogicalSortAgg` | GROUP BY + 聚合 |
| 排序 | `LogicalSort` / `LogicalTopN` / `LogicalGroupTopN` | ORDER BY / LIMIT |
| 连接 | `LogicalJoin` / `LogicalApply` / `LogicalLookupJoin` | JOIN |
| 集合 | `LogicalUnion` / `LogicalIntersect` / `LogicalExcept` | UNION / INTERSECT / EXCEPT |
| 窗口 | `LogicalOverWindow` / `LogicalHopWindow` | 窗口函数 / Hop 窗口 |
| 其他 | `LogicalValues` / `LogicalInsert` / `LogicalDelete` / `LogicalUpdate` / `LogicalDedup` / `LogicalExpand` / `LogicalGapFill` | 特殊操作 |

每个逻辑算子都是一个结构体，持有子节点引用（`PlanRef`）和自身特有的属性。它们统一实现一个通用的 `PlanTreeNode` trait（在 `plan_node` 的 mod.rs 中定义），提供 `inputs()` / `clone_with_inputs()` 等方法，使 Optimizer 能统一遍历和变换计划树。

---

## 5.9 从 BoundStatement 到 PlanRef 的完整示例

以 `SELECT name, count(*) FROM users WHERE age > 18 GROUP BY name` 为例：

```rust
// 1. plan_select 被调用
// from = BoundBaseTable { table_id: 42, schema: [id, name, age] }
// where = ExprImpl(GreaterThan(InputRef(2), Literal(18)))
// select_items = [InputRef(1), AggCall(Count, [])]
// group_by = GroupKey([InputRef(1)])
```

生成流程：

```
① plan_relation → LogicalSeqScan(users_table)
         │
② LogicalFilter(GreaterThan(InputRef(2), Literal(18)))
         │
③ LogicalAgg(
     agg_calls=[CountStar],        ← 聚合表达式
     group_key=GroupKey([1]),      ← 分组键：name 位于 schema 的 index 1
     input=Filter                  ← 子节点
   )
         │
④ LogicalProjectSet([InputRef(1), AggCall(0)])
   → 输出列：name (原表 index 1) 和 count (聚合结果 index 0)
```

最终生成的计划树：

```
     LogicalProjectSet
     [name, count(*)]
           │
      LogicalAgg
   group_key=[1]
   agg_calls=[CountStar]
           │
     LogicalFilter
   age > Literal(18)
           │
    LogicalSeqScan
     users_table
```

这正是 PostgreSQL 的 `EXPLAIN` 输出格式的等价树形表示。Planner 完成后，这棵树就进入 Optimizer 的规则引擎进行变换和优化。

---

## 5.10 小结

Planner 是 RisingWave SQL 编译管线中"结构化翻译"的一步：

- 输入：`BoundStatement`（Binder 的语义分析结果）
- 输出：`PlanRef` 的树形结构（逻辑算子 DAG），包装在 `LogicalPlanRoot` 中
- 核心方法：`plan_select` 按 SQL 逻辑顺序逐阶段构建算子树
- 关键机制：`share_cache` 的共享去重、子查询的 Cross Join vs Left Deep 策略选择、DISTINCT 的聚合重写

Planner 生成的计划树是**逻辑层**的——它还不知道数据如何分布、算子如何并行。这些物理层的决策，将由下一章的 Optimizer 来完成。

---

*本章完成。下一章：[第 6 章 · Optimizer——查询优化器](../chapters/06-Optimizer-查询优化器.md)*
