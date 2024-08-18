# Doris 优化规则详细分析报告

> **生成时间:** 2026-04-06 12:18:01

> **分析源码路径:** `/home/lism/work/doris`

> **规则总数:** 463

## 📊 一、规则统计总览

### 1.1 规则分类统计

| 规则类型 | 数量 | 占比 |
|----------|------|------|

| 其他规则 | 359 | 77.5% |
| RBO | 43 | 9.3% |
| 表达式规则 | 25 | 5.4% |
| 重写规则 | 23 | 5.0% |
| 分析规则 | 4 | 0.9% |
| Implementation | 4 | 0.9% |
| CBO | 3 | 0.6% |
| 实现规则 | 2 | 0.4% |
| **总计** | **463** | **100%** |

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


### 2.1 分析规则 (Analysis)

> 共 48 条规则


#### 2.1.1 `VariableToLiteral`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.2 `for`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.3 `ExpressionAnalyzer`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 语义分析和绑定

---

#### 2.1.4 `WindowFunctionChecker`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.5 `CheckPolicy`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.6 `SubExprAnalyzer`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 语义分析和绑定

---

#### 2.1.7 `NormalizeAggregate`

**中文名称:** Normalize聚合

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.8 `GetFormatFunctionBinder`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.9 `ProjectToGlobalAggregate`

**中文名称:** 投影ToGlobal聚合

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.10 `ArithmeticFunctionBinder`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.11 `DatetimeFunctionBinder`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.12 `NormalizeRepeat`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.13 `UserAuthentication`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.14 `AvgDistinctToSumDivCount`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.15 `CheckSearchUsage`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.16 `is`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.17 `LogicalSubQueryAliasToLogicalProject`

**中文名称:** LogicalSubQueryAliasToLogical投影

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.18 `FoldConstantForSqlCache`

**中文名称:** 折叠常量ForSqlCache

**关系代数表达:**
```
expr(const) → const_value
```

---

#### 2.1.19 `HavingToFilter`

**中文名称:** HavingTo过滤

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.20 `LeadingJoin`

**中文名称:** Leading连接

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.21 `BindSkewExpr`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.22 `BindSink`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.1.23 `AdjustAggregateNullableForEmptySet`

**中文名称:** Adjust聚合NullableForEmptySet

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.24 `CompressedMaterialize`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.25 `AddInitMaterializationHook`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.26 `EliminateLogicalPreAggOnHint`

**中文名称:** 消除LogicalPreAggOnHint

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.27 `ColumnAliasGenerator`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.28 `FillUpMissingSlots`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.29 `for`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.30 `ReplaceExpressionByChildOutput`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 标量表达式优化

---

#### 2.1.31 `CollectSubQueryAlias`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.32 `EliminateLogicalSelectHint`

**中文名称:** 消除LogicalSelectHint

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.33 `AnalyzeCTE`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 语义分析和绑定

---

#### 2.1.34 `OneRowRelationExtractAggregate`

**中文名称:** OneRowRelationExtract聚合

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.35 `NormalizeGenerate`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.36 `CollectOneLevelRelation`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.37 `FillUpQualifyMissingSlot`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.38 `CheckAnalysis`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 语义分析和绑定

---

#### 2.1.39 `QualifyToFilter`

**中文名称:** QualifyTo过滤

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.40 `CheckAfterRewrite`

**中文名称:** CheckAfter重写

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 查询重写优化

**依赖资源:** 物理属性

---

#### 2.1.41 `OneRowRelationToProject`

**中文名称:** OneRowRelationTo投影

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.42 `BindExpression`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 标量表达式优化

---

#### 2.1.43 `BindRelation`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.44 `SubqueryToApply`

**中文名称:** 子查询ToApply

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.45 `EliminateDistinctConstant`

**中文名称:** 消除Distinct常量

**关系代数表达:**
```
expr(const) → const_value
```

---

#### 2.1.46 `ProjectWithDistinctToAggregate`

**中文名称:** 投影WithDistinctTo聚合

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.47 `CollectJoinConstraint`

**中文名称:** Collect连接Constraint

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.1.48 `CollectRelation`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

### 2.2 探索规则 (Exploration)

> 共 82 条规则


#### 2.2.1 `CBOUtils`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.2.2 `EagerGroupBy`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.2.3 `TransposeAggSemiJoinProject`

**中文名称:** 转置AggSemi连接投影

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.2.4 `for`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.2.5 `TransposeAggSemiJoin`

**中文名称:** 转置AggSemi连接

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.2.6 `EagerGroupByCount`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.2.7 `IntersectReorder`

**中文名称:** 交集重排序

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 统计信息

---

#### 2.2.8 `for`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.2.9 `MergeProjectsCBO`

**中文名称:** 合并投影sCBO

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.2.10 `EagerCount`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.2.11 `EagerSplit`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.2.12 `LogicalJoinSemiJoinTransposeProject`

**中文名称:** Logical连接Semi连接转置投影

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.2.13 `SemiJoinSemiJoinTransposeProject`

**中文名称:** Semi连接Semi连接转置投影

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.2.14 `InnerJoinLAsscomProject`

**中文名称:** Inner连接LAsscom投影

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 统计信息

---

#### 2.2.15 `PushDownProjectThroughSemiJoin`

**功能描述:** 将投影操作下推，只读取需要的列

**优化目标:** 减少列扫描，降低IO和内存

---

#### 2.2.16 `InnerJoinLeftAssociateProject`

**中文名称:** Inner连接LeftAssociate投影

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.2.17 `JoinExchangeBothProject`

**中文名称:** 连接交换Both投影

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.2.18 `OuterJoinAssocProject`

**中文名称:** Outer连接Assoc投影

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.2.19 `JoinCommute`

**功能描述:** 利用连接交换律改变连接顺序

**优化目标:** 选择更优的连接顺序

---

#### 2.2.20 `JoinReorderContext`

