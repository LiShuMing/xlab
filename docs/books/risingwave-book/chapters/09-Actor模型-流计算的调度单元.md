# 第 9 章 · Actor 模型——流计算的调度单元

> **核心源码**：
> - `src/stream/src/executor/actor.rs` — Actor、ActorContext、Actor::run 主循环（337 行）
> - `src/stream/src/task/mod.rs` — 流任务管理架构文档，`LocalStreamManager`、event 类型定义
> - `src/stream/src/task/barrier_manager/mod.rs` — `LocalBarrierManager`、`LocalBarrierEvent`（267 行）
> - `src/stream/src/task/barrier_worker/mod.rs` — `LocalBarrierWorker`、`ControlStreamHandle`、Barrier 完成上报
> - `src/stream/src/task/barrier_worker/managed_state.rs` — Barrier 状态机、`PartialGraphState`、`InflightActorState`（1527 行）
> - `src/stream/src/task/actor_manager.rs` — `StreamActorManager`、`spawn_actor`、`create_actor`（626 行）
> **关键数据结构**：`Actor<C>`、`ActorContext`、`LocalBarrierManager`、`PartialGraphStatus`、`ManagedBarrierStateInner`

---

## 9.1 Actor 是什么

在前两章中，我们从 SQL 文本一路走到 Fragment Graph，又深入了 Message/Barrier 的核心抽象。现在要把这两条线交织起来：**Fragment Graph 上的节点（算子拓扑）如何变成运行时执行的实体？**

答案就是 Actor。

```
                    Fragment 2 (Singleton)
                    ┌────────────────────────┐
                    │  StreamMaterialize     │
                    │  StreamHashAgg         │
                    │  Merge (← Exchange)    │
                    └────────────────────────┘
                              ↑
                    ┌─────────┴──────────┐
                    │                    │
              Actor A4              Actor A5    ← 两个 Actor = Fragment 的并行实例
```

在 RisingWave 中，**Actor 是流计算的最小调度和容错单元**。从数据结构上看（`actor.rs:177-186`）：

```rust
pub struct Actor<C> {
    consumer: C,                           // StreamConsumer，输出 Barrier 的末端
    subtasks: Vec<SubtaskHandle>,          // 附属异步任务（Source 读取等）
    pub actor_context: ActorContextRef,    // Actor 的运行时上下文
    expr_context: ExprContext,             // 表达式计算上下文
    barrier_manager: LocalBarrierManager,  // 屏障事件上报
}
```

一个 Actor 内部包含了一条完整的 **Executor 链（DAG）**——从 Source/Chain 到 Dispatch 的所有算子。它不是单个算子，而是一段算子拓扑的容器。

> **第一性原理思考**：为什么需要 Actor 这一层抽象？Executor 已经能处理消息了，为什么不让每个 Executor 独立运行？答案在于**调度粒度**。如果每个 Executor 都是独立的 Tokio Task，那么 100 个 Executor（每个 Actor 平均 10 个 Executor × 10 个 Actor）就意味着 100 个独立的异步任务竞争调度器。Actor 将同一 Fragment 内的 Executor 链合并到一个 Tokio Task 中运行——数据在内存中传递，不需要跨 Task 的通道开销。这既是性能优化（减少调度和序列化），也是复杂度管理（Barrier 只需在 Actor 层面收集）。

---

## 9.2 ActorContext——Actor 的"出生证明"

`ActorContext`（`actor.rs:49-77`）在 Actor 创建时生成，包含 Actor 一生中不变的基础信息：

```rust
pub struct ActorContext {
    pub id: ActorId,                                          // 全局唯一 Actor ID
    pub fragment_id: FragmentId,                              // 所属 Fragment
    pub vnode_count: usize,                                   // 持有多少个 vnode
    pub mview_definition: String,                             // 关联的 MV 定义（调试用）
    pub streaming_metrics: Arc<StreamingMetrics>,             // 指标收集
    pub initial_dispatch_num: usize,                          // 启动时的下游数量
    pub initial_subscriber_ids: HashSet<SubscriberId>,        // 初始订阅者
    pub initial_upstream_actors: HashMap<FragmentId, UpstreamActors>, // 上游拓扑
    pub meta_client: Option<MetaClient>,                      // Meta 客户端（Schema Change）
    pub config: Arc<StreamingConfig>,                         // Actor 级配置覆盖
    pub stream_env: StreamEnvironment,                        // 全局运行环境
}
```

