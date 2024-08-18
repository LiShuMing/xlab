# Calcite 优化规则详细分析报告

> **生成时间:** 2026-04-06 12:18:01

> **分析源码路径:** `/home/lism/work/calcite`

> **规则总数:** 153

## 📊 一、规则统计总览

### 1.1 规则分类统计

| 规则类型 | 数量 | 占比 |
|----------|------|------|

| 其他规则 | 128 | 83.7% |
| RBO | 20 | 13.1% |
| CBO | 2 | 1.3% |
| 表达式规则 | 2 | 1.3% |
| 转换规则 | 1 | 0.7% |
| **总计** | **153** | **100%** |

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


### 2.1 优化规则 (Rules)

> 共 153 条规则


#### 2.1.1 `FilterCalcMergeRule`

**功能描述:** 合并多个过滤条件

**优化目标:** 减少扫描次数

---

#### 2.1.2 `JoinDeriveIsNotNullFilterRule`

**中文名称:** 连接DeriveIsNotNull过滤

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.1.3 `SortJoinCopyRule`

**中文名称:** 排序连接Copy

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.1.4 `SemiJoinJoinTransposeRule`

**中文名称:** Semi连接连接转置

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.1.5 `AggregateExtractProjectRule`

**中文名称:** 聚合Extract投影

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.6 `SortRemoveDuplicateKeysRule`

**中文名称:** 排序RemoveDuplicateKeys

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.7 `SetOpToFilterRule`

**中文名称:** SetOpTo过滤

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.8 `AggregateFilterToCaseRule`

**中文名称:** 聚合过滤ToCase

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.9 `SortRemoveRedundantRule`

**中文名称:** 排序RemoveRedundant

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.10 `IntersectToDistinctRule`

**中文名称:** 交集ToDistinct

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.11 `JoinProjectTransposeRule`

**中文名称:** 连接投影转置

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.1.12 `UnionMergeRule`

**功能描述:** 合并相同的Union分支

**优化目标:** 消除重复计算

---

#### 2.1.13 `AggregateStarTableRule`

**中文名称:** 聚合StarTable

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.1.14 `SortRemoveRule`

**中文名称:** 排序Remove

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.1.15 `CoerceInputsRule`

**中文名称:** CoerceInputs

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.1.16 `SortMergeRule`

**中文名称:** 排序合并

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.17 `UnionToValuesRule`

**中文名称:** UnionToValues

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.18 `TableScanRule`

**中文名称:** Table扫描

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.19 `IntersectToExistsRule`

**中文名称:** 交集ToExists

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.20 `FilterWindowTransposeRule`

**功能描述:** 移动过滤操作的位置

**优化目标:** 尽早过滤减少数据量

---

#### 2.1.21 `for`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.1.22 `DphypJoinReorderRule`

**功能描述:** 调整多表连接顺序，优先连接小表

**优化目标:** 最小化中间结果大小

---

#### 2.1.23 `MarkToSemiOrAntiJoinRule`

**中文名称:** MarkToSemiOrAnti连接

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.24 `ProjectToCalcRule`

**中文名称:** 投影ToCalc

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.25 `JoinPushThroughJoinRule`

**中文名称:** 连接PushThrough连接

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.1.26 `AggregateProjectConstantToDummyJoinRule`

**中文名称:** 聚合投影常量ToDummy连接

**关系代数表达:**
```
expr(const) → const_value
```

---

#### 2.1.27 `that`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.28 `JoinAssociateRule`

**中文名称:** 连接Associate

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.1.29 `AggregateUnionTransposeRule`

**功能描述:** 交换聚合和连接的顺序

**优化目标:** 先聚合减少数据量再连接

---

#### 2.1.30 `ProjectMultiJoinMergeRule`

**中文名称:** 投影Multi连接合并

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.31 `JoinPushTransitivePredicatesRule`

**中文名称:** 连接PushTransitive谓词s

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.1.32 `ProjectWindowTransposeRule`

**中文名称:** 投影Window转置

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.1.33 `CoreRules`

**中文名称:** Cores

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 代价模型

---

#### 2.1.34 `AggregateValuesRule`

**中文名称:** 聚合Values

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.35 `SingleValuesOptimizationRules`

**中文名称:** SingleValuesOptimizations

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.36 `AggregateRemoveRule`

**中文名称:** 聚合Remove

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.1.37 `ProjectJoinJoinRemoveRule`

**中文名称:** 投影连接连接Remove

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.38 `FilterSetOpTransposeRule`

