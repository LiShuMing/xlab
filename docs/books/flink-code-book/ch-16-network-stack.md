# 第 16 章 · 网络栈分层架构

## 导读

- **一句话**：本章从 RecordWriter 出发，一层层剥开 Flink 网络栈——从算子产出到对方算子接收的全链路。
- **前置知识**：第 10 章 StreamTask / RecordWriter、第 11 章反压。
- **读完本章你能回答**：
  - `ResultPartition` 和 `ResultSubpartition` 的规划关系
  - `InputGate` 和 `InputChannel` 的消费模型
  - 记录怎样被分割发送、在没集 End 时如何拼接
  - Flink 的 Netty Protocol 内部是怎样对 Header + Body 打包的

---

## 16.1 — 网络栈全景

```
生产端 Task:
  OperatorChain → RecordWriter.emit(record)
    → 选择 ResultSubpartition (目标分区)
    → SpanningRecordSerializer 序列化到 MemorySegment
    → BufferBuilder 装箱成 Buffer
    → ResultSubpartition 添加到发送队列
    → Credit-based Flow Control 检查:
      - 有 credit → BufferConsumer → netty flush
      - 无 credit → 保留在队列，阻塞 RecordWriter

网络传输: Netty TCP

消费端 Task:
  Network → InputChannel (netty handler) 
    → 接收 Buffer → 放入 InputGate
    → BufferListener 通知 StreamTask 有数据可读
    → RecordDeserializer 反序列化 → 供算子 processElement()
```

源码模块：`flink-runtime/.../io/network/`

---

## 16.2 — 生产端：ResultPartition + ResultSubpartition

### ResultPartition 源码

`ResultPartition` 是生产端的核心抽象（`flink-runtime/.../io/network/partition/ResultPartition.java:78`）：

```java
public abstract class ResultPartition implements ResultPartitionWriter {
    // 生命周期三阶段：Produce → Consume → Release
    protected final ResultPartitionType partitionType;   // PIPELINED / BLOCKING / PIPELINED_BOUNDED
    protected final ResultSubpartition[] subpartitions;  // 子分区数组
    private BufferPool bufferPool;                       // 本 Partition 的 Buffer 池
    @Nullable private BufferCompressor bufferCompressor; // 可选的 Buffer 压缩器
    private final AtomicBoolean isReleased;              // 释放标记
}
```

**三阶段生命周期**：
1. **Produce**：Task 运行，通过 `ResultPartitionWriter` 写数据到 subpartitions
2. **Consume**：下游 Task 请求 subpartition，消费已写入的 Buffer
3. **Release**：所有消费者释放后，释放 Buffer 和内存

### 结构

```
一个 JobVertex 产出一个 IntermediateResult
  → IntermediateResult 有 N 个 IntermediateResultPartition (一个 per producer subtask)
  → 每个 IntermediateResultPartition = 一个 ResultPartition

ResultPartition
  ├── partitionType: PIPELINED / BLOCKING / HYBRID
  └── subpartitions: ResultSubpartition[]
      └── 每个往下游每个 consumer 一个 (总 C 个，C=下游 parallel 度)
```

`PIPELINED`：数据持续发送（流默认）
`BLOCKING`：全部写完才可消费（批默认）
`HYBRID`：先内存、满了溢写盘（批优化）

源码入口：
- `flink-runtime/.../io/network/partition/ResultPartition.java`
- `flink-runtime/.../io/network/partition/ResultSubpartition.java`

### ResultSubpartition 的内部 Buffer 队列

每个 `ResultSubpartition` 内部是两个队列：
- `buffers`：等待下游 credit 的 Buffer 队列
- `flush`：累积（等待下一个 flush 事件）的 Buffer

当 RecordWriter 刷新一条 record 时，对应 OutputChannel 可能等了多个 record 才一起 flush——减少 netty 写入次数。

---

## 16.3 — 消费端：InputGate + InputChannel

### 结构

```
一个 ExecutionVertex 消费上游 K 个 partition
  → 1 个 InputGate (收集所有上游)
  → K 个 InputChannel (每个上游 partition 一个)
    └── RemoteInputChannel (跨网络)
    └── LocalInputChannel (同 TM，直接内存引用，0 拷贝)
```

