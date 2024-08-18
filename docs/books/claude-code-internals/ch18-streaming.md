# 第 18 章 流式架构与实时交互

> LLM Agent 不是批处理系统——它是实时交互系统。流式架构从 AsyncGenerator 链到流式工具执行，定义了 Agent 如何"边想边做"。这一章拆解整个流式链路的架构和设计权衡。

---

## 18.1 AsyncGenerator 链：yield* 的接力

整个 LLM API 响应通过多层 AsyncGenerator 接力传递：

```
queryModel()    → yield StreamEvent / AssistantMessage
    ↓ yield*
query()         → yield StreamEvent / AssistantMessage / UserMessage
    ↓ yield*
QueryEngine     → yield SDKMessage
    ↓
REPL / SDK 消费者
```

每一层都可能添加自己的产出：

- `queryModel` → 流式事件、assistant 消息
- `query()` → 加上工具结果消息、进度消息、墓碑消息
- `QueryEngine` → 转换为 SDK 格式，加上会话级事件

### yield* 的效率

`yield*` 是 JavaScript 的委托 yield——它不复制值，直接将上层的 yield 转发给下层。一个从 API 接收的 token 在存储到 content block 之前不产生任何 CPU 复制开销。

---

## 18.2 流式工具执行：LLM 与工具流水线

StreamingToolExecutor（第 6 章介绍）实现了 LLM 输出和工具执行的**时间重叠**：

```
普通模式:
  LLM输出[======] 工具执行[###] LLM继续[===]
  总时间 = LLM输出 + 工具执行 + LLM继续

流式模式:
  LLM输出[=======   ]
  工具执行   [###    ]
  LLM继续         [===]
  总时间 = max(LLM输出, 工具执行+LLM继续)
```

---

## 18.3 中断语义：abort signal 的穿透

`AbortController.signal` 是整个链路的"中断信号"：

```
用户 Ctrl+C
  → abortController.abort()
  → signal.aborted = true
  → queryModel() 立即停止流式迭代
  → query() 不执行后续工具
  → QueryEngine 返回 "aborted" 状态
```

Signal 通过引用传递——一个 signal 对象在整条调用链中共享。任何层都可以检测 `signal.aborted` 并提前退出。

---

## 18.4 消息类型系统的回顾

10 种消息类型在第 1 章已介绍。从流式视角看，它们的生灭时机是：

```
请求开始:     RequestStartEvent
流式进行中:   StreamEvent (delta events)
助手响应完成:  AssistantMessage
工具执行中:    ProgressMessage
工具结果:      UserMessage
压缩进行中:    SystemMessage (compact_boundary)
用户上下文:    AttachmentMessage
消息回退:      TombstoneMessage
```

这个类型系统不是形式化的——每种类型的产生时机和处理逻辑直接影响 Agent 的实际行为。

---

## 18.5 与传统数据库流式执行的类比

```
cursor    → AsyncGenerator     ← 逐行/逐事件产出
pipeline  → StreamingToolExecutor ← 时间重叠执行
LIMIT     → maxOutputTokens    ← 输出数量控制
CANCEL    → abortController    ← 中断正在执行的操作
```

数据库的 cursor 模型和 Agent 的 AsyncGenerator 模型遵循相同的迭代器模式——"给我下一个结果"而非"给我全部结果"。这保证了无论结果集多大，内存使用保持恒定。

---

## 本章小结

流式架构是 Agent 实时性的基础设施。四个关键设计：

1. **AsyncGenerator 链**：零拷贝的接力传递
2. **StreamingToolExecutor**：时间重叠的流水线
3. **AbortSignal**：跨层的中断共享
4. **消息类型系统**：精确的流式事件建模

这些不是"性能优化"——它们定义了 Agent 与用户的交互模式。没有流式架构，Agent 就是批处理系统；有了流式架构，Agent 成为了实时协作者。
