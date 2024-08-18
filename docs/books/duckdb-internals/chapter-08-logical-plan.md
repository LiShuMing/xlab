# 第8章：Logical Plan —— 关系代数的逻辑表达

> LogicalOperator 树是 DuckDB 查询处理的"数学灵魂"。它不关心数据怎么读、怎么算——只关心"做什么"。理解逻辑计划，就是理解 DuckDB 如何将 SQL 的语义翻译为关系代数操作。

## 8.1 LogicalOperator 体系：50+ 种逻辑算子

### 基类设计

```cpp
// src/include/duckdb/planner/logical_operator.hpp:28-113
class LogicalOperator {
public:
    LogicalOperatorType type;                             // 算子类型枚举
    vector<unique_ptr<LogicalOperator>> children;        // 子算子（通常 0-2 个）
    vector<unique_ptr<Expression>> expressions;           // 算子关联的表达式
    vector<LogicalType> types;                            // 输出列类型
    idx_t estimated_cardinality;                          // 估算基数
    bool has_estimated_cardinality;                       // 是否有估算

    virtual vector<ColumnBinding> GetColumnBindings();    // 输出列绑定
    virtual bool RequireOptimizer() const { return true; } // 是否需要优化

protected:
    virtual void ResolveTypes() = 0;                      // 纯虚：解析输出类型
};
```

`LogicalOperator` 是一个极简的基类——只有四个核心字段。但它通过 `type` 枚举和虚方法实现了 50+ 种算子的差异化行为。

### 算子类型分类

DuckDB 的逻辑算子可以按功能分为六个家族：

**扫描家族**——数据来源：

| 算子 | 职责 |
|------|------|
| `LogicalGet` | 从表/表函数读取数据 |
| `LogicalDummyScan` | 不读数据（`SELECT 1+2` 无 FROM） |
| `LogicalCTERef` | 引用 CTE 的结果 |
| `LogicalColumnDataGet` | 读取内存中的 ColumnData |
| `LogicalExpressionGet` | 读取表达式列表（VALUES 子句） |
| `LogicalDelimGet` | 读取去重后的子查询结果 |
| `LogicalEmptyResult` | 编译期已知空结果 |

**过滤/变换家族**——逐行操作：

| 算子 | 职责 |
|------|------|
| `LogicalFilter` | WHERE/HAVING 过滤 |
| `LogicalProjection` | 列选择与表达式计算 |
| `LogicalUnnest` | UNNEST 展开嵌套类型 |

**聚合/窗口家族**——分组与窗口：

| 算子 | 职责 |
|------|------|
| `LogicalAggregate` | 分组聚合 |
| `LogicalWindow` | 窗口函数 |
| `LogicalDistinct` | DISTINCT 去重 |

**Join 家族**——两表关联：

| 算子 | 职责 |
|------|------|
| `LogicalJoin` | 基类（INNER/LEFT/RIGHT/FULL/SEMI/ANTI/MARK） |
| `LogicalComparisonJoin` | 等值/非等值比较 Join |
| `LogicalAnyJoin` | `a JOIN b ON condition`（任意条件） |
| `LogicalCrossProduct` | 笛卡尔积 |
| `LogicalDependentJoin` | 相关子查询转化的依赖 Join |
| `LogicalPositionalJoin` | 位置 Join（按行号对齐） |
| `LogicalUnconditionalJoin` | 无条件 Join |

**排序/限制家族**——结果整形：

| 算子 | 职责 |
|------|------|
| `LogicalOrder` | ORDER BY |
| `LogicalLimit` | LIMIT/OFFSET |
| `LogicalTopN` | ORDER BY + LIMIT 的优化组合 |
| `LogicalSample` | TABLESAMPLE |

**写入/DDL 家族**——数据修改：

| 算子 | 职责 |
|------|------|
| `LogicalInsert` | INSERT |
| `LogicalDelete` | DELETE |
| `LogicalUpdate` | UPDATE |
| `LogicalCreate` | CREATE TABLE/INDEX/VIEW |
| `LogicalCreateTable` | CREATE TABLE（含数据填充） |
| `LogicalCopyToFile` | COPY TO |
| `LogicalMergeInto` | MERGE INTO |