每个字段都有明确的用途：

- **`vnode_count`**：决定了这个 Actor 负责的数据范围。在 `ActorContext::create` 中（`actor.rs:110-142`），vnode_count 从 `vnode_bitmap` 的 len 计算得来。如果 bitmap 未设置（`None`），则 `vnode_count = 1`，表示这是一个 Singleton Actor。
- **`initial_dispatch_num`**：Actor 的下游分发器数量。如果为 0，说明这是个"孤立 Actor"——没有下游，可以启用特殊优化（如 Source 暂停、Materialize 跳过冲突检测）。
- **`initial_upstream_actors`**：记录了从 Fragment Upstreams 映射来的上游信息，Merge 算子用它建立到上游 Actor 的连接。
- **`config`**：Actor 级别的配置覆盖。通过 `StreamActorManager::get_overridden_config`（`actor_manager.rs:392-419`）解析 job 级别的 `config_override` 字段，与全局 config 合并后生成。这使得同一个 Compute Node 上的不同 Actor 可以有不同的 chunk_size、checkpoint_interval 等参数。

`ActorContext::for_test_with_config`（`actor.rs:86-107`）提供了测试用的 context 构造，其中 `vnode_count = VirtualNode::COUNT_FOR_TEST`。测试代码能独立运行不依赖真实的 vnode 分配。

---

## 9.3 LocalBarrierManager——Actor 到系统的桥梁

`LocalBarrierManager`（`barrier_manager/mod.rs:93-98`）是 Actor 与 Compute Node 的事件系统之间的唯一通信通道：

```rust
pub struct LocalBarrierManager {
    barrier_event_sender: UnboundedSender<LocalBarrierEvent>,
    actor_failure_sender: UnboundedSender<(ActorId, StreamError)>,
    pub(crate) term_id: String,
    pub(crate) env: StreamEnvironment,
}
```

两个 channel 分别承担两种职责：
- **`barrier_event_sender`**：发送 Barrier 相关的生命周期事件
- **`actor_failure_sender`**：发送 Actor 错误（崩溃通知）

`LocalBarrierEvent` 枚举定义（`barrier_manager/mod.rs:38-87`）覆盖了 Actor 需要向系统汇报的所有事件：

| 事件 | 发送时机 | 处理者 |
|------|---------|-------|
| `ReportActorCollected` | Actor 收到一个 Barrier 时 | `PartialGraphState::collect` |
| `ReportCreateProgress` | Backfill 进度更新时 | Barrier 完成上报 |
| `RegisterBarrierSender` | Actor 启动时注册 Barrier 通道 | `InflightActorState::register_barrier_sender` |
| `RegisterLocalUpstreamOutput` | 同节点 Actor 间建立本地通道 | 本地通道注册 |
| `ReportSourceListFinished` | Source 数据列举完成 | Refresh 流程 |
| `ReportSourceLoadFinished` | Source 数据加载完成 | Refresh 流程 |
| `RefreshFinished` | MV Refresh 完成 | 通知 Meta |
| `ReportCdcTableBackfillProgress` | CDC Backfill 进度 | CDC 同步进度上报 |
| `ReportCdcSourceOffsetUpdated` | CDC Source Offset 更新 | 告知 Meta |

关键方法 `collect`（`barrier_manager/mod.rs:135-140`）：

```rust
pub fn collect<M>(&self, actor_id: ActorId, barrier: &BarrierInner<M>) {
    self.send_event(LocalBarrierEvent::ReportActorCollected {
        actor_id,
        epoch: barrier.epoch,
    })
}
```

这里 `send_event` 使用的是 `let _ = self.barrier_event_sender.send(event)`——发送失败不报错，只是静默丢弃。原因是：当 Actor 被 Stop Mutation 终止后，`LocalBarrierManager` 可能已经是 stale 的，下游的 `PartialGraphState` 可能已经被清理。用 `unbounded_channel` + 静默丢弃，避免了 Actor 退出时的时序问题。

---

## 9.4 Actor 的创建——从 protobuf 到运行

### 9.4.1 创建入口

