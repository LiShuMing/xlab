# 第6章：Model Client——与 LLM 的对话协议

> 源码版本：2026-05-04
> 关键文件：`core/src/client.rs`, `core/src/client_common.rs`, `codex-api/src/`, `model-provider/src/`, `login/src/`

---

## 6.1 多 Provider 架构：一个接口，多种实现

Codex 不绑定任何一家 LLM 厂商。它通过 `ModelProvider` trait 实现多 Provider 支持：

```rust
// model-provider/src/ + model-provider-info/src/
pub struct ModelProviderInfo {
    pub id: String,
    pub name: String,
    // ...
}
```

支持的 Provider 类型（`codex-api/src/` 中实现）：

| Provider | 接口 | 关键 Crate |
|----------|------|-----------|
| OpenAI | Responses API (REST + WebSocket) | `codex-api` (默认) |
| Ollama | 本地 OpenAI-compatible API | `ollama/` |
| LMStudio | 本地 OpenAI-compatible API | `lmstudio/` |
| ChatGPT | ChatGPT API | `chatgpt/` |

每个 Provider 都实现一个共同的 trait（如 `AuthProvider`、`ResponsesClient`），上层 `ModelClient` 通过 `Arc<dyn Trait>` 使用它们。这是经典的策略模式——Provider 是可替换的运行时实现。

---

## 6.2 Auth 流程：认证链

```rust
// login/src/ + login/src/default_client.rs
pub struct AuthManager { ... }
pub struct CodexAuth { ... }
```

Codex 支持四种认证方式：

```
认证方式       来源                    流程
─────────────────────────────────────────────────
ChatGPT 登录  浏览器 OAuth            run_login_with_chatgpt()
API Key       stdin pipe             printenv KEY | codex login --with-api-key
Agent Identity stdin pipe            codex login --with-agent-identity
Device Code   设备授权码              run_login_with_device_code()
```

`AuthManager` 是共享的（`Arc<AuthManager>`），被所有 Thread 共用。这保证了 Token 刷新是全局性的——不会出现每个 Thread 独立刷新产生竞态。

### Token 刷新与恢复

```rust
// client.rs:68-70
pub enum RefreshTokenError { ... }
pub enum UnauthorizedRecovery { ... }
```

当 API 返回 401，`ModelClient` 进入 `UnauthorizedRecovery` 流程：
1. 尝试刷新 Token
2. 如果刷新失败，标记 AuthManager 为"需要重新认证"
3. 返回错误给上层，让用户看到登录提示

这个流程有一个重要保证：**重试只发生一次**。不会出现无限重试的雪崩。

---

## 6.3 Responses API：HTTP vs WebSocket 双模传输

`ModelClient` 支持两种访问 LLM 的传输模式：

### REST (SSE over HTTP POST)

```
POST /v1/responses
Body: { "model": "gpt-5.1", "input": [...], "stream": true }
→ SSE 事件流
```

这是最传统的方式。优势是简单，所有 HTTP 基础设施（代理、负载均衡、缓存）都支持。

### WebSocket

```
WS CONNECT /v1/realtime/responses
→ { "type": "response.create", "response": { ... } }
← 事件流在同一连接中返回
```

WebSocket 的优势：
- **更低的延迟**：无需每次请求都握手（TLS 握手 ~1-2 RTT）
- **连接复用**：多个 Turn 可以复用同一连接
- **Prewarm**：可以提前"预热"连接（见 6.4）

### 两种模式的统一抽象

```rust
// client.rs — ModelClientSession 封装了传输细节
pub struct ModelClientSession {
    // 内部可能持有 HTTP client 或 WS connection
    // 外部调用者不需要关心
}
```

`async fn stream(...) -> ResponseStream` 对调用者透明——调用者只需要知道"给我一个响应流"，不需要知道底层是 HTTP 还是 WebSocket。

---

## 6.4 WebSocket Prewarm：连接预热

WebSocket 预热是 Codex 最有巧思的性能优化之一：

```rust
// client.rs:16-19 — doc comment
// WebSocket prewarm is a v2-only `response.create` with `generate=false`;
// it waits for completion so the next request can reuse the same
// connection and `previous_response_id`.
```

预热流程：
```
Turn 开始
  │
  ├─→ 可选: WS Prewarm (generate=false, 不产生输出)
  │     │
  │     ├─→ WS 连接建立
  │     ├─→ 发送 response.create { generate: false }
  │     └─→ 等待 completion (不消耗推理资源)
  │
  ├─→ 正请求: response.create { generate: true }
  │     │
  │     └─→ 复用预热的 WS 连接 + previous_response_id
  │
  └─→ 后续 Turn 复用同一连接...
```

