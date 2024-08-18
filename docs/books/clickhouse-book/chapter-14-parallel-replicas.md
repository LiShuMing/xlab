# Chapter 14: Parallel Replicas — 动态 Mark Range 分发的无状态计算层

## 14.1 问题：单分片单线程的瓶颈

在 ClickHouse 的传统模型中，一个分片的数据只能被一个副本读取。即使有 3 个副本，查询也只用其中一个。这意味着：
- 单分片查询无法利用多副本的 CPU 资源
- 大查询受限于单个节点的 I/O 带宽
- 无法动态扩缩容

## 14.2 协议设计：请求/响应模型

`src/Storages/MergeTree/RequestResponse.h` — Parallel Replicas 使用一个简洁的二进制协议在 Coordinator 和 Replica 之间通信。

### CoordinationMode

```cpp
enum class CoordinationMode : uint8_t
{
    Default = 0,       // 均匀分配 Mark Range
    WithOrder = 1,     // 按主键顺序分配
    ReverseOrder = 2,  // 按主键逆序分配
};
```

### InitialAllRangesAnnouncement — 副本初始化声明

```cpp
struct InitialAllRangesAnnouncement
{
    CoordinationMode mode;                   // 协调模式
    RangesInDataPartsDescription description; // 该副本持有的 Part + Mark Range
    size_t replica_num;                      // 副本编号
    size_t mark_segment_size;                // Mark 段大小
    size_t min_marks_per_request;            // 每次请求最少分配的 Mark 数
};
```

副本启动时向 Coordinator 发送此消息，声明自己持有哪些 Part 的哪些 Mark Range。

### ParallelReadRequest — 读取请求

```cpp
struct ParallelReadRequest
{
    CoordinationMode mode;
    size_t replica_num;                      // 请求者编号
    size_t min_marks_per_request;            // 期望的最少 Mark 数
    RangesInDataPartsDescription description; // InOrder 模式下的 Part 描述
};
```

### ParallelReadResponse — 读取响应

```cpp
struct ParallelReadResponse
{
    bool finish{false};                       // 是否所有 Mark 已分配完毕
    RangesInDataPartsDescription description; // 分配给该副本的 Mark Range
};
```

## 14.3 ParallelReplicasReadingCoordinator — 协调器

`src/Storages/MergeTree/ParallelReplicasReadingCoordinator.h` — 协调器持有全局 Mark Range 视图：

```cpp
class ParallelReplicasReadingCoordinator
{
public:
    // 1. 接收副本的初始化声明
    void handleInitialAllRangesAnnouncement(InitialAllRangesAnnouncement announcement);

    // 2. 处理副本的读取请求 → 分配 Mark Range
    ParallelReadResponse handleRequest(ParallelReadRequest request);

    // 3. 标记副本不可用（宕机、超时）
    void markReplicaAsUnavailable(size_t replica_number);

    // 4. 设置进度回调
    void setProgressCallback(ProgressCallback callback);

    // 5. 设置读取完成回调
    void setReadCompletedCallback(ReadCompletedCallback callback);

private:
    void initialize(CoordinationMode mode);
    bool isReadingCompleted() const;

    std::mutex mutex;                              // 保护状态
    const size_t replicas_count;                   // 副本数
    std::unique_ptr<ImplInterface> pimpl;          // 策略实现
    ProgressCallback progress_callback;
    std::set<size_t> replicas_used;                // 已使用的副本
    std::optional<size_t> snapshot_replica_num;    // 快照副本编号
    std::atomic_bool is_reading_completed{false};

    // 不可用副本列表（可能在初始化前就收到）
    std::vector<size_t> unavailable_nodes_registered_before_initialization;
};
```

### Pimpl 模式：策略实现

```cpp
// Coordinator 的实际分配逻辑通过 ImplInterface 实现
class ParallelReplicasReadingCoordinator::ImplInterface
{
public:
    virtual ~ImplInterface() = default;
    virtual ParallelReadResponse handleRequest(ParallelReadRequest request) = 0;
};
```