### 为什么需要这么多算子？

答案不是"为了优雅"，而是"为了优化"。每种算子携带不同的语义信息——`LogicalComparisonJoin` 告诉优化器"这是等值条件，可以考虑 HashJoin"；`LogicalAnyJoin` 告诉优化器"条件可能很复杂，需要 NestedLoop"。如果合并为一个 `LogicalJoin`，优化器就需要从表达式中重新推导这些信息——复杂度更高，正确性更难保证。

## 8.2 从 BoundStatement 到 LogicalOperator 树

Planner 将 `BoundStatement` 转化为 `LogicalOperator` 树的过程是一个递归构建：

```
BoundSelectStatement
  ├── select_list → LogicalProjection
  ├── from_table  → LogicalGet / LogicalJoin / ...
  ├── where_clause → LogicalFilter
  ├── group_by    → LogicalAggregate
  ├── having      → LogicalFilter (附加在 Aggregate 之上)
  ├── window      → LogicalWindow
  ├── order_by    → LogicalOrder
  ├── limit       → LogicalLimit
  └── distinct    → LogicalDistinct
```

### 构建顺序：自底向上

DuckDB 的 Planner 按 SQL 的逻辑顺序自底向上构建算子树：

```cpp
// 伪代码：Planner 的核心逻辑
CreatePlan(BoundSelectNode &node) {
    // 1. 绑定 FROM 子句 → 生成数据源算子
    auto plan = BindTableRef(node.from_table);

    // 2. WHERE 过滤
    if (node.where_clause) {
        plan = LogicalFilter(node.where_clause, std::move(plan));
    }

    // 3. GROUP BY + 聚合
    if (node.groups || node.aggregates) {
        plan = LogicalAggregate(node.groups, node.aggregates, std::move(plan));
    }

    // 4. HAVING 过滤（在聚合之后）
    if (node.having) {
        plan = LogicalFilter(node.having, std::move(plan));
    }

    // 5. Window 函数
    if (node.windows) {
        plan = LogicalWindow(node.windows, std::move(plan));
    }

    // 6. SELECT 列表 → Projection
    plan = LogicalProjection(node.select_list, std::move(plan));

    // 7. ORDER BY
    if (node.order_by) {
        plan = LogicalOrder(node.order_by, std::move(plan));
    }

    // 8. LIMIT/OFFSET
    if (node.limit) {
        plan = LogicalLimit(node.limit, node.offset, std::move(plan));
    }

    // 9. DISTINCT
    if (node.distinct) {
        plan = LogicalDistinct(std::move(plan));
    }

    return plan;
}
```

这个顺序很重要——它决定了树中算子的位置。例如 `LogicalFilter`（WHERE）在 `LogicalAggregate` 之下，意味着过滤在聚合之前执行——这在语义上等同于"WHERE 先于 GROUP BY"。而 HAVING 的 `LogicalFilter` 在 `LogicalAggregate` 之上，意味着它在聚合之后执行。

## 8.3 关键算子的逻辑语义深入

### LogicalGet：统一的数据源抽象

```cpp
// src/include/duckdb/planner/operator/logical_get.hpp:20-110
class LogicalGet : public LogicalOperator {
    TableIndex table_index;                // BindContext 中的表索引
    TableFunction function;                // 表函数（read_csv / 内置 scan / 扩展函数）
    unique_ptr<FunctionData> bind_data;    // 函数的绑定数据（文件路径、选项等）
    vector<LogicalType> returned_types;    // 所有可返回列的类型
    vector<string> names;                  // 所有可返回列的名称
    vector<ProjectionIndex> projection_ids; // 实际需要的列（列裁剪后）
    TableFilterSet table_filters;          // 下推的过滤条件
    shared_ptr<DynamicTableFilterSet> dynamic_filters; // 运行时动态过滤
};
```

