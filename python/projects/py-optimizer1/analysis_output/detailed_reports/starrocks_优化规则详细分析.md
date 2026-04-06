# StarRocks 优化规则详细分析报告

> **生成时间:** 2026-04-06 12:18:01

> **分析源码路径:** `/home/lism/work/starrocks`

> **规则总数:** 269

## 📊 一、规则统计总览

### 1.1 规则分类统计

| 规则类型 | 数量 | 占比 |
|----------|------|------|

| 其他规则 | 128 | 47.6% |
| RBO | 54 | 20.1% |
| 重写规则 | 42 | 15.6% |
| 实现规则 | 41 | 15.2% |
| Implementation | 2 | 0.7% |
| 转换规则 | 1 | 0.4% |
| 表达式规则 | 1 | 0.4% |
| **总计** | **269** | **100%** |

### 1.2 关系代数符号说明


| 符号 | 名称 | 含义 |
|------|------|------|
| σ | Sigma | 选择操作，筛选满足条件的行 |
| π | Pi | 投影操作，选择特定列 |
| ⋈ | Join | 连接操作，连接两个关系 |
| × | Cartesian | 笛卡尔积 |
| γ | Gamma | 聚合操作，分组和计算 |
| τ | Tau | 排序操作 |
| ∪ | Union | 并集 |
| ∩ | Intersect | 交集 |
| → | Arrow | 转换为 |


## 📚 二、规则详细分析


### 2.1 转换规则 (Transformation)

> 共 224 条规则


#### 2.1.1 `PushDownLimitCTEAnchor`

**功能描述:** 将Limit操作下推到数据源

**优化目标:** 减少数据传输

---

#### 2.1.2 `MultiDistinctByMultiFuncRewriter`

**中文名称:** MultiDistinctByMultiFunc重写r

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 查询重写优化

---

#### 2.1.3 `PruneValuesColumnsRule`

**功能描述:** 移除查询中不需要的列

**优化目标:** 减少数据传输量

---

#### 2.1.4 `ConvertToEqualForNullRule`

**中文名称:** ConvertToEqualForNull

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.5 `PushDownPredicateAggRule`

**功能描述:** 将过滤条件尽可能下推到数据源附近，减少中间结果集大小

**优化目标:** 减少连接前的数据量


**优化示例:**
```sql
SELECT * FROM orders JOIN customers ON o_id = c_id WHERE c_status = 'active' → 先过滤customers再连接
```

---

#### 2.1.6 `PushDownPredicateSetRule`

**功能描述:** 将过滤条件尽可能下推到数据源附近，减少中间结果集大小

**优化目标:** 减少连接前的数据量


**优化示例:**
```sql
SELECT * FROM orders JOIN customers ON o_id = c_id WHERE c_status = 'active' → 先过滤customers再连接
```

---

#### 2.1.7 `PushDownApplyLeftRule`

**中文名称:** 下推ApplyLeft

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.8 `PruneProjectEmptyRule`

**中文名称:** 裁剪投影Empty

**关系代数表达:**
```
π_{A}(R) → π_{A'}(R) where A' ⊆ A
```

---

#### 2.1.9 `does`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.10 `PruneTableFunctionColumnRule`

**功能描述:** 移除查询中不需要的列

**优化目标:** 减少数据传输量

---

#### 2.1.11 `PruneUKFKJoinRule`

**中文名称:** 裁剪UKFK连接

**关系代数表达:**
```
π_{A}(R) → π_{A'}(R) where A' ⊆ A
```

**依赖资源:** 物理属性

---

#### 2.1.12 `JoinCommutativityRule`

**中文名称:** 连接Commutativity

**关系代数表达:**
```
(R ⋈ S) ⋈ T → R ⋈ (S ⋈ T)
```

**依赖资源:** 物理属性

---

#### 2.1.13 `ForceCTEReuseRule`

**中文名称:** ForceCTEReuse

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.14 `PruneEmptyExceptRule`

**中文名称:** 裁剪Empty差集

**关系代数表达:**
```
π_{A}(R) → π_{A'}(R) where A' ⊆ A
```

---

#### 2.1.15 `RewriteToVectorPlanRule`

**中文名称:** 重写ToVectorPlan

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 查询重写优化

---

#### 2.1.16 `ScalarApplyNormalizeCountRule`

**中文名称:** ScalarApplyNormalizeCount

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.17 `PruneFilterColumnsRule`

**功能描述:** 移除查询中不需要的列

**优化目标:** 减少数据传输量

---

#### 2.1.18 `JoinLeftAsscomRule`

**中文名称:** 连接LeftAsscom

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.1.19 `PushDownJoinAggRule`

**中文名称:** 下推连接Agg

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.20 `CombinationRule`

**中文名称:** Combination

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.21 `GroupByCountDistinctDataSkewEliminateRule`

**中文名称:** GroupByCountDistinctDataSkew消除

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 代价模型

---

#### 2.1.22 `UnionToValuesRule`

**中文名称:** UnionToValues

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.1.23 `PushDownTopNBelowOuterJoinRule`

**功能描述:** 将排序+Limit转换为TopN操作

**优化目标:** 避免全排序，使用堆获取TopN

---

#### 2.1.24 `CTEProduceAddProjectionRule`

**中文名称:** CTEProduceAdd投影ion

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.25 `RewriteCountIfFunction`

**中文名称:** 重写CountIfFunction

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 查询重写优化

---

#### 2.1.26 `need`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.27 `PushDownPredicateRankingWindowRule`

