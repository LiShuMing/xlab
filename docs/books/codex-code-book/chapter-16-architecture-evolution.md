# 第16章：架构演进——从 v1 到 v2 的迁移之路

> 源码版本：2026-05-04
> 关键文件：协议层级中的新旧类型别名、`app-server-transport/`、`core/src/` 中的 deprecated 标注

---

## 16.1 演进的设计原则

Codex 项目展示了几个关键的架构演进原则：

### 原则一：渐进式弃用，不是打破性重写

```rust
// core/src/lib.rs
#[deprecated = "Use ThreadManager instead"]
pub type ConversationManager = ThreadManager;

#[deprecated = "Use CodexThread instead"]
pub type CodexConversation = CodexThread;
```

旧的类型名通过 `#[deprecated]` + 类型别名保留，编译器会给出警告但不阻止编译。使用者有充足的时间迁移。这比直接删除旧 API 要友好得多。

### 原则二：协议层向后兼容

新协议版本的消息格式中保留了对旧的字段名的兼容性：

```rust
#[serde(alias = "old_field_name")]  // 旧名字仍然可以反序列化
pub new_field_name: String,
```

`serde(alias)` 允许新版本代码接收旧格式的消息——发送方可能还是旧版本，但接收方已升级。

### 原则三：Config Layer Stack 多层覆盖

配置系统使用 ConfigLayerStack 实现多级配置合并。新的配置层可以叠加在旧层之上，而不是替换。这允许新旧配置共存。

---

## 16.2 关键架构变迁

### SandboxPolicy → PermissionProfile

旧版使用扁平的 `SandboxPolicy` 枚举（4 个变体），新版使用 `PermissionProfile`（3 个变体带结构化子字段）。迁移策略：

```rust
// protocol/src/models.rs
pub fn to_legacy_sandbox_policy(&self, cwd: &Path) -> io::Result<SandboxPolicy> {
    // PermissionProfile → SandboxPolicy 的兼容转换
}

pub fn from_legacy_sandbox_policy_for_cwd(policy: &SandboxPolicy, cwd: &Path) -> Self {
    // SandboxPolicy → FileSystemSandboxPolicy 的反向转换
}
```

双向转换函数保证新旧代码可以互操作。旧版 Client 发送 `SandboxPolicy`，新版 Server 可以理解；新版 Client 发送 `PermissionProfile`，旧版 Server 也能降级处理。

### Thread/Conversation 重命名

早期 API 使用 "Conversation" 概念，后来统一为 "Thread"。改名策略：
1. 添加新名字（`ThreadManager`, `CodexThread`）
2. 保留旧名字为 deprecated 别名（`ConversationManager`, `CodexConversation`）
3. 逐步迁移内部代码使用新名字
4. 最终（未来版本）移除 deprecated 别名

### App Server v1 → v2

App Server 协议从 v1 演进到 v2：
- v1：原始的 JSON-RPC over stdio
- v2：统一的 transport 抽象层，支持 stdio/UDS/WebSocket 三种传输方式，连接级别的生命周期管理，更完善的错误处理和 backpressure

迁移通过 `app-server-transport` crate 的 `TransportEvent` 枚举实现，新旧传输方式在同一套抽象下工作。

---

## 16.3 演进中的设计教训

### 教训一：wire format 是永恒的

AGENTS.md 反复强调"先定义 wire format"。因为：
- wire format 定义了"谁和谁能对话"
- 代码可以重写，但 wire format 必须向后兼容
- `#[ts(export_to)]` 保证 Rust 和 TypeScript 看到同一个 schema

### 教训二：弱引用防止内存泄漏

多 Agent 系统从最初使用 `Arc` 到使用 `Weak<ThreadManagerState>`，是因为发现了循环引用问题：

```
之前: ThreadManagerState → CodexThread → Session → AgentControl → Arc<ThreadManagerState> = 循环
现在: ThreadManagerState → CodexThread → Session → AgentControl → Weak<ThreadManagerState> ✓
```

### 教训三：单线程消息处理 + 异步业务执行

MessageProcessor 最初可能尝试过在消息处理中做业务逻辑，后来演进为"单线程分发 + 异步 handler 执行"模式——快速的 message routing（微秒级）和耗时的业务逻辑（秒级）解耦。

---

## 16.4 未来展望

基于代码中的 TODO 注释和实验性功能代码，可以推测 Codex 的未来方向：

- **MultiAgentV2**：更复杂的多 Agent 协作模式（当前代码中已有 flag）
- **Remote Thread Store**：云端 Thread 同步（`RemoteThreadStore` 已有基础实现）
- **Plugin 系统深化**：第三方扩展的标准接口（当前 Plugin 系统偏早期）
- **更细粒度的权限控制**：`Granular` approval policy 的持续完善

---

## 16.5 本章要点

1. **渐进式演进**：deprecated 别名 + serde(alias) 保证向后兼容。
2. **双向转换函数**：新旧格式互相转换，允许新旧代码共存。
3. **Thread 重命名三步走**：新名字 → deprecated 别名 → 移除。
4. **wire format 优先**：协议层必须向后兼容，代码可以重写。
5. **Weak 替代 Arc**：解决多 Agent 树的循环引用问题。
6. **教训可迁移**：这些演进模式适用于任何长期维护的分布式系统。
