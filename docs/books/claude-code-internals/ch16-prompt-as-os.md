# 第 16 章 提示词是操作系统

> 如果把 Claude Code 看作一个操作系统，System Prompt 就是它的内核。这一章用 OS 类比来组织前 15 章积累的理解，建立理解 LLM Agent 架构的认知框架。

---

## 16.1 Unix 类比的完整映射

| Unix 概念 | Claude Code 对应 | 说明 |
|-----------|-----------------|------|
| Kernel | System Prompt | 定义 Agent 的身份、行为规则、能力边界 |
| Syscalls | Tools | Agent 与外部世界交互的唯一接口 |
| File Descriptors | Content Blocks | 流式 I/O 的读写单元 |
| Capabilities | Permissions | 操作的安全检查边界 |
| Process | Agent Instance | 独立的执行上下文 |
| fork() | Fork Mode | 继承父进程的完整状态 |
| IPC | Mailbox | Agent 间异步通信 |
| Scheduler | runTools / StreamingToolExecutor | 工具执行的并发调度 |
| Memory Management | Token Budget / Compression | 有限容量下的资源回收 |
| Checkpoint | Compact Boundary | 状态持久化和恢复点 |
| WAL | Transcript | 操作日志，追加写，支持恢复 |

---

## 16.2 提示词的 ABI 稳定性

System Prompt 的字节布局决定了 Prompt Cache 的命中率。一个 section 的插入就像改变了 syscall 的编号——所有依赖它位置的行为全部失效。

```
System Prompt 的 "ABI 契约"：
- Section 顺序 = syscall 编号
- Section 内容 = syscall 语义
- 改变顺序/内容 → cache 全部失效 → 所有用户承担全量传输成本
```

这就是为什么 Claude Code 在 `SYSTEM_PROMPT_DYNAMIC_BOUNDARY` 前后有如此严格的顺序约束，以及为什么 `buildSystemPromptBlocks` 中对 boundary 有特殊处理。

---

## 16.3 动态描述的运行时链接

`description(input, options)` ≈ `dlopen()`：

```
dlopen("libfoo.so")  → 加载动态库，返回函数指针
description(input)   → 根据 input 动态返回工具描述文本
```

两者都是**推迟到运行时的绑定**。静态链接代价太高（在 prompt 静态区硬编码所有工具描述），动态绑定给予灵活性。

---

## 16.4 工具发现 ≈ 动态加载

```
ToolSearch ≈ /proc filesystem

ls /proc           → 查看可用的内核接口
ToolSearch("slack") → 查看可用的 MCP 工具

发现模块 → 加载到内核
tool_reference → 加载到 tool schema
```

---

## 16.5 Hooks ≈ LSM (Linux Security Modules)

```
LSM hook: security_file_open()  → 允许/拒绝打开文件
PreToolUse hook: canUseTool()   → 允许/拒绝执行工具

SELinux policy → settings.json permissions
AppArmor profile → Hook script
```

Hooks 和 LSM 都在核心代码路径中插入了可插拔的安全检查点，让安全策略成为配置而非代码。

---

## 本章小结

提示词是操作系统——这不是比喻，而是架构级的同构。它们都在解决相同的根本问题：

- **资源管理**（内存/上下文窗口）
- **安全边界**（capability/permission）
- **接口抽象**（syscall/tool）
- **并发调度**（process/agent execution）
- **持久化**（checkpoint/compact boundary）

理解了这个映射，你就能用几十年的 OS 设计经验来推理 Agent 架构的正确性。
