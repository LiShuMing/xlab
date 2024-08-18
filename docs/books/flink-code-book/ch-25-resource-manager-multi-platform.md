# 第 25 章 · 资源管理器的多平台适配

## 导读

- **一句话**：本章回答"Flink 怎么在 YARN、Kubernetes、Standalone 不同底座上用同一套 ResourceManager 逻辑完成 Slot 分配和容器管理"。
- **前置知识**：第 1 章架构、第 7 章 Slot。
- **读完本章你能回答**：
  - ActiveResourceManager 按需申请容器的完整链路
  - YARN/K8s/Standalone 三种实现如何通过同一模板适配
  - TaskManager 注册与 Slot 上报如何将外部容器纳入调度体系

---

## 25.1 — 设计动机

为什么这样设计？Flink 需要在 YARN、Kubernetes、Standalone 三种完全不同的资源底座上运行，但 Slot 分配逻辑是通用的——不管底层是 YARN Container 还是 K8s Pod，JobMaster 请求 Slot 时只关心"有没有可用 Slot"。

**解决的问题**：将"Slot 分配策略"与"容器生命周期管理"解耦。SlotManager 负责前者，平台特定的 ResourceManagerDriver 负责后者。

**放弃的替代方案**：如果让每种平台各自实现完整的 ResourceManager（含 Slot 分配逻辑），则 YarnResourceManager、KubernetesResourceManager、StandaloneResourceManager 之间将大量重复，且 Slot 分配策略的改进需同步修改三处。当前分层设计把变化点隔离在 Driver 层。

```
抽象层：ResourceManager + SlotManager          ← 通用 Slot 分配
  └── ActiveResourceManager                    ← 通用弹性调度逻辑
        └── ResourceManagerDriver（接口）      ← 平台适配点
              ├── YarnResourceManagerDriver    ← YARN AMRMClientAsync
              ├── KubernetesResourceManagerDriver ← K8s Pod Watch
              └── 其他自定义 Driver
独立分支：StandaloneResourceManager            ← 固定资源，不申请容器
```

`ResourceManagerFactory` 通过工厂模式将平台选择延迟到启动阶段——`YarnResourceManagerFactory`、`KubernetesResourceManagerFactory`、`StandaloneResourceManagerFactory` 分别创建对应实现。

源码入口：
- `org.apache.flink.runtime.resourcemanager.ResourceManagerFactory`
- `org.apache.flink.runtime.resourcemanager.active.ActiveResourceManagerFactory`

---

## 25.2 — 核心数据结构

### 25.2.1 ResourceManager 基类核心字段

`ResourceManager<WorkerType>` 维护三张核心注册表和两个心跳管理器：

```java
// <org.apache.flink.runtime.resourcemanager.ResourceManager:L#132>
private final Map<JobID, JobManagerRegistration> jobManagerRegistrations;
// <org.apache.flink.runtime.resourcemanager.ResourceManager:L#141>
private final Map<ResourceID, WorkerRegistration<WorkerType>> taskExecutors;
// <org.apache.flink.runtime.resourcemanager.ResourceManager:L#153>
private final SlotManager slotManager;
// <org.apache.flink.runtime.resourcemanager.ResourceManager:L#166>
private HeartbeatManager<...> taskManagerHeartbeatManager;
// <org.apache.flink.runtime.resourcemanager.ResourceManager:L#169>
private HeartbeatManager<Void, Void> jobManagerHeartbeatManager;
```

**jobManagerRegistrations** 解决 JobMaster 寻址问题；**taskExecutors** 是所有已注册 TaskExecutor 的权威视图，`WorkerRegistration` 封装了 Gateway、InstanceID、硬件描述、内存配置、Slot 资源 Profile；两个 **HeartbeatManager** 分别监控 TaskExecutor 和 JobMaster 存活，超时触发连接清理。SlotManager 不持有 Gateway——它是纯粹的资源簿记器，所有 RPC 由 ResourceManager 代理。

### 25.2.2 ActiveResourceManager 的状态追踪

`ActiveResourceManager` 在基类之上增加 Worker 生命周期追踪：

