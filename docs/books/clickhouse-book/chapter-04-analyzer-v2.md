# Chapter 4: Analyzer v2 — QueryTree 与 Pass 管理器

## 4.1 为什么需要 Analyzer v2？

ClickHouse 历史上有两套分析器：
- **旧版**：`Interpreters/ExpressionAnalyzer` — 直接操作 AST，名称解析、类型推导、优化全部耦合在一个巨大的类中
- **新版**：`Analyzer/` — 基于 QueryTree 的语义分析框架，通过 Pass 管理器实现可扩展的优化管线

核心区别：AST 是语法表示（不知道列来自哪个表、类型是什么），QueryTree 是语义表示（每个节点都知道自己的类型和来源）。

### 旧版 ExpressionAnalyzer 的问题

```
1. 名称解析与优化耦合
   → 添加优化需要修改同一个类
   → 不同优化之间可能冲突

2. 缺乏结构化表示
   → AST 只有字符串标识符，不知道列来自哪个表
   → 每次需要来源信息都要重新查找符号表

3. 难以扩展
   → 新的优化规则需要侵入式修改
   → 优化顺序难以调整

4. 无法表达复杂语义
   → JOIN 重排需要理解表间关系
   → AST 层面缺乏这种信息
```

### Analyzer v2 的设计目标

```
1. 语义化 — 每个节点知道自己的类型和来源
2. 可扩展 — 通过 Pass 管理器添加优化
3. 可调试 — QueryTree ↔ AST 双向转换
4. 可分析 — 支持更复杂的优化（CBO Join Reorder）
```

## 4.2 QueryTree 节点类型

`src/Analyzer/IQueryTreeNode.h:29-49` — QueryTree 的节点类型枚举：

```cpp
enum class QueryTreeNodeType : uint8_t
{
    IDENTIFIER,       // 标识符（解析阶段，尚未解析到具体列）
    MATCHER,          // COLUMNS(...) 匹配器
    TRANSFORMER,      // 列变换器
    LIST,             // 节点列表
    CONSTANT,         // 常量值
    FUNCTION,         // 函数调用
    COLUMN,           // 已解析的列（知道来源表、类型）
    LAMBDA,           // Lambda 表达式
    SORT,             // 排序描述
    INTERPOLATE,      // 插值
    WINDOW,           // 窗口函数
    TABLE,            // 表引用
    TABLE_FUNCTION,   // 表函数 (file(), url(), s3())
    QUERY,            // 子查询
    ARRAY_JOIN,       // ARRAY JOIN
    CROSS_JOIN,       // 交叉连接
    JOIN,             // JOIN
    UNION,            // UNION
};
```

### IQueryTreeNode 基类

```cpp
// src/Analyzer/IQueryTreeNode.h:87-120
class IQueryTreeNode : public TypePromotion<IQueryTreeNode>
{
public:
    virtual QueryTreeNodeType getNodeType() const = 0;
    virtual DataTypePtr getResultType() const;  // 类型推导结果

    // 弱指针到来源节点（列→表、函数→参数来源）
    using WeakPtr = std::weak_ptr<IQueryTreeNode>;

    // 可逆转换：QueryTree ↔ AST
    virtual ASTPtr toAST(const ConvertToASTOptions & options) const = 0;

    // 节点比较（用于缓存 key）
    virtual bool isEqual(const IQueryTreeNode & rhs) const = 0;

    // 子节点访问
    List & getChildren();
    const List & getChildren() const;
};
```

**弱指针来源追踪**：每个 `ColumnNode` 保持一个 `weak_ptr` 指向它的来源（TableNode / LambdaNode / SubqueryNode）。这使得 Planner 可以确定列来自哪个表，而不需要额外的符号表查找。

## 4.3 核心节点类型

### QueryNode — 查询节点

`src/Analyzer/QueryNode.h` — 对应一个 SELECT 查询：

```
QueryNode
  ├── projection: [ColumnNode, FunctionNode, ...]   // SELECT 列表
  ├── from: TableNode | JoinNode | SubqueryNode      // FROM 子句
  ├── where: FunctionNode                             // WHERE
  ├── prewhere: FunctionNode                          // PREWHERE
  ├── group_by: [ColumnNode, FunctionNode, ...]       // GROUP BY
  ├── having: FunctionNode                            // HAVING
  ├── order_by: [SortNode, ...]                       // ORDER BY
  ├── limit_by: [SortNode, ...] + ConstantNode        // LIMIT BY
  ├── limit: ConstantNode                             // LIMIT
  └── join: JoinNode | CrossJoinNode                  // JOIN
```

