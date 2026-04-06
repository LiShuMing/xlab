# StarRocks 优化器详细分析报告

**生成时间:** 2026-04-06 12:02:08

**分析源码路径:** /home/lism/work/starrocks

## 一、概述

### 1.1 引擎基本信息

| 属性 | 值 |
|------|----|

| 引擎类型 | columnar_olap |

| 优化器风格 | cascades |

| 主要编程语言 | Java |

| 规则总数 | 269 |


### 1.2 优化器特点

- Cascades-style optimizer with Memo, Group, GroupExpression
- Rules organized in rule/transformation/, rule/implementation/
- Cost model in cost/ directory
- Statistics in statistics/ directory
- Properties in property/ directory
- Java-based optimizer in FE (Frontend)

## 二、优化器架构

### 2.1 核心组件


**核心类:**

- `Optimizer.java`: 主优化器入口，协调整个优化流程
- `Memo.java`: Memoization结构，存储等价表达式组
- `Group.java`: 表达式组，管理等价逻辑表达式
- `GroupExpression.java`: 组内表达式，带有属性要求
- `OptExpression.java`: 优化表达式树节点
- **规则系统**: rule/目录包含转换和实现规则
- **代价模型**: cost/目录包含代价估算逻辑
- **统计信息**: statistics/目录包含统计信息收集
- **属性系统**: property/目录包含物理属性定义

### 2.2 关键文件验证

| 文件 | 存在 |
|------|------|

| Memo.java | ✅ |
| Group.java | ✅ |
| Optimizer.java | ✅ |

## 三、规则详解

### 3.1 规则统计

| 规则类型 | 数量 |
|----------|------|

| 转换规则 (Transformation) | 224 |
| 实现规则 (Implementation) | 45 |
| **总计** | **269** |

### 3.2 转换规则

> 共 224 条规则，仅展示前50条

| 序号 | 规则名称 | 类型 | 依赖 |
|------|----------|------|------|

| 1 | `PushDownLimitCTEAnchor` | 其他规则 | - |
| 2 | `MultiDistinctByMultiFuncRewriter` | 转换规则 | - |
| 3 | `PruneValuesColumnsRule` | 其他规则 | - |
| 4 | `ConvertToEqualForNullRule` | 其他规则 | - |
| 5 | `PushDownPredicateAggRule` | 其他规则 | - |
| 6 | `PushDownPredicateSetRule` | 其他规则 | - |
| 7 | `PushDownApplyLeftRule` | 其他规则 | - |
| 8 | `PruneProjectEmptyRule` | 其他规则 | - |
| 9 | `does` | 其他规则 | - |
| 10 | `PruneTableFunctionColumnRule` | 其他规则 | - |
| 11 | `PruneUKFKJoinRule` | 其他规则 | - |
| 12 | `JoinCommutativityRule` | 其他规则 | - |
| 13 | `ForceCTEReuseRule` | 其他规则 | - |
| 14 | `PruneEmptyExceptRule` | 其他规则 | - |
| 15 | `RewriteToVectorPlanRule` | 转换规则 | - |
| 16 | `ScalarApplyNormalizeCountRule` | 其他规则 | - |
| 17 | `PruneFilterColumnsRule` | 其他规则 | - |
| 18 | `JoinLeftAsscomRule` | 其他规则 | - |
| 19 | `PushDownJoinAggRule` | 其他规则 | - |
| 20 | `CombinationRule` | 其他规则 | - |
| 21 | `GroupByCountDistinctDataSkewEliminateRule` | 其他规则 | 代价模型 |
| 22 | `UnionToValuesRule` | 其他规则 | - |
| 23 | `PushDownTopNBelowOuterJoinRule` | 其他规则 | - |
| 24 | `CTEProduceAddProjectionRule` | 其他规则 | - |
| 25 | `RewriteCountIfFunction` | 转换规则 | - |
| 26 | `need` | 其他规则 | - |
| 27 | `PushDownPredicateRankingWindowRule` | 其他规则 | - |
| 28 | `CollectCTEConsumeRule` | 其他规则 | - |
| 29 | `EliminateGroupByConstantRule` | 其他规则 | - |
| 30 | `RewriteBitmapCountDistinctRule` | 转换规则 | - |
| 31 | `PushDownPredicateJoinRule` | 其他规则 | - |
| 32 | `GroupByCountDistinctRewriteRule` | 转换规则 | - |
| 33 | `MergeTwoFiltersRule` | 其他规则 | - |
| 34 | `PruneCTEConsumeColumnsRule` | 其他规则 | - |
| 35 | `ListPartitionPruner` | 其他规则 | - |
| 36 | `PushDownPredicateCTEAnchor` | 其他规则 | - |
| 37 | `PruneUKFKGroupByKeysRule` | 其他规则 | - |
| 38 | `SplitLimitRule` | 其他规则 | - |
| 39 | `EliminateJoinWithConstantRule` | 其他规则 | - |
| 40 | `PruneProjectRule` | 其他规则 | - |
| 41 | `SeparateProjectRule` | 其他规则 | 统计信息 |
| 42 | `PruneEmptyIntersectRule` | 其他规则 | - |
| 43 | `PushDownJoinOnExpressionToChildProject` | 表达式规则 | - |
| 44 | `ExternalScanPartitionPruneRule` | 其他规则 | - |
| 45 | `EliminateLimitZeroRule` | 其他规则 | - |
| 46 | `ExistentialApply2JoinRule` | 其他规则 | - |
| 47 | `PruneEmptyUnionRule` | 其他规则 | - |
| 48 | `MultiDistinctByCTERewriter` | 转换规则 | - |
| 49 | `QuantifiedApply2JoinRule` | 其他规则 | - |
| 50 | `RewriteSumByAssociativeRule` | 转换规则 | - |