这允许根据 `CoordinationMode` 选择不同的分配策略。

## 14.4 工作流程

### 完整的 Parallel Replicas 查询生命周期

```
阶段 1: 初始化
  Coordinator 创建 ParallelReplicasReadingCoordinator
  │
  ├── Replica 1 发送 InitialAllRangesAnnouncement
  │     → Coordinator 记录 Replica 1 持有的 Part 和 Mark Range
  │
  ├── Replica 2 发送 InitialAllRangesAnnouncement
  │     → Coordinator 记录 Replica 2 持有的 Part 和 Mark Range
  │
  └── Replica 3 发送 InitialAllRangesAnnouncement
        → Coordinator 记录 Replica 3 持有的 Part 和 Mark Range
        → Coordinator 合并所有副本的 Mark Range 视图
        → Coordinator 初始化分配策略（Pimpl）

阶段 2: 执行
  每个 Replica 的 MergeTreeReadPoolParallelReplicas:
  │
  while (有更多 Mark 要读):
  │     ├── 向 Coordinator 发送 ParallelReadRequest
  │     ├── 收到 ParallelReadResponse
  │     │     └── description = 分配到的 Mark Range
  │     ├── 读取分配到的 Mark Range（从本地 Part 或 S3）
  │     └── 发送结果 Block 到 Coordinator
  │
  └── Coordinator 收到 finish=true → 该副本读取完成

阶段 3: 完成
  ├── 所有副本完成读取
  ├── is_reading_completed = true
  └── 触发 read_completed_callback
        → 通知所有使用了哪些副本
```

### Default 模式：均匀分配

```
Part A 有 30 个 Mark Range:

初始分配:
  Replica 1: Mark 0-9
  Replica 2: Mark 10-19
  Replica 3: Mark 20-29

动态调整:
  如果 Replica 2 先完成 Mark 10-19:
    → Replica 2 请求更多任务
    → Coordinator 从 Replica 1 的未读 Mark 中分割一部分给 Replica 2
    → Replica 2: Mark 8-12（从 Replica 1 的范围中偷取）

这保证了快副本不会空闲，慢副本不成为瓶颈。
```

### WithOrder 模式：按序分配

`MergeTreeReadPoolParallelReplicasInOrder.h` — 当 ORDER BY 与主键一致时：

```
保证: Mark Range 按主键顺序分配
  Round 1:
    Replica 1: Mark 0-2     (最小主键)
    Replica 2: Mark 10-12
    Replica 3: Mark 20-22
  Round 2:
    Replica 1: Mark 3-5
    Replica 2: Mark 13-15
    Replica 3: Mark 23-25
  ...

结果: 每个 Replica 的输出按主键有序
      Coordinator 只需做归并排序（k-way merge）
      不需要完整的 SortStep
```

### ReverseOrder 模式

与 WithOrder 相同，但分配从最大主键开始，适用于 `ORDER BY ... DESC`。

## 14.5 MergeTreeReadPoolParallelReplicas

`src/Storages/MergeTree/MergeTreeReadPoolParallelReplicas.h` — 副本侧的读取池：

```cpp
class MergeTreeReadPoolParallelReplicas : public IMergeTreeReadPool
{
    // 核心方法
    MergeTreeReadTaskPtr getTask() override
    {
        // 1. 向 Coordinator 请求 Mark Range
        auto response = callback(request);

        if (response.finish)
            return nullptr;  // 所有 Mark 已分配完毕

        // 2. 构建 ReadTask
        return std::make_shared<MergeTreeReadTask>(
            response.description,  // Part + Mark Range
            ...);
    }

    void profileFeedback(const ReadProgressInfo & info) override
    {
        // 报告读取进度
        // Coordinator 可根据进度调整分配策略
    }

private:
    MergeTreeReadTaskCallback callback;  // → Coordinator 的 handleRequest
    size_t replica_num;
    size_t min_marks_per_request;
};
```

