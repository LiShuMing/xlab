# 第 8 章 · 核心抽象：Message / Barrier / Executor

> **核心源码**：
> - `src/stream/src/executor/mod.rs` — Message、Barrier、Mutation、Watermark、DynamicReceivers、DispatchBarrierBuffer（1881 行）
> - `src/stream/src/executor/actor.rs` — Actor、ActorContext、Actor 生命周期
> - `src/stream/src/executor/barrier_recv.rs` — BarrierRecvExecutor，本地 Barrier 注入入口
> - `src/common/src/util/epoch.rs` — Epoch 与 EpochPair 定义
> - `proto/stream_plan.proto` — Barrier protobuf 定义（BarrierKind 枚举、Barrier 消息体）
> **关键数据结构**：`Message`、`Barrier`、`Mutation`、`Watermark`、`Executor`/`Execute`、`DynamicReceivers`、`StreamChunk`

---

## 8.1 三条消息，一个流

进入 RisingWave 流计算引擎内部，你看到的不是 SQL、不是算子树、也不是 Fragment Graph——你看到的只有一个东西：**消息流**。所有 Actor 之间、所有 Executor 之间，只通过一种渠道通信：

```rust
// executor/mod.rs:1276-1280
pub enum MessageInner<M> {
    Chunk(StreamChunk),
    Barrier(BarrierInner<M>),
    Watermark(Watermark),
}
```

这就是 RisingWave 流引擎的"最小语汇"——三种消息类型构成了流计算的完整语义：

| 消息类型 | 携带内容 | 语义 |
|---------|---------|------|
| `Chunk` | 数据行的增删改 | 数据变更，业务的核心 |
| `Barrier` | epoch + 控制指令（Mutation） | 全局时钟 + 拓扑变更命令 |
| `Watermark` | 列索引 + 水印值 | 事件时间进度，窗口触发依据 |

> **第一性原理思考**：流计算的本质是什么？如果批处理的本质是"对一个静态数据集的一次完整计算"，那么流处理的本质就是"对一个持续变化的数据集的持续计算"。这就要求流引擎必须同时处理两类信息：**数据变化**（什么数据变了）和**时间推移**（现在算到哪里了）。Chunk 承担前者，Barrier 和 Watermark 共同承担后者——Barrier 代表"处理时间"的推进，Watermark 代表"事件时间"的推进。三者合一，才能完整描述一个流式世界的状态。

---

## 8.2 Chunk——数据的最小传输单元

`StreamChunk` 定义在 `src/common/src/array/stream_chunk.rs`，是 RisingWave 中数据变更的载体。它不是一个简单的行集合，而是**带变更语义的列式数据块**：

```
StreamChunk
├── columns: Vec<ArrayImpl>       // 列式存储的数据列
├── visibility: Bitmap            // 哪些行是可见的
└── ops: Vec<Op>                  // 每行的操作类型
    ├── Op::Insert    (+)
    ├── Op::Delete    (-)
    ├── Op::UpdateDelete (U-)
    └── Op::UpdateInsert (U+)
```

`UpdateDelete + UpdateInsert` 成对出现，表示一行"先删后插"的更新操作。这与 PostgreSQL 的 `RETRACT` 语义直接对应——流中的更新不是 `UPDATE SET`，而是 **Delete + Insert 的原子对**。

`StreamChunk` 的内部存储是列式的（`ArrayImpl`），但变更语义是按行的（`Op`）。这种"列存 + 行操作"的混合设计有两个好处：
- **内存高效**：数据以列式压缩存储，减少缓存未命中
- **语义清晰**：每行的变更语义独立，算子不需要跨列推断

在 Actor 内部，`StreamChunk` 直接传递；在 Actor 之间，它被序列化为 protobuf（`to_protobuf()` / `from_protobuf()`），通过 gRPC `Stream` 传输。

---

## 8.3 Barrier——全局时钟与控制信号

### 8.3.1 Barrier 的数据结构