**功能描述:** 调整多表连接顺序，优先连接小表

**优化目标:** 最小化中间结果大小

---

#### 2.2.21 `InnerJoinRightAssociateProject`

**中文名称:** Inner连接RightAssociate投影

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.2.22 `OuterJoinLAsscomProject`

**中文名称:** Outer连接LAsscom投影

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.2.23 `PushDownProjectThroughInnerOuterJoin`

**功能描述:** 将投影操作下推，只读取需要的列

**优化目标:** 减少列扫描，降低IO和内存

---

#### 2.2.24 `MaterializedViewOnlyScanRule`

**中文名称:** MaterializedViewOnly扫描

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.2.25 `AbstractMaterializedViewAggregateRule`

**中文名称:** AbstractMaterializedView聚合

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.2.26 `SyncMaterializationContext`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 统计信息

---

#### 2.2.27 `EquivalenceClass`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.2.28 `MaterializedViewTopNJoinRule`

**功能描述:** 将排序+Limit转换为TopN操作

**优化目标:** 避免全排序，使用堆获取TopN

---

#### 2.2.29 `MaterializedViewAggregateRule`

**中文名称:** MaterializedView聚合

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.2.30 `MaterializedViewFilterAggregateRule`

**中文名称:** MaterializedView过滤聚合

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.2.31 `MaterializedViewWindowJoinRule`

**中文名称:** MaterializedViewWindow连接

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.2.32 `MaterializedViewProjectFilterProjectJoinRule`

**中文名称:** MaterializedView投影过滤投影连接

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.2.33 `InitMaterializationContextHook`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 统计信息

---

#### 2.2.34 `MaterializedViewFilterProjectAggregateRule`

**中文名称:** MaterializedView过滤投影聚合

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.2.35 `MaterializedViewProjectFilterAggregateRule`

**中文名称:** MaterializedView投影过滤聚合

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.2.36 `AsyncMaterializationContext`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 统计信息

---

#### 2.2.37 `MaterializedViewLimitJoinRule`

**功能描述:** 将Limit操作下推到数据源

**优化目标:** 减少数据传输

---

#### 2.2.38 `MaterializedViewTopNScanRule`

**功能描述:** 将排序+Limit转换为TopN操作

**优化目标:** 避免全排序，使用堆获取TopN

---

#### 2.2.39 `PreMaterializedViewRewriter`

**中文名称:** PreMaterializedView重写r

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 查询重写优化

---

#### 2.2.40 `AbstractMaterializedViewLimitOrTopNRule`

**功能描述:** 将Limit操作下推到数据源

**优化目标:** 减少数据传输

---

#### 2.2.41 `RelatedTableInfo`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.2.42 `MaterializedViewLimitAggregateRule`

**功能描述:** 将Limit操作下推到数据源

**优化目标:** 减少数据传输

---

#### 2.2.43 `Predicates`

**中文名称:** 谓词s

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.2.44 `ComparisonResult`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.2.45 `MaterializedViewProjectJoinRule`

**中文名称:** MaterializedView投影连接

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.2.46 `MaterializedViewFilterScanRule`

**中文名称:** MaterializedView过滤扫描

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.2.47 `MaterializedViewProjectFilterJoinRule`

**中文名称:** MaterializedView投影过滤连接

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.2.48 `MaterializedViewAggregateOnNoneAggregateRule`

**中文名称:** MaterializedView聚合OnNone聚合

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.2.49 `MaterializedViewLimitScanRule`

**功能描述:** 将Limit操作下推到数据源

**优化目标:** 减少数据传输

---

#### 2.2.50 `MaterializedViewWindowAggregateRule`

**中文名称:** MaterializedViewWindow聚合

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.2.51 `MaterializedViewProjectFilterScanRule`

**中文名称:** MaterializedView投影过滤扫描

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.2.52 `StructInfo`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.2.53 `HyperGraphComparator`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.2.54 `AbstractMaterializedViewScanRule`

**中文名称:** AbstractMaterializedView扫描

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.2.55 `AbstractMaterializedViewWindowRule`

**中文名称:** AbstractMaterializedViewWindow

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.2.56 `MaterializedViewWindowScanRule`

**中文名称:** MaterializedViewWindow扫描

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.2.57 `PartitionCompensator`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.2.58 `MaterializedViewFilterJoinRule`

**中文名称:** MaterializedView过滤连接

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.2.59 `for`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 代价模型, 统计信息

---

#### 2.2.60 `MaterializedViewProjectScanRule`

**中文名称:** MaterializedView投影扫描

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.2.61 `MaterializedViewUtils`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.2.62 `MaterializedViewTopNAggregateRule`

**功能描述:** 将排序+Limit转换为TopN操作

**优化目标:** 避免全排序，使用堆获取TopN

---

#### 2.2.63 `PartitionIncrementMaintainer`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.2.64 `InitConsistentMaterializationContextHook`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.2.65 `MaterializedViewFilterProjectJoinRule`

**中文名称:** MaterializedView过滤投影连接

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.2.66 `LogicalCompatibilityContext`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.2.67 `MaterializedViewFilterProjectScanRule`

**中文名称:** MaterializedView过滤投影扫描

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.2.68 `PredicatesSplitter`

**中文名称:** 谓词sSplitter

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.2.69 `AbstractMaterializedViewJoinRule`

**中文名称:** AbstractMaterializedView连接

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.2.70 `MaterializationContext`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 代价模型, 统计信息

---

#### 2.2.71 `MaterializedViewProjectAggregateRule`

**中文名称:** MaterializedView投影聚合

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.2.72 `set`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.2.73 `RelationMapping`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.2.74 `SlotMapping`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.2.75 `ExpressionMapping`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 标量表达式优化

---

#### 2.2.76 `Mapping`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.2.77 `AggFunctionRollUpHandler`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.2.78 `DirectRollupHandler`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.2.79 `MappingRollupHandler`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.2.80 `BothCombinatorRollupHandler`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.2.81 `ContainDistinctFunctionRollupHandler`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.2.82 `SingleCombinatorRollupHandler`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