## 14.6 容错与恢复

### 副本不可用处理

```cpp
void ParallelReplicasReadingCoordinator::markReplicaAsUnavailable(size_t replica_number)
{
    // 1. 将该副本从活跃列表中移除
    // 2. 重新分配该副本未完成的 Mark Range
    // 3. 通知其他副本可以请求更多任务
}
```

**场景**：Replica 2 在读取 Mark 10-15 时宕机：
1. Coordinator 检测到超时或连接断开
2. `markReplicaAsUnavailable(2)` 被调用
3. Mark 13-15（未完成部分）重新放入全局池
4. Replica 1 或 3 在下次请求时可能获得这些 Mark

### 快照副本

```cpp
std::optional<size_t> snapshot_replica_num;
```

Coordinator 将第一个发送 `InitialAllRangesAnnouncement` 的副本视为"快照副本"——它持有完整的 Part 元数据视图。其他副本可能只持有部分 Part。Coordinator 在分配任务时优先考虑快照副本的 Part 视图。

## 14.7 与存算分离的关系

Parallel Replicas 是存算分离的**计算层基础**：

```
传统模式:
  Data (本地磁盘) → 单个 Replica → 查询

Parallel Replicas:
  Data (S3 共享存储) → 多个无状态计算节点 → Coordinator 聚合

关键差异:
  传统: 数据和计算绑定在同一节点
  新模式: 数据在 S3，计算节点无状态，可动态扩缩
```

**从 Parallel Replicas 到 SharedMergeTree 的演进路径**：

```
阶段 1: Parallel Replicas（当前）
  → 多副本并行读取同一分片
  → 数据仍在各副本的本地磁盘
  → Coordinator 持有全局 Mark Range 视图

阶段 2: Parallel Replicas + S3
  → 数据在 S3，本地只有 FileCache
  → 计算节点无状态，可动态扩缩
  → 类似 ClickHouse Cloud 的架构

阶段 3: SharedMergeTree（未来）
  → 数据完全在 S3
  → 元数据在共享存储（Keeper / S3）
  → 计算节点完全无状态
  → 任意计算节点可以读取任意 Part
```

## 14.8 设置参数

| 设置 | 默认值 | 说明 |
|------|--------|------|
| `parallel_replicas_count` | 0 (auto) | 并行副本数 |
| `parallel_replicas_min_count_for_single_replica` | 0 | 触发并行的最小 Mark 数 |
| `allow_parallel_replicas` | 1 | 启用/禁用 |
| `max_parallel_replicas` | 0 (unlimited) | 最大并行副本数 |
| `parallel_replicas_custom_cluster` | "" | 自定义集群名 |
| `parallel_replicas_for_non_replicated_merge_tree` | 0 | 非复制表也使用并行读取 |

## 14.9 本章小结

```
Parallel Replicas 协议:
  InitialAllRangesAnnouncement → 副本声明持有的 Mark Range
  ParallelReadRequest → 副本请求更多任务
  ParallelReadResponse → Coordinator 分配 Mark Range

协调模式:
  Default → 均匀分配 + 动态偷取
  WithOrder → 按主键顺序分配（归并排序优化）
  ReverseOrder → 按主键逆序分配

容错:
  副本不可用 → Mark Range 重新分配
  快照副本 → 持有完整 Part 元数据

核心价值:
  单分片查询利用多副本 CPU + I/O 带宽
  为存算分离提供计算层基础
  支持动态扩缩容
```

**关键文件地图**：
```
src/Storages/MergeTree/ParallelReplicasReadingCoordinator.h     → 协调器
src/Storages/MergeTree/RequestResponse.h                       → 协议定义
src/Storages/MergeTree/MergeTreeReadPoolParallelReplicas.h     → 副本读取池
src/Storages/MergeTree/MergeTreeReadPoolParallelReplicasInOrder.h → 有序读取池
```
