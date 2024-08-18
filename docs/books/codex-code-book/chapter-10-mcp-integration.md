# 第10章：MCP 集成——跨进程调用链的最长路径

> 源码版本：2026-05-04
> 关键文件：`codex-mcp/src/`, `rmcp-client/src/`, `core/src/mcp.rs`, `core/src/mcp_tool_call.rs`, `core/src/mcp_tool_exposure.rs`

---

## 10.1 MCP 在 Codex 架构中的位置

MCP（Model Context Protocol）是 Anthropic 提出的开放协议，用于 AI 应用与外部工具/数据源之间的标准化通信。在 Codex 中，MCP 是 Tool 系统的四大来源之一，但它的特殊性在于：**它是唯一跨越进程边界的 Tool 调用路径**。

```
Codex Session
  │
  ├─→ McpManager::call_tool(server_name, tool_name, args)
  │
  ├─→ McpConnectionManager (codex-mcp crate)
  │     │  管理所有 MCP Server 连接的生命周期
  │     │  聚合所有 Server 的工具/资源列表
  │     │  路由 tool call 到正确的 Server
  │     │
  │     └─→ AsyncManagedClient (每个 MCP Server 一个)
  │
  ├─→ rmcp-client (codex-rmcp-client crate)
  │     │  JSON-RPC 协议的 Rust 实现
  │     │  支持 stdio 和 Streamable HTTP 两种传输
  │     │
  │     └─→ 外部 MCP Server 进程
```

这个调用链跨越了 **至少两个进程**（Codex + MCP Server），涉及 JSON-RPC 序列化/反序列化、异步 I/O、超时管理。

---

## 10.2 McpConnectionManager：MCP 连接的总管家

```rust
// codex-mcp/src/connection_manager.rs:70-75
pub struct McpConnectionManager {
    clients: HashMap<String, AsyncManagedClient>,   // server_name → 客户端
    server_origins: HashMap<String, String>,         // server_name → 来源描述
    elicitation_requests: ElicitationRequestManager, // 权限诱导管理器
    startup_cancellation_token: CancellationToken,   // 启动取消令牌
}
```

`McpConnectionManager` 的设计遵循单一职责：它只管理"连接"，不关心"MCP 协议细节"（那是 rmcp-client 的职责）。

### 启动流程

```rust
// connection_manager.rs:132-199
pub async fn new(
    mcp_servers: &HashMap<String, McpServerConfig>,
    store_mode: OAuthCredentialsStoreMode,
    auth_entries: HashMap<String, McpAuthStatusEntry>,
    approval_policy: &Constrained<AskForApproval>,
    ...
) -> (Self, CancellationToken)
```

启动过程：
1. 遍历所有启用（`cfg.enabled`）的 MCP Server 配置
2. 为每个 Server 发送 `McpStartupStatus::Starting` 事件
3. 创建 `AsyncManagedClient` 并启动异步连接
4. 通过 `JoinSet` 并行管理所有 Server 的连接初始化

`DEFAULT_STARTUP_TIMEOUT` = 30 秒——如果 MCP Server 在 30 秒内没有完成初始化，连接将被标记为失败。

### 工具命名：前缀重组避免冲突

来自不同 MCP Server 的工具名称可能冲突（两个 Server 都有 `search` 工具），所以 Codex 使用前缀命名：

```rust
// codex-mcp/src/mcp/mod.rs:61-64
pub fn qualified_mcp_tool_name_prefix(server_name: &str) -> String {
    sanitize_responses_api_tool_name(&format!(
        "mcp__{server_name}__"
    ))
}
```

例如，`github` Server 的 `search_issues` 工具 → `mcp__github__search_issues`。

### 关闭流程：优雅停机

```rust
// connection_manager.rs:97-113
pub fn begin_shutdown(&mut self) -> impl Future<Output = ()> + Send + 'static {
    self.startup_cancellation_token.cancel();       // 1. 取消所有进行中的启动
    let clients = std::mem::take(&mut self.clients); // 2. 取出所有客户端
    async move {
        for client in clients.into_values() {
            client.shutdown().await;                 // 3. 逐个关闭 + 终止 stdio 进程
        }
    }
}
```

---

## 10.3 AsyncManagedClient：单 Server 连接的生命周期

```rust
// codex-mcp/src/rmcp_client.rs
const DEFAULT_STARTUP_TIMEOUT: Duration = Duration::from_secs(30);
const DEFAULT_TOOL_TIMEOUT: Duration = Duration::from_secs(120);
```

每个 MCP Server 对应一个 `AsyncManagedClient`，它管理：
- **传输建立**：stdio（子进程 stdin/stdout）或 Streamable HTTP
- **初始化握手**：发送 `InitializeRequestParams`（包含 client capabilities, protocol version）
- **工具列表获取**：`list_tools` → 应用 per-server tool filter → 格式化工具 schema
- **工具调用**：`call_tool` → 序列化参数 → JSON-RPC → 等待响应

### 传输层：stdio 与 Streamable HTTP

```rust
// 两种传输模式
McpServerTransportConfig::Stdio {
    command: String,         // 启动命令
    args: Vec<String>,      // 命令参数
    env: HashMap<...>,      // 环境变量
}

McpServerTransportConfig::StreamableHttp {
    url: String,                     // HTTP URL
    bearer_token_env_var: Option<...>, // Bearer token 环境变量
    ...
}
```

stdio 模式的优势是简单：Codex 直接启动 MCP Server 作为子进程，通过 stdin/stdout 通信。Streamable HTTP 模式适合远程 Server。

### Capability 协商

```rust
// rmcp_client.rs:67
pub const MCP_SANDBOX_STATE_META_CAPABILITY: &str = "codex/sandbox-state-meta";
```