### 2.3 实现规则 (Implementation)

> 共 54 条规则


#### 2.3.1 `LogicalDictionarySinkToPhysicalDictionarySink`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 统计信息

---

#### 2.3.2 `LogicalDeferMaterializeTopNToPhysicalDeferMaterializeTopN`

**功能描述:** 将排序+Limit转换为TopN操作

**优化目标:** 避免全排序，使用堆获取TopN

---

#### 2.3.3 `LogicalSchemaScanToPhysicalSchemaScan`

**中文名称:** LogicalSchema扫描ToPhysicalSchema扫描

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.3.4 `LogicalMaxComputeTableSinkToPhysicalMaxComputeTableSink`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.3.5 `LogicalIcebergMergeSinkToPhysicalIcebergMergeSink`

**中文名称:** LogicalIceberg合并SinkToPhysicalIceberg合并Sink

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.3.6 `LogicalRepeatToPhysicalRepeat`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.3.7 `LogicalIcebergTableSinkToPhysicalIcebergTableSink`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.3.8 `LogicalCTEConsumerToPhysicalCTEConsumer`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.3.9 `LogicalIntersectToPhysicalIntersect`

**中文名称:** Logical交集ToPhysical交集

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.3.10 `LogicalPartitionTopNToPhysicalPartitionTopN`

**功能描述:** 将排序+Limit转换为TopN操作

**优化目标:** 避免全排序，使用堆获取TopN

---

#### 2.3.11 `LogicalCTEProducerToPhysicalCTEProducer`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.3.12 `LogicalFilterToPhysicalFilter`

**中文名称:** Logical过滤ToPhysical过滤

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.3.13 `LogicalTVFTableSinkToPhysicalTVFTableSink`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.3.14 `LogicalLimitToPhysicalLimit`

**功能描述:** 将Limit操作下推到数据源

**优化目标:** 减少数据传输

---

#### 2.3.15 `LogicalJoinToHashJoin`

**功能描述:** 使用哈希表实现连接

**优化目标:** O(n+m)时间复杂度的连接

---

#### 2.3.16 `LogicalDeferMaterializeOlapScanToPhysicalDeferMaterializeOlapScan`

**中文名称:** LogicalDeferMaterializeOlap扫描ToPhysicalDeferMaterializeOlap扫描

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.3.17 `LogicalOdbcScanToPhysicalOdbcScan`

**中文名称:** LogicalOdbc扫描ToPhysicalOdbc扫描

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.3.18 `LogicalExceptToPhysicalExcept`

**中文名称:** Logical差集ToPhysical差集

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.3.19 `LogicalCTEAnchorToPhysicalCTEAnchor`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.3.20 `AggregateStrategies`

**中文名称:** 聚合Strategies

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.3.21 `LogicalRecursiveUnionAnchorToPhysicalRecursiveUnionAnchor`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.3.22 `LogicalUnionToPhysicalUnion`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.3.23 `LogicalEmptyRelationToPhysicalEmptyRelation`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.3.24 `SplitAggWithoutDistinct`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.3.25 `LogicalGenerateToPhysicalGenerate`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.3.26 `LogicalTVFRelationToPhysicalTVFRelation`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.3.27 `LogicalBlackholeSinkToPhysicalBlackholeSink`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.3.28 `LogicalHudiScanToPhysicalHudiScan`

**中文名称:** LogicalHudi扫描ToPhysicalHudi扫描

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.3.29 `SplitAggMultiPhaseWithoutGbyKey`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.3.30 `LogicalRecursiveUnionProducerToPhysicalRecursiveUnionProducer`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.3.31 `LogicalFileScanToPhysicalFileScan`

**中文名称:** LogicalFile扫描ToPhysicalFile扫描

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.3.32 `SplitAggMultiPhase`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 统计信息

---

#### 2.3.33 `LogicalWorkTableReferenceToPhysicalWorkTableReference`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.3.34 `LogicalProjectToPhysicalProject`

**中文名称:** Logical投影ToPhysical投影

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.3.35 `LogicalOneRowRelationToPhysicalOneRowRelation`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.3.36 `LogicalTopNToPhysicalTopN`

**功能描述:** 将排序+Limit转换为TopN操作

**优化目标:** 避免全排序，使用堆获取TopN

---

#### 2.3.37 `SplitAggBaseRule`

**中文名称:** SplitAggBase

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.3.38 `LogicalJdbcTableSinkToPhysicalJdbcTableSink`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.3.39 `LogicalWindowToPhysicalWindow`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.3.40 `LogicalEsScanToPhysicalEsScan`

**中文名称:** LogicalEs扫描ToPhysicalEs扫描

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.3.41 `LogicalSortToPhysicalQuickSort`

**中文名称:** Logical排序ToPhysicalQuick排序

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.3.42 `LogicalOlapTableSinkToPhysicalOlapTableSink`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.3.43 `LogicalFileSinkToPhysicalFileSink`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.3.44 `LogicalDeferMaterializeResultSinkToPhysicalDeferMaterializeResultSink`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.3.45 `LogicalIcebergDeleteSinkToPhysicalIcebergDeleteSink`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.3.46 `LogicalJdbcScanToPhysicalJdbcScan`

**中文名称:** LogicalJdbc扫描ToPhysicalJdbc扫描

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.3.47 `for`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.3.48 `LogicalJoinToNestedLoopJoin`

**功能描述:** 使用嵌套循环实现连接

**优化目标:** 适用于小表连接

---

#### 2.3.49 `LogicalResultSinkToPhysicalResultSink`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.3.50 `LogicalRecursiveUnionToPhysicalRecursiveUnion`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.3.51 `LogicalOlapScanToPhysicalOlapScan`

