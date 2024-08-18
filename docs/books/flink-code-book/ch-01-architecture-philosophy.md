# 第 1 章 · Flink 的架构哲学：流优先的一体化引擎

## 导读

- **一句话**：本章回答"Flink 的进程模型长什么样、各个组件怎么协作把一段用户代码变成一个运行中的 Job"。
- **前置知识**：分布式系统基本概念（主从架构、服务发现），对 Spark Driver/Executor 模型有了解即可。
- **读完本章你能回答**：
  - Flink 的 JobManager 和 Spark Driver 的职责划分有什么本质不同？
  - Dispatcher、ResourceManager、JobMaster 三者怎样分工？
  - 为什么 Flink 强调"流优先"，而 Spark 强调"批优先"——它俩的运行时架构差异在哪？
  - 一个 `StreamExecutionEnvironment.execute()` 到底经历了哪些进程和线程？
  - `isChainable()` 的 6 个判定条件分别是什么？

---

## 1.1 — 设计动机：为什么流批一体要从运行时开始统一

### 流与批，差异不在 API，在调度

大多数人对"流批一体"的理解停留在 API 层——同一套 SQL 或 DataStream API 既能跑批也能跑流。但这不是 Flink 的野心。

Flink 的真正野心是：**让运行时（Runtime）天然就是流的，批只是流的一个特例**。这句话可以这样理解：

| | 流 | 批 |
|---|---|---|
| 输入 | 无限，实时到达 | 有限，已经存在 |
| 输出 | 持续产出 | 一次性结果 |
| 调度 | 所有算子长期存活 | 上游算完下游再算 |
| 容错 | 状态兜底 | 重跑即可 |

为什么这很重要？因为**如果运行时是批的，流就是在批上模拟出来的**——这就是 Spark Streaming 的 Micro-batch 方案。Micro-batch 会引入一个根本性妥协：**延迟的下界是 mini-batch 的间隔**。而如果运行时是流的，批只是"输入有限，所以会在某个时刻完成"的流，不需要 hack。

### 流优先运行时的推论

一旦运行时确定以流为核心，以下架构决策是自然的：

1. **算子是长期运行的对象**（而不是 Stage-by-Stage 临时实体），它们需要彼此之间永久连接着的消费关系。
2. **数据传输是流水线式的**（Pipeline），上游产出即推下游，而不是必须等一个 stage 全算完再做 shuffle。
3. **状态是算子的一部分**，不是外部 KV 存储——需要 checkpoint 来保证 fault tolerance。

这三点直接塑造了 Flink 的进程模型。

---

## 1.2 — 架构全景图

### 进程模型

Flink 集群的进程只有两类（加上客户端就是三类）：

```
             ┌──────────────┐
             │   Client     │  提交 Jar / JobGraph
             └──────┬───────┘
                    │ REST / RPC Submit
                    ▼
    ┌───────────────────────────────┐
    │        JobManager             │
    │  ┌────────────────────────┐   │
    │  │    Dispatcher          │   │  ← 接收提交、启动 JobMasterRunner
    │  ├────────────────────────┤   │
    │  │    ResourceManager     │   │  ← 管理 TaskManager 的 Slot
    │  ├────────────────────────┤   │
    │  │  JobMaster (per job)   │   │  ← 核心：持有 ExecutionGraph
    │  └────────────────────────┘   │     发 Task 给 TaskManager
    └──────────────┬────────────────┘
                   │ RPC (Akka)
                   │ 心跳 / Deploy Task
                   ▼
    ┌──────────────────────────────┐
    │        TaskManager            │
    │  ┌────────┐  ┌────────┐      │
    │  │  Slot  │  │  Slot  │ ...  │  ← 每个 Slot 可跑一个 Task
    │  │ ┌────┐ │  │ ┌────┐ │      │     多个算子链成 OperatorChain
    │  │ │Task│ │  │ │Task│ │      │
    │  │ └────┘ │  │ └────┘ │      │
    │  └────────┘  └────────┘      │
    └──────────────────────────────┘
```

