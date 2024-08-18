# 第7章：Binder —— 语义分析与名字解析

> Parser 只知道语法——"orders 这个词出现在 FROM 子句中"。Binder 知道语义——"orders 是一张表，有 5 列，amount 列的类型是 DECIMAL(18,2)"。这一跳，从"符号"到"实体"，是 SQL 编译中最复杂的环节之一。

## 7.1 Binder 的核心职责

Binder 的输入是 Parser 产生的 AST，输出是 `BoundStatement`——一棵所有名字引用都被解析、所有类型都被推导的语义树。

```cpp
// src/include/duckdb/planner/binder.hpp:198,222-223
class Binder : public enable_shared_from_this<Binder> {
public:
    static shared_ptr<Binder> CreateBinder(ClientContext &context,
                                            optional_ptr<Binder> parent = nullptr,
                                            BinderType binder_type = BinderType::REGULAR_BINDER);
    BoundStatement Bind(SQLStatement &statement);  // 主入口
    BoundStatement Bind(QueryNode &node);
    BoundStatement Bind(TableRef &ref);             // 表引用绑定

    ClientContext &context;
    BindContext bind_context;                        // 名字解析上下文
    CorrelatedColumns correlated_columns;            // 相关子查询的列信息
    CatalogEntryRetriever entry_retriever;           // Catalog 查找器
    shared_ptr<Binder> parent;                       // 父级 Binder（嵌套查询时）
    shared_ptr<GlobalBinderState> global_binder_state;  // 跨查询全局状态
    shared_ptr<QueryBinderState> query_binder_state;    // 查询内共享状态
};
```

Binder 做四件事：

1. **名字解析**：`orders` → `TableCatalogEntry`，`amount` → `ColumnBinding(table_idx=0, column_idx=2)`
2. **类型推导**：`42 + 0.5` → 表达式类型为 `DECIMAL(?,?)` → 推导为 `DOUBLE`
3. **函数重载解析**：`sum(x)` → 有多个 `sum` 重载（`INT→BIGINT`, `DOUBLE→DOUBLE` 等），根据 `x` 的类型选一个
4. **合法性检查**：GROUP BY 的列、HAVING 的条件、窗口函数的位置——这些规则检查都在 Binder 中

### Binder 的层次结构

Binder 是可嵌套的——子查询、视图、CTE 各自创建子级 Binder。`parent` 指针形成了一条链：

```
最外层 Binder (SELECT ...)
  └── 子查询 Binder (WHERE EXISTS (SELECT ...))
        └── 更深层子查询 Binder
```

`GlobalBinderState` 在整条链上共享——它记录全局信息（已绑定表数、参数映射）。`QueryBinderState` 在同一查询内共享——新视图会创建新的 QueryBinderState。这种分层让 `CTE` 和视图中的名字解析不污染外层。

## 7.2 TableRef 绑定：从名字到 Catalog Entry

绑定一个表引用（`BaseTableRef`）是 Binder 中最复杂的操作之一——因为它需要处理 CTE、视图、替代扫描等多种情况。

### 绑定 BaseTableRef 的完整流程

```cpp
// src/planner/binder/tableref/bind_basetableref.cpp:119-219
BoundStatement Binder::Bind(BaseTableRef &ref) {
    // Step 1: 检查是否为 CTE
    auto ctebinding = GetCTEBinding(binding_alias);
    if (ctebinding && ctebinding->CanBeReferenced()) {
        // → 返回 LogicalCTERef
    }

    // Step 2: 在 Catalog 中查找表/视图
    auto table_or_view = entry_retriever.GetEntry(
        ref.catalog_name, ref.schema_name, table_lookup, OnEntryNotFound::RETURN_NULL);

    // Step 3: 找不到 → 尝试 Replacement Scan
    if (!table_or_view) {
        auto replacement_scan_bind_result = BindWithReplacementScan(context, ref);
        if (replacement_scan_bind_result.plan) {
            return replacement_scan_bind_result;
        }
        // Step 3.5: 尝试自动加载扩展后重试
        auto extension_loaded = TryLoadExtensionForReplacementScan(context, full_path);
        if (extension_loaded) {
            replacement_scan_bind_result = BindWithReplacementScan(context, ref);
            // ...
        }
    }

    // Step 4: 找到表 → 绑定为 LogicalGet
    // Step 5: 找到视图 → 递归绑定视图的 SELECT 定义
}
```

### 替代扫描机制