**中文名称:** LogicalOlap扫描ToPhysicalOlap扫描

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.3.52 `LogicalHiveTableSinkToPhysicalHiveTableSink`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.3.53 `LogicalAssertNumRowsToPhysicalAssertNumRows`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.3.54 `for`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

### 2.4 重写规则 (Rewrite)

> 共 191 条规则


#### 2.4.1 `DistinctAggStrategySelector`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 统计信息

---

#### 2.4.2 `SimplifyEncodeDecode`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.3 `PushDownTopNThroughJoin`

**功能描述:** 将排序+Limit转换为TopN操作

**优化目标:** 避免全排序，使用堆获取TopN

---

#### 2.4.4 `EliminateNullAwareLeftAntiJoin`

**中文名称:** 消除NullAwareLeftAnti连接

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.5 `PushDownAggThroughJoinOnPkFk`

**中文名称:** 下推AggThrough连接OnPkFk

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.4.6 `PushDownTopNThroughWindow`

**功能描述:** 将排序+Limit转换为TopN操作

**优化目标:** 避免全排序，使用堆获取TopN

---

#### 2.4.7 `ExtractFilterFromCrossJoin`

**中文名称:** Extract过滤FromCross连接

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.8 `ReduceAggregateChildOutputRows`

**中文名称:** Reduce聚合ChildOutputRows

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.9 `PushDownAliasThroughJoin`

**中文名称:** 下推AliasThrough连接

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.10 `InferJoinNotNull`

**中文名称:** Infer连接NotNull

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.11 `QueryPartitionCollector`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.12 `InferPredicates`

**中文名称:** Infer谓词s

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.13 `UnCorrelatedApplyProjectFilter`

**中文名称:** UnCorrelatedApply投影过滤

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.14 `CreatePartitionTopNFromWindow`

**功能描述:** 将排序+Limit转换为TopN操作

**优化目标:** 避免全排序，使用堆获取TopN

---

#### 2.4.15 `PullUpCteAnchor`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.16 `CheckAndStandardizeWindowFunctionAndFrame`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.17 `EliminateAggregate`

**中文名称:** 消除聚合

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.18 `RewriteSearchToSlots`

**中文名称:** 重写SearchToSlots

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 查询重写优化

---

#### 2.4.19 `CheckPrivileges`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.20 `LimitAggToTopNAgg`

**功能描述:** 将Limit操作下推到数据源

**优化目标:** 减少数据传输

---

#### 2.4.21 `PushDownJoinOnAssertNumRows`

**中文名称:** 下推连接OnAssertNumRows

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.22 `PushDownProject`

**功能描述:** 将投影操作下推，只读取需要的列

**优化目标:** 减少列扫描，降低IO和内存

---

#### 2.4.23 `PruneEmptyPartition`

**中文名称:** 裁剪EmptyPartition

**关系代数表达:**
```
π_{A}(R) → π_{A'}(R) where A' ⊆ A
```

---

#### 2.4.24 `CollectCteConsumerOutput`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.25 `ScalarApplyToJoin`

**中文名称:** ScalarApplyTo连接

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.26 `CheckMultiDistinct`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.27 `InferFilterNotNull`

**中文名称:** Infer过滤NotNull

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.28 `AdjustConjunctsReturnType`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.29 `DecoupleEncodeDecode`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.30 `PushDownFilterThroughJoin`

**中文名称:** 下推过滤Through连接

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.31 `EliminateGroupBy`

**中文名称:** 消除GroupBy

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.4.32 `PushDownFilterThroughWindow`

**中文名称:** 下推过滤ThroughWindow

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.33 `MaxMinFilterPushDown`

**中文名称:** MaxMin过滤下推

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.34 `TransposeSemiJoinAgg`

**中文名称:** 转置Semi连接Agg

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.35 `StatsDerive`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 统计信息

---

#### 2.4.36 `for`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.37 `MergeSetOperationsExcept`

**中文名称:** 合并SetOperations差集

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.38 `do`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.4.39 `CheckDataTypes`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.40 `PushDownEncodeSlot`

**中文名称:** 下推EncodeSlot

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.41 `PruneOlapScanPartition`

**中文名称:** 裁剪Olap扫描Partition

**关系代数表达:**
```
π_{A}(R) → π_{A'}(R) where A' ⊆ A
```

---

#### 2.4.42 `MergeOneRowRelationIntoUnion`

**中文名称:** 合并OneRowRelationIntoUnion

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.43 `PushDownTopNDistinctThroughJoin`

**功能描述:** 将排序+Limit转换为TopN操作

**优化目标:** 避免全排序，使用堆获取TopN

---

#### 2.4.44 `OperativeColumnDerive`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.4.45 `PushDownFilterThroughAggregation`

**中文名称:** 下推过滤ThroughAggregation

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.46 `EliminateSortUnderSubqueryOrView`

**中文名称:** 消除排序Under子查询OrView

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.47 `PushDownLimit`

**功能描述:** 将Limit操作下推到数据源

**优化目标:** 减少数据传输

---

#### 2.4.48 `JoinExtractOrFromCaseWhen`

**中文名称:** 连接ExtractOrFromCaseWhen

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.49 `UnCorrelatedApplyFilter`

**中文名称:** UnCorrelatedApply过滤

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.50 `EliminateGroupByKey`

**中文名称:** 消除GroupByKey

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.4.51 `SkipSimpleExprs`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.52 `EliminateAggCaseWhen`

**中文名称:** 消除AggCaseWhen

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.53 `AddProjectForJoin`

**中文名称:** Add投影For连接

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.54 `NormalizeToSlot`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.55 `PushDownFilterThroughProject`

**功能描述:** 将投影操作下推，只读取需要的列

**优化目标:** 减少列扫描，降低IO和内存

---

#### 2.4.56 `NormalizeSort`

**中文名称:** Normalize排序

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.57 `PushDownFilterIntoSchemaScan`