```rust
// executor/mod.rs:402-410
pub struct BarrierInner<M> {
    pub epoch: EpochPair,
    pub mutation: M,
    pub kind: BarrierKind,
    pub tracing_context: TracingContext,
}
```

两个具体的类型别名：

```rust
// executor/mod.rs:412-414
pub type BarrierMutationType = Option<Arc<Mutation>>;
pub type Barrier = BarrierInner<BarrierMutationType>;       // Actor 内部
pub type DispatcherBarrier = BarrierInner<()>;              // 跨 Actor 传输（Mutation 已擦除）
```

为什么有两种 Barrier？这是因为**Mutation 的生命周期不同**：在 Actor 内部，各算子需要读取 Mutation 执行相应的变更；但在 Actor 之间（通过 protobuf 传输时），Mutation 已经被 DispatchExecutor 消费并转化为具体的 `DispatcherUpdate` / `MergeUpdate` 操作，下游 Actor 只需要知道 epoch 即可。`DispatcherBarrier` 的 `mutation: ()` 就是这种"已擦除"状态。

### 8.3.2 EpochPair——双纪元机制

```rust
// common/src/util/epoch.rs:156-159
pub struct EpochPair {
    pub curr: u64,
    pub prev: u64,
}
```

每个 Barrier 携带的不是一个 epoch，而是一个 **epoch pair（当前 + 前一个）**。这背后的原因是什么？

想象一个 `HashJoinExecutor`：它维护左右两张状态表。当它收到 epoch=5 的 Barrier 时，它需要将 epoch=4 期间的增量数据合并到状态表中，为 epoch=5 做好准备。此时它既需要知道"现在的 epoch 是什么"（curr=5），也需要知道"前一个 epoch 是什么"（prev=4）——因为某些状态清理需要按 prev epoch 来做。

更深层的原因：在 RisingWave 的分布式 Checkpoint 中，每个 epoch 的数据需要同时存在于存储层（Hummock）中，用 epoch 作为版本号。`EpochPair` 使得算子始终能追踪"当前"和"上一次"两个时间点。

### 8.3.3 BarrierKind——屏障的四种角色

```protobuf
// proto/stream_plan.proto:213-222
message Barrier {
  enum BarrierKind {
    BARRIER_KIND_UNSPECIFIED = 0;
    BARRIER_KIND_INITIAL = 1;    // 首次启动或恢复后的第一个 Barrier
    BARRIER_KIND_BARRIER = 2;     // 普通 Barrier，本地 Flush
    BARRIER_KIND_CHECKPOINT = 3;  // Checkpoint Barrier，同步到共享存储
  }
  // ...
}
```

四种 BarrierKind 形成了 **逐步升级的持久化要求**：

| Kind | 触发时机 | 持久化要求 | 频率 |
|------|---------|-----------|------|
| `Initial` | Actor 启动 / 恢复 | 无，前一个 epoch 无数据 | 一次性 |
| `Barrier` | Meta 定期注入 | 本地 Flush（写 MemTable） | 高频（毫秒级） |
| `Checkpoint` | Meta 按配置间隔注入 | Flush + 共享存储同步 | 低频（秒级，可配） |
| `Unspecified` | （保留/未使用） | — | — |

`Barrier` 和 `Checkpoint` 的区别是关键设计：
- **Barrier** 只要求算子将内部缓冲的数据刷到本地状态存储（Hummock Shared Buffer），不强制同步到对象存储。这保证了低延迟。
- **Checkpoint** 要求数据必须同步到对象存储（S3/MinIO），为故障恢复提供可靠的快照。

这种"Barrier 快 + Checkpoint 稳"的分层策略，让 RisingWave 在延迟和可靠性之间取得了灵活的平衡。用户可以通过调整 `barrier_interval_ms` 和 `checkpoint_interval_ms` 配置来微调这个平衡。

### 8.3.4 Barrier 的注入路径

```
Meta (GlobalBarrierManager)
  │
  │  gRPC InjectBarrier
  ▼
Compute Node (LocalBarrierManager)
  │
  │  mpsc::unbounded_channel
  ▼
BarrierRecvExecutor
  │
  │  Message::Barrier(barrier) 进入流图
  ▼
所有下游 Executor
```