`LogicalGet` 是 DuckDB 中唯一的数据源算子——无论是从本地表、Parquet 文件、CSV 文件还是自定义表函数，都统一为 `LogicalGet`。这种统一的关键是 `TableFunction`：

```cpp
// 内置表扫描：扫描本地表
TableFunction scan_function("seq_scan", ...);

// Parquet 扩展：扫描 Parquet 文件
TableFunction parquet_scan("parquet_scan", ...);

// CSV 扩展：扫描 CSV 文件
TableFunction csv_scan("csv_scan", ...);

// 用户自定义表函数
TableFunction my_scan("my_custom_source", ...);
```

所有这些扫描方式在逻辑计划层面完全相同——一个 `LogicalGet`。区别只在 `function` 和 `bind_data` 中。这是一个深刻的架构决策：**逻辑计划不关心数据的来源，只关心数据的结构**。

**列裁剪的信息就存在 projection_ids 中**。优化器的 `RemoveUnusedColumns` 规则修改 `projection_ids`——只保留下游算子实际需要的列。执行引擎根据 `projection_ids` 只读取需要的列，跳过其他列的 I/O。

**table_filters 是谓词下推的结果**。当优化器将 `amount > 100` 推到 `LogicalGet` 时，它不只是把表达式移到 `LogicalGet` 的上方——它将过滤条件转换为 `TableFilterSet`，嵌入 `LogicalGet` 中。执行引擎在读取数据时就可以利用 Zone Map（min/max 统计）跳过整个 RowGroup。

**dynamic_filters 是 Join 过滤下推的结果**。当 HashJoin 的构建端完成后，构建端产生的等值条件可以被推回到探测端的 `LogicalGet` 中——例如 `orders JOIN customers ON customer_id = id`，构建端读完 customers 后，可以将所有 `id` 值推到 orders 的扫描中，进一步减少读取量。

### LogicalFilter：表达式的合取拆分

```cpp
// src/include/duckdb/planner/operator/logical_filter.hpp:16-47
class LogicalFilter : public LogicalOperator {
    vector<ProjectionIndex> projection_map;  // 列映射

    bool SplitPredicates();  // 拆分 AND 连接的谓词
    static bool SplitPredicates(vector<unique_ptr<Expression>> &expressions);
};
```

`LogicalFilter` 的 `expressions` 字段存储过滤条件——但不是整个 WHERE 子句作为一个表达式，而是**拆分为 AND 连接的原子谓词**：

```
输入：WHERE a > 10 AND b < 20 AND c = 'hello'
LogicalFilter.expressions = [
    a > 10,          // 原子谓词 1
    b < 20,          // 原子谓词 2
    c = 'hello'      // 原子谓词 3
]
```

`SplitPredicates` 方法递归拆分 `ConjunctionExpression(AND, ...)`：

```cpp
// 伪代码
SplitPredicates(expressions) {
    for (expr in expressions) {
        if (expr is ConjunctionExpression(AND)) {
            // 拆分！将 AND 的左右子表达式独立加入列表
            expressions.push_back(expr.left);
            expressions.push_back(expr.right);
            expressions.remove(expr);
            return true;  // 发生了拆分
        }
    }
    return false;  // 没有可拆分的
}
```

拆分的好处是**谓词可以独立下推**——`a > 10` 可以推到 `LogicalGet` 中，`b < 20` 可以推到另一个 Join 条件中，而 `c = 'hello'` 留在 Filter 中。如果它们作为一个整体 `AND` 表达式存在，就无法独立移动。

### LogicalJoin：双投影映射

```cpp
// src/include/duckdb/planner/operator/logical_join.hpp:18-52
class LogicalJoin : public LogicalOperator {
    JoinType join_type;                          // INNER/LEFT/RIGHT/FULL/SEMI/ANTI/MARK
    TableIndex mark_index;                       // MARK Join 的标记列索引
    vector<ProjectionIndex> left_projection_map;  // 左表输出列映射
    vector<ProjectionIndex> right_projection_map; // 右表输出列映射
};
```

`LogicalJoin` 有两个子算子（`children[0]` = 左表，`children[1]` = 右表），但**不总是输出所有列**。`left_projection_map` 和 `right_projection_map` 控制输出哪些列——这是列裁剪在 Join 中的体现。