Actor 的创建由 Meta 的 `InjectBarrierRequest` 触发。Meta 在 Barrier 中携带 `actors_to_build` 字段，Compute Node 收到后调用 `StreamActorManager::spawn_actor`（`actor_manager.rs:472-564`）：

```rust
pub(super) fn spawn_actor(
    self: &Arc<Self>,
    actor: BuildActorInfo,              // Proto 定义的 Actor 构建信息
    fragment_id: FragmentId,
    node: Arc<StreamNode>,              // 物理计划子树（Proto）
    local_barrier_manager: LocalBarrierManager,
    new_output_request_rx: UnboundedReceiver<(ActorId, NewOutputRequest)>,
) -> (JoinHandle<()>, Option<JoinHandle<()>>) {
```

spawn_actor 返回两个 handle：
- **`JoinHandle<()>`**：Actor 主任务的 handle，用于 abort 和 join
- **`Option<JoinHandle<()>>`**：可选的 `tokio_metrics::TaskMonitor` handle，用于收集 Actor 的 poll/idle/scheduled 时间

### 9.4.2 异步创建链

`create_actor`（`actor_manager.rs:421-470`）是异步构造函数：

```
create_actor:
  ① ActorContext::create(build_actor_info, ...)
       → 从 Proto 填充 ActorContext 的所有字段
  ② create_nodes(fragment_id, stream_node, ...)
       → 递归构造 Executor 树
       → StreamNode(Proto) → (Executor, SubtaskHandle[])
  ③ DispatchExecutor::new(executor, dispatchers, ...)
       → 在 Executor 链末端包装分发器
  ④ Actor::new(dispatcher, subtasks, context, ...)
       → 组装 Actor 结构体
```

`create_nodes_inner`（`actor_manager.rs:206-288`）是 Executor 树的构造核心。它递归遍历 `StreamNode` 的 `input` 子节点，自底向上构建：

```rust
async fn create_nodes_inner(
    &self, fragment_id, node, env, store, actor_context,
    vnode_bitmap, has_stateful, subtasks, local_barrier_manager,
) -> StreamResult<Executor> {
    // 先递归构建子输入
    for input_stream_node in &node.input {
        input.push(self.create_nodes_inner(..., input_stream_node, ...).await?);
    }
    // 再根据当前节点类型生成 Executor
    self.generate_executor_from_inputs(fragment_id, node, env, store,
        actor_context, vnode_bitmap, local_barrier_manager, input).await?
}
```

特殊处理 `StreamScan`（SnapshotBackfill）：当 `StreamScanType::SnapshotBackfill` 时，跳过标准的递归构建，走 `create_snapshot_backfill_node`（`actor_manager.rs:111-200`），直接构建 `BatchTable` + `StateTable` + `SnapshotBackfillExecutor` 组合。

### 9.4.3 ExecutorParams——统一的构造参数

`ExecutorParams`（`actor_manager.rs:570-613`）是所有 Executor 构造函数的统一参数容器：

```rust
pub struct ExecutorParams {
    pub env: StreamEnvironment,
    pub info: ExecutorInfo,
    pub executor_id: ExecutorId,
    pub operator_id: GlobalOperatorId,
    pub op_info: String,
    pub input: Vec<Executor>,
    pub fragment_id: FragmentId,
    pub executor_stats: Arc<StreamingMetrics>,
    pub actor_context: ActorContextRef,
    pub vnode_bitmap: Option<Bitmap>,
    pub eval_error_report: ActorEvalErrorReport,
    pub watermark_epoch: AtomicU64Ref,
    pub local_barrier_manager: LocalBarrierManager,
    pub config: Arc<StreamingConfig>,
}
```

这个 struct 的存在揭示了一个重要设计：**Executors 通过统一的参数构造，而不是每个 Executor 自己分散获取上下文**。这使得添加新 Executor 类型的接口保持稳定——只是把 `ExecutorParams` 传进去，具体 Executor 自己取需要的字段。

---

## 9.5 Actor 的运行循环

### 9.5.1 Actor::run——生命周期的驾驶舱

`Actor::run`（`actor.rs:210-233`）是 Actor 生命周期的入口：