### TableNode — 表引用

`src/Analyzer/TableNode.h` — 表示一个表（或子查询）：

```cpp
class TableNode : public IQueryTreeNode
{
    // 表的来源
    StoragePtr storage;           // 已解析的存储引擎
    TableExpressionPtr table_expression; // AST 中的表表达式

    // 表的统计信息（CBO 使用）
    std::optional<TableStatistics> statistics;
};
```

### ColumnNode — 列引用

`src/Analyzer/ColumnNode.h` — 已解析的列引用：

```cpp
class ColumnNode : public IQueryTreeNode
{
    String column_name;               // 列名
    DataTypePtr column_type;          // 列类型
    WeakPtr source_node;              // 来源节点（TableNode / LambdaNode / SubqueryNode）

    // 列统计信息
    std::optional<ColumnStatistics> statistics;
};
```

### JoinNode — JOIN 节点

`src/Analyzer/JoinNode.h` — 独立的 JOIN 表示：

```
JoinNode
  ├── left_table: TableNode | JoinNode    // 左侧
  ├── right_table: TableNode              // 右侧
  ├── join_conditions: [FunctionNode]     // ON 条件
  ├── join_kind: Left / Right / Inner / Full / Cross
  └── join_strictness: All / Any / Asof
```

### FunctionNode — 函数节点

`src/Analyzer/FunctionNode.h` — 包含函数解析结果：

```
FunctionNode
  ├── function_name: String           // "plus", "count"
  ├── arguments: [QueryTreeNodePtr]   // 参数列表
  ├── result_type: DataTypePtr        // 返回类型（已推导）
  └── function: IFunctionBasePtr      // 已解析的函数实现
```

**类型推导**：FunctionNode 在构造时就完成了类型推导——`getResultType()` 直接返回缓存的结果，不需要运行时计算。这是 QueryTree 相对 AST 的关键优势。

## 4.4 QueryTreeBuilder：AST → QueryTree

`src/Analyzer/QueryTreeBuilder.h` — 将 AST 转换为 QueryTree：

```cpp
class QueryTreeBuilder
{
public:
    static QueryTreeNodePtr build(
        const ASTPtr & ast,
        ContextPtr context);

    // 带 CTE 支持
    static QueryTreeNodePtr build(
        const ASTPtr & ast,
        ContextPtr context,
        const std::unordered_map<String, QueryTreeNodePtr> & ctes);
};
```

**构建过程**：

```
Step 1: 创建初始 QueryTree
  AST → QueryTree 节点
  → 列引用还是 IdentifierNode（不知道来源）
  → 函数调用还是未解析的 FunctionNode

Step 2: QueryAnalysisPass — 名称解析
  对每个 IdentifierNode:
    1. 在 FROM 子句的表中查找列名
    2. 找到 → 转换为 ColumnNode
       → 设置 weak_ptr 指向来源 TableNode
    3. 未找到 → 检查 CTE / 子查询
    4. 仍未找到 → 报错 "Unknown identifier"

Step 3: 类型推导
  对每个 FunctionNode:
    → 根据参数类型推导返回类型
    → 解析函数实现（IFunctionBasePtr）

Step 4: 语义检查
  → GROUP BY 键合法性
  → HAVING 子句引用合法性
  → 窗口函数使用合法性
```

### CTE (Common Table Expression) 处理

```sql
WITH
    cte1 AS (SELECT a, b FROM t1),
    cte2 AS (SELECT a, c FROM t2)
SELECT * FROM cte1 JOIN cte2 ON cte1.a = cte2.a
```

```
CTE 处理:
  1. 解析 WITH 子句 → 每个 CTE 定义创建一个 QueryNode
  2. 存储 CTE 名称 → QueryNode 的映射
  3. 解析主查询时，遇到 CTE 名称 → 替换为对应的 QueryNode
  4. CTE 可以引用之前定义的 CTE（顺序依赖）

递归 CTE:
  ClickHouse 不支持递归 CTE (WITH RECURSIVE)
  → 这是与 PostgreSQL 的一个重要差异
```

### 标识符解析规则

```
解析顺序:
  1. 当前查询的 FROM 子句中的表列
  2. CTE 定义
  3. 外层查询的列（子查询中引用外部列）
  4. 数据库函数/表函数

歧义处理:
  SELECT t1.a, t2.a FROM t1 JOIN t2 ON t1.id = t2.id
  → t1.a 和 t2.a 通过表前缀区分
  → 未加前缀的 a 是歧义的，报错

星号展开:
  SELECT * FROM t → 展开 t 的所有列
  SELECT t.* FROM t JOIN t2 → 展开 t 的所有列
  SELECT * EXCEPT (a) FROM t → 展开除 a 外的所有列
  SELECT * REPLACE (a + 1 AS a) FROM t → 展开并替换
```

