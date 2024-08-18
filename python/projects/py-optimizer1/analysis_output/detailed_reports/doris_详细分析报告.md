# Doris 优化器详细分析报告

**生成时间:** 2026-04-06 12:02:08

**分析源码路径:** /home/lism/work/doris

## 一、概述

### 1.1 引擎基本信息

| 属性 | 值 |
|------|----|

| 引擎类型 | columnar_olap |

| 优化器风格 | cascades |

| 主要编程语言 | Java |

| 规则总数 | 463 |


### 1.2 优化器特点

- Nereids optimizer - Cascades-style with memo
- Rules organized in rules/analysis, rules/exploration, rules/implementation, rules/rewrite
- Cost model in cost/ directory
- CascadesContext for memo management
- Java-based optimizer in FE (Frontend)
- Evolved from old optimizer to Nereids

## 二、优化器架构

### 2.1 核心组件


**核心类:**

- `NereidsPlanner.java`: Nereids优化器主入口
- `CascadesContext.java`: Cascades上下文，管理Memo
- `PlanContext.java`: 计划上下文
- `Rule.java`: 规则基类
- `RuleSet.java`: 规则集管理
- **规则系统**: rules/目录按功能分类（分析、探索、实现、重写、表达式）
- **代价模型**: cost/目录包含代价计算
- **统计信息**: statistics/目录包含统计信息
- **分析器**: analyzer/目录包含语义分析

### 2.2 关键文件验证

| 文件 | 存在 |
|------|------|

| CascadesContext.java | ✅ |
| NereidsPlanner.java | ✅ |
| Rule.java | ✅ |

## 三、规则详解

### 3.1 规则统计

| 规则类型 | 数量 |
|----------|------|

| 分析规则 (Analysis) | 48 |
| 探索规则 (Exploration) | 82 |
| 实现规则 (Implementation) | 54 |
| 重写规则 (Rewrite) | 191 |
| 表达式规则 (Expression) | 88 |
| **总计** | **463** |

### 3.2 分析规则

| 序号 | 规则名称 | 类型 | 依赖 |
|------|----------|------|------|

| 1 | `VariableToLiteral` | 其他规则 | - |
| 2 | `for` | 其他规则 | - |
| 3 | `ExpressionAnalyzer` | 分析规则 | - |
| 4 | `WindowFunctionChecker` | 其他规则 | - |
| 5 | `CheckPolicy` | 其他规则 | - |
| 6 | `SubExprAnalyzer` | 分析规则 | - |
| 7 | `NormalizeAggregate` | 其他规则 | - |
| 8 | `GetFormatFunctionBinder` | 其他规则 | - |
| 9 | `ProjectToGlobalAggregate` | 其他规则 | - |
| 10 | `ArithmeticFunctionBinder` | 其他规则 | - |
| 11 | `DatetimeFunctionBinder` | 其他规则 | - |
| 12 | `NormalizeRepeat` | 其他规则 | - |
| 13 | `UserAuthentication` | 其他规则 | - |
| 14 | `AvgDistinctToSumDivCount` | 其他规则 | - |
| 15 | `CheckSearchUsage` | 其他规则 | - |
| 16 | `is` | 其他规则 | - |
| 17 | `LogicalSubQueryAliasToLogicalProject` | 其他规则 | - |
| 18 | `FoldConstantForSqlCache` | 其他规则 | - |
| 19 | `HavingToFilter` | 其他规则 | - |
| 20 | `LeadingJoin` | 其他规则 | - |
| 21 | `BindSkewExpr` | 其他规则 | - |
| 22 | `BindSink` | 其他规则 | - |
| 23 | `AdjustAggregateNullableForEmptySet` | 其他规则 | - |
| 24 | `CompressedMaterialize` | 其他规则 | - |
| 25 | `AddInitMaterializationHook` | 其他规则 | - |
| 26 | `EliminateLogicalPreAggOnHint` | 其他规则 | - |
| 27 | `ColumnAliasGenerator` | 其他规则 | - |
| 28 | `FillUpMissingSlots` | 其他规则 | - |
| 29 | `for` | 其他规则 | - |
| 30 | `ReplaceExpressionByChildOutput` | 表达式规则 | - |
| 31 | `CollectSubQueryAlias` | 其他规则 | - |
| 32 | `EliminateLogicalSelectHint` | 其他规则 | - |
| 33 | `AnalyzeCTE` | 分析规则 | - |
| 34 | `OneRowRelationExtractAggregate` | 其他规则 | - |
| 35 | `NormalizeGenerate` | 其他规则 | - |
| 36 | `CollectOneLevelRelation` | 其他规则 | - |
| 37 | `FillUpQualifyMissingSlot` | 其他规则 | - |
| 38 | `CheckAnalysis` | 分析规则 | - |
| 39 | `QualifyToFilter` | 其他规则 | - |
| 40 | `CheckAfterRewrite` | 转换规则 | - |
| 41 | `OneRowRelationToProject` | 其他规则 | - |
| 42 | `BindExpression` | 表达式规则 | - |
| 43 | `BindRelation` | 其他规则 | - |
| 44 | `SubqueryToApply` | 其他规则 | - |
| 45 | `EliminateDistinctConstant` | 其他规则 | - |
| 46 | `ProjectWithDistinctToAggregate` | 其他规则 | - |
| 47 | `CollectJoinConstraint` | 其他规则 | - |
| 48 | `CollectRelation` | 其他规则 | - |