`LocalInputChannel` 直接在同一个 TaskManager 进程内从上游 `ResultPartition` 读 Buffer，不经过网络——**同存访问，零拷贝**。

`RemoteInputChannel` 需要通过 Netty 交换——Credit 流控在此处生效。

源码入口：
- `flink-runtime/.../io/network/partition/consumer/InputGate.java`
- `flink-runtime/.../io/network/partition/consumer/InputChannel.java`

---

## 16.4 — SpanningRecordSerializer：记录跨 Buffer

### 问题与解决

一条 record 可能大于单个 MemorySegment 的大小（32KB）。`SpanningRecordSerializer` 可以将一条 record 分割到多个 Buffer 中：

```
序列化格式:
  Buffer-1: [header: 1 span MSB=1] [record part 0]
  Buffer-2: [header: 0 span MSB=0] [record part 1]
  ...
  Buffer-N: [header: -1 span MSB=1] [record part N]
```

源码入口：`flink-runtime/.../io/network/api/serialization/SpanningRecordSerializer.java`

消费端 `SpillingAdaptiveSpanningRecordDeserializer` 负责重组多 Buffer 的 record——如果中间 Buffer 丢失，丢弃整条 record。

---

## 16.5 — Netty Protocol

### Header + Body 结构

Flink 的 Netty 帧协议：

```
┌──────────────────────────────────────┐
│  Buffer Length (4 bytes)              │
├──────────────────────────────────────┤
│  Buffer Header:                       │
│  - isEvent (1 byte)                   │  0=数据, 1=事件(Checkpoint)
│  - channelId (2 bytes)                │  Subpartition 标识
│  - ...                                │
├──────────────────────────────────────┤
│  Buffer Body (record data)           │
└──────────────────────────────────────┘
```

源码：`flink-runtime/.../io/network/netty/NettyMessage.java`

---

## 16.6 — 完整数据流动胞图

```
[上游] OperatorChain.processElement()
  → output.collect(record)
  → RecordWriter.emit(record, channelSelector)
  → Serializer.serialize(record, targetBuffer)
  → Buffer 满或flush → ResultSubpartition.add(Buffer)
  → Netty Channel 处理 → TCP write to downstream
  
  ... 网络传输 (TCP) ...

[下游] Netty Channel read
  → partitionRequestClientHandler.channelRead(buffer)
  → InputChannel.receiveBuffer(buffer)
  → InputGate 收集满所有 channel 的 1 buffer ready
  → InputProcessor.processInput()
  → OperatorChain.processElement(deserialized record)
```

---

## 16.7 — 横向对比

### vs Spark Netty Shuffle

Spark 也用了 Netty——但有额外的 MapOutputTracker（在 Driver 中注册 map status location）和 ShuffleClient。Flink 没有 MapOutputTracker——因为上下 Task 是长时间在线且动态发现 partition 的（通过固定的 DAG 连接）。

### vs StarRocks

StarRocks 用 BRPC 做 Fragment 间数据传输——基本上是 `serialize → protobuf → BRPC channel`。Flink Netty Protocol 更原始——直接 MemorySegment 写 header，无 Protobuf。

---

## 本章要点回顾

1. 网络栈 = RecordWriter → ResultPartition/Subpartition → Netty → InputChannel/InputGate → RecordDeserializer。
2. 同 TM 上任务走 LocalInputChannel，零拷贝。
3. SpanningRecordSerializer 支持跨 Buffer 的大记录分割/重组。
4. Netty Protocol 自简——没有 Protobuf，二进制 Directive。

## 源码导航

- ResultPartition：`flink-runtime/.../io/network/partition/ResultPartition.java`
- InputGate/InputChannel：`flink-runtime/.../io/network/partition/consumer/`
- SpanningRecordSerializer：`flink-runtime/.../io/network/api/serialization/`
- Netty Protocol：`flink-runtime/.../io/network/netty/NettyMessage.java`
- LocalInputChannel：`flink-runtime/.../io/network/partition/consumer/LocalInputChannel.java`
