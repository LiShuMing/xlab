# 第 8 章 · Watermark、Event Time 与窗口计算

## 导读

- **一句话**：本章回答"在有乱序的数据流中，Flink 怎么知道'12:00-12:05 这个窗口的数据都到齐了'，以及窗口的计算何时触发"。
- **前置知识**：事件时间 vs 处理时间的区别、基本的窗口概念。
- **读完本章你能回答**：
  - Watermark 是什么？它怎么生成、怎么在 DAG 中传播？
  - 乱序数据到达时，Flink 怎么处理 late events？
  - Tumbling/Sliding/Session 三种窗口的实现本质区别是什么？
  - `AllowedLateness` 和 `SideOutput` 的作用

---

## 8.1 — 设计动机：从 Google Dataflow Model 说起

Flink 的时间语义直接源自 Google Dataflow Model（2015 年那篇论文）。Dataflow 提出了三个核心概念：

1. **Event Time**：事件实际发生的时间（数据本身携带的时间戳）
2. **Windowing**：将无限流切成有限块进行计算
3. **Trigger + Watermark**：决定窗口何时可计算

Flink 的独特之处：**Watermark 是纯运行时概念——它从 Source 注入，沿 DAG 边传播，在任意算子处可达**。这跟结构化数据不同——传统批处理可以把所有数据按时间排出后精确切割，流中无法"排好"——只有 watermark 能给我们一个**不确定但合理的"数据完整性"指标**。

---

## 8.2 — Watermark 的定义与生成

### 定义

> **Watermark(t)** 表示：**"所有事件时间 ≤ t 的事件，都已经到达了这个点（或以后不会再来更早的事件了）"**。

在 Flink 源码中，`Watermark` 本质上就是一个 `long timestamp`，没有别的字段：

```java
// flink-core/.../streaming/api/watermark/Watermark.java
public final class Watermark extends StreamElement {
    private final long timestamp;
}
```

Watermark 和 StreamRecord 一样继承自 `StreamElement`——在运行时管道中，Watermark 和数据记录混在一起流动，算子通过类型判断来区分处理。

### WatermarkGenerator

Source 端通过 `WatermarkGenerator` 生成 watermark：

```java
public interface WatermarkGenerator<T> {
    void onEvent(T event, long eventTimestamp, WatermarkOutput output);
    void onPeriodicEmit(WatermarkOutput output);
}
```

两种策略：

**Periodic（定期）**：
- `onPeriodicEmit()` 定期被调用（频率 = `pipeline.auto-watermark-interval`，默认 200ms）
- 典型实现：`BoundedOutOfOrdernessGenerator` —— 记录当前见到的最大 eventTime，发射 `maxTime - interval` 的 watermark

**Punctuated（每个事件驱动）**：
- `onEvent()` 中根据事件内容直接发射 watermark
- 适合"每个事件携带完整信息"的场景，例如流中带有 "timestamp of the next event" 的信号

---

## 8.3 — Watermark 的广播与传播

### 广播语义

Watermark 沿数据边广播——当算子有多个上游输入时，它看到的 `currentWatermark` 是 **所有上游中最小的那个**：

```
         上游-0 [WM(12:05)]
operator 上游-1 [WM(12:03)]  → 当前 WM = min(12:05, 12:03) = 12:03
         上游-2 [WM(12:07)]
```

源码入口：`flink-streaming-java/.../runtime/io/StreamTwoInputProcessor` 中的 `currentWatermark` 计算

### 广播的问题：Idle Source

如果多源中有一个是 "idle" 的（一直没有数据），它永不会发出 watermark → 阻塞全局。解决方案：**标记该分区为 idle** (`WatermarkStrategy.withIdleness(Duration)`)。超过指定时间没数据，该分区被排除在 min() 计算之外，不阻塞全局 Watermark 前进。

---

## 8.4 — 窗口计算

Flink 中的窗口由三要素定义：
- **WindowAssigner**：决定每条记录去哪个窗口
- **Trigger**：决定窗口什么触发
- **WindowFunction**：处理对窗口内所有记录的计算

### Tumbling Window

```java
public class TumblingEventTimeWindows extends WindowAssigner<...> {
    public Collection<TimeWindow> assignWindows(Object element, long timestamp, ...) {
        long start = timestamp - (timestamp % size);
        return Collections.singletonList(new TimeWindow(start, start + size));
    }
}
```

每条记录只映射到**一个窗口**——分配给 `start = timestamp - (timestamp % size)`。

### Sliding Window

每条记录映射到**多个窗口**——由 `window stagger` 决定有多少窗口重叠。结果：同样一条记录参与多个窗口的计算。需要用 `WindowBuffer` 缓存对应窗口的状态。

### Session Window

没有固定窗口边界——根据 event time gap 动态决定窗口合并。这需要 `MergingWindowAssigner` + `MergingWindowSet` 来实现动态合窗/分裂。

源码入口：
- `flink-runtime/.../streaming/runtime/operators/windowing/WindowOperator.java`（实现 `OneInputStreamOperator` + `Triggerable`）

WindowOperator 的核心字段（`WindowOperator.java:120-160`）：

```java
public class WindowOperator<K, IN, ACC, OUT, W extends Window>
        extends AbstractUdfStreamOperator<OUT, InternalWindowFunction<ACC, OUT, K, W>>
        implements OneInputStreamOperator<IN, OUT>, Triggerable<K, W> {

    protected final WindowAssigner<? super IN, W> windowAssigner;  // 窗口分配器
    protected final Trigger<? super IN, ? super W> trigger;        // 触发器
    protected final StateDescriptor<? extends AppendingState<IN, ACC>> windowStateDescriptor; // 窗口状态
    protected final KeySelector<IN, K> keySelector;               // Key 选择器
    private final OutputTag<IN> lateDataOutputTag;                // 晚数据输出

    private transient InternalTimerService<W> internalTimerService;  // 定时器服务
    private transient KeyedStateBackend<K> keyedStateBackend;        // Keyed State 后端
    private transient WindowContext windowContext;                    // 窗口上下文
}
```