### 3.2 探索规则

> 共 82 条规则，仅展示前50条

| 序号 | 规则名称 | 类型 | 依赖 |
|------|----------|------|------|

| 1 | `CBOUtils` | 其他规则 | - |
| 2 | `EagerGroupBy` | 其他规则 | - |
| 3 | `TransposeAggSemiJoinProject` | 其他规则 | - |
| 4 | `for` | 其他规则 | - |
| 5 | `TransposeAggSemiJoin` | 其他规则 | - |
| 6 | `EagerGroupByCount` | 其他规则 | - |
| 7 | `IntersectReorder` | 其他规则 | 统计信息 |
| 8 | `for` | 其他规则 | - |
| 9 | `MergeProjectsCBO` | 其他规则 | - |
| 10 | `EagerCount` | 其他规则 | - |
| 11 | `EagerSplit` | 其他规则 | - |
| 12 | `LogicalJoinSemiJoinTransposeProject` | 其他规则 | - |
| 13 | `SemiJoinSemiJoinTransposeProject` | 其他规则 | - |
| 14 | `InnerJoinLAsscomProject` | 其他规则 | 统计信息 |
| 15 | `PushDownProjectThroughSemiJoin` | 其他规则 | - |
| 16 | `InnerJoinLeftAssociateProject` | 其他规则 | - |
| 17 | `JoinExchangeBothProject` | 其他规则 | - |
| 18 | `OuterJoinAssocProject` | 其他规则 | - |
| 19 | `JoinCommute` | 其他规则 | 统计信息 |
| 20 | `JoinReorderContext` | 其他规则 | - |
| 21 | `InnerJoinRightAssociateProject` | 其他规则 | - |
| 22 | `OuterJoinLAsscomProject` | 其他规则 | - |
| 23 | `PushDownProjectThroughInnerOuterJoin` | 其他规则 | - |
| 24 | `MaterializedViewOnlyScanRule` | 其他规则 | - |
| 25 | `AbstractMaterializedViewAggregateRule` | 其他规则 | - |
| 26 | `SyncMaterializationContext` | 其他规则 | 统计信息 |
| 27 | `EquivalenceClass` | 其他规则 | - |
| 28 | `MaterializedViewTopNJoinRule` | 其他规则 | - |
| 29 | `MaterializedViewAggregateRule` | 其他规则 | - |
| 30 | `MaterializedViewFilterAggregateRule` | 其他规则 | - |
| 31 | `MaterializedViewWindowJoinRule` | 其他规则 | - |
| 32 | `MaterializedViewProjectFilterProjectJoinRule` | 其他规则 | - |
| 33 | `InitMaterializationContextHook` | 其他规则 | 统计信息 |
| 34 | `MaterializedViewFilterProjectAggregateRule` | 其他规则 | - |
| 35 | `MaterializedViewProjectFilterAggregateRule` | 其他规则 | - |
| 36 | `AsyncMaterializationContext` | 其他规则 | 统计信息 |
| 37 | `MaterializedViewLimitJoinRule` | 其他规则 | - |
| 38 | `MaterializedViewTopNScanRule` | 其他规则 | - |
| 39 | `PreMaterializedViewRewriter` | 转换规则 | - |
| 40 | `AbstractMaterializedViewLimitOrTopNRule` | 其他规则 | - |
| 41 | `RelatedTableInfo` | 其他规则 | - |
| 42 | `MaterializedViewLimitAggregateRule` | 其他规则 | - |
| 43 | `Predicates` | 其他规则 | - |
| 44 | `ComparisonResult` | 其他规则 | - |
| 45 | `MaterializedViewProjectJoinRule` | 其他规则 | - |
| 46 | `MaterializedViewFilterScanRule` | 其他规则 | - |
| 47 | `MaterializedViewProjectFilterJoinRule` | 其他规则 | - |
| 48 | `MaterializedViewAggregateOnNoneAggregateRule` | 其他规则 | - |
| 49 | `MaterializedViewLimitScanRule` | 其他规则 | - |
| 50 | `MaterializedViewWindowAggregateRule` | 其他规则 | - |

