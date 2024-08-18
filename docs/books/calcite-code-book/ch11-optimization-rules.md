# 第11章：优化规则深度解析

## 11.1 CoreRules 全景

`CoreRules`（997 行）是 Calcite 内置规则的注册中心，包含约 100 条预定义规则。按功能分为以下族：

| 族 | 规则数 | 核心变换 |
|----|--------|---------|
| Aggregate | 15+ | 合并、消除、下推、转置 |
| Filter | 12+ | 下推、合并、转置 |
| Project | 10+ | 合并、消除、下推、转置 |
| Join | 8+ | 转置、交换、条件化简 |
| Sort | 8+ | 消除、下推、合并 |
| Calc | 5+ | 合并、消除、拆分 |
| SetOp | 10+ | 合并、消除、转换 |
| SubQuery | 2+ | 子查询消除 |

## 11.2 投影下推规则族

投影下推是最基本也最有效的优化——减少中间结果的列数。

### 11.2.1 ProjectFilterTransposeRule

将 Project 下推到 Filter 之前：

```
Before: Project([a, b]) → Filter(cond) → Scan([a, b, c, d])
After:  Filter(cond) → Project([a, b]) → Scan([a, b, c, d])
        ↑ 条件只引用 a, b，所以 Project 可以下推
```

但注意：如果 Filter 条件引用了被 Project 丢弃的列，不能下推。

### 11.2.2 ProjectJoinTransposeRule

将 Project 下推到 Join 的两侧：

```
Before: Project([a, c]) → Join(cond) → Scan1([a, b]), Scan2([c, d])
After:  Join(cond) → Project([a, c])
          ↑
          Project([a]) → Scan1([a, b])    左侧只保留 a
          Project([c]) → Scan2([c, d])    右侧只保留 c
```

下推后，Join 处理的列更少，内存和 CPU 开销降低。

## 11.3 过滤下推规则族

过滤下推是最重要的优化——尽早减少行数。

### 11.3.1 FilterJoinRule (FilterIntoJoinRule)

将 Filter 条件下推到 Join 中：

```sql
SELECT * FROM emp e JOIN dept d ON e.dept_id = d.id WHERE e.salary > 1000
```

```
Before: Filter(salary > 1000) → Join(dept_id = id) → Scan(emp), Scan(dept)
After:  Join(dept_id = id AND salary > 1000) → Scan(emp), Scan(dept)
         ↑ salary > 1000 只引用左表，可以下推为 Join 的左表过滤条件
```

实际实现更精细——它会将条件分为三类：
- **左表条件**：下推到左输入之前
- **右表条件**：下推到右输入之前
- **跨表条件**：保留在 Join 条件中

### 11.3.2 FilterAggregateTransposeRule

将 Filter 下推到 Aggregate 之前：

```
Before: Filter(dept = 'Sales') → Aggregate(groupBy=[dept], sum=[salary])
After:  Aggregate(groupBy=[dept], sum=[salary]) → Filter(dept = 'Sales')
         ↑ 先聚合再过滤
```

等一下——这看起来是把 Filter 上推了？实际上，这个规则的真正用途是处理 **HAVING 条件的下推**。当 HAVING 条件中有不引用聚合函数的条件时，可以下推到 GROUP BY 之前：

```sql
-- HAVING 中包含非聚合条件
SELECT dept, SUM(salary) FROM emp GROUP BY dept HAVING dept = 'Sales'
-- dept = 'Sales' 不引用聚合函数，可以下推为 WHERE
```

### 11.3.3 FilterSetOpTransposeRule

将 Filter 下推到 Union/Intersect/Minus 的各分支：

```
Before: Filter(cond) → Union → Scan1, Scan2
After:  Union → Filter(cond) → Scan1, Filter(cond) → Scan2
```

## 11.4 聚合优化规则族

### 11.4.1 AggregateMergeRule

合并嵌套的 Aggregate：

```
Before: Aggregate(groupSet=[0], SUM=[1]) → Aggregate(groupSet=[0, 1], SUM=[2])
After:  Aggregate(groupSet=[0, 1], SUM=[2])  -- 直接在原始数据上聚合
```

条件：内层 Aggregate 的分组列是外层分组列的子集，且聚合函数可合并（如 SUM(SUM(x)) = SUM(x)）。

### 11.4.2 AggregateReduceFunctionsRule

将复杂聚合函数分解为简单聚合：

```
AVG(salary) → SUM(salary) / COUNT(salary)
STDDEV(salary) → 基于 SUM, COUNT, SUM_SQUARE 计算
COVAR_POP(x, y) → 基于 SUM, COUNT 计算
```

分解后，优化器可以对简单聚合做更多优化（如部分聚合下推）。

### 11.4.3 AggregateJoinTransposeRule

将 Aggregate 下推到 Join 之前：

```sql
SELECT d.dept_name, COUNT(*)
FROM emp e JOIN dept d ON e.dept_id = d.id
GROUP BY d.dept_name
```

```
Before: Aggregate(group=[dept_name], COUNT) → Join → Scan(emp), Scan(dept)
After:  Join → Aggregate(group=[dept_name], COUNT)
          ↑
          Aggregate(group=[dept_id], COUNT) → Scan(emp)  -- 先在 emp 上按 dept_id 聚合
          Project(dept_name) → Scan(dept)                -- dept 表只取需要的列
```

这显著减少了 Join 的输入行数——先聚合再 Join 而非先 Join 再聚合。