```cpp
// src/planner/binder/tableref/bind_basetableref.cpp:47-87
BoundStatement Binder::BindWithReplacementScan(ClientContext &context, BaseTableRef &ref) {
    auto &config = DBConfig::GetConfig(context);
    for (auto &scan : config.replacement_scans) {
        ReplacementScanInput input(ref.catalog_name, ref.schema_name, ref.table_name);
        auto replacement_function = scan.function(context, input, scan.data.get());
        if (!replacement_function) continue;
        // 转换为表函数引用或子查询引用
        return Bind(*replacement_function);
    }
    return BoundStatement();
}
```

当用户写 `SELECT * FROM 'data.csv'`，Parser 会将 `'data.csv'` 解析为一个 `BaseTableRef`（不是表函数调用）。Binder 在 Catalog 中找不到叫 `data.csv` 的表，于是尝试替代扫描。

替代扫描是一组注册在 `DBConfig` 中的回调函数。DuckDB 内置的替代扫描规则之一是：如果表名看起来像文件路径（包含 `.` 和扩展名），就自动转换为 `read_csv_auto('data.csv')` 或 `read_parquet(...)`。这就是为什么你能直接写 `SELECT * FROM 'data.parquet'`。

如果替代扫描也失败了，DuckDB 还会尝试自动加载扩展（`TryLoadExtensionForReplacementScan`）。如果文件名以 `.parquet` 结尾但 Parquet 扩展尚未加载，DuckDB 会自动加载它然后重试。

### 绑定 JoinRef：两表绑定的协调

```cpp
// src/planner/binder/tableref/plan_joinref.cpp
// 绑定 Join 时，左右两侧各自绑定，然后在 BindContext 中注册 USING 列
```

Join 绑定的特殊之处在于 **USING 子句**的处理。`a JOIN b USING (id)` 中的 `id` 列同时存在于 `a` 和 `b` 中——`BindContext` 需要注册一个 `UsingColumnSet`，使得后续对 `id` 的引用可以同时解析到两表的同名列。

```cpp
// src/include/duckdb/planner/bind_context.hpp:33-36
struct UsingColumnSet {
    BindingAlias primary_binding;   // 主绑定（左表）
    vector<BindingAlias> bindings;  // 所有参与的绑定（左表 + 右表）
};
```

当后续表达式引用 `id` 时，`BindContext::BindColumn` 发现 `id` 属于一个 `UsingColumnSet`，返回主绑定（左表）的 `ColumnBinding`，但在 JOIN 的 ON 条件中，USING 列会自动展开为 `a.id = b.id`。

## 7.3 Expression Binder：列引用消歧与函数解析

表达式绑定是 Binder 中代码量最大的部分——`src/planner/binder/expression/` 下有 20+ 个文件，每个文件绑定一种表达式类型。

### 列引用绑定（最频繁的操作）

```cpp
// src/planner/binder/expression/bind_columnref_expression.cpp
// BindColumnRefExpression 的核心逻辑
```

当 Binder 遇到 `ColumnRefExpression("amount")` 时，需要回答：`amount` 来自哪张表的哪一列？这个过程由 `BindContext::BindColumn` 驱动：

1. **无歧义引用**：只有一张表有 `amount` 列 → 直接绑定到该表的列
2. **有歧义引用**：多张表有 `amount` 列 → 报错 `ambiguous reference to column name "amount"`
3. **限定引用**：`orders.amount` → 先找 `orders` 表，再找其 `amount` 列
4. **不存在**：没有表有 `amount` 列 → 搜索 Levenshtein 距离最近的列名给出建议

```cpp
// src/include/duckdb/planner/bind_context.hpp:49-56
optional_ptr<Binding> GetMatchingBinding(const string &column_name, QueryErrorContext context);
vector<reference<Binding>> GetMatchingBindings(const string &column_name);
vector<string> GetSimilarBindings(const string &column_name);  // 模糊匹配建议
```

绑定成功后，`ColumnRefExpression("amount")` 变成 `BoundColumnRefExpression`：

```cpp
class BoundColumnRefExpression : public Expression {
    ColumnBinding binding;    // {table_index, column_index} —— 唯一标识一列
    idx_t depth;              // 子查询深度（0=当前层，1=外层，2=更外层...）
};
```

`ColumnBinding` 是执行引擎中定位一列的核心数据结构：

```cpp
struct ColumnBinding {
    idx_t table_index;   // 哪个表/算子的输出
    idx_t column_index;  // 该表的哪一列
};
```

`depth` 字段是相关子查询的关键——当一个子查询引用外层查询的列时，`depth > 0`。Binder 通过 `depth` 标记"这个列引用来自第几层外"，后续的 Subquery Planner 会根据 depth 将相关列传递到子查询内部。

