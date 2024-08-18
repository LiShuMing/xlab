# 第10章：核心优化规则深入

> 33 步优化流水线中，有几条规则对查询性能的影响是决定性的。本章深入四条核心规则——谓词下推、列裁剪、公共子表达式消除和 Join 消除——揭示它们的实现策略和适用边界。

## 10.1 谓词下推（Filter Pushdown）

谓词下推是 OLAP 查询优化中最重要的一条规则——它将过滤条件尽可能推到靠近数据源的位置，减少上游算子需要处理的数据量。

### 两阶段策略：Pullup → Pushdown

DuckDB 的谓词下推分两步执行：

```
原始计划：
  Projection [a, b]
    Filter [a > 10 AND c < 5]
      Join [t1, t2 ON t1.id = t2.id]

Step 1: FilterPullup — 将嵌入在 Join/Projection 中的过滤条件"拉"出来
  Filter [a > 10 AND c < 5]
    Projection [a, b]
      Join [t1, t2 ON t1.id = t2.id]

Step 2: FilterPushdown — 将过滤条件"推"到最合适的位置
  Projection [a, b]
    Join [t1.id = t2.id]
      Filter [a > 10]          ← 推到了 t1 的 Scan 之上
        Get(t1)
      Filter [c < 5]            ← 推到了 t2 的 Scan 之上
        Get(t2, filters=[c<5])   ← 进一步推入 LogicalGet 的 table_filters
```

### FilterPushdown 的核心实现

```cpp
// src/optimizer/filter_pushdown.cpp
// FilterPushdown 递归遍历逻辑计划树，根据算子类型决定过滤条件可以推多远

// 过滤条件通过 FilterInfo 结构体传递：
struct FilterInfo {
    unique_ptr<Expression> filter;        // 过滤表达式
    unordered_set<TableIndex> bindings;   // 该表达式引用的表
};
```

**下推规则的核心逻辑**——每种算子有不同的下推策略：

| 算子 | 下推策略 |
|------|----------|
| `LogicalGet` | **全部接受**——过滤条件直接嵌入 `table_filters`，执行引擎利用 Zone Map 跳过 RowGroup |
| `LogicalJoin` | **按表分拆**——引用左表的谓词推到左子树，引用右表的推到右子树，同时引用两表的留在 Join 条件中 |
| `LogicalProjection` | **替换列引用**——如果过滤条件引用投影列，替换为投影表达式后再下推 |
| `LogicalAggregate` | **拒绝下推**——聚合后的过滤（HAVING）不能下推到聚合之前 |
| `LogicalWindow` | **拒绝下推**——窗口函数的结果在窗口计算后才存在 |
| `LogicalOrder` | **直接穿过**——排序不影响过滤条件，直接下推 |
| `LogicalLimit` | **拒绝下推**——LIMIT 后的过滤语义不同于 LIMIT 前的过滤 |

### 推入 LogicalGet 的深层优化

当过滤条件到达 `LogicalGet` 时，它不只是"挂在 Get 上方"——它被转换为 `TableFilterSet`，嵌入 `LogicalGet` 的 `table_filters` 字段：

```cpp
// 过滤条件推入 Scan 后的效果
LogicalGet:
  table_filters:
    amount > 100   → ColumnFilter(GREATER_THAN, 100)
    region = 'US'  → ColumnFilter(EQUAL, 'US')
```

执行引擎在读取数据时，先检查每个 RowGroup 的 Zone Map（min/max 统计信息）：
- 如果 RowGroup 的 `amount` 列 max = 50，而过滤条件是 `amount > 100`，整个 RowGroup 被跳过
- 这不是"在内存中过滤"——这是"在磁盘读取之前就决定不读"

### Mark Join → Semi Join 的转换

```cpp
// src/optimizer/filter_pushdown.cpp:163-165
filter_pushdown.CheckMarkToSemi(*plan, top_bindings);
```

`EXISTS` 子查询最初被绑定为 MARK Join（为每行生成一个 boolean 标记列）。FilterPushdown 发现下游有一个 `mark_column = true` 的过滤条件后，将 MARK Join 转换为更高效的 SEMI Join——SEMI Join 不需要产生标记列，只需判断是否存在匹配。

## 10.2 列裁剪（Remove Unused Columns）

列裁剪确保只读取和传递真正需要的列——这在列式存储中尤其重要，因为每多读一列就多一次 I/O。

