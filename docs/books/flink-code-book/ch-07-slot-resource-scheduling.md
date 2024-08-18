# 第 7 章 · Slot 管理与资源调度

## 导读

- **一句话**：本章回答"Slot 到底是什么？Slot 怎么在 JobMaster 和 ResourceManager 之间分配的资源？Slot Sharing Group 又是什么？"
- **前置知识**：第 1 章进程模型、第 6 章调度策略。
- **读完本章你能回答**：
  - Slot = 什么？为什么它既不是线程也不是进程而是一个"共享资源的名额"？
  - SlotPool（JM 端）和 SlotManager（RM 端）的分工是怎样的
  - Slot Sharing Group 允许为算子有不同 ResourceProfile 是什么意思
  - 资源配置要求的匹配算法是怎么工作的

---

## 7.1 — 设计动机：Slot 是"内存配额"，不是执行线程

### 第一性原理

如果你从零设计一个分布式计算框架，你会有两种资源要管理：
1. **CPU 时间**——执行线程的基本需要
2. **内存空间**——数据驻留的基本需要

Flink 选择让 Slot 管理内存，CPU 靠线程池竞争。这是 FLink 跟 Spark 不同的最优决策：
- Spark 让 Executor 管理**线程数**（spark.executor.cores）——每个 core 同时跑一个 task
- Flink 让 Slot 管理**内存割裂**——每个 Slot 有固定内存份额，同一个 Slot 内可以有很多 Task（通过 operator chain 串在一个线程上），也可 Task 间共用内存

### Slot 的正式定义

> **Slot = TaskManager 上对"计算资源"的预先分配。一个 Slot 保证有 TaskManager 总内存的 1/N (N=Slot数) 可用**。

源码入口：`org.apache.flink.runtime.jobmaster.slotpool.PhysicalSlot`

TaskManager 中的内存划分：
```
TaskManager with 2 Slots:
┌────────────────────────────────────────┐
│  Slot-0                   Slot-1       │
│  ├ Network Buffer:  128MB ┊ 128MB     │
│  ├ Managed Memory:   128MB ┊ 128MB    │
│  └ Task Heap:        256MB ┊ 256MB    │
│                                        │
│  Shared: Framework Heap (256MB)        │
└────────────────────────────────────────┘
```

---

## 7.2 — SlotPool：JM 端的 Slot "缓冲池"

### 为什么 JM 需要一个 Slot Pool

JobMaster 是作业视角。当它想部署一个 Task 时，它需要的是 "找出一个空闲的 Slot"。如果每次都去问 ResourceManager，会引入大量 RPC 延迟。SlotPool 在 JM 端持有**已申请但尚未分配给 Task 的 Slot**——像一个"缓存层"。

```
JobMaster
  └── SlotPool
      ├── 已获得的 Slot（从 RM 获得的空闲 Slot）
      ├── 挂起的 Slot 请求（等待 RM 的响应）
      └── providePhysicalSlot() → 分配此 Slot 给具体 Execution
```

### SlotPool 接口源码

`SlotPool` 是 JM 端的 Slot 管理接口（`flink-runtime/.../jobmaster/slotpool/SlotPool.java:39`）：

```java
public interface SlotPool extends AllocatedSlotActions, AutoCloseable {
    // 生命周期
    void start(JobMasterId jobMasterId, String newJobManagerAddress);
    void close();

    // RM 连接
    void connectToResourceManager(ResourceManagerGateway resourceManagerGateway);
    void disconnectResourceManager();

    // TM 注册
    boolean registerTaskManager(ResourceID resourceID);
    boolean releaseTaskManager(ResourceID resourceId, Exception cause);

    // Slot 接收（TM 向 JM offer slot）
    Collection<SlotOffer> offerSlots(
            TaskManagerLocation taskManagerLocation,
            TaskManagerGateway taskManagerGateway,
            Collection<SlotOffer> offers);

    // Slot 分配
    Optional<PhysicalSlot> allocateAvailableSlot(
            AllocationID allocationID, PhysicalSlotRequest physicalSlotRequest);
    CompletableFuture<PhysicalSlot> requestNewAllocatedSlot(
            PhysicalSlotRequest physicalSlotRequest, Duration timeout);
    CompletableFuture<PhysicalSlot> requestNewAllocatedBatchSlot(
            PhysicalSlotRequest physicalSlotRequest);
}
```

**两种 Slot 请求模式**：
1. `allocateAvailableSlot()`：从已缓存的空闲 Slot 中分配——零延迟
2. `requestNewAllocatedSlot()`：向 RM 申请新 Slot——需要等待 RPC + TM 启动

**Batch Slot 的特殊处理**：`requestNewAllocatedBatchSlot()` 创建的请求不会因为 RM 失败信号而超时——批处理允许更长的等待时间。

### Slot Offer 的接收

```
TM 启动 → 向 RM 注册 → RM 分配 Slot 给 JM → TM offerSlots() 给 JM
→ SlotPool.offerSlots() 接受或拒绝 offer
→ 接受的 offer 变成 AllocatedSlot 进入池中
→ 检查 PendingRequest 是否有匹配的
```

源码入口：`flink-runtime/.../jobmaster/slotpool/PhysicalSlotProvider.java`

### Pending Request 和 Redundancy

SlotPool 维护一个水线：如果有超过某个阈值还未满足的请求，考虑申请更多 Slot（冗余）。这避免了"忙时一直都等 RM 响应"的延迟。

---

## 7.3 — SlotManager：RM 端的资源全局视图

ResourceManager 装着所有 TaskManager 的 Slot 可用状态。SlotManager 对全局的 Slot 资源进行状态管理。

