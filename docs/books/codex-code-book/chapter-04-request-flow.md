# 第4章：从按键到 API 请求——前端到后端的请求流

> 源码版本：2026-05-04
> 关键文件：`cli/src/main.rs`, `tui/src/lib.rs`, `tui/src/app.rs`, `app-server/src/message_processor.rs`, `app-server/src/thread_state.rs`

---

## 4.1 总览：一次用户输入的旅程

用户敲下回车，Codex 内部发生了什么？我们追踪"从输入到 LLM API 请求发出"的完整路径：

```
用户按键
  │
  ▼
crossterm 事件流 (PollEvent::Key)
  │
  ▼
TUI 事件循环 (run_main → app.run())
  │
  ▼
AppEvent::ChatMsg("fix the bug")
  │
  ▼
AppServerSession → AppServerClient
  │
  ▼
JSON-RPC: {"method": "thread/submit", "params": {"op": "UserTurn", ...}}
  │           ← 如果是 UDS，走 Unix Domain Socket
  │           ← 如果是 remote，走 WebSocket
  ▼
App Server MessageProcessor
  │
  ▼
ThreadManager::send_op(thread_id, Op::UserTurn { ... })
  │
  ▼
CodexThread::submit(op)
  │
  ▼
Session(Codex) 内部处理
  │       │
  │       ├─→ Context 装配 (第5章)
  │       ├─→ Agent 启动
  │       └─→ ModelClient::stream() → LLM API 请求 (第6章)
  │
  ▼
SSE 事件流回流（反向路径）
```

这个流程跨越了三个异步边界、两次序列化/反序列化、至少一次进程间通信。理解这条路径是理解 Codex 架构的关键。

---

## 4.2 起点：TUI 事件循环

### 双进程模式 vs 内嵌模式

Codex TUI 有两种运行模式：

**模式一：独立进程（默认）**。TUI 是独立进程，App Server 是独立进程，通过 UDS 或 WebSocket 通信。

```rust
// tui/src/lib.rs — run_main 内部
// 启动 App Server 子进程
// TUI 通过 AppServerClient 连接
```

**模式二：内嵌模式（测试/特殊场景）**。App Server 和 TUI 运行在同一个进程内：

```rust
// app-server/src/in_process.rs + app_server_client InProcessAppServerClient
// 两者通过内存 channel 通信，跳过序列化
```

本书主要讨论模式一（独立进程），因为只有它涉及真正的 IPC。

### TUI 的主循环

```rust
// tui/src/app.rs — run loop skeleton
impl App {
    pub async fn run(&mut self) -> AppExitInfo {
        loop {
            // 1. 拉取 TUI 事件
            let event = self.tui.next().await;
            // 2. App Server 事件（异步回调）
            while let Ok(event) = self.app_server_rx.try_recv() {
                // 处理 App Server 发送的事件
            }
            // 3. 渲染
            self.draw_frame(&mut terminal)?;
        }
    }
}
```

事件循环是经典的"事件 → 更新状态 → 渲染"模式：

1. **输入事件**（键盘、鼠标、粘贴）从 `crossterm::event::EventStream` 来
2. **App Server 事件**（模型响应、权限请求、通知）从 `mpsc::Receiver` 来
3. **渲染**：ratatui 将状态树渲染到终端缓冲区，然后 flush

### CLI 多入口：arg0 分发

`cli/src/main.rs` 中没有任何业务逻辑——它只做命令分发：

```rust
// cli/src/main.rs:730-735
fn main() -> anyhow::Result<()> {
    arg0_dispatch_or_else(|arg0_paths: Arg0DispatchPaths| async move {
        cli_main(arg0_paths).await?;
        Ok(())
    })
}
```

`arg0_dispatch_or_else` 检查 `argv[0]`（即 `arg0`）的名字，如果它匹配某个预定义的平台相关名称（如 `codex-x86_64-unknown-linux-musl`），就直接执行对应的子命令（如 Linux Sandbox），而不需要用户显式指定。这就是"一个二进制，多个入口"的模式。