**功能描述:** 将过滤条件尽可能下推到数据源附近，减少中间结果集大小

**优化目标:** 减少连接前的数据量


**优化示例:**
```sql
SELECT * FROM orders JOIN customers ON o_id = c_id WHERE c_status = 'active' → 先过滤customers再连接
```

---

#### 2.1.28 `CollectCTEConsumeRule`

**中文名称:** CollectCTEConsume

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.29 `EliminateGroupByConstantRule`

**中文名称:** 消除GroupBy常量

**关系代数表达:**
```
expr(const) → const_value
```

---

#### 2.1.30 `RewriteBitmapCountDistinctRule`

**中文名称:** 重写BitmapCountDistinct

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 查询重写优化

---

#### 2.1.31 `PushDownPredicateJoinRule`

**功能描述:** 将过滤条件尽可能下推到数据源附近，减少中间结果集大小

**优化目标:** 减少连接前的数据量


**优化示例:**
```sql
SELECT * FROM orders JOIN customers ON o_id = c_id WHERE c_status = 'active' → 先过滤customers再连接
```

---

#### 2.1.32 `GroupByCountDistinctRewriteRule`

**中文名称:** GroupByCountDistinct重写

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 查询重写优化

---

#### 2.1.33 `MergeTwoFiltersRule`

**中文名称:** 合并Two过滤s

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.34 `PruneCTEConsumeColumnsRule`

**功能描述:** 移除查询中不需要的列

**优化目标:** 减少数据传输量

---

#### 2.1.35 `ListPartitionPruner`

**中文名称:** ListPartition裁剪r

**关系代数表达:**
```
π_{A}(R) → π_{A'}(R) where A' ⊆ A
```

---

#### 2.1.36 `PushDownPredicateCTEAnchor`

**功能描述:** 将过滤条件尽可能下推到数据源附近，减少中间结果集大小

**优化目标:** 减少连接前的数据量


**优化示例:**
```sql
SELECT * FROM orders JOIN customers ON o_id = c_id WHERE c_status = 'active' → 先过滤customers再连接
```

---

#### 2.1.37 `PruneUKFKGroupByKeysRule`

**中文名称:** 裁剪UKFKGroupByKeys

**关系代数表达:**
```
π_{A}(R) → π_{A'}(R) where A' ⊆ A
```

---

#### 2.1.38 `SplitLimitRule`

**功能描述:** 将Limit操作下推到数据源

**优化目标:** 减少数据传输

---

#### 2.1.39 `EliminateJoinWithConstantRule`

**中文名称:** 消除连接With常量

**关系代数表达:**
```
expr(const) → const_value
```

---

#### 2.1.40 `PruneProjectRule`

**中文名称:** 裁剪投影

**关系代数表达:**
```
π_{A}(R) → π_{A'}(R) where A' ⊆ A
```

---

#### 2.1.41 `SeparateProjectRule`

**中文名称:** Separate投影

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 统计信息

---

#### 2.1.42 `PruneEmptyIntersectRule`

**中文名称:** 裁剪Empty交集

**关系代数表达:**
```
π_{A}(R) → π_{A'}(R) where A' ⊆ A
```

---

#### 2.1.43 `PushDownJoinOnExpressionToChildProject`

**功能描述:** 将投影操作下推，只读取需要的列

**优化目标:** 减少列扫描，降低IO和内存

---

#### 2.1.44 `ExternalScanPartitionPruneRule`

**中文名称:** External扫描Partition裁剪

**关系代数表达:**
```
π_{A}(R) → π_{A'}(R) where A' ⊆ A
```

---

#### 2.1.45 `EliminateLimitZeroRule`

**功能描述:** 将Limit操作下推到数据源

**优化目标:** 减少数据传输

---

#### 2.1.46 `ExistentialApply2JoinRule`

**中文名称:** ExistentialApply2连接

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.47 `PruneEmptyUnionRule`

**中文名称:** 裁剪EmptyUnion

**关系代数表达:**
```
π_{A}(R) → π_{A'}(R) where A' ⊆ A
```

---

#### 2.1.48 `MultiDistinctByCTERewriter`

**中文名称:** MultiDistinctByCTE重写r

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 查询重写优化

---

#### 2.1.49 `QuantifiedApply2JoinRule`

**中文名称:** QuantifiedApply2连接

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.50 `RewriteSumByAssociativeRule`

**中文名称:** 重写SumByAssociative

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 查询重写优化

---

#### 2.1.51 `PushDownPredicateCTEConsumeRule`

**功能描述:** 将过滤条件尽可能下推到数据源附近，减少中间结果集大小

**优化目标:** 减少连接前的数据量


**优化示例:**
```sql
SELECT * FROM orders JOIN customers ON o_id = c_id WHERE c_status = 'active' → 先过滤customers再连接
```

---

#### 2.1.52 `SplitMultiPhaseAggRule`

**中文名称:** SplitMultiPhaseAgg

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 统计信息, 物理属性

---

#### 2.1.53 `EliminateConstantCTERule`

**中文名称:** 消除常量CTE

**关系代数表达:**
```
expr(const) → const_value
```

---

#### 2.1.54 `MergeProjectWithChildRule`

**中文名称:** 合并投影WithChild

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.55 `PushDownApplyFilterRule`

**中文名称:** 下推Apply过滤

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.56 `QuantifiedApply2OuterJoinRule`

**中文名称:** QuantifiedApply2Outer连接

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.1.57 `PushDownLimitDirectRule`

**功能描述:** 将Limit操作下推到数据源

**优化目标:** 减少数据传输

---

