# 第 9 章 五级压缩管线：从轻量到重度的渐进策略

> 压缩不是开关，而是连续谱。Claude Code 的五级压缩从最轻量的规则裁剪到最重度的 LLM 摘要，每级都是对"保留什么、丢弃什么"的一次权衡。这一章拆解每级的触发条件、执行逻辑和成本考虑。

---

## 9.1 Level 1 — Snip：基于规则的裁剪

Snip 是最轻量的压缩——不调用 LLM，只做规则层面的消息过滤。

**触发条件**：每轮 API 调用前自动检查。

**执行逻辑**：
- 移除重复的、冗余的消息
- 裁剪过长的工具输出中无价值的部分
- 清理已被标记为 tombstone 的消息引用

**为什么叫 Snip**：它就像剪刀一样精准裁剪不需要的部分，而非重写内容。Snip 不改变保留内容的任何字节，这保持了 prompt cache 的前缀一致性。

---

## 9.2 Level 2 — Microcompact：Cache Editing 的零缓存失效

Microcompact 是 Claude Code 最巧妙的压缩创新——它利用 Anthropic API 的 `cache_edits` 特性，**在缓存层面替换消息内容**，做到"内容变了但缓存没变"。

### 9.2.1 Prompt Cache 的工作原理

```
请求 1: system_prompt_part_A + message_1 + message_2 + message_3
          ↑ 这部分被缓存                    ↑ cache_control marker

请求 2: system_prompt_part_A + message_1 + message_2 + message_4
          ↑ 命中缓存，不收费                ↑ 新内容，重新计算
```

### 9.2.2 cache_edits：在缓存层面替换

Microcompact 的关键创新：不是"修改消息后重新发送"，而是"发送一个新指令告诉服务端用什么替换哪条消息的内容"：

```typescript
// cache_edits 块
{
  type: 'cache_edits',
  edits: [
    {
      cache_reference: 'toolu_abc123',  // 引用缓存的 tool_use
      operation: 'delete',               // 删除操作
    },
  ]
}
```

### 9.2.3 为什么不需要重新发送完整请求

因为 `cache_edits` 操作的是服务端已缓存的 KV cache——它直接从缓存中移除指定范围，而不需要客户端重新传输任何内容。这就像数据库中的**索引原地更新**而非全表重建。

---

## 9.3 Level 3 — Context Collapse：渐进式折叠

当 microcompact 还不够时，进入 Context Collapse——渐进式折叠消息内容。

### 折叠语义

```
折叠前: "I'll analyze the login flow. Let me first read the auth module..."
折叠后: "[analysis of login flow and auth module read]"
```

折叠是可展开的——UI 中用户可以看到折叠标记，点击展开查看完整内容。这是"对 LLM 隐藏但对人保留"的设计。

### 恢复路径

```
API 返回 413 实际错误
  → drain staged collapses (释放预折叠但未真正移除的内容)
  → 重试
  → 如果还失败 → 进入 Level 4/5
```

---

## 9.4 Level 4 — Auto Compact：LLM 驱动的会话摘要

这是最常见、最重要的压缩级别——由 Haiku 模型自动生成对话摘要。

### 9.4.1 触发条件

```typescript
// 自动压缩阈值 = 模型上下文窗口 × 百分比
const threshold = getAutoCompactThreshold()
// 当已用 token 数 > threshold 时触发
```

### 9.4.2 摘要请求的构建

```xml
<analysis>
  What was the user's original request?
  What were the key decisions and discoveries?
  What's the current state? What's next?
</analysis>
<summary>
  Compact summary of the conversation so far.
  The summary should enable the assistant to continue
  seamlessly without losing context.
</summary>
```

双层结构：`<analysis>` 是"草稿纸"——可能会被 strip；`<summary>` 是最终摘要——被保留并注入后续上下文。

### 9.4.3 Forked Agent 路径

Auto Compact 使用 Forked Agent 路径——子 Agent 从父会话 fork，共享 prompt cache 前缀。这意味着摘要请求的 `system_prompt + messages_prefix` 与主 Agent 相同，**摘要调用几乎免费**（只需支付摘要输出本身的 token）。

### 9.4.4 prompt-too-long 恢复

当摘要请求本身也要超出窗口时：
- `truncateHeadForPTLRetry()`：递归截断最旧的消息，用边界标记替换
- 每次截断 50%，重试直到成功或无法再截断

### 9.4.5 后压缩恢复

压缩后，系统重新注入：
- **文件状态**：readFileState 缓存中最近读取的文件
- **Plan**：当前计划内容
- **Skill 列表**：可用技能
- **工具发现状态**：已被发现的延迟加载工具

这些操作确保 Agent 在压缩后不丢失"对世界状态的认知"。

---

## 9.5 Level 5 — Reactive Compact：413 错误触发的响应式压缩

当所有预防措施都失败，API 实际返回 413（Prompt too long），触发最后的防线。

### 9.5.1 消息拦截

```typescript
// isWithheldPromptTooLong() 检查：
// 不让模型看到中间的 API 413 错误消息
// 而是静默触发压缩
```

模型不应该感知到压缩在发生——如果模型看到 413 错误，它会改变行为（"我遇到了错误，我应该...")。拦截错误消息保持了 Agent 行为的一致性。

### 9.5.2 媒体移除

图片和 PDF 是最"昂贵"的内容——一张图片可能等于几千 token。当 prompt-too-long 时：
- 优先移除最旧的媒体
- 保留文本（文本的信息密度比图片高）
- 逐步移除直到请求成功

### 9.5.3 熔断器

```typescript
if (consecutiveFailures > MAX_REACTIVE_COMPACT_RETRIES) {
  // 熔断：不再尝试压缩
  // 返回明确的错误给用户："请手动 /compact"
}
```

熔断器防止 Agent 在"压缩→失败→再压缩→再失败"的无限循环中消耗 API 费用。

---

## 本章小结

五级压缩管线是一个精心设计的**渐进式退让**策略：

```
Level 1 (Snip)        → 零成本，规则驱动
Level 2 (Microcompact)→ 零缓存失效，API 原生
Level 3 (Collapse)    → 低信息损失，可展开恢复
Level 4 (Auto Compact)→ 高信息损失，LLM 重写
Level 5 (Reactive)    → 紧急模式，硬性截断
```

每级的"信息保真度"递减，但"清理能力"递增。系统的目标是尽可能在低级别解决问题——只有低级别失败才升级到高级别。这种递增成本结构确保了在绝大多数情况下，压缩的成本保持在最低。

**与数据库的类比**：这类似于数据库内存管理的多层次策略。Level 1 ≈ 清理临时变量；Level 2 ≈ 原地更新索引；Level 3 ≈ 内存压缩（如 ZRAM）；Level 4 ≈ checkpoint + WAL 截断；Level 5 ≈ OOM killer。问题本质相同——有限容量下的资源回收。
