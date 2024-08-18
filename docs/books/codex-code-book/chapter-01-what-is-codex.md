# 第1章：Codex 是什么——一个 AI 编程内核的诞生

> 源码版本：2026-05-04, commit `67849d950d`
> 关键文件：`README.md`, `AGENTS.md`, `codex-rs/Cargo.toml`, `codex-rs/cli/src/main.rs`, `codex-rs/core/src/lib.rs`

---

## 1.1 问题域：为什么需要 Codex？

要理解 Codex，首先要理解它所处的演进浪潮。

第一代 AI 编程工具是 **IDE 内的代码补全**。GitHub Copilot、Cursor 的 Tab 补全——模型在编辑器内，你写代码，它补全，交互的原子单位是"行"。

第二代是 **IDE 内的对话式 Agent**。Cursor Composer、Copilot Chat——你在侧边栏和模型对话，它可以读文件、运行终端命令、修改代码。交互的原子单位变成了"任务"。

Codex 代表了第三代：**终端原生的 AI Agent 内核**。它不依附于任何 IDE，而是直接在终端中运行，把整个计算机当作它的操作环境。它读取文件系统、执行 Shell 命令、管理 Git 仓库、与外部 MCP 服务器交互——本质上，它是一个**运行在用户态、用自然语言编程的操作系统 Shell**。

这个演进背后有一条清晰的主线：

| 代际 | 运行环境 | 交互单位 | 能力边界 |
|------|---------|---------|---------|
| 第一代 | IDE 补全框 | 行 | 光标位置的代码补全 |
| 第二代 | IDE 侧边栏 | 任务 | 读文件 + 写代码 + 终端 |
| 第三代 | 终端（Codex） | 会话 | 完整计算机 + MCP 扩展 + 沙箱隔离 |

**Codex 不是"更好的 Copilot"，它是另一种东西。** 正如 Docker 不是"更好的虚拟机"，Kubernetes 不是"更好的 init.d"——Codex 重新定义了人机协作的界面。界面不再是代码编辑器的补全框，而是终端里的自然语言对话。

---

## 1.2 Codex 的定位：AI 内核，而非 AI 聊天工具

如果我们用操作系统的视角来审视 Codex，会得到一张非常有趣的类比表：

| OS 概念 | Codex 对应 | 实现位置 |
|---------|-----------|---------|
| 进程管理 | `ThreadManager` ↔ `CodexThread` ↔ `Agent` | `core/src/thread_manager.rs:14`, `core/src/agent/` |
| 内存管理 / 虚拟内存 | Context Window / Token Budget | `core/src/compact.rs`, `core/src/thread_rollout_truncation.rs` |
| I/O 子系统 | `ModelClient` → API 通信 | `core/src/client.rs:1` |
| 文件系统 | Rollout / Session 持久化 (jsonl + SQLite) | `core/src/rollout.rs`, `thread-store/` |
| 系统调用 | Tool 系统（Shell/MCP/File/WebSearch） | `core/src/tools/`, `tools/` |
| 用户态隔离 | Sandbox（Landlock/Seatbelt/Seccomp） | `sandboxing/`, `core/src/landlock.rs` |
| 用户空间程序 | Plugin / Skills / MCP Servers | `plugin/`, `skills/`, `codex-mcp/` |
| 进程间通信(IPC) | App Server Protocol (JSON-RPC over UDS) | `app-server/`, `app-server-protocol/` |
| Shell | TUI + CLI + Exec | `tui/`, `cli/`, `exec/` |

这不是牵强附会。当你阅读 Codex 源码时，你会发现它在解决的问题和 OS 内核在解决的问题高度同构：

- **如何在受限资源（Token Budget ≈ 物理内存）下最大化任务吞吐？** → Context 压缩、轮转截断、智能 Summarize
- **如何安全地执行不受信任的代码（Shell 命令 ≈ 用户态程序）？** → 多层沙箱、ExecPolicy、权限审批
- **如何让多个执行单元（Agent ≈ 线程/进程）并发协作而不互相干扰？** → Mailbox、独立 Session、Agent Status 状态机
- **如何管理持久化状态（会话历史 ≈ 文件系统）？** → SQLite Thread Store、jsonl Rollout、Fork/Snapshot

