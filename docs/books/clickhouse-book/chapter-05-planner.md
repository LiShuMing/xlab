# Chapter 5: Planner — 从 QueryTree 到 QueryPlan

## 5.1 Planner 的角色

Planner 位于 Analyzer 和 Pipeline 之间，负责将语义化的 QueryTree 转换为可执行的 QueryPlan：

```
Optimized QueryTree → Planner → QueryPlan → QueryPlanOptimizer → QueryPipeline
```

## 5.2 源码导航

| 文件 | 作用 |
|------|------|
| `src/Planner/Planner.h` | Planner 主入口 |
| `src/Planner/PlannerJoins.h` | JOIN 规划 |
| `src/Planner/PlannerJoinsLogical.h` | 逻辑 JOIN 规划（Analyzer v2 路径） |
| `src/Planner/PlannerAggregation.h` | 聚合规划 |
| `src/Planner/PlannerSorting.h` | 排序规划 |
| `src/Planner/PlannerWindowFunctions.h` | 窗口函数规划 |
| `src/Planner/PlannerContext.h` | 规划上下文 |
| `src/Processors/QueryPlan/` | QueryPlan Step 定义 |
| `src/Processors/QueryPlan/Optimizations/joinOrder.cpp` | Join Reorder CBO 框架 |

## 5.3 QueryPlan：声明式执行计划

QueryPlan 由一系列 `IQueryPlanStep` 组成，每个 Step 表示一个逻辑操作：

```
QueryPlan:
  └── LimitStep
        └── SortingStep
              └── AggregatingStep
                    ├── ExpressionStep (before GROUP BY)
                    │     └── JoinStep
                    │           ├── ReadFromMergeTree (left)
                    │           └── ReadFromMergeTree (right)
                    └── ExpressionStep (after GROUP BY)
```

### IQueryPlanStep 核心接口

```cpp
class IQueryPlanStep
{
public:
    virtual String getName() const = 0;
    virtual Type getType() const = 0;   // Read / Transform / Sink

    // 将 Step 转换为 Processor（物理执行节点）
    virtual QueryPipelineBuilderPtr updatePipeline(
        QueryPipelineBuilders pipelines) const = 0;

    // 优化接口
    virtual void describeActions(FormatSettings & settings) const = 0;
    virtual void describePipeline(FormatSettings & settings) const = 0;
};
```

### 核心步骤类型

| Step | 作用 | 关键文件 |
|------|------|----------|
| `ReadFromMergeTree` | 从 MergeTree 读取 | `ReadFromMergeTree.h` |
| `FilterStep` | WHERE 过滤 | `FilterStep.h` |
| `ExpressionStep` | 表达式求值/投影 | `ExpressionStep.h` |
| `JoinStepLogical` → `JoinStep` | JOIN 操作 | `JoinStepLogical.h` |
| `AggregatingStep` | GROUP BY | `AggregatingStep.h` |
| `MergingAggregatedStep` | 聚合结果合并 | `MergingAggregatedStep.h` |
| `SortingStep` | ORDER BY | `SortingStep.h` |
| `LimitStep` | LIMIT | `LimitStep.h` |
| `UnionStep` | UNION ALL | `UnionStep.h` |
| `ExtremesStep` | 极值计算 | `ExtremesStep.h` |
| `TotalsHavingStep` | WITH TOTALS | `TotalsHavingStep.h` |
| `WindowStep` | 窗口函数 | `WindowStep.h` |
| `SortingStep` | 排序 | `SortingStep.h` |
| `DistinctStep` | DISTINCT | `DistinctStep.h` |
| `RollupStep` / `CubeStep` | ROLLUP / CUBE | `RollupStep.h` |

### QueryPlan 树的构建

```
Planner 从 QueryTree 构建 QueryPlan 的过程:

1. 识别 FROM 子句 → ReadFromMergeTree Step
2. 识别 JOIN → JoinStepLogical Step
3. 识别 WHERE → FilterStep
4. 识别 GROUP BY → AggregatingStep
5. 识别 HAVING → FilterStep (在聚合后)
6. 识别 SELECT 表达式 → ExpressionStep
7. 识别 ORDER BY → SortingStep
8. 识别 LIMIT → LimitStep
9. 识别 DISTINCT → DistinctStep

构建顺序: 自底向上
  Step 的输入是子 Step 的输出
  最终形成一棵 Step 树
```

## 5.4 聚合规划

