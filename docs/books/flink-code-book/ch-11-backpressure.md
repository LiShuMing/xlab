# 第 11 章 · 反压机制

## 导读

- **一句话**：本章回答"当下游消费速度跟不上上游生产速度时，Flink 怎样让上游慢下来——从 Buffer Pool 到 TCP 流控的完整反压链路"。
- **前置知识**：第 4 章 NetworkBufferPool、第 16 章网络栈概述。
- **读完本章你能回答**：
  - Flink 的反压机制和 TCP 流控有什么本质相似和不同
  - Credit-based Flow Control 的工作流程
  - 反压如何在 Web UI 中被可视化
  - 什么是"反压传播链路"——怎样追踪源头

---

## 11.1 — 设计动机：流系统天生需要反压

### 为什么有反压

批处理中，算子输出最终会被下游处理。如果下游慢，结果只是总体时间变长——没有"当下"的概念。**流处理中，数据源源不断到达。如果下游慢、上游继续产，数据就在内存中堆积 → OOM**。

解决方案只有一个：**当下游慢时，上游必须自动降速**。这就是反压。

### 两个流派

| 流派 | 代表 | 方式 |
|------|------|------|
| **TCP-based backpressure** | Spark Streaming | 遇到阻塞时 TCP receive buffer 满 → TCP sliding window 对付远端 |
| **Credit-based flow control** | Flink | 在应用层实现信用机制——下游给上游"我能接受 N 个 buffer"的信用 |

为什么 Flink 不给 TCP？因为 TCP 的反压是**对通道的**——一条 TCP 连接满了，所有在这条连接上跑的数据都被卡住。但 Flink 每 Task 间有独立的 Subpartition，如果只有部分 Subpartition 阻塞而继续收其他 Subpartition——TCP 做不到这个粒度割裂。Credit-based 流控可以做到 **per-Subpartition 反压**。

---

## 11.2 — Credit-based Flow Control

### 信用模型

```
下游 InputGate 对每个上游的 Subpartition 有一个 credit（信用额度）
credit = 下游"能接受"的 Buffer 数量

上游 ResultSubpartition 被给予 N 个 credit:
  → 可发送 N 个 Buffer
  → 发出 1 个 → credit -= 1
  → 不可以发送 < 0 credit
```

### 握手流程

```
消费端 (InputChannel):
1. 拿到 Buffer 后 → 返回到 LocalBufferPool
2. 检是否还有至少 1 个 Buffer 空闲
3. 有 → 向对应生产端发 "add credit" 信号
4. 无 → 不发信号 → 生产端收到 credit = 0

生产端 (ResultSubpartition):
1. 积累 Buffer 到本地发送队列
2. 检查 credit:
   - credit > 0 → 发送最前的 N 个 Buffer
   - credit == 0 → 不能发送 → 队列积压
   - RecordWriter 试图分配新的 Buffer 
     → LocalBufferPool 会尝试从全局池请求 
     → 全局池也可能耗尽 
     → 此时 RecordWriter.emit() 阻塞等待 Buffer
     → 算子线程停止
     → 反压完成
```

**关键**：反压最终的效果是 **RecordWriter 阻塞**——算子线程被卡在 `output.collect(record)` 里。

源码入口：`flink-runtime/.../io/network/netty/CreditBasedPartitionRequestClientHandler.java`

---

## 11.3 — 两级 Buffer Pool 在反压中的角色

回顾第 4 章的两级池：

```
NetworkBufferPool (全局)
  └── LocalBufferPool (每个 Task)
      └── ResultSubpartition (每个子输出通道)
```

当反压发生时，效应反向传播：

```
下游慢
  → 下游 Buffer 回收缓慢
  → 下游 InputChannel 没有空闲 Buffer → 不发 credit
  → 上游收到 credit == 0
  → 上游 ResultSubpartition 的 Buffer 不能发网络 → 队列积压
  → 上游 LocalBufferPool 从全局池请求更多 Buffer 暂存
    → 用光自己 LocalPool 的允许数量后 → 请求失败
    → 上游 RecordWriter.emit() 阻塞
    → 上游算子线程停止
    → 继续向上游传播
```