## 11.5 Join 重排序：DpHyp 算法

### 11.5.1 问题本质

N 个表的 Join 顺序有 (2N-1)!! 种可能。当 N > 10 时，穷举不可行。Calcite 提供了两种 Join 重排序方法：

1. **MultiJoin + LoptOptimizeJoinRule**：基于启发式的左深树优化
2. **DphypJoinReorderRule**：基于动态规划的稠密树优化

### 11.5.2 DpHyp 算法

`DpHyp`（`rel/rules/DpHyp.java`）实现了 DPHyp 算法（Neumann and Kemper, 2009），可以在 O(3^N) 时间内找到最优的 bushy Join 顺序：

```java
// DpHyp 简化
class DpHyp {
  // 搜索最优 Join 顺序
  RelNode findBestOrder(VolcanoPlanner planner, RelMetadataQuery mq) {
    // dpTable: 记录每个表子集的最优计划
    Map<ImmutableBitSet, RelSubset> dpTable = new HashMap<>();

    // 1. 初始化：每个单表的最优计划
    for (RelNode table : tables) {
      dpTable.put(tableSet, register(table));
    }

    // 2. 递归枚举：从小到大枚举表子集
    for (int size = 2; size <= tables.size(); size++) {
      for (ImmutableBitSet subset : subsetsOf(size)) {
        // 枚举所有二分法 partition
        for (Pair<ImmutableBitSet, ImmutableBitSet> partition : partitions(subset)) {
          RelNode left = dpTable.get(partition.left);
          RelNode right = dpTable.get(partition.right);
          if (hasJoinCondition(left, right)) {
            RelNode join = LogicalJoin.create(left, right, condition);
            if (cost(join) < cost(dpTable.get(subset))) {
              dpTable.put(subset, join);
            }
          }
        }
      }
    }

    return dpTable.get(allTables);
  }
}
```

### 11.5.3 启用 Join 重排序

```java
// 通过 Programs.heuristicJoinOrder()
Program program = Programs.heuristicJoinOrder(ImmutableList.of(
    FilterJoinRule.FILTER_INTO_JOIN,
    JoinCommuteRule.INSTANCE,
    DphypJoinReorderRule.INSTANCE
), false);
```

## 11.6 子查询消除：SubQueryRemoveRule

`SubQueryRemoveRule` 将 SQL 子查询转换为关系代数操作：

| 子查询类型 | 转换目标 |
|-----------|---------|
| `WHERE x IN (SELECT ...)` | SemiJoin |
| `WHERE x NOT IN (SELECT ...)` | AntiJoin |
| `WHERE EXISTS (SELECT ...)` | SemiJoin |
| `WHERE NOT EXISTS (SELECT ...)` | AntiJoin |
| 标量子查询 | Aggregate + Correlate |
| `ARRAY(SELECT ...)` | Correlate + Collect |

## 11.7 物化视图规则族

`rel/rules/materialize/`（10 文件）提供了 6 条物化视图匹配规则：

```
MaterializedViewFilterRule        — Filter + Scan → Scan(物化视图)
MaterializedViewProjectFilterRule — Project + Filter + Scan → Scan(物化视图)
MaterializedViewJoinRule          — Join → Join with 物化视图
MaterializedViewProjectJoinRule   — Project + Join → ...
MaterializedViewAggregateRule     — Aggregate → Aggregate on 物化视图
MaterializedViewOnlyAggregateRule — 聚合专用匹配
```

## 11.8 剪枝规则：PruneEmptyRules

`PruneEmptyRules` 检测并消除产出空集的子树：

```
Filter(FALSE) → 任何输入     → Values(empty)  -- 条件永假
Union()                         → Values(empty)  -- 空的 Union
Intersect(空输入)               → Values(empty)  -- 空的 Intersect
Values(空行列表)               → Values(empty)
Aggregate(空输入)              → Values(empty)
```

这是 Calcite 1.42 修复了 WINDOW 语句中此规则失效的问题（CALCITE-7490）。

## 11.9 从 Spark/StarRocks 视角对比

| 优化类别 | Calcite | Spark Catalyst | StarRocks |
|---------|---------|----------------|-----------|
| 谓词下推 | FilterJoinRule | PushDownPredicate | PushDownPredicates |
| 投影下推 | ProjectJoinTransposeRule | PruneFileSourcePartitions | ColumnPruning |
| 常量折叠 | ReduceExpressionsRule | ConstantFolding | ConstantFolding |
| Join 重排 | DpHyp | JoinReorderDP | DPHyp |
| 子查询消除 | SubQueryRemoveRule | RewriteSubquery | SubqueryRewrite |
| 聚合拆分 | AggregateReduceFunctionsRule | 不内置 | 内置 |
| 规则数量 | 100+ | 30+ | 50+ |

Calcite 的规则库比 Spark 和 StarRocks 都要丰富，但代价是规则间交互更复杂，VolcanoPlanner 可能需要更多迭代才能收敛。

---

## 本章小结

Calcite 的 100+ 条优化规则覆盖了投影下推、过滤下推、聚合优化、Join 重排序、子查询消除等所有经典优化。FilterJoinRule 是最重要的规则，将条件下推到 Join 两侧。DpHyp 算法实现高效的 Join 重排序。PruneEmptyRules 消除空子树。与 Spark/StarRocks 相比，Calcite 的规则更丰富但也更复杂。下一章将深入元数据系统——规则和代价计算的信息基础。