`src/Planner/PlannerAggregation.h` — 聚合函数的规划涉及多个 Step：

### 两阶段聚合

```
第一阶段: AggregatingStep
  每个读取线程独立聚合
  → 输出: 部分聚合状态 (AggregateDataPtr)

第二阶段: MergingAggregatedStep
  合并所有线程的部分聚合状态
  → 输出: 最终聚合结果

为什么需要两阶段?
  单阶段聚合: 所有线程共享一个哈希表 → 锁竞争严重
  两阶段聚合: 每个线程独立哈希表 → 无锁 → 并行度更高
```

### 分布式聚合

```
分布式查询中的聚合:

模式 1: WithMergeableState
  Shard 1: GROUP BY key → 部分聚合状态
  Shard 2: GROUP BY key → 部分聚合状态
  Coordinator: MergingAggregated → 最终结果

模式 2: WithMergeableStateAfterAggregation (当 GROUP BY = sharding_key)
  Shard 1: GROUP BY sharding_key → 最终结果（数据不跨分片）
  Coordinator: 直接拼接（无需重新聚合）
```

### 聚合优化

```
优化 1: 聚合键简化
  GROUP BY date, toYYYYMM(date)
  → toYYYYMM(date) 可从 date 推导，不加入哈希键

优化 2: 单射函数简化
  GROUP BY user_id, toString(user_id)
  → toString 是单射函数，不加入哈希键

优化 3: TopN 优化 (PR #102024)
  SELECT key, sum(value) FROM t GROUP BY key ORDER BY sum(value) DESC LIMIT 10
  → 维护 Top-10 的部分聚合状态
  → 避免完整排序
```

## 5.5 窗口函数规划

`src/Planner/PlannerWindowFunctions.h` — 窗口函数的规划：

```sql
SELECT
    user_id,
    event_time,
    row_number() OVER (PARTITION BY user_id ORDER BY event_time) AS rn,
    sum(amount) OVER (PARTITION BY user_id ORDER BY event_time
                      ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_sum
FROM events
```

### WindowStep

```
WindowStep 的处理流程:
  1. 按 PARTITION BY 列排序（将相同分区的行放在一起）
  2. 在分区内按 ORDER BY 排序
  3. 计算窗口函数

实现:
  → WindowTransform 处理窗口函数
  → 支持 ROWS / RANGE / GROUPS 帧
  → 支持滑动窗口 (ROWS BETWEEN ... AND ...)

窗口函数类型:
  排名函数: row_number, rank, dense_rank, percent_rank, ntile
  聚合函数: sum, count, avg, min, max (带 OVER 子句)
  偏移函数: lag, lead, first_value, last_value, nth_value
```

### 窗口函数与聚合的区别

```
聚合: 多行 → 一行
  GROUP BY user_id → 每个 user_id 一行

窗口: 多行 → 多行（每行都有窗口计算结果）
  PARTITION BY user_id → 每个 user_id 的行保留，附加计算值

QueryPlan 中的差异:
  聚合: AggregatingStep → 行数减少
  窗口: WindowStep → 行数不变，增加列
```

## 5.6 排序规划

`src/Planner/PlannerSorting.h` — 排序的多种优化路径：

### 排序优化策略

```
策略 1: 利用主键顺序 (InOrder Read)
  ORDER BY 主键 → 不需要 SortingStep
  → ReadFromMergeTree 使用 InOrder 模式

策略 2: 利用 MergeTree 的数据有序性
  ORDER BY 部分主键前缀 → PartialSort (k-way merge)
  → 每个 Part 内部已有序 → 只需归并

策略 3: TopN 优化
  ORDER BY x LIMIT n → 使用 PartialSortingStep
  → 维护大小为 n 的堆，避免完整排序

策略 4: 完整排序
  SortingStep → 内部使用 RadixSort / LSDSort / QuickSort
  → 根据数据类型选择最优排序算法
```

### LIMIT 优化

```
SELECT * FROM t ORDER BY date LIMIT 10

无优化: 全量排序 100 万行 → 取前 10 行
优化后: PartialSortingStep → 只维护前 10 行的堆 → O(N * log(10))

进一步优化:
  + 读到足够行后提前终止 (ReadWithLimit)
  + 利用索引的有序性避免排序
```

## 5.7 Join Reorder：CBO 优化框架

这是 ClickHouse 近期最重要的内核进展之一。实现在 `src/Processors/QueryPlan/Optimizations/joinOrder.cpp`（867 行）。

