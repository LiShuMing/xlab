# 第 19 章 · Calcite 集成与 Optimizer

## 导读

- **一句话**：本章深入 Flink 如何把 Calcite 框架嵌套进自己的优化器——从 RelNode 的定制到 150+ 条优化规则的执行，最终输出可直接翻译为算子的 ExecNode 图。
- **前置知识**：第 18 章 SQL 架构、Calcite 基础概念（RelNode, RelOptRule, VolcanoPlanner）。
- **读完本章你能回答**：
  - Flink 扩展了哪些 Calcite 的 RelNode？为什么需要扩展？
  - VolcanoPlanner 的 Cost-Based Optimization 在 Flink 中怎样利用统计信息
  - Sub-plan Reuse、Fusion 等高级优化的原理
  - 流和批两套不同的优化规则各自侧重什么
  - ChangelogMode 的三种语义如何影响算子选择

---

## 19.1 — 设计动机

Calcite 提供了通用的关系代数节点（LogicalTableScan, LogicalFilter, LogicalJoin...）和两套优化器（HepPlanner, VolcanoPlanner）。Flink 不直接使用 Calcite 的原始节点，而是在其上建立一套 Flink-specific 的 Logical / Physical 节点体系。

**为什么这样设计？** 解决两个问题：（1）Calcite 的 Logical 节点不携带流语义信息（如 ChangelogMode、Watermark、StateTTL），无法表达流批差异；（2）Calcite 的 Physical 节点（Enumerable 系）面向 JVM 执行，而 Flink 需要自己的 CodeGen 和分布式执行模型。放弃的替代方案是直接扩展 Calcite 的 Enumerable Convention——这会迫使 Flink 穿透 Calcite 的代码生成层，无法独立控制算子行为。

因此 Flink 定义了三个 Convention 层：

```
FlinkConventions.LOGICAL         → FlinkLogicalRel 节点
FlinkConventions.STREAM_PHYSICAL → StreamPhysicalRel 节点
FlinkConventions.BATCH_PHYSICAL  → BatchPhysicalRel 节点
```

源码入口：`org.apache.flink.table.planner.plan.nodes.FlinkConventions:L#50`

---

## 19.2 — 核心数据结构

### 19.2.1 FlinkLogicalRel 节点体系

`FlinkLogicalRel` 是一个空 trait，所有 Flink Logical 节点混入它以标记 Convention 为 `LOGICAL`：

```scala
trait FlinkLogicalRel extends FlinkRelNode {}
```

`org.apache.flink.table.planner.plan.nodes.logical.FlinkLogicalRel:L#23`

关键节点清单：FlinkLogicalAggregate（分组聚合）、FlinkLogicalCalc（Filter+Project 合体）、FlinkLogicalJoin（两表 Join）、FlinkLogicalMultiJoin（多表 Join 中间态，供 Reorder 使用）、FlinkLogicalCorrelate（表函数关联）、FlinkLogicalRank（TopN 排名）、FlinkLogicalExpand（GROUPING SETS 展开）、FlinkLogicalOverAggregate（OVER 窗口聚合）、FlinkLogicalWindowAggregate / FlinkLogicalWindowTableAggregate（Group Window 聚合）、FlinkLogicalSort（排序）、FlinkLogicalUnion / Intersect / Minus（集合操作）、FlinkLogicalSnapshot（时态表版本快照）、FlinkLogicalWatermarkAssigner（Watermark 分配）、FlinkLogicalTableSourceScan（Source 扫描）、FlinkLogicalSink（数据汇写）、FlinkLogicalMatch（CEP 模式匹配）。

每个 Logical 节点附带一个 `CONVERTER`，将 Calcite 原生节点转为 FlinkLogical 节点：

```scala
val CONVERTER: ConverterRule = new FlinkLogicalJoinConverter(
  Config.INSTANCE.withConversion(classOf[LogicalJoin],
    Convention.NONE, FlinkConventions.LOGICAL, "FlinkLogicalJoinConverter"))
```