**中文名称:** 下推过滤IntoSchema扫描

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.58 `for`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.59 `PushDownScoreTopNIntoOlapScan`

**功能描述:** 将排序+Limit转换为TopN操作

**优化目标:** 避免全排序，使用堆获取TopN

---

#### 2.4.60 `CheckScoreUsage`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.61 `SplitLimit`

**功能描述:** 将Limit操作下推到数据源

**优化目标:** 减少数据传输

---

#### 2.4.62 `InferPredicateByReplace`

**中文名称:** Infer谓词ByReplace

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.4.63 `MergePercentileToArray`

**中文名称:** 合并PercentileToArray

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.64 `AddProjectForUniqueFunction`

**中文名称:** Add投影ForUniqueFunction

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.65 `TransposeSemiJoinLogicalJoin`

**中文名称:** 转置Semi连接Logical连接

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.66 `MergeTopNs`

**功能描述:** 将排序+Limit转换为TopN操作

**优化目标:** 避免全排序，使用堆获取TopN

---

#### 2.4.67 `LogicalResultSinkToShortCircuitPointQuery`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.68 `OrExpansion`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.69 `EliminateSortUnderApply`

**中文名称:** 消除排序UnderApply

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.70 `PushDownTopNThroughUnion`

**功能描述:** 将排序+Limit转换为TopN操作

**优化目标:** 避免全排序，使用堆获取TopN

---

#### 2.4.71 `PushDownFilterThroughSort`

**中文名称:** 下推过滤Through排序

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.72 `AddDefaultLimit`

**功能描述:** 将Limit操作下推到数据源

**优化目标:** 减少数据传输

---

#### 2.4.73 `ClearContextStatus`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.74 `MergeProjectable`

**中文名称:** 合并投影able

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.75 `PushDownFilterThroughRepeat`

**中文名称:** 下推过滤ThroughRepeat

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.76 `CountDistinctRewrite`

**中文名称:** CountDistinct重写

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 查询重写优化

---

#### 2.4.77 `LimitSortToTopN`

**功能描述:** 将Limit操作下推到数据源

**优化目标:** 减少数据传输

---

#### 2.4.78 `PushDownVectorTopNIntoOlapScan`

**功能描述:** 将排序+Limit转换为TopN操作

**优化目标:** 避免全排序，使用堆获取TopN

---

#### 2.4.79 `NestedColumnPruning`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.80 `ExprIdRewriter`

**中文名称:** ExprId重写r

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 查询重写优化

---

#### 2.4.81 `PullUpJoinFromUnionAll`

**中文名称:** PullUp连接FromUnionAll

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.82 `UnCorrelatedApplyAggregateFilter`

**中文名称:** UnCorrelatedApply聚合过滤

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.83 `PushDownLimitDistinctThroughJoin`

**功能描述:** 将Limit操作下推到数据源

**优化目标:** 减少数据传输

---

#### 2.4.84 `ConvertInnerOrCrossJoin`

**中文名称:** ConvertInnerOrCross连接

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.85 `DistinctWindowExpression`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 标量表达式优化

---

#### 2.4.86 `EliminateDedupJoinCondition`

**中文名称:** 消除Dedup连接Condition

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.87 `PushDownTopNDistinctThroughUnion`

**功能描述:** 将排序+Limit转换为TopN操作

**优化目标:** 避免全排序，使用堆获取TopN

---

#### 2.4.88 `PushDownAggThroughJoinOneSide`

**中文名称:** 下推AggThrough连接OneSide

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.89 `SimplifyAggGroupBy`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.90 `PushDownFilterThroughPartitionTopN`

**功能描述:** 将排序+Limit转换为TopN操作

**优化目标:** 避免全排序，使用堆获取TopN

---

#### 2.4.91 `PushProjectThroughUnion`

**中文名称:** Push投影ThroughUnion

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.92 `CheckRestorePartition`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.93 `PushDownAggWithDistinctThroughJoinOneSide`

**中文名称:** 下推AggWithDistinctThrough连接OneSide

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.94 `ConstantPropagation`

**中文名称:** 常量Propagation

**关系代数表达:**
```
expr(const) → const_value
```

**依赖资源:** 物理属性

---

#### 2.4.95 `ConvertOuterJoinToAntiJoin`

**中文名称:** ConvertOuter连接ToAnti连接

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.96 `TransposeSemiJoinAggProject`

**中文名称:** 转置Semi连接Agg投影

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.97 `SlotTypeReplacer`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.98 `DeferMaterializeTopNResult`

**功能描述:** 将排序+Limit转换为TopN操作

**优化目标:** 避免全排序，使用堆获取TopN

---

#### 2.4.99 `SaltJoin`

**中文名称:** Salt连接

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.100 `EliminateGroupByKeyByUniform`

**中文名称:** 消除GroupByKeyByUniform

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.4.101 `EliminateJoinCondition`

**中文名称:** 消除连接Condition

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.102 `PullUpProjectUnderLimit`

**功能描述:** 将Limit操作下推到数据源

**优化目标:** 减少数据传输

---

#### 2.4.103 `MergeProjects`

**中文名称:** 合并投影s

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.104 `MergeFilters`

**中文名称:** 合并过滤s

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.105 `PushDownExpressionsInHashCondition`

**中文名称:** 下推ExpressionsInHashCondition

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 标量表达式优化

---

#### 2.4.106 `EliminateOrderByKey`

**中文名称:** 消除OrderByKey

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.4.107 `FindHashConditionForJoin`

**中文名称:** FindHashConditionFor连接

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.108 `MergeLimits`

**功能描述:** 将Limit操作下推到数据源

**优化目标:** 减少数据传输

---

#### 2.4.109 `MultiJoin`

**中文名称:** Multi连接

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.110 `EliminateEmptyRelation`

**中文名称:** 消除EmptyRelation

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.111 `EliminateSort`

**中文名称:** 消除排序

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.112 `MergeAggregate`