*...还有 32 条规则未展示*

### 3.2 实现规则

> 共 54 条规则，仅展示前50条

| 序号 | 规则名称 | 类型 | 依赖 |
|------|----------|------|------|

| 1 | `LogicalDictionarySinkToPhysicalDictionarySink` | 其他规则 | 统计信息 |
| 2 | `LogicalDeferMaterializeTopNToPhysicalDeferMaterializeTopN` | 其他规则 | - |
| 3 | `LogicalSchemaScanToPhysicalSchemaScan` | 其他规则 | - |
| 4 | `LogicalMaxComputeTableSinkToPhysicalMaxComputeTableSink` | 其他规则 | - |
| 5 | `LogicalIcebergMergeSinkToPhysicalIcebergMergeSink` | 其他规则 | - |
| 6 | `LogicalRepeatToPhysicalRepeat` | 其他规则 | - |
| 7 | `LogicalIcebergTableSinkToPhysicalIcebergTableSink` | 其他规则 | - |
| 8 | `LogicalCTEConsumerToPhysicalCTEConsumer` | 其他规则 | - |
| 9 | `LogicalIntersectToPhysicalIntersect` | 其他规则 | - |
| 10 | `LogicalPartitionTopNToPhysicalPartitionTopN` | 其他规则 | 统计信息 |
| 11 | `LogicalCTEProducerToPhysicalCTEProducer` | 其他规则 | - |
| 12 | `LogicalFilterToPhysicalFilter` | 其他规则 | - |
| 13 | `LogicalTVFTableSinkToPhysicalTVFTableSink` | 其他规则 | - |
| 14 | `LogicalLimitToPhysicalLimit` | 其他规则 | - |
| 15 | `LogicalJoinToHashJoin` | 其他规则 | - |
| 16 | `LogicalDeferMaterializeOlapScanToPhysicalDeferMaterializeOlapScan` | 其他规则 | - |
| 17 | `LogicalOdbcScanToPhysicalOdbcScan` | 其他规则 | - |
| 18 | `LogicalExceptToPhysicalExcept` | 其他规则 | - |
| 19 | `LogicalCTEAnchorToPhysicalCTEAnchor` | 其他规则 | - |
| 20 | `AggregateStrategies` | 其他规则 | - |
| 21 | `LogicalRecursiveUnionAnchorToPhysicalRecursiveUnionAnchor` | 其他规则 | - |
| 22 | `LogicalUnionToPhysicalUnion` | 其他规则 | - |
| 23 | `LogicalEmptyRelationToPhysicalEmptyRelation` | 其他规则 | - |
| 24 | `SplitAggWithoutDistinct` | 其他规则 | - |
| 25 | `LogicalGenerateToPhysicalGenerate` | 其他规则 | - |
| 26 | `LogicalTVFRelationToPhysicalTVFRelation` | 其他规则 | - |
| 27 | `LogicalBlackholeSinkToPhysicalBlackholeSink` | 其他规则 | - |
| 28 | `LogicalHudiScanToPhysicalHudiScan` | 其他规则 | - |
| 29 | `SplitAggMultiPhaseWithoutGbyKey` | 其他规则 | - |
| 30 | `LogicalRecursiveUnionProducerToPhysicalRecursiveUnionProducer` | 其他规则 | - |
| 31 | `LogicalFileScanToPhysicalFileScan` | 其他规则 | - |
| 32 | `SplitAggMultiPhase` | 其他规则 | 统计信息 |
| 33 | `LogicalWorkTableReferenceToPhysicalWorkTableReference` | 其他规则 | - |
| 34 | `LogicalProjectToPhysicalProject` | 其他规则 | - |
| 35 | `LogicalOneRowRelationToPhysicalOneRowRelation` | 其他规则 | - |
| 36 | `LogicalTopNToPhysicalTopN` | 其他规则 | - |
| 37 | `SplitAggBaseRule` | 其他规则 | - |
| 38 | `LogicalJdbcTableSinkToPhysicalJdbcTableSink` | 其他规则 | - |
| 39 | `LogicalWindowToPhysicalWindow` | 其他规则 | - |
| 40 | `LogicalEsScanToPhysicalEsScan` | 其他规则 | - |
| 41 | `LogicalSortToPhysicalQuickSort` | 其他规则 | - |
| 42 | `LogicalOlapTableSinkToPhysicalOlapTableSink` | 其他规则 | - |
| 43 | `LogicalFileSinkToPhysicalFileSink` | 其他规则 | - |
| 44 | `LogicalDeferMaterializeResultSinkToPhysicalDeferMaterializeResultSink` | 其他规则 | - |
| 45 | `LogicalIcebergDeleteSinkToPhysicalIcebergDeleteSink` | 其他规则 | - |
| 46 | `LogicalJdbcScanToPhysicalJdbcScan` | 其他规则 | - |
| 47 | `for` | 其他规则 | - |
| 48 | `LogicalJoinToNestedLoopJoin` | 其他规则 | - |
| 49 | `LogicalResultSinkToPhysicalResultSink` | 其他规则 | - |
| 50 | `LogicalRecursiveUnionToPhysicalRecursiveUnion` | 其他规则 | - |

