# 第 10 章 · StreamTask 执行引擎

## 导读

- **一句话**：本章深入到 StreamTask 的内部循环，理解 TaskManager 上的 Task 线程是怎样被驱动、数据怎样流通、Mailbox 如何保障不阻塞的。
- **前置知识**：第 9 章 OperatorChain、第 1 章 TaskDeploymentDescriptor 概念。
- **读完本章你能回答**：
  - StreamTask.start() 的内部循环到底做了什么
  - InputProcessor 如何把多个上游输入融合成单一的数据流
  - 三种 StreamTask（源、单输入、双输入）的差异
  - RecordWriter 和网络栈的连接点在哪

---

## 10.1 — 设计动机：Task 是 Flink 最底层的执行单元

在前面的章节中，我们的数据 DAG 一步步从 `StreamGraph → JobGraph → ExecutionGraph`。现在到了最终的物理执行——**一个 ExecutionVertex → 一个 Task**。

```
ExecutionGraph              ← JobMaster 在 JVM 上持有的
  ExecutionVertex#3
    Execution#1 → Task     ← TaskManager 上的 Task 实例
    Execution#2 → Task (retry)
```

Task 的代码来自 `TaskDeploymentDescriptor` 的序列化信息——当 TaskManager 收到 TDD，它反序列化出 `JobInformation + TaskInformation`，构造 `Task` 对象。

源码入口：`flink-runtime/.../taskexecutor/TaskExecutor.java` → `submitTask()`

---

## 10.2 — StreamTask 的 subtypes（三种核心 Task）

```
StreamTask
├── SourceStreamTask        ← Source 算子
│   └── 无 InputGate，直接读数据源 (Kafka/Kinesis/File)
├── OneInputStreamTask      ← 单输入算子（map, filter, flatMap）
│   └── 1 个 InputGate + 1 个 ResultPartition
├── TwoInputStreamTask      ← 双输入算子（join, coGroup）
│   └── 2 个 InputGate + 1 个 ResultPartition
└── MultipleInputStreamTask ← 多输入算子（n 个）
```

每个 `StreamTask` 在构造函数中创建自己的 `InputProcessor`：

```java
// OneInputStreamTask
class OneInputStreamTask {
    StreamOneInputProcessor inputProcessor;  // single input gate
}

// TwoInputStreamTask  
class TwoInputStreamTask {
    StreamTwoInputProcessor inputProcessor;  // two input gates
}
```

源码入口：
- `flink-streaming-java/.../runtime/tasks/OneInputStreamTask.java`
- `flink-streaming-java/.../runtime/tasks/TwoInputStreamTask.java`
- `flink-streaming-java/.../runtime/tasks/SourceStreamTask.java`

---

## 10.3 — StreamTask 的生命周期

从 `Task.run()` 看完整的生命周期：

```java
// flink-runtime/.../taskmanager/Task.java
public void run() {
    // 1. 反序列化 StreamTask 和 OperatorChain（从 TDD）
    // 2. StreamTask.invoke()
}

// flink-streaming-java/.../runtime/tasks/StreamTask.java
public void invoke() {
    // 1. beforeInvoke() → 初始化 StateBackend、Register Metrics
    // 2. operatorChain.openOperators() → 调用每个算子的 open()
    // 3. runMailboxLoop() → 进入事件循环
    //      → 整个 Task 95% 的时间都在这个循环里
    // 4. afterInvoke() → 关闭算子、清理状态
}
```

### 主循环剖析

```java
void runMailboxLoop() {
    while (isRunning()) {
        mailboxProcessor.yield();
        
        // 关键：检查是否有 available input
        // 若有 → 处理并推进数据流
        // 若无 → 检查 mailbox action
        // 两者皆无 → 阻塞等待更多数据或 mailbox action
    }
}
```

---

## 10.4 — InputProcessor：怎样混入一个流

### 单一输入

```java
// OneInputStreamTask 的 processInput:
Input input = inputProcessor.processInput();

if (input instanceof StreamRecord) {
    // 直接喂给 OperatorChain 的第一个算子
    headOperator.processElement((StreamRecord) input);
} else if (input instanceof Watermark) {
    // 更新当前 watermark 并传播给所有算子
    headOperator.processWatermark((Watermark) input);
} else if (input instanceof CheckpointBarrier) {
    // Checkpoint 事件——触发 snapshotState()
}
```

源码入口：`flink-streaming-java/.../runtime/io/StreamOneInputProcessor.java`

### 双输入混合

`TwoInputStreamTask` 更有趣——它有两个上游输入源，需要"交错"读取：