例如 `SELECT o.id FROM orders o JOIN customers c ON o.cid = c.id`，只需要左表的 `id` 列，不需要右表的任何列。此时 `right_projection_map` 为空（或只包含 Join 条件需要的列），`left_projection_map = [0]`。

Join 的输出 `ColumnBinding` 按"左表所有输出列 + 右表所有输出列"的顺序排列。下游算子通过 `ColumnBinding(table_index, column_index)` 定位到具体的列。

### LogicalAggregate：分组+聚合的统一表示

```cpp
// src/include/duckdb/planner/operator/logical_aggregate.hpp
class LogicalAggregate : public LogicalOperator {
    vector<unique_ptr<Expression>> groups;        // GROUP BY 表达式
    vector<unique_ptr<Expression>> expressions;   // 聚合函数表达式
    TableIndex group_index;                       // 分组表的索引
    TableIndex aggregate_index;                   // 聚合表的索引
};
```

`LogicalAggregate` 将 GROUP BY 和聚合函数合并在一个算子中。`groups` 存储分组键表达式，`expressions` 存储聚合函数（如 `SUM(amount)`, `COUNT(*)`）。

输出列的顺序是：`[groups..., aggregates...]`。例如 `SELECT region, SUM(amount), COUNT(*) FROM orders GROUP BY region`：

```
groups = [BoundColumnRef(region)]
expressions = [BoundAggregateExpression(sum, amount), BoundAggregateExpression(count_star)]
输出类型 = [VARCHAR, DOUBLE, BIGINT]
```

**无 GROUP BY 的聚合**（`SELECT COUNT(*) FROM t`）——`groups` 为空，整个表是一个分组。这种情况下 `LogicalAggregate` 是一个 Sink 算子（Pipeline Breaker），必须消费所有输入后才能输出一行结果。

## 8.4 Column Binding 与表达式树

### ColumnBinding：全局唯一的列标识

```cpp
// src/include/duckdb/planner/column_binding.hpp
struct ColumnBinding {
    idx_t table_index;    // 哪个算子的输出
    idx_t column_index;   // 该算子的哪一列

    bool operator==(const ColumnBinding &other) const {
        return table_index == other.table_index && column_index == other.column_index;
    }
};
```

`ColumnBinding` 是逻辑计划中"列"的唯一标识——它由 `table_index`（算子的标识）和 `column_index`（该算子输出的第几列）组成。每个 `LogicalOperator` 的 `GetColumnBindings()` 方法返回其输出列的 `ColumnBinding` 列表。

例如一棵简单的计划树：

```
LogicalProjection [table_index=2]
  ├── 输出列: [(2,0), (2,1)]  ← 投影后的列
  └── LogicalFilter [table_index=1]
        ├── 输出列: [(1,0), (1,1), (1,2)]  ← 过滤后保留的列
        └── LogicalGet [table_index=0]
              ├── 输出列: [(0,0), (0,1), (0,2)]  ← 表的原始列
```

`BoundColumnRefExpression` 的 `binding` 字段指向具体的 `ColumnBinding`——例如 `BoundColumnRefExpression("amount", binding=(0, 2))` 表示"table_index=0 的算子的第 3 列"。

### 表达式树：LogicalOperator 的"血肉"

`LogicalOperator.expressions` 中的每个元素是一棵 `Expression` 子类树。DuckDB 定义了约 30 种 `Expression` 类型：

```
Expression (基类)
├── BoundColumnRefExpression     ← 列引用 (binding + depth)
├── BoundConstantExpression      ← 常量 (Value)
├── BoundFunctionExpression      ← 函数调用 (函数 + 参数)
├── BoundAggregateExpression     ← 聚合函数
├── BoundWindowExpression        ← 窗口函数
├── BoundComparisonExpression    ← 比较 (=, <, >, ...)
├── BoundConjunctionExpression   ← 逻辑 (AND, OR)
├── BoundCastExpression          ← 类型转换
├── BoundCaseExpression          ← CASE WHEN
├── BoundOperatorExpression      ← 算术 (+, -, *, /)
├── BoundSubqueryExpression      ← 子查询
├── BoundParameterExpression     ← 预备参数 ($1)
└── ... 更多
```