#### 2.1.58 `PushDownPredicateExceptRule`

**功能描述:** 将过滤条件尽可能下推到数据源附近，减少中间结果集大小

**优化目标:** 减少连接前的数据量


**优化示例:**
```sql
SELECT * FROM orders JOIN customers ON o_id = c_id WHERE c_status = 'active' → 先过滤customers再连接
```

---

#### 2.1.59 `PruneTopNColumnsRule`

**功能描述:** 移除查询中不需要的列

**优化目标:** 减少数据传输量

---

#### 2.1.60 `PushDownPredicateToExternalTableScanRule`

**功能描述:** 将过滤条件尽可能下推到数据源附近，减少中间结果集大小

**优化目标:** 减少连接前的数据量


**优化示例:**
```sql
SELECT * FROM orders JOIN customers ON o_id = c_id WHERE c_status = 'active' → 先过滤customers再连接
```

---

#### 2.1.61 `RewriteDuplicateAggregateFnRule`

**中文名称:** 重写Duplicate聚合Fn

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 查询重写优化

---

#### 2.1.62 `PruneEmptyWindowRule`

**中文名称:** 裁剪EmptyWindow

**关系代数表达:**
```
π_{A}(R) → π_{A'}(R) where A' ⊆ A
```

---

#### 2.1.63 `SplitTopNRule`

**功能描述:** 将排序+Limit转换为TopN操作

**优化目标:** 避免全排序，使用堆获取TopN

---

#### 2.1.64 `PruneTrueFilterRule`

**中文名称:** 裁剪True过滤

**关系代数表达:**
```
π_{A}(R) → π_{A'}(R) where A' ⊆ A
```

---

#### 2.1.65 `PruneEmptyScanRule`

**中文名称:** 裁剪Empty扫描

**关系代数表达:**
```
π_{A}(R) → π_{A'}(R) where A' ⊆ A
```

---

#### 2.1.66 `ScalarApply2JoinRule`

**中文名称:** ScalarApply2连接

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.67 `RewriteSimpleAggToMetaScanRule`

**中文名称:** 重写SimpleAggToMeta扫描

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 查询重写优化

---

#### 2.1.68 `ArrayDistinctAfterAggRule`

**中文名称:** ArrayDistinctAfterAgg

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.69 `PushDownPredicateIntersectRule`

**功能描述:** 将过滤条件尽可能下推到数据源附近，减少中间结果集大小

**优化目标:** 减少连接前的数据量


**优化示例:**
```sql
SELECT * FROM orders JOIN customers ON o_id = c_id WHERE c_status = 'active' → 先过滤customers再连接
```

---

#### 2.1.70 `TransformationRule`

**中文名称:** 转换ation

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 逻辑等价变换，生成备选执行计划

---

#### 2.1.71 `HoistHeavyCostExprsUponTopnRule`

**功能描述:** 将排序+Limit转换为TopN操作

**优化目标:** 避免全排序，使用堆获取TopN

---

#### 2.1.72 `MergeLimitWithSortRule`

**功能描述:** 将Limit操作下推到数据源

**优化目标:** 减少数据传输

---

#### 2.1.73 `MergeApplyWithTableFunction`

**中文名称:** 合并ApplyWithTableFunction

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.74 `SplitAggregateRule`

**中文名称:** Split聚合

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 统计信息

---

#### 2.1.75 `RewriteGroupingSetsByCTERule`

**中文名称:** 重写GroupingSetsByCTE

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 查询重写优化

---

#### 2.1.76 `PruneProjectColumnsRule`

**功能描述:** 移除查询中不需要的列

**优化目标:** 减少数据传输量

---

#### 2.1.77 `LimitPruneTabletsRule`

**功能描述:** 将Limit操作下推到数据源

**优化目标:** 减少数据传输

---

#### 2.1.78 `PushDownAggregateGroupingSetsRule`

**中文名称:** 下推聚合GroupingSets

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 统计信息

---

#### 2.1.79 `EliminateAggRule`

**中文名称:** 消除Agg

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.80 `DeriveRangeJoinPredicateRule`

**中文名称:** DeriveRange连接谓词

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 统计信息

---

#### 2.1.81 `PushDownFlatJsonMetaToMetaScanRule`

**中文名称:** 下推FlatJsonMetaToMeta扫描

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.82 `MergeLimitWithLimitRule`

**功能描述:** 将Limit操作下推到数据源

**优化目标:** 减少数据传输

---

#### 2.1.83 `PruneAggregateColumnsRule`

**功能描述:** 移除查询中不需要的列

**优化目标:** 减少数据传输量

---

#### 2.1.84 `PushDownPredicateWindowRule`

**功能描述:** 将过滤条件尽可能下推到数据源附近，减少中间结果集大小

**优化目标:** 减少连接前的数据量


**优化示例:**
```sql
SELECT * FROM orders JOIN customers ON o_id = c_id WHERE c_status = 'active' → 先过滤customers再连接
```

---

#### 2.1.85 `EliminateSortColumnWithEqualityPredicateRule`

**中文名称:** 消除排序ColumnWithEquality谓词

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.86 `MaterializedViewTransparentRewriteRule`

**中文名称:** MaterializedViewTransparent重写

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 查询重写优化

**依赖资源:** 物理属性

---

#### 2.1.87 `PushDownLimitJoinRule`

**功能描述:** 将Limit操作下推到数据源

**优化目标:** 减少数据传输

---

#### 2.1.88 `PushDownProjectLimitRule`

**功能描述:** 将投影操作下推，只读取需要的列