*...还有 174 条规则未展示*

### 3.2 实现规则

| 序号 | 规则名称 | 类型 | 依赖 |
|------|----------|------|------|

| 1 | `IcebergEqualityDeleteScanImplementationRule` | 实现规则 | - |
| 2 | `PaimonScanImplementationRule` | 实现规则 | - |
| 3 | `CTEConsumerReuseImplementationRule` | 实现规则 | - |
| 4 | `IcebergMetadataScanImplementationRule` | 实现规则 | - |
| 5 | `MysqlScanImplementationRule` | 实现规则 | - |
| 6 | `ValuesImplementationRule` | 实现规则 | - |
| 7 | `IcebergScanImplementationRule` | 实现规则 | - |
| 8 | `HudiScanImplementationRule` | 实现规则 | - |
| 9 | `NestLoopJoinImplementationRule` | 实现规则 | - |
| 10 | `RepeatImplementationRule` | 实现规则 | - |
| 11 | `ProjectImplementationRule` | 实现规则 | - |
| 12 | `HashJoinImplementationRule` | 实现规则 | - |
| 13 | `MetaScanImplementationRule` | 实现规则 | - |
| 14 | `ImplementationRule` | 实现规则 | - |
| 15 | `ExceptImplementationRule` | 实现规则 | - |
| 16 | `WindowImplementationRule` | 实现规则 | - |
| 17 | `EsScanImplementationRule` | 实现规则 | - |
| 18 | `TopNImplementationRule` | 实现规则 | - |
| 19 | `AssertOneRowImplementationRule` | 实现规则 | - |
| 20 | `RawValuesImplementationRule` | 实现规则 | - |
| 21 | `TableFunctionImplementationRule` | 实现规则 | - |
| 22 | `CTEAnchorToNoCTEImplementationRule` | 实现规则 | - |
| 23 | `TableFunctionTableScanImplementationRule` | 实现规则 | - |
| 24 | `SchemaScanImplementationRule` | 实现规则 | - |
| 25 | `DeltaLakeScanImplementationRule` | 实现规则 | - |
| 26 | `CTEProduceImplementationRule` | 实现规则 | - |
| 27 | `FileScanImplementationRule` | 实现规则 | - |
| 28 | `CTEConsumeInlineImplementationRule` | 实现规则 | - |
| 29 | `OdpsScanImplementationRule` | 实现规则 | - |
| 30 | `HashAggImplementationRule` | 实现规则 | - |
| 31 | `IntersectImplementationRule` | 实现规则 | - |
| 32 | `KuduScanImplementationRule` | 实现规则 | - |
| 33 | `MergeJoinImplementationRule` | 实现规则 | - |
| 34 | `CTEAnchorImplementationRule` | 实现规则 | - |
| 35 | `JDBCScanImplementationRule` | 实现规则 | - |
| 36 | `FilterImplementationRule` | 实现规则 | - |
| 37 | `HiveScanImplementationRule` | 实现规则 | - |
| 38 | `UnionImplementationRule` | 实现规则 | - |
| 39 | `JoinImplementationRule` | 实现规则 | - |
| 40 | `OlapScanImplementationRule` | 实现规则 | - |
| 41 | `LimitImplementationRule` | 实现规则 | - |
| 42 | `StreamAggregateImplementationRule` | 实现规则 | - |
| 43 | `StreamScanImplementationRule` | 实现规则 | - |
| 44 | `StreamImplementationRule` | 实现规则 | - |
| 45 | `StreamJoinImplementationRule` | 实现规则 | - |

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
│   分析      │  语义分析、类型检查
└─────────────┘
    │
    ▼