### QueryGraph：连接图

```cpp
// src/Processors/QueryPlan/Optimizations/joinOrder.h:57-86
struct QueryGraph
{
    std::vector<RelationStats> relation_stats;          // 表统计信息
    std::vector<JoinActionRef> edges;                   // 连接边（等值条件）
    std::unordered_map<size_t, std::pair<BitSet, JoinKind>> join_kinds;  // JOIN 类型约束
    std::unordered_map<JoinActionRef, size_t> pinned;   // 固定谓词（OUTER JOIN ON 子句）
    EquivalenceClasses<JoinActionRef> column_equivalences; // 列等价类
};
```

### DPJoinEntry：DP 表条目

```cpp
struct DPJoinEntry
{
    BitSet relations;                    // 包含的关系集合（位图）
    DPJoinEntryPtr left, right;          // 子计划
    double cost = 0.0;                   // 代价
    std::optional<UInt64> estimated_rows; // 估计行数
    std::unordered_map<String, ColumnStats> column_stats; // 列统计
    JoinOperator join_operator;          // JOIN 操作符
    JoinMethod join_method = JoinMethod::Hash; // JOIN 方法
    int relation_id = -1;                // 叶节点 ID
};
```

### 代价模型

```cpp
// joinOrder.cpp:476-482 — 代价计算
double computeJoinCost(DPJoinEntryPtr left, DPJoinEntryPtr right, double selectivity)
{
    return left->cost + right->cost
         + selectivity * left->estimated_rows * right->estimated_rows;
}

// joinOrder.cpp:445-474 — 基数估计
UInt64 estimateJoinCardinality(DPJoinEntryPtr left, DPJoinEntryPtr right,
    double selectivity, JoinKind kind)
{
    double joined = selectivity * left_rows * right_rows;
    if (kind == Left)  joined = max(joined, left_rows);
    if (kind == Right) joined = max(joined, right_rows);
    if (kind == Full)  joined = max(joined, left_rows + right_rows);
}
```

### 选择率估算

```cpp
// joinOrder.cpp:364-382 — 基于 NDV 的选择率
double computeSelectivity(const JoinActionRef & edge)
{
    UInt64 lhs_ndv = getColumnStats(lhs.getSourceRelations(), lhs.getColumnName());
    UInt64 rhs_ndv = getColumnStats(rhs.getSourceRelations(), rhs.getColumnName());
    UInt64 max_ndv = max(lhs_ndv, rhs_ndv);
    if (max_ndv > 0)
        selectivity = 1.0 / max_ndv;  // 经典选择率公式
}
```

### DPsize 算法

```cpp
// joinOrder.cpp:681-792 — 动态规划枚举
DPJoinEntryPtr solveDPsize()
{
    // 按 component_size 从 2 到 N 迭代
    for (size_t size = 2; size <= total_relations; ++size)
    {
        // 枚举所有左右子集划分
        for (size_t left_size = 1; left_size <= size/2; ++left_size)
        {
            for (auto & [_, left] : components[left_size])
            {
                for (auto & [_, right] : components[size - left_size])
                {
                    if (!isValidJoinOrder(left, right)) continue;
                    if (!connected(left, right)) continue;

                    auto cost = computeJoinCost(left, right, selectivity);
                    if (cost < dp_table[combined].cost)
                        dp_table[combined] = new_best_plan;
                }
            }
        }
    }
    return dp_table[full_set];  // 返回全局最优
}
```

**限制**：`APPLY_DP_THRESHOLD = 10` — 超过 10 张表时回退到贪心算法，因为 DP 的搜索空间是 2^n。

### Greedy 算法

```cpp
// joinOrder.cpp:553-671 — 贪心算法
DPJoinEntryPtr solveGreedy()
{
    std::deque<DPJoinEntryPtr> components = {all_leaf_relations};

    while (components.size() > 1)
    {
        // 贪心：找代价最小的两两 JOIN
        DPJoinEntryPtr best_plan = nullptr;
        for (i, j in all_pairs)
        {
            if (!isValidJoinOrder(left, right)) continue;
            auto cost = computeJoinCost(left, right, selectivity);
            if (cost < best_plan.cost)
                best_plan = {left, right, cost};
        }

        // 无连通 JOIN 时：最小笛卡尔积
        if (!best_plan)
            best_plan = cross_product(smallest_two);

        // 替换两个组件为合并后的组件
        components.erase(i, j);
        components.push_front(best_plan);
    }
}
```