`BarrierRecvExecutor` 是每个 Actor 中 Barrier 的入口（`barrier_recv.rs:22-27`）：

```rust
pub struct BarrierRecvExecutor {
    _ctx: ActorContextRef,
    barrier_receiver: UnboundedReceiver<Barrier>,
}
```

它的 `execute()` 方法极其简洁——只是把 `UnboundedReceiver` 转成 `MessageStream`。选用 `unbounded_channel` 是因为 Barrier 绝不能阻塞：如果 channel 满了导致 Meta 无法注入 Barrier，整个集群的时钟就会停滞。

---

## 8.4 Mutation——控制指令的类型体系

### 8.4.1 Mutation 枚举

```rust
// executor/mod.rs:362-396
pub enum Mutation {
    Stop(StopMutation),
    Update(UpdateMutation),
    Add(AddMutation),
    SourceChangeSplit(SplitAssignments),
    Pause,
    Resume,
    Throttle(HashMap<FragmentId, ThrottleConfig>),
    ConnectorPropsChange(HashMap<u32, HashMap<String, String>>),
    DropSubscriptions { subscriptions_to_drop: Vec<SubscriptionUpstreamInfo> },
    StartFragmentBackfill { fragment_ids: HashSet<FragmentId> },
    RefreshStart { table_id: TableId, associated_source_id: SourceId },
    ListFinish { associated_source_id: SourceId },
    LoadFinish { associated_source_id: SourceId },
    ResetSource { source_id: SourceId },
    InjectSourceOffsets { source_id: SourceId, split_offsets: HashMap<String, String> },
}
```

Mutation 是 Barrier 的核心负载——它告诉每个 Actor："在这个 epoch，你要执行以下控制操作"。没有 Mutation 的 Barrier（`mutation: None`）就是纯粹的时钟信号。这 13 种 Mutation 覆盖了流作业的完整生命周期：

### 8.4.2 三大核心 Mutation

**Stop Mutation** — Actor 销毁（`executor/mod.rs:354-357`）：

```rust
pub struct StopMutation {
    pub dropped_actors: HashSet<ActorId>,
    pub dropped_sink_fragments: HashSet<FragmentId>,
}
```

当 MV 被 `DROP` 或被替换时，Meta 在 Barrier 中附加 Stop Mutation，告诉相关 Actor "这是你的最后一个 Barrier"。在 `Actor::run_consumer()` 中（`actor.rs:298-301`）：

```rust
if barrier.is_stop(id) {
    debug!(actor_id = %id, epoch = ?barrier.epoch, "stop at barrier");
    break Ok(barrier);
}
```

Actor 收到 Stop 后有序退出，将最终状态刷到存储，确保恢复时的一致性。

**Add Mutation** — Actor 创建/扩容（`executor/mod.rs:338-350`）：

```rust
pub struct AddMutation {
    pub adds: HashMap<ActorId, Vec<PbDispatcher>>,
    pub added_actors: HashSet<ActorId>,
    pub splits: SplitAssignments,
    pub pause: bool,
    pub subscriptions_to_add: Vec<(TableId, SubscriberId)>,
    pub backfill_nodes_to_pause: HashSet<FragmentId>,
    pub actor_cdc_table_snapshot_splits: CdcTableSnapshotSplitAssignmentWithGeneration,
    pub new_upstream_sinks: HashMap<FragmentId, PbNewUpstreamSink>,
}
```

`pause: bool` 字段特别重要：新创建的 Actor 需要等待上游 Backfill 完成对齐后才能开始消费数据，所以在第一个 Barrier 中 `pause=true`，Actor 启动后进入暂停状态。

**Update Mutation** — 动态调整拓扑（`executor/mod.rs:324-334`）：