┌─────────────┐
│ 逻辑优化    │  应用转换规则、Memo构建
└─────────────┘
    │
    ▼
┌─────────────┐
│ 物理优化    │  应用实现规则、代价估算
└─────────────┘
    │
    ▼
┌─────────────┐
│ 计划选择    │  选择最优执行计划
└─────────────┘
    │
    ▼
执行计划输出
```

### 4.2 Memo结构

StarRocks采用Cascades风格的Memo结构：
- **Memo**: 存储所有等价表达式组
- **Group**: 逻辑上等价的表达式集合
- **GroupExpression**: 组内具体表达式，带物理属性要求

### 4.3 规则应用策略

1. **转换规则**: 在逻辑优化阶段应用，生成等价逻辑表达式
2. **实现规则**: 在物理优化阶段应用，将逻辑算子转换为物理算子
3. **代价驱动**: 通过代价模型比较不同实现方案


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


### 6.1 相比Calcite

| 方面 | StarRocks | Calcite |
|------|-----------|---------|
| 定位 | 完整OLAP数据库 | SQL框架 |
| Memo支持 | ✅ 内置 | ❌ 无 |
| 代价模型 | ✅ 内置 | ⚠️ 可插拔 |
| 规则数量 | 269 | 155 |
| 学习曲线 | 较陡 | 平缓 |

### 6.2 相比Doris

| 方面 | StarRocks | Doris |
|------|-----------|-------|
| 规则数量 | 269 | 463 |
| 规则分类 | 2类 | 5类 |
| 架构清晰度 | ✅ 更清晰 | ⚠️ 较复杂 |
| 成熟度 | ✅ 较成熟 | ⚠️ 新优化器 |


## 七、总结与建议


### 7.1 优势

1. **架构清晰**: 纯Cascades实现，Memo/Group分离明确
2. **性能优秀**: 列存优化、向量化执行
3. **规则完整**: 转换和实现规则分离清晰
4. **文档齐全**: 官方文档完善

### 7.2 学习建议

1. 从`Optimizer.java`入口开始理解整体流程
2. 研究`Memo.java`和`Group.java`理解搜索空间管理
3. 阅读`rule/transformation/`中的典型规则
4. 分析`cost/`目录理解代价模型

### 7.3 参考资源

- 官方文档: https://docs.starrocks.io/
- 源码仓库: https://github.com/StarRocks/starrocks


---

*本报告由Optimizer Expert Analyzer Agent自动生成*

*生成时间: 2026-04-06T12:02:08.171998*