然后 `cli_main` 匹配 `subcommand` 分发：
- `None` → `run_interactive_tui(...)`（默认交互模式）
- `Some(Exec(...))` → `codex_exec::run_main(...)`（非交互模式）
- `Some(AppServer(...))` → `codex_app_server::run_main_with_transport(...)`（App Server 模式）
- 其他十几个子命令...

---

## 4.3 用户提交：从文本到 Op

### 输入框（Chat Composer）

TUI 的输入组件在 `bottom_pane/chat_composer.rs`，负责：

- 多行文本编辑
- `@` 提及语法解析（plugin/tool/skill mentions）
- Bracketed Paste 处理
- 文件路径拖放

当用户按下回车：

```rust
// 简化：AppEvent::ChatMsg 被发送
let text = composer.take_text();
self.event_tx.send(AppEvent::ChatMsg(text));
```

### AppEvent 到 Op

在 `App` 的事件处理中，`ChatMsg` 被转换为 `Op::UserTurn`：

```rust
match event {
    AppEvent::ChatMsg(text) => {
        // 解析提及 (@plugin, @tool, @skill)
        // 检查是否需要触发 Skill
        let op = Op::UserTurn {
            submission: Submission::UserText { text, images, ... },
            // 环境选择、审批策略覆盖等
        };
        self.app_server_session.submit_op(op).await;
    }
}
```

这里有一个重要的设计：**TUI 不直接调用 `codex-core` 的任何 API**。它只构造 `Op`（协议层类型），交给 `AppServerSession` 转发。TUI 对 "LLM 是什么"、"Context 怎么装配" 一无所知。

### Op 枚举：所有操作的统一类型

```rust
// protocol/src/protocol.rs
pub enum Op {
    UserTurn { submission: Submission, ... },   // 用户文本输入
    Interrupt,                                    // 用户中断
    Approve { ... },                             // 用户批准操作
    Reject { ... },                              // 用户拒绝操作
    RefreshMcpServers { config: ... },           // 刷新 MCP Server
    Shutdown,                                    // 关闭
    // ...
}
```

Op 是对 Codex Session 的所有可能操作的枚举。这是一种 **Actor Model** 风格的设计——`CodexThread` 就像一个 Actor，通过消息（Op）驱动，有自己的内部状态，外部只能通过发消息来控制它。

---

## 4.4 App Server 处理：MessageProcessor

### 消息入口

App Server 收到一条 JSON-RPC 请求后，进入 `MessageProcessor::process_message()`：

```rust
// app-server/src/message_processor.rs
impl MessageProcessor {
    pub(crate) async fn process_message(
        &self,
        connection_id: ConnectionId,
        message: JSONRPCMessage,
    ) {
        match message {
            JSONRPCMessage::Request(request) => {
                let method = request.method.as_str();
                match method {
                    "thread/submit" => {
                        // 验证参数
                        // 调用 ThreadManager::send_op()
                        // 返回 response 给 connection
                    }
                    "thread/read" => { ... }
                    "config/read" => { ... }
                    "models/list" => { ... }
                    // ... 几十个 API 方法
                }
            }
            JSONRPCMessage::Notification(notification) => {
                match notification.method.as_str() {
                    "initialized" => {
                        // 标记连接为已初始化
                    }
                    // ...
                }
            }
            JSONRPCMessage::Response(_) => {
                // 服务器端通常不接收 Response（Response 是客户端收的）
            }
        }
    }
}
```

每个 RPC 方法的处理遵循同一模式：
1. 解析 `params` 
2. 调用 ThreadManager 或 ConfigManager
3. 构造 Response 或 Error
4. 通过 connection 发送回去

### ThreadState：连接与 Thread 的关联

```rust
// app-server/src/thread_state.rs
pub(crate) struct ThreadState {
    thread_id: ThreadId,
    connection_id: ConnectionId,  // ← 绑定了哪个连接
    // ...
}
```

