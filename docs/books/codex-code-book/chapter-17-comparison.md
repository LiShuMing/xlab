# 第17章：横向对比——Codex 与其他 AI 编程工具的差异

> 编写日期：2026-05-04
> 对比对象：Claude Code、Gemini CLI、Qwen Code、Kimi CLI、Cursor、Windsurf、Continue

---

## 17.1 对比框架：从五个维度审视

评价一个 AI 编程工具，不能只看"谁写得准"。本章从五个架构维度出发，建立系统化的对比框架：

```
维度一：进程模型      — TUI/Server 分离度、IPC 机制、可扩展性
维度二：安全沙箱      — 隔离层级、跨平台策略、默认安全姿态
维度三：Agent 模型    — 多 Agent 协作深度、子 Agent 语义、状态传递
维度四：工具生态      — 内建工具丰富度、MCP 支持深度、扩展机制
维度五：工程成熟度    — 构建系统、测试体系、版本演进策略
```

---

## 17.2 进程模型对比

### Codex：多进程 Actor Model

```
┌────────┐     JSON-RPC      ┌────────────┐     Rust FFI     ┌──────────┐
│  TUI   │ ←───────────────→ │ App Server │ ←─────────────→ │   Core   │
│(rust)  │   UDS/WebSocket   │  (rust)    │    in-process   │  (rust)  │
└────────┘                   └────────────┘                  └──────────┘
```

- TUI 进程不 link core，只知道 Op/Event 协议
- App Server 进程做消息路由、并发控制、连接管理
- Core 库可以被 TUI、Exec CLI、测试框架、WASM 等多种前端复用
- 天然支持远程连接（`codex --remote ws://...`）

### Claude Code：单进程 Node.js

```
┌─────────────────────────────────────────┐
│            Claude Code (Node.js)          │
│  TUI + API Client + Tool Runtime + ...    │
│  所有逻辑在一个进程中                      │
└─────────────────────────────────────────┘
```

- 单进程架构，开发迭代快
- TUI、API 调用、Tool 执行全部在同一 Node.js 线程中
- 不支持远程连接（TUI 和逻辑绑定）
- 沙箱依赖于操作系统的进程隔离（子进程 sandbox）

### Gemini CLI / Qwen Code / Kimi CLI

| 工具 | 进程模型 | 语言 |
|------|---------|------|
| Gemini CLI | 单进程（Go/Node） | Go |
| Qwen Code | 单进程 | Python |
| Kimi CLI | 单进程 | Python/TypeScript |
| Cursor | Electron 多进程（Renderer + Extension Host） | TypeScript |
| Continue | VS Code Extension（单进程） | TypeScript |

### 差异分析

Codex 的多进程架构多了一层 IPC 延迟（UDS 上通常 <1ms），但换来了：
- **前端可替换**：同一个 App Server 可以被 TUI、VS Code 插件、Web 前端共用
- **远程能力**：`codex --remote` 将 App Server 部署在远端，TUI 通过 WebSocket 连接
- **崩溃隔离**：TUI crash 不影响 Agent 运行状态（App Server 保持 Thread 活跃）

Claude Code 的单进程模型开发体验更流畅（无需进程管理），但远程协作需要额外的会话同步机制。

---

## 17.3 安全沙箱对比

这是 Codex 与所有其他工具**差距最大**的维度。

### Codex：三层纵深防御

| 层级 | 机制 | 覆盖度 |
|------|------|--------|
| PermissionProfile | 声明式权限（文件系统 Read/Write/None + 网络 Enabled/Restricted） | 100% |
| 平台沙箱 | Linux bubblewrap+seccomp / macOS Seatbelt / Windows WFP | 100% |
| ExecPolicy | 命令级规则引擎（Allow/Prompt/Forbidden + 自动修正建议） | 100% |

关键特征：
- **默认安全**：默认 PermissionProfile = Restricted（只有 cwd 可写），你必须显式放宽
- **OS 级强制执行**：不是"建议 LLM 不要做"，是内核拦截。即使 LLM 生成 `rm -rf /`，内核也拒绝
- **跨平台一致**：三个平台的沙箱机制不同，但安全语义一致

### Claude Code：两级审批 + 子进程沙箱

| 层级 | 机制 |
|------|------|
| 权限审批 | AskForApproval（Always/Never/OnRequest）+ 记住前缀 |
| 沙箱 | macOS Seatbelt（子进程级别）、Linux landlock（beta） |