```rust
pub async fn run(mut self) -> StreamResult<()> {
    let run = async move {
        tokio::join!(
            join_all(std::mem::take(&mut self.subtasks)),  // 并发驱动附属任务
            self.run_consumer(),                             // 运行消费循环
        ).1
    }.boxed();

    // 附加四个 scoped context
    let run = expr_context_scope(expr_context, run);     // 表达式上下文
    let run = FRAGMENT_ID::scope(fragment_id, run);      // Fragment ID（日志/指标）
    let run = VNODE_COUNT::scope(vnode_count, run);      // VNode 数量
    let run = CONFIG.scope(config, run);                  // Actor 级配置
    run.await
}
```

这四个 `tokio::task_local` scope 保证了 Executor 树中任何地方的代码都可以通过 `CONFIG::try_get()`、`FRAGMENT_ID::try_get()` 等访问到正确的上下文，而不需要显式传递参数。这是 Rust 异步编程中的经典模式——用 task-local 替代参数透传。

`tokio::join!` 并发驱动 subtasks 和 consumer。当 `run_consumer` 完成时（Stop Mutation），`join_all(subtasks)` 也会因为 Actor 退出而被取消。这里只关心 `run_consumer` 的结果（`.1`）。

### 9.5.2 run_consumer——Barrier 驱动的主循环

`run_consumer`（`actor.rs:235-322`）是 Actor 的"心跳"：

```rust
let mut stream = Box::pin(Box::new(self.consumer).execute());
let result = loop {
    let barrier = match stream.try_next().await {
        Ok(Some(barrier)) => barrier,
        Ok(None) => break Err(anyhow!("actor exited unexpectedly").into()),
        Err(err) => break Err(err),
    };
    // 检查 Stop 信号
    if barrier.is_stop(id) {
        break Ok(barrier);
    }
    // 向 LocalBarrierManager 上报收集完成
    self.barrier_manager.collect(id, &barrier);
    // 更新 epoch 追踪
    last_epoch = Some(barrier.epoch);
};
```

这个循环的精妙在于它的极简：

1. **每轮循环只消费一个 Barrier**。这就是 `StreamConsumer` trait 的约定——消费 Barrier 意味着所有内部数据已被处理。`try_next()` 内部可能经历了数千次 Chunk 的消费，但 `run_consumer` 只看到 Barrier。
2. **Stop 检查在 collect 之前**。Actor 在收到停止自己的 Barrier 时退出循环，不经 collect 直接 break。collect 发生在正常 Barrier 时，告诉系统"这个 epoch 我已经完成了"。
3. **退出后再次 collect Stop Barrier**（`actor.rs:315-318`）。这是为了释放 Actor 占用的资源后，告诉系统"我的最终状态已落盘，可以安全删除了"。

`spawn_blocking_drop_stream(stream)` 在 Actor 退出后以 blocking task 方式 drop 整个 Executor 树。这是因为 Executor 内部的 in-memory cache 可能很大（HashAgg 的状态表、HashJoin 的 degree 表），同步 drop 会阻塞 Tokio 调度器。blocking task 确保其他 Actor 不受影响。

---

## 9.6 Actor 生命周期的五阶段状态机

Actor 的生命周期不是简单的"运行/停止"二元状态。它有一个精细的状态机，定义在 `PartialGraphStatus`（`managed_state.rs:401-408`）：

```rust
pub(in crate::task) enum PartialGraphStatus {
    ReceivedExchangeRequest(Vec<(UpDownActorIds, TakeReceiverRequest)>),
    Running(PartialGraphState),
    Suspended(SuspendedPartialGraphState),
    Resetting,
    Unspecified,
}
```

```
                        Meta 注入 Barrier + actors_to_build
                                  │
                                  ▼
                  ReceivedExchangeRequest ──────────────────┐
                  (等待上游建立连接)                          │
                       │                                     │
                       │ exchange 注册完成                    │
                       ▼                                     │
                  Running ◄────────────────────────────┐     │
                  (正常执行 Barrier 循环)               │     │
                       │                               │     │
                  ┌────┼────┐                          │     │
                  │    │    │                          │     │
           Actor  │ 正常  │ Actor                      │     │
           Error  │ Stop  │ 被扩缩容替换                 │     │
                  │    │    │                          │     │
                  ▼    ▼    ▼                          │     │
              Suspended   (Actor 销毁，从 Running 移除) ─┘     │
              (挂起，等待 Meta 指令)                            │
                  │                                             │
                  │ Meta ResetPartialGraphsRequest              │
                  ▼                                             │
              Resetting                                         │
              (清理 Actor 句柄 + 输入队列)                       │
                  │                                             │
                  │ 清理完成，通知 Meta                          │
                  ▼                                             │
              ReceiveExchangeRequest ← (回到初始态) ────────────┘
```