## 4.5 QueryTreePassManager：优化管线

`src/Analyzer/QueryTreePassManager.h` — 管理和调度优化 Pass：

```cpp
class QueryTreePassManager : public WithContext
{
public:
    void addPass(QueryTreePassPtr pass);
    void run(QueryTreeNodePtr & query_tree_node);        // 运行所有 pass
    void run(QueryTreeNodePtr & query_tree_node, size_t up_to_pass_index);
    void runOnlyResolve(QueryTreeNodePtr & query_tree_node);
};
```

### 注册的 Pass 列表（`QueryTreePassManager.cpp:263-340`）

共 **41 个 Pass**，按功能分为 5 类：

**1. 分析与解析（3 个）**
| Pass | 作用 |
|------|------|
| `QueryAnalysisPass` | 名称解析、类型推导、列来源追踪 |
| `GroupingFunctionsResolvePass` | 解析 GROUPING() 函数 |
| `AutoFinalOnQueryPass` | 自动添加 FINAL（当表有轻量删除时） |

**2. 列裁剪（2 个）**
| Pass | 作用 |
|------|------|
| `RemoveUnusedProjectionColumnsPass` | 移除 SELECT 中未使用的列 |
| `PruneArrayJoinColumnsPass` | 裁剪 ARRAY JOIN 中未使用的列 |

**3. 表达式重写（~25 个）**
| Pass | 作用 |
|------|------|
| `ConvertLogicalExpressionToCNFPass` | 逻辑表达式 → 合取范式 |
| `CountDistinctPass` | `COUNT(DISTINCT x)` → `uniqExact(x)` |
| `UniqToCountPass` | `uniq(x)` → `count()` 当精确度可接受 |
| `CrossToInnerJoinPass` | 笛卡尔积 → INNER JOIN（基于 WHERE 条件） |
| `RewriteSumFunctionWithSumAndCountPass` | `sum(x * y)` → `sum(x) * sum(y)` 在分组键上 |
| `FunctionToSubcolumnsPass` | `length(arr)` → `arr.size0` 子列访问 |
| `InverseDictionaryLookupPass` | 逆向字典查找优化 |
| `LikePerfectAffixRewritePass` | LIKE 前缀/后缀重写 |
| `IfTransformStringsToEnumPass` | IF + 字符串 → Enum 优化 |
| `FuseFunctionsPass` | 函数融合 |

**4. GROUP BY / ORDER BY 优化（6 个）**
| Pass | 作用 |
|------|------|
| `AggregateFunctionOfGroupByKeysPass` | 聚合函数在 GROUP BY 键上简化 |
| `OptimizeGroupByFunctionKeysPass` | GROUP BY 函数键优化 |
| `OptimizeGroupByInjectiveFunctionsPass` | 单射函数 GROUP BY 简化 |
| `OptimizeRedundantFunctionsInOrderByPass` | ORDER BY 冗余函数消除 |
| `TruncateOrderByAfterGroupByKeysPass` | GROUP BY 后截断 ORDER BY |
| `OrderByTupleEliminationPass` | ORDER BY 元组消除 |

**5. 并行与调度（2 个）**
| Pass | 作用 |
|------|------|
| `InjectRandomOrderIfNoOrderByPass` | 无 ORDER BY 时注入随机顺序（并行读取） |
| `DisableParallelReplicasPass` | 禁止并行副本（条件检测） |

### Pass 执行模型

```cpp
void QueryTreePassManager::run(QueryTreeNodePtr & query_tree_node)
{
    for (auto & pass : passes)
    {
        pass->run(query_tree_node, getContext());
        // 每个 pass 执行后，query_tree_node 可能被原地修改
    }
}
```

Pass 之间通过 `QueryTreeNodePtr &` 引用传递，每个 Pass 可以：
- 替换节点（`query_tree_node = new_node`）
- 修改子树（`node->getChildren()[i] = new_child`）
- 移除节点（将引用设为 `nullptr` 或空列表）

### 重要 Pass 详解

#### CrossToInnerJoinPass — 笛卡尔积优化

```
输入:
  SELECT * FROM t1, t2 WHERE t1.id = t2.id

转换前:
  FROM: CrossJoin(t1, t2)
  WHERE: equals(t1.id, t2.id)

转换后:
  FROM: InnerJoin(t1, t2, ON t1.id = t2.id)
  WHERE: (empty)

效果:
  Cross Join (M × N 行) → Inner Join (M + N 行)
  性能提升: 数量级
```

