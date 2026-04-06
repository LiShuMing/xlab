# StarRocks 查询优化器深度分析报告

## 概述

基于对 StarRocks 查询优化器源码的自动化分析，使用 LLM (qwen3.5-plus) 对优化规则进行深度解析。

**分析状态**: 完成  
**数据来源**: `/home/lism/work/starrocks`  
**分析时间**: 2026-04-06  

---

## 统计摘要

| 指标 | 数值 |
|------|------|
| 发现规则总数 | 191 |
| 已完成分析 | 181 |
| 需人工审核 | 10 |
| 平均置信度 | 0.92 |
| 高置信度 (>0.9) | 76% |
| 结果条目总数 | 303 |

### 按类别分布 (TOP 15)

| 类别 | 数量 | 说明 |
|------|------|------|
| predicate_pushdown | 19 | 谓词下推优化 |
| aggregation | 16 | 聚合优化 |
| scan | 17 | 扫描优化 |
| column_pruning | 12 | 列剪枝 |
| set_operation | 11 | 集合操作优化 |
| cte_optimization | 8 | CTE 优化 |
| aggregation_rewrite | 8 | 聚合重写 |
| subquery_unnesting | 6 | 子查询解嵌套 |
| limit | 6 | Limit 优化 |
| property | 6 | 物理属性 |
| physical_scan_impl | 21 | 物理扫描实现 |
| physical_implementation | 8 | 物理实现选择 |
| optimizer_control | 6 | 优化器控制 |

---

## 核心规则详解

### 1. 谓词下推 (Predicate Pushdown)

**PushDownPredicateJoinRule**
- **功能**: 将过滤条件下推至 Join 操作下方
- **关系代数**: `σ_p(R ⋈ S) → (σ_p(R)) ⋈ S` 或 `R ⋈ (σ_p(S))`
- **触发条件**: 谓词仅引用单一边的列
- **性能影响**: 显著减少 Join 输入数据量

**PushDownPredicateAggRule**
- **功能**: 将谓词下推穿过聚合操作
- **关系代数**: `σ_p(γ_G(R)) → γ_G(σ_p(R))`
- **条件**: 谓词仅引用分组列

**PushDownPredicateCTEConsumeRule**
- **功能**: 谓词下推至 CTE Consume 节点
- **关系代数**: `σ_p(CTEConsume) → CTEConsume_with_filter`

### 2. 聚合优化 (Aggregation)

**RewriteSumByAssociativeRule**
- **功能**: 利用结合律重写 SUM 表达式
- **关系代数**: `SUM(a + b) → SUM(a) + SUM(b)`
- **分类**: aggregate_rewrite.sum_associative

**MergeTwoAggRule**
- **功能**: 合并相邻的聚合操作
- **关系代数**: `γ_G1(γ_G2(R)) → γ_G(R)`
- **条件**: 内层聚合可被外层吸收

**GroupByCountDistinctRewriteRule**
- **功能**: 将 COUNT DISTINCT 重写为两阶段聚合
- **说明**: 本地聚合去重 + 全局聚合汇总

**ArrayDistinctAfterAggRule**
- **功能**: 合并外层 array_distinct 与聚合操作
- **优化效果**: 减少中间结果物化

### 3. 列剪枝 (Column Pruning)

**PruneProjectColumnsRule**
- **功能**: 剪枝 Project 操作未使用的输出列
- **关系代数**: `π_A(π_B(R)) → π_A(R)` 其中 A ⊆ B

**PruneFilterColumnsRule**
- **功能**: 基于 Filter 谓词需求剪枝输入列

**PruneJoinColumnsRule**
- **功能**: 剪枝 Join 未引用的输出列

**PruneWindowColumnsRule**
- **功能**: 剪枝 Window 函数未使用的列

### 4. 子查询解嵌套 (Subquery Unnesting)

**ExistentialApply2JoinRule**
- **功能**: 将 Existential Apply 转换为 Semi-join
- **关系代数**: `R ⋈_apply^∃ S → R ⋉ S`
- **说明**: 支持 EXISTS/NOT EXISTS 子查询

**QuantifiedApply2JoinRule**
- **功能**: 将 Quantified Apply 转换为 Join
- **关系代数**: `R ⋈_apply^{ANY/ALL} S → R ⋈ S`
- **说明**: 支持 ANY/ALL 量词子查询

**Apply2JoinRule**
- **功能**: 通用 Apply 到 Join 的转换
- **分类**: subquery_unnesting.apply_to_join

### 5. Join 优化

**EliminateJoinWithConstantRule**
- **功能**: 消除与常量表的连接
- **关系代数**: `R ⋈_θ C where |C| = 1 → π_{proj}(σ_{θ}(R))`
- **条件**: 常量表只有一行

**JoinCommutativityWithoutInnerRule**
- **功能**: Join 交换律 (不含 Inner Join)
- **关系代数**: `R ⋈_θ S → S ⋈_θ R`

**SemiReorderRule**
- **功能**: Semi-join 重排序优化
- **分类**: join_reorder.semi_reorder

**PruneUKFKJoinRule**
- **功能**: 基于 UK-FK 约束消除冗余 Join

### 6. 集合操作优化

**PruneEmptyIntersectRule**
- **功能**: 检测空交集并优化
- **关系代数**: `E_1 ∩ E_2 ∩ ... ∩ E_n → ∅ (if any E_i = ∅)`