*...还有 4 条规则未展示*

### 3.2 重写规则

> 共 191 条规则，仅展示前50条

| 序号 | 规则名称 | 类型 | 依赖 |
|------|----------|------|------|

| 1 | `DistinctAggStrategySelector` | 其他规则 | 统计信息 |
| 2 | `SimplifyEncodeDecode` | 其他规则 | - |
| 3 | `PushDownTopNThroughJoin` | 其他规则 | - |
| 4 | `EliminateNullAwareLeftAntiJoin` | 其他规则 | - |
| 5 | `PushDownAggThroughJoinOnPkFk` | 其他规则 | - |
| 6 | `PushDownTopNThroughWindow` | 其他规则 | - |
| 7 | `ExtractFilterFromCrossJoin` | 其他规则 | - |
| 8 | `ReduceAggregateChildOutputRows` | 其他规则 | - |
| 9 | `PushDownAliasThroughJoin` | 其他规则 | - |
| 10 | `InferJoinNotNull` | 其他规则 | - |
| 11 | `QueryPartitionCollector` | 其他规则 | - |
| 12 | `InferPredicates` | 其他规则 | - |
| 13 | `UnCorrelatedApplyProjectFilter` | 其他规则 | - |
| 14 | `CreatePartitionTopNFromWindow` | 其他规则 | - |
| 15 | `PullUpCteAnchor` | 其他规则 | - |
| 16 | `CheckAndStandardizeWindowFunctionAndFrame` | 其他规则 | - |
| 17 | `EliminateAggregate` | 其他规则 | - |
| 18 | `RewriteSearchToSlots` | 转换规则 | - |
| 19 | `CheckPrivileges` | 其他规则 | - |
| 20 | `LimitAggToTopNAgg` | 其他规则 | - |
| 21 | `PushDownJoinOnAssertNumRows` | 其他规则 | - |
| 22 | `PushDownProject` | 其他规则 | - |
| 23 | `PruneEmptyPartition` | 其他规则 | - |
| 24 | `CollectCteConsumerOutput` | 其他规则 | - |
| 25 | `ScalarApplyToJoin` | 其他规则 | - |
| 26 | `CheckMultiDistinct` | 其他规则 | - |
| 27 | `InferFilterNotNull` | 其他规则 | - |
| 28 | `AdjustConjunctsReturnType` | 其他规则 | - |
| 29 | `DecoupleEncodeDecode` | 其他规则 | - |
| 30 | `PushDownFilterThroughJoin` | 其他规则 | - |
| 31 | `EliminateGroupBy` | 其他规则 | - |
| 32 | `PushDownFilterThroughWindow` | 其他规则 | - |
| 33 | `MaxMinFilterPushDown` | 其他规则 | - |
| 34 | `TransposeSemiJoinAgg` | 其他规则 | - |
| 35 | `StatsDerive` | 其他规则 | 统计信息 |
| 36 | `for` | 其他规则 | - |
| 37 | `MergeSetOperationsExcept` | 其他规则 | - |
| 38 | `do` | 其他规则 | - |
| 39 | `CheckDataTypes` | 其他规则 | - |
| 40 | `PushDownEncodeSlot` | 其他规则 | - |
| 41 | `PruneOlapScanPartition` | 其他规则 | - |
| 42 | `MergeOneRowRelationIntoUnion` | 其他规则 | - |
| 43 | `PushDownTopNDistinctThroughJoin` | 其他规则 | - |
| 44 | `OperativeColumnDerive` | 其他规则 | - |
| 45 | `PushDownFilterThroughAggregation` | 其他规则 | - |
| 46 | `EliminateSortUnderSubqueryOrView` | 其他规则 | - |
| 47 | `PushDownLimit` | 其他规则 | - |
| 48 | `JoinExtractOrFromCaseWhen` | 其他规则 | - |
| 49 | `UnCorrelatedApplyFilter` | 其他规则 | - |
| 50 | `EliminateGroupByKey` | 其他规则 | - |

