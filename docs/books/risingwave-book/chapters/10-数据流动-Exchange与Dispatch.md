# 第 10 章 · 数据流动：Exchange 与 Dispatch

> **核心源码**：
> - `src/stream/src/executor/exchange/input.rs` — `LocalInput`、`RemoteInput`、`new_input`（379 行）
> - `src/stream/src/executor/exchange/output.rs` — `Output` 发送端（60 行）
> - `src/stream/src/executor/exchange/permit.rs` — 基于 Semaphore 的背压通道（306 行）
> - `src/stream/src/executor/merge.rs` — `MergeExecutor`、`ReceiverExecutor`、`BufferChunks`（960 行）
> - `src/stream/src/executor/dispatch.rs` — `DispatchExecutor`、分发策略（1799 行）
> - `src/stream/src/executor/mod.rs` — `DynamicReceivers`、`DispatchBarrierBuffer`（已在第 8 章详述）
> **关键数据结构**：`LocalInput`、`RemoteInput`、`Output`、`DispatchExecutor`、`MergeExecutor`、`BufferChunks`

---

## 10.1 两条通道，一个网络

第 8 章讲了消息的三种类型，第 9 章讲了 Actor 如何作为容错单元运行。现在要把这两者连接起来：**消息如何在 Actor 之间流动？**

RisingWave 的数据流动可以浓缩为两个词：**Exchange（交换）** 和 **Dispatch（分发）**。它们分别对应流的输入端和输出端：

```
                   (同一 Actor 内)
  Filter ──► Project ──► HashJoin ──► HashAgg
                                          │
                                   DispatchExecutor ←── 输出端
                                   ┌────┬────┬────┐
                                   │    │    │    │
                              Output  Output Output   ←── 物理通道
                                   │    │    │
                              ┌────┘    │    └────┐
                              │         │         │
                         LocalInput  RemoteInput   │  ←── 输入端
                              │         │         │
                              └────┬────┘         │
                                   │              │
                            MergeExecutor ────────┘
                                   │
                           下一个 Actor 的算子链
```

> **第一性原理思考**：Actor 之间的数据传输和 Actor 内部的数据传输有什么本质区别？Actor 内部是**内存传递**——同一个 Tokio Task 中的函数调用。Actor 之间是**网络传递**——需要序列化、背压控制、屏障对齐。这两者的边界就是 Fragment = Exchange 的边界。RisingWave 将这种差异抽象为 `Input` trait 和 `Output` struct，使得上层算子不需要知道自己是在同 Actor 还是跨 Actor 通信。

---

## 10.2 通道基础设施——permit-based 背压

交换层的底层是一个精心设计的背压通道（`permit.rs`）。

### 10.2.1 为什么不用 bounded channel？

Tokio 提供了 `mpsc::channel(capacity)` 做背压，非常方便。但 RisingWave 没有用它，而是自己基于 `Semaphore` 实现了一套 permit 机制。原因有两层：

**第一层：需要区分 Chunk 和 Barrier 的 permit。** Chunk 按 cardinality（行数）消耗 permit，Barrier 按个数消耗 permit，Watermark 不消耗 permit。如果使用统一的 bounded channel，一个 barrier 卡住就意味着它后面的 chunks 也全部卡住——这在屏障对齐中是灾难性的。

**第二层：Remote Exchange 需要把 permit 还给上游。** 在跨节点传输中，下游 Actor 消费一条消息后，需要向上游 Actor 发送 "add_permits" 信号。`Permits` 结构体（`permit.rs:120-125`）用一个 `Arc<Semaphore>` 支撑了这种跨节点的背压：

```rust
pub struct Permits {
    pub records: Semaphore,   // Chunk 行数许可
    pub barriers: Semaphore,  // Barrier 个数许可
}
```

### 10.2.2 通道创建

```rust
// permit.rs:87-97
pub fn channel_from_config_with_metrics(
    config: &StreamingConfig,
    metrics: ChannelMetrics,
) -> (Sender, Receiver) {
    channel_with_metrics(
        config.developer.exchange_initial_permits,     // Chunk 初始许可数
        config.developer.exchange_batched_permits,     // 批处理保留许可数
        config.developer.exchange_concurrent_barriers,  // 并发 Barrier 数
        metrics,
    )
}
```