```java
// <org.apache.flink.runtime.resourcemanager.active.ActiveResourceManager:L#92>
private final Map<ResourceID, WorkerType> workerNodeMap;       // 所有已知 Worker
// <org.apache.flink.runtime.resourcemanager.active.ActiveResourceManager:L#95>
private final WorkerCounter pendingWorkerCounter;              // 已请求未注册
// <org.apache.flink.runtime.resourcemanager.active.ActiveResourceManager:L#98>
private final WorkerCounter totalWorkerCounter;                // pending + registered
// <org.apache.flink.runtime.resourcemanager.active.ActiveResourceManager:L#101>
private final Map<ResourceID, WorkerResourceSpec> workerResourceSpecs;
// <org.apache.flink.runtime.resourcemanager.active.ActiveResourceManager:L#106>
private final Set<ResourceID> currentAttemptUnregisteredWorkers;
// <org.apache.flink.runtime.resourcemanager.active.ActiveResourceManager:L#109>
private final Set<ResourceID> previousAttemptUnregisteredWorkers;
```

为什么需要两个 WorkerCounter？`pendingWorkerCounter` 追踪"已请求但未注册的 Worker"；`totalWorkerCounter` 追踪所有已知 Worker，用于与 SlotManager 声明的需求量做差值。只有一个计数器则无法区分"Worker 在启动中"和"Worker 已可用"。

`currentAttemptUnregisteredWorkers` 与 `previousAttemptUnregisteredWorkers` 解决 RM Failover 后的 Worker 恢复——二者超时策略不同：当前任期的超时后直接释放，前任期恢复的 Worker 有独立的 `previousWorkerRecoverTimeout`。

### 25.2.3 WorkerResourceSpec：从逻辑需求到物理规格

`WorkerResourceSpec` 是 SlotManager 向 RM 声明资源需求的契约：

```java
// <org.apache.flink.runtime.resourcemanager.WorkerResourceSpec:L#47>
private final CPUResource cpuCores;
private final MemorySize taskHeapSize;
private final MemorySize taskOffHeapSize;
private final MemorySize networkMemSize;
private final MemorySize managedMemSize;
private final int numSlots;
private final Map<String, ExternalResource> extendedResources;  // GPU/FPGA
```

转换链：`ResourceProfile`（Slot 维度）→ `WorkerResourceSpec`（Worker 维度）→ `TaskExecutorProcessSpec`（进程参数）→ YARN Resource / K8s Pod Spec（平台格式）。关键转换在 `requestNewWorker`（`<ActiveResourceManager:L#491>`）中调用 `TaskExecutorProcessUtils.processSpecFromWorkerResourceSpec`，再由 Driver 的 `requestResource` 转为平台格式。

### 25.2.4 ResourceManagerFactory 的工厂链

工厂模式分两层：`ResourceManagerFactory` 创建 `ResourceManagerRuntimeServices`（含 SlotManager）；`ActiveResourceManagerFactory` 在基类上创建 `ThresholdMeter`（Worker 启动失败率监控），调用子类的 `createResourceManagerDriver` 生成平台 Driver。`YarnResourceManagerFactory` 和 `KubernetesResourceManagerFactory` 只需实现 `createResourceManagerDriver`，整个 ActiveResourceManager 的弹性调度逻辑对所有平台复用。

---

## 25.3 — 关键流程走读

### 25.3.1 ActiveResourceManager 容器申请完整流程

Flink 弹性调度的主链路：

```
JobMaster 请求 Slot → SlotManager 分配失败
  → FineGrainedSlotManager.declareNeededResourcesWithDelay()
    → resourceAllocator.declareResourceNeeded(resourceDeclarations)
      → ActiveResourceManager.checkResourceDeclarations()
        → requestNewWorker(workerResourceSpec)
          → resourceManagerDriver.requestResource(taskExecutorProcessSpec)
            → [平台：YARN addContainerRequest / K8s createTaskManagerPod]
              → 容器启动 → TaskExecutor 注册 → SlotManager 登记 Slot → 满足请求
```

关键决策点在 `checkResourceDeclarations`（`<ActiveResourceManager:L#327>`）：

```java
for (ResourceDeclaration resourceDeclaration : resourceDeclarations) {
    int releaseOrRequestWorkerNumber =
            totalWorkerCounter.getNum(workerResourceSpec) - declaredWorkerNumber;
    if (releaseOrRequestWorkerNumber > 0) {
        // 释放：先 unwanted → 再未分配 → 再已注册
    } else if (releaseOrRequestWorkerNumber < 0) {
        if (startWorkerCoolDown.isDone()) {
            for (int i = 0; i < requestWorkerNumber; i++) requestNewWorker(workerResourceSpec);
        }
    }
}
```