预热解决了 WS 的"冷启动"问题——首次使用 WS 时需要建立连接（TLS + HTTP Upgrade），这个延迟（~100-300ms）对交互式 CLI 来说是不可忽视的。通过将连接建立提前到 Turn 执行的最开始（甚至上一个 Turn 的末尾），用户感知到的延迟趋近于零。

### 预热失败的容错

```rust
// client.rs:23-24
// WebSocket prewarm is treated as the first websocket connection attempt
// for a turn. If it fails, normal stream retry/fallback logic handles
// recovery on the same turn.
```

预热是 best-effort——失败了不影响正常请求。正常请求的 retry 逻辑会自动使用 HTTP fallback。

---

## 6.5 传输容错：重试预算与降级

```rust
// client.rs:21-23
// Retry-Budget Tradeoff: WebSocket prewarm is treated as the first
// websocket connection attempt for a turn. If it fails, normal stream
// retry/fallback logic handles recovery.
```

传输容错策略：

1. **重试预算**：每个 Turn 有固定数量的重试机会。Prewarm 也消耗一次预算。
2. **降级链**：WebSocket → HTTP → 错误返回。不会无限重试。
3. **Fallback State**：`ModelClient` 内部维护一个"传输健康状态"——如果 WS 连续失败 N 次，后续 Turn 自动降级到 HTTP，不用等每次 WS 连接超时。
4. **Sticky Routing**：通过 `x-codex-turn-state` header 实现粘性路由——同一个 Turn 的多次请求发送到同一个后端节点，确保服务端状态一致。

---

## 6.6 流式解析：从 SSE 到结构化事件

```rust
// client_common.rs
pub type ResponseStream = ...;
pub enum ResponseEvent {
    ResponseCreated(...),
    TextDelta(...),
    FunctionCall(...),
    Completed(...),
    // ...
}
```

Codex 对 SSE 事件流的处理流程：

```
HTTP/WS 字节流
  │
  ├─→ eventsource-stream / tokio-tungstenite  → 文本行
  │     │
  │     └─→ "data: {\"type\": \"response.created\", ...}\n\n"
  │
  ├─→ serde_json::from_str → ResponseItem
  │
  ├─→ stream_events_utils::parse_event → 内部事件
  │     │
  │     └─→ 分类：ResponseCreated | TextDelta | FunctionCall | ...
  │
  └─→ codex-utils-stream-parser → ResponseEvent 流
```

`ResponseStream` 实现了 `futures::Stream` trait——上层代码可以通过 `stream.next().await` 逐个消费事件。这是一种"推转拉"的设计——异步事件流被转换为 async Stream。

### 事件速率控制

```rust
// core/src/stream_events_utils.rs
pub(crate) mod stream_events_utils {
    // 处理事件的节流、批量、渲染触发器
}
```

TUI 不需要每个 TextDelta 都重新渲染——`stream_events_utils` 提供了合并相邻 TextDelta 的逻辑，将渲染频率控制在可接受的范围内（通常 ~30-60fps）。

---

## 6.7 类比：Model Client = 网络 I/O 子系统

| OS 网络栈 | Codex Model Client |
|-----------|-------------------|
| TCP 连接管理 | WS 连接管理（connect/reconnect/prewarm） |
| HTTP 协议栈 | Responses API（请求格式/流式解析） |
| 路由表 | Model Catalog（哪个 model 走哪个 endpoint？） |
| 拥塞控制 | Rate Limiting（token 使用量限制） |
| Keep-alive | WS Prewarm + 连接复用 |
| 数据链路层重传 | Retry Budget + Fallback |

---

## 6.8 本章要点

1. **多 Provider 策略模式**：OpenAI/Ollama/LMStudio/ChatGPT，通过 `Arc<dyn Trait>` 可替换。
2. **四种认证方式**：ChatGPT OAuth、API Key stdin、Agent Identity、Device Code。
3. **HTTP + WebSocket 双模传输**：WS 延迟更低，HTTP 兼容性更好。`ModelClientSession` 封装传输细节。
4. **WS Prewarm 是核心优化**：使用 `generate=false` 预热连接，消除冷启动延迟。
5. **传输容错**：重试预算 + 降级链（WS→HTTP→错误）+ Sticky Routing。
6. **流式解析**：SSE 字节流 → `ResponseEvent` Stream，合并 TextDelta 优化渲染频率。
