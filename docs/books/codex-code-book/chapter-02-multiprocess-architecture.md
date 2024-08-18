# 第2章：多进程架构与进程间通信

> 源码版本：2026-05-04
> 关键文件：`app-server/src/lib.rs`, `app-server/src/transport.rs`, `app-server-transport/src/transport/mod.rs`, `stdio-to-uds/src/lib.rs`, `app-server/src/connection_rpc_gate.rs`

---

## 2.1 为什么 Codex 是多进程的？

如果你写过 Spark/StarRocks 这样的分布式系统，你对"一个 Driver 进程 + 多个 Executor 进程"的架构一定不陌生。Codex 在单机上同样选择了多进程架构。

一个自然的问题是：**为什么不在一个进程里搞定所有事情？**

答案是三重的：

### 感知说：TUI 渲染需要独占线程

ratatui 的渲染管线（crossterm 事件流 → ratatui Frame 渲染 → 终端 write）需要一个不被阻塞的事件循环。如果这个循环同时还承担 LLM API 调用的等待（可能长达数十秒）、Shell 命令执行的阻塞（可能数分钟），用户界面就会彻底卡死。

### 安全说：沙箱需要独立进程边界

当 AI 生成 `rm -rf /` 并试图执行时，你不能用"线程隔离"来应对。操作系统级别的沙箱（Landlock/Seatbelt/Seccomp）作用于进程——沙箱是进程的属性，不是线程的属性。`codex-linux-sandbox` 本身就是一个独立的可执行文件（`arg0_paths.codex_linux_sandbox_exe`），Codex 通过 fork+exec 方式把它作为子进程启动。

### 演进说：多 Client 支持需要中心化服务

Codex 需要支持多种客户端同时连接——TUI（终端）、VS Code 扩展（IDE）、Desktop App——它们通过同一个 App Server 来管理共享的状态（认证、配置、模型目录）。这需要一个独立于渲染的服务进程。

```
┌──────────┐   ┌──────────────┐   ┌───────────┐
│ TUI 进程  │   │ VS Code 扩展  │   │ Desktop App│
│ (Rust)   │   │ (TypeScript) │   │  (Electron) │
└────┬─────┘   └──────┬───────┘   └─────┬─────┘
     │                │                 │
     │  JSON-RPC      │  JSON-RPC       │  JSON-RPC
     │  over UDS/WS   │  over stdio     │  over WS
     │                │                 │
     └────────────────┼─────────────────┘
                      │
              ┌───────┴─────────┐
              │   App Server     │
              │  (独立进程)       │
              │                  │
              │ ┌──────────────┐ │
              │ │MessageProcessor││
              │ │ ConfigManager │ │
              │ │ ThreadManager │ │
              │ └──────────────┘ │
              └───────┬─────────┘
                      │
            ┌─────────┼─────────┐
            │         │         │
      ┌─────┴──┐ ┌───┴───┐ ┌──┴──────────┐
      │ Exec   │ │ MCP   │ │ Exec Server  │
      │(子进程) │ │Server │ │ (守护进程)    │
      └────────┘ └───────┘ └─────────────┘
```

### 类比 OS 视角：微内核架构

Codex 的进程拓扑非常类似一个**微内核操作系统**：

| 微内核概念 | Codex 对应 | 实现 |
|-----------|-----------|------|
| 微内核（消息总线） | App Server | `app-server/` |
| 用户态驱动（渲染） | TUI 进程 | `tui/` |
| 用户态驱动（批处理） | Exec CLI | `exec/` |
| 用户态服务 | MCP Server / Exec Server | `mcp-server/`, `exec-server/` |
| IPC 通道 | UDS / WebSocket / stdio | `app-server-transport/` |
| 能力令牌 | Auth Token / API Key | `login/`, `app-server-transport/src/transport/auth.rs` |