**Codex 的本质是一个"AI 时代的操作系统内核"**——它管理的不再是 CPU 周期和物理内存页，而是 LLM 的上下文窗口和 Token 预算；它调度的不再是 x86 指令流，而是 Agent 的思考-行动-观察循环。

---

## 1.3 仓库全景：三层架构

Codex 的代码仓库采用三层架构：

```
codex/                           # 仓库根目录
├── codex-rs/                    # ★ Rust 内核（本书核心关注）— 109 个 crate
│   ├── core/                    #   核心引擎：Session、Agent、Tool、Context
│   ├── cli/                     #   CLI 入口：clap 命令解析、arg0 多入口
│   ├── tui/                     #   TUI 渲染引擎：ratatui + ChatWidget
│   ├── app-server/              #   进程间消息总线
│   ├── app-server-protocol/     #   JSON-RPC 协议定义 (v1/v2)
│   ├── protocol/                #   跨 crate 共享的类型和协议
│   ├── codex-api/               #   LLM API 客户端（HTTP + WebSocket）
│   ├── mcp-server/              #   MCP Server 实现（Codex 作为 MCP 服务）
│   ├── codex-mcp/               #   MCP Client 实现（Codex 连接外部 MCP）
│   ├── tools/                   #   Tool 定义和实现
│   ├── exec/                    #   非交互执行引擎
│   ├── exec-server/             #   执行服务器（独立进程）
│   ├── sandboxing/              #   沙箱抽象层
│   ├── linux-sandbox/           #   Linux Landlock + Seccomp
│   ├── windows-sandbox-rs/      #   Windows 沙箱
│   ├── thread-store/            #   SQLite 会话持久化
│   ├── rollout/                 #   会话录制与回放
│   ├── plugin/                  #   插件系统
│   ├── skills/                  #   Skill 系统
│   ├── config/                  #   配置管理
│   ├── login/                   #   认证管理
│   ├── model-provider/          #   多 Provider 抽象
│   └── utils/                   #   15+ 工具 crate
│
├── codex-cli/                   # TypeScript CLI 外层（npm 包入口）
│   └── package.json
│
├── sdk/                         # SDK（多语言）
│
├── docs/                        # 文档（贡献指南、安装指南）
│
├── tools/                       # 构建工具
│
└── BUILD.bazel / MODULE.bazel   # Bazel 构建系统（与 Cargo 并存）
```

关键认知：

1. **Rust 是内核，TypeScript 是启动器。** `codex-cli`（TypeScript）只做一件事：下载并启动 `codex` 二进制。所有核心逻辑都在 `codex-rs`。你运行的 `codex` 命令本质上是一个 Rust 编译出的独立二进制。
2. **109 个 crate 看起来很吓人，但有清晰的层次。** `core` 是最大的 crate（也是 AGENTS.md 明确说"不要再往里面加代码"的），它依赖几乎所有其他 crate。`protocol` 是零依赖的"类型语言"——所有 crate 都理解它。App Server 系（`app-server` / `app-server-client` / `app-server-protocol`）实现了进程间通信。
3. **双构建系统是工程现实的体现。** Cargo 用于日常开发（快），Bazel 用于 CI 和跨平台构建（正确、可复现）。`AGENTS.md` 中关于 "Cargo vs Bazel runfiles" 的注意事项反映了这种双轨制的复杂性。

---

## 1.4 核心哲学

从源码和 AGENTS.md 中，可以提炼出 Codex 设计的四条核心哲学：

### 哲学一：Terminal-Native（终端原生的）

Codex 的第一 UI 是终端。不是 Web，不是 IDE 插件。`codex-rs/tui/` 基于 ratatui 构建了整个渲染管线——消息列表、Markdown 渲染（pulldown-cmark）、Diff 展示（diffy/similar）、多行输入、语法高亮（syntect/two-face）。

这个选择很激进：放弃 GUI 的丰富表达能力，换取了什么？

- **零环境依赖**：只要有个终端就能跑。SSH 上去、tmux 里、甚至 TERM=dumb 时给个警告也能继续。
- **Unix 哲学的延续**：stdin/stdout/stderr 就是 I/O，管道就是组合。
- **与 Shell 的天然融合**：Codex 执行 Shell 命令，Shell 的输出又喂给 Codex——这是一个闭环。

### 哲学二：Sandbox-First（沙箱优先的）