Dispatcher、ResourceManager、JobMaster **在同一个 JVM 进程**（JobManager 进程）中，它们之间通过本地方法调用而非 RPC 通信。

### 各组件的职责

**Dispatcher**（`org.apache.flink.runtime.dispatcher.Dispatcher`）
- 提供 REST API（通过 `DispatcherRestEndpoint`）接收客户端提交的 Job
- 为每个 Job 启动一个 `JobMasterRunner`（通过 leader election 决定是否激活）
- 管理 JobManagerRunner 的注册（`DefaultJobManagerRunnerRegistry`）
- 也是 Web UI 的后端

**ResourceManager**（`org.apache.flink.runtime.resourcemanager.ResourceManager`）
- 管理所有注册的 TaskManager
- 管理 Slot 资源分配
- 对接外部资源平台（YARN/K8s）申请释放计算节点
- 具体实现：`StandaloneResourceManager`（独立集群）/ Active ResourceManager（容器化部署）

**JobMaster**（`org.apache.flink.runtime.jobmaster.JobMaster`）
- 一个 Job 一个实例——这是 Flink 最核心的运行时组件
- 持有 `ExecutionGraph`（物理执行图），是任务的逻辑大脑
- 负责调度、checkpoint 协调、failover
- **跟 Spark DAGScheduler + TaskScheduler 合起来对标**，但它比这两者的职权范围更广——JobMaster 还管 CheckpointCoordinator、SlotPool

**TaskManager**（`org.apache.flink.runtime.taskexecutor.TaskExecutor`）
- 运行实际 Task 的 JVM 进程
- 管理自己的 Slot 资源，每个 Slot 有固定份额的内存
- 提供数据交换的 Network Buffer Pool
- 连接服务：`TaskExecutorToResourceManagerConnection`（向 RM 注册）、心跳

**Client**
- 编译 StreamGraph → JobGraph
- 将 Jar/JobGraph 提交到 Dispatcher
- 客户端可以是 `flink run` 命令（`CliFrontend`）、SQL Client、IDE 中运行的 `env.execute()` 调用

### 和 Spark 的对照

| 概念 | Flink | Spark |
|------|-------|-------|
| 作业提交入口 | Dispatcher | SparkSubmit → Driver |
| 资源管理 | ResourceManager | ClusterManager (YARN/K8s) + Driver 内置 |
| 作业调度 | JobMaster | DAGScheduler + TaskScheduler（均在 Driver 内） |
| 执行节点 | TaskManager | Executor |
| 执行单元 | Slot | Core（线程） |
| 物理计划 | ExecutionGraph | DAG of Stages |
| 状态 | StateBackend（算子本地状态） | 无内置状态 |

关键差别：**Flink 的 JobMaster 职责比 Spark Driver 中的调度组件更重**——它同时承担 checkpoint 协调、容错恢复、SlotPool 管理。而 Spark Driver 额外还需要跑 DAG 转换和优化逻辑，Flink 的这些工作在 Client 端就完成了。

---

## 1.3 — 集群启动：从 `ClusterEntrypoint` 到三大组件就位

### 启动链路源码走读

`ClusterEntrypoint` 是所有 Flink 集群启动的基类。以 Standalone Session 模式为例：

```
bin/start-cluster.sh
  → StandaloneSessionClusterEntrypoint.main()
    → ClusterEntrypoint.startCluster()
      → runCluster(configuration, pluginManager)
        → initializeServices()         // ① 初始化所有基础服务
        → createDispatcherResourceManagerComponentFactory()  // ② 工厂
        → factory.create(...)          // ③ 创建 Dispatcher + RM + JobMasterRunner
```

**① `initializeServices()`** 做了什么（`ClusterEntrypoint.java:334`）：