```cpp
// src/optimizer/remove_unused_columns.cpp
class RemoveUnusedColumns : public LogicalOperatorVisitor {
    void VisitOperator(LogicalOperator &op) override;
};
```

### 自顶向下的列需求传播

列裁剪的工作方式是**自顶向下**传播"需要哪些列"的信息：

```
原始计划（需要哪些列？从最顶层开始分析）：
  Projection [region, SUM(amount)]        ← 需要 region, SUM(amount)
    Aggregate [groups=region, aggs=SUM(amount)]  ← 需要 region, amount
      Get(orders, columns=[*])              ← 原始：读取所有列

裁剪后：
  Projection [region, SUM(amount)]
    Aggregate [groups=region, aggs=SUM(amount)]
      Get(orders, columns=[region, amount])  ← 只读 2 列而非全部
```

### 特殊场景：Join 的列需求

Join 的列需求需要同时考虑左表和右表：

```sql
SELECT o.id FROM orders o JOIN customers c ON o.cid = c.id;
```

分析过程：
1. `Projection` 只需要 `o.id` → 列需求 = {o.id}
2. `Join` 的条件 `o.cid = c.id` 引用了 `o.cid` 和 `c.id` → 列需求 += {o.cid, c.id}
3. 左表需求 = {o.id, o.cid}，右表需求 = {c.id}
4. 右表只需要 `c.id` 一列——如果 customers 表有 50 列，我们省掉了 49 列的读取

### ColumnLifetimeAnalyzer：投影映射的生成

```cpp
// src/optimizer/column_lifetime_analyzer.cpp
// 在列裁剪之后，ColumnLifetimeAnalyzer 为每个算子生成 projection_map
// projection_map 告诉算子：只需要输出哪些列，其他列可以尽早丢弃
```

`ColumnLifetimeAnalyzer` 与 `RemoveUnusedColumns` 的区别：后者决定"读哪些列"，前者决定"在哪里丢弃已经不需要的列"。例如：

```
Join 输出 10 列，但下游只需要 3 列
→ ColumnLifetimeAnalyzer 在 Join 上方插入一个 Projection
  或修改 Join 的 left/right_projection_map
  使得 Join 只输出 3 列而非 10 列
```

## 10.3 公共子表达式消除（CSE）

```cpp
// src/optimizer/cse_optimizer.cpp
class CommonSubExpressionOptimizer : public LogicalOperatorVisitor {
    // 在每个算子内部查找重复的表达式子树
    // 用一个引用替换重复出现的表达式
};
```

CSE 在单个算子的 `expressions` 列表中查找结构相同的子表达式：

```sql
SELECT EXTRACT(YEAR FROM ts), EXTRACT(MONTH FROM ts), EXTRACT(YEAR FROM ts) + 1
FROM events;
```

`EXTRACT(YEAR FROM ts)` 出现了两次——CSE 将第二次出现替换为对第一次的引用，避免重复计算。

### CSE 的局限

DuckDB 的 CSE 是**算子内**的——它只消除同一算子内部的重复表达式，不跨算子消除。跨算子的公共子计划由 `CommonSubplanOptimizer` 处理（它将公共子计划转化为物化 CTE）。这个设计选择的原因是：跨算子 CSE 的实现复杂度远高于算子内 CSE，且收益通常不如列裁剪和谓词下推明显。

## 10.4 CTE 内联与过滤推动

### CTEInlining

```cpp
// src/optimizer/cte_inlining.cpp
// 判断 CTE 是否值得物化，如果引用次数为 1 → 内联展开
```

DuckDB 的 CTE 默认策略是**物化**（MATERIALIZED）——CTE 的结果被计算一次并缓存。但如果 CTE 只被引用一次，物化就没有意义——它增加了额外的内存开销，但不节省计算。

`CTEInlining` 检查每个 CTE 的引用次数。如果引用次数 ≤ 1，将 CTE 的定义直接内联到引用点——相当于 CTE 从未存在过。

```sql
-- 引用 1 次：内联
WITH large_cte AS (SELECT * FROM million_row_table) 
SELECT * FROM large_cte;
-- 等价于：SELECT * FROM million_row_table;

-- 引用 2 次：物化
WITH large_cte AS (SELECT * FROM million_row_table)
SELECT * FROM large_cte WHERE a > 10
UNION ALL
SELECT * FROM large_cte WHERE b < 5;
-- CTE 只计算一次，两个分支共享结果
```

### CTEFilterPusher

```cpp
// src/optimizer/cte_filter_pusher.cpp
// 将下游的过滤条件推入 CTE 的物化结果中
```