Codex 的核心安全假设是：**AI 生成的命令不可信，必须在沙箱中执行。** 为此它在三个平台上实现了三层沙箱：

- **Linux**：Landlock（文件系统隔离）+ Seccomp（系统调用过滤）+ Bubblewrap（可选）
- **macOS**：Seatbelt（sandbox-exec + SBPL profile）+ PID 追踪
- **Windows**：Restricted Token + Read Grants

沙箱策略不是可选的"安全加固"，而是架构的内在一部分。`SandboxPolicy` 在 `CodexThread` 创建时就计算好了（`codex_thread.rs:65-73`），整个执行路径都带着它。

### 哲学三：Protocol-Driven（协议驱动的）

Codex 的内部通信采用强类型协议：

- **App Server Protocol**（`app-server-protocol/`）：TUI 进程和 App Server 进程之间的 JSON-RPC 风格协议。有严格的 v1/v2 版本管理、camelCase 命名规范、`#[experimental]` 标记机制。
- **codex-protocol**（`protocol/`）：跨 crate 共享的类型定义。包括 `Op`（操作枚举）、`Event`（事件枚举）、`Submission`、`ThreadId` 等核心概念。
- **MCP（Model Context Protocol）**：与外部工具服务器的标准协议。

这种"先定义协议，再实现功能"的方式，使得不同进程、甚至不同语言（Rust ↔ TypeScript via `ts-rs`）的组件可以可靠协作。

### 哲学四：抗膨胀设计（Anti-Bloat by Design）

`AGENTS.md` 中最有意思的一条规则是：

> **Resist adding code to codex-core!**

并且给出了具体约束：
- 每个 Rust 模块不超过 500 LoC（不含测试）
- 超过 800 LoC 就必须拆
- 鼓励创建新的 crate 而非把代码塞进 `core`
- 不要写"只被引用一次的小 helper 方法"

这不是"代码洁癖"，而是在一个 AI Agent 项目中，**上下文窗口就是第一资源**。模块越小，AI 一次性需要理解的范围就越小，生成的代码正确率就越高。这是 Codex 在用自己的架构设计来适配 LLM 的工作特性——也是 AI 时代系统设计最值得深思的地方。

---

## 1.5 关键数字

| 指标 | 数值 | 说明 |
|------|------|------|
| Crate 数量 | 109 | Cargo workspace members |
| 核心抽象层数 | 4 | ThreadManager → CodexThread → Session → Agent |
| 沙箱层数 | 3 | 文件系统 + 网络 + 进程 |
| 支持的 OS 平台 | 3 | Linux (Landlock+Seccomp) / macOS (Seatbelt) / Windows |
| 进程间通信方式 | 3 | Unix Domain Socket / WebSocket / stdio |
| Provider 类型 | 4+ | OpenAI / Ollama / LMStudio / ChatGPT |
| API 传输模式 | 2 | REST + WebSocket（带预暖） |
| Tool 类型 | 4 | Builtin (Shell/File/Web/ApplyPatch) / MCP / Skill / Plugin |
| 协议版本 | 2 | App Server v1 (deprecated) + v2 (active) |
| 构建系统 | 2 | Cargo (开发) + Bazel (CI/跨平台) |
| Rust Edition | 2024 | 全 workspace 统一 |
| 许可证 | Apache-2.0 | `LICENSE` |

---

## 1.6 本章要点

1. **Codex 是第三代 AI 编程工具**：从 IDE 代码补全（行级）→ IDE Agent（任务级）→ 终端 Agent 内核（会话级）。
2. **Codex 的本质是 AI 操作系统内核**：它管理上下文窗口（≈ 虚拟内存）、调度 Agent（≈ 进程调度）、隔离沙箱（≈ 用户态保护）、持久化会话（≈ 文件系统）。
3. **三层架构**：TypeScript 启动器层 → Rust 内核层（109 crate）→ SDK 层。本书聚焦 Rust 内核层。
4. **四条核心哲学**：Terminal-Native、Sandbox-First、Protocol-Driven、Anti-Bloat by Design。
5. **"Ant-Bloat by Design"是 AI 时代系统设计的关键思想**：小模块 = 低认知负荷 = 高 AI 代码质量。这不是传统的软件工程实践，而是针对 LLM 工作特性的架构适配。