```java
protected void initializeServices(Configuration configuration, PluginManager pluginManager) {
    // 1. 生成 ResourceID（本 JM 进程的唯一标识）
    resourceId = ... ResourceID.generate();

    // 2. 创建 RPC Service（基于 Akka）
    rpcSystem = RpcSystem.load(configuration);  // SPI 加载
    commonRpcService = RpcUtils.createRemoteRpcService(rpcSystem, ...);

    // 3. 创建 IO 线程池（用于非 RPC 的异步操作）
    ioExecutor = Executors.newFixedThreadPool(...);

    // 4. 创建 HA Services（ZK 或 Standalone）
    haServices = createHaServices(configuration, ioExecutor, rpcSystem);

    // 5. 启动 BlobServer（大对象传输：Jar、User Code）
    blobServer = BlobUtils.createBlobServer(configuration, ..., haServices.createBlobStore());

    // 6. 创建心跳服务
    heartbeatServices = createHeartbeatServices(configuration);

    // 7. 创建 Metrics Registry
    metricRegistry = createMetricRegistry(configuration, pluginManager, rpcSystem);

    // 8. 创建 ArchivedApplicationStore（用于恢复场景）
    archivedApplicationStore = createArchivedApplicationStore(...);
}
```

**③ `factory.create()`** 做了什么（`DefaultDispatcherResourceManagerComponentFactory.java:104`）：

```java
public DispatcherResourceManagerComponent create(...) {
    // 1. 从 HA Services 获取 Leader 选举/检索服务
    dispatcherLeaderRetrievalService = haServices.getDispatcherLeaderRetriever();
    resourceManagerRetrievalService = haServices.getResourceManagerLeaderRetriever();

    // 2. 创建并启动 REST Endpoint（Web UI + REST API）
    webMonitorEndpoint = restEndpointFactory.createRestEndpoint(...);
    webMonitorEndpoint.start();

    // 3. 创建 ResourceManagerService
    resourceManagerService = ResourceManagerServiceImpl.create(
        resourceManagerFactory, configuration, resourceId, rpcService, ...);

    // 4. 创建 DispatcherRunner（内含 Dispatcher，通过 Leader Election 激活）
    dispatcherRunner = dispatcherRunnerFactory.createDispatcherRunner(
        haServices.getDispatcherLeaderElection(),  // 选举 latch
        fatalErrorHandler,
        new HaServicesPersistenceComponentFactory(haServices),
        rpcService,
        partialDispatcherServices);

    // 5. 启动 ResourceManagerService
    resourceManagerService.start();

    // 6. 启动 Leader 检索（让 RM/Dispatcher 互相发现）
    resourceManagerRetrievalService.start(resourceManagerGatewayRetriever);
    dispatcherLeaderRetrievalService.start(dispatcherGatewayRetriever);

    return new DispatcherResourceManagerComponent(
        dispatcherRunner, resourceManagerService, ...);
}
```

**关键理解**：Dispatcher 和 ResourceManager 的启动是**先参加 Leader Election，抢到 latch 后才真正激活**。这保证了 HA 模式下只有一个活跃的 Dispatcher 和 RM。

---

## 1.4 — 从 `env.execute()` 到 Task 运行：一次完整的提交流程

### 阶段 1：客户端生成 StreamGraph → JobGraph

```
用户代码: StreamExecutionEnvironment env = ...; env.execute("job-name")
  → StreamGraphGenerator.generate()          // 生成 StreamGraph
  → StreamingJobGraphGenerator.createJobGraph()  // 转换成 JobGraph
  → PipelineExecutor 通过 REST API 提交到 Dispatcher
```

源码入口：
- `flink-runtime/.../streaming/api/graph/StreamGraphGenerator.java`
- `flink-runtime/.../streaming/api/graph/StreamingJobGraphGenerator.java`

### `StreamingJobGraphGenerator.createJobGraph()` 的完整步骤

```java
// StreamingJobGraphGenerator.java:222
private JobGraph createJobGraph() {
    preValidate(streamGraph, userClassloader);   // 校验

    setChaining();    // ★ 核心：决定哪些算子合并成同一个 JobVertex

    if (jobGraph.isDynamic()) {
        setVertexParallelismsForDynamicGraphIfNecessary();
    }

    setAllOperatorNonChainedOutputsConfigs(...);  // 配置非 chain 输出
    setAllVertexNonChainedOutputsConfigs(...);

    setPhysicalEdges(...);       // 设置物理边（ResultPartition → InputGate）

    markSupportingConcurrentExecutionAttempts(...);

    setSlotSharingAndCoLocation(...);   // ★ 设置 SlotSharingGroup
    setManagedMemoryFraction(...);      // 设置内存比例

    // 异步序列化算子配置（并行化，用线程池加速）
    serializeOperatorCoordinatorsAndStreamConfig(serializationExecutor, ...);

    return jobGraph;
}
```

