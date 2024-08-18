# 第 6 章 · 调度策略：从 Eager 到 Adaptive 的演进

## 导读

- **一句话**：本章回答"Flink 决定'下一步该调度哪个 Task'的逻辑是什么，以及自适应调度如何在运行时调整并行度"。
- **前置知识**：第 5 章 ExecutionGraph 结构、基本的图算法（拓扑排序）。
- **读完本章你能回答**：
  - Eager Scheduling 为什么适合流而 Adaptive 为什么适合批
  - Pipelined Region 的概念——它是怎么把 DAG 切成独立调度单元的
  - Adaptive Scheduler 的动态并行度是怎么决策的
  - Adaptive Batch Scheduler 怎么根据上游产出数据量自动决定下游并行度

---

## 6.1 — 设计动机：流和批对调度的要求截然不同

### 流的要求
- 所有算子需要**同时在线**——管道的源端、中间算子、sink 都长期存活
- 调度越快越好——初始化时一次性把所有 Task 部署完
- 对并行度变化不敏感——通常用户会预先确定并行度

### 批的要求  
- 算子可以**按阶段运行**——上游完成后再跑下游
- 调度需要适配数据量——如果上游产出了少量数据，下游就不需要那么多并行实例
- 对并行度变化敏感——自动调整并行度可以显著改善批作业性能

Flink 的调度策略演进回答了这个问题：**怎样让同一个引擎原生支持两种截然不同的调度模型**。

---

## 6.2 — 调度核心组件

```
Scheduler (SchedulerBase)
├── SchedulingStrategy        ← 调度逻辑
│   ├── EagerSchedulingStrategy
│   ├── LazyFromSourcesSchedulingStrategy
│   └── PipelinedRegionSchedulingStrategy
├── SlotProvider (SlotPool)   ← Slot 分配
├── ExecutionGraph            ← 被调度的图
└── SchedulingTopology        ← ExecutionGraph 的拓扑适配层
```

### SchedulerBase：调度器的公共基类

`SchedulerBase` 是所有调度器的公共基类（`flink-runtime/.../scheduler/SchedulerBase.java`），持有以下核心字段：

```java
public abstract class SchedulerBase implements Scheduler {
    private final ExecutionGraph executionGraph;       // 被调度的执行图
    private final SchedulingStrategy schedulingStrategy; // 调度策略
    private final SlotPoolService slotPoolService;      // Slot 池服务
    private final ExecutionOperations executionOperations; // Execution 操作封装
    private final ExecutionVertexVersioner executionVertexVersioner; // 版本追踪
    private final InputsLocationsRetriever inputsLocationsRetriever; // 输入位置检索
}
```

**关键方法 `startScheduling()`**：

```java
// SchedulerBase.java
public final void startScheduling() {
    registerJobMetrics();
    schedulingStrategy.startScheduling();  // ← 委托给具体策略
}
```

**关键方法 `deployTask()`**：

```java
// SchedulerBase.java
private void deployTask(ExecutionVertex executionVertex, ...) {
    final Execution execution = executionVertex.getCurrentExecutionAttempt();
    // 创建 TaskDeploymentDescriptor → 发送给 TaskExecutor
    execution.deploy(slotProvider, slotRequestId, ...);
}
```

### SchedulingTopology：调度视图

`SchedulingTopology` 是 ExecutionGraph 的调度视图——它只暴露调度相关的接口（不暴露 checkpoint、accumulator 等非调度信息）：

```java
public interface SchedulingTopology {
    Iterable<SchedulingExecutionVertex> getVertices();
    Iterable<SchedulingResultPartition> getResultPartitions();
    Iterable<PipelinedRegion> getAllPipelinedRegions();
}
```

源码入口：
- `flink-runtime/.../scheduler/SchedulerBase.java`
- `flink-runtime/.../scheduler/strategy/SchedulingStrategy.java`
- `flink-runtime/.../scheduler/strategy/SchedulingTopology.java`

---

## 6.3 — Eager Scheduling：流作业的一键启动

```java
// 逻辑最简单：所有 ExecutionVertex 一次性调度
public class EagerSchedulingStrategy implements SchedulingStrategy {
    void startScheduling() {
        // 把所有 vertex 标记为 SCHEDULED
        // 为每个 vertex 启动 Slot 申请和部署
    }
}
```

适用于流的理由：所有 Task 长期在线，立即启动一切是最优决策。缺点：**必须等待所有 Slot 都到位**——非共享 Slot 如果不够 job 就永远不启动。这就是为什么流作业推荐 `SlotSharingGroup`（让所有算子复用同一组 Slot）。

---