`org.apache.flink.table.planner.plan.nodes.logical.FlinkLogicalJoin:L#93`

### 19.2.2 FlinkPhysicalRel 节点体系

`FlinkPhysicalRel` 的核心方法是将自己翻译为 `ExecNode`：

```scala
trait FlinkPhysicalRel extends FlinkRelNode {
  def satisfyTraits(requiredTraitSet: RelTraitSet): Option[RelNode] = None
  def translateToExecNode(): ExecNode[_]
}
```

`org.apache.flink.table.planner.plan.nodes.physical.FlinkPhysicalRel:L#27`

Physical 节点按流/批分为两个子体系。流式关键节点：StreamPhysicalGroupAggregate（全局聚合）、StreamPhysicalLocalGroupAggregate / StreamPhysicalGlobalGroupAggregate（MiniBatch 两阶段）、StreamPhysicalIncrementalGroupAggregate（增量聚合）、StreamPhysicalJoin（Regular Join）、StreamPhysicalIntervalJoin / TemporalJoin / LookupJoin / WindowJoin（各类 Join）、StreamPhysicalChangelogNormalize（Changelog 归一化）、StreamPhysicalMiniBatchAssigner（MiniBatch 分配器）。批式关键节点：BatchPhysicalHashJoin / SortMergeJoin / NestedLoopJoin（三类 Join）、BatchPhysicalHashAggregate / SortAggregate / LocalHashAggregate / LocalSortAggregate（聚合策略）、BatchPhysicalRuntimeFilter（运行时过滤）、BatchPhysicalExchange（Shuffle）。

**为什么这样设计？** 流式节点必须携带 State 描述和 ChangelogMode 约束，批式节点关注 Partition 策略和排序属性。分开到不同 Convention 使 VolcanoPlanner 不会产生流批混搭的非法计划。放弃的替代方案是共用一套 Physical 节点用字段区分——这会导致单类膨胀且 Convention 机制失效。

### 19.2.3 ExecNode —— Physical Plan 到 CodeGen 的桥梁

```java
public interface ExecNode<T> extends ExecNodeTranslator<T>, FusionCodegenExecNode {
    int getId();
    LogicalType getOutputType();
    List<InputProperty> getInputProperties();
    List<ExecEdge> getInputEdges();
    void setCompiled(boolean isCompiled);
}
```

`org.apache.flink.table.planner.plan.nodes.exec.ExecNode:L#54`

ExecNode 是 Flink 优化的最终输出，被 `ExecGraphGenerator` 转换为 Transformation 链。支持 JSON 序列化（CompiledPlan），通过 `@ExecNodeMetadata` 注解管理版本。

### 19.2.4 FlinkRelBuilder 的构建过程

```java
public final class FlinkRelBuilder extends RelBuilder {
    public static final RelBuilder.Config FLINK_REL_BUILDER_CONFIG =
        Config.DEFAULT.withSimplifyValues(false).withConvertCorrelateToJoin(false);
}
```

`org.apache.flink.table.planner.calcite.FlinkRelBuilder:L#71`

关键扩展点：`ExpandFactory`（GROUPING SETS）、`RankFactory`（TopN）、`LogicalWindowAggregate` / `LogicalWatermarkAssigner`（窗口/水位线）。`withSimplifyValues(false)` 禁用 Calcite 的 Values 简化，`withConvertCorrelateToJoin(false)` 禁用自动 Correlate-to-Join 转换（Flink 有自己的 CorrelateToTemporalTableJoin 规则）。构建路径：`QueryOperation → QueryOperationConverter → FlinkRelBuilder → RelNode`。

### 19.2.5 ChangelogMode 的三种语义

```java
public final class ChangelogMode {
    private static final ChangelogMode INSERT_ONLY = ...;  // 仅 INSERT
    private static final ChangelogMode UPSERT = ...;       // INSERT + UPDATE_AFTER + DELETE
    private static final ChangelogMode ALL = ...;          // 全部四种 RowKind
}
```