#### CountDistinctPass — 去重计数优化

```
COUNT(DISTINCT x) → uniqExact(x)

为什么转换?
  COUNT(DISTINCT) 是 SQL 标准语法
  uniqExact 是 ClickHouse 内部函数名
  转换后可以应用后续优化:
    - 如果 GROUP BY 包含 x → uniqExact(x) = count()
    - 如果精度可接受 → uniq(x) (近似算法，更快)
```

#### FunctionToSubcolumnsPass — 子列优化

```
length(arr) → arr.size0

为什么?
  length(arr) 需要读取整个 arr 列（反序列化 offset 数组）
  arr.size0 是 ColumnArray 的子列，直接存储大小值
  → 读取 size0 比读取整个 arr 快得多

类似的子列优化:
  mapKeys(m) → m.keys
  mapValues(m) → m.values
  nullable_column.null → null bitmap
  low_cardinality_column.dictionary → 字典
```

> **侧边栏 · 与 Spark Catalyst 对比**：Spark Catalyst 使用规则批次（RuleBatch）+ 固定迭代次数的策略（如 `FixedPoint(100)`），允许规则在多轮迭代中收敛。ClickHouse 的 Pass 管理器是单遍执行——每个 Pass 只运行一次，不迭代。这意味着 Pass 的顺序至关重要（如 `CrossToInnerJoinPass` 必须在名称解析之后），且 Pass 之间不能有循环依赖。这种设计的 trade-off：可预测的执行时间 vs 可能错过某些多轮优化机会。

## 4.6 QueryTree ↔ AST 双向转换

QueryTree 的一个重要约束：**必须能无损失地转换回 AST**（`IQueryTreeNode.h:63-64`）。

```cpp
// 每个 QueryTreeNode 都实现了 toAST()
virtual ASTPtr toAST(const ConvertToASTOptions & options) const = 0;
```

这保证了：
1. `EXPLAIN QUERY TREE` 可以将优化后的 QueryTree 重新格式化为 SQL
2. 分布式查询中可以将 QueryTree 序列化发送到远程节点
3. 调试时可以对比优化前后的 SQL 文本

### EXPLAIN QUERY TREE

```sql
EXPLAIN QUERY TREE SELECT a, count() FROM t GROUP BY a

输出:
  └── QueryNode
        ├── projection: [ColumnNode(a), FunctionNode(count)]
        ├── from: TableNode(t)
        └── group_by: [ColumnNode(a)]
```

## 4.7 QueryTree vs AST 对比

| 维度 | AST | QueryTree |
|------|-----|-----------|
| 标识符 | 字符串 `"user_id"` | ColumnNode（带来源表指针） |
| 类型信息 | 无 | 每个节点有 `getResultType()` |
| 函数解析 | 函数名未解析 | FunctionNode（已绑定 IFunctionBasePtr） |
| 优化 | 难（缺乏语义信息） | 易（节点有完整语义） |
| 格式化 | 原生支持 | 通过 `toAST()` 间接支持 |
| 来源追踪 | 无 | ColumnNode → TableNode 弱指针 |

## 4.8 本章小结

Analyzer v2 的核心架构：

```
AST → QueryTreeBuilder → QueryTree → QueryTreePassManager → Optimized QueryTree
                              │                                      │
                              ├── QueryAnalysisPass（名称解析）         └── → Planner
                              ├── 41 个优化 Pass
                              └── 每个 Pass 独立、单遍执行
```

**关键设计决策**：
- **弱指针来源追踪** — ColumnNode → TableNode，无需符号表
- **单遍 Pass 执行** — 可预测性能，但 Pass 顺序至关重要
- **QueryTree ↔ AST 双向转换** — 保证调试和分布式场景的完整性
- **类型推导缓存** — FunctionNode 构造时完成类型推导，运行时零开销

**关键文件地图**：
```
src/Analyzer/IQueryTreeNode.h          → QueryTree 节点基类
src/Analyzer/QueryNode.h               → 查询节点
src/Analyzer/TableNode.h               → 表节点
src/Analyzer/ColumnNode.h              → 列节点
src/Analyzer/FunctionNode.h            → 函数节点
src/Analyzer/JoinNode.h                → JOIN 节点
src/Analyzer/QueryTreeBuilder.h        → AST → QueryTree
src/Analyzer/QueryTreePassManager.h    → Pass 管理器
src/Analyzer/IQueryTreePass.h          → Pass 基类
src/Analyzer/Passes/                   → 所有 Pass 实现
```
