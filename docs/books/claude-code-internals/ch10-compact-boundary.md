# 第 10 章 Compact Boundary：压缩的语义与持久化

> 压缩改变了对话历史的结构。如何在"压缩后的摘要"和"压缩前保留的消息"之间建立清晰的语义边界，决定了 Agent 能否在压缩后无缝继续推理。这就是 Compact Boundary 要解决的问题。

---

## 10.1 边界标记：createCompactBoundaryMessage()

压缩完成后，系统插入一个特殊的 SystemMessage——Compact Boundary：

```typescript
// 边界消息的结构
{
  type: 'system',
  subtype: 'compact_boundary',
  metadata: {
    compactId: 'compact_xxx',
    compactedMessageCount: 45,    // 被压缩了多少条消息
    compactedTokenCount: 85000,   // 释放了多少 token
    compactTimestamp: '2026-05-02T...',
    summaryMessageCount: 2,       // 摘要占据了几条消息
  }
}
```

Boundary 是一个**声明**——"从这里之前的所有消息，已经被摘要替代。你应该看摘要而非原始消息。"

---

## 10.2 消息可见性：getMessagesAfterCompactBoundary()

这是上下文管理中最关键的函数之一：

```typescript
function getMessagesAfterCompactBoundary(messages: Message[]): Message[] {
  // 找到最近的 compact_boundary
  // 返回 boundary 之后的所有消息
  // boundary 之前的消息对后续 API 调用不可见
}
```

### 为什么 boundary 之前的消息不必可见？

当 Agent 继续推理时，它需要的是"到目前为止发生了什么"的理解——这正是摘要提供的信息。原始对话的逐字记录对推理是噪音而非信号。

关键约束：**boundary 之前的消息不能出现在后续 API 调用中**。如果它们出现了，就意味着摘要 + 原始消息都在 context 中——上下文窗口瞬间爆炸。

---

## 10.3 preservedSegment：保留的消息链

边界之后保留了什么？

```
压缩后的消息结构：
  [compact_boundary]
  [summary_user_message_1]      ← 摘要的 user 部分
  [summary_assistant_message]   ← 摘要的 assistant 部分
  [user_message_recent_1]       ← 保留的最近 N 条消息
  [assistant_message_recent_1]  ← （"窗口尾部"）
  ...
```

被保留的消息数量取决于配置——典型值是最近 2-3 轮对话。这些是压缩点之后仍在进行的推理。

---

## 10.4 Transcript 持久化：磁盘写入与内存释放

Compact boundary 触发两个操作：写入和释放。

**写入**：boundary 之前的完整 transcript 被序列化到磁盘：
```
~/.claude/projects/<project-id>/<session-id>.jsonl
```

**释放**：内存中的消息数组被替换为"boundary + 摘要 + 尾部消息"。原来的大数组可以被 GC 回收。

### 为什么不是流式写入？

Transcript 是追加写入——每个 boundary 产生一个新文件增量。但读取时，完整 transcript 可以通过拼接所有增量重建。这种写入模式类似于 WAL 的追加写——快、无锁、易于恢复。

---

## 10.5 摘要的用户消息：getCompactUserSummaryMessage()

压缩后第一条用户消息的构造很特别：

```typescript
// "无缝继续" 指令
content: "The conversation has been summarized to save context. Continue from where you left off. The summary above contains everything you need to know."
```

告诉 Agent："你没有被重置，你只是获得了一个浓缩版的记忆。继续工作。"

---

## 10.6 压缩后的首次 API 调用

压缩后的第一条消息遵循与正常消息相同的 `queryModel` 路径，但有一个关键差异：

**prompt cache 从头开始**。因为 system prompt + 摘要消息 + 新的尾部消息构成了全新的前缀，服务端缓存中没有匹配项。第一次 API 调用（"post-compact turn"）承担全量 prompt 传输的成本。

但这只发生一次——后续 API 调用回到正常的缓存命中模式。对长会话来说，一次全量传输的成本远低于每轮都在超大上下文中传输的费用。

---

## 本章小结

Compact Boundary 是上下文管理的"checkpoint"：

```
完整历史 → [压缩] → boundary + 摘要 + 尾部
                        ↓
                   内存释放
                        ↓
                   磁盘持久化（transcript）
                        ↓
                   后续推理继续（只看 boundary 之后）
```

这个设计将"压缩"从一次性操作升级为**持久化的状态转换**。它不是把旧消息扔掉——而是归档到磁盘、从上下文移除、用摘要替代。正如数据库的 checkpoint 不是丢掉 WAL，而是把 WAL 中的更改合并到数据文件后腾出空间。

下一章，我们将讨论 token 预算的精细控制——Agent 如何在 token 消耗和任务完成度之间保持平衡。