### 列等价类与传递谓词

```cpp
// joinOrder.cpp:114-148 — 构建列等价类
void QueryGraph::buildColumnEquivalences()
{
    for (auto & edge : edges)
    {
        auto [op, lhs, rhs] = edge.asBinaryPredicate();
        if (op != Equals) continue;

        // OUTER JOIN 的等值条件不传播（因为 NULL 行破坏传递性）
        if (isOuter(lhs_rel) || isOuter(rhs_rel)) continue;

        column_equivalences.add(lhs, rhs);
    }
}
```

```cpp
// joinOrder.cpp:181-276 — 冗余谓词清理 + 传递谓词合成
void cleanupJoinPredicates(DPJoinEntryPtr root, const EquivalenceClasses & equiv)
{
    // Phase 1: 移除冗余谓词（已被等价类覆盖的）
    std::erase_if(expressions, [&](auto & pred) {
        return equiv.getClass(lhs) == equiv.getClass(rhs);
    });

    // Phase 2: 为纯传递性 JOIN 合成谓词
    if (expressions.empty() && isInner(join_kind))
    {
        // 找到跨越左右子树的等价类，合成 A.x = C.x
        for (auto & [member, _] : column_equivalences)
            if (member in left && equivalent in right)
                expressions.push_back(member = equivalent);
    }
}
```

### 外连接约束

```cpp
// joinOrder.cpp:794-842 — JOIN 类型约束检查
std::optional<JoinKind> isValidJoinOrder(BitSet left, BitSet right) const
{
    // LEFT JOIN 的左表不能被重排到右侧
    // FROM t1 LEFT JOIN t2 LEFT JOIN t3
    //   → (t2 JOIN t3) 不合法
    //   → (t1 JOIN t3) LEFT JOIN t2 合法

    // FULL JOIN：仅允许交换表顺序，不可与第三表重排
    if (left_type == Full && right_type == Full)
        return Full;

    return {}; // 冲突
}
```

### 设置

| Setting | Default | 状态 |
|---------|---------|------|
| `query_plan_optimize_join_order_algorithm` | `"greedy"` | Stable |
| `query_plan_optimize_join_order_limit` | `10` | Stable |
| `enable_join_transitive_predicates` | `false` | **EXPERIMENTAL** |
| `use_hash_table_stats_for_join_reordering` | `true` | Stable |

### Join Reorder 完整流程

```
QueryTree (Analyzer v2 输出)
  │
  ├── PlannerJoinsLogical::plan()
  │     ├── 提取 JoinNode → 构建 QueryGraph
  │     │     ├── relation_stats: 每张表的行数和列统计
  │     │     ├── edges: 等值连接条件
  │     │     ├── join_kinds: JOIN 类型约束
  │     │     └── pinned: OUTER JOIN 固定谓词
  │     │
  │     ├── buildColumnEquivalences() → 列等价类
  │     │
  │     └── optimizeJoinOrder()
  │           ├── solveDPsize() (≤10 张表)
  │           │     └── 2^n 空间枚举，找最小代价
  │           └── solveGreedy() (>10 张表)
  │                 └── 每步贪心选最小代价对
  │
  ├── cleanupJoinPredicates()
  │     ├── 移除冗余谓词
  │     └── 合成传递谓词
  │
  └── 生成 JoinStep → 加入 QueryPlan
```

> **侧边栏 · 与 StarRocks CBO 对比**：StarRocks 使用 DP + Genetic Algorithm 的混合策略，支持更多表（30+），并使用直方图进行选择率估算。ClickHouse 的 CBO 框架更轻量：NDV-based 选择率、DP 上限 10 表、Greedy 兜底。这是务实的选择——ClickHouse 的典型查询中 JOIN 表数通常 < 10，而精确选择率需要 ANALYZE TABLE 收集直方图（ClickHouse 的统计收集还在早期阶段）。

> **侧边栏 · 与 MaxCompute 对比**：MaxCompute 的 CBO 基于 Volcano/Cascades 框架，支持 Top-Down 记忆搜索和属性强制（Enforcer）。ClickHouse 的 DPsize 是 Bottom-Up 枚举，不支持属性强制（如强制排序顺序），但实现更简单直接。

## 5.8 QueryPlanOptimizer

在 Planner 生成初始 QueryPlan 后，`QueryPlanOptimizer` 执行物理层优化：

