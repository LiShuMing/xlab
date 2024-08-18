# Calcite 优化器详细分析报告

**生成时间:** 2026-04-06 12:02:08

**分析源码路径:** /home/lism/work/calcite

## 一、概述

### 1.1 引擎基本信息

| 属性 | 值 |
|------|----|

| 引擎类型 | framework |

| 优化器风格 | volcano |

| 主要编程语言 | Java |

| 规则总数 | 155 |


### 1.2 优化器特点

- Volcano/Cascades-style planner framework
- Rules in rel/rules/ directory (hundreds of rules)
- Plan rules in plan/ directory (RelOptRule, RelOptPlanner)
- Traits and conventions support
- Pure Java implementation
- Used by many projects (Hive, Drill, Flink, etc.)

## 二、优化器架构

### 2.1 核心组件


**核心类:**

- `RelOptPlanner.java`: 优化器接口，定义规则应用框架
- `VolcanoPlanner.java`: Volcano风格优化器实现
- `RelOptRule.java`: 优化规则基类
- `RelTrait.java`: 物理特征定义（排序、分布等）
- `RelTraitDef.java`: 特征定义接口
- **规则系统**: rel/rules/目录包含大量预定义规则
- **特征系统**: 支持Convention（执行约定）、Collation（排序）、Distribution（分布）
- **转换框架**: 支持逻辑到物理的转换

## 三、规则详解

### 3.1 规则统计

| 规则类型 | 数量 |
|----------|------|

| 优化规则 (Rules) | 155 |
| **总计** | **155** |

### 3.2 优化规则

> 共 155 条规则，仅展示前50条

| 序号 | 规则名称 | 类型 | 依赖 |
|------|----------|------|------|

| 1 | `FilterCalcMergeRule` | 其他规则 | - |
| 2 | `JoinDeriveIsNotNullFilterRule` | 其他规则 | - |
| 3 | `SortJoinCopyRule` | 其他规则 | - |
| 4 | `SemiJoinJoinTransposeRule` | 其他规则 | - |
| 5 | `AggregateExtractProjectRule` | 其他规则 | - |
| 6 | `SortRemoveDuplicateKeysRule` | 其他规则 | - |
| 7 | `SetOpToFilterRule` | 其他规则 | - |
| 8 | `AggregateFilterToCaseRule` | 其他规则 | - |
| 9 | `SortRemoveRedundantRule` | 其他规则 | - |
| 10 | `IntersectToDistinctRule` | 其他规则 | - |
| 11 | `JoinProjectTransposeRule` | 其他规则 | - |
| 12 | `UnionMergeRule` | 其他规则 | - |
| 13 | `AggregateStarTableRule` | 其他规则 | - |
| 14 | `SortRemoveRule` | 其他规则 | - |
| 15 | `CoerceInputsRule` | 其他规则 | - |
| 16 | `SortMergeRule` | 其他规则 | - |
| 17 | `UnionToValuesRule` | 其他规则 | - |
| 18 | `TableScanRule` | 其他规则 | - |
| 19 | `IntersectToExistsRule` | 其他规则 | - |
| 20 | `FilterWindowTransposeRule` | 其他规则 | - |
| 21 | `for` | 其他规则 | - |
| 22 | `DphypJoinReorderRule` | 其他规则 | - |
| 23 | `MarkToSemiOrAntiJoinRule` | 其他规则 | - |
| 24 | `ProjectToCalcRule` | 其他规则 | - |
| 25 | `JoinPushThroughJoinRule` | 其他规则 | - |
| 26 | `AggregateProjectConstantToDummyJoinRule` | 其他规则 | - |
| 27 | `that` | 其他规则 | - |
| 28 | `JoinAssociateRule` | 其他规则 | - |
| 29 | `AggregateUnionTransposeRule` | 其他规则 | - |
| 30 | `ProjectMultiJoinMergeRule` | 其他规则 | - |
| 31 | `JoinPushTransitivePredicatesRule` | 其他规则 | - |
| 32 | `ProjectWindowTransposeRule` | 其他规则 | - |
| 33 | `CoreRules` | 其他规则 | 代价模型 |
| 34 | `AggregateValuesRule` | 其他规则 | - |
| 35 | `SingleValuesOptimizationRules` | 其他规则 | - |
| 36 | `AggregateRemoveRule` | 其他规则 | - |
| 37 | `ProjectJoinJoinRemoveRule` | 其他规则 | - |
| 38 | `FilterSetOpTransposeRule` | 其他规则 | - |
| 39 | `FilterProjectTransposeRule` | 其他规则 | - |
| 40 | `FilterSampleTransposeRule` | 其他规则 | - |
| 41 | `JoinPushExpressionsRule` | 表达式规则 | - |
| 42 | `AggregateFilterTransposeRule` | 其他规则 | - |
| 43 | `AggregateExpandDistinctAggregatesRule` | 其他规则 | 统计信息 |
| 44 | `JoinCommuteRule` | 其他规则 | - |
| 45 | `FilterTableFunctionTransposeRule` | 其他规则 | - |
| 46 | `used` | 其他规则 | - |
| 47 | `ProjectJoinRemoveRule` | 其他规则 | - |
| 48 | `ConflictRule` | 其他规则 | - |
| 49 | `UnionToDistinctRule` | 其他规则 | - |
| 50 | `MultiJoinProjectTransposeRule` | 其他规则 | - |