`org.apache.flink.table.connector.ChangelogMode:L#38`

| 模式 | 包含 RowKind | 典型场景 | State 影响 |
|------|-------------|----------|-----------|
| INSERT_ONLY | INSERT | Append-only 流 | 无需 State |
| UPSERT | INSERT, UA, DELETE | Kafka 有 Key | 只需 Key State |
| ALL (RETRACT) | INSERT, UB, UA, DELETE | 含非确定性更新 | Key + Value State |

**为什么这样设计？** 同一个逻辑聚合在 INSERT_ONLY 输入时可无状态，在 UPSERT 输入时只需 Key 去重，在 RETRACT 输入时需完整 State。ChangelogMode 让优化器在物理计划阶段决定是否插入 `StreamPhysicalChangelogNormalize` 归一化 Changelog。放弃的替代方案是运行时动态判断——这会导致 State 大小不可预测。

---

## 19.3 — 关键流程走读

### 19.3.1 SQL 到物理计划的完整流程

```
SQL String
  ↓ SqlParser → SqlNode
  ↓ SqlValidator → Validated SqlNode
  ↓ SqlToRelConverter + FlinkRelBuilder → RelNode (Convention=NONE)
  ↓ VolcanoProgram (LOGICAL) → FlinkLogicalRel 树
  ↓ FlinkChainedProgram (Hep+Volcano 多阶段) → FlinkPhysicalRel 树
  ↓ translateToExecNode() → ExecNode 图
  ↓ ExecGraphGenerator → Transformation → StreamGraph / JobGraph
```

FlinkChainedProgram 阶段（流模式，`FlinkStreamProgram.buildProgram`）：

1. SUBQUERY_REWRITE → 子查询转 Semi-Join
2. TEMPORAL_JOIN_REWRITE → Correlate 转 Temporal Join
3. DECORRELATE → 去关联
4. DEFAULT_REWRITE → 谓词简化、表达式归约
5. PREDICATE_PUSHDOWN → 谓词下推（含分区下推、过滤下推）
6. JOIN_REORDER → Join 重排（可选，默认关闭）
7. MULTI_JOIN → 合并 Binary Join 为 MultiJoin
8. PROJECT_REWRITE → 投影优化
9. LOGICAL → VolcanoProgram: Calcite Logical → FlinkLogical
10. LOGICAL_REWRITE → Watermark 下推、Rank 变换、Split Distinct Agg
11. TIME_INDICATOR → 时间属性处理
12. PHYSICAL → VolcanoProgram: FlinkLogical → StreamPhysical
13. PHYSICAL_REWRITE → ChangelogMode 推断、MiniBatch、增量聚合

`org.apache.flink.table.planner.plan.optimize.program.FlinkStreamProgram:L#46`

### 19.3.2 HepPlanner 的规则应用流程

1. 按 `HepMatchOrder`（BOTTOM_UP / TOP_DOWN）遍历 RelNode 树
2. 对每个 RelNode 检查 `RelOptRule.matches()`
3. 匹配成功则调用 `onMatch()` 产生新 RelNode
4. 重复直到不动点

两种执行模式：`RULE_SEQUENCE`（按序执行，不循环）、`RULE_COLLECTION`（整体反复执行直到不动点，受 `setIterations` 控制）。

`org.apache.flink.table.planner.plan.optimize.program.FlinkHepProgram:L#46`

### 19.3.3 VolcanoPlanner 的成本计算流程

1. 注册初始 RelNode 到 memo 结构（RelSet + RelSubset）
2. 触发 ConverterRule / TransformRule 生成等价替代计划
3. 自底向上通过 `FlinkRelMdNonCumulativeCost` / `FlinkRelMdCumulativeCost` 计算成本
4. 每个 RelSubset 保留成本最低的实现