- 审批模型与 Codex 的 ExecPolicy 类似（前缀匹配 + 记住决策）
- 沙箱执行比 Codex 晚一个层次——Codex 在 Session 创建时确定沙箱策略，Claude Code 按需应用
- 没有 Codex 的 PermissionProfile 抽象层（文件系统和网络权限的统一声明）

### 其他工具

| 工具 | 沙箱策略 |
|------|---------|
| Gemini CLI | 基本无沙箱（依赖用户审批） |
| Qwen Code | 无沙箱 |
| Kimi CLI | 基本审批模型 |
| Cursor | VS Code 沙箱（Extension Host 隔离） |
| Windsurf | 基本审批模型 |

### 差异分析

Codex 在安全上的投入远超其他工具。这不是说其他工具"不安全"，而是它们的安全模型重心不同：

- **Claude Code**：依赖 LLM 的对齐训练 + 用户审批作为最后防线。沙箱是"附加保障"
- **Codex**：沙箱是第一道防线，审批是第二道，LLM 对齐是第三道。纵深防御

从"AI 操作系统内核"的视角看，Codex 的做法更接近 OS 的设计哲学——**安全不能依赖"进程不干坏事"，必须依赖"内核不让你干坏事"**。

---

## 17.4 Agent 模型对比

### Codex：完整的 Agent 树

```
.root                   (Root Agent, 用户交互)
.root/explorer          (子 Agent, Fork 模式继承 Shell 状态)
.root/explorer/reader   (孙 Agent, FS Path 层级命名)
```

核心能力：
- **AgentPath**：文件系统式的层级命名（`root/sub1/sub2`），精确 Agent 间寻址
- **Fork 模式**：从父 Agent 的 rollout 历史 fork，子 Agent 继承对话上下文
- **Shell Snapshot 继承**：子 Agent 从父 Agent 继承 Shell 状态（环境变量、别名、当前目录），类似 `fork()` 的文件描述符继承
- **CompletionWatcher**：异步监控子 Agent 完成，自动注入结果到父 Agent Context
- **InterAgentCommunication**：Agent 间消息传递，支持触发 Turn 或仅注入 Context

### Claude Code：子 Agent + Task 工具

- 通过 `Task` 工具创建子 Agent（类似 `spawn_agent_internal`）
- 子 Agent 之间独立运行，没有 AgentPath 寻址
- 支持 background task（类似 CompletionWatcher 模式）
- 子 Agent 共享同一个会话上下文，没有 Fork/新建的区分

### Cursor / Windsurf / Continue

| 工具 | Agent 模型 |
|------|-----------|
| Cursor | 单 Agent + Composer/Inline Chat 双交互模式 |
| Windsurf | 单 Agent + Flow 模式（自动跨文件操作） |
| Continue | 单 Agent + @mention 上下文引用 |

### 差异分析

Codex 的 Agent 模型最接近操作系统的进程模型——有完整的命名空间、继承语义、异步监控。Claude Code 的 Agent 模型更接近"函数调用"——子 Agent 是一个可以异步等待的函数。

对于简单任务，这两种模型效果类似。但当任务需要"5 个 Agent 并行探索不同子目录，再汇总结果"时，Codex 的 Agent Tree + Fork + InterAgentCommunication 提供了更强的协调能力。

---

## 17.5 工具生态对比

### MCP 支持深度

| 特性 | Codex | Claude Code | 其他 |
|------|-------|-------------|------|
| MCP 协议版本 | 最新（2024-11-05+） | 最新 | 部分支持或未支持 |
| 传输方式 | stdio + Streamable HTTP | stdio + HTTP | 通常仅 stdio |
| 自定义 Capability | `codex/sandbox-state-meta` | 基本无 | - |
| 工具命名策略 | `mcp__server__tool` 前缀 | `mcp__server__tool` 前缀 | - |
| Codex Apps MCP | 内建特权 MCP Server | 无 | - |
| 审批模板 | AutoReview + Approve | 基本审批 | - |
| 资源系统 | Resources + Templates 完整支持 | 支持 | - |
| Elicitation | 完整支持 | 支持 | - |

### 内建工具