```
ResourceManager
  └── SlotManager
      ├── TaskManagerStatus: 每个 TM 有多少空闲 Slot
      ├── 分配 Slot 请求给特定 TaskManager
      ├── 监控 Slot 使用量
      └── 触发容器回收/再分配
```

源码入口：`flink-runtime/.../resourcemanager/slotmanager/`

---

## 7.4 — Slot Sharing Group：一个 Slot 内跑多个算子的哲学

### 设想去掉 Slot Sharing Group 会怎样

如果你不设置 `SlotSharingGroup`，Flink 会尝试为每个独立的 JobVertex 分配独立的 Slot——意味着一个大 Job（50个 JobVertex, parallelism=32）需要 1600 个 Slot。这是不可用的。

**Slot Sharing Group** 让你将相关算子放在同一个 Slot 中——它们共用内存割裂，在一个 JVM 线程内 pipeline 起来（通过 Operator Chain，第 9 章）。

```java
.map(...).slotSharingGroup("group-a")
.keyBy(...).map(...).slotSharingGroup("group-b")
```

### 同组内如何共享

同一 SharingGroup 内的所有算子：
- 在同一个 JVM 进程中跑
- 可能被 chain （是同一个线程内串行执行）
- 也一样被分配不同线程（如果条件不允许 chain）但都在同一个 Slot 的进程中

---

## 7.5 — ResourceProfile：Slot 不仅仅是内存

每个 ExecutionVertex 携带一个 `ResourceProfile` 描述它的需求：

```java
public class ResourceProfile {
    // CPU 核心数
    // 堆内存大小
    // 直接内存大小
    // 外扩资源（GPU）
    // 额外资源（如 FPGA）
}
```

### Requirement Matcher

当 SlotPool 有多个可用 Slot 时，用 `RequirementMatcher` 决定哪个 Slot 最适合这个 Vertex：

```java
public interface RequirementMatcher {
    PhysicalSlot match(ResourceProfile requirement, Collection<PhysicalSlot> availableSlots);
}
```

源码入口：`flink-runtime/.../slots/DefaultRequirementMatcher.java`

---

## 7.6 — 完整 Slot 分配流程图解

```
Scheduler: "我要部署 ExecutionVertex-X"
  → SlotPool.providePhysicalSlot(ResourceProfile)
  → SlotPool 查本地是否有可用 Slot
  → 有 → 直接返回 PhysicalSlot
  → 没有 → 向 SlotPool 创建一个 PendingRequest
  → 等待 RM 分配 Slot

RM.SlotManager 接收到请求:
  → 扫描所有 TM 的空闲 Slot
  → 无空闲 → 尝试申请新的 TM (容器平台)
  → 有空闲 → 分配 Slot 给目标 JM
  → RM.allocateSlot → 发送 slot offer 给 TM

TM 收到 slot offer:
  → 创建 Slot 对象，分配内存
  → 通知 JM (JobMaster) slot 已就绪

JM 收到 slot:
  → SlotPool 把 slot 放入可用列表
  → 检查 PendingRequest
  → 对应 request 被满足
  → Task 被部署到这个 Slot
```

---

## 7.7 — 横向对比

### vs Spark Executor Core

Spark 的 `--executor-cores` 的粒度是 Task 数。一个 task 一个线程、并发上限等于 cores。没有"Slot"的概念——内存在 Executor 进程中靠堆空间灵活分配。

### vs StarRocks BE

StarRocks BE 节点没有 Slot 概念——收到 Fragment 后直接用 Pipeline 并发限制 (`pipeline_dop`)。这是 MPP 架构的天然特征——算子复制统一管理而非通过内存配额。

---

## 调优与实战陷阱

### Slot 不均衡导致的调度延迟

如果一个 Job 中某些算子用了大分量资源和另的轻算子放同一 SharingGroup → 大分量的 Slot 数不充分 → light 算子占满 Slot → heavy 算子无法部署。

解法：**创建两个 SlotSharingGroup**——heavy 自己一个组配多个 Slot，light 另一个组配少 Slot。

### ResourceProfile 配置在对 GPU 的独占

`resource.setResource(ExternalResource.forGPU(0.5))` 表示需要半 GPU 核。如果 TM 上有零的应用 GPU 资源，该 Slot 可能占不满——注意平台中的 GPU 抽象跟 Flink 的 Slot 抽象是资源约束的补充。

### Adaptive Scheduler 如何影响 Slot 需求

Adaptive Scheduler 可以随需改变并行度——等同于可以在运行中改变 Slot 需求。这需要在外部平台中（K8s）支持动态扩展 TM 数目或外部 Autoscaler。

---

## 本章要点回顾

1. Slot = 内存配额的分片，不是执行线程——CPU 竞争在 Slot 内部线程之间进行。
2. SlotPool 是 JM 端的 Slot 缓存——避免每次部署都全程往返 RM。
3. SlotManager 是 RM 端的全局 Slot 视图和管理逻辑——按需分配、回收、触发容器扩缩。
4. Slot Sharing Group 实现多算子资源共置——降低总 Slot 需求、减少跨进程数据传输。
5. ResourceProfile + RequirementMatcher 使 Slot 分配不仅基于内存还基于其他资源类型。

## 源码导航

- PhysicalSlot 定义：`flink-runtime/.../jobmaster/slotpool/PhysicalSlot.java`
- PhysicalSlotProvider：`flink-runtime/.../jobmaster/slotpool/PhysicalSlotProvider.java`
- SlotManager：`flink-runtime/.../resourcemanager/slotmanager/`
- ResourceProfile：`flink-runtime/.../slots/ResourceProfile.java`
- RequirementMatcher：`flink-runtime/.../slots/RequirementMatcher.java`
- ResourceRequirement：`flink-runtime/.../slots/ResourceRequirement.java`