整个反压是可观察的——Web UI 会显示每个 Task 的 "Backpressured" 状态（绿色/橙色/红色）。

---

## 11.4 — Back Pressure Monitor

Flink 采样每个 Task 的线程调用栈：

```
1. 定期 (每隔几百 ms) 获取每个 Task 线程的 Stack Trace
2. 如果线程卡在:
   - LocalBufferPool.requestBuffer() 
   - RecordWriter.emit()
   - CreditBasedSender.readyToSend()
   → 该 Task 被标记为 "Backpressured"
3. 比率 = (backpressured samples) / (total samples)
   - < 0.10 → OK (low)
   - 0.10~0.50 → LOW
   - 0.50~1.00 → HIGH
```

这个信息在 Web UI 的每个算子 Node 上都是一个环形图——红色表示高反压。

---

## 11.5 — 反压的常见源头

| 源头 | 表现 | 解法 |
|------|------|------|
| **Sink 慢** | 反压从 sink 向上蔓延 | 增加 Sink 并行度或优化写入 |
| **CPU 热点** | 某个算子一直消耗 100% CPU | 膨胀并行度、禁用 chain 让相关算子在多核上跑 |
| **Network Buffer 不够** | 非 CPU-bound 但反压高 | 增加 `taskmanager.memory.network.max` |
| **GC 抖动** | 反压随 GC 周期性起伏 | 移到 off-heap，或者 State Backend 调整 |
| **Data Skew** | 某个 partition 流量特别大 | Key 设正确、用 `.rebalance()` 补救 |

---

## 11.6 — 横向对比

### vs TCP Buffer-based 反压

Spark (非结构化流) 依赖 TCP send/receive buffer 反压——简单的"Tube clogging"。但跨 task 要用到多 TCP 连接时，一条 cheng了只能卡住对应通道，不够精确也没有抢占信用控制。

Flink 的在信用模型上额外做了两个跟 TCP 不同的事：
- 可断链（关闭 Subpartition）– 下游可以通知上游 "不再需要这个 subpartition 的数据"
- 优先级数据——Watermark 和 Checkpoint Barrier 优先级高于一般数据，可以拿 credit 例外通行

### vs StarRocks

StarRocks Pipeline 通过内存不够 → `BlockingQueue` 满 → 下游 pipeline worker 被阻塞 → 反压向上传递。机制更简单但没有 Credit 的精细控制。

---

## 调优与实战陷阱

### 反压循环诊断脚本

```bash
# 最快的方法：看 Web UI BackPressure 选项卡
# 或者用 REST API:
curl http://<jobmanager>:8081/jobs/<job-id>/vertices/<vertex-id>/backpressure
```

### 反压但 CPU 很低 → 几乎就是 Network Buffer 不够

症状：反压颜色是橙色/红的，但 JMX 中 operator 的 Avg CPU Load < 0.5 → 此时加上 `taskmanager.memory.network.max`。

### Credit 的初始值

浮想：下游默认给上游多少信用级别？Flink 默认从 2 个 Buffer 开始——如果 pipeline 延迟感、提高可增加 `taskmanager.network.credit-based-flow-control.buffers-per-channel` 参数。但要谨慎——设太大反压不精准，下游 Buffer 用尽时有延迟。

---

## 本章要点回顾

1. Flink 用 Credit-based Flow Control——下游给上游"能接受 N 个 buffer"的信用。
2. 反压从下游向上游缓存波浪式传播——最终使 RecordWriter 阻塞，算子线程降速。
3. Web UI 通过采样 Task 线程调用栈来可视化反压。
4. CPU 热点、GC 抖动、Sink 慢、Data Skew 是反压最常见的四个根源。

## 源码导航

- Credit-based 发送处理：`flink-runtime/.../io/network/netty/CreditBasedPartitionRequestClientHandler.java`
- RecordWriter 阻塞：`flink-runtime/.../io/network/api/writer/RecordWriter.java`
- LocalBufferPool：`flink-runtime/.../io/network/buffer/LocalBufferPool.java`
- BackPressure 采样：`flink-runtime/.../taskmanager/Task.java` → back pressure sample
- REST API for backpressure：`flink-runtime/.../rest/handler/job/JobVertexBackPressureHandler.java`