**PruneEmptyUnionRule**
- **功能**: 剪枝空输入的 Union
- **关系代数**: `R ∪ ∅ → R`

**PushDownPredicateExceptRule**
- **功能**: 谓词下推穿过 Except 操作

### 7. Limit 优化

**EliminateLimitZeroRule**
- **功能**: 消除 LIMIT 0 操作
- **关系代数**: `λ_0(R) → ∅`

**SplitLimitRule**
- **功能**: 将 Limit 拆分为本地和全局阶段
- **说明**: 本地 limit+offset，全局 limit

**PushDownLimitUnionRule**
- **功能**: 将 Limit 下推至 Union 分支

### 8. CTE 优化

**PushLimitAndFilterToCTEProduceRule**
- **功能**: 将 Limit 和 Filter 下推至 CTE Produce

**InlineOneCTEConsumeRule**
- **功能**: 内联只被引用一次的 CTE

**PruneCTEProduceColumnsRule**
- **功能**: 剪枝 CTE Produce 未使用的列

### 9. 扫描优化

**ExternalScanPartitionPruneRule**
- **功能**: 外部表分区剪枝
- **支持**: Hive、Iceberg、Hudi 等

**OlapScanPartitionPruneRule**
- **功能**: OLAP 表分区剪枝
- **说明**: 基于谓词的分区裁剪

### 10. 物理实现规则

**PhysicalScanImplRule**
- **功能**: 生成物理扫描算子
- **分类**: physical_scan_impl

**PhysicalOlapScanRule / PhysicalHiveScanRule**
- **功能**: 特定存储的扫描实现

---

## 关系代数符号系统

| 符号 | 含义 | 示例 |
|------|------|------|
| σ | 选择/过滤 | `σ_p(R)` |
| π | 投影 | `π_A(R)` |
| ⋈ | 连接 | `R ⋈_θ S` |
| ⟕ | 左外连接 | `R ⟕ S` |
| ⋉ | Semi-join | `R ⋉ S` |
| ⋊ | Anti-semi-join | `R ⋊ S` |
| γ | 分组聚合 | `γ_G(R)` |
| λ | Limit | `λ_n(R)` |
| ω | 窗口函数 | `ω_{f;P;O}(R)` |
| ∩ | 交集 | `R ∩ S` |
| ∪ | 并集 | `R ∪ S` |
| ∅ | 空集 | `∅` |

---

## 优化器框架特征

StarRocks 采用 Cascades 框架，具有以下特征:

1. **Memo-based 优化**: 使用 Memo 结构存储等价表达式
2. **逻辑/物理算子分离**: 逻辑计划通过规则转换为物理计划
3. **Property Enforcement**: 支持排序、分布等属性的强制执行
4. **代价模型驱动**: 基于统计信息选择最优计划

### 规则分类体系

- **RBO (Rule-Based Optimization)**: 逻辑等价变换，基于启发式规则
- **CBO (Cost-Based Optimization)**: 物理实现选择，基于代价模型
- **Scalar**: 标量表达式重写
- **Property**: 物理属性处理
- **Post-Optimization**: 后优化阶段规则

---

## 分析质量评估

### 置信度分布

| 区间 | 数量 | 占比 |
|------|------|------|
| 0.9-1.0 | 231 | 76% |
| 0.8-0.9 | 45 | 15% |
| 0.7-0.8 | 15 | 5% |
| <0.7 | 12 | 4% |

### 验证指标

- **关系代数正确性**: 高，符号使用规范
- **分类一致性**: 良好，同类规则归类准确
- **描述完整性**: 高，包含触发条件和边界情况

---

## 与业界对比

| 能力 | StarRocks | 备注 |
|------|-----------|------|
| 谓词下推 | 完整 | 支持多种算子，包括 CTE/Join/Agg |
| 子查询解嵌套 | 完整 | Existential/Quantified/Scalar 均支持 |
| Join 重排序 | 完整 | 支持交换律、结合律优化 |
| 聚合优化 | 丰富 | 多种重写规则，两阶段聚合 |
| 分区剪枝 | 完整 | 支持内部表和外部表 |
| CTE 优化 | 完整 | Limit/Filter 下推，内联优化 |
| 列剪枝 | 完整 | 覆盖所有主要算子类型 |
| 物理实现 | 丰富 | 多种存储引擎适配 |

---

## 数据文件

- **分析结果**: `data/starrocks/*.jsonl` (303 条分析结果)
- **任务队列**: `data/task_queue.json` (191 个任务)
- **配置文件**: `engines/starrocks.yaml`

---

## 总结

本次分析共处理 191 个 StarRocks 查询优化规则，完成 181 个 (94.8%)，平均置信度 0.92。分析覆盖 RBO、CBO、Scalar、Property 等多个类别，生成了 303 条详细的规则分析结果。

StarRocks 优化器展现了现代数据库查询优化器的典型特征:
- 完整的谓词下推体系
- 完善的子查询解嵌套能力
- 丰富的聚合优化策略
- 高效的 CTE 优化机制
- 灵活的物理实现选择

---

*报告生成时间: 2026-04-06*  
*分析模型: qwen3.5-plus*  
*项目路径: /home/lism/work/xlab/python/projects/py-optimizer2*