为什么这样设计？`totalWorkerCounter` 包含 pending + registered，避免启动中重复申请。`startWorkerCoolDown` 是限流机制——失败率超阈值时暂停申请。释放按优先级：先释放 SlotManager 标记 unwanted 的，再释放未分配的，最后才释放已注册的。

### 25.3.2 YarnResourceManagerDriver：AMRMClientAsync 回调流程

YARN 模式通过 Hadoop `AMRMClientAsync` 与 YARN RM 交互，核心是 `AMRMCallbackHandler`。

**申请**（`<YarnResourceManagerDriver:L#266>`）：`requestResource` 将 `TaskExecutorProcessSpec` 转为 YARN `Resource` + `Priority`，调用 `addContainerRequest`，同时加速心跳间隔。同一规格的请求共享 Priority，按 `requestResourceFutures` 队列顺序匹配。

**分配回调**（`<YarnResourceManagerDriver:L#695>`）：`onContainersAllocated` 按 Priority 分组，将 Container 与等待队列一一匹配，完成 Future，然后 `NMClientAsync.startContainerAsync` 启动 TaskExecutor。多分配的 Container 调用 `returnExcessContainer` 归还。

**完成回调**（`<YarnResourceManagerDriver:L#676>`）：`onContainersCompleted` 通知 `ActiveResourceManager.onWorkerTerminated`，清理状态并重新评估需求。

### 25.3.3 KubernetesResourceManagerDriver：Pod Watch 流程

K8s 采用 Watch 机制，与 YARN 有本质差异。

**申请**（`<KubernetesResourceManagerDriver:L#174>`）：`requestResource` 直接创建 Pod（`flinkKubeClient.createTaskManagerPod`），由 K8s Scheduler 负责调度。YARN 先请求再启动；K8s 创建即提交，Pod 名称做 key。

**Watch 回调**（`<KubernetesResourceManagerDriver:L#441>`）：`PodCallbackHandlerImpl` 监听 onAdded/onModified/onDeleted/onError，分发到：
- **Pod 已调度**（`isScheduled`）→ `onPodScheduled`：complete 对应 Future
- **Pod 终止**（`isTerminated` / DELETED）→ `onPodTerminated`：以 `RetryableException` 异常完成，触发重试

为什么 K8s 用 Pod 名称做 key？因为同一 ProcessSpec 可对应多个 Pod，Pod 名称全局唯一，ProcessSpec 不唯一。YARN 用 Priority 分组同规格请求，K8s 用 Pod 名称精确匹配。Watch 断连后自动重建——`KubernetesTooOldResourceVersionException` 触发 `watchTaskManagerPods` 重建 Watch。

### 25.3.4 StandaloneResourceManager 的固定资源模式

`StandaloneResourceManager` 不申请也不释放容器（`<StandaloneResourceManager:L#52>`）：

```java
protected void initialize() { startStartupPeriod(); }
private void startStartupPeriod() {
    setFailUnfulfillableRequest(false);  // 启动期内容忍资源不足
    scheduleRunAsync(() -> setFailUnfulfillableRequest(true), startupPeriodMillis);
}
protected ResourceAllocator getResourceAllocator() {
    return NonSupportedResourceAllocatorImpl.INSTANCE;
}
```

为什么这样设计？Standalone 下 TaskExecutor 由运维脚本启动，RM 无法动态增减。`startupPeriodTime` 解决启动初期问题：TaskExecutor 未全部注册时，若 SlotManager 立即 fail fast，Job 会部署失败。启动期内容忍未满足的请求，等待 TaskExecutor 逐步注册。

### 25.3.5 TaskManager 注册与 Slot 上报

容器启动后 TaskExecutor 必须向 RM 注册——这是将外部容器纳入 Flink 调度的关键一步。

**注册**（`<ResourceManager:L#1043>`）：清理旧注册 → `getWorkerNodeIfAcceptRegistration` 校验 Worker 身份（ActiveRM 通过 `workerNodeMap` 校验；Standalone 全部接受）→ 创建 `WorkerRegistration`，启动心跳监控。