**功能描述:** 移动过滤操作的位置

**优化目标:** 尽早过滤减少数据量

---

#### 2.1.39 `FilterProjectTransposeRule`

**功能描述:** 移动过滤操作的位置

**优化目标:** 尽早过滤减少数据量

---

#### 2.1.40 `FilterSampleTransposeRule`

**功能描述:** 移动过滤操作的位置

**优化目标:** 尽早过滤减少数据量

---

#### 2.1.41 `JoinPushExpressionsRule`

**中文名称:** 连接PushExpressions

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 标量表达式优化

---

#### 2.1.42 `AggregateFilterTransposeRule`

**功能描述:** 交换聚合和连接的顺序

**优化目标:** 先聚合减少数据量再连接

---

#### 2.1.43 `AggregateExpandDistinctAggregatesRule`

**中文名称:** 聚合ExpandDistinct聚合s

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 统计信息, 物理属性

---

#### 2.1.44 `JoinCommuteRule`

**功能描述:** 利用连接交换律改变连接顺序

**优化目标:** 选择更优的连接顺序

---

#### 2.1.45 `FilterTableFunctionTransposeRule`

**功能描述:** 移动过滤操作的位置

**优化目标:** 尽早过滤减少数据量

---

#### 2.1.46 `used`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.47 `ProjectJoinRemoveRule`

**中文名称:** 投影连接Remove

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.1.48 `ConflictRule`

**中文名称:** Conflict

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.49 `UnionToDistinctRule`

**中文名称:** UnionToDistinct

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.50 `MultiJoinProjectTransposeRule`

**中文名称:** Multi连接投影转置

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.51 `ExpandDisjunctionForTableRule`

**中文名称:** ExpandDisjunctionForTable

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.1.52 `AggregateFilterToFilteredAggregateRule`

**中文名称:** 聚合过滤To过滤ed聚合

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.53 `FilterSortTransposeRule`

**功能描述:** 移动过滤操作的位置

**优化目标:** 尽早过滤减少数据量

---

#### 2.1.54 `of`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.1.55 `AggregateProjectStarTableRule`

**中文名称:** 聚合投影StarTable

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.56 `SpatialRules`

**中文名称:** Spatials

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.57 `ReduceExpressionsRule`

**中文名称:** ReduceExpressions

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 标量表达式优化

**依赖资源:** 物理属性

---

#### 2.1.58 `MinusToAntiJoinRule`

**中文名称:** MinusToAnti连接

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.59 `AggregateExpandWithinDistinctRule`

**中文名称:** 聚合ExpandWithinDistinct

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.60 `JoinToHyperGraphRule`

**中文名称:** 连接ToHyperGraph

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.1.61 `ProjectAggregateMergeRule`

**功能描述:** 合并相邻的聚合操作

**优化目标:** 减少聚合计算次数

---

#### 2.1.62 `FilterToCalcRule`

**中文名称:** 过滤ToCalc

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.63 `JoinExpandOrToUnionRule`

**中文名称:** 连接ExpandOrToUnion

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.64 `MaterializedViewFilterScanRule`

**中文名称:** MaterializedView过滤扫描

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.1.65 `SemiJoinRemoveRule`

**中文名称:** Semi连接Remove

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.66 `MinusToDistinctRule`

**中文名称:** MinusToDistinct

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.67 `SemiJoinRule`

**中文名称:** Semi连接

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.68 `DateRangeRules`

**中文名称:** DateRanges

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.69 `ConflictDetectionHelper`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.70 `FilterTableScanRule`

**中文名称:** 过滤Table扫描

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.71 `AggregateMergeRule`

**功能描述:** 合并相邻的聚合操作

**优化目标:** 减少聚合计算次数

---

#### 2.1.72 `LoptOptimizeJoinRule`

**中文名称:** LoptOptimize连接

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 代价模型

---

#### 2.1.73 `DpHyp`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 代价模型, 物理属性

---

#### 2.1.74 `PruneEmptyRules`

**中文名称:** 裁剪Emptys

**关系代数表达:**
```
π_{A}(R) → π_{A'}(R) where A' ⊆ A
```

**依赖资源:** 物理属性

---

#### 2.1.75 `indicates`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.76 `of`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.77 `ProjectOverSumToSum0Rule`

**中文名称:** 投影OverSumToSum0

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.78 `TransformationRule`

**中文名称:** 转换ation

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 逻辑等价变换，生成备选执行计划