**优化目标:** 减少列扫描，降低IO和内存

---

#### 2.1.89 `SplitJoinORToUnionRule`

**中文名称:** Split连接ORToUnion

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.90 `CastToEmptyRule`

**中文名称:** CastToEmpty

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.91 `ReorderIntersectRule`

**中文名称:** 重排序交集

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 统计信息

---

#### 2.1.92 `JoinCommutativityWithoutInnerRule`

**中文名称:** 连接CommutativityWithoutInner

**关系代数表达:**
```
(R ⋈ S) ⋈ T → R ⋈ (S ⋈ T)
```

---

#### 2.1.93 `CollectCTEProduceRule`

**中文名称:** CollectCTEProduce

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.94 `RewriteUnnestBitmapRule`

**中文名称:** 重写UnnestBitmap

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 查询重写优化

---

#### 2.1.95 `IntersectAddDistinctRule`

**中文名称:** 交集AddDistinct

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 统计信息

---

#### 2.1.96 `LargeInPredicateToJoinRule`

**中文名称:** LargeIn谓词To连接

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 代价模型

---

#### 2.1.97 `SemiReorderRule`

**中文名称:** Semi重排序

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.98 `PushLimitAndFilterToCTEProduceRule`

**功能描述:** 将Limit操作下推到数据源

**优化目标:** 减少数据传输

---

#### 2.1.99 `MergeTwoAggRule`

**中文名称:** 合并TwoAgg

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.100 `PushDownApplyAggProjectFilterRule`

**功能描述:** 将投影操作下推，只读取需要的列

**优化目标:** 减少列扫描，降低IO和内存

---

#### 2.1.101 `SplitTwoPhaseAggRule`

**中文名称:** SplitTwoPhaseAgg

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.1.102 `PruneWindowColumnsRule`

**功能描述:** 移除查询中不需要的列

**优化目标:** 减少数据传输量

---

#### 2.1.103 `PushDownProjectToCTEAnchorRule`

**功能描述:** 将投影操作下推，只读取需要的列

**优化目标:** 减少列扫描，降低IO和内存

---

#### 2.1.104 `PruneExceptColumnsRule`

**功能描述:** 移除查询中不需要的列

**优化目标:** 减少数据传输量

---

#### 2.1.105 `PushDownLimitRankingWindowRule`

**功能描述:** 将Limit操作下推到数据源

**优化目标:** 减少数据传输

---

#### 2.1.106 `PruneScanColumnRule`

**功能描述:** 移除查询中不需要的列

**优化目标:** 减少数据传输量

---

#### 2.1.107 `MinMaxOptOnScanRule`

**中文名称:** MinMaxOptOn扫描

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.108 `PruneGroupByKeysRule`

**中文名称:** 裁剪GroupByKeys

**关系代数表达:**
```
π_{A}(R) → π_{A'}(R) where A' ⊆ A
```

---

#### 2.1.109 `ScalarApply2AnalyticRule`

**中文名称:** ScalarApply2Analytic

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.110 `PruneRepeatColumnsRule`

**功能描述:** 移除查询中不需要的列

**优化目标:** 减少数据传输量

---

#### 2.1.111 `MergeLimitDirectRule`

**功能描述:** 将Limit操作下推到数据源

**优化目标:** 减少数据传输

---

#### 2.1.112 `SplitScanORToUnionRule`

**中文名称:** Split扫描ORToUnion

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 统计信息

---

#### 2.1.113 `ApplyExceptionRule`

**中文名称:** Apply差集ion

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.114 `PushDownPredicateRepeatRule`

**功能描述:** 将过滤条件尽可能下推到数据源附近，减少中间结果集大小

**优化目标:** 减少连接前的数据量


**优化示例:**
```sql
SELECT * FROM orders JOIN customers ON o_id = c_id WHERE c_status = 'active' → 先过滤customers再连接
```

---

#### 2.1.115 `PruneJoinColumnsRule`

**功能描述:** 移除查询中不需要的列

**优化目标:** 减少数据传输量

---

#### 2.1.116 `PushDownAggToMetaScanRule`

**中文名称:** 下推AggToMeta扫描

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.117 `SkewJoinOptimizeRule`

**中文名称:** Skew连接Optimize

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 统计信息

---

#### 2.1.118 `IcebergPartitionsTableRewriteRule`

**中文名称:** IcebergPartitionsTable重写

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 查询重写优化

---

#### 2.1.119 `JoinAssociateBaseRule`

**中文名称:** 连接AssociateBase

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.120 `PullUpScanPredicateRule`

**中文名称:** PullUp扫描谓词

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.121 `PushDownJoinOnClauseRule`

**中文名称:** 下推连接OnClause

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.122 `MergeTwoProjectRule`

**中文名称:** 合并Two投影

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.123 `RewriteHllCountDistinctRule`

**中文名称:** 重写HllCountDistinct

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 查询重写优化

---

#### 2.1.124 `EliminateAggFunctionRule`

**中文名称:** 消除AggFunction

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.125 `PruneEmptyJoinRule`

**中文名称:** 裁剪Empty连接

**关系代数表达:**
```
π_{A}(R) → π_{A'}(R) where A' ⊆ A
```

---

#### 2.1.126 `InlineOneCTEConsumeRule`

**中文名称:** InlineOneCTEConsume

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.127 `PushDownPredicateTableFunctionRule`

**功能描述:** 将过滤条件尽可能下推到数据源附近，减少中间结果集大小

**优化目标:** 减少连接前的数据量