Codex 声明自定义 capability `codex/sandbox-state-meta`。如果 MCP Server 也声明此 capability，Codex 会在每次 tool call 的 `_meta` 字段中附加 `SandboxState`，让 Server 了解当前的沙箱状态。

---

## 10.4 rmcp-client：MCP 协议的 Rust 实现

`codex-rmcp-client` crate 是对 `rmcp` crate 的高层封装，提供：

- **StdioServerLauncher**：启动和管理 MCP Server 子进程
- **RmcpClient**：发送 JSON-RPC 请求/通知，接收响应
- **Elicitation 支持**：MCP 协议的 elicitation 机制（Server 请求 Client 输入）

传输层在 `codex-rmcp-client` 中处理：
```rust
// rmcp-client/src/stdio_server_launcher.rs
// 管理子进程生命周期，包括沙箱状态传递
```

### 工具的过滤与转换

```rust
// codex-mcp/src/tools.rs
pub fn filter_tools(tools: Vec<ToolInfo>, filter: &ToolFilter) -> Vec<ToolInfo>;
pub fn tool_with_model_visible_input_schema(tool: &ToolInfo) -> Tool;
```

不是所有 MCP Server 暴露的工具都会对 Agent 可见。`ToolFilter` 可以按名称白名单/黑名单过滤工具。经过滤后，`tool_with_model_visible_input_schema()` 将 RMCP 工具格式转换为 LLM 可理解的 function schema 格式。

---

## 10.5 McpManager：连接 Core 与 MCP 的桥梁

`core/src/mcp.rs` 中的 `McpManager` 是 `codex-core` 与 `codex-mcp` 之间的接口层：

```rust
// McpManager 的主要职责：
// 1. 持有 McpConnectionManager
// 2. 提供 call_tool(server_name, tool_name, arguments) API
// 3. 提供 list_tools() / list_resources() / read_resource() 查询 API
// 4. 管理 MCP Server 生命周期事件（启动/失败/关闭）
```

### Tool Call 的完整路径

```
Agent (LLM)
  │ function_call("mcp__github__search_issues", {query: "..."})
  ▼
codex-core: Tool dispatch → MCP path
  │
  ▼
McpManager::call_tool("github", "search_issues", {query: "..."})
  │
  ▼
McpConnectionManager: 查找 "github" → AsyncManagedClient
  │
  ▼
AsyncManagedClient: JSON-RPC tools/call
  │
  ▼
MCP Server (外部进程): 执行，返回结果
  │
  ▼
结果返回到 Context，注入 conversation history
```

---

## 10.6 MCP 权限与审批

### 审批模板

MCP 工具的操作可能需要用户批准。`mcp_permission_prompt_is_auto_approved()` 决定何时自动批准：

```rust
// codex-mcp/src/mcp/mod.rs:69-80
pub fn mcp_permission_prompt_is_auto_approved(
    approval_policy: AskForApproval,
    permission_profile: &PermissionProfile,
    context: McpPermissionPromptAutoApproveContext,
) -> bool {
    if matches!(approval_policy, AskForApproval::OnRequest | AskForApproval::Granular(_))
        && context.approvals_reviewer == Some(ApprovalsReviewer::AutoReview)
        && context.tool_approval_mode == Some(AppToolApproval::Approve)
    {
        return true;  // AutoReview + Approve → 自动批准
    }
    // ...
}
```

### Codex Apps MCP Server

Codex 内建了一个特权的 MCP Server：`codex_apps`。它处理与 Codex 平台相关的集成功能（如账号管理、云端服务调用）。这个 Server 的认证与普通的 MCP Server 不同——它可以直接使用 Codex 用户认证。

---

## 10.7 Codex 的 MCP 资源系统

除了工具，MCP 协议还定义了 **资源（Resources）** 和 **资源模板（Resource Templates）**：

```rust
// codex-mcp/src/connection_manager.rs
// list_resources, read_resource, list_resource_templates
```

资源是 MCP Server 暴露的"数据端点"——Agent 可以"读取"一个资源获取结构化数据，而无需通过 tool call。这类似于 REST API 中的 GET 端点，但遵循 MCP 的 JSON-RPC 语义。

---

## 10.8 类比：微服务架构中的 API Gateway

| 微服务模式 | Codex MCP 系统 |
|-----------|---------------|
| API Gateway | McpManager（统一入口，路由分发） |
| Service Discovery | McpConnectionManager（管理所有 Server 连接） |
| Service Instance | AsyncManagedClient（每个 MCP Server 一个） |
| Health Check | McpStartupStatus 事件（Starting/Connected/Failed） |
| Circuit Breaker | DEFAULT_STARTUP_TIMEOUT + DEFAULT_TOOL_TIMEOUT |
| Request/Response | JSON-RPC over stdio/HTTP |
| API Versioning | ProtocolVersion 协商 |
| Auth Middleware | OAuthCredentialsStoreMode + bearer_token |

---

## 10.9 本章要点

1. **MCP 是唯一跨进程的 Tool 调用路径**：Session → McpManager → McpConnectionManager → AsyncManagedClient → rmcp-client → 外部 MCP Server。
2. **McpConnectionManager 管理所有 MCP 连接**：HashMap 键为 server_name，支持并行启动、独立关闭。
3. **工具名防冲突**：`mcp__<server_name>__<tool_name>` 前缀格式。
4. **两种传输模式**：stdio（子进程管道，简单）和 Streamable HTTP（远程，灵活）。
5. **自定义 Capability**：`codex/sandbox-state-meta` 用于向 MCP Server 传递沙箱状态。
6. **权限有审批模板**：支持 AutoReview + Approve 自动批准、默认需用户确认。
7. **Codex Apps 是特权 MCP Server**：内建于系统，使用 Codex 用户认证。