## 6.4 — Lazy From Sources：从"发源地"开始

```
LazyFromSourcesSchedulingStrategy:
1. 标记所有 Source 为 ready to schedule
2. Source 部署后 → 标记所有只能被 Source 通电的消费者为 ready
3. 逐步推进直到所有 vertex 被调度
```

**为什么能更早开始跑？** 不是非要所有 Slot 一次到位——只要有足够的 Slot 跑 Source 就能先开始产出数据，后面下游再慢慢跟随。这在资源受限的共享集群上特别有用。

---

## 6.5 — Pipelined Region：因连接的调度边界

### 概念

`PipelinedRegionSchedulingStrategy` 的核心理念是：**按 Pipelined Region 独立调度**。

```
Pipelined Region = 区域内所有边都是 Pipeline（有界的流水线连接，数据同步流动）
                + 区域的输入要么是 Source，要么是 Blocking 边（上游区域已完成）
```

想象这个 DAG：
```
Source → Map → [shuffle-A] → Reduce-1 → [shuffle-B] → Reduce-2 → Sink
```
这里 Source+Map 是一个 PipelinedRegion；Reduce-1 是第二个；Reduce-2+Sink 是第三个。Shuffle 边是 Region 的边界。

**每个 Region 内**：所有算子同时调度、pipeline 数据。
**Region 之间**：上游 Region 所有跑完成以后，下游 Region 才能开始——类似 Spark 的"Staged"调度。

### 调度流程

```
PipelinedRegionSchedulingStrategy:
1. 扫描输入为 Source 的 Region → 立即调度
2. 该 Region 内所有 ExecutionVertex 完成 → 标记其输出为 Consumable
3. 检查下游 Region 的所有输入是否都 Consumable → 调度该 Region
4. 重复直到最后 Region 完成
```

源码入口：`flink-runtime/.../scheduler/strategy/PipelinedRegionSchedulingStrategy.java`

### Vertex 的 Consumable 判断

`InputConsumableDecider` 决定一个 ExecutionVertex 的输入是否可以开始消费：

```java
public interface InputConsumableDecider {
    boolean isInputConsumable(ExecutionVertexID, Set<ExecutionVertexID>, ...);
}
```

三种实现：
- `AllFinishedInputConsumableDecider`：所有上游 Vertex 都跑完 → Consumable（最严格，批默认）
- `PartialFinishedInputConsumableDecider`：上游部分完成 → Consumable（需要 Non-blocking 边支持）
- `DefaultInputConsumableDecider`：根据边的类型混合判断

---

## 6.6 — Adaptive Scheduler：运行时调整并行度

### 核心思路

**先提交，后决策**：Adaptive Scheduler 不要求用户预先确定并行度——运行中根据"已完成的 Subtask 数量和产出数据量"动态决定下游该跑多少个实例。

```
JobMaster
  ├── AdaptiveScheduler
  │   ├── 初始并行度 = -1（未知）
  │   └── 等待 Source 跑完
  ├── Source 跑完后 → 基于产出量自动确定下游并行度
  ├── 创建对应的 ExecutionVertex
  └── 部署到 TaskManager
```

### 适用场景

- 批处理的写入操作（INSERT INTO）：不知道 Hive/File Sink 该有多少并行 writer
- 弹性伸缩：运行中可以自动调整算子实例数以应对流量变化

源码入口：
- `flink-runtime/.../scheduler/adaptive/AdaptiveScheduler.java`

---

## 6.7 — Adaptive Batch Scheduler：面向批的智能调度

### 问题

传统 Flink batch 中 parallel = 用户显式指定。如果对一个超大 join key 展开 512 度的 instance，但只有一个 key 有数据——511 个 instance 在空闲等那一个跑完。Adaptive Batch 自动变化并行度解决这种情况。

### 核心机制

```
上游 vertex 跑完 → 报告产出数据量（ResultPartitionBytes 统计）
  → AdaptiveBatchScheduler 根据产出量确定下游的并行度
  → 自动展开 ExecutionVertex
  → 做数据分区分配
```

源码入口：
- `flink-runtime/.../scheduler/adaptivebatch/AdaptiveBatchScheduler.java`

`AdaptiveBatchScheduler` 里有 `SchedulingTopology` 遍历所有可判断的子图结构——类似于 Spark SQL 中 AQE（Adaptive Query Execution）根据中间 shuffle 大小动态决定下游并行度。区别是：Flink 的这个判断在 JobMaster 层面，Spark 的在 DAGScheduler 根据 shuffle map output 大小调整后面阶段。

---

## 6.8 — Slow Task Detector：推测执行