### 函数重载解析

```cpp
// src/planner/binder/expression/bind_function_expression.cpp
```

当 Binder 遇到 `FunctionExpression("sum", [ColumnRef("x")])`，需要从 Catalog 中查找名为 `sum` 的函数，然后选择最匹配的重载版本。

DuckDB 的函数重载解析步骤：

1. **查找候选函数**：在 Catalog 中按名字查找所有同名函数（可能有标量版、聚合版、窗口版）
2. **类型匹配**：检查每个候选函数的参数类型是否与实际参数类型兼容
3. **隐式类型转换**：如果参数不完全匹配，尝试隐式转换（如 `INT → BIGINT`），计算转换代价（cast score）
4. **选择最优匹配**：选择 cast score 最低的函数（需要最少类型转换的版本）
5. **歧义检查**：如果多个候选有相同的最优 score，报错 `ambiguous function call`

```cpp
// 类型转换的优先级（cast score 越低越好）
// 精确匹配（同类型）           → score = 0
// 近似匹配（INT32→INT64）     → score = 1
// 跨类转换（INT→DOUBLE）      → score = 2
// 字符串转换（VARCHAR→INT）   → score = 5（惩罚较高）
// ANY 参数                    → 由 ANY_PARAMS 的 cast_score 决定
```

### 隐式类型转换

```cpp
// src/include/duckdb/common/types.hpp:359-363
static LogicalType MaxLogicalType(ClientContext &context,
                                   const LogicalType &left,
                                   const LogicalType &right);
```

当函数参数需要 `DOUBLE` 但实际传入 `INT` 时，Binder 自动在表达式树中插入一个 `BoundCastExpression`：

```
函数调用前：  sum(x)    其中 x: INTEGER
函数调用后：  sum(CAST(x AS BIGINT))   — sum 的 INT 重载返回 BIGINT
```

Cast 不只是"换个类型标签"——它可能改变内存布局（`INT32 → INT64` 需要扩展 4 字节到 8 字节）。执行引擎在遇到 `BoundCastExpression` 时，会生成相应的向量化 Cast 操作（如 `VectorOperations::Cast`）。

### MACRO 的内联展开

```cpp
// src/planner/binder/expression/bind_macro_expression.cpp
```

当 Binder 遇到 `add(1, 2)`，如果 `add` 是一个 MACRO（`CREATE MACRO add(a, b) AS a + b`），Binder 不会在 Catalog 中查找函数。它会：

1. 将 MACRO 的定义表达式（`a + b`）深拷贝一份
2. 将参数（`a → 1`, `b → 2`）替换到拷贝中
3. 递归绑定替换后的表达式（`1 + 2`）
4. 常量折叠：`1 + 2 → 3`

MACRO 的内联发生在绑定阶段——执行引擎根本不知道 MACRO 的存在。这是零成本抽象的又一个实例。

## 7.4 子查询处理与相关子查询检测

子查询是 Binder 中最精妙的部分。子查询分为两类：

### 无相关子查询

```sql
SELECT * FROM orders
WHERE amount > (SELECT AVG(amount) FROM orders)
```

子查询 `(SELECT AVG(amount) FROM orders)` 不引用外层查询的任何列——它可以独立执行。Binder 为它创建一个子级 Binder，绑定结果是一个独立的 `BoundSubqueryExpression`，Planner 将其转化为独立的子计划。

### 相关子查询

```sql
SELECT * FROM orders o
WHERE amount > (SELECT AVG(amount) FROM orders WHERE region = o.region)
```

子查询引用了外层的 `o.region`——这是相关子查询。Binder 的处理方式：

1. **检测相关性**：当子级 Binder 绑定 `o.region` 时，它在外层 `BindContext` 中找到了这个列，标记 `depth = 1`
2. **收集相关列**：将 `CorrelatedColumnInfo{o.region, depth=1}` 添加到子级 Binder 的 `correlated_columns` 中
3. **标记 `has_unplanned_dependent_joins = true`**：通知 Planner 需要处理相关子查询

```cpp
// src/include/duckdb/planner/binder.hpp:86-103
struct CorrelatedColumnInfo {
    ColumnBinding binding;   // 列绑定信息
    LogicalType type;        // 列类型
    string name;             // 列名
    idx_t depth;             // 子查询深度
};
```

相关子查询在 Planner 中被转换为 **Dependent Join**（`LogicalDependentJoin`）——逻辑上等价于"对每一行外层数据，执行一次子查询"。Optimizer 会尝试将 Dependent Join "扁平化"（flatten）为普通 Join——如果子查询的选择性足够高，扁平化后的 HashJoin 通常比逐行执行子查询快几个数量级。