这三个配置参数决定了背压的灵敏度：
- `exchange_initial_permits`：通道中能同时存在的最大数据行数（默认值较大，避免不必要的阻塞）
- `exchange_batched_permits`：为批处理预留的许可数，确保大 chunk 不会被卡在中间
- `exchange_concurrent_barriers`：通道中能同时存在的 Barrier 数（通常为 1 或 2）

### 10.2.3 Sender——许可控制的发送端

```rust
// permit.rs:156-165
pub struct Sender {
    tx: mpsc::UnboundedSender<MessageWithPermits>,
    permits: Arc<Permits>,
    max_chunk_permits: usize,   // 单个 chunk 最大许可数
    sender_actor_channel_buffered_bytes: LabelGuardedIntGauge,
}
```

关键在 `send` 方法（`permit.rs:171-203`）：

```rust
pub async fn send(&self, message: Message) -> Result<(), mpsc::error::SendError<Message>> {
    let permits = match &message {
        Message::Chunk(c) => {
            let card = c.cardinality().clamp(1, self.max_chunk_permits);
            Some(permits::Value::Record(card as _))  // 按行数消耗许可
        }
        Message::BarrierBatch(_) => Some(permits::Value::Barrier(1)), // 一个 Barrier 消耗一个许可
        Message::Watermark(_) => None,  // Watermark 不消耗许可
    };
    if let Some(permits) = &permits {
        self.permits.acquire_permits(permits).await?; // 阻塞等待许可
    }
    self.tx.send(MessageWithPermits { message, permits })?;
    Ok(())
}
```

即使内部使用 `mpsc::unbounded_channel()`（不阻塞的），Sender 在 `acquire_permits` 处阻塞，保证了背压。与 bounded channel 的区别在于：这里的阻塞是**区分消息类型的**——Watermark 不受限，Barrier 独立计算，Chunk 按行数限流。

### 10.2.4 Receiver——许可回收

```rust
// permit.rs:207-211
pub struct Receiver {
    rx: mpsc::UnboundedReceiver<MessageWithPermits>,
    permits: Arc<Permits>,
    receiver_actor_channel_buffered_bytes: LabelGuardedIntGauge,
}
```

`recv` 方法（`permit.rs:218-226`）在消费消息后自动回收 permits，使得上游的 `acquire_permits` 放行下一批消息。`recv_raw`（`permit.rs:247-256`）则用于远程交换场景——拿到消息和 permits 后，permits 由 gRPC 层手动归还。

`Receiver::drop` 调用 `permits.close()`，关闭两个 Semaphore。这使得上游所有 `acquire_permits` 调用立即返回错误——优雅地终止整个通道。

---

## 10.3 输入端——LocalInput 与 RemoteInput

### 10.3.1 Input trait

```rust
// input.rs:33-44
pub trait Input: Stream + Send {
    type InputId;
    fn id(&self) -> Self::InputId;
}

pub trait ActorInput = Input<Item = DispatcherMessageStreamItem, InputId = ActorId>;
pub type BoxedActorInput = Pin<Box<dyn ActorInput>>;
```

`ActorInput` 是一个 trait alias（nightly 特性），约束 Item 为 `DispatcherMessageStreamItem`、InputId 为 `ActorId`。这使得 `MergeExecutor` 和 `ReceiverExecutor` 可以用统一的接口处理多上游输入。

### 10.3.2 LocalInput——同节点传输

```rust
// input.rs:64-70
#[pin_project]
pub struct LocalInput {
    inner: LocalInputStreamInner,
    actor_id: ActorId,
}
```

`LocalInput` 的内部是一个 `async_stream`（`input.rs:102-125`）：

```rust
async fn run_inner(mut channel: Receiver, upstream_actor_id: ActorId) {
    while let Some(msg) = channel.recv().await {
        match msg.into_messages() {
            Either::Left(barriers) => {
                for b in barriers { yield b; }
            }
            Either::Right(m) => { yield m; }
        }
    }
    Err(ExchangeChannelClosed::local_input(upstream_actor_id))?
}
```