### 9.6.1 Running 态的内部——Barrier 级状态机

在 `Running` 态内部，还有一个更细粒度的 per-epoch 状态机 `ManagedBarrierStateInner`（`managed_state.rs:67-81`）：

```rust
enum ManagedBarrierStateInner {
    Issued(IssuedState),        // Barrier 已下发给 Actor，正在收集
    AllCollected { ... },       // 所有 Actor 都已收集完成
}
```

每个 epoch 的完整生命周期：

```
InjectBarrierRequest from Meta
  │
  ├── 创建新 Actor（如果有 actors_to_build）
  │     spawn_actor → create_actor → Actor::run
  │
  ▼
transform_to_issued(barrier, actor_ids_to_collect)
  │
  │ InflightActorState::issue_barrier
  │ → 通过 mpsc channel 发送 Barrier 给每个 Actor
  │
  ▼
Issued { remaining_actors: [A1, A2, A3, ...] }
  │
  │ 每个 Actor 在 run_consumer 循环中
  │ barrier_manager.collect(id, &barrier)
  │ → LocalBarrierEvent::ReportActorCollected
  │ → PartialGraphState::collect(actor_id, epoch)
  │ → remaining_actors.remove(actor_id)
  │
  ▼
AllCollected { progress, ... }
  │
  │ on_epoch_completed
  │ → 如果 Checkpoint: sync state store
  │ → 构造 BarrierCompleteResponse
  │ → gRPC → Meta 汇报完成
  │
  ▼
Meta 收到，推进全局 epoch
```

### 9.6.2 InflightActorState——单个 Actor 的追踪

`InflightActorState`（`managed_state.rs:201-214`）追踪单个 Actor 在 Barrier 流的地位：

```rust
pub(crate) struct InflightActorState {
    actor_id: ActorId,
    status: InflightActorStatus,    // IssuedFirst | CollectedFirst
    join_handle: JoinHandle<()>,
    monitor_task_handle: Option<JoinHandle<()>>,
    barrier_sender: Option<mpsc::UnboundedSender<Barrier>>,
}
```

`InflightActorStatus` 有两种状态：
- **`IssuedFirst`**：Actor 已被注入了一些 Barrier，但还没完成第一次收集
- **`CollectedFirst`**：Actor 已完成第一次 Barrier 收集，之后的 Barrier 正常流转

第一次 Barrier 之所以特殊，是因为 Actor 可能需要 `pause_on_startup`——等待 Backfill 完成或者上游数据对齐。`MaxIssuedEpoch` 方法（`managed_state.rs:191-195`）追踪已下发给 Actor 的最大 epoch，确保 epoch 严格递增。

### 9.6.3 Suspended 态

当 Actor 遇到错误或 `suspend` 被调用时（`managed_state.rs:463-475`）：

```rust
pub(super) fn suspend(
    &mut self,
    failed_actor: Option<ActorId>,
    err: StreamError,
    completing_futures: Option<FuturesOrdered<AwaitEpochCompletedFuture>>,
) {
    let state = must_match!(replace(self, PartialGraphStatus::Unspecified),
        PartialGraphStatus::Running(state) => state);
    *self = PartialGraphStatus::Suspended(SuspendedPartialGraphState::new(
        state, Some((failed_actor, err)), completing_futures,
    ));
}
```

Suspended 态保留 failed actor 的错误信息和时间戳（`suspend_time`），等待 Meta 下发 `ResetPartialGraphsRequest` 来进入 Resetting 态。

---

## 9.7 LocalBarrierWorker——事件驱动的心脏

`LocalBarrierWorker`（`barrier_worker/mod.rs:300-313`）是 Compute Node 上所有 PartialGraph 的中央协调器：