这些表达式在逻辑计划中被"嵌入"算子中——`LogicalFilter` 的 `expressions` 包含 `BoundComparisonExpression`，`LogicalProjection` 的 `expressions` 包含各种计算表达式，`LogicalAggregate` 的 `expressions` 包含 `BoundAggregateExpression`。

### ResolveTypes：类型推导的传递

```cpp
// src/include/duckdb/planner/logical_operator.hpp:58,94-95
void ResolveOperatorTypes();
virtual void ResolveTypes() = 0;  // 每个算子必须实现
```

每个算子的 `ResolveTypes()` 方法根据子算子的类型和自己的表达式推导输出类型：

```cpp
// LogicalFilter：类型不变（过滤不改变列类型）
void LogicalFilter::ResolveTypes() {
    types = children[0]->types;  // 继承子算子的类型
}

// LogicalProjection：类型由表达式决定
void LogicalProjection::ResolveTypes() {
    for (auto &expr : expressions) {
        types.push_back(expr->return_type);  // 每个表达式的返回类型
    }
}

// LogicalAggregate：groups + aggregates 的类型
void LogicalAggregate::ResolveTypes() {
    for (auto &group : groups) {
        types.push_back(group->return_type);
    }
    for (auto &aggregate : expressions) {
        types.push_back(aggregate->return_type);
    }
}
```

### RequireOptimizer：跳过优化的算子

```cpp
// src/include/duckdb/planner/logical_operator.hpp:77-79
virtual bool RequireOptimizer() const {
    return true;  // 默认需要优化
}
```

少数算子覆盖此方法返回 `false`——告诉 Optimizer "我不需要优化"。例如 `LogicalSimple`（PRAGMA、SET 等简单命令）和 `LogicalExplain`。这是一种工程优化——不是所有逻辑计划都需要经过 33 条优化规则的遍历。

## 8.5 逻辑计划的可视化

DuckDB 提供了 `EXPLAIN` 和 `EXPLAIN ANALYZE` 来查看逻辑/物理计划：

```sql
EXPLAIN SELECT region, SUM(amount) FROM orders WHERE amount > 100 GROUP BY region;
```

输出类似：

```
┌───────────────────────────┐
│         PROJECTION         │
│   region, SUM(amount)      │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│       AGGREGATE            │
│   groups: [region]         │
│   aggs: [SUM(amount)]      │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│         FILTER             │
│   amount > 100             │
└─────────────┬─────────────┘
┌─────────────┴─────────────┐
│         SEQ_SCAN           │
│   orders                   │
│   projection: region,amount│
│   filters: amount>100      │
└───────────────────────────┘
```

注意：`EXPLAIN` 显示的是**优化后**的计划——`amount > 100` 已经从 `FILTER` 下推到了 `SEQ_SCAN` 的 `filters` 属性中。要看优化前的逻辑计划，可以设置 `set explain_output=optimized_only` 或 `set explain_output=physical_only`。

---

## 本章小结

LogicalOperator 树是 DuckDB 查询的"关系代数表示"。核心要点：

1. **50+ 种算子**：每种算子携带不同的语义信息，为优化器提供差异化处理的基础
2. **LogicalGet 的统一抽象**：所有数据源（表、文件、函数）统一为 `TableFunction` + `bind_data`
3. **自底向上构建**：Planner 按 FROM → WHERE → GROUP BY → HAVING → Window → SELECT → ORDER → LIMIT 的顺序构建算子树
4. **ColumnBinding**：`table_index + column_index` 唯一标识逻辑计划中的每一列
5. **表达式嵌入算子**：`expressions` 字段存储算子关联的表达式树，类型由 `ResolveTypes()` 传递推导

下一章，我们将进入优化器——它如何在这棵逻辑计划树上做 33 条规则的重写，让查询执行得更高效。