**优化示例:**
```sql
SELECT * FROM orders JOIN customers ON o_id = c_id WHERE c_status = 'active' → 先过滤customers再连接
```

---

#### 2.1.128 `PruneEmptyDirectRule`

**中文名称:** 裁剪EmptyDirect

**关系代数表达:**
```
π_{A}(R) → π_{A'}(R) where A' ⊆ A
```

---

#### 2.1.129 `RewriteMultiDistinctRule`

**中文名称:** 重写MultiDistinct

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 查询重写优化

**依赖资源:** 统计信息, 物理属性

---

#### 2.1.130 `PruneIntersectColumnsRule`

**功能描述:** 移除查询中不需要的列

**优化目标:** 减少数据传输量

---

#### 2.1.131 `PushDownTopNBelowUnionRule`

**功能描述:** 将排序+Limit转换为TopN操作

**优化目标:** 避免全排序，使用堆获取TopN

---

#### 2.1.132 `PartitionColumnValueOnlyOnScanRule`

**中文名称:** PartitionColumnValueOnlyOn扫描

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.133 `PushDownLimitUnionRule`

**功能描述:** 将Limit操作下推到数据源

**优化目标:** 减少数据传输

---

#### 2.1.134 `ExistentialApply2OuterJoinRule`

**中文名称:** ExistentialApply2Outer连接

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.135 `RewriteSimpleAggToHDFSScanRule`

**中文名称:** 重写SimpleAggToHDFS扫描

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 查询重写优化

---

#### 2.1.136 `PruneHDFSScanColumnRule`

**功能描述:** 移除查询中不需要的列

**优化目标:** 减少数据传输量

---

#### 2.1.137 `SchemaTableEvaluateRule`

**中文名称:** SchemaTableEvaluate

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.138 `IcebergEqualityDeleteRewriteRule`

**中文名称:** IcebergEqualityDelete重写

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 查询重写优化

---

#### 2.1.139 `FineGrainedRangePredicateRule`

**中文名称:** FineGrainedRange谓词

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.140 `JoinAssociativityRule`

**中文名称:** 连接Associativity

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.1.141 `RemoveAggregationFromAggTable`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.142 `PushDownPredicateProjectRule`

**功能描述:** 将过滤条件尽可能下推到数据源附近，减少中间结果集大小

**优化目标:** 减少连接前的数据量


**优化示例:**
```sql
SELECT * FROM orders JOIN customers ON o_id = c_id WHERE c_status = 'active' → 先过滤customers再连接
```

---

#### 2.1.143 `PushDownPredicateUnionRule`

**功能描述:** 将过滤条件尽可能下推到数据源附近，减少中间结果集大小

**优化目标:** 减少连接前的数据量


**优化示例:**
```sql
SELECT * FROM orders JOIN customers ON o_id = c_id WHERE c_status = 'active' → 先过滤customers再连接
```

---

#### 2.1.144 `PushDownPredicateScanRule`

**功能描述:** 将过滤条件尽可能下推到数据源附近，减少中间结果集大小

**优化目标:** 减少连接前的数据量


**优化示例:**
```sql
SELECT * FROM orders JOIN customers ON o_id = c_id WHERE c_status = 'active' → 先过滤customers再连接
```

---

#### 2.1.145 `PruneUnionColumnsRule`

**功能描述:** 移除查询中不需要的列

**优化目标:** 减少数据传输量

---

#### 2.1.146 `PushDownApplyLeftProjectRule`

**功能描述:** 将投影操作下推，只读取需要的列

**优化目标:** 减少列扫描，降低IO和内存

---

#### 2.1.147 `PushDownApplyProjectRule`

**功能描述:** 将投影操作下推，只读取需要的列

**优化目标:** 减少列扫描，降低IO和内存

---

#### 2.1.148 `PartitionColumnMinMaxRewriteRule`

**中文名称:** PartitionColumnMinMax重写

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 查询重写优化

---

#### 2.1.149 `PruneCTEProduceRule`

**中文名称:** 裁剪CTEProduce

**关系代数表达:**
```
π_{A}(R) → π_{A'}(R) where A' ⊆ A
```

---

#### 2.1.150 `OnPredicateMoveAroundRule`

**中文名称:** On谓词MoveAround

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.1.151 `PushDownApplyAggFilterRule`

**中文名称:** 下推ApplyAgg过滤

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.152 `MVColumnPruner`

**中文名称:** MVColumn裁剪r

**关系代数表达:**
```
π_{A}(R) → π_{A'}(R) where A' ⊆ A
```

---

#### 2.1.153 `LineageFactory`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.154 `ColumnRangePredicate`

**中文名称:** ColumnRange谓词

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.155 `AggregatedMaterializedViewPushDownRewriter`

**中文名称:** 聚合dMaterializedView下推重写r

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 查询重写优化

**依赖资源:** 物理属性

---

#### 2.1.156 `MVCompensationPruneUnionRule`

**中文名称:** MVCompensation裁剪Union

**关系代数表达:**
```
π_{A}(R) → π_{A'}(R) where A' ⊆ A
```

**依赖资源:** 物理属性

---

#### 2.1.157 `TableScanDesc`

**中文名称:** Table扫描Desc

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.158 `RangeSimplifier`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.159 `RewriteContext`

**中文名称:** 重写Context

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 查询重写优化

---

#### 2.1.160 `MVPartitionPruner`

**中文名称:** MVPartition裁剪r

**关系代数表达:**
```
π_{A}(R) → π_{A'}(R) where A' ⊆ A
```

---