```scala
val planner = root.getCluster.getPlanner.asInstanceOf[VolcanoPlanner]
FlinkRelMdNonCumulativeCost.THREAD_PLANNER.set(planner)
optProgram.run(planner, root, targetTraits, ImmutableList.of(), ImmutableList.of())
```

`org.apache.flink.table.planner.plan.optimize.program.FlinkVolcanoProgram:L#43`

核心元数据处理器：`FlinkRelMdRowCount`（行数估计）、`FlinkRelMdSelectivity`（选择率）、`FlinkRelMdDistinctRowCount`（NDV）、`FlinkRelMdColumnInterval`（列值区间）、`FlinkRelMdUniqueKeys` / `FlinkRelMdUpsertKeys`（键推导）。统计信息来源：Catalog 统计 + Connector 上报 + Plan 自底向上推导。

### 19.3.4 Sub-Plan Reuse 的识别和执行流程

Calcite 不支持 DAG 优化，Flink 分两步完成：

第一步：`CommonSubGraphBasedOptimizer` 将 DAG 分解为 `RelNodeBlock`（每个 Block 是一棵树，可独立优化），非根 Block 结果包装为 `IntermediateRelTable`，优化后展开还原。

第二步：`SubplanReuser` 按 `digest`（规范字符串）识别重复子计划，合并为同一物理实例。可通过 `table.optimizer.reuse-sub-plan-enabled` 关闭。

`org.apache.flink.table.planner.plan.optimize.CommonSubGraphBasedOptimizer:L#78`

### 19.3.5 Fusion 的实现机制

Fusion 将相邻无 Shuffle 依赖的算子打包为一个代码生成单元，减少虚函数调用和序列化开销：

1. `OpFusionCodegenSpecGenerator` 按拓扑序组织算子链
2. 每个算子实现 `OpFusionCodegenSpec` 接口（`processProduce` / `processConsume`）
3. `FusionCodegenUtil` 将整条链代码拼接为单个 Java 类
4. Janino 编译为字节码，运行时作为单个 Operator 执行

已实现 Spec：CalcFusionCodegenSpec、HashAggFusionCodegenSpec、HashJoinFusionCodegenSpec、InputAdapterFusionCodegenSpec、OutputFusionCodegenSpec、RuntimeFilterFusionCodegenSpec。

`org.apache.flink.table.planner.plan.fusion.FusionCodegenUtil:L#43`

### 19.3.6 谓词下推的完整走读

PREDICATE_PUSHDOWN 阶段三步：

Step 1：`JoinDependentConditionDerivationRule` 从 Join 条件提取可下推子条件。Step 2：Filter 准备与传播——`FlinkFilterJoinRule` 下推到 Join 输入、`FlinkFilterProjectTransposeRule` 穿过 Project、`FILTER_AGGREGATE_TRANSPOSE` 穿过 Aggregate、`FILTER_SET_OP_TRANSPOSE` 穿过 SetOp。Step 3：下推到 Source——`PushFilterIntoTableSourceScanRule` 通过 `SupportsFilterPushDown` 能力协商，Source 决定接受/拒绝哪些谓词，拒绝的保留在上层 Calc。

`org.apache.flink.table.planner.plan.rules.logical.PushFilterIntoTableSourceScanRule:L#43`

### 19.3.7 流模式下的特殊优化

**MiniBatch 聚合**：`FlinkMiniBatchIntervalTraitInitProgram` 注入 MiniBatchInterval trait → `MiniBatchIntervalInferRule` 推断间隔 → 插入 `StreamPhysicalMiniBatchAssigner`。链路：`MiniBatchAssigner → LocalGroupAggregate → Exchange → GlobalGroupAggregate`。

**Local-Global Aggregation**：`TwoStageOptimizedAggregateRule` 将 `GlobalAgg + Exchange` 拆为 `LocalAgg + Exchange + GlobalAgg`，Local 端预聚合减少 Shuffle 数据量。

`org.apache.flink.table.planner.plan.rules.physical.stream.TwoStageOptimizedAggregateRule:L#59`