```rust
pub struct UpdateMutation {
    pub dispatchers: HashMap<ActorId, Vec<DispatcherUpdate>>,
    pub merges: HashMap<(ActorId, UpstreamFragmentId), MergeUpdate>,
    pub vnode_bitmaps: HashMap<ActorId, Arc<Bitmap>>,
    pub dropped_actors: HashSet<ActorId>,
    pub actor_splits: SplitAssignments,
    pub actor_new_dispatchers: HashMap<ActorId, Vec<PbDispatcher>>,
    pub actor_cdc_table_snapshot_splits: CdcTableSnapshotSplitAssignmentWithGeneration,
    pub sink_schema_change: HashMap<SinkId, PbSinkSchemaChange>,
    pub subscriptions_to_drop: Vec<SubscriptionUpstreamInfo>,
}
```

Update Mutation 是最高频的控制操作，用于两种场景：
1. **扩缩容**：修改 dispatchers 和 merges，将数据重分布到新的 Actor 集合
2. **Sink Schema Change**：当 Sink 的输出 Schema 变更时，更新下游连接器

### 8.4.3 其他 Mutation 的语义

| Mutation | 语义 | 使用场景 |
|----------|------|---------|
| `Pause` / `Resume` | 暂停/恢复 Actor 数据消费 | 扩容后的对齐期 |
| `SourceChangeSplit` | 变更 Source 的 Split 分配 | Kafka Partition 重分配 |
| `Throttle` | 限制指定 Fragment 的吞吐 | 资源管控 |
| `DropSubscriptions` | 取消订阅 MV | SUBSCRIPTION CURSOR 关闭 |
| `StartFragmentBackfill` | 触发 Backfill | 新 MV 的历史数据回填 |
| `RefreshStart/ListFinish/LoadFinish` | MV Refresh 生命周期 | REFRESH MATERIALIZED VIEW |
| `ResetSource` | 重置 Source 状态 | 故障恢复 |
| `InjectSourceOffsets` | 注入 Source Offset | 时间旅行/精确恢复 |
| `ConnectorPropsChange` | 更新连接器属性 | ALTER SOURCE/SINK 动态配置 |

> **设计洞察**：Mutation 类型从最初的几个演变到如今的 13 种，反映了一个普遍规律——**控制平面总是比数据平面更复杂**。数据平面只需处理三种消息（Chunk/Barrier/Watermark），但控制平面需要处理创建、销毁、暂停、恢复、扩容、缩容、属性变更、订阅管理、Backfill 协调等大量操作。实际上，RisingWave 中最容易出 Bug 的代码不在算子逻辑里，而在 Mutation 的处理路径上。

---

## 8.5 Watermark——事件时间的标尺

```rust
// executor/mod.rs:1199-1204
pub struct Watermark {
    pub col_idx: usize,
    pub data_type: DataType,
    pub val: ScalarImpl,
}
```

Watermark 只包含三样东西：一个列索引（哪一列代表事件时间）、一个数据类型（时间戳的类型）、一个标量值（当前 watermark 的值）。

Watermark 的语义是：**"在所有来自 Source 的数据中，列 `col_idx` 的值不会再有小于（或大于，取决于窗口语义）`val` 的了"**。这个看似简单的承诺，是窗口计算（Tumble/Hop/Session）和 Temporal Join 的前提。

Watermark 在流中有两处关键变换：

1. **`transform_with_expr`**（`mod.rs:1227-1240`）：当 Project 算子对 watermark 列做了表达式变换时（如 `window_start + INTERVAL '1' HOUR`），watermark 值也需要同样的变换
2. **`transform_with_indices`**（`mod.rs:1244-1249`）：当列被重排或剪枝时，重新映射列索引

`DynamicReceivers` 中的 Watermark 处理则负责对齐：当多个上游输入对齐到同一个 Barrier 时，系统需要从多个上游对同一列的 watermark 中取"最保守"的值（`BufferedWatermarks`——`mod.rs:1465-1466`）。

---

## 8.6 Executor 与 Execute——双层 trait 封装

这是 RisingWave 流引擎中最精妙的设计之一：