#### 2.1.161 `AggregatedTimeSeriesRewriter`

**中文名称:** 聚合dTimeSeries重写r

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 查询重写优化

**依赖资源:** 物理属性

---

#### 2.1.162 `MaterializedViewRewriter`

**中文名称:** MaterializedView重写r

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 查询重写优化

**依赖资源:** 统计信息, 物理属性

---

#### 2.1.163 `PredicateSplit`

**中文名称:** 谓词Split

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.164 `for`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.165 `OptExpressionDuplicator`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 标量表达式优化

---

#### 2.1.166 `BestMvSelector`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 统计信息

---

#### 2.1.167 `represents`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.1.168 `AggregatedMaterializedViewRewriter`

**中文名称:** 聚合dMaterializedView重写r

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 查询重写优化

**依赖资源:** 物理属性

---

#### 2.1.169 `ColumnEnforcer`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.1.170 `MvUtils`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 代价模型, 物理属性

---

#### 2.1.171 `EquationRewriter`

**中文名称:** Equation重写r

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 查询重写优化

---

#### 2.1.172 `MVTransparentState`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.173 `to`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.174 `MvRewriteStrategy`

**中文名称:** Mv重写Strategy

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 查询重写优化

---

#### 2.1.175 `TableScanContext`

**中文名称:** Table扫描Context

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.176 `MVUnionRewriteMode`

**中文名称:** MVUnion重写Mode

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 查询重写优化

---

#### 2.1.177 `AndRangePredicate`

**中文名称:** AndRange谓词

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.178 `AggregateFunctionRewriter`

**中文名称:** 聚合Function重写r

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 查询重写优化

---

#### 2.1.179 `ColumnRewriter`

**中文名称:** Column重写r

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 查询重写优化

---

#### 2.1.180 `PredicateExtractor`

**中文名称:** 谓词Extractor

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.181 `ConstantOperatorDiscreteDomain`

**中文名称:** 常量OperatorDiscreteDomain

**关系代数表达:**
```
expr(const) → const_value
```

---

#### 2.1.182 `OrRangePredicate`

**中文名称:** OrRange谓词

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.183 `PartitionSelector`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.184 `UniquenessBasedTablePruneRule`

**中文名称:** UniquenessBasedTable裁剪

**关系代数表达:**
```
π_{A}(R) → π_{A'}(R) where A' ⊆ A
```

---

#### 2.1.185 `CPJoinGardener`

**中文名称:** CP连接Gardener

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.186 `RboTablePruneRule`

**中文名称:** RboTable裁剪

**关系代数表达:**
```
π_{A}(R) → π_{A'}(R) where A' ⊆ A
```

---

#### 2.1.187 `CPEdge`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.188 `PrimaryKeyUpdateTableRule`

**中文名称:** PrimaryKeyUpdateTable

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.189 `CPNode`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.190 `ExtractRangePredicateFromScalarApplyRule`

**中文名称:** ExtractRange谓词FromScalarApply

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.191 `CboTablePruneRule`

**中文名称:** CboTable裁剪

**关系代数表达:**
```
π_{A}(R) → π_{A'}(R) where A' ⊆ A
```

---

#### 2.1.192 `CPBiRel`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.193 `OnlyScanRule`

**中文名称:** Only扫描

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.194 `BaseMaterializedViewRewriteRule`

**中文名称:** BaseMaterializedView重写

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 查询重写优化

**依赖资源:** 统计信息, 物理属性

---

#### 2.1.195 `OnlyJoinRule`

**中文名称:** Only连接

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.196 `TextMatchBasedRewriteRule`

**中文名称:** TextMatchBased重写

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 查询重写优化

**依赖资源:** 代价模型, 物理属性

---

#### 2.1.197 `AggregateTimeSeriesRule`

**中文名称:** 聚合TimeSeries

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.198 `AggregateJoinPushDownRule`

**中文名称:** 聚合连接下推

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.199 `AggregateJoinRule`

**中文名称:** 聚合连接

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.200 `SingleTableRewriteBaseRule`

**中文名称:** SingleTable重写Base

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 查询重写优化

**依赖资源:** 统计信息

---

#### 2.1.201 `to`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.202 `AggregateScanRule`

**中文名称:** 聚合扫描

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.203 `AggregateFunctionRollupUtils`

**中文名称:** 聚合FunctionRollupUtils

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.204 `AggregatePushDownUtils`

**中文名称:** 聚合下推Utils

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.1.205 `PartitionRetentionTableCompensation`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.1.206 `OlapTableCompensation`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.207 `ExternalTableCompensation`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.208 `MVCompensation`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.209 `MVCompensationBuilder`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.1.210 `TableCompensation`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.211 `OptCompensator`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.212 `PercentileRewriteEquivalent`

**中文名称:** Percentile重写Equivalent

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 查询重写优化

---

#### 2.1.213 `EquivalentShuttleContext`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.214 `TimeSliceRewriteEquivalent`

**中文名称:** TimeSlice重写Equivalent

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 查询重写优化

---

#### 2.1.215 `BitmapRewriteEquivalent`

**中文名称:** Bitmap重写Equivalent

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 查询重写优化

---

#### 2.1.216 `ArrayRewriteEquivalent`

**中文名称:** Array重写Equivalent

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 查询重写优化

---

#### 2.1.217 `IRewriteEquivalent`

**中文名称:** I重写Equivalent

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 查询重写优化

---

#### 2.1.218 `IPredicateRewriteEquivalent`

**中文名称:** I谓词重写Equivalent

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 查询重写优化

---