物化 CTE 的一个问题是：CTE 可能在物化时计算了比下游需要更多的行。`CTEFilterPusher` 分析下游对 CTE 的过滤条件，如果所有引用点都有相同的过滤条件，就将该条件推入 CTE 的定义中——减少物化的数据量。

## 10.5 Join 消除与 Outer Join 简化

### JoinElimination

```sql
-- orders JOIN customers ON o.cid = c.id
-- 如果查询不引用 customers 的任何列 → Join 可以被消除
SELECT o.id, o.amount FROM orders o JOIN customers c ON o.cid = c.id;
-- 等价于：SELECT o.id, o.amount FROM orders o WHERE o.cid IS NOT NULL;
```

`JoinElimination` 识别"不需要右表数据"的 Join 场景。对于 INNER Join，如果下游不引用右表的任何列，Join 可以被直接消除（INNER Join 只起到存在性检查的作用，等价于 `IS NOT NULL` 过滤）。

对于 LEFT Join，消除条件更严格：不仅不引用右表列，还需要确保右表的 Join 列有 UNIQUE 约束（否则 LEFT Join 可能产生重复行，消除后行数会变少）。

### OuterJoinSimplification

```cpp
// src/optimizer/outer_join_simplification.cpp
// FULL OUTER JOIN → LEFT JOIN → INNER JOIN 的逐步简化
```

如果 OUTER JOIN 的右表列在下游被 `IS NOT NULL` 过滤，那么右表为 NULL 的行会被过滤掉——这与 INNER JOIN 的语义等价。`OuterJoinSimplification` 检测这种模式并简化 Join 类型：

```
FULL OUTER JOIN + WHERE right_col IS NOT NULL → LEFT JOIN
LEFT JOIN + WHERE right_col IS NOT NULL → INNER JOIN
```

INNER Join 比 OUTER Join 有更大的优化空间——优化器可以自由选择 Join 的哪一侧作为构建端和探测端，而 OUTER Join 的构建端/探测端是受限的。

## 10.6 TopN 优化：ORDER BY + LIMIT 的合并

```sql
SELECT * FROM orders ORDER BY amount DESC LIMIT 10;
```

传统执行方式：先对所有数据排序，再取前 10 行。如果 orders 有 1 亿行，排序的代价是 O(n log n)。

```cpp
// src/optimizer/topn_optimizer.cpp
// 检测 ORDER BY + LIMIT 模式，将 LogicalOrder + LogicalLimit 合并为 LogicalTopN
```

`TopN` 算子使用**最小堆**（min-heap for DESC / max-heap for ASC）维护前 N 行，避免全量排序。时间复杂度从 O(n log n) 降为 O(n log k)，其中 k 是 LIMIT 值（通常是 10-100），这是一个数量级的提升。

## 10.7 Late Materialization：延迟物化

```cpp
// src/optimizer/late_materialization.cpp
// 对于 SELECT * FROM t WHERE expensive_filter(x)
// 先读取 x 列做过滤，得到满足条件的行号
// 再根据行号读取其他列 → 避免读取不满足条件的行的全部列
```

延迟物化是列式存储的经典优化：先在少量列上做过滤，得到满足条件的行号集合，然后用行号去读其他列。如果过滤的选择性很高（如 99% 的行被过滤掉），这可以省掉 99% 的其他列 I/O。

DuckDB 的 `LateMaterialization` 优化器在逻辑计划层面识别这种模式——当 Filter 的条件只引用少量列，而下游需要大量列时，它会重新排列读取顺序：先读过滤列 → 过滤 → 再读其他列。

---

## 本章小结

四条核心优化规则的实现策略：

1. **谓词下推**：两阶段（Pullup → Pushdown），推入 LogicalGet 的 `table_filters` 后可触发 Zone Map 裁剪
2. **列裁剪**：自顶向下传播列需求，在 LogicalGet 的 `projection_ids` 中只保留必要的列
3. **CSE**：算子内消除重复表达式，跨算子由 CommonSubplanOptimizer 处理
4. **Join 消除**：识别不引用右表列的 INNER Join 和满足 UNIQUE 约束的 LEFT Join

以及两条重要的模式优化：
5. **TopN**：ORDER BY + LIMIT 合并为最小堆维护
6. **Late Materialization**：先过滤后读取，减少 I/O

下一章，我们深入 Join Order 优化——DuckDB 如何在多表 Join 的组合爆炸中找到一条近优路径。