`LocalInput` 从 `Receiver` 拉取 `DispatcherMessageBatch`，然后把 `BarrierBatch` 展开为逐条的 `DispatcherMessage::Barrier`，逐条 yield。这样做的目的是：下游的 `MergeExecutor` 和 `DynamicReceivers` 只需要处理 `DispatcherMessage`（单条 Barrier），不需要理解 BarrierBatch 的语义。

### 10.3.3 RemoteInput——跨节点 gRPC 传输

`RemoteInput` 的创建（`input.rs:160-198`）分两步：

1. **建立 gRPC 连接**：通过 `client_pool` 获取到上游节点的 `StreamExchangeService` client，调用 `get_stream` 建立双向流
2. **运行接收循环**：`remote_input::run_inner`（`input.rs:238-310`）是一个 async stream：

```rust
async fn run_inner(
    stream: Streaming<GetStreamResponse>,
    permits_tx: mpsc::UnboundedSender<permits::Value>,
    ...
) {
    pin_mut!(stream);
    while let Some(data_res) = stream.next().await {
        let msg_res = DispatcherMessageBatch::from_protobuf(&msg);  // 反序列化
        // 批处理 permits 减少网络往返
        if batched_permits_accumulated >= batched_permits_limit {
            permits_tx.send(permits::Value::Record(permits))?;
        }
        match msg.into_messages() {
            Either::Left(barriers) => { for b in barriers { yield b; } }
            Either::Right(m) => { yield m; }
        }
    }
    Err(ExchangeChannelClosed::remote_input(...))?
}
```

两个关键设计：

1. **Permits 批处理**（`input.rs:269-279`）：不是每收到一条消息就归还 permits，而是累积到 `batched_permits_limit` 再发送。Barrier 的 permits 总是立即归还（因为 Barrier 不频繁，延迟归还会导致对齐等待）。
2. **错误处理**：流结束时（`stream.next()` 返回 `None`），不返回 None 而是返回错误 `ExchangeChannelClosed`。因为 Actor 是通过 Stop Mutation 主动退出的，通道意外关闭说明上游崩溃了。

### 10.3.4 new_input——自动选择本地/远程

```rust
// input.rs:331-367
pub(crate) async fn new_input(
    local_barrier_manager: &LocalBarrierManager,
    metrics, actor_id, fragment_id,
    upstream_actor_info: &ActorInfo,
    upstream_fragment_id, actor_config,
) -> StreamExecutorResult<BoxedActorInput> {
    let upstream_addr = upstream_actor_info.get_host()?.into();
    if is_local_address(local_barrier_manager.env.server_address(), &upstream_addr) {
        // 同节点 → LocalInput
        LocalInput::new(rx, upstream_actor_id).boxed_input()
    } else {
        // 跨节点 → RemoteInput
        RemoteInput::new(local_barrier_manager, upstream_addr, ...).await?.boxed_input()
    }
}
```

这个函数封装了本地/远程的自动判断。上游 Actor 的 `host` 地址来自 Meta 的调度信息。同节点时，通过 `LocalBarrierManager` 注册的本地通道直接传输（零网络开销）；跨节点时，建立 gRPC 双向流。

---

## 10.4 输出端——Output

输出端极其简洁（`output.rs:27-44`）：

```rust
pub struct Output {
    actor_id: ActorId,
    span: await_tree::Span,
    ch: Sender,
}
```

每个 `Output` 对应一条下游通道。`send` 方法（`output.rs:48-54`）只是把消息交给 `Sender::send`，由 permit 机制控制背压。`Output` 不做分发策略、不做 Barrier 改写——这些都在 `DispatchExecutor` 中完成。Output 只有一个职责：**可靠地把一条消息写入一条通道**。

---

## 10.5 DispatchExecutor——消息的岔路口

`DispatchExecutor`（`dispatch.rs:60-63`）是每个 Actor 的输出末端：