```rust
// executor/mod.rs:240-253
pub trait Execute: Send + 'static {
    fn execute(self: Box<Self>) -> BoxedMessageStream;
    fn execute_with_epoch(self: Box<Self>, _epoch: u64) -> BoxedMessageStream;
    fn boxed(self) -> Box<dyn Execute> where Self: Sized + Send + 'static;
}

// executor/mod.rs:257-260
pub struct Executor {
    info: ExecutorInfo,
    execute: Box<dyn Execute>,
}
```

**Execute trait** 是行为抽象——任何实现了 `Execute` 的类型都是一个可执行的流处理器。`execute()` 方法接收 `Box<Self>`，返回 `BoxedMessageStream`。这个签名意味着：调用者交出所有权，获得一个消息流。

**Executor struct** 是信息+行为的组合体：

```rust
// executor/mod.rs:209-225
pub struct ExecutorInfo {
    pub schema: Schema,           // 输出 Schema
    pub stream_key: StreamKey,    // 输出流键（用于分布）
    pub stream_kind: PbStreamKind, // 流的 Retract/Append 特性
    pub identity: String,         // 执行器标识（用于调试）
    pub id: ExecutorId,           // 全局唯一 ID
}
```

这种双层封装的好处：

1. **信息可提前获取**：不需要构造完整的 `Execute` 就可以拿到算子信息（Schema、StreamKey），这在 Optimizer 和 Fragmenter 中至关重要
2. **`Execute` 可以在被包在 `Box` 中**：`Executor` 内部的 `Box<dyn Execute>` 使得算子可以被动态分发，支持"先知道元数据，后执行"的模式
3. **类型擦除**：各种不同的算子（`FilterExecutor`、`HashJoinExecutor`、`HashAggExecutor`）都擦除为 `Box<dyn Execute>`，统一放入 `Executor` 中

看看 `From` 的便利实现（`mod.rs:302-315`）：

```rust
impl From<(ExecutorInfo, Box<dyn Execute>)> for Executor {
    fn from((info, execute): (ExecutorInfo, Box<dyn Execute>)) -> Self {
        Self::new(info, execute)
    }
}

impl<E> From<(ExecutorInfo, E)> for Executor
where E: Execute,
{
    fn from((info, execute): (ExecutorInfo, E)) -> Self {
        Self::new(info, execute.boxed())
    }
}
```

---

## 8.7 MessageBatch——Actor 内/外格式转换

在 Actor 之间，消息通过 gRPC 流传输。为了减少网络往返，多个 Barrier 可以被**批量发送**：

```rust
// executor/mod.rs:1298-1305
pub enum MessageBatchInner<M> {
    Chunk(StreamChunk),
    BarrierBatch(Vec<BarrierInner<M>>),
    Watermark(Watermark),
}
pub type MessageBatch = MessageBatchInner<BarrierMutationType>;
pub type DispatcherMessageBatch = MessageBatchInner<()>;
```

`MessageBatch` 和 `Message` 的区别只有一点：`Message::Barrier` 在 `MessageBatch` 中变成了 `BarrierBatch(Vec<Barrier>)`。这使得网络层可以攒批——比如当 Meta 快速注入了多个非 Checkpoint 的 Barrier 时，它们可以被打包为一次 gRPC 消息发送。

`DispatcherMessageBatch` 有完整的 protobuf 序列化/反序列化（`mod.rs:1353-1403`），处理 BarrierBatch 时从 protobuf 直接反序列化为 `Vec<DispatcherBarrier>`，确保类型安全和零拷贝引用。

---

## 8.8 DynamicReceivers——屏障对齐的核心算法

`DynamicReceivers`（`mod.rs:1456-1571`）是 RisingWave 中屏障对齐（Barrier Alignment）的算法实现。它是 `MergeExecutor` 和 `UnionExecutor` 的底层引擎。

```rust
// executor/mod.rs:1456-1471
pub struct DynamicReceivers<InputId, M> {
    barrier: Option<BarrierInner<M>>,
    start_ts: Option<Instant>,
    blocked: Vec<BoxedMessageInput<InputId, M>>,
    active: FuturesUnordered<StreamFuture<BoxedMessageInput<InputId, M>>>,
    buffered_watermarks: BTreeMap<usize, BufferedWatermarks<InputId>>,
    barrier_align_duration: Option<LabelGuardedMetric<GenericCounter<AtomicU64>>>,
    merge_barrier_align_duration: Option<LabelGuardedMetric<GenericCounter<AtomicU64>>>,
}
```