*...还有 141 条规则未展示*

### 3.2 表达式规则

> 共 88 条规则，仅展示前50条

| 序号 | 规则名称 | 类型 | 依赖 |
|------|----------|------|------|

| 1 | `ExpressionPatternMatchRule` | 表达式规则 | - |
| 2 | `QueryColumnCollector` | 其他规则 | 统计信息 |
| 3 | `ExpressionNormalizationAndOptimization` | 表达式规则 | - |
| 4 | `ExpressionBottomUpRewriter` | 转换规则 | - |
| 5 | `ExpressionOptimization` | 表达式规则 | - |
| 6 | `ExpressionTraverseListenerMapping` | 表达式规则 | - |
| 7 | `ExpressionPatternRuleFactory` | 表达式规则 | - |
| 8 | `ExpressionNormalization` | 表达式规则 | - |
| 9 | `ExpressionMatchingAction` | 表达式规则 | - |
| 10 | `ExpressionTraverseListener` | 表达式规则 | - |
| 11 | `ExpressionTraverseListenerFactory` | 表达式规则 | - |
| 12 | `of` | 其他规则 | - |
| 13 | `ExpressionListenerMatcher` | 表达式规则 | - |
| 14 | `ExpressionRuleExecutor` | 表达式规则 | - |
| 15 | `CheckLegalityAfterRewrite` | 转换规则 | - |
| 16 | `MergeGuardExpr` | 其他规则 | - |
| 17 | `ExpressionRewriteContext` | 转换规则 | - |
| 18 | `of` | 其他规则 | - |
| 19 | `ExpressionRewrite` | 转换规则 | - |
| 20 | `ExpressionPatternMatcher` | 表达式规则 | - |
| 21 | `NullableDependentExpressionRewrite` | 转换规则 | - |
| 22 | `ExpressionMatchingContext` | 表达式规则 | - |
| 23 | `ExpressionRuleType` | 表达式规则 | - |
| 24 | `CheckCast` | 其他规则 | - |
| 25 | `PartitionPredicateToRange` | 其他规则 | - |
| 26 | `SimplifyConditionalFunction` | 其他规则 | - |
| 27 | `ArrayContainToArrayOverlap` | 其他规则 | - |
| 28 | `RangeInference` | 其他规则 | - |
| 29 | `PushIntoCaseWhenBranch` | 其他规则 | 代价模型 |
| 30 | `SimplifyArithmeticRule` | 其他规则 | - |
| 31 | `NormalizeBinaryPredicatesRule` | 其他规则 | - |
| 32 | `InPredicateExtractNonConstant` | 其他规则 | - |
| 33 | `DistinctPredicatesRule` | 其他规则 | - |
| 34 | `ColumnRange` | 其他规则 | - |
| 35 | `SimplifyTimeFieldFromUnixtime` | 其他规则 | - |
| 36 | `SimplifyEqualBooleanLiteral` | 其他规则 | - |
| 37 | `FoldConstantRule` | 其他规则 | - |
| 38 | `RangePartitionValueIterator` | 其他规则 | - |
| 39 | `OneRangePartitionEvaluator` | 其他规则 | - |
| 40 | `ReplaceVariableByLiteral` | 其他规则 | - |
| 41 | `InPredicateToEqualToRule` | 其他规则 | - |
| 42 | `implements` | 其他规则 | - |
| 43 | `CondReplaceNullWithFalse` | 其他规则 | - |
| 44 | `TimestampToAddTime` | 其他规则 | - |
| 45 | `TopnToMax` | 其他规则 | - |
| 46 | `PartitionPruner` | 其他规则 | - |
| 47 | `DateFunctionRewrite` | 转换规则 | - |
| 48 | `ColumnBound` | 其他规则 | - |
| 49 | `DigitalMaskingConvert` | 其他规则 | - |
| 50 | `MergeDateTrunc` | 其他规则 | - |