App Server 就是那个"微内核"——它不做任何"用户可见"的工作（不渲染 UI、不调用 LLM），它只做一件事：**路由消息**。你把请求发给它，它把响应发回给你。所有的"业务逻辑"都在 `codex-core` 库中，但 `codex-core` 是一个库（lib），不是进程——实际的进程调度在 App Server 和 TUI/CLI 之间完成。

---

## 2.2 Transport 层：三种通信方式的统一抽象

Transport 层的核心概念抽象在 `AppServerTransport` 枚举中：

```rust
// app-server-transport/src/transport/mod.rs:52-58
pub enum AppServerTransport {
    Stdio,
    UnixSocket { socket_path: AbsolutePathBuf },
    WebSocket { bind_address: SocketAddr },
    Off,
}
```

四种模式（包括 Off），三种真正的通信方式：

### Stdio Transport：最简单的入参

```rust
// app-server-transport/src/transport/stdio.rs
pub async fn start_stdio_connection(...) -> JoinHandle<()>
```

当 VS Code 扩展启动 Codex App Server 时，它使用 `stdio://`——父进程（VS Code）通过子进程（App Server）的标准输入/输出发送 JSON-RPC 消息。每一行是一个完整的 JSON 对象，用换行符分隔。

这是最简单的通信方式，因为：
- 不需要端口号
- 不需要文件路径
- 进程边界天然提供了连接生命周期管理——子进程退出，连接就断了

### Unix Domain Socket Transport：本地高性能 IPC

```rust
// app-server-transport/src/transport/unix_socket.rs
pub async fn start_control_socket_acceptor(...) -> JoinHandle<()>
```

对于 TUI 进程和 App Server 进程之间的通信，Codex 使用 Unix Domain Socket。socket 文件位于：

```
$CODEX_HOME/app-server-control/app-server-control.sock
```

为什么是 UDS？
- **性能**：UDS 是内核级别的字节流，不经过 TCP 协议栈。内存拷贝量远小于 TCP loopback。
- **安全**：UDS 的访问控制依赖文件系统权限——只有能访问 socket 文件的进程才能连接。不需要额外的认证 token。
- **语义清晰**：socket 文件的存在 = "App Server 正在运行"，删除 = "App Server 已停止"。

`stdio-to-uds` crate 是一个精巧的适配器：

```rust
// stdio-to-uds/src/lib.rs:12-46
pub async fn run(socket_path: &Path) -> anyhow::Result<()> {
    let stream = UnixStream::connect(socket_path).await?;
    let (mut socket_reader, mut socket_writer) = tokio::io::split(stream);

    let copy_socket_to_stdout = async {
        let mut stdout = tokio::io::stdout();
        tokio::io::copy(&mut socket_reader, &mut stdout).await?;
        stdout.flush().await?;
        Ok(())
    };
    let copy_stdin_to_socket = async {
        let mut stdin = tokio::io::stdin();
        tokio::io::copy(&mut stdin, &mut socket_writer).await?;
        // ...
    };

    tokio::try_join!(copy_stdin_to_socket, copy_socket_to_stdout)?;
    Ok(())
}
```

这个 46 行的函数实现了 stdin/stdout ↔ UDS 的双向转发。它是 `codex app-server proxy` 子命令的实现。设计哲学：**每个组件只做一件事，用 pipeline 组合。**

### WebSocket Transport：远程/云场景

```rust
// app-server-transport/src/transport/websocket.rs
pub async fn start_websocket_acceptor(...) -> JoinHandle<()>
```

当使用 `--remote ws://host:port` 时，TUI 连接到远程的 App Server。这需要认证层（auth module）：

```rust
// app-server-transport/src/transport/auth.rs
pub fn policy_from_settings(...) -> ...
```

WebSocket transport 支持三种认证模式：
- **无认证**（仅 localhost）
- **Capability Token**：预分发的静态 token（`--ws-token-file`）
- **Signed Bearer Token**：带签名的 JWT（`--ws-shared-secret-file` + `--ws-issuer` + `--ws-audience`）

---

## 2.3 App Server Protocol：类型安全的 JSON-RPC