```rust
pub struct DispatchExecutor {
    input: Executor,                    // 上游的最后一个算子
    inner: DispatchExecutorInner,       // 分发状态
}
```

### 10.5.1 分发策略

`DispatchExecutor` 的核心在 `dispatch` 方法的分发策略。根据 `DispatcherType`（来自 Fragment Graph 的 `DispatchStrategy`），不同的消息按不同规则分发：

| 消息类型 | Hash 分发 | Broadcast 分发 | Simple 分发 | NoShuffle |
|---------|----------|---------------|------------|-----------|
| Chunk | 按 distribution key hash → 目标 Actor | 全量复制到所有下游 | Round-Robin | 保持分区 |
| Barrier | 全量广播 | 全量广播 | 全量广播 | 全量广播 |
| Watermark | 全量广播 | 全量广播 | 全量广播 | 全量广播 |

**数据按策略分发，控制消息全量广播**——这是流计算中的铁律。其原因在于：Barrier 和 Watermark 是全局信号，每个下游 Actor 都需要收到才能推进自己的计算。

### 10.5.2 输出映射：DispatchOutputMapping

`output_mapping.rs`（从 `dispatch.rs:51-53` 可见）处理 Actor 扩容时的数据重分布：

```
扩容前: Actor10 → Downstream [A, B, C]  (3 个下游)
扩容后: Actor10 → Downstream [A, B, C, D, E, F]  (6 个下游)

DispatchOutputMapping 将旧的下游 Actor 映射到新的 vnode bitmap，
确保每个 vnode 的旧数据被正确地重新分配到新的下游集合。
```

### 10.5.3 两阶段 Barrier 应用

当 `DispatchExecutor` 的 `run` 循环收到 Barrier 时，它需要执行一个两阶段操作（与 `DispatchBarrierBuffer` 协作）：

```
Phase 1: 收到 Barrier
├─ 提取 Mutation（Stop/Update/Add）
├─ Stop → 通知所有下游"这是最后一个 Barrier"
├─ Update → 处理 DispatcherUpdate
│  ├─ 有新 downstream actor → 创建新 Output
│  └─ 有移除 downstream actor → 删除旧 Output
├─ Add → 处理 initial subscribers
└─ 其他 Mutation → 透传给下游

Phase 2: Barrier 改写并分发
├─ Barrier → DispatcherBarrier（擦除 Mutation）
├─ 所有 Output 并发 send(DispatcherBarrier)
└─ 等待所有 Output 确认发送完成
```

`DispatchExecutor` 的 `StreamConsumer` 实现中，`execute` 返回一个只产出 Barrier 的流。这意味着在 Actor 层面（`run_consumer`），Dispatch 之后全是 Barrier——数据 Chunk 已经在 Dispatch 内部处理完了。

---

## 10.6 MergeExecutor——Barrier 对齐与数据合流

`MergeExecutor` 是 `DispatchExecutor` 的镜像。一端分发，一端合流。

### 10.6.1 两种变体

```rust
// merge.rs:32-36
pub(crate) enum MergeExecutorUpstream {
    Singleton(SingletonUpstream),   // 单一上游（Receiver 模式）
    Merge(MergeUpstream),           // 多上游合并
}
```

**Singleton 模式**用于 `Exchange(Single)`：Materialize → HashAgg 之间，下游只有一个上游 Actor，不需要对齐，直接透传。

**Merge 模式**用于 `Exchange(Hash)` 或 `Exchange(Simple)`：多个上游 Actor 的数据经过不同路径到达，需要 Barrier 对齐。

### 10.6.2 execute_inner——合流的主循环

```rust
// merge.rs:280-366
async fn execute_inner(mut self: Box<Self>) {
    let mut barrier_buffer = DispatchBarrierBuffer::new(...);
    loop {
        let msg = barrier_buffer.await_next_message(&mut upstream, &metrics).await?;
        match msg {
            DispatcherMessage::Chunk(chunk) => {
                metrics.actor_in_record_cnt.inc_by(chunk.cardinality() as _);
                Message::Chunk(chunk)   // 直接透传 Chunk
            }
            DispatcherMessage::Watermark(w) => Message::Watermark(w),
            DispatcherMessage::Barrier(barrier) => {
                let (barrier, new_inputs) = barrier_buffer.pop_barrier_with_inputs(barrier).await?;
                // 处理 Update Mutation → 添加/移除上游
                if let Some(update) = barrier.as_update_merge(...) {
                    upstream.update(new_inputs, &removed_upstream_actor_id);
                }
                let msg = Message::Barrier(barrier);
                if is_stop { yield msg; break; }
                msg
            }
        };
        yield msg;
    }
}
```