每个连接可以关联多个 Thread，每个 Thread 只关联一个连接。当一个连接断开时，它关联的所有 Thread 被自动清理。

### RPC Gate 的并发控制

```rust
// app-server/src/connection_rpc_gate.rs — 回顾第2章
// 每个连接有一个 RPC Gate，控制并发 handler 的启动和关闭
```

重要：MessageProcessor 是**单线程事件循环**处理所有连接的消息，但每个 RPC handler 的执行（实际业务逻辑）是在独立的 tokio task 中并发运行的。Gate 负责在连接关闭时阻止新的 handler 启动。

---

## 4.5 Exec CLI：非交互的请求路径

`codex exec` 是 Codex 的非交互模式。它跳过了整个 TUI 渲染管线，直接把文本传给 App Server：

```rust
// exec/src/main.rs 或类似
// 构造 Config → start_thread_with_tools → submit(Op::UserTurn)
// 等待所有事件 → 输出结果 → 退出
```

Exec 模式的关键差异：
- 没有 TUI 进程（直接 link `codex-core`）
- 没有 App Server 进程（直接创建 `ThreadManager`）
- 输出是普通 JSON（`--json` 标志时）或 Markdown

这是"无前端"的 Codex——最简路径，延迟最低。

---

## 4.6 调试视角：追踪一次请求

如果你想在本地追踪一次请求的完整路径，以下 tracing target 是关键：

```
RUST_LOG=codex_app_server=debug codex_tui=debug  codex
```

关键的 span 边界：

1. **TUI 端**：`tui::app::run` span → 事件处理
2. **发送**：`app_server_client::send_request` → 序列化 + 发送
3. **App Server 端**：`app_server::message_processor::process_message` → 收到 + 路由
4. **Core 端**：`codex_core::session` → 实际的 Session 处理

还可以使用 `codex debug prompt-input "test query"` 来查看实际发送到 LLM 的 prompt 内容——不发起实际 API 调用，只输出构造好的 prompt JSON。

---

## 4.7 设计启示

这条请求路径展示了 Codex 架构的若干设计原则：

### 关注点分离：TUI 不"懂" LLM

TUI 只知道 `Op` 枚举，不知道 `Prompt`、`Token`、`ModelProvider`。这种分离意味着：
- 可以替换前端（TUI → VS Code → Web）而不改动核心
- TUI 可以被完全移除（Exec 模式）
- 协议成了清晰的契约边界

### Actor Model：消息驱动的异步架构

`CodexThread::submit(op)` → Agent Mailbox → Agent 处理。外部无法直接操作 Session 内部状态，只能通过 Op 消息来间接控制。这是 Elixir/Erlang 的 Actor Model 在 Rust 中的体现。

### "先协议，后实现"

AGENTS.md 中反复强调"API 开发在 app-server v2 进行"，并要求先定义 wire format（`#[ts(export_to)]`, `#[serde(tag = "type")]`），再实现业务逻辑。这保证了跨语言（Rust↔TypeScript）的兼容性。

---

## 4.8 本章要点

1. **TUI 事件循环**：crossterm 键盘事件 + App Server 消息 channel → 状态更新 → ratatui 渲染。
2. **arg0 分发**：一个二进制，十几个入口，通过 argv[0] 名称自动选择子命令。
3. **从输入到 Op**：用户文本 → `AppEvent::ChatMsg` → 提及解析 → `Op::UserTurn` → `AppServerClient` → JSON-RPC 发送。
4. **App Server MessageProcessor**：单线程分发，异步 handler 执行。每个 RPC 方法对应一个处理分支。
5. **非交互模式（Exec）**：跳过 TUI 和 App Server，直接 link `codex-core`，最简路径。
6. **设计原则**：关注点分离（TUI 不懂 LLM）、Actor Model（Op 消息驱动）、先协议后实现。