### EXISTS / NOT EXISTS 的特殊处理

```sql
SELECT * FROM customers c
WHERE EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.id)
```

`EXISTS` 子查询被 Binder 绑定为 `BoundSubqueryExpression(SubqueryType::EXISTS)`。Optimizer 将其转化为 Semi Join——只检查右表是否有匹配行，不需要实际返回右表的列。这是一个经典的优化——将 EXISTS 子查询转化为 `c SEMI JOIN o ON c.id = o.customer_id`。

## 7.5 BindContext：名字解析的核心数据结构

```cpp
// src/include/duckdb/planner/bind_context.hpp:42-80
class BindContext {
public:
    BindContext(Binder &binder);

    optional_ptr<Binding> GetMatchingBinding(const string &column_name, QueryErrorContext context);
    BindResult BindColumn(ColumnRefExpression &colref, idx_t depth);
    unique_ptr<ParsedExpression> CreateColumnReference(const string &table_name, const string &column_name);

    // 注册各种绑定
    void AddBinding(BindingAlias alias, unique_ptr<Binding> binding);
    void AddTableBinding(idx_t index, TableCatalogEntry &table, LogicalGet &get);
    void AddGenericBinding(idx_t index, const string &alias, vector<string> &names, vector<LogicalType> &types);
};
```

`BindContext` 维护一个"当前可见的名字空间"——所有已经绑定的表、CTE、子查询都在其中注册。它是一个扁平的名字表（不是树），但支持 `BindingAlias`（catalog.schema.table）的三级限定名。

当 `BindColumn` 被调用时，搜索策略是：

```
1. 如果列名有限定表名（如 orders.amount）→ 直接查该表
2. 如果列名无限定 → 遍历所有可见绑定，收集有该列名的绑定
   → 唯一匹配 → 成功
   → 多个匹配 → 报歧义错误，列出所有候选表
   → 无匹配 → 报未知列错误，附带 Levenshtein 距离最近的建议
```

### 表绑定的种类

| 绑定类型 | 来源 | 包含内容 |
|----------|------|----------|
| `TableBinding` | BaseTableRef → Catalog 中的表 | 列名列表 + 类型 + ColumnBinding |
| `CTEBinding` | CTE 定义 | 列名列表 + 类型 + CTE 索引 |
| `SubqueryBinding` | 子查询 | 列名列表 + 类型 + 子查询索引 |
| `GenericBinding` | DummyScan、VALUES | 列名列表 + 类型 |

### 模糊建议的实现

```cpp
// src/include/duckdb/planner/bind_context.hpp:55-56
vector<string> GetSimilarBindings(const string &column_name);
```

当你写错了列名（如 `amout` 而非 `amount`），DuckDB 会用 Levenshtein 编辑距离算法搜索最接近的 3 个列名，输出类似：

```
Binder Error: Referenced column "amout" not found in FROM clause!
Candidate bindings: "amount", "about"
```

这个"小"功能极大提升了开发体验——在调试复杂查询时，这种即时反馈节省了大量时间。

## 7.6 BoundStatement：绑定的最终输出

```cpp
struct BoundStatement {
    vector<LogicalType> types;      // 输出列类型
    vector<string> names;           // 输出列名
    unique_ptr<LogicalOperator> plan;  // 逻辑算子树的根
};
```

`BoundStatement` 是 Binder 的最终产品——它包含完整的列名、类型信息和一棵逻辑算子树。注意此时树上的算子仍然是逻辑的（`LogicalGet`, `LogicalFilter`, `LogicalJoin` 等），还没有物理实现细节。物理化是 `PhysicalPlanGenerator` 的工作（第 13 章）。

---

## 本章小结

Binder 是 SQL 编译中"最有人情味"的环节——它需要理解用户意图，处理歧义，给出有用的错误信息。核心要点：

1. **四层名字解析**：CTE → Catalog → Replacement Scan → 扩展自动加载，每层都有退路
2. **BindContext**：扁平的名字空间，支持三级限定名、模糊建议、USING 列共享
3. **函数重载解析**：cast score 驱动的最优匹配选择，兼顾正确性和效率
4. **相关子查询**：通过 `depth` 标记外层引用，`correlated_columns` 收集相关列，交给 Planner 做扁平化
5. **MACRO 内联**：绑定阶段的零成本抽象，执行引擎无感知

下一章，我们将看到 Planner 如何将 `BoundStatement` 中的语义信息转化为一棵 `LogicalOperator` 树——关系代数的程序化表达。