### `isChainable()` — 算子链合并的判定条件

这是 `StreamingJobGraphGenerator.java:1734` 的核心判定逻辑：

```java
public static boolean isChainable(StreamEdge edge, StreamGraph streamGraph,
                                   boolean allowChainWithDefaultParallelism) {
    StreamNode downStreamVertex = streamGraph.getTargetVertex(edge);

    // 条件 1: 下游算子只有一个输入
    return downStreamVertex.getInEdges().size() == 1
            && isChainableInput(edge, streamGraph, allowChainWithDefaultParallelism);
}
```

`isChainableInput()` 内部（`StreamingJobGraphGenerator.java:1756`）包含完整 6 条判定：

```java
private static boolean isChainableInput(StreamEdge edge, StreamGraph streamGraph, ...) {
    StreamNode upStreamVertex = streamGraph.getSourceVertex(edge);
    StreamNode downStreamVertex = streamGraph.getTargetVertex(edge);

    // 条件 2: 全局 chaining 开启
    // 条件 3: 上下游属于同一个 SlotSharingGroup
    // 条件 4: areOperatorsChainable() → 上下游算子的 ChainingStrategy 兼容
    //   - 上游 NEVER → 不可 chain
    //   - 下游 NEVER / HEAD → 不可 chain
    //   - 上下游并行度相同
    // 条件 5: arePartitionerAndExchangeModeChainable() → 分区策略是 Forward
    //   - ForwardPartitioner 且非 BATCH 交换模式 → 可 chain
    //   - 其他分区策略 → 不可 chain
    if (!(streamGraph.isChainingEnabled()
            && upStreamVertex.isSameSlotSharingGroup(downStreamVertex)
            && areOperatorsChainable(upStreamVertex, downStreamVertex, streamGraph, ...)
            && arePartitionerAndExchangeModeChainable(
                    edge.getPartitioner(), edge.getExchangeMode(), ...))) {
        return false;
    }

    // 条件 6: 下游没有 Union 操作（同 typeNumber 的输入边只有一条）
    for (StreamEdge inEdge : downStreamVertex.getInEdges()) {
        if (inEdge != edge && inEdge.getTypeNumber() == edge.getTypeNumber()) {
            return false;
        }
    }
    return true;
}
```

**6 条判定总结**：

| # | 条件 | 不满足的后果 |
|---|------|------------|
| 1 | 下游只有一个输入边 | 双输入算子（Join）不能 chain |
| 2 | `isChainingEnabled()` = true | `.disableChaining()` 禁止 |
| 3 | 同 SlotSharingGroup | 不同组不 chain |
| 4 | 上下游 ChainingStrategy 兼容 + 并行度相同 | `.disableChaining()` / 并行度不匹配 |
| 5 | 分区策略是 ForwardPartitioner | keyBy/broadcast 断链 |
| 6 | 无 Union（同 typeNumber 输入只有 1 条） | connect+union 断链 |

### 阶段 2：Dispatcher 接收并启动 JobMaster

```
Client --[REST]--> Dispatcher.submitJob()
```

`Dispatcher.submitJob()` 源码走读（`Dispatcher.java:835`）：

```java
public CompletableFuture<Acknowledge> submitJob(ExecutionPlan executionPlan, Duration timeout) {
    final JobID jobID = executionPlan.getJobID();

    return isInGloballyTerminalState(jobID)
        .thenComposeAsync(isTerminated -> {
            if (isTerminated) {
                // Job 已结束 → 拒绝重复提交
                return FutureUtils.completedExceptionally(
                    DuplicateJobSubmissionException.ofGloballyTerminated(jobID));
            } else if (jobManagerRunnerRegistry.isRegistered(jobID)) {
                // Job 正在运行 → 拒绝重复提交
                return FutureUtils.completedExceptionally(
                    DuplicateJobSubmissionException.of(jobID));
            } else {
                return internalSubmitJob(executionPlan);  // ★ 进入提交流程
            }
        }, getMainThreadExecutor(jobID));
}
```