---

#### 2.1.79 `SubQueryRemoveRule`

**中文名称:** SubQueryRemove

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.80 `MultiJoinOptimizeBushyRule`

**中文名称:** Multi连接OptimizeBushy

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 代价模型, 物理属性

---

#### 2.1.81 `FilterCorrelateRule`

**中文名称:** 过滤Correlate

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.1.82 `JoinConditionExpandIsNotDistinctFromRule`

**中文名称:** 连接ConditionExpandIsNotDistinctFrom

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.83 `IntersectReorderRule`

**中文名称:** 交集重排序

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.84 `SortUnionTransposeRule`

**中文名称:** 排序Union转置

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.1.85 `FullToLeftAndRightJoinRule`

**中文名称:** FullToLeftAndRight连接

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.86 `MatchRule`

**中文名称:** Match

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.1.87 `AggregateMinMaxToLimitRule`

**功能描述:** 将Limit操作下推到数据源

**优化目标:** 减少数据传输

---

#### 2.1.88 `SampleToFilterRule`

**中文名称:** SampleTo过滤

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.89 `AggregateProjectPullUpConstantsRule`

**中文名称:** 聚合投影PullUp常量s

**关系代数表达:**
```
expr(const) → const_value
```

---

#### 2.1.90 `ProjectFilterTransposeRule`

**功能描述:** 移动过滤操作的位置

**优化目标:** 尽早过滤减少数据量

---

#### 2.1.91 `ExchangeRemoveConstantKeysRule`

**中文名称:** 交换Remove常量Keys

**关系代数表达:**
```
expr(const) → const_value
```

---

#### 2.1.92 `JoinToCorrelateRule`

**中文名称:** 连接ToCorrelate

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.93 `HyperGraph`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.1.94 `MultiJoin`

**中文名称:** Multi连接

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.1.95 `ExpandDisjunctionForJoinInputsRule`

**中文名称:** ExpandDisjunctionFor连接Inputs

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.1.96 `AggregateJoinRemoveRule`

**中文名称:** 聚合连接Remove

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.1.97 `ProjectTableScanRule`

**中文名称:** 投影Table扫描

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.98 `of`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.1.99 `ProjectCorrelateTransposeRule`

**中文名称:** 投影Correlate转置

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.1.100 `is`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.1.101 `ProjectSetOpTransposeRule`

**中文名称:** 投影SetOp转置

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.1.102 `ProjectCalcMergeRule`

**中文名称:** 投影Calc合并

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.1.103 `MinusToFilterRule`

**中文名称:** MinusTo过滤

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.104 `HyperEdge`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.105 `FilterAggregateTransposeRule`

**功能描述:** 交换聚合和连接的顺序

**优化目标:** 先聚合减少数据量再连接

---

#### 2.1.106 `IntersectToSemiJoinRule`

**中文名称:** 交集ToSemi连接

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.107 `used`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.108 `CalcSplitRule`

**中文名称:** CalcSplit

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.109 `FilterJoinRule`

**中文名称:** 过滤连接

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.1.110 `CalcMergeRule`

**中文名称:** Calc合并

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.1.111 `ProjectJoinTransposeRule`

**中文名称:** 投影连接转置

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.1.112 `AggregateCaseToFilterRule`

**中文名称:** 聚合CaseTo过滤

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.113 `CommonRelSubExprRegisterRule`

**中文名称:** CommonRelSubExprRegister

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.114 `SortJoinTransposeRule`

**中文名称:** 排序连接转置

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.1.115 `AggregateReduceFunctionsRule`

**中文名称:** 聚合ReduceFunctions

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.116 `SortProjectTransposeRule`

**中文名称:** 排序投影转置

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.1.117 `FilterRemoveIsNotDistinctFromRule`

**中文名称:** 过滤RemoveIsNotDistinctFrom

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.118 `AggregateJoinTransposeRule`

**功能描述:** 交换聚合和连接的顺序

**优化目标:** 先聚合减少数据量再连接

---

#### 2.1.119 `UnnestDecorrelateRule`

**中文名称:** UnnestDecorrelate

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.120 `SortRemoveConstantKeysRule`

**中文名称:** 排序Remove常量Keys

**关系代数表达:**
```
expr(const) → const_value
```

**依赖资源:** 物理属性

---

#### 2.1.121 `SemiJoinFilterTransposeRule`

**功能描述:** 移动过滤操作的位置

**优化目标:** 尽早过滤减少数据量

---