*...还有 38 条规则未展示*

## 四、优化流程


### 4.1 优化生命周期

```
SQL输入
    │
    ▼
┌─────────────┐
│   解析      │  SQL Parser → AST
└─────────────┘
    │
    ▼
┌─────────────┐
│   分析      │  分析规则绑定、类型检查
└─────────────┘
    │
    ▼
┌─────────────┐
│  逻辑优化   │  重写规则优化
└─────────────┘
    │
    ▼
┌─────────────┐
│  探索优化   │  探索规则生成备选计划
└─────────────┘
    │
    ▼
┌─────────────┐
│  物理优化   │  实现规则选择物理算子
└─────────────┘
    │
    ▼
执行计划输出
```

### 4.2 Nereids优化器特点

Doris的Nereids优化器采用现代Cascades实现：
- **CascadesContext**: 管理整个优化上下文
- **分层规则**: 分析→重写→探索→实现
- **表达式规则**: 独立的表达式优化层

### 4.3 规则分类应用

1. **分析规则**: 绑定列引用、解析视图
2. **重写规则**: 逻辑等价变换
3. **探索规则**: 生成备选执行计划
4. **实现规则**: 选择具体物理实现
5. **表达式规则**: 标量表达式优化


## 五、可观测性


### 5.1 Explain支持

| 功能 | 支持情况 |
|------|----------|
| EXPLAIN | ✅ 支持 |
| EXPLAIN ANALYZE | ✅ 支持 |
| 优化器追踪 | ✅ 支持 |
| Memo导出 | ✅ 支持 |
| 会话控制 | ✅ 支持 |

### 5.2 调试接口

可通过会话变量控制优化器行为，查看优化过程。


## 六、与其他引擎对比


### 6.1 相比StarRocks

| 方面 | Doris | StarRocks |
|------|-------|-----------|
| 规则数量 | 463 | 269 |
| 规则分类 | 5类（更细粒度） | 2类 |
| 优化器名称 | Nereids | 内置优化器 |
| 历史包袱 | ⚠️ 新旧优化器共存 | ✅ 单一优化器 |

### 6.2 规则丰富度

Doris在以下方面有更多规则：
- **分析规则**: 48条，处理绑定和分析
- **探索规则**: 82条，生成备选计划
- **表达式规则**: 88条，标量表达式优化


## 七、总结与建议


### 7.1 优势

1. **规则丰富**: 463条规则覆盖全面
2. **分类细致**: 5类规则各司其职
3. **现代架构**: Nereids采用现代Cascades设计
4. **持续演进**: 社区活跃，功能不断增强

### 7.2 学习建议

1. 从`NereidsPlanner.java`理解入口
2. 研究`CascadesContext.java`理解上下文管理
3. 按分类阅读rules/下各类规则
4. 对比新旧优化器理解演进

### 7.3 参考资源

- 官方文档: https://doris.apache.org/docs/
- 源码仓库: https://github.com/apache/doris
- Nereids论文: 了解设计背景


---

*本报告由Optimizer Expert Analyzer Agent自动生成*

*生成时间: 2026-04-06T12:02:08.848368*