屏障对齐算法的核心流程：

```
1. 从 active 上游中轮询消息
   ├── Chunk     → 直接输出（不阻塞）
   ├── Watermark → 缓冲，对齐后输出
   └── Barrier   → 阻塞该上游
         ├── 第一个 Barrier → 记录为当前对齐目标
         ├── 后续 Barrier   → 校验 epoch 必须一致
         └── 所有上游都阻塞 → 对齐完成
               │
2. 所有上游阻塞后
   ├── 计算对齐耗时（barrier_align_duration）
   ├── 释放 aligned Barrier 到下游
   ├── 将所有 blocked 上游移回 active
   └── 继续轮询
```

这个算法的精妙之处在于：
- **Chunk 不阻塞**：在 Barrier 对齐等待期间，已经从某个上游收到的 Chunk（带有当前或更早 epoch 的数据）可以直接输出，不需要等待
- **Watermark 批量输出**：多个上游对同一列的 watermark 会在屏障对齐时取最保守值一并输出
- **动态上游**：`extend_active()` 和类似的移除操作允许运行时动态增减上游——这正是扩容和故障恢复的基础

屏障对齐的 epoch 一致性校验（`mod.rs:1514-1523`）：

```rust
if let Some(current_barrier) = self.barrier.as_ref() {
    if current_barrier.epoch != barrier.epoch {
        return Poll::Ready(Some(Err(
            StreamExecutorError::align_barrier(
                current_barrier.clone().map_mutation(|_| None),
                barrier.map_mutation(|_| None),
            ),
        )));
    }
}
```

如果两个不同上游在同一个"屏障窗口"中发来了不同 epoch 的 Barrier，这属于严重的一致性错误，必须立即上报。

> **第一性原理思考**：为什么需要 Barrier Alignment？因为不同的 Source 有不同的速率。上游 A 可能在一秒内产出 1000 条数据后到达 Barrier，上游 B 可能只产出 3 条数据就到达 Barrier。如果不做对齐，Join 算子会看到一个上游在 epoch 5 而另一个还在 epoch 3，产生跨 epoch 的不一致结果。Barrier Alignment = 流计算的分布式同步点。

---

## 8.9 DispatchBarrierBuffer——两阶段变更应用

`DispatchBarrierBuffer`（`mod.rs:1701-1880`）是 Actor 网络层最巧妙的设计。

```rust
pub(crate) struct DispatchBarrierBuffer {
    buffer: VecDeque<(Barrier, Option<Vec<BoxedActorInput>>)>,
    barrier_rx: mpsc::UnboundedReceiver<Barrier>,
    recv_state: BarrierReceiverState,
    curr_upstream_fragment_id: FragmentId,
    actor_id: ActorId,
    build_input_ctx: Arc<BuildInputContext>,
}
```

`DispatchBarrierBuffer` 解决的核心问题：**当 Barrier 携带 Update Mutation（需要建立新的上游 Actor 连接）时，必须先建立连接并验证 Barrier 一致性，才能将 Barrier 发送给下游算子**。

其 `try_fetch_barrier_rx` 方法实现了一个**两阶段状态机**（`mod.rs:1809-1834`）：

```
BarrierReceiverState::ReceivingBarrier
  │
  │ barrier_rx.recv() → 收到 Barrier
  │
  ├── 无新上游 → buffer.push_back((barrier, None))
  │                继续 ReceivingBarrier
  │
  └── 有新上游 → BarrierReceiverState::CreatingNewInput(barrier, fut)
                   │
                   │ fut.await → 建立 gRPC 连接 + 验证第一个 Barrier
                   │
                   ▼
                 buffer.push_back((barrier, Some(new_inputs)))
                 BarrierReceiverState::ReceivingBarrier
```

