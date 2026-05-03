# 深入 Claude Code：LLM Agent 实现原理

> 从第一性原理出发，以源码为线索，拆解一个 50 万行生产级 Agent 系统的设计与实现

## 篇章结构

- **第一篇：原子** — 一次 API 调用的完整生命周期
- **第二篇：循环** — Agent Loop 与工具系统
- **第三篇：记忆** — 上下文管理与持续推理
- **第四篇：群体** — 多 Agent 编排与分布式架构
- **第五篇：工程** — 系统设计与第一性原理

## 章节目录

| 章节 | 标题 | 文件 |
|------|------|------|
| 第 1 章 | 入口：从终端到请求 | [ch01-entry.md](ch01-entry.md) |
| 第 2 章 | 提示词工程：System Prompt 的动态组装 | [ch02-system-prompt.md](ch02-system-prompt.md) |
| 第 3 章 | 模型调用：流式请求的构建与执行 | [ch03-model-call.md](ch03-model-call.md) |
| 第 4 章 | Agent Loop：while(true) 的哲学 | [ch04-agent-loop.md](ch04-agent-loop.md) |
| 第 5 章 | 工具系统：Agent 的感知与行动接口 | [ch05-tool-system.md](ch05-tool-system.md) |
| 第 6 章 | 工具执行管线：从 tool_use 到 tool_result | [ch06-tool-pipeline.md](ch06-tool-pipeline.md) |
| 第 7 章 | 权限系统：自主性与安全性的连续谱 | [ch07-permissions.md](ch07-permissions.md) |
| 第 8 章 | 有限窗口下的推理：问题的本质 | [ch08-finite-context.md](ch08-finite-context.md) |
| 第 9 章 | 五级压缩管线：从轻量到重度的渐进策略 | [ch09-compression.md](ch09-compression.md) |
| 第 10 章 | Compact Boundary：压缩的语义与持久化 | [ch10-compact-boundary.md](ch10-compact-boundary.md) |
| 第 11 章 | Token 预算与输出控制 | [ch11-token-budget.md](ch11-token-budget.md) |
| 第 12 章 | Agent 工具：从单体到群体的跃迁 | [ch12-agent-tool.md](ch12-agent-tool.md) |
| 第 13 章 | 子 Agent 的执行模型 | [ch13-subagent.md](ch13-subagent.md) |
| 第 14 章 | Fork 模式：上下文共享与缓存优化 | [ch14-fork.md](ch14-fork.md) |
| 第 15 章 | Coordinator 与 Swarm：分布式 Agent 架构 | [ch15-swarm.md](ch15-swarm.md) |
| 第 16 章 | 提示词是操作系统 | [ch16-prompt-as-os.md](ch16-prompt-as-os.md) |
| 第 17 章 | 有损压缩下的推理保真度 | [ch17-lossy-fidelity.md](ch17-lossy-fidelity.md) |
| 第 18 章 | 流式架构与实时交互 | [ch18-streaming.md](ch18-streaming.md) |
| 第 19 章 | Agent 的系统边界 | [ch19-boundaries.md](ch19-boundaries.md) |
| 第 20 章 | 从第一性原理看 LLM Agent 的本质 | [ch20-first-principles.md](ch20-first-principles.md) |

## 阅读方式

- **线性阅读**：从第 1 章到第 20 章，逐步深入
- **按篇跳读**：每篇相对独立，可根据兴趣选择
- **按问题索引**：每章开头列出核心问题，可直接跳到感兴趣的问题

## 源码版本

本书基于 Claude Code 源码分析，源码路径：`/Users/lism/work/claude-code/src/`