**Incremental Aggregate**：`IncrementalAggregateRule` 将 `GlobalAgg(Exchange(LocalAgg(PartialGlobalAgg)))` 合并为 `IncrementalGroupAggregate`，避免 Retract 开销。

`org.apache.flink.table.planner.plan.rules.physical.stream.IncrementalAggregateRule:L#56`

---

## 19.4 — 横向对比（Spark / StarRocks / MaxCompute）

### vs Spark Catalyst

| 维度 | Flink | Spark Catalyst |
|------|-------|----------------|
| 优化框架 | Calcite (Hep + Volcano) | 自研 Catalyst (Rule + CBO) |
| Rule 执行 | HepPlanner (不动点) + VolcanoPlanner (memo) | RuleExecutor (不动点, 批次) |
| 物理代码生成 | Janino + FusionCodegen | Tungsten WholeStageCodeGen |
| 流式支持 | ChangelogMode / State / Watermark | 无（Structured Streaming 是微批） |
| Convention | LOGICAL / STREAM_PHYSICAL / BATCH_PHYSICAL | 无 Convention，直接 SparkPlan |

**关键差异**：Spark 的 Tungsten 将整条算子链编译为单个 Java 函数，类似 Flink Fusion 但更激进。Flink 必须考虑 State 大小和 ChangelogMode——这是 Spark 不存在的约束。

### vs StarRocks 优化器

| 维度 | Flink | StarRocks |
|------|-------|-----------|
| 统计信息 | Catalog Statistics + Connector 报告 | ANALYZE TABLE + 实时采样 + 直方图 |
| CBO 模型 | VolcanoPlanner | 自研 CBO + Bottom-Up 枚举 |
| Runtime Filter | 批模式支持（默认关闭） | 核心优化，默认开启 |

**关键差异**：StarRocks 统计信息更丰富（直方图、实时采样），CBO 更精准。Flink 缺失统计信息时退化为默认估计（行数 100、选择率 0.25），容易导致错误 Join 顺序。

### vs MaxCompute 优化器

| 维度 | Flink | MaxCompute |
|------|-------|-----------|
| 优化框架 | Calcite VolcanoPlanner | 基于 Cascades |
| 搜索策略 | Volcano (自顶向下 memo) | Cascades (任务驱动 memo) |
| 多表 Join | bushy-join-threshold=12 | 搜索空间更大 |

**关键差异**：MaxCompute 基于 Cascades，搜索空间更大，任务驱动模型更适合大规模搜索。Flink 的 VolcanoPlanner 受限于搜索深度。

---

## 19.5 — 调优与实战陷阱

### 陷阱 1：统计信息缺失导致错误 Join 顺序

**现象**：三表 Join 应 Broadcast 小表却走 SortMergeJoin，导致 OOM。**原因**：VolcanoPlanner 用默认基数（行数=100）误判所有表等大。**解决**：在 Catalog 注册表统计、启用 Source 统计上报（`table.optimizer.source.report-statistics-enabled=true`）、用查询提示 `/*+ BROADCAST(t2) */` 手动控制。

### 陷阱 2：流模式下的 State 膨胀

**现象**：Regular Join State 持续增长直到 Checkpoint 超时。**原因**：双流 Join 需保留两侧全量 State，未设 TTL。**解决**：设 `table.exec.state.ttl=1h`、优先用 Interval Join / Lookup Join、启用 MiniBatch 减少状态访问。

### 陷阱 3：优化规则冲突导致无限循环

**现象**：优化阶段卡死，规则反复应用。**原因**：RULE_COLLECTION 模式下两条规则互为逆操作形成循环。**解决**：检查 `setIterations`（默认 5 次）、用 RULE_SEQUENCE 替代 RULE_COLLECTION、关闭易冲突规则集。

### 陷阱 4：两阶段聚合退化为单阶段