`pre_apply_barrier`（`mod.rs:1836-1879`）的"预应用"逻辑：当 Barrier 含有 `MergeUpdate` 且有新的上游 Actor 时，**在新输入被建立并对齐到同一个 Barrier 之前，绝不能将这个 Barrier 交给下游**。`DispatchBarrierBuffer` 保证了这一点：它缓存 Barrier，等新输入就绪后，再将 Barrier 和新输入一起交给下游。

这种"先建立通道，再传递 Barrier"的协议，是 RisingWave 在动态拓扑变更下保持 Exactly-Once 语义的基石。

---

## 8.10 Actor——流计算的调度单元

### 8.10.1 ActorContext

```rust
// actor.rs:49-77
pub struct ActorContext {
    pub id: ActorId,
    pub fragment_id: FragmentId,
    pub vnode_count: usize,
    pub mview_definition: String,
    pub streaming_metrics: Arc<StreamingMetrics>,
    pub initial_dispatch_num: usize,
    pub initial_subscriber_ids: HashSet<SubscriberId>,
    pub initial_upstream_actors: HashMap<FragmentId, UpstreamActors>,
    pub meta_client: Option<MetaClient>,
    pub config: Arc<StreamingConfig>,
    pub stream_env: StreamEnvironment,
    // mem tracking fields...
}
```

`ActorContext` 是 Actor 的"出生证明"——它在 Actor 创建时生成，包含 Actor 运行所需的所有静态信息和基础设施引用。`vnode_count` 决定了这个 Actor 持有多少虚拟节点，`initial_dispatch_num` 告诉 Actor 它有多少下游，用于判断是否是"孤立 Actor"（可做特殊优化）。

### 8.10.2 Actor 的 run 循环

```rust
// actor.rs:177-186
pub struct Actor<C> {
    consumer: C,
    subtasks: Vec<SubtaskHandle>,
    pub actor_context: ActorContextRef,
    expr_context: ExprContext,
    barrier_manager: LocalBarrierManager,
}
```

`Actor::run` 的核心是一个精心编排的调度（`actor.rs:210-233`）：

```rust
pub async fn run(mut self) -> StreamResult<()> {
    let run = async move {
        tokio::join!(
            join_all(std::mem::take(&mut self.subtasks)),
            self.run_consumer(),
        ).1
    };
    // 附加上下文：expr_context, FRAGMENT_ID, VNODE_COUNT, CONFIG
    let run = CONFIG.scope(config, run);
    run.await
}
```

`subtasks` 是 Actor 的附属异步任务（如 Source 的 `StreamChunk` 读取循环），它们和 `run_consumer` 并发执行，当 `run_consumer` 完成时（通常是因为收到 Stop Mutation），Actor 退出。

`run_consumer`（`actor.rs:235-322`）则是一个无限循环：

```rust
let result = loop {
    let barrier = match stream.try_next().await {
        Ok(Some(barrier)) => barrier,
        Ok(None) => break Err(anyhow!("actor exited unexpectedly").into()),
        Err(err) => break Err(err),
    };
    if barrier.is_stop(id) {
        break Ok(barrier);
    }
    self.barrier_manager.collect(id, &barrier);
    last_epoch = Some(barrier.epoch);
};
```

Loop 中的每一圈只消费**一个 Barrier**（由 `StreamConsumer` 保证）。它不消费 Chunk 和 Watermark——这些在 Executor 内部被处理了。Actor 层关心的只有 Barrier：用它来追踪 epoch、检查 Stop 信号、向 `LocalBarrierManager` 汇报进度。

---

## 8.11 完整消息流转图

将以上所有抽象串联起来，从 Source 到 Materialize 的消息流转全景：

