# 第 14 章 Fork 模式：上下文共享与缓存优化

> Fork 是 Claude Code 最聪明的性能优化之一——通过字节级相同的前缀来共享 Prompt Cache，让"克隆 Agent"的成本几乎为零。这一章拆解 Fork 的约束、实现和权衡。

---

## 14.1 Fork vs Delegate：两种多 Agent 模式

| 维度 | Fork | Delegate（常规子 Agent） |
|------|------|--------------------------|
| 上下文 | 完整继承父 Agent 的所有消息 | 独立上下文，只有提示 |
| Prompt Cache | 共享（前缀字节相同） | 不共享 |
| 工具 | 默认全部可用 | 按 AgentDefinition 裁剪 |
| 启动速度 | 极快（缓存命中） | 正常（需要初始化） |
| 隔离性 | 无状态隔离 | 完全隔离 |

**Fork = 完整继承、共享缓存。Delegate = 独立构建、完全隔离。**

---

## 14.2 Fork 的核心约束：byte-identical 前缀

Fork 能共享 cache 的前提是严苛的：

> 父 Agent 和 Fork Agent 的 `system_prompt + tools + model + messages_prefix` 必须在字节层面完全相同。

如果任何一个字节不同——缓存失效，需要全量重新传输。

---

## 14.3 消息分叉：buildForkedMessages()

Fork Agent 的消息历史构建方式独特：

```typescript
function buildForkedMessages(parentMessages) {
  // 1. 复制父 Agent 的所有消息
  // 2. 最后一条 assistant 消息的 tool_use blocks → placeholder tool_results
  // 3. tool_result 的 content 被替换为占位符
  return forkedMessages
}
```

### 为什么用 placeholder tool_result？

父 Agent 的最后一条消息可能包含正在执行的 tool_use blocks。Fork Agent 不能等待它们执行完——这违背了 Fork 的"快速启动"目标。Placeholder 让 Fork Agent 看到完整的消息结构（保持前缀一致），同时不关心工具执行结果的内容。

---

## 14.4 递归 Fork 防护

```
主 Agent → Fork A → Fork B (如果 A 试图 Fork)
```

系统通过 `isInForkChild()` 检测递归：

```typescript
// 检测 boilerplate tag 来判断是否已在 Fork 中
if (isInForkChild()) {
  // 直接执行，不要再 Fork
  // 防止无限递归
}
```

递归 Fork 会导致上下文窗口指数级膨胀（每个 Fork 都在复制父 Agent 的全部上下文）。

---

## 14.5 权限冒泡：permissionMode 'bubble'

Fork Agent 的权限弹窗冒泡到父 Agent 的终端：

```
Fork Agent → 需要权限 → 通过 mailbox → 父 Agent UI → 用户决定
                                                      ↓
                                              allow → 回传给 Fork
                                              deny  → 回传给 Fork
```

`bubble` 模式确保用户不会面对"灰色弹窗"（后台运行的 Fork Agent 的权限请求用户看不到）。

---

## 14.6 CacheSafeParams

```typescript
interface CacheSafeParams {
  systemPrompt: SystemPrompt    // 必须与父 Agent 完全相同
  userContext: {}               // 用户上下文（CLAUDE.md 等）
  systemContext: {}             // 系统上下文（git status 等）
  toolUseContext: ToolUseContext
  forkContextMessages: Message[] // Fork 的消息历史
}
```

这些字段一起构成了 "cache key"。任何变化都会导致 cache miss。

---

## 本章小结

Fork 模式的本质是**用缓存的一致性约束换取速度**：

- 支付：严格遵守 byte-identical 前缀约束
- 获得：几乎零成本的 Agent "克隆"

这就像进程的 fork()——子进程继承父进程的完整地址空间，通过 COW (Copy-on-Write) 优化物理内存。Claude Code 的 Fork 继承父 Agent 的完整 Prompt Cache，通过 API 层的 cache_control 优化实际的 token 传输。相同的设计模式，不同的抽象层级。

下一章，我们探索最激进的分布式 Agent 架构——Coordinator 与 Swarm。