```java
// StreamTwoInputProcessor:
// 选一个能读的 input channel
// 读数据 → 标记是从 input1 还是 input2 来的
// 不同的流发给 TwoInputStreamOperator.processElement1() 或 processElement2()
```

Watermark 的合并也属于同一 Process：分别拿到两个输入的 watermark，取 min，输出给算子。

---

## 10.5 — RecordWriter：Task 与网络栈的桥梁

### 角色

`RecordWriter` 在 OperatorChain 尾部——当算子调用 `output.collect(StreamRecord)`，实际调用的就是 `RecordWriter.emit()`。这个关键方法完成：

1. **序列化 record**（通过 `SpanningRecordSerializer` 将数据写入 MemorySegment）
2. **选择目标 partition**：根据分区策略和 OutputChannel 的数量，决定这条 record 该写入哪个 ResultSubpartition
3. **写入 Buffer**：将序列化后的字节拷贝到 target partition 的 Buffer 队列
4. **Buffer 满了** → 发送通知给 Netty 发送

```java
// flink-runtime/.../io/network/api/writer/RecordWriter.java
public void emit(Record record, int targetPartition) {
    // 找到对应 targetPartition 的 ResultSubpartition
    // 将序列化后的数据写入 buffer
    // 如果 buffer 满了 → flush 触发网络发送
}
```

源码入口：`flink-runtime/.../io/network/api/writer/RecordWriter.java`

---

## 10.6 — 集成：从 RecordWriter 到 Netty

```
OperatorChain
  ↓ RecordWriter.emit(record)
  ↓ 选择一个 ResultSubpartition
  ↓ ResultSubpartitionView 产生 BufferReceived 通知
  ↓ Netty 的 ChannelOutboundHandler 消费 Buffer 事件
  ↓ 网络写到远端
```

Buffer 的生命周期（第 16 章展开）就是从 RecordWriter 开始——一个 `MemorySegment` 被用作"写缓冲"，满了以后被 posting 到 network 的 netty channel，下游收到后归还回池。

---

## 10.7 — 横向对比

### vs Spark Task

Spark 的 `Task.run()` 是 **一次性执行**的：迭代所有数据、处理、输出到 shuffle writer --> 完成 → 通知 Driver。不存在消息循环。

Flink 的 `StreamTask.runMailboxLoop()` 是**长期循环**：Task 线程生命周期与 Job 绑定。类似 Erlang Actor 或 Go goroutine 的 run loop。这是流对批的根本差异。

### vs StarRocks Pipeline Driver

StarRocks Pipeline Driver 也是永久运行的消息循环——但这由 C++ 的 bthread 调度，有 M:N 映射（M 个 pipeline driver 映射到 N 个 OS 线程）。Flink 是 1 Task 对应 1 Thread，没有 bthread 的 M:N 调度。

---

## 调优与实战陷阱

### 长耗时算子阻塞整个 Mailbox

如果算子占用 CPU 时间太长（比如算一个极复杂的 ML 模型预测），mailbox 循环始终耗在 processElement() 里 —— 没有机会处理 watermark、process check barrier → checkpoint 超时。

解法：将长时间运算交给异步线程池，主 mailbox 返回 mailbox action 的信号量。

### 内存泄漏：算子链中 del 不完的数据

算子链越长，尾端和起始算子的 Stack Context 越.advance——中间任意位置如果缓存了大量数据（collection 对象），GC 无法扫描——超过单个 Task 的内存后导致 OOM。使用 `HeapMonitor` 或 `GC Log` 应用排查链内 GC 压力占最高的算子。

---

## 本章要点回顾

1. StreamTask = TaskManager 上的基本执行单元——源码是 Task 对象框架 + 被序列化的 StreamTask 实现。
2. 三种 Task 类型由 input gate 的数量区分——源（无）、单输入（1）、双输入（2）。
3. `runMailboxLoop()` 是核心事件循环——处理三种事件：Record/Watermark/CheckpointBarrier。
4. `RecordWriter` 将算子输出序列化到 MemorySegment 并发布给 Netty 网络层。

## 源码导航

- Task 框架：`flink-runtime/.../taskmanager/Task.java`
- StreamTask 生命周期：`flink-streaming-java/.../runtime/tasks/StreamTask.java`
- SourceStreamTask：`flink-streaming-java/.../runtime/tasks/SourceStreamTask.java`
- One/TwoInputStreamTask：`flink-streaming-java/.../runtime/tasks/OneInputStreamTask.java`, `TwoInputStreamTask.java`
- StreamInputProcessor：`flink-streaming-java/.../runtime/io/StreamOneInputProcessor.java`, `StreamTwoInputProcessor.java`
- RecordWriter：`flink-runtime/.../io/network/api/writer/RecordWriter.java`
