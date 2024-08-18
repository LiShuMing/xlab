# 第11章：Join Order 优化

> 多表 Join 的排列组合是 NP-hard 问题——5 张表有 120 种 Join 顺序，10 张表有超过 36 亿种。DuckDB 使用 DP + Greedy 的混合策略，在有限时间内找到"足够好"的 Join 顺序。

## 11.1 问题定义：Join 排序为什么重要

```sql
SELECT * FROM a JOIN b ON a.id = b.a_id JOIN c ON b.id = c.b_id;
```

三种可能的 Join 顺序：
1. `(a JOIN b) JOIN c` — 如果 a 有 100 行，b 有 100万行，c 有 10 行
2. `(a JOIN c) JOIN b` — 先连接小表
3. `(b JOIN c) JOIN a` — 先连接大表

Join 顺序决定了中间结果的大小——错误的顺序可能导致中间结果膨胀到几十亿行，而正确的顺序可能只有几千行。

## 11.2 JoinOrderOptimizer 的实现

```cpp
// src/optimizer/join_order/join_order_optimizer.cpp
class JoinOrderOptimizer {
public:
    unique_ptr<LogicalOperator> Optimize(unique_ptr<LogicalOperator> plan);

private:
    // 核心数据结构
    JoinRelationSetManager set_manager;     // 管理表的子集
    vector<unique_ptr<FilterInfo>> filters; // Join 条件和过滤条件
    vector<JoinNode *> plans;               // DP 表：每个子集的最优计划

    // DP 求解
    JoinNode *SolveJoinOrder();
    JoinNode *GenerateCrossProduct(JoinRelationSet &set);
};
```

### DP 求解过程

1. **提取 Query Graph**：将逻辑计划中的所有 Join 条件和表引用提取为 Query Graph
2. **枚举子集**：对每个表的子集，计算最优的 Join 顺序
3. **自底向上 DP**：从单表开始，逐步合并更大的子集

```
DP 表（3 表 Join 的示例）：
{a}     → cost=100 (scan a)
{b}     → cost=1M  (scan b)
{c}     → cost=10  (scan c)
{a,b}   → cost=5K  (a JOIN b, 选择性高)
{a,c}   → cost=1K  (a JOIN c)
{b,c}   → cost=100K (b JOIN c)
{a,b,c} → min({a,b} JOIN c, {a,c} JOIN b, {b,c} JOIN a)
```

### Greedy 回退

当表数量超过 DP 的阈值时（默认 12 张表），DuckDB 切换到 Greedy 策略——每次选择代价最小的 Join，贪心构建 Join 树。Greedy 不是最优的，但在 O(n²) 时间内完成，不会因组合爆炸而超时。

## 11.3 基数估算

Join 代价的核心输入是基数估算——每个 Join 的中间结果有多少行？

```cpp
// src/optimizer/statistics_propagator.cpp
// StatisticsPropagator 使用列统计信息估算 Join 的选择性
```

DuckDB 的基数估算策略：

- **等值 Join (a.id = b.id)**：选择性 = 1 / max(NDV(a.id), NDV(b.id))，NDV = Number of Distinct Values
- **范围 Join (a.x > b.y)**：选择性 = 1/3（经验值）
- **无统计信息**：默认选择性 = 0.1（10%）

这种估算是粗糙的——DuckDB 不维护精确的直方图（如 PostgreSQL 的 MCV 列表），但在实践中"够用"。OLAP 查询通常涉及大表扫描，精确的基数估算对整体性能的影响不如谓词下推和列裁剪显著。

---

## 第12章：统计信息与代价模型

### DuckDB 收集哪些统计信息

```cpp
// src/include/duckdb/storage/statistics/
// BaseStatistics 是统计信息的基类
class BaseStatistics {
    LogicalType type;
    bool has_null;
    // NumericStatistics 额外包含：min, max
    // StringStatistics 额外包含：min, max, NDV 估算
};
```

DuckDB 在每个 RowGroup 的每个列上维护：
- **min / max**：列的最小值和最大值（Zone Map）
- **has_null**：该列是否有 NULL 值
- **NDV**（部分类型）：不同值的数量估算

### RowGroup Pruner

```cpp
// src/optimizer/row_group_pruner.cpp
// 利用 Zone Map 在逻辑计划阶段裁剪不需要的 RowGroup
```

`RowGroupPruner` 将 `LogicalGet` 中的 `table_filters` 与每个 RowGroup 的 min/max 统计对比。如果一个 RowGroup 的 `amount` 列范围是 [50, 80]，而过滤条件是 `amount > 100`，该 RowGroup 被标记为"可跳过"。

这是列式存储最强大的 Data Skipping 机制——不是索引，而是"隐式索引"。OLTP 数据库依赖 B-Tree 索引来快速定位行，OLAP 数据库依赖 Zone Map + 列裁剪来快速跳过不相关的数据块。两种范式的"索引哲学"完全不同。

### 代价模型：为什么 DuckDB 不做精确代价估算

DuckDB 不像 PostgreSQL 那样维护精细的代价模型（seq_page_cost, random_page_cost, cpu_tuple_cost 等参数）。原因：

1. **OLAP 的瓶颈是 I/O 而非 CPU**——列裁剪和 Zone Map 裁剪的影响远大于 Join 顺序的微调
2. **嵌入式场景缺少统计收集时机**——没有 ANALYZE 命令的自动执行窗口
3. **查询编译时间需要短**——精确代价估算本身可能比执行查询更慢

DuckDB 的选择是：用粗略的基数估算指导 Join 排序，用 Zone Map 指导 RowGroup 裁剪，用启发式规则（而非代价模型）做大多数优化决策。这是一个有意识的工程折中。