`app-server-protocol` crate 定义了进程间对话的全部"词汇"。这是 Codex 中除 `codex-core` 外最需要理解的 crate。

### 消息类型

```rust
// app-server-protocol 中的核心消息枚举
JSONRPCMessage {
    Request(JSONRPCRequest),       // 客户端 → 服务器："请做某事"
    Response(JSONRPCResponse),     // 服务器 → 客户端："这是结果"
    Notification(JSONRPCNotification), // 服务器 → 客户端："发生了一件事"
}
```

与标准 JSON-RPC 2.0 的差异：
- **没有客户端 Notification**（客户端不发通知，只发请求）
- **`trace` 字段**附加在 Request 上，用于 W3C Trace Context 传播
- **`experimental_api` 标记**用于渐进式 API 发布

### v1 → v2 演进

AGENTS.md 明确规定：

> All active API development should happen in app-server v2. Do not add new API surface area to v1.

v1 是早期版本，存在但不扩展。v2 的命名规范：

- `*Params` — 请求参数（客户端→服务器）
- `*Response` — 响应（服务器→客户端）
- `*Notification` — 通知（服务器→客户端，无 id）

RPC 方法命名：`resource/method`，resource 保持单数形式。例如：
- `thread/read`
- `app/list`
- `config/read`

### Wire Format 规范

```rust
// camelCase on the wire:
#[serde(rename_all = "camelCase")]

// 例外：config RPC 使用 snake_case 以匹配 config.toml 的 key 格式

// optional 字段在 Params 中:
#[ts(optional = nullable)]

// 时间戳：整数 Unix 秒
created_at: i64
```

### Experimental API 机制

```rust
// 标记实验性方法/字段
#[experimental("method/or/field")]

// 运行时检查
if !experimental_api_enabled {
    params.strip_experimental_fields();
}
```

这个设计非常精妙：**实验性 API 在 protocol 层就做了类型级别的标记**，而不是依赖文档说明。"API 是否可用"变成了编译时+运行时的双重保证。在 transport 层的消息过滤中（`transport.rs:165-187`），如果连接没有开启实验功能，实验性字段会在序列化前被自动剥离。

---

## 2.4 消息路由引擎：连接管理与背压

Transport 层不只是"收发消息"，它有一套完整的连接管理和背压控制机制。

### 连接生命周期

```
ConnectionOpened
    │
    ├─→ initialized: false (等待客户端发送 "initialized" 通知)
    │
    ├─→ initialized: true (开始处理业务请求)
    │
    ├─→ 消息循环: TransportEvent::IncomingMessage
    │       │
    │       └─→ enqueue_incoming_message() → transport_event_tx
    │
    └─→ ConnectionClosed (客户端断开 或 背压触发断开)
```

### 背压控制：不丢弃响应，可丢弃请求

```rust
// app-server-transport/src/transport/mod.rs:205-243
async fn enqueue_incoming_message(...) -> bool {
    match transport_event_tx.try_send(event) {
        Ok(()) => true,                                  // 正常入队
        Err(Closed) => false,                             // 通道已关闭
        Err(Full(JSONRPCMessage::Request(request))) => {  // ★ 请求超载
            // 返回 overload 错误（不丢失）
            let overload_error = OutgoingMessage::Error(OutgoingError {
                id: request.id,
                error: JSONRPCErrorError {
                    code: -32001,       // OVERLOADED
                    message: "Server overloaded; retry later.".to_string(),
                    ...
                },
            });
            // 尝试发送 overload 错误...
        }
        Err(Full(event)) => transport_event_tx.send(event).await,  // ★ 非请求则等待
    }
}
```

这段代码展示了一个精心设计的背压策略：

1. **请求（Request）超载时**：不等待，立即返回 `-32001` 错误。客户端可以重试。这保证了服务器不会因为队列满而阻塞，也不会丢失请求（因为客户端知道它失败了）。
2. **响应（Response）超载时**：**等待**（`.await`）。响应必须送达——如果丢弃了响应，客户端会永远挂起等待。
3. **通知（Notification）超载时**：**等待**——通知反映了服务器状态变化（如 config 更新），同样不应丢弃。