**Slot 上报**两条路径：
1. **初始上报**：注册后调用 `sendSlotReport`（`<ResourceManager:L#509>`），SlotManager 首次登记所有 Slot
2. **心跳上报**：每次心跳 `TaskExecutorHeartbeatPayload` 携带 `SlotReport`，由 `TaskManagerHeartbeatListener.reportPayload` 转发给 `slotManager.reportSlotStatus`（`<ResourceManager:L#1511>`）

对 ActiveResourceManager，注册成功还触发 `onWorkerRegistered`：更新 `workerResourceSpecs`，将 Worker 从 `currentAttemptUnregisteredWorkers` 移入已注册状态，减少 `pendingWorkerCounter`。心跳超时则 `closeTaskManagerConnection` 清理注册 + `internalStopWorker` 通知 Driver 释放容器。

---

## 25.4 — 横向对比（Spark / StarRocks / MaxCompute）

### 25.4.1 vs Spark on YARN：Executor 申请机制

| 维度 | Flink ActiveResourceManager | Spark on YARN |
|------|----------------------------|---------------|
| 资源申请单元 | WorkerResourceSpec → TaskExecutor（含 N Slot） | ExecutorAllocations → Executor（含 N Core） |
| 调度触发 | SlotManager.declareNeededResources → RM → Driver | ExecutorAllocationManager 按 pending task 数量 |
| 反压机制 | startWorkerCoolDown 限流 | maxExecutors 上限 |
| Container 复用 | Session 模式多 Job 共享 | Executor 按 Application 隔离 |

Spark 的 `ExecutorAllocationManager` 以"待调度 Task 数量"驱动，Flink 的 `FineGrainedSlotManager` 以"资源声明"驱动——声明的是"需要几个什么规格的 Worker"，粒度更细（内存各维度 + 外部资源）。Spark 放弃了细粒度内存规格声明——Container 内存由 `spark.executor.memory` 静态配置；Flink 允许不同 Worker 使用不同 WorkerResourceSpec。

### 25.4.2 vs StarRocks BE：手动扩缩容 vs 自动弹性

| 维度 | Flink | StarRocks |
|------|-------|-----------|
| 节点扩缩 | 自动：SlotManager 声明 → Driver 申请 | 手动：ALTER SYSTEM ADD/DECOMMISSION BACKEND |
| 节点下线 | unwanted 标记 → RM 释放 → Driver 停止 | DECOMMISSION 触发 Tablet 迁移后下线 |

StarRocks 选择手动扩缩容因为 BE 承载 Tablet 数据副本，下线必须先完成数据迁移；Flink TaskExecutor 无状态（状态由 Checkpoint 管理），放弃了数据本地性，换来弹性调度简洁性。

### 25.4.3 vs MaxCompute（Fuxi 调度）：Quota 模型 vs Slot 模型

| 维度 | Flink ResourceManager | MaxCompute Fuxi |
|------|----------------------|-----------------|
| 资源模型 | Slot（固定切片，Worker 内分 Slot） | Quota（资源池，按优先级抢占） |
| 调度单位 | Worker（整台申请/释放） | Quota Unit（细粒度到单核单 GB） |
| 多租户 | Session 模式多 Job 共享 Worker | Quota Group 隔离，支持抢占 |

这是"嵌入式调度器"与"集中式调度器"的根本差异：Flink 嵌入 YARN/K8s 复用多租户能力；Fuxi 自建调度器获得抢占式调度的控制权，但放弃通用平台兼容性。

---

## 25.5 — 调优与实战陷阱

### 25.5.1 TaskManager 启动慢导致调度超时

**现象**：Job 长期 INITIALIZING，日志 `Worker xxx did not register in PTxxS, will stop it`。

**根因**：`workerRegistrationTimeout` 短于容器实际启动时间。大型 State 恢复场景 JVM 启动 + ClassLoader + Restore 可能耗时数分钟。

**调优**：增大 `resourcemanager.task-manager-registration-timeout`（默认 5min，大 State 建议 10+ min）。注意与 YARN `yarn.am.expiry-interval-ms` / K8s activeDeadlineSeconds 的交互——RM 侧超时释放容器但平台侧未判定超时，造成容器泄漏。

### 25.5.2 K8s 中 Pod Pending 的常见原因

**排查链**：
1. **资源不足**：`kubectl describe pod` 查看 `Insufficient cpu/memory`
2. **PVC 不可绑**：State PVC 无可用 PV 导致 Pending
3. **镜像拉取慢**：`ImagePullBackOff`，`onPodScheduled` 在调度后即 complete Future，但 TaskExecutor 进程未就绪
4. **节点选择器**：`kubernetes.taskmanager.node-selector` 配置不当