`internalSubmitJob()` → `persistAndRunJob()` → `runJob(createJobMasterRunner(executionPlan), ...)`:

```java
// Dispatcher.java:1333
private void persistAndRunJob(ExecutionPlan executionPlan) throws Exception {
    executionPlanWriter.putExecutionPlan(executionPlan);  // 持久化到 HA 存储
    initJobClientExpiredTime(executionPlan);
    runJob(
        createJobMasterRunner(executionPlan),   // ★ 创建 JobMasterRunner
        ExecutionType.SUBMISSION,
        executionPlan.getApplicationId().orElse(null));
}
```

### 阶段 3：JobMaster 构建 ExecutionGraph

```
JobMaster.start()
  → SchedulerBase.createAndRestoreExecutionGraph()
    → ExecutionGraphBuilder.buildGraph()
      → 按 parallelism 展开 ExecutionVertex
```

JobGraph 和 ExecutionGraph 的核心区别：
- **JobGraph**：JobVertex 中 `parallelism=4` 是一个 int
- **ExecutionGraph**：JobVertex 展开成 4 个 `ExecutionVertex`，每个有独立的 `Execution` 对象

### 阶段 4-5：Slot 申请 → Task 部署

```
Scheduler → SlotPool → ResourceManager → 分配 Slot
  → ExecutionVertex 获得 SlotOffer
  → TaskDeploymentDescriptor 序列化发送给 TaskExecutor
  → TaskExecutor.submitTask()
  → 创建 Task 对象 + 启动线程
```

### 阶段 6：数据开始流动

```
Task 启动 → InputGate 建立到上游 ResultPartition 的连接
  → Credit-based Flow Control 握手
  → 上游产出 Buffer → 下游消费 Buffer → 触发算子计算
```

---

## 1.5 — 横向对比：Spark / StarRocks / MaxCompute

### vs Spark

Spark 的 DAGScheduler 把 RDD DAG 切分成 ShuffleMapStage 和 ResultStage，Stage 之间是严格的前后依赖——上游 Stage 的所有 task 完成后，下游 Stage 才可以被调度。`Executor` 上跑的 Task 是临时的——跑完即销毁。

**Flink 则不同**：
- Task 长期存活，上下游同时在线
- Stage 概念弱化（存在 Pipelined Region 概念但没有"阶段边界"）
- 调度粒度更细——可以逐个 ExecutionVertex 调度而非等整个 Stage

**本质差异**：Spark 运行时是"分批次的图计算"，Flink 运行时是"持续的数据流网络"。

### vs StarRocks

StarRocks 是 MPP 数据库的架构——Fragment-based Execution：
- FE（Frontend）做 SQL 解析 → Fragment Plan
- BE（Backend）执行 Fragment，Fragment 之间通过 RPC 传递 Chunk
- 所有算子是一次性拉起的，跑完即释放

**Flink 跟 StarRocks 最大的交集在 Table/SQL 层**——Flink SQL batch 模式生成的 ExecutionGraph 拓扑与 StarRocks Fragment Plan 非常相似。

### vs MaxCompute

MaxCompute 是经典的 Staged Scheduler——按 Stage 执行，上游全完成下游才开始。Flink 用 `AdaptiveBatchScheduler`——可以根据上游产出数据量动态决定下游并行度。

---

## 1.6 — 调优与实战陷阱

### 理解入口：看日志识别组件

```
[cluster-io] ... ClusterEntrypoint - Starting StandaloneSessionClusterEntrypoint.
[Dispatcher] ... Dispatcher - Dispatcher with id ... was granted leadership.
[ResourceManager] ... StandaloneResourceManager - ResourceManager ... was granted leadership.
[JobMaster] ... JobMaster - Starting execution of job ... with 4 vertices, parallelism 8
```

