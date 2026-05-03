# 第 19 章 Agent 的系统边界

> 任何系统都有边界——定义"系统内"和"系统外"是架构设计的第一课。Agent 系统的边界多层嵌套：上下文边界、权限边界、状态边界、错误边界、缓存边界。这一章拆解每个边界的定义和穿透规则。

---

## 19.1 上下文边界：父子 Agent 的信息隔离与共享

| 通信方向 | 机制 | 信息损失 |
|----------|------|---------|
| 父 → 子（Delegate） | prompt 文本 | 父的内部推理丢失 |
| 父 → 子（Fork） | 完整消息复制 | 零损失（但代价是 cache 一致性约束） |
| 子 → 父 | tool_result 文本 | 子的完整推理过程丢失 |
| 子 → 子 | Mailbox | 结构化消息 |

上下文边界是可穿透的——通过 prompt 和 result——但总是有损的。穿透的信息经过了序列化→文本→理解的转换，每一步都有压缩。

---

## 19.2 权限边界：权限冒泡、session-scoped grant

```
Agent A (permissionMode: acceptEdits)
  └── Agent B (permissionMode: bubble)
        ├── 弹窗冒泡到 Agent A 的终端
        └── 权限决策回传到 Agent B
```

权限边界的关键规则：

1. **子 Agent 可以向父请求更高权限**，但不能自行提权
2. **Always Allow 只在当前 session 有效**，不修改文件
3. **权限模式在 Agent 创建时确定**，运行中不变

---

## 19.3 状态边界：全局 vs 局部 vs 透传

```
全局状态 (bootstrap/state.ts)
  sessionId, projectRoot, totalCost, totalApiDuration

AppState (React)
  UI 状态、权限模式、fast mode、effort value

局部状态 (toolUseContext)
  messages, readFileState, abortController

透传状态
  MCP resources, file history, attribution
```

状态的可见性遵循**最小可见原则**：
- 全局 → 所有 Agent 可见
- App → 同进程 Agent 可见（通过 getAppState）
- 局部 → 当前 Agent 独有
- 透传 → 父→子单向

---

## 19.4 错误边界：子 Agent 失败如何影响父

```
子 Agent 失败类别:
  1. 工具错误 (tool_result is_error: true) → 正常处理，不影响父
  2. API 错误 (529/429) → 重试或降级
  3. 崩溃 (uncaught exception) → 隔离，返回 error 摘要给父
  4. 超时 (maxTurns reached) → 返回 partial result
```

错误边界的核心设计：**子 Agent 的失败不应该导致父 Agent 失败**。每个子 Agent 有独立的 try-catch 壳，将所有错误转化为可消费的 error result。

---

## 19.5 缓存边界：prompt cache 的共享粒度

缓存边界的层次：

```
Session 级 ← 同一 session 内所有 API 调用共享
  ├── Agent 级 ← 同 Agent 的连续调用共享
  │   └── Fork 级 ← Fork 子 Agent 继承父的缓存前缀
  └── Cross-Org 级 ← system prompt 静态区 (scope: 'global')
```

缓存失效的传播：
- Session 清除：`/clear` → 所有缓存失效
- 压缩：`/compact` → 当前 Agent 的缓存刷新
- Fork 创建：继承父缓存 → 但一旦分流（字节开始不同），后续各自独立

---

## 本章小结

Agent 的系统边界不是一条线——它是多层嵌套的：

```
缓存边界 ⊂ 上下文边界 ⊂ 状态边界 ⊂ 权限边界 ⊂ 错误边界
  内层边界被打破 → 外层边界仍然保护
```

这个设计反映了**纵深防御**的原则——不会因为缓存被意外破坏就失去权限控制，不会因为状态不一致就导致父 Agent 崩溃。

**与数据库的类比**：这类似于数据库的隔离级别（READ UNCOMMITTED → SERIALIZABLE）。Agent 的不同边界提供了不同层次的保护，开发者可以根据需求选择"穿透"或"保持"哪个边界。
