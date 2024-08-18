# 第 5 章 · 逻辑图到物理图：JobGraph → ExecutionGraph 的转化

## 导读

- **一句话**：本章回答"从用户写的 DataStream API 到实际在集群上跑的多节点图结构，中间经历了几层图转换、每层做了什么优化"。
- **前置知识**：第 1 章的提交流程概览、第 1 章的 `isChainable()` 6 条判定条件。
- **读完本章你能回答**：
  - StreamGraph → JobGraph → ExecutionGraph 三层图分别存在哪里、谁生成、谁消费
  - ExecutionVertex vs Execution 的区别——为什么"Vertex 是位置，Execution 是尝试"？
  - `IntermediateResult` / `IntermediateResultPartition` / `ConsumedPartitionGroup` 的关系
  - `ExecutionGraph` 接口的 `attachJobGraph()` 如何将 JobGraph 展开为执行图

---

## 5.1 — 设计动机：编译时优化和运行时调度需要不同的图

计算机程序的编译管线中，源码 → IR → 目标码的分层是标准操作。Flink 将同一个思路应用于数据处理 DAG：

| 图层 | 对应阶段 | 类似编译概念 |
|------|---------|-------------|
| **StreamGraph** | Client 端，API 调用后立即生成 | AST（抽象语法树） |
| **JobGraph** | Client 端，提交前优化 | IR 中间表示（optimized IR） |
| **ExecutionGraph** | JobMaster 端，调度时实时维护 | Machine Code（物理表示） |

三层图的层层转换**正是一种编译过程**——每一层都抛弃上一层的"语法糖"和冗余信息，加入更多运行时约束。

---

## 5.2 — StreamGraph：最接近用户代码的拓扑

### 结构

`StreamGraph` 中的核心数据结构：

```java
// flink-runtime/.../streaming/api/graph/StreamGraph.java
public class StreamGraph {
    Map<Integer, StreamNode> streamNodes;          // node ID → 节点
    Map<Integer, Tuple2<Integer, List<String>>> virtualSelectNodes;  // 虚拟节点
    Map<Integer, Tuple2<Integer, OutputTag>> virtualSideOutputNodes;
    Map<Integer, Tuple3<Integer, StreamPartitioner<?>, StreamShuffleMode>> virtualShuffleNodes;
}
```

`StreamNode` 包含：
- 算子类型（Source / Map / KeyedProcess / Sink）
- 用户函数 (`StreamOperatorFactory`)
- 并行度
- 类型信息 (TypeInformation)
- 分区策略（keyBy → KeyGroupStreamPartitioner 等）

`StreamEdge` 描述两个节点之间的连接：
- 源和目标节点 ID
- 分区器类型（Forward / KeyBy / Rebalance / Broadcast 等）

**StreamGraph 的特征**：每个操作符是一个独立的 node。`dataStream.map().filter().keyBy().reduce()` 生成 5 个 StreamNode。

源码入口：`org.apache.flink.streaming.api.graph.StreamGraphGenerator`

### StreamGraph 的"虚拟节点"

在 `keyBy` / `partitionCustom` 等涉及 shuffle 的节点间会插入虚拟节点——这是一个占位节点，不生成实际算子，只记录"此处有数据分区变更"。这些虚拟节点在 StreamGraph→JobGraph 转换时被消除——分区策略直接写在 `StreamEdge` 上。

---

## 5.3 — JobGraph：算子链合并后的优化 IR

### StreamGraph → JobGraph 的转换

`StreamingJobGraphGenerator.createJobGraph()` 的完整步骤在第 1 章已有详细走读。核心是 `setChaining()`——遍历 StreamGraph 的所有 Source 节点，递归判断下游是否可以 chain。

### 算子链的合并条件（6 条判定，详见第 1 章）

`isChainable()` 和 `isChainableInput()` 的 6 条判定（`StreamingJobGraphGenerator.java:1734-1848`）：

| # | 条件 | 不满足的后果 |
|---|------|------------|
| 1 | 下游只有一个输入边 | 双输入算子（Join）不能 chain |
| 2 | `isChainingEnabled()` = true | `.disableChaining()` 禁止 |
| 3 | 同 SlotSharingGroup | 不同组不 chain |
| 4 | 上下游 ChainingStrategy 兼容 + 并行度相同 | `.disableChaining()` / 并行度不匹配 |
| 5 | 分区策略是 ForwardPartitioner | keyBy/broadcast 断链 |
| 6 | 无 Union（同 typeNumber 输入只有 1 条） | connect+union 断链 |

### JobGraph 的结构