#### 2.1.219 `CountRewriteEquivalent`

**中文名称:** Count重写Equivalent

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 查询重写优化

---

#### 2.1.220 `DateTruncEquivalent`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.221 `HLLRewriteEquivalent`

**中文名称:** HLL重写Equivalent

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 查询重写优化

---

#### 2.1.222 `RewriteEquivalent`

**中文名称:** 重写Equivalent

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 查询重写优化

---

#### 2.1.223 `AggStateRewriteEquivalent`

**中文名称:** AggState重写Equivalent

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 查询重写优化

---

#### 2.1.224 `IAggregateRewriteEquivalent`

**中文名称:** I聚合重写Equivalent

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 查询重写优化

---

### 2.2 实现规则 (Implementation)

> 共 45 条规则


#### 2.2.1 `IcebergEqualityDeleteScanImplementationRule`

**中文名称:** IcebergEqualityDelete扫描实现ation

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 将逻辑算子转换为物理算子

---

#### 2.2.2 `PaimonScanImplementationRule`

**中文名称:** Paimon扫描实现ation

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 将逻辑算子转换为物理算子

---

#### 2.2.3 `CTEConsumerReuseImplementationRule`

**中文名称:** CTEConsumerReuse实现ation

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 将逻辑算子转换为物理算子

---

#### 2.2.4 `IcebergMetadataScanImplementationRule`

**中文名称:** IcebergMetadata扫描实现ation

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 将逻辑算子转换为物理算子

---

#### 2.2.5 `MysqlScanImplementationRule`

**中文名称:** Mysql扫描实现ation

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 将逻辑算子转换为物理算子

---

#### 2.2.6 `ValuesImplementationRule`

**中文名称:** Values实现ation

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 将逻辑算子转换为物理算子

---

#### 2.2.7 `IcebergScanImplementationRule`

**中文名称:** Iceberg扫描实现ation

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 将逻辑算子转换为物理算子

---

#### 2.2.8 `HudiScanImplementationRule`

**中文名称:** Hudi扫描实现ation

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 将逻辑算子转换为物理算子

---

#### 2.2.9 `NestLoopJoinImplementationRule`

**中文名称:** NestLoop连接实现ation

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 将逻辑算子转换为物理算子

---

#### 2.2.10 `RepeatImplementationRule`

**中文名称:** Repeat实现ation

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 将逻辑算子转换为物理算子

---

#### 2.2.11 `ProjectImplementationRule`

**中文名称:** 投影实现ation

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 将逻辑算子转换为物理算子

---

#### 2.2.12 `HashJoinImplementationRule`

**功能描述:** 使用哈希表实现连接

**优化目标:** O(n+m)时间复杂度的连接

---

#### 2.2.13 `MetaScanImplementationRule`

**中文名称:** Meta扫描实现ation

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 将逻辑算子转换为物理算子

---

#### 2.2.14 `ImplementationRule`

**中文名称:** 实现ation

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 将逻辑算子转换为物理算子

---

#### 2.2.15 `ExceptImplementationRule`

**中文名称:** 差集实现ation

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 将逻辑算子转换为物理算子

---

#### 2.2.16 `WindowImplementationRule`

**中文名称:** Window实现ation

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 将逻辑算子转换为物理算子

---

#### 2.2.17 `EsScanImplementationRule`

**中文名称:** Es扫描实现ation

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 将逻辑算子转换为物理算子

---

#### 2.2.18 `TopNImplementationRule`

**功能描述:** 将排序+Limit转换为TopN操作

**优化目标:** 避免全排序，使用堆获取TopN

---

#### 2.2.19 `AssertOneRowImplementationRule`

**中文名称:** AssertOneRow实现ation

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 将逻辑算子转换为物理算子

---

#### 2.2.20 `RawValuesImplementationRule`

**中文名称:** RawValues实现ation

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 将逻辑算子转换为物理算子

---

#### 2.2.21 `TableFunctionImplementationRule`

**中文名称:** TableFunction实现ation

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 将逻辑算子转换为物理算子

---

#### 2.2.22 `CTEAnchorToNoCTEImplementationRule`

**中文名称:** CTEAnchorToNoCTE实现ation

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 将逻辑算子转换为物理算子

---

#### 2.2.23 `TableFunctionTableScanImplementationRule`

**中文名称:** TableFunctionTable扫描实现ation

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 将逻辑算子转换为物理算子

---

#### 2.2.24 `SchemaScanImplementationRule`

**中文名称:** Schema扫描实现ation

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 将逻辑算子转换为物理算子

---

#### 2.2.25 `DeltaLakeScanImplementationRule`

**中文名称:** DeltaLake扫描实现ation

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 将逻辑算子转换为物理算子

---

#### 2.2.26 `CTEProduceImplementationRule`

**中文名称:** CTEProduce实现ation

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 将逻辑算子转换为物理算子

---

#### 2.2.27 `FileScanImplementationRule`

**中文名称:** File扫描实现ation

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 将逻辑算子转换为物理算子

---

#### 2.2.28 `CTEConsumeInlineImplementationRule`

**中文名称:** CTEConsumeInline实现ation

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 将逻辑算子转换为物理算子

---

#### 2.2.29 `OdpsScanImplementationRule`

**中文名称:** Odps扫描实现ation

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 将逻辑算子转换为物理算子

---

#### 2.2.30 `HashAggImplementationRule`

**中文名称:** HashAgg实现ation

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 将逻辑算子转换为物理算子

---

#### 2.2.31 `IntersectImplementationRule`