这个循环中，`DispatchBarrierBuffer` 的 `await_next_message` 做了**屏障预取**——一旦从 `barrier_rx` 收到 Barrier，立即缓存，然后在 `pop_barrier_with_inputs` 阶段与上游流的 Barrier 对齐后一起消费。这确保了 Update Mutation（需要建立/移除上游连接）与数据流的同步。

### 10.6.3 BufferChunks——数据合并优化

```rust
// merge.rs:380-398
pub struct BufferChunks<S: Stream> {
    inner: S,                               // 底层 SelectReceivers
    chunk_builder: StreamChunkBuilder,      // 攒批构建器
    pending_items: VecDeque<S::Item>,       // 待 emit 的消息队列
}
```

`BufferChunks` 包裹在 `SelectReceivers`（`DynamicReceivers<ActorId, ()>`）外层，做一件事：**将来自多个上游的小 Chunk 合并成大 Chunk**。

```
来自上游 A: [Insert x 10行]
来自上游 B: [Insert y 5行]
来自上游 C: [Watermark: col=0, val=100]
      │
      ▼
BufferChunks:
  ① 先收集 A 的 10 行 → chunk_builder
  ② 再收集 B 的 5 行  → chunk_builder (现在 15 行)
  ③ 碰到 Watermark → take chunk_builder → 输出 [Insert 15行的合并Chunk]
                    → 输出 Watermark
```

实现的精妙在于 `pending_items` 队列。当 chunk_builder 满了（达到 chunk_size）时，合并后的 Chunk 入队而不是直接 emit 后面的 Watermark/Barrier。这保证了**Chunk 总是紧挨着被 emit，而不会被中间的消息打断**。

---

## 10.7 Exactly-Once 的传输语义

RisingWave 如何在 Actor 之间保证 Exactly-Once？

### 10.7.1 Barrier 驱动的幂等性

每个 Barrier 携带唯一的 `EpochPair`。下游 Actor 通过 epoch 判断自己是否已经处理过某个 Barrier。如果因为网络故障收到重复的 Barrier（重试），`DynamicReceivers` 的 epoch 校验会直接报错（`align_barrier`），而不是默默重复处理。这意味着 RisingWave 依赖的是**Barrier 级别的精确一次注入**（Meta 保证），然后在 Actor 内依赖**算子状态的幂等更新**。

### 10.7.2 通道关闭 = 错误

回顾 `LocalInput` 和 `RemoteInput` 的循环：

```rust
// 通道意外关闭 → 返回错误，不是 None
Err(ExchangeChannelClosed::local_input(upstream_actor_id))?
```

RisingWave 的流不是靠"通道关闭"来终止的，而是靠"Stop Mutation 的 Barrier"。通道意外关闭一定是故障，必须上报错误。这种设计确保：
- **正常终止**：走 Barrier + Stop Mutation，元数据和状态一致
- **异常终止**：走 error report，系统进入恢复流程

### 10.7.3 Checkpoint 时的一致性保障

当 Barrier 的 kind 是 `Checkpoint` 时，`LocalBarrierWorker::complete_barrier` 会触发：
1. 所有 Actor 将自己的 MemTable 刷到 Shared Buffer
2. Shared Buffer 同步到对象存储（S3）
3. 对象存储的 epoch 版本标记（Hummock Version）

只有这三步全部完成，Meta 才会推进全局 epoch。如果任一步失败，整个 epoch 回退——所有 Actor 从上一个成功的 Checkpoint epoch 重启。

---

## 10.8 端到端消息流示例

