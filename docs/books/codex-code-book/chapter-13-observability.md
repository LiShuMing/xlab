# 第13章：遥测、日志与可观测性——Agent 的"感官系统"

> 源码版本：2026-05-04
> 关键文件：`analytics/src/`, `app-server/src/analytics_utils.rs`, `core/src/tracing_init.rs`, `tui/src/session_log.rs`

---

## 13.1 可观测性的三层架构

Codex 的可观测性体系分为三层：

```
第一层：结构化事件（Analytics）
  │  "用户做了什么"——submit turn, approve tool, fork thread
  │  消费端：后端分析平台、产品决策
  │
第二层：分布式追踪（Tracing）
  │  "代码路径是什么"——span 进入/退出、关键分支
  │  消费端：开发调试、性能优化
  │
第三层：日志（Logging）
  │  "发生了什么"——错误信息、警告、状态转换
  │  消费端：CLI 输出、用户排查
```

每层有不同的消费场景和性能特征。

---

## 13.2 Analytics：结构化遥测事件

```rust
// analytics/src/events.rs
// 定义所有遥测事件类型
// 每个事件有明确的 schema（通过 serde 序列化）
```

Analytics 系统是"给机器看的数据"——它不在乎可读性，在乎结构化和可查询性。

### 事件模型

关键设计原则：
- **事件是不可变的**：一旦发出就不修改
- **事件是增量的**：每个事件描述一个原子操作（一个 turn 提交、一个 tool 执行）
- **事件有事实集（Facts）**：`facts.rs` 定义了可附加到事件上的"事实"——如当前 model、session id、sandbox type

### 客户端架构

```rust
// analytics/src/client.rs
// AnalyticsClient 负责：
// 1. 缓冲事件（避免每次事件都发网络请求）
// 2. 批量上传（周期性或达到阈值时 flush）
// 3. 离线缓存（网络断开时缓存在磁盘，恢复后重发）
```

### 服务端集成

```rust
// app-server/src/analytics_utils.rs
// 将 analytics 事件与 App Server 的生命周期绑定
// Server 启动 → analytics client 初始化
// Server 关闭 → flush 所有缓冲事件
```

---

## 13.3 Tracing：分布式追踪

Codex 使用 Rust 的 `tracing` 生态（tokio-rs/tracing）实现分布式追踪：

```rust
// core/src/lib.rs 及相关文件中的 tracing instrumentation
#[instrument(level = "info", skip_all)]
pub async fn spawn_thread(...) -> ... { ... }
```

关键 span 边界：

| Span 名称 | 含义 | 覆盖范围 |
|-----------|------|---------|
| `session::process_turn` | 处理一个完整 Turn | Context 装配 → LLM 调用 → Tool 执行 → 结果注入 |
| `model_client::stream` | 一次 LLM API 调用 | API 请求发送 → SSE 流解析 → 返回 |
| `tool::shell::execute` | 一次 Shell 工具执行 | 权限检查 → 沙箱包装 → 进程 spawn → 输出捕获 |
| `agent::spawn` | 一次子 Agent 派生 | 准备 → 身份分配 → Fork/Spawn → 启动通知 |

### 日志级别策略

- `ERROR`：不应该发生但可以恢复的错误（如单次 API 调用失败 → 重试）
- `WARN`：需要注意但不阻塞流程的情况（如 .rules 文件解析失败 → 使用空策略继续）
- `INFO`：关键状态转换（Session 创建、Thread 关闭、子 Agent 完成）
- `DEBUG`：详细的参数和中间结果（通常仅在开发阶段开启）
- `TRACE`：极其详细的逐行执行信息（仅在排查特定问题时开启）

---

## 13.4 Session Log：会话日志

```rust
// tui/src/session_log.rs
// 为每个 Session 创建独立的日志文件
// 路径: <codex_home>/sessions/<session_id>/session.log
```

Session Log 是"给人看的数据"——它在遇到问题时提供回溯能力：

- 记录每个 Turn 的提交内容（用户说了什么）
- 记录每个 Tool 的调用（Agent 执行了什么命令）
- 记录错误上下文（如果出错，日志中记录了之前几步的操作）

---

## 13.5 可观测性设计的权衡

### 隐私 vs 可见性

Analytics 事件**不包含**用户的实际对话内容、文件内容、Shell 命令输出。它只包含"元数据"：哪个 tool 被调用了、耗时多久、是否成功。内容级别的日志保留在本地 session.log 中，不上传。

### 性能 vs 可见性

- Analytics：缓冲 + 批量发送，对性能影响极小
- Tracing：仅在 DEBUG/TRACE 级别有可见开销，INFO 级别几乎无感
- Session Log：异步写入，不阻塞主流程

---

## 13.6 类比

| 概念 | OS 层面 | Codex 可观测性 |
|------|--------|--------------|
| 性能计数器 (PMC) | CPU 硬件计数器 | Analytics events（操作计数 + 耗时） |
| ftrace / DTrace | 内核函数追踪 | Tracing spans（函数级调用链） |
| syslog / journald | 系统日志 | Session log + tracing events |
| /proc 文件系统 | 进程信息暴露 | Status line（实时 Agent 状态） |
| 审计日志 (auditd) | 安全审计 | ExecPolicy 决策日志 |

---

## 13.7 本章要点

1. **三层可观测性**：Analytics（结构化遥测）→ Tracing（分布式追踪）→ Logging（文本日志）。
2. **Analytics 是不可变的增量事件**：每个事件描述一个原子操作，带结构化事实集。
3. **Tracing 使用 tokio-rs/tracing**：通过 `#[instrument]` 宏标注 span 边界，支持分级过滤。
4. **Session Log 是给人看的**：保留在本地，不上传，用于用户排查问题。
5. **隐私设计**：遥测事件不含用户内容，只含操作元数据。
