# 第 9 章 · StreamOperator 与算子链

## 导读

- **一句话**：本章从 StreamOperator 的接口设计出发，展示算子链的完整构建流程和运行时模型。
- **前置知识**：第 5 章 JobGraph 结构，知道什么是 Operator Chain。
- **读完本章你能回答**：
  - StreamOperator 的接口隐含哪些常见需求——从 watermark 到 Record 怎么走
  - OperatorChain 在 Task 中怎么被构建——构建顺序、如何连接上下游算子
  - MailboxProcessor 是怎样的——它怎样实现单线程中多任务协作调度

---

## 9.1 — 设计动机：流算子需要统一的生命周期接口

对比不同计算模型的算子接口：

| 框架 | 接口 | 特征 |
|------|------|------|
| Spark RDD | Iterator-to-Iterator | 无状态、上游完成才调用 |
| MapReduce | Mapper / Reducer | 单次调用、批式 |
| Flink | StreamOperator | 有状态、生命周期管理、Watermark 感知 |

Flink 选择一个完整接口的原因是：流算子需要长期存活，需要接收元素、watermark、checkpoint barrier —— 三次元的事件类型。

---

## 9.2 — StreamOperator 接口

```java
public interface StreamOperator<OUT> {
    void open() throws Exception;
    void close() throws Exception;
    void finish() throws Exception;
    
    // 处理三种不同的事件
    void processElement(StreamRecord<IN> element) throws Exception;
    void processWatermark(Watermark mark) throws Exception;
    void processLatencyMarker(LatencyMarker latencyMarker) throws Exception;
    
    OperatorSnapshotFutures snapshotState(long checkpointId, long timestamp, ...);
    void notifyCheckpointComplete(long checkpointId) throws Exception;
    void notifyCheckpointAborted(long checkpointId) throws Exception;
    
    void setKeyContextElement(StreamRecord<?> record);
    void setCurrentKey(Object key);
    Object getCurrentKey();
}
```

三种事件类型是 Flink 流处理的精华：

- `processElement()` — 收到一条流记录（正常的数据）
- `processWatermark()` — Watermark 推进（时间语义，第 8 章）
- `processLatencyMarker()` — 延迟追踪（Monitor 用）

---

## 9.3 — AbstractStreamOperator 与 TwoInputStreamOperator

- `AbstractStreamOperator<OUT>` 是所有算子的基类——提供通用的状态访问、checkpoint 保存、mailbox 等
- `OneInputStreamOperator<IN, OUT>` — 单输入算子 (map, filter, flatMap)
- `TwoInputStreamOperator<IN1, IN2, OUT>` — 双输入算子 (join, coGroup, keyBy-connect)

多输入通过 `MultipleInputStreamOperator` 处理。所有算子最终都是 StreamTask 通过 `InputProcessor` 驱动的。

---

## 9.4 — OperatorChain：多个算子链在一起跑

### 构建流程

```
Task 部署时 → OperatorChain 构造器：
  1. 从 JobVertex 的算子列表（自底向上）遍历
  2. 第一个算子 → 创建 head operator + 连接到底层的 Output
  3. 后续算子 → 
     a. 创建算子的 Output 和 Input
     b. 连接上一个算子和下一个算子的 Output/Input
  4. 最后一个算子 → 创建 Output 连接到 RecordWriter (网络层)
```

源码入口：`flink-streaming-java/.../runtime/io/OperatorChain.java`

### RecordWriterOutput 和 network 的连接

最后一个算子有一个特殊的 Output：`RecordWriterOutput`。它把 `collect(StreamRecord)` 转成 `RecordWriter.emit()` → ResultPartition → netty 发送。它将整条 chain 的计算结果传送到网络栈。

### 链示例

```
Task:  Source → Map → Filter  (2 个算子链，不同的 JobVertex)
OperatorChain:
  InputGate (上游数据或 Source) 
    → SourceOperator
    → MapOperator
    → FilterOperator 
    → RecordWriterOutput (连接到此 Task 的网络输出)
```

---

## 9.5 — 单线程中多算子的协程模型

一个 Task 对应一个 JVM 线程（`Thread`）。但一个 Task 包含多个算子（一个 OperatorChain），它们都跑在这个单一线程中。