**现象**：预期 Local+Global，实际只有 GlobalAgg。**原因**：`agg-phase-strategy=ONE_PHASE` 或聚合函数不支持 `merge()`。**解决**：确认 `AUTO`、检查 `merge()` 实现、用 `EXPLAIN` 验证。

### 关键 `table.optimizer.*` 配置

| 配置项 | 默认值 | 作用 |
|--------|--------|------|
| `join-reorder-enabled` | false | 启用 Join 重排 |
| `agg-phase-strategy` | AUTO | 聚合阶段策略 |
| `reuse-sub-plan-enabled` | true | 子计划复用 |
| `distinct-agg.split.enabled` | false | Distinct 聚合拆分 |
| `multiple-input-enabled` | true | 批模式算子融合 |
| `dynamic-filtering.enabled` | true | 动态分区裁剪 |
| `runtime-filter.enabled` | false | 运行时过滤 |
| `bushy-join-reorder-threshold` | 12 | Bushy Join 搜索上限 |
| `join.broadcast-threshold` | 1MB | Broadcast 阈值 |

`org.apache.flink.table.api.config.OptimizerConfigOptions:L#39`

---

## 本章要点回顾

1. Flink 扩展 Calcite 的 RelNode 来携带流特有语义（ChangelogMode, Watermark, State），通过 FlinkConventions 三层 Convention 区分 Logical / StreamPhysical / BatchPhysical。
2. 优化分两个引擎：HepPlanner（基于规则，确定性）+ VolcanoPlanner（基于成本，枚举式），由 FlinkChainedProgram 编排为十多个阶段。
3. 关键优化技术：Sub-Plan Reuse（DAG 分解 + 消除重复）、Fusion（算子级代码融合）、Ability-based Pushdown（Source 能力协商）、ChangelogMode 推断（决定 State 策略）。
4. 流优化的第一优先级是最小化 State 大小——MiniBatch、Local-Global Agg、Incremental Agg 都为此服务。
5. 统计信息缺失是 CBO 最大的实战陷阱，默认基数估计往往严重偏离真实值。

## 源码导航

- FlinkConventions 定义：`flink-table-planner/.../plan/nodes/FlinkConventions.scala`
- FlinkLogical 节点：`flink-table-planner/.../plan/nodes/logical/`
- StreamPhysical 节点：`flink-table-planner/.../plan/nodes/physical/stream/`
- BatchPhysical 节点：`flink-table-planner/.../plan/nodes/physical/batch/`
- ExecNode 接口：`flink-table-planner/.../plan/nodes/exec/ExecNode.java`
- FlinkRelBuilder：`flink-table-planner/.../calcite/FlinkRelBuilder.java`
- ChangelogMode：`flink-table-common/.../connector/ChangelogMode.java`
- 流优化程序：`flink-table-planner/.../plan/optimize/program/FlinkStreamProgram.scala`
- 批优化程序：`flink-table-planner/.../plan/optimize/program/FlinkBatchProgram.scala`
- HepPlanner 程序：`flink-table-planner/.../plan/optimize/program/FlinkHepProgram.scala`
- VolcanoPlanner 程序：`flink-table-planner/.../plan/optimize/program/FlinkVolcanoProgram.scala`
- Sub-Plan Reuse：`flink-table-planner/.../plan/optimize/CommonSubGraphBasedOptimizer.scala`
- Fusion：`flink-table-planner/.../plan/fusion/FusionCodegenUtil.scala`
- 元数据/代价：`flink-table-planner/.../plan/metadata/`
- 谓词下推规则：`flink-table-planner/.../plan/rules/logical/PushFilterIntoTableSourceScanRule.java`
- 两阶段聚合：`flink-table-planner/.../plan/rules/physical/stream/TwoStageOptimizedAggregateRule.java`
- 增量聚合：`flink-table-planner/.../plan/rules/physical/stream/IncrementalAggregateRule.java`
- 优化器配置：`flink-table-api-java/.../config/OptimizerConfigOptions.java`
- Source Ability 体系：`flink-table-planner/.../plan/abilities/source/`