**中文名称:** 交集实现ation

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 将逻辑算子转换为物理算子

---

#### 2.2.32 `KuduScanImplementationRule`

**中文名称:** Kudu扫描实现ation

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 将逻辑算子转换为物理算子

---

#### 2.2.33 `MergeJoinImplementationRule`

**功能描述:** 使用归并排序实现连接

**优化目标:** 适用于已排序数据

---

#### 2.2.34 `CTEAnchorImplementationRule`

**中文名称:** CTEAnchor实现ation

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 将逻辑算子转换为物理算子

---

#### 2.2.35 `JDBCScanImplementationRule`

**中文名称:** JDBC扫描实现ation

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 将逻辑算子转换为物理算子

---

#### 2.2.36 `FilterImplementationRule`

**中文名称:** 过滤实现ation

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 将逻辑算子转换为物理算子

---

#### 2.2.37 `HiveScanImplementationRule`

**中文名称:** Hive扫描实现ation

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 将逻辑算子转换为物理算子

---

#### 2.2.38 `UnionImplementationRule`

**中文名称:** Union实现ation

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 将逻辑算子转换为物理算子

---

#### 2.2.39 `JoinImplementationRule`

**中文名称:** 连接实现ation

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 将逻辑算子转换为物理算子

**依赖资源:** 物理属性

---

#### 2.2.40 `OlapScanImplementationRule`

**中文名称:** Olap扫描实现ation

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 将逻辑算子转换为物理算子

---

#### 2.2.41 `LimitImplementationRule`

**功能描述:** 将Limit操作下推到数据源

**优化目标:** 减少数据传输

---

#### 2.2.42 `StreamAggregateImplementationRule`

**中文名称:** Stream聚合实现ation

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 将逻辑算子转换为物理算子

---

#### 2.2.43 `StreamScanImplementationRule`

**中文名称:** Stream扫描实现ation

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 将逻辑算子转换为物理算子

---

#### 2.2.44 `StreamImplementationRule`

**中文名称:** Stream实现ation

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 将逻辑算子转换为物理算子

---

#### 2.2.45 `StreamJoinImplementationRule`

**中文名称:** Stream连接实现ation

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 将逻辑算子转换为物理算子

---

## 🔬 三、优化原理总结

### 3.1 优化目标分布

| 优化目标 | 规则数量 |
|----------|----------|

| 查询重写优化 | 42 |
| 将逻辑算子转换为物理算子 | 41 |
| 减少数据传输量 | 15 |
| 减少连接前的数据量 | 15 |
| 减少数据传输 | 13 |
| 减少列扫描，降低IO和内存 | 6 |
| 避免全排序，使用堆获取TopN | 5 |
| 逻辑等价变换，生成备选执行计划 | 1 |
| 标量表达式优化 | 1 |
| O(n+m)时间复杂度的连接 | 1 |

### 3.2 关系代数优化原理


查询优化的核心是利用关系代数的等价变换规则：

1. **选择下推 (Selection Pushdown)**
   - 原理: 尽早过滤减少中间结果
   - 公式: `σ_{p}(R ⋈ S) = R ⋈ σ_{p}(S)` (当p只涉及S的属性时)

2. **投影下推 (Projection Pushdown)**
   - 原理: 只保留需要的列
   - 公式: `π_{A}(R ⋈ S) = π_{A}(R ⋈ π_{A∩attr(S)}(S))`

3. **连接重排序 (Join Reordering)**
   - 原理: 选择产生最小中间结果的连接顺序
   - 公式: `(R ⋈ S) ⋈ T` 与 `R ⋈ (S ⋈ T)` 可能代价不同

4. **聚合下推 (Aggregation Pushdown)**
   - 原理: 先聚合减少数据量
   - 公式: 在特定条件下 `γ_{g,a}(R ⋈ S) = γ_{g,a}(R) ⋈ S`


## 🔍 四、与其他引擎对比


### 4.1 规则完整性对比

| 维度 | StarRocks | Doris | Calcite |
|------|-----------|-------|---------|
| 规则总数 | 269 | 463 | 155 |
| 转换规则 | 224 | 191(重写)+82(探索) | 155 |
| 实现规则 | 45 | 54 | 框架提供 |

### 4.2 特点总结

**StarRocks优势:**
- 规则分类清晰（转换/实现）
- Cascades实现完整
- Memo管理高效

**可借鉴之处:**
- Doris的细粒度规则分类
- Calcite的Trait系统


## 📖 五、参考资料


### 5.1 关系代数基础

1. **选择操作 σ**: `σ_{condition}(R)` - 从关系R中选择满足条件的元组
2. **投影操作 π**: `π_{attributes}(R)` - 从关系R中选择指定属性
3. **连接操作 ⋈**: `R ⋈_{condition} S` - 连接两个关系
4. **聚合操作 γ**: `γ_{group, agg}(R)` - 分组聚合

### 5.2 优化理论

- **Volcano优化器**: Exodus项目提出的优化器框架
- **Cascades优化器**: Volcano的改进版本，使用Memo和Top-Down搜索
- **代价模型**: 基于统计信息估算查询执行代价
- **启发式优化**: 基于规则的优化，不依赖代价模型

### 5.3 相关论文

1. "The Cascades Framework for Query Optimization" - Graefe, 1995
2. "Volcano-An Extensible and Parallel Query Evaluation System" - Graefe, 1994
3. "Access Path Selection in a Relational Database Management System" - Selinger, 1979


---

*本报告由 Optimizer Expert Analyzer 自动生成*

*使用关系代数符号描述规则语义*