```java
public class JobGraph {
    Map<JobVertexID, JobVertex> taskVertices;
}

public class JobVertex {
    JobVertexID id;
    int parallelism;  // 还是单个 int——尚未展开
    List<OperatorID> operatorIDs;  // chain 内的所有算子 ID
    List<IntermediateDataSet> producedDataSets;  // 产出边
    List<JobEdge> inputs;  // 消费边
}
```

`IntermediateDataSet` 是 JobVertex 产出的一条"数据边"——它有产出类型、分区模式。对应 Spark 中 Spark 的 `ShuffleDependency`（Spark 把 shuffle 建模为 RDD 之间的 dependency，Flink 把它模型化在边对象本身）。

---

## 5.4 — ExecutionGraph：展开并行度后的运行时图

### ExecutionGraph 接口

`ExecutionGraph` 是核心接口（`flink-runtime/.../executiongraph/ExecutionGraph.java:81`）：

```java
public interface ExecutionGraph extends AccessExecutionGraph {
    void start(ComponentMainThreadExecutor jobMasterMainThreadExecutor);
    SchedulingTopology getSchedulingTopology();
    void enableCheckpointing(...);
    CheckpointCoordinator getCheckpointCoordinator();
    Iterable<ExecutionJobVertex> getVerticesTopologically();
    Iterable<ExecutionVertex> getAllExecutionVertices();
    ExecutionJobVertex getJobVertex(JobVertexID id);
    Map<JobVertexID, ExecutionJobVertex> getAllVertices();
    Map<IntermediateDataSetID, IntermediateResult> getAllIntermediateResults();
    void attachJobGraph(List<JobVertex> topologicallySorted, ...) throws JobException;
    void transitionToRunning();
    void cancel();
    void suspend(Throwable suspensionCause);
    void failJob(Throwable cause, long timestamp);
    CompletableFuture<JobStatus> getTerminationFuture();
}
```

**关键方法 `attachJobGraph()`**：将拓扑排序后的 JobVertex 列表展开为 ExecutionGraph——这是从"逻辑"到"物理"的关键一步。

### 核心对象关系

```
JobGraph 层:          ExecutionGraph 层:
───────────          ─────────────────
JobVertex (1个)  →   ExecutionJobVertex (1个，持有聚合信息)
  parallelism=4       ├── ExecutionVertex x 4 (按并行度展开)
                      │     ├── currentExecution: Execution    ← 当前运行尝试
                      │     └── executionHistory: 执行历史
                      └── IntermediateResult (1个)
                            └── IntermediateResultPartition x 4
```

### ExecutionVertex：并行子任务的位置

`ExecutionVertex` 是 DAG 中的"位置"（`flink-runtime/.../executiongraph/ExecutionVertex.java:60`）：

```java
public class ExecutionVertex implements AccessExecutionVertex, Archiveable<ArchivedExecutionVertex> {
    final ExecutionJobVertex jobVertex;
    private final int subTaskIndex;
    private final ExecutionVertexID executionVertexId;
    Execution currentExecution;  // ← 当前运行尝试（永不为 null）
    final ExecutionHistory executionHistory;
    private final Map<IntermediateResultPartitionID, IntermediateResultPartition> resultPartitions;
    private int nextAttemptNumber;
    @Nullable private TaskManagerLocation lastAssignedLocation;
    @Nullable private AllocationID lastAssignedAllocationID;
}
```

**关键设计**：`currentExecution` 永不为 null——Vertex 创建时就会创建第一个 Execution。当 Task 失败重试时，不是修改现有 Execution 的状态，而是创建新的 Execution 对象替代 `currentExecution`，旧的 Execution 移入 `executionHistory`。

Vertex 的标识格式：`"myTask (2/7)"`——第 2 个子任务，总共 7 个并行度。

### Execution vs ExecutionVertex

这是 Flink 运行时模型最精妙的设计之一：

| 概念 | 含义 | 生命周期 |
|------|------|---------|
| ExecutionVertex | DAG 中的静态位置 | 从创建到 Job 结束 |
| Execution | Vertex 的一次运行尝试 | 从 CREATED 到终态（FINISHED/CANCELED/FAILED） |

**Execution 不是 Vertex**——它表示 Vertex 的一次运行尝试（attempt）。Vertex 是 DAG 中的静态位置，Execution 是动态实例。当 Task 失败重试时，Vertex 不变而创建新的 Execution。

所有 JM ↔ TM 的通信（deploy task、状态更新、checkpoint 触发）都使用 `ExecutionAttemptID` 而非 `ExecutionVertexID`——这保证了对"哪一次尝试"的精确追踪。

### IntermediateResult 和 IntermediateResultPartition