### 最常见新手误区：把 Slot 当线程

**Slot ≠ 线程**。Slot 是 TaskManager 上的一个资源单位——一块内存切分。TaskManager 上的 Slot 数跟你可以并行跑多少个 Task 强相关，但同一 Slot 内可以串行跑多个 Task（通过 Operator Chain 合并在一个线程内）。

**Slot ≠ CPU Core**。8 Core 的机器可以设 `taskmanager.numberOfTaskSlots: 16`——只是内存会被切成 16 份，CPU 靠多线程共享。

### Application Mode vs Session Mode vs Per-Job Mode

| Mode | 进程模型 | 适合场景 |
|------|---------|---------|
| **Session** | 一个预先启动的 JM + TM 集群，多个 Job 共享 | SQL Client / 交互式 |
| **Per-Job** | 每个 Job 一套独立的 JM + TM | 资源隔离要求高 |
| **Application** | main() 方法运行在集群上，而不是客户端 | 避免 Client 成为瓶颈 |

### 算子链被意外打断

排查工具：在 Flink Web UI 中查看 JobGraph 的拓扑——如果有超预期的 JobVertex 数量（应该比你的操作符少得多），说明 chain 没按预期合并。

常见原因：在两个 map 之间插了一个 `.keyBy()` 或者加了 `.disableChaining()` → 多一次序列化+网络开销 → 吞吐下降 2-5x。

### 并行度和 Slot 的匹配

ExecutionGraph 的总 task 数 = sum(各 JobVertex 的并行度)。如果所有 SharingGroup 为默认（都共用同一个 group），那么需要的 Slot 数 = max(所有 JobVertex 的并行度)。这个数应 ≤ 集群的总 Slot 数。否则调度会死锁，Web UI 一直显示 `CREATED` 或 `SCHEDULED` 不动。

---

## 本章要点回顾

1. Flink 是**流优先的一体化运行时**，批 = 有限输入的流，不是 Mini-batch 模拟出的流。
2. 进程模型 = Client + JobManager（含 Dispatcher + ResourceManager + JobMaster）+ TaskManager 集群。
3. `ClusterEntrypoint.startCluster()` → `initializeServices()` → `factory.create()` 的启动链路逐步初始化 RPC/HA/Blob/Metrics/Dispatcher/RM。
4. JobMaster 是每作业一个的核心调度者，比 Spark Driver 的 DAGScheduler/TaskScheduler 职权更广。
5. `StreamingJobGraphGenerator.createJobGraph()` 的核心步骤：`setChaining()` → `setSlotSharingAndCoLocation()` → 序列化。
6. `isChainable()` 有 6 条判定：单输入、全局启用、同 SlotSharingGroup、ChainingStrategy 兼容、Forward 分区、无 Union。
7. Slot 是 Flink 资源抽象的核心，表示一段割裂的内存，不等同于线程或 CPU core。

## 源码导航

- 集群启动：`flink-runtime/.../entrypoint/ClusterEntrypoint.java` → `runCluster()` → `initializeServices()`
- 组件工厂：`flink-runtime/.../entrypoint/component/DefaultDispatcherResourceManagerComponentFactory.java` → `create()`
- Dispatcher：`flink-runtime/.../dispatcher/Dispatcher.java` → `submitJob()` → `internalSubmitJob()` → `persistAndRunJob()`
- ResourceManager：`flink-runtime/.../resourcemanager/ResourceManager.java`
- JobMaster：`flink-runtime/.../jobmaster/JobMaster.java`
- TaskExecutor：`flink-runtime/.../taskexecutor/TaskExecutor.java`
- StreamGraph 构建：`flink-runtime/.../streaming/api/graph/StreamGraphGenerator.java`
- JobGraph 构建：`flink-runtime/.../streaming/api/graph/StreamingJobGraphGenerator.java` → `createJobGraph()` → `setChaining()` → `isChainable()`
- ExecutionGraph：`flink-runtime/.../executiongraph/ExecutionGraph.java`
- Task 部署：`flink-runtime/.../scheduler/SchedulerBase.java` → `deployTask()`