```
Source(Kafka)                          Meta
    │                                    │
    │ StreamChunk                        │ gRPC InjectBarrier
    ▼                                    ▼
SourceExecutor ────────────────── BarrierRecvExecutor
    │                                    │
    │ Message::Chunk                     │ Message::Barrier
    │ Message::Watermark                 │
    ▼                                    ▼
ChainExecutor ◄──────────────────────────┘
    │
    │ Message::Chunk + Watermark + Barrier (interleaved)
    ▼
FilterExecutor
    │
    ▼
HashJoinExecutor ─── 左右两侧 Barrier 对齐后更新 State Table
    │
    ▼
HashAggExecutor ─── Barrier 时增量合并到 Agg State Table
    │
    ▼
MaterializeExecutor ─── Barrier 时冲突检测 + 写入存储
    │
    │ 向下游 Dispatchers 输出
    ▼
DispatchExecutor ─── 按 distribution key 分发
    │
    │ DispatcherBarrier (Mutation 已擦除)
    ▼
MergeExecutor (下游 Actor) ─── Barrier Alignment
    │
    ▼
  ... 继续传递 ...
```

这个图揭示了流消息的三个关键特性：
1. **Chunk 和 Watermark 被算子处理，Barrier 穿越算子**——算子在收到 Chunk 时立即计算，在收到 Barrier 时才做状态合并
2. **Barrier 在网络边界被改写**——进入 Dispatch 前还是 `Barrier(BarrierMutationType)`，穿过 Dispatch 后变成 `DispatcherBarrier(())`
3. **Chunk 永不阻塞，Barrier 需要对齐**——这是流计算和批计算在执行模型上的根本差异

---

## 8.12 与 Flink 的消息模型对比

| 维度 | RisingWave | Apache Flink |
|------|-----------|-------------|
| 消息类型 | `Message = Chunk \| Barrier \| Watermark` | `StreamRecord` + `Watermark` + `StreamStatus` + `LatencyMarker` |
| Barrier 实现 | Barrier 是独立消息，与数据分离 | `CheckpointBarrier` 是 `StreamElement` 的子类型 |
| 语义一致性 | Barrier Alignment（`DynamicReceivers`） | Aligned / Unaligned Checkpoint |
| Mutation | 13 种结构化 Mutation，精细控制 | 通过 Operator Coordinator 和 Source Split 事件 |
| 数据计算 | 即时处理，"Barrier 时合并" | 即时处理，"Checkpoint 时 snapshot" |

RisingWave 将 Barrier 作为"一等公民"放在 Message 中，且设计了 EpochPair 和 BarrierKind 的细粒度控制，本质上是因为**流数据库需要比流计算引擎更强的状态管理能力**——Flink 的 Checkpoint 主要是为了故障恢复，而 RisingWave 的 Barrier 还承担了物化视图一致性保证和动态拓扑变更的职责。

---

## 8.13 小结

本章从三条消息出发，拆解了 RisingWave 流计算引擎的核心抽象：

- **Message = Chunk | Barrier | Watermark**，Chunk 带变更语义（Insert/Delete/UpdateDelete/UpdateInsert），Barrier 带 epoch pair 和控制指令，Watermark 带事件时间进度
- **Barrier** 拥有四种 Kind（Initial/Barrier/Checkpoint/Unspecified），形成分层持久化策略；EpochPair（curr+prev）使得算子能同时访问两个时间点的状态
- **Mutation** 体系包含 13 种控制指令，覆盖 Actor 创建/销毁/暂停/恢复/扩容/属性变更等全生命周期操作
- **Executor = ExecutorInfo + Box<dyn Execute>** 的双层封装，将"元数据获取"和"消息执行"解耦
- **DynamicReceivers** 实现了屏障对齐算法——Chunk 不阻塞、Barrier 对齐后释放、epoch 不一致则报错
- **DispatchBarrierBuffer** 通过两阶段状态机，确保拓扑变更时新连接先建立、Barrier 再传递，保证 Exactly-Once

从下一章开始，我们将深入到 Actor 模型的运行时细节，看 `LocalBarrierManager` 如何协调 Actor 内的 Barrier 流转，以及 Actor 的生命周期管理。

---

*本章完成。下一章：[第 9 章 · Actor 模型——流计算的调度单元](../chapters/09-Actor模型-流计算的调度单元.md)*