| 工具 | Codex | Claude Code | 说明 |
|------|-------|-------------|------|
| Shell | PTY + 沙箱 + 输出截断 | 子进程 + 输出截断 | Codex 沙箱更深 |
| Read/Write/Edit | 通过 file-system crate | 直接文件操作 | Codex 防 shell injection |
| Apply Patch | diffy/similar diff | diff 应用 | 机制相似 |
| Web Search | 内建 | 内建 | - |
| Web Fetch | 内建 | 内建 | - |
| Image Generation | 内建 | 无 | - |
| Plan Mode | Plan Tool + update_plan | /plan 模式 | - |
| Memory | 会话/项目/用户三级 | 会话级 | Codex 更结构化 |

---

## 17.6 工程成熟度对比

| 维度 | Codex | Claude Code | Cursor | 开源 CLI |
|------|-------|-------------|--------|---------|
| 语言 | Rust | TypeScript/Node.js | TypeScript | Python/Go/TS |
| 构建系统 | Cargo + Bazel | npm/tsup | VS Code build | 各自为政 |
| CI/CD | 三平台 (Linux/macOS/Windows) | GitHub Actions | GitHub Actions | 通常仅 Linux |
| 测试 | 单测 + 集成 + E2E + insta snapshot | 单测 + E2E | 单测 + E2E | 参差不齐 |
| 依赖管理 | Cargo.lock 入库 + patch | package-lock.json | package-lock.json | - |
| 协议稳定性 | 严格的 wire format 兼容 | HTTP/gRPC | VS Code API | - |
| 自更新 | self_replace crate | npm update | VS Code marketplace | 手动 |
| 包大小 | ~50MB（musl static） | ~200MB（node_modules） | IDE 插件 | 不等 |

---

## 17.7 设计哲学的根本差异

通过以上对比，可以看到不同工具的设计哲学差异：

### Codex："AI 操作系统内核"

- Agent = 进程、Tool = 系统调用、Context = 虚拟内存、Sandbox = 内核保护
- 安全是第一性原理（纵深防御，OS 级强制）
- 协议优先（多前端共享核心，远程天然支持）
- 工程严谨（Rust + 三平台 + dual build system）

### Claude Code："AI 协作伙伴"

- Agent = 对话参与者、Tool = 技能
- 安全依赖对齐 + 审批（沙箱是辅助）
- 单进程快速迭代（体验优先）
- Node.js 生态（npm 包分发，开发速度快）

### Cursor / Windsurf："AI 增强的 IDE"

- Agent 嵌入在 IDE 的编辑流中
- 安全依赖 IDE 沙箱 + VS Code Extension Host
- 重点是编辑体验（composer, inline edit, diff preview）
- AI 是 IDE 的一个功能，而非独立的操作系统

### Kimi / Qwen / 开源 CLI："模型能力的前端"

- Agent 是 API 调用的薄封装
- 安全=无或基本审批
- 核心价值在模型能力而非工程架构
- 快速将模型能力暴露给 CLI

---

## 17.8 选型建议

| 场景 | 推荐 | 原因 |
|------|------|------|
| 需要最高安全保证（生产环境操作） | Codex | 三层沙箱 + OS 级隔离 |
| 需要远程协作（云开发环境） | Codex | 原生 remote 支持 |
| 快速原型 + 个人项目 | Claude Code | 安装简单，迭代快 |
| IDE 深度集成 | Cursor / Windsurf | 编辑流最流畅 |
| 学习 AI Agent 架构实现 | Codex (开源) | 架构最完整，源码可读 |
| MCP Server 开发调试 | Codex / Claude Code | MCP 支持最成熟 |
| 中国国内网络环境 | Kimi / Qwen | 不受 GFW 影响 |

---

## 17.9 本章要点

1. **Codex 在安全沙箱上领先**：三平台 OS 级隔离 + PermissionProfile + ExecPolicy 是独有能力。
2. **Codex 的多进程架构换取前端可替换 + 远程 + 崩溃隔离**，代价是额外 IPC 延迟。
3. **Agent 模型上 Codex 最接近 OS 进程模型**：AgentPath + Fork + Shell Snapshot + CompletionWatcher。
4. **MCP 支持上 Codex 和 Claude Code 处于第一梯队**，Codex 有自定义 Capability 和 Codex Apps。
5. **Claude Code 体验更流畅**（单进程 + 快速迭代），适合个人开发者快速使用。
6. **其他国产/开源工具在安全、工程成熟度上与两者有显著差距**，核心优势在模型能力或网络可达性。
7. **选型取决于你的优先级**：安全→Codex，体验→Claude Code，IDE 集成→Cursor，中文网络→Kimi/Qwen。