**中文名称:** 合并聚合

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.113 `PushDownVirtualColumnsIntoOlapScan`

**中文名称:** 下推VirtualColumnsIntoOlap扫描

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 代价模型, 物理属性

---

#### 2.4.114 `EliminateNotNull`

**中文名称:** 消除NotNull

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.115 `AccessPathExpressionCollector`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 标量表达式优化

---

#### 2.4.116 `PullUpCorrelatedFilterUnderApplyAggregateProject`

**中文名称:** PullUpCorrelated过滤UnderApply聚合投影

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.117 `PushDownAggThroughJoin`

**中文名称:** 下推AggThrough连接

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.118 `PruneFileScanPartition`

**中文名称:** 裁剪File扫描Partition

**关系代数表达:**
```
π_{A}(R) → π_{A'}(R) where A' ⊆ A
```

---

#### 2.4.119 `PruneOlapScanTablet`

**中文名称:** 裁剪Olap扫描Tablet

**关系代数表达:**
```
π_{A}(R) → π_{A'}(R) where A' ⊆ A
```

---

#### 2.4.120 `PullUpProjectUnderApply`

**中文名称:** PullUp投影UnderApply

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.121 `MergeGenerates`

**中文名称:** 合并Generates

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.122 `PushProjectIntoUnion`

**中文名称:** Push投影IntoUnion

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.123 `RewriteSimpleAggToConstantRule`

**中文名称:** 重写SimpleAggTo常量

**关系代数表达:**
```
expr(const) → const_value
```

**优化目标:** 查询重写优化

**依赖资源:** 统计信息

---

#### 2.4.124 `TransposeSemiJoinLogicalJoinProject`

**中文名称:** 转置Semi连接Logical连接投影

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.125 `PullUpProjectUnderTopN`

**功能描述:** 将排序+Limit转换为TopN操作

**优化目标:** 避免全排序，使用堆获取TopN

---

#### 2.4.126 `CTEInline`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.127 `PushDownFilterThroughSetOperation`

**中文名称:** 下推过滤ThroughSetOperation

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.128 `AccessPathPlanCollector`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.129 `SetPreAggStatus`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.130 `EliminateLimitUnderApply`

**功能描述:** 将Limit操作下推到数据源

**优化目标:** 减少数据传输

---

#### 2.4.131 `CheckMatchExpression`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 标量表达式优化

---

#### 2.4.132 `ForeignKeyContext`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.133 `CollectPredicateOnScan`

**中文名称:** Collect谓词On扫描

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 统计信息

---

#### 2.4.134 `MergeSetOperations`

**中文名称:** 合并SetOperations

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.135 `EliminateSemiJoin`

**中文名称:** 消除Semi连接

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.136 `PushFilterInsideJoin`

**中文名称:** Push过滤Inside连接

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.137 `DistinctAggregateRewriter`

**中文名称:** Distinct聚合重写r

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 查询重写优化

**依赖资源:** 统计信息

---

#### 2.4.138 `EliminateUnnecessaryProject`

**中文名称:** 消除Unnecessary投影

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.139 `RewriteCteChildren`

**中文名称:** 重写CteChildren

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 查询重写优化

---

#### 2.4.140 `PushDownFilterThroughGenerate`

**中文名称:** 下推过滤ThroughGenerate

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.141 `InferSetOperatorDistinct`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.142 `EliminateAssertNumRows`

**中文名称:** 消除AssertNumRows

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.143 `PushDownLimitDistinctThroughUnion`

**功能描述:** 将Limit操作下推到数据源

**优化目标:** 减少数据传输

---

#### 2.4.144 `InferAggNotNull`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.145 `AccessPathInfo`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.146 `PushDownProjectThroughLimit`

**功能描述:** 将投影操作下推，只读取需要的列

**优化目标:** 减少列扫描，降低IO和内存

---

#### 2.4.147 `AdjustNullable`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.148 `AggScalarSubQueryToWindowFunction`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.149 `EliminateJoinByUnique`

**中文名称:** 消除连接ByUnique

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.4.150 `EliminateOuterJoin`

**中文名称:** 消除Outer连接

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.151 `DecomposeRepeatWithPreAggregation`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 统计信息

---

#### 2.4.152 `SemiJoinCommute`

**功能描述:** 利用连接交换律改变连接顺序

**优化目标:** 选择更优的连接顺序

---

#### 2.4.153 `PushDownJoinOtherCondition`

**中文名称:** 下推连接OtherCondition

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.154 `SplitMultiDistinctStrategy`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.155 `EliminateFilter`

**中文名称:** 消除过滤

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.156 `InApplyToJoin`

**中文名称:** InApplyTo连接

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.157 `ProjectOtherJoinConditionForNestedLoopJoin`

**功能描述:** 使用嵌套循环实现连接

**优化目标:** 适用于小表连接

---

#### 2.4.158 `PushDownMatchProjectionAsVirtualColumn`

**功能描述:** 将投影操作下推，只读取需要的列

**优化目标:** 减少列扫描，降低IO和内存

---

#### 2.4.159 `CountLiteralRewrite`

**中文名称:** CountLiteral重写

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 查询重写优化

---

#### 2.4.160 `BuildAggForUnion`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.161 `EliminateConstHashJoinCondition`

**功能描述:** 使用哈希表实现连接

**优化目标:** O(n+m)时间复杂度的连接

---

#### 2.4.162 `ReorderJoin`

**中文名称:** 重排序连接

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.163 `InferInPredicateFromOr`

**中文名称:** InferIn谓词FromOr

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.164 `VariantSubPathPruning`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.4.165 `PushDownUnnestInProject`

**功能描述:** 将投影操作下推，只读取需要的列

**优化目标:** 减少列扫描，降低IO和内存

---

#### 2.4.166 `ColumnPruning`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.167 `PullUpProjectBetweenTopNAndAgg`

**功能描述:** 将排序+Limit转换为TopN操作