WindowOperator 同时实现了 `Triggerable`——当 event time timer 触发时（watermark 超过 timer 注册时间），`onEventTime()` 回调被调用，驱动窗口计算。

---

## 8.5 — Trigger：窗口计算何时触发

`Trigger` 决定窗口在什么条件下触发计算并释放结果：

```java
public abstract class Trigger<T, W extends Window> {
    public abstract TriggerResult onElement(T element, long timestamp, W window, ...);
    public abstract TriggerResult onEventTime(long time, W window, ...);
    public abstract TriggerResult onProcessingTime(long time, W window, ...);
    
    public enum TriggerResult {
        CONTINUE,   // 不触发
        FIRE,       // 触发计算
        PURGE,      // 清理窗口
        FIRE_AND_PURGE  // 触发计算并清理
    }
}
```

最常用：`EventTimeTrigger.onEventTime()` — 当 Watermark > window.maxTimestamp 时返回 `FIRE`。

---

## 8.6 — AllowedLateness 与 Late Events

"Window 触发了 = 从窗口移除" 这是默认行为。但用户可以声明 AllowedLateness 保持该窗口继续接收晚期数据：

```java
dataStream.keyBy(...)
    .window(TumblingEventTimeWindows.of(Time.minutes(5)))
    .allowedLateness(Time.minutes(2))  // 触发后仍然接收 2 分钟晚数据
    .reduce(...)
```

这期间窗口不会被清理，收到一条晚期数据会**立即**触发一次窗口更新。

如果再晚于 `allowedLateness` → 可以路由到 Side Output（延迟数据的日志流）：

```java
.window(...)
.sideOutputLateData(lateDataTag)
```

---

## 8.7 — 完整流程图解

```
Source 产生记录 [eventTime=12:01]
  ↓ 通过分配 WatermarkStrategy
  ↓ WM(12:00) 沿 forward 边发送
Map 算子接收记录 + WM
  ↓ keyBy partition
KeyedProcess 算子
  ↓ 分配到窗口：TumblingEventTimeWindows(5min)
  ↓ 记录进入 WindowState
  ↓ WM 到达 12:05 → Trigger.onEventTime() → FIRE
  ↓ WindowFunction 计算结果
  ↓ 输出到下游（沿 keyBy 边发送给下游 Sink）
```

---

## 8.8 — 横向对比

### vs Spark Structured Streaming

Spark SS 在 2.3+ 也有 Watermark、Window、以及输出延迟的概念。但区别在于：
- Spark 的 Watermark 只能设在一个 query 的全局延迟阈值——不像 Flink 支持 per-operator watermark 和 idle source
- Spark 没有 "Session Window" 概念（adaptive window gap）
- 底层：Spark 的 Watermark 是 Trigger-based 检查点实现的，Flink 的 Watermark 是 Operation Chain 内在线流转的

### vs StarRocks/MaxCompute

StarRocks/MaxCompute 本身是 SQL 引擎，没有 Watermark 概念——数据完整的假设来自"存储中有有限数据"。如果 MaxCompute 做增量计算，需要通过事务表扫描 + 时间戳快照来实现。

---

## 8.9 — 调优与实战陷阱

### Watermark 不前进导致无限延迟

症状：窗口永远不触发，checkpoint 正常但 compute 一直没有输出。
原因：某个 Source 处于 idle 状态但没标记 withIdleness → WM 被卡死。
解法：`WatermarkStrategy.withIdleness(Duration.ofSeconds(30))`。

### BoundedOutOfOrderness 的策略

如果设置太保守（大），窗口计算延迟长（允许晚到的数据等待更长），反之则延迟低但晚数据多。
在 Kafka 中的经验公式：**BoundedOutOfOrder = 2x max observed lag between Kafka partitions**。

### Late Events 积累导致 OOM

如果设置了 AllowedLateness 但晚数据持续到来 → 窗口一直保留 → State 中积压的数据量指数增长 → heap OOM。监控 `numLateRecordsDropped` 指标——如果持续增长，设置更严的 AllowedLateness 或增加资源。

---

## 本章要点回顾

1. Watermark = 时间完整性的**不确定但合理的指标**——告诉下游"早于 t 的事件都到了"。
2. Watermark 沿数据边传播，多输入取 min——idle source 需要显式标记避免全局阻塞。
3. Tumbling/Sliding/Session 的窗口分配逻辑差异很大——Session 需要动态合并。
4. Trigger 决定"何时计算"，AllowedLateness 决定触发后"是否仍接收晚数据"。

## 源码导航

- Watermark 类：`flink-core/.../streaming/api/watermark/Watermark.java`
- WatermarkGenerator：`flink-core/.../api/common/eventtime/WatermarkGenerator.java`
- WatermarkStrategy：`flink-core/.../api/common/eventtime/WatermarkStrategy.java`
- WindowAssigner：`flink-core/.../api/windowing/assigners/WindowAssigner.java`
- TumblingEventTimeWindows：`flink-core/.../api/windowing/assigners/TumblingEventTimeWindows.java`
- Trigger：`flink-core/.../api/windowing/triggers/Trigger.java`
- EventTimeTrigger：`flink-core/.../api/windowing/triggers/EventTimeTrigger.java`
- WindowOperator：`flink-runtime/.../streaming/runtime/operators/windowing/WindowOperator.java`（L120-160 核心字段）