```rust
pub(super) struct LocalBarrierWorker {
    pub(super) state: ManagedBarrierState,          // 所有 PartialGraph 的状态
    await_epoch_completed_futures: HashMap<...>,     // 等待 epoch 完成的 futures
    control_stream_handle: ControlStreamHandle,      // 与 Meta 的双向流
    pub(super) actor_manager: Arc<StreamActorManager>,
    pub(super) term_id: String,
}
```

其主 `run` 循环（`barrier_worker/mod.rs:370-400+`）是一个 `select!` 驱动的多路事件处理：

```
loop {
    select! {
        event = self.state.next_event() => {
            match event {
                BarrierCollected → complete_barrier → 更新 epoch
                ActorError → on_partial_graph_failure → suspend
                PartialGraphsReset → ack_partial_graph_reset → 通知 Meta
                RegisterLocalUpstreamOutput → 建立本地通道
            }
        }
        partial_graph_id, barrier, result =
            next_completed_epoch(futures) => {
            on_epoch_completed → 构造 response → gRPC → Meta
        }
        local_actor_op = actor_op_rx.recv() => {
            match op {
                NewControlStream → 更新 control stream
                TakeReceiver → 分配通道
                Shutdown → 优雅退出
            }
        }
    }
}
```

`ControlStreamHandle`（`barrier_worker/mod.rs:110-131`）是对 Meta 双向流的封装。它内部持有一对 `(sender, receiver_stream)`，负责接收 Meta 的 `InjectBarrierRequest` 和发送 `BarrierCompleteResponse`。当连接断开时，`reset_stream_with_err`（`barrier_worker/mod.rs:136-146`）通过 sender 发送错误通知已建立的等待者。

---

## 9.8 端到端示例：一个 MV 的 Actor 生命周期

以 `CREATE MATERIALIZED VIEW mv1 AS SELECT count(*) FROM t GROUP BY a` 为例，看 Actor 从无到有的完整过程：

```
Meta Service                                    Compute Node
────────────                                    ────────────
① GlobalBarrierManager 决定注入 Barrier Epoch=1
   携带 actors_to_build=[ActorInfo {
     actor_id: 10,
     fragment_id: 2,
     vnode_bitmap: [vnode 0-63],
     dispatchers: [],
     stream_node: StreamMaterialize → StreamHashAgg → Merge
   }]

② gRPC InjectBarrier
                                               ③ LocalBarrierWorker.run
                                                 control_stream next_request
                                                 → InjectBarrierRequest

                                               ④ PartialGraphState.transform_to_issued
                                                 ├─ 检查 actors_to_build: [ActorInfo(10)]
                                                 ├─ spawn_actor(ActorInfo(10))
                                                 │  ├─ ActorContext::create → ctx
                                                 │  ├─ create_nodes:
                                                 │  │  Merge(UpstreamFragment=0)
                                                 │  │  → HashAgg → Materialize
                                                 │  │  → DispatchExecutor(dispatchers=[])
                                                 │  ├─ Actor::new(dispatch, ...)
                                                 │  └─ runtime.spawn(actor.run())
                                                 │
                                                 └─ issue_barrier(barrier, actor_ids=[10])
                                                       │
                                                       ▼
                                               ⑤ Actor 10 的 run_consumer 循环启动
                                                 try_next() → 阻塞等待第一个 Barrier

                                               ⑥ barrier_tx.send(Barrier { epoch=(1,0), kind:Checkpoint })
                                                       │
                                                       ▼
                                               ⑦ Actor 10 run_consumer:
                                                 try_next() → Ok(Barrier { epoch=(1,0) })
                                                 barrier.is_stop(10)? → No
                                                 barrier_manager.collect(10, &barrier)
                                                   → LocalBarrierEvent::ReportActorCollected
                                                       │
                                                       ▼
                                               ⑧ PartialGraphState::collect(10, epoch=(1,0))
                                                 remaining_actors.remove(10) → empty!
                                                 → ManagedBarrierStateInner::AllCollected
                                                       │
                                                       ▼
                                               ⑨ on_epoch_completed
                                                 ├─ sync state store (Checkpoint)
                                                 └─ gRPC BarrierCompleteResponse
                                                       │
                                                       ▼
⑩ Meta 收到 BarrierComplete → 推进全局 epoch 到 2
   循环 ②-⑩ 持续执行...
```

当执行 `DROP MATERIALIZED VIEW mv1` 时：