**优化目标:** 避免全排序，使用堆获取TopN

---

#### 2.4.168 `PullUpPredicates`

**中文名称:** PullUp谓词s

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.169 `EliminateJoinByFK`

**中文名称:** 消除连接ByFK

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.170 `InitJoinOrder`

**中文名称:** Init连接Order

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.171 `EliminateLimit`

**功能描述:** 将Limit操作下推到数据源

**优化目标:** 减少数据传输

---

#### 2.4.172 `SkewJoin`

**中文名称:** Skew连接

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 统计信息

---

#### 2.4.173 `ExtractAndNormalizeWindowExpression`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 标量表达式优化

---

#### 2.4.174 `SumLiteralRewrite`

**中文名称:** SumLiteral重写

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 查询重写优化

---

#### 2.4.175 `ExtractSingleTableExpressionFromDisjunction`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 标量表达式优化

---

#### 2.4.176 `ExistsApplyToJoin`

**中文名称:** ExistsApplyTo连接

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.177 `PushDownDistinctThroughJoin`

**中文名称:** 下推DistinctThrough连接

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 统计信息

---

#### 2.4.178 `EliminateOrderByConstant`

**中文名称:** 消除OrderBy常量

**关系代数表达:**
```
expr(const) → const_value
```

---

#### 2.4.179 `CollectFilterAboveConsumer`

**中文名称:** Collect过滤AboveConsumer

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.180 `SimplifyWindowExpression`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 标量表达式优化

**依赖资源:** 物理属性

---

#### 2.4.181 `InlineLogicalView`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.182 `RecordPlanForMvPreRewrite`

**中文名称:** RecordPlanForMvPre重写

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 查询重写优化

---

#### 2.4.183 `MultiDistinctFunctionStrategy`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.184 `PushCountIntoUnionAll`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.185 `PushDownAggregation`

**中文名称:** 下推Aggregation

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 物理属性

---

#### 2.4.186 `EagerAggRewriter`

**中文名称:** EagerAgg重写r

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 查询重写优化

**依赖资源:** 统计信息

---

#### 2.4.187 `PushDownAggContext`

**中文名称:** 下推AggContext

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.188 `BatchRewriteRuleFactory`

**中文名称:** Batch重写Factory

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 查询重写优化

---

#### 2.4.189 `EliminateUselessPlanUnderApply`

**中文名称:** 消除UselessPlanUnderApply

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.190 `ApplyToJoin`

**中文名称:** ApplyTo连接

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.4.191 `CorrelateApplyToUnCorrelateApply`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

### 2.5 表达式规则 (Expression)

> 共 88 条规则


#### 2.5.1 `ExpressionPatternMatchRule`

**中文名称:** ExpressionPatternMatch

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 标量表达式优化

---

#### 2.5.2 `QueryColumnCollector`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 统计信息

---

#### 2.5.3 `ExpressionNormalizationAndOptimization`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 标量表达式优化

---

#### 2.5.4 `ExpressionBottomUpRewriter`

**中文名称:** ExpressionBottomUp重写r

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 查询重写优化

---

#### 2.5.5 `ExpressionOptimization`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 标量表达式优化

---

#### 2.5.6 `ExpressionTraverseListenerMapping`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 标量表达式优化

---

#### 2.5.7 `ExpressionPatternRuleFactory`

**中文名称:** ExpressionPatternFactory

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 标量表达式优化

---

#### 2.5.8 `ExpressionNormalization`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 标量表达式优化

---

#### 2.5.9 `ExpressionMatchingAction`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 标量表达式优化

---

#### 2.5.10 `ExpressionTraverseListener`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 标量表达式优化

---

#### 2.5.11 `ExpressionTraverseListenerFactory`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 标量表达式优化

---

#### 2.5.12 `of`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.5.13 `ExpressionListenerMatcher`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 标量表达式优化

---

#### 2.5.14 `ExpressionRuleExecutor`

**中文名称:** ExpressionExecutor

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 标量表达式优化

---

#### 2.5.15 `CheckLegalityAfterRewrite`

**中文名称:** CheckLegalityAfter重写

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 查询重写优化

---

#### 2.5.16 `MergeGuardExpr`

**中文名称:** 合并GuardExpr

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.5.17 `ExpressionRewriteContext`

**中文名称:** Expression重写Context

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 查询重写优化

---

#### 2.5.18 `of`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.5.19 `ExpressionRewrite`

**中文名称:** Expression重写

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 查询重写优化

---

#### 2.5.20 `ExpressionPatternMatcher`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 标量表达式优化

---

#### 2.5.21 `NullableDependentExpressionRewrite`

**中文名称:** NullableDependentExpression重写

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 查询重写优化

---

#### 2.5.22 `ExpressionMatchingContext`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 标量表达式优化

---

#### 2.5.23 `ExpressionRuleType`

**中文名称:** ExpressionType

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 标量表达式优化

---

#### 2.5.24 `CheckCast`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.5.25 `PartitionPredicateToRange`

**中文名称:** Partition谓词ToRange

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.5.26 `SimplifyConditionalFunction`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.5.27 `ArrayContainToArrayOverlap`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.5.28 `RangeInference`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.5.29 `PushIntoCaseWhenBranch`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**依赖资源:** 代价模型

---

#### 2.5.30 `SimplifyArithmeticRule`

**中文名称:** SimplifyArithmetic

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.5.31 `NormalizeBinaryPredicatesRule`

**中文名称:** NormalizeBinary谓词s

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.5.32 `InPredicateExtractNonConstant`

**中文名称:** In谓词ExtractNon常量

**关系代数表达:**
```
expr(const) → const_value
```

---

#### 2.5.33 `DistinctPredicatesRule`

**中文名称:** Distinct谓词s

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.5.34 `ColumnRange`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.5.35 `SimplifyTimeFieldFromUnixtime`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.5.36 `SimplifyEqualBooleanLiteral`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.5.37 `FoldConstantRule`