```
StreamTask.run():
  while (running) {
    // 拉下一个可用的 Input
    Input input = inputProcessor.processInput();
    
    if (input is StreamRecord) {
      // 直接调用 chain 上第一个算子的 processElement()
      // 这是一个同步调用链  Source.processElement() → Map.processElement()
      // 即 OperatorChain 内串行处理
    } else if (input is Watermark) {
      // 传播 watermark 给所有链中的算子
    }
  }
```

源码入口：`flink-streaming-java/.../runtime/tasks/StreamTask.java` → `processInput()`

---

## 9.6 — Mailbox：非阻塞操作让算子更 cooperatively

有的算子需要做"暂时不能继续，需要等外部结果"的操作——例如异步 IO 等待远端 RPC 响应。直接阻塞线程会让整个 Task 都停滞。Mailbox 模型允许算子**暂停当前 action、把控制流还给 StreamTask 的 run 循环**——这样 Task 线程可以在 mailbox 中循环接收上游数据，而不用阻塞等待异步结果。

```
StreamTask:
  while (running) {
    mailboxProcessor.runMailboxLoop();
    // 处理 mailbox 中所有有新状态的动作
    // 包括 processInput 和 异步回调后续处理
  }
```

源码入口：`flink-streaming-java/.../runtime/tasks/StreamTask.java` → `MailboxProcessor`

Mailbox 中的动作执行顺序由 mailbox 的队列保证——这是一个**用户态的合作式调度器**（对比 OS 的抢占式调度），避免多余上下文切换。

---

## 9.7 — 横向对比

### vs Spark WholeStageCodeGen

Spark 中的 WholeStageCodeGen 将多个算子融合成一个函数——用编译时的方式把这些算子"inline"。Flink 的 OperatorChain 是运行时方式的——**认识算子的过程中动态决定哪个算子进 chain、哪个 chuángu 该用哪种 Output/Input 连接**。Spark 的是编译期替换（用了 Janino 代码），Flink 的是运行期动态构造。

### vs StarRocks Pipeline Engine

StarRocks 2.5 引入 Pipeline Execution Engine——类似 Flink 的 OperatorChain：多个算子在一个 Pipeline Worker 线程中跑。关键差异是 StarRocks pipeline 是 MPP 的（一个 fragment 内由多个 pipeline driver 并发处理），而 Flink chain 是单线程内串行处理。

---

## 调优与实战陷阱

### Chain Too Long → GC 和 Buffer 耗尽

同一个 chain 太长意味着数据泄漏积攒多。如果链中一个算子缓存了很多数据（例如 WindowOperator State 中有大量未触发的窗口）——它影响 chain 中所有算子的 GC（因为它们在同一进程中共享 JVM GC）。解法：**在重量级窗口算子处 `disableChaining()`**，让其占用独立的 Slot。

### 链断裂导致反压变化

在一个链里，所有算子共享相同的 LocalBufferPool（第 11 章）。如果链路被 N 个 shuffle 打断——会有 N 个独立的 LocalBufferPool 要维护和管理——增加内存复杂性。

---

## 本章要点回顾

1. StreamOperator 三分事件：Record（数据处理）、Watermark（时间推进）、LatencyMarker（延迟追踪）。
2. OperatorChain 在 Task 部署时构建——自底向上连接算子的 Input/Output，最后一个算子连接到网络输出。
3. 单线程内多个算子通过链的原始方法调用串联——无多余内存拷贝，最高效。
4. Mailbox 行为用户态合作调度——让异步算子在等待时不阻塞 Task 线程。

## 源码导航

- StreamOperator 接口：`flink-streaming-java/.../api/operators/StreamOperator.java`
- AbstractStreamOperator：`flink-streaming-java/.../api/operators/AbstractStreamOperator.java`
- OperatorChain：`flink-streaming-java/.../runtime/io/OperatorChain.java`
- StreamTask.processInput()：`flink-streaming-java/.../runtime/tasks/StreamTask.java`
- MailboxProcessor：`flink-streaming-java/.../runtime/tasks/mailbox/MailboxProcessor.java`