```
上游 ExecutionJobVertex
  └── IntermediateResult (逻辑边，1条)
        └── IntermediateResultPartition x N (物理分区，每个 ExecutionVertex 产出1个)

下游 ExecutionVertex
  └── ConsumedPartitionGroup (消费组——包含需要读取的所有上游 partition)
```

**分区策略决定 ConsumedPartitionGroup 的内容**：
- Forward/KeyBy：下游每个 vertex 只消费 1 个 partition
- Rebalance/Broadcast：下游每个 vertex 消费所有 N 个 partition

---

## 5.5 — 三图对比速查

| | StreamGraph | JobGraph | ExecutionGraph |
|---|---|---|---|
| **在哪里** | Client | Client → Dispatcher | JobMaster |
| **节点粒度** | 每个操作符一个节点 | 合并成 JobVertex（chain合并） | 每并行度一个 ExecutionVertex |
| **并行度** | StreamNode.parallelism (单个int) | JobVertex.parallelism (单个int) | N × ExecutionVertex |
| **可以被序列化** | 否 | 是 | 是 |
| **生命周期** | 生成后不变 | 提交后不变 | 随时间变化（执行、失败、重试） |
| **类似编译** | AST | Optimized IR | Machine Code |

---

## 5.6 — 横向对比

### vs Spark 的 DAGScheduler

Spark 的 DAGScheduler 把 `RDD DAG` → Split 成 `Stage`（ShuffleMapStage / ResultStage）。每个 Stage 对应 Spark 里面的 `TaskSet`。这和 Flink 的 `JobVertex` 概念相当，但 Spark 的 Stage 是"等待所有上游 Stage 完成"的——而 Flink 的 JobVertex 表现为"直接同时在线且 Pipe 数据"。

Spark 没有 Execution 的概念——Task 失败后直接重新调度一个新 Task，不追踪历史 attempt。Flink 的 ExecutionVertex + Execution 历史机制为 checkpoint 和 failover 提供了精确的状态追踪。

### vs StarRocks Fragment

StarRocks 的 `PlanFragment` 概念与 JobVertex 类似——过程中的算子合并发生在 Fragment 内。但 Fragment 间的数据交换是"上游 Fragment 跑完给下游"，而 Flink shuffle 两边同时在线持续传送数据。

---

## 5.7 — 调优与实战陷阱

### 算子链被意外打断

最常见场景：在两个 map 之间插了一个 `.partitionCustom()` 或者加了 `.disableChaining()`。结果：两个算子不能 chain → 多一次序列化+网络开销 → 吞吐下降 2-5x。

排查工具：在 Flink Web UI 中查看 JobGraph 的拓扑——如果有超预期的 JobVertex 数量（应该比你的操作符少得多），说明 chain 没按预期合并。

### 并行度和 Slot 的匹配

`ExecutionGraph` 的总 task 数 = sum(各 JobVertex 的并行度)。如果所有 SharingGroup 为默认（都共用同一个 group），那么需要的 Slot 数 = max(所有 JobVertex 的并行度)。这个数应 ≤ 集群的总 Slot 数。否则调度会死锁，Web UI 一直显示 `CREATED` 或 `SCHEDULED` 不动。

---

## 本章要点回顾

1. 三层图对应三步编译——StreamGraph（AST）、JobGraph（IR）、ExecutionGraph（machine code）。
2. 算子链合并在 StreamGraph→JobGraph 阶段完成——6 个条件缺一不可（详见第 1 章）。
3. ExecutionGraph 展开并行度并引入 Execution（运行尝试）概念——Vertex 是位置，Execution 是尝试。
4. `ExecutionGraph.attachJobGraph()` 是从逻辑到物理的关键方法——JobVertex 展开为 ExecutionVertex + IntermediateResultPartition。
5. 所有 JM↔TM 通信使用 `ExecutionAttemptID` 而非 `ExecutionVertexID`——精确追踪"哪一次尝试"。

## 源码导航

- StreamGraph：`flink-runtime/.../streaming/api/graph/StreamGraph.java`
- StreamGraphGenerator：`flink-runtime/.../streaming/api/graph/StreamGraphGenerator.java`
- StreamingJobGraphGenerator：`flink-runtime/.../streaming/api/graph/StreamingJobGraphGenerator.java`（`createJobGraph()` L222, `isChainable()` L1734）
- JobGraph：`flink-runtime/.../jobgraph/JobGraph.java`
- JobVertex：`flink-runtime/.../jobgraph/JobVertex.java`
- ExecutionGraph 接口：`flink-runtime/.../executiongraph/ExecutionGraph.java`（L81）
- ExecutionVertex：`flink-runtime/.../executiongraph/ExecutionVertex.java`（L60）
- ExecutionJobVertex：`flink-runtime/.../executiongraph/ExecutionJobVertex.java`