通道容量是 `CHANNEL_CAPACITY = 128`——"在吞吐量和内存之间平衡，128 条消息对一个交互式 CLI 已经足够"。

### 消息路由：点对点 vs 广播

```rust
// app-server/src/transport.rs:189-228
pub(crate) async fn route_outgoing_envelope(envelope: OutgoingEnvelope, ...) {
    match envelope {
        OutgoingEnvelope::ToConnection { connection_id, message, ... } => {
            // 点对点：发到指定连接
            send_message_to_connection(connections, connection_id, message, ...).await;
        }
        OutgoingEnvelope::Broadcast { message } => {
            // 广播：发到所有已初始化的连接
            for connection_id in target_connections {
                send_message_to_connection(connections, connection_id, message.clone(), ...).await;
            }
        }
    }
}
```

这对应了 OS 中 IPC 的两种模式：**直接通信（direct message passing）** 和 **组播（multicast）**。

### ConnectionRpcGate：优雅关闭

```rust
// app-server/src/connection_rpc_gate.rs:16-48
impl ConnectionRpcGate {
    pub(crate) async fn run<F: Future<Output = ()>>(&self, future: F) {
        let token = {
            let accepting = self.accepting.lock().await;
            if !*accepting { return; }  // 门已关闭，拒绝新任务
            self.tasks.token()           // 登记任务
        };
        future.await;                    // 执行
        drop(token);                     // 注销任务
    }

    pub(crate) async fn shutdown(&self) {
        *self.accepting.lock().await = false;  // 关上门
        self.tasks.close();                     // 不再接受新任务
        self.tasks.wait().await;                // 等待所有在途任务完成
    }
}
```

这是 `tokio_util::TaskTracker` 的经典用法：关闭时不是暴力终止，而是**拒新等旧**——新请求被拒绝，已经在执行的请求被允许完成。这保证了状态的完整性。

---

## 2.5 与分布式系统的类比

如果你是 Spark/StarRocks 工程师，这个架构会让你特别熟悉：

| 分布式系统概念 | Codex 对应 |
|--------------|-----------|
| Driver 进程 | App Server |
| Executor 进程 | TUI / CLI / Exec |
| RPC 框架 (gRPC/Thrift) | App Server Protocol (JSON-RPC) |
| 服务发现 | Unix Domain Socket 文件 |
| 认证 | AuthManager / WebSocket Auth |
| Backpressure | CHANNEL_CAPACITY (128) + overload error (-32001) |
| Graceful Shutdown | ConnectionRpcGate |
| Heartbeat / Ping | WebSocket ping/pong |

但有一个根本差异：**分布式系统做背压是因为"下游慢"，Codex 做背压是因为"LLM 慢"**。当 LLM 的 API 响应延迟从 2s 飙升到 30s 时，前端的消息队列不会被撑爆——因为请求已经在 App Server 层被反压了。

---

## 2.6 本章要点

1. **Codex 是多进程架构**，原因三重：TUI 渲染需独占、沙箱需进程边界、多 Client 需中心化服务。
2. **App Server 是微内核**：不执行业务逻辑，只路由消息。业务逻辑在 `codex-core` 库中。
3. **Transport 层提供三种通信方式**：stdio（IDE 集成）、UDS（本地 IPC）、WebSocket（远程/云）。`AppServerTransport` 枚举是统一抽象。
4. **App Server Protocol 是强类型的 JSON-RPC**：v1/v2 分治、experimental API 标记、严格的 wire format 规范。
5. **背压控制遵循"不丢弃响应，可丢弃请求"原则**：请求超载返回 `-32001`，响应超载则等待。
6. **ConnectionRpcGate 实现优雅关闭**：拒新等旧，保证状态完整性。