以一个跨越三个 Fragment 的查询为例，追踪一条 Chunk 在 Actor 之间的完整旅程：

```
Fragment 0 (Source)              Fragment 1 (HashJoin)          Fragment 2 (MView)
Actor 0                              Actor 1                       Actor 4
┌──────────────────┐            ┌──────────────────────┐     ┌──────────────────┐
│ SourceExecutor   │            │ MergeExecutor (对齐)  │     │ MergeExecutor    │
│   │              │            │   │                  │     │   │              │
│   ▼              │            │   ├─ LocalInput(A0)  │     │   ▼              │
│ ChainExecutor    │            │   ├─ LocalInput(A2)  │     │ HashAggExecutor  │
│   │              │            │   └─ RemoteInput(A3) │     │   │              │
│   ▼              │            │   ▼                  │     │   ▼              │
│ FilterExecutor   │            │ HashJoinExecutor     │     │ Materialize      │
│   │              │            │   │                  │     │   │              │
│   ▼              │            │   ▼                  │     │   ▼              │
│ DispatchExecutor │            │ DispatchExecutor     │     │ DispatchExecutor │
│  ├─ Output → A1  │            │  └─ Output → A4      │     │  └─ (no output)  │
│  └─ Output → A2  │            └──────────────────────┘     └──────────────────┘
└──────────────────┘
  Actor 2
┌──────────────────┐
│ (同 Fragment 0   │
│  的另一个实例)   │
│  ...             │
│ DispatchExecutor │
│  ├─ Output → A1  │
│  └─ Output → A3  │
└──────────────────┘
```

当 Source 产生一条数据 `(region="US", amount=100)` 时：

```
① SourceExecutor → StreamChunk(Insert: (US, 100))
② ChainExecutor → 透传
③ FilterExecutor → 透传（假设条件满足）
④ DispatchExecutor:
   hash(US) % vnode_count → 路由到 Actor 1 的 LocalInput
   → 构造 DispatcherMessageBatch::Chunk → Output.send()

⑤ LocalInput(Actor 1):
   Receiver.recv() → DispatcherMessageBatch → BarChunk → yield

⑥ BufferChunks → SelectReceivers:
   poll_next → 收到 Chunk → chunk_builder 攒批

⑦ MergeExecutor.execute_inner:
   barrier_buffer.await_next_message → 收到 Chunk → 透传
   → Message::Chunk(合并后的 StreamChunk)

⑧ HashJoinExecutor:
   消费 Chunk → 更新 Join State Table → 产出匹配结果

⑨ DispatchExecutor:
   hash(join_key) → 路由到 Actor 4 → Output.send()

⑩ MergeExecutor(Actor 4) → HashAggExecutor → MaterializeExecutor
   → 最终物化到存储
```

这整个过程中，从 Source 到 Materialize，数据只做了**两次网络传输**（Actor 0→1、Actor 1→4），因为同一个 Actor 内的算子链是内存传递。

---

## 10.9 小结

本章追踪了消息在 Actor 之间的完整流动路径：

- **permit-based 通道**：用 `Semaphore` 区分 Chunk（按行数）和 Barrier（按个数）的背压，比 bounded channel 更精细
- **LocalInput / RemoteInput**：自动选择同节点零拷贝或跨节点 gRPC 传输，统一实现 `Input` trait
- **Output**：极简的发送端封装，只负责可靠写入一条通道
- **DispatchExecutor**：按分发策略（Hash/Broadcast/Simple/NoShuffle）将数据定向到下游，Barrier 全量广播
- **MergeExecutor**：通过 `DispatchBarrierBuffer` 两阶段应用 Barrier，`BufferChunks` 合并小 Chunk 优化吞吐
- **Exactly-Once**：Barrier 驱动的幂等性 + 通道关闭即错误 + Checkpoint 三步一致性保障

从下一章开始，我们将逐个深入流式算子的内部实现，先从无状态算子（Source/Chain/Filter/Project/Union）入手。

---

*本章完成。下一章：[第 11 章 · 算子实现精析（上）——无状态算子](../chapters/11-算子实现精析上-无状态算子.md)*