```
src/Processors/QueryPlan/Optimizations/
├── joinOrder.cpp          → Join Reorder CBO
├── pushPredicateDown.cpp  → 谓词下推
├── aggregateProjection.cpp → 聚合投影优化
├── countStarPartition.cpp → COUNT(*) 分区优化
├── crossToInnerJoin.cpp   → 笛卡尔积转 INNER JOIN
├── distinctOrder.cpp      → DISTINCT + ORDER BY 优化
├── distinctSimulation.cpp → DISTINCT 模拟优化
├── fuseSorting.cpp        → 排序融合
├── optimizeProjection.cpp → 投影优化
├── readInOrder.cpp        → 按序读取优化
├── repeatTailOptimization.cpp → REPEAT 尾部优化
└── ...
```

### 谓词下推

```
原始 Plan:
  FilterStep(x > 10) → JoinStep(t1, t2) → ...

优化后:
  JoinStep(
    FilterStep(t1, t1.x > 10),  ← 谓词下推到 Join 左侧
    t2
  ) → ...

效果:
  减少进入 Join 的行数 → 减少 Hash Table 大小 → 更快
```

### 投影优化

```
原始 Plan:
  ReadFromMergeTree(所有列) → FilterStep → AggregatingStep(sum(x))

优化后:
  ReadFromMergeTree(只读 x 列) → FilterStep → AggregatingStep(sum(x))

效果:
  不读取不需要的列 → 减少 I/O
  列裁剪在 ReadFromMergeTree Step 内部执行
```

### 按序读取优化

```
原始 Plan:
  ReadFromMergeTree(Default) → SortingStep(date)

优化后:
  ReadFromMergeTree(InOrder) → (不需要 SortingStep)

条件:
  ORDER BY 列 = 主键前缀
  → 利用 MergeTree 的物理有序性
```

### DISTINCT 优化

```
优化 1: DISTINCT + ORDER BY
  SELECT DISTINCT a FROM t ORDER BY a
  → 合并为 SortingStep（DISTINCT 等价于排序后去重）

优化 2: DISTINCT 模拟
  SELECT DISTINCT a, b FROM t
  → 转换为 GROUP BY a, b
  → 可以利用两阶段聚合
```

## 5.9 EXPLAIN 查询

```sql
-- 查看 QueryPlan
EXPLAIN SELECT a, count() FROM t GROUP BY a

-- 查看 Pipeline
EXPLAIN PIPELINE SELECT a, count() FROM t GROUP BY a

-- 查看 QueryTree
EXPLAIN QUERY TREE SELECT a, count() FROM t GROUP BY a

-- 查看语法树
EXPLAIN SYNTAX SELECT a, count() FROM t GROUP BY a

-- 查看执行计划（包含索引裁剪信息）
EXPLAIN PLAN SELECT a FROM t WHERE date = '2024-01-01'
```

## 5.10 本章小结

Planner 的核心架构：

```
QueryTree → Planner → QueryPlan → QueryPlanOptimizer → Optimized QueryPlan
                │
                ├── 聚合规划 (两阶段聚合, 分布式聚合)
                ├── 窗口函数规划 (PARTITION BY + ORDER BY)
                ├── 排序规划 (InOrder/PartialSort/TopN/FullSort)
                ├── Join Reorder CBO (DPsize + Greedy)
                ├── 谓词下推
                ├── 投影优化
                └── 排序/聚合优化
```

**关键设计决策**：
- **声明式 QueryPlan Step** — 每个 Step 只描述"做什么"，不描述"怎么做"
- **CBO Join Reorder** — NDV-based 代价模型 + DP/Greedy 双算法 + 列等价类传递
- **两阶段优化** — QueryTree Pass（逻辑优化） + QueryPlan Optimization（物理优化）
- **多种排序策略** — 根据查询特征选择最优排序路径

**关键文件地图**：
```
src/Planner/Planner.h                              → Planner 主入口
src/Planner/PlannerJoinsLogical.h                  → JOIN 规划
src/Planner/PlannerAggregation.h                   → 聚合规划
src/Planner/PlannerSorting.h                       → 排序规划
src/Planner/PlannerWindowFunctions.h               → 窗口函数规划
src/Processors/QueryPlan/QueryPlan.h               → QueryPlan 定义
src/Processors/QueryPlan/Optimizations/joinOrder.cpp → Join Reorder 核心
src/Processors/QueryPlan/Optimizations/             → 物理优化集合
```