```
Meta 注入 Barrier Epoch=N + Stop Mutation(dropped_actors=[10])

Actor 10 run_consumer:
  try_next() → Ok(Barrier { mutation: Some(Stop({dropped_actors:[10]})), ... })
  barrier.is_stop(10) → true
  break Ok(barrier)

spawn_blocking_drop_stream(stream) → 清理 Executor 树
barrier_manager.collect(10, &stop_barrier) → 最终状态上报
Actor 退出
```

---

## 9.9 与 Flink / Spark 的对比

### 9.9.1 Actor vs Flink Task/Subtask

| 维度 | RisingWave Actor | Flink Task (Subtask) |
|------|-----------------|---------------------|
| 粒度 | 一个 Fragment 的所有算子（1个） | 一个 JobVertex 的并行实例 |
| 数据传递 | 同 Actor 内通过函数调用 | 同 Task 内通过 `StreamRecordQueue` |
| 调度 | 1 Actor = 1 Tokio Task | 1 Subtask = 1 Thread |
| Barrier | Actor 主动上报 `collect` | Task 被动等待 `CheckpointBarrier` 对齐 |
| 容错 | 全局 `PartialGraph` 级 Reset | Per-job `ExecutionGraph` 级 Restart |
| 创建代价 | 轻量（Tokio Task spawn） | 较重（需要 TM 资源分配 + 线程池调度） |

关键差异：**RisingWave 的 Actor 是同 Fragment 的下完整算子链，而 Flink 的 Subtask 是单个算子（Chain 除外）**。在 Flink 中，`Source → Map → Filter → KeyBy → Window → Sink` 可能被 chain 优化为少数几个 Task，但默认每个算子是一个独立的 Subtask。在 RisingWave 中，同一个 Fragment 内的所有算子天然就在一个 Actor 里——这就是 Fragment = Exchange 边界的直接推论。

### 9.9.2 Actor vs Spark Stage/Task

| 维度 | RisingWave Actor | Spark Task |
|------|-----------------|-----------|
| 生命周期 | 长期运行（流式，持续到 Stop） | 短期运行（批式，完成后退出） |
| 数据粒度 | 增量 Chunk（若干行） | 全量 Partition |
| 状态 | 有状态（State Table，跨 Barrier 保持） | 无状态（或依赖 Shuffle+Disk） |
| 错误处理 | Failover 恢复 + 状态快照 | Stage 级重试 |
| 并发模型 | 异步（async fn + Tokio） | 同步（线程池） |

根本差异在于**流 vs 批的执行哲学**：Spark Task 是"拿一批数据、算完、输出、关闭"，RisingWave Actor 是"无限循环、每来一批数据就算、永不关闭（除非 Stop）"。这种差异不是实现细节，而是第一性原理级别的——批处理的状态是计算完毕就丢弃的工作集，流处理的状态是需要跨 epoch 持久化的数据资产。

---

## 9.10 小结

本章从 Actor 结构到生命周期到事件系统，完成了对 RisingWave 运行时调度单元的全面剖析：

- **Actor 是 Fragment 的运行时实例**，内部包含完整的 Executor 链，1 Actor = 1 Tokio Task
- **ActorContext** 携带 Actor 一生不变的元数据（ID、vnode_count、dispatch_num、config override）
- **LocalBarrierManager** 通过 `LocalBarrierEvent` 枚举，将 Actor 的 Barrier 收集、错误通知、进度上报等事件桥接到 LocalBarrierWorker
- **生命周期五阶段**：`ReceivedExchangeRequest → Running → Suspended → Resetting → ReceivedExchangeRequest`，由 Meta 的命令驱动
- **Barrier 级状态机**：`Issued → AllCollected`，每个 epoch 的 Barrier 都经历下发-收集-完成的全过程
- **与 Flink/Spark 的根本差异**：Actor 是长生命期的、有状态的、由 Barrier 驱动的异步执行体

从下一章开始，我们将深入 Actor 之间的数据流动，看 Exchange/Dispatch/Merge 如何在 Actor 拓扑中编织数据消息的网络。

---

*本章完成。下一章：[第 10 章 · 数据流动：Exchange 与 Dispatch](../chapters/10-数据流动-Exchange与Dispatch.md)*