批处理中的"Slow Task"会影响整个 Stage 的延迟——因为下游要等所有上游完成。Flink 做的推测执行（Speculative Execution）跟 Hadoop/Spark 类似：**检测到某个 Subtask 坐得很慢 → 在新的 Slot 启动同样的 Subtask → 谁先完成用谁的结果 → 杀掉慢的**。

`SlowTaskDetector` 监控每个 Execution 的进度/持续时间跟同批次的平均时间对比：
- 如果持续时间超过 `execution.batch.speculative.threshold-multiplier` 倍的平均值 → 标记为 Slow → 触发推测执行

源码入口：`flink-runtime/.../scheduler/slowtaskdetector/SlowTaskDetector.java`

---

## 6.9 — 调度演进总结

| 调度策略 | 适合 | 核心机制 |
|---------|------|---------|
| **Eager** | 流作业（所有 Task 长期在线） | 一次性部署所有 vertex |
| **Lazy From Sources** | 资源受限的流作业 | 从 Source 逐步扩散部署 |
| **Pipelined Region** | 混合 DAG（有 Blocking 有 Pipelined） | 按 block shuffle 边界切成语义独立的 Region 执行 |
| **Adaptive** | 不确定并行度的长作业 | 运行时根据已完成的 Workload 决定下游并行度 |
| **Adaptive Batch** | 标准批作业 | 根据产出量自动变化下游并行度 + 推测执行 |

---

## 6.10 — 横向对比

### vs Spark AQE（Adaptive Query Execution）

- Spark AQE 根据 shuffle 后的 partition 数据做自动优化（切换 join 策略、调整 reducer 数、优化 skew join）
- Flink Adaptive Batch Scheduler 是一个全局调度框架——比 AQE 调整 reducer 数更广：它可以在运行中重新规划整个图结构
- AQE 作用于 Spark SQL 的物理计划层，Adaptive Batch 是 Flink 的通用调度层——可以用于 DataStream API 的 batch 作业，可以不依赖 SQL

### vs MaxCompute Staged Scheduler

MaxCompute 和 Flink Pipelined Region 的思想非常相似（按 Stage 执行），但 MaxCompute 的 Stage 是静态的——执行前完全确定、不可变；Flink 的可以自适应动态调整。

---

## 6.11 — 调优与实战陷阱

### 用 Eager 踩到的 Slot Deadlock

最常见场景：ExecutionGraph ready 但 20% 的 Vertex 因为没有 Slot 一直停在 SCHEDULED。其它 80% 已经 Running 并产生数据给下游——但下游还没 Slot 所以不运行，触发反压一路传到上游。这形成了一个"等 Slot"的状态。

解法：要么加大集群的资源（增加 YARN/K8s 的 Container 数）要么用 `SlotSharingGroup` 把相关的 Task 放同一 Slot。

### Pipelined Region 中的数据边界

设置 breakpoint 在 `PipelinedRegionSchedulingStrategy` 中观察每个 Region 的调度顺序——可以理解为什么有时候图没有按预期并行。

### Adaptive Batch 中手动并行度高于自动判断

如果你用自适应批调度，但又显式 `.parallelism(10)` 声明了并行度——Adaptive Batch 会尊重你的声明而不会自动变化。这既保证了可用性也尊重了用户意图。

---

## 本章要点回顾

1. 五种调度策略对应不同的场景——Eager（流）、Lazy From Sources（弹性流）、Pipelined Region（混合）、Adaptive（弹性长作业）、Adaptive Batch（批处理）。
2. Pipelined Region 将 DAG 按 shuffle 边切片——Region 内部流水线调度，Region 之间按 Stage 调度。
3. Adaptive Scheduler 接受运行时并行度改变——类似 AQE 但范围更广、通用性更高。
4. Slow Task Detector 探测慢任务并启动推测执行——批处理场景的性能安全网。

## 源码导航

- SchedulingStrategy 接口：`flink-runtime/.../scheduler/strategy/SchedulingStrategy.java`
- Eager：`flink-runtime/.../scheduler/strategy/EagerSchedulingStrategy.java`
- PipelinedRegion：`flink-runtime/.../scheduler/strategy/PipelinedRegionSchedulingStrategy.java`
- AdaptiveScheduler：`flink-runtime/.../scheduler/adaptive/AdaptiveScheduler.java`
- AdaptiveBatchScheduler：`flink-runtime/.../scheduler/adaptivebatch/AdaptiveBatchScheduler.java`
- SlowTaskDetector：`flink-runtime/.../scheduler/slowtaskdetector/SlowTaskDetector.java`
- SchedulingTopology：`flink-runtime/.../scheduler/strategy/SchedulingTopology.java`