**中文名称:** 折叠常量

**关系代数表达:**
```
expr(const) → const_value
```

---

#### 2.5.38 `RangePartitionValueIterator`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.5.39 `OneRangePartitionEvaluator`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.5.40 `ReplaceVariableByLiteral`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.5.41 `InPredicateToEqualToRule`

**中文名称:** In谓词ToEqualTo

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.5.42 `implements`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 将逻辑算子转换为物理算子

---

#### 2.5.43 `CondReplaceNullWithFalse`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.5.44 `TimestampToAddTime`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.5.45 `TopnToMax`

**功能描述:** 将排序+Limit转换为TopN操作

**优化目标:** 避免全排序，使用堆获取TopN

---

#### 2.5.46 `PartitionPruner`

**中文名称:** Partition裁剪r

**关系代数表达:**
```
π_{A}(R) → π_{A'}(R) where A' ⊆ A
```

---

#### 2.5.47 `DateFunctionRewrite`

**中文名称:** DateFunction重写

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 查询重写优化

---

#### 2.5.48 `ColumnBound`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.5.49 `DigitalMaskingConvert`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.5.50 `MergeDateTrunc`

**中文名称:** 合并DateTrunc

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.5.51 `NestedCaseWhenCondToLiteral`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.5.52 `CaseWhenToIf`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.5.53 `MedianConvert`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.5.54 `ExtractCommonFactorRule`

**中文名称:** ExtractCommonFactor

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.5.55 `FoldConstantRuleOnBE`

**中文名称:** 折叠常量OnBE

**关系代数表达:**
```
expr(const) → const_value
```

---

#### 2.5.56 `SimplifyComparisonPredicate`

**中文名称:** SimplifyComparison谓词

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.5.57 `CaseWhenToCompoundPredicate`

**中文名称:** CaseWhenToCompound谓词

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.5.58 `implements`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 将逻辑算子转换为物理算子

---

#### 2.5.59 `SimplifySelfComparison`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.5.60 `SimplifyArithmeticComparisonRule`

**中文名称:** SimplifyArithmeticComparison

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.5.61 `NormalizeStructElement`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.5.62 `FoldConstantRuleOnFE`

**中文名称:** 折叠常量OnFE

**关系代数表达:**
```
expr(const) → const_value
```

---

#### 2.5.63 `InPredicateDedup`

**中文名称:** In谓词Dedup

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.5.64 `BetweenToEqual`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.5.65 `RewriteDefaultExpression`

**中文名称:** 重写DefaultExpression

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 查询重写优化

---

#### 2.5.66 `NullSafeEqualToEqual`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.5.67 `ConditionRewrite`

**中文名称:** Condition重写

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 查询重写优化

---

#### 2.5.68 `PartitionItemToRange`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.5.69 `OrToIn`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.5.70 `SupportJavaDateFormatter`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.5.71 `PredicateRewriteForPartitionPrune`

**中文名称:** 谓词重写ForPartition裁剪

**关系代数表达:**
```
π_{A}(R) → π_{A'}(R) where A' ⊆ A
```

**优化目标:** 查询重写优化

---

#### 2.5.72 `OneListPartitionEvaluator`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.5.73 `LikeToEqualRewrite`

**中文名称:** LikeToEqual重写

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

**优化目标:** 查询重写优化

---

#### 2.5.74 `OnePartitionEvaluator`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.5.75 `LogToLn`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.5.76 `ConvertAggStateCast`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.5.77 `SortedPartitionRanges`

**中文名称:** 排序edPartitionRanges

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.5.78 `PartitionRangeExpander`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.5.79 `ConcatWsMultiArrayToOne`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.5.80 `SimplifyNotExprRule`

**中文名称:** SimplifyNotExpr

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.5.81 `SimplifyInPredicate`

**中文名称:** SimplifyIn谓词

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.5.82 `UnknownPartitionEvaluator`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.5.83 `SimplifyCastRule`

**中文名称:** SimplifyCast

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.5.84 `MultiColumnBound`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.5.85 `SimplifyConflictCompound`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.5.86 `PartitionPruneExpressionExtractor`

**中文名称:** Partition裁剪ExpressionExtractor

**关系代数表达:**
```
π_{A}(R) → π_{A'}(R) where A' ⊆ A
```

**优化目标:** 标量表达式优化

---

#### 2.5.87 `TrySimplifyPredicateWithMarkJoinSlot`

**中文名称:** TrySimplify谓词WithMark连接Slot

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

#### 2.5.88 `PartitionSlotInput`

**关系代数表达:**
```
Pattern(R) → Transformed(R)
```

---

## 🔬 三、优化原理总结

### 3.1 优化目标分布

| 优化目标 | 规则数量 |
|----------|----------|

| 标量表达式优化 | 25 |
| 查询重写优化 | 23 |
| 避免全排序，使用堆获取TopN | 20 |
| 减少数据传输 | 16 |
| 减少列扫描，降低IO和内存 | 7 |
| 语义分析和绑定 | 4 |
| 选择更优的连接顺序 | 2 |
| O(n+m)时间复杂度的连接 | 2 |
| 适用于小表连接 | 2 |
| 将逻辑算子转换为物理算子 | 2 |

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

| 规则类别 | Doris | StarRocks | 说明 |
|----------|-------|-----------|------|
| 分析规则 | 48 | - | 绑定和语义分析 |
| 探索规则 | 82 | - | 计划空间探索 |
| 重写规则 | 191 | 224 | 逻辑等价变换 |
| 实现规则 | 54 | 45 | 物理实现选择 |
| 表达式规则 | 88 | - | 标量优化 |

### 4.2 特点总结

**Doris优势:**
- 规则最丰富，覆盖最全面
- 分类细致，职责清晰
- 表达式优化独立

**Nereids架构特点:**
- 现代Cascades实现
- 与旧优化器共存


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