#### 2.1.122 `UnionPullUpConstantsRule`

**中文名称:** UnionPullUp常量s

**关系代数表达:**
```
expr(const) → const_value
```

---

#### 2.1.123 `LoptSemiJoinOptimizer`

**中文名称:** LoptSemi连接Optimizer

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 代价模型

---

#### 2.1.124 `ProjectMergeRule`

**中文名称:** 投影合并

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.125 `ReduceDecimalsRule`

**中文名称:** ReduceDecimals

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.126 `CombineSimpleEquivalenceRule`

**中文名称:** CombineSimpleEquivalence

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.127 `of`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.128 `AggregateJoinJoinRemoveRule`

**中文名称:** 聚合连接连接Remove

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.129 `MeasureRules`

**中文名称:** Measures

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.130 `AggregateProjectMergeRule`

**功能描述:** 合并相邻的聚合操作

**优化目标:** 减少聚合计算次数

---

#### 2.1.131 `LongBitmap`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.132 `UnionEliminatorRule`

**中文名称:** UnionEliminator

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.133 `AggregateUnionAggregateRule`

**中文名称:** 聚合Union聚合

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.134 `ProjectToWindowRule`

**中文名称:** 投影ToWindow

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.1.135 `FilterMultiJoinMergeRule`

**功能描述:** 合并多个过滤条件

**优化目标:** 减少扫描次数

---

#### 2.1.136 `JoinUnionTransposeRule`

**中文名称:** 连接Union转置

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.1.137 `FilterFlattenCorrelatedConditionRule`

**中文名称:** 过滤FlattenCorrelatedCondition

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.138 `SemiJoinProjectTransposeRule`

**中文名称:** Semi连接投影转置

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.139 `ProjectRemoveRule`

**中文名称:** 投影Remove

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.1.140 `ValuesReduceRule`

**中文名称:** ValuesReduce

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.141 `AggregateGroupingSetsToUnionRule`

**中文名称:** 聚合GroupingSetsToUnion

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.142 `FilterMergeRule`

**功能描述:** 合并多个过滤条件

**优化目标:** 减少扫描次数

---

#### 2.1.143 `CalcRemoveRule`

**中文名称:** CalcRemove

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.1.144 `MaterializedViewAggregateRule`

**中文名称:** MaterializedView聚合

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.1.145 `MaterializedViewOnlyJoinRule`

**中文名称:** MaterializedViewOnly连接

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.146 `MaterializedViewOnlyAggregateRule`

**中文名称:** MaterializedViewOnly聚合

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.147 `MaterializedViewRule`

**中文名称:** MaterializedView

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.148 `MaterializedViewOnlyFilterRule`

**中文名称:** MaterializedViewOnly过滤

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.149 `MaterializedViewProjectJoinRule`

**中文名称:** MaterializedView投影连接

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.150 `MaterializedViewRules`

**中文名称:** MaterializedViews

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.151 `MaterializedViewProjectFilterRule`

**中文名称:** MaterializedView投影过滤

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.152 `MaterializedViewJoinRule`

**中文名称:** MaterializedView连接

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.1.153 `MaterializedViewProjectAggregateRule`

**中文名称:** MaterializedView投影聚合

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

## 🔬 三、优化原理总结

### 3.1 优化目标分布

| 优化目标 | 规则数量 |
|----------|----------|

| 尽早过滤减少数据量 | 8 |
| 先聚合减少数据量再连接 | 4 |
| 减少扫描次数 | 3 |
| 减少聚合计算次数 | 3 |
| 标量表达式优化 | 2 |
| 消除重复计算 | 1 |
| 最小化中间结果大小 | 1 |
| 选择更优的连接顺序 | 1 |
| 逻辑等价变换，生成备选执行计划 | 1 |
| 减少数据传输 | 1 |

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


### 4.1 框架特点

Calcite作为SQL优化框架，与其他数据库优化器的定位不同：

| 特性 | Calcite | StarRocks/Doris |
|------|---------|-----------------|
| 定位 | 框架/库 | 完整数据库 |
| Memo | 无内置 | 内置支持 |
| Trait系统 | 完整 | 有属性系统 |
| 扩展性 | 极高 | 中等 |

### 4.2 使用场景

**适合使用Calcite:**
- 构建新的SQL引擎
- 需要SQL解析和验证
- 需要可插拔的优化器

**Calcite用户:**
- Apache Hive
- Apache Flink
- Apache Drill
- Apache Kylin


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