*...还有 105 条规则未展示*

## 四、优化流程


### 4.1 优化生命周期

```
SQL输入
    │
    ▼
┌─────────────┐
│   解析      │  SqlParser → SqlNode
└─────────────┘
    │
    ▼
┌─────────────┐
│   验证      │  SqlValidator验证语义
└─────────────┘
    │
    ▼
┌─────────────┐
│ 转换为RelNode│  SqlToRelConverter
└─────────────┘
    │
    ▼
┌─────────────┐
│  规则优化   │  VolcanoPlanner应用规则
└─────────────┘
    │
    ▼
┌─────────────┐
│ 特征转换    │  RelTrait转换
└─────────────┘
    │
    ▼
执行计划输出
```

### 4.2 特征系统 (Trait System)

Calcite的特征系统是其核心特性：
- **Convention**: 执行约定（如Enumerable、Bindable）
- **Collation**: 排序特征
- **Distribution**: 分布特征

### 4.3 规则应用策略

1. **规则注册**: 将规则添加到Planner
2. **规则匹配**: 基于操作符类型匹配规则
3. **特征协商**: 在转换时协商目标特征
4. **代价估算**: 使用RelOptCost比较方案


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


### 6.1 作为框架的优势

- **广泛使用**: Apache Hive, Drill, Flink, Kylin等
- **扩展性强**: 可自定义规则、特征、代价模型
- **标准实现**: 遵循SQL标准
- **文档完善**: 官方文档和教程丰富

### 6.2 与数据库优化器的差异

Calcite作为框架，不像StarRocks/Doris那样内置完整的数据库功能：
- 不内置Memo结构
- 代价模型需要用户实现
- 统计信息管理需要外部提供


## 七、总结与建议


### 7.1 优势

1. **框架成熟**: 被众多项目采用验证
2. **扩展性强**: Trait系统灵活
3. **标准实现**: SQL标准兼容性好
4. **社区活跃**: Apache顶级项目

### 7.2 学习建议

1. 理解RelNode树结构
2. 学习RelTrait和Convention机制
3. 阅读VolcanoPlanner实现
4. 参考Hive/Flink的使用方式

### 7.3 参考资源

- 官方文档: https://calcite.apache.org/docs/
- 源码仓库: https://github.com/apache/calcite
- 论文: "Volcano-An Extensible and Parallel Query Evaluation System"


---

*本报告由Optimizer Expert Analyzer Agent自动生成*

*生成时间: 2026-04-06T12:02:08.376013*