**调优**：设置 `resourcemanager.previous-worker-recovery-timeout` 避免 RM HA 恢复时无限等待旧 Pod。

### 25.5.3 YARN 容器内存超限被杀

**现象**：TaskExecutor 日志中断，YARN UI 显示 Container 被 kill，Exit Code 137/143。

**根因**：YARN Container 物理内存是硬限制。Flink 进程实际使用（含 JVM 元空间、JIT 缓存、堆外 Direct Buffer）超过 Container 限制时 YARN 直接杀容器。

**调优**：YARN Container 内存 > Flink `taskmanager.memory.process.size`，留 10-20% 余量；CentOS/RHEL 上建议 `yarn.nodemanager.vmem-check-enabled=false`（JVM 虚拟内存远大于物理内存，易误杀）；检查 `taskmanager.memory.jvm-overhead.max` 是否覆盖运行时额外开销。

### 25.5.4 Session 模式下多 Job 的资源竞争

**现象**：先提交的大 Job 占满 Slot，后提交的 Job 长期等待；或一个 Job 的 TaskExecutor 失败导致其他 Job 的 Slot 也丢失。

**根因**：Session 模式 SlotManager 统一规划不区分 Job 优先级，大 Job 的 N 个 Worker 需求挤占小 Job。

**调优**：配置 `slotmanager.number-of-slots.min` 保证最小可用资源；K8s 模式可用 Flink Kubernetes Operator 的 Session Job 机制按优先级限额；严重隔离需求应切换 Application 模式——每个 Job 独占 RM 和 TaskExecutor 集群。

---

## 本章要点回顾

1. **分层适配**：ResourceManager + SlotManager 管理通用 Slot 分配，ResourceManagerDriver 隔离平台差异。YARN/K8s/Standalone 各自只实现 Driver。
2. **声明驱动**：FineGrainedSlotManager 通过 `ResourceDeclaration` 声明 Worker 需求，ActiveResourceManager 据此申请或释放。totalWorkerCounter 含 pending + registered，避免重复申请。
3. **YARN vs K8s 差异**：YARN 通过 AMRMClientAsync 回调获取 Container 分配，按 Priority 匹配；K8s 直接创建 Pod 并 Watch 状态变化，以 Pod 名称精确匹配。
4. **Standalone 的妥协**：不申请容器，startupPeriod 容忍启动期资源不足，NonSupportedResourceAllocatorImpl 禁用弹性。
5. **注册是桥梁**：TaskExecutor 注册将外部容器纳入调度——RM 校验身份、创建注册、启动心跳；Slot 上报完成从"容器可用"到"Slot 可分配"的闭环。

## 源码导航

- ResourceManager 基类：`org.apache.flink.runtime.resourcemanager.ResourceManager`
- ActiveResourceManager：`org.apache.flink.runtime.resourcemanager.active.ActiveResourceManager`
- ResourceManagerDriver 接口：`org.apache.flink.runtime.resourcemanager.active.ResourceManagerDriver`
- ResourceEventHandler 回调：`org.apache.flink.runtime.resourcemanager.active.ResourceEventHandler`
- YarnResourceManagerDriver：`org.apache.flink.yarn.YarnResourceManagerDriver`
- KubernetesResourceManagerDriver：`org.apache.flink.kubernetes.KubernetesResourceManagerDriver`
- StandaloneResourceManager：`org.apache.flink.runtime.resourcemanager.StandaloneResourceManager`
- ResourceManagerFactory：`org.apache.flink.runtime.resourcemanager.ResourceManagerFactory`
- ActiveResourceManagerFactory：`org.apache.flink.runtime.resourcemanager.active.ActiveResourceManagerFactory`
- WorkerResourceSpec：`org.apache.flink.runtime.resourcemanager.WorkerResourceSpec`
- ResourceDeclaration：`org.apache.flink.runtime.resourcemanager.slotmanager.ResourceDeclaration`
- WorkerCounter：`org.apache.flink.runtime.resourcemanager.active.WorkerCounter`
- FineGrainedSlotManager：`org.apache.flink.runtime.resourcemanager.slotmanager.FineGrainedSlotManager`
- External Resource 框架：`org.apache.flink.runtime.externalresource`
