# 第3章：核心抽象层次——从 ThreadManager 到 Agent

> 源码版本：2026-05-04
> 关键文件：`core/src/thread_manager.rs`, `core/src/codex_thread.rs`, `core/src/session/mod.rs`, `core/src/agent/mod.rs`, `core/src/agent/control.rs`

---

## 3.1 四层抽象总览

如果把 Codex 比作一台计算机，那么：

- **ThreadManager** = 操作系统（管理所有"进程"）
- **CodexThread** = 进程（一个用户可见的对话会话）
- **Session（Codex）** = CPU + 内存（执行引擎 + 上下文窗口）
- **Agent** = 线程/任务（在 Session 上执行的思考-行动循环）

```
ThreadManager ("操作系统")
    │
    ├── CodexThread #1 ("进程")
    │       │
    │       └── Session / Codex ("执行引擎")
    │               │
    │               ├── Agent Main ("主线程") → 思考-行动循环
    │               │
    │               ├── Agent Sub #1 ("子线程") → 独立子任务
    │               │
    │               └── Turn #1, Turn #2, ... ("时间片")
    │
    ├── CodexThread #2
    │       └── ...
    │
    └── ...
```

这不是比喻，Codex 源码中的层级关系就是这样的：

```rust
// thread_manager.rs:239-253
pub(crate) struct ThreadManagerState {
    threads: Arc<RwLock<HashMap<ThreadId, Arc<CodexThread>>>>,  // ★ 进程表
    // ...
}

// codex_thread.rs — CodexThread 持有 Codex（= Session）
// session/mod.rs — Codex 持有 AgentControl
// agent/control.rs — AgentControl 管理所有活跃 Agent
```

---

## 3.2 ThreadManager：全局进程管理

`ThreadManager` 是 Codex 中**存活时间最长、管理范围最大**的对象。它从 App Server 启动时创建，直到 App Server 关闭才销毁。

### 核心职责

```rust
// thread_manager.rs:210-213
pub struct ThreadManager {
    state: Arc<ThreadManagerState>,
    _test_codex_home_guard: Option<TempCodexHomeGuard>,
}
```

ThreadManager 负责三件事：

#### (1) 创建 Thread：spawn_thread_with_source

```rust
// thread_manager.rs:1063-1156 — 核心创建路径
pub(crate) async fn spawn_thread_with_source(
    &self,
    config: Config,
    initial_history: InitialHistory,
    auth_manager: Arc<AuthManager>,
    agent_control: AgentControl,     // ← 外部传入的控制句柄
    session_source: SessionSource,    // ← "谁创建了这个 Thread？"
    dynamic_tools: Vec<DynamicToolSpec>,
    // ... 更多参数
) -> CodexResult<NewThread> {
```

整个创建路径从上层逐步收敛到这个最终方法。每一层的包装函数（`start_thread` → `start_thread_with_tools` → `start_thread_with_options` → `state.spawn_thread_with_source`）做的事情只是**逐步填充参数默认值**。这是"窄接口"模式——外部调用者只需要知道最少的参数，内部逐步补全。

#### (2) 查询 Thread：线程表查找

```rust
// thread_manager.rs:483-485
pub async fn get_thread(&self, thread_id: ThreadId) -> CodexResult<Arc<CodexThread>> {
    self.state.get_thread(thread_id).await
}

// thread_manager.rs:852-858
pub(crate) async fn get_thread(&self, thread_id: ThreadId) -> CodexResult<Arc<CodexThread>> {
    let threads = self.threads.read().await;
    match threads.get(&thread_id) {
        Some(thread) if !thread.session_source.is_internal() => Ok(thread.clone()),
        Some(_) | None => Err(CodexErr::ThreadNotFound(thread_id)),
    }
}
```

注意 `!thread.session_source.is_internal()` ——内部 Thread（如子 Agent 的内部 Thread）对外部调用者不可见。ThreadManager 在"进程表"层面就做了可见性过滤。

#### (3) 关闭 Thread：并发关机和超时

```rust
// thread_manager.rs:699-745
pub async fn shutdown_all_threads_bounded(&self, timeout: Duration) -> ThreadShutdownReport {
    let shutdowns = threads.into_iter()
        .map(|(thread_id, thread)| async move {
            let outcome = match tokio::time::timeout(timeout, thread.shutdown_and_wait()).await {
                Ok(Ok(())) => ShutdownOutcome::Complete,
                Ok(Err(_)) => ShutdownOutcome::SubmitFailed,
                Err(_) => ShutdownOutcome::TimedOut,
            };
            (thread_id, outcome)
        })
        .collect::<FuturesUnordered<_>>();  // ← 并发执行所有 shutdown

    // 收集结果，返回分类报告
    let mut report = ThreadShutdownReport::default();
    while let Some((thread_id, outcome)) = shutdowns.next().await {
        match outcome { ... }
    }
}
```

`FuturesUnordered` 保证了所有 Thread 的关闭是**并发**的——不会因为某个 Thread 挂起而阻塞其他的关闭。`ThreadShutdownReport` 将结果三分类（完成/失败/超时），让调用者能精确知道发生了什么。

### Thread 去重：幂等的 resume

```rust
// thread_manager.rs:1080-1100
if let InitialHistory::Resumed(resumed) = &initial_history {
    let mut threads = self.threads.write().await;
    if let Some(thread) = threads.get(&resumed.conversation_id).cloned() {
        if thread.is_running() {
            // 已在运行 → 直接返回现有 Thread（幂等）
            if let Some(requested_rollout_path) = ... {
                return Err(CodexErr::InvalidRequest(...));  // 路径冲突
            }
            return Ok(NewThread { thread_id, thread, ... });
        }
        threads.remove(&resumed.conversation_id);  // 已停止 → 移除旧实例
    }
}
```

同一個 Thread ID 被 resume 两次时，如果已经在运行，直接返回旧的 `Arc<CodexThread>`。这是函数式的幂等语义——同一个输入永远产生同一个输出。

---

## 3.3 CodexThread：用户视角的"对话线程"

`CodexThread` 是外部世界（TUI、CLI、IDE 插件）看到的"对话"对象。它是 `Codex`（核心引擎）的外壳。

```rust
// codex_thread.rs:78-82
pub struct CodexThreadTurnContextOverrides {
    pub cwd: Option<PathBuf>,
    pub approval_policy: Option<AskForApproval>,
    // ...
}
```

### ThreadConfigSnapshot：配置快照

```rust
// codex_thread.rs:49-62
pub struct ThreadConfigSnapshot {
    pub model: String,
    pub model_provider_id: String,
    pub service_tier: Option<ServiceTier>,
    pub approval_policy: AskForApproval,
    pub permission_profile: PermissionProfile,
    pub cwd: AbsolutePathBuf,
    pub ephemeral: bool,
    pub reasoning_effort: Option<ReasoningEffort>,
    pub personality: Option<Personality>,
    pub session_source: SessionSource,
}
```

`ThreadConfigSnapshot` 在 Thread 创建时拍下快照。**它不能被修改**——如果你想改变 model 或 personality，你必须创建新 Thread（或 Fork）。这个不可变性保证了会话回放时的一致性。

### sandbox_policy：配置 → 安全策略的推导

```rust
// codex_thread.rs:65-73
pub fn sandbox_policy(&self) -> SandboxPolicy {
    let file_system_sandbox_policy = self.permission_profile.file_system_sandbox_policy();
    codex_sandboxing::compatibility_sandbox_policy_for_permission_profile(
        &self.permission_profile,
        &file_system_sandbox_policy,
        self.permission_profile.network_sandbox_policy(),
        self.cwd.as_path(),
    )
}
```

这个函数体现了 Codex 的安全哲学：**沙箱策略不是在执行时决定的，而是在配置解析时就计算好了**。`PermissionProfile` → `SandboxPolicy` 是一个纯函数——给定相同的 profile 和 cwd，永远产生相同的沙箱策略。

---

## 3.4 Session（Codex）：对话执行引擎

### spawn 模式：创建即启动

```rust
// session/mod.rs
pub struct CodexSpawnArgs {
    pub config: Config,
    pub auth_manager: Arc<AuthManager>,
    pub models_manager: SharedModelsManager,
    pub skills_manager: Arc<SkillsManager>,
    pub mcp_manager: Arc<McpManager>,
    pub conversation_history: InitialHistory,
    pub session_source: SessionSource,
    pub agent_control: AgentControl,
    // ... 十几个参数
}

pub struct CodexSpawnOk {
    pub codex: Codex,
    pub thread_id: ThreadId,
    // ...
}
```

Codex 使用"spawn"而非"new"——它在创建后立即启动，第一个事件必须是 `SessionConfigured`：

```rust
// thread_manager.rs:1165-1173
let session_configured = match event {
    Event {
        id,
        msg: EventMsg::SessionConfigured(session_configured),
    } if id == INITIAL_SUBMIT_ID => session_configured,  // ← 必须是 SubmitId(0)
    _ => return Err(CodexErr::SessionConfiguredNotFirstEvent),
};
```

这是一个契约：每个新 Session 的第一个事件必定是配置确认。如果 LLM 返回的第一个事件不是 `SessionConfigured`，Codex 会拒绝创建 Thread。

### Codex 的内部结构

Codex 本身是一个庞大的类型，包含：
- **Services**：`ModelClient`（LLM 通信）、`RolloutRecorder`（会话录制）、`EnvironmentManager`（环境管理）
- **Context**：当前装配的系统提示词、用户指令、权限指令
- **Agent Control**：Agent 生命周期管理句柄
- **State**：会话状态数据库句柄

Session 是 Codex 中"最难懂的类"——它同时管理上下文、通信、安全、持久化，这也是为什么 AGENTS.md 说"不要再往 core 里加代码了"。

---

## 3.5 Agent：思考-行动循环的执行单元

### 三层 Agent 模型

```rust
// agent/control.rs
pub struct AgentControl { ... }   // 外部控制接口（发指令给 Agent）

// agent/mailbox.rs
pub struct Mailbox { ... }        // Agent 的输入邮箱
pub struct MailboxReceiver { ... }// Agent 的输入接收端
```

Agent 不是线程（没有 `tokio::task::spawn`），它是一种**逻辑抽象**——Agent 的执行是嵌入在 Turn 的异步流程中的：

```
Turn 开始
  │
  ├─→ 向 ModelClient 发送请求（包含 Context）
  │
  ├─→ 接收 SSE 事件流
  │     │
  │     ├─→ ResponseCreated   → 创建响应记录
  │     ├─→ TextDelta         → 流式文本
  │     ├─→ FunctionCall      → Tool 调用请求
  │     ├─→ Completed         → 响应完成
  │     └─→ ...
  │
  ├─→ 如果有 Tool 调用：
  │     ├─→ 权限检查
  │     ├─→ 执行 Tool
  │     ├─→ 将结果注入上下文
  │     └─→ 回到 ModelClient 请求（循环）
  │
  └─→ Turn 完成
```

### AgentStatus 状态机

```rust
// agent/status.rs + protocol/src/protocol.rs
pub enum AgentStatus {
    Idle,         // 空闲
    Running,      // 正在执行
    Waiting,      // 等待用户输入
    Completed,    // 已完成
    Failed,       // 失败
    Aborted,      // 被中断
}
```

状态转换由事件驱动——`agent_status_from_event(event)` 根据收到的 SSE 事件推断 Agent 当前应该在什么状态。

### AgentControl：向下管理的控制句柄

```rust
// thread_manager.rs:825-827 — ThreadManager 创建 AgentControl 的方式
pub(crate) fn agent_control(&self) -> AgentControl {
    AgentControl::new(Arc::downgrade(&self.state))  // ★ Weak 引用！
}
```

`AgentControl::new(Arc::downgrade(...))`——用的是 `Weak` 引用而非 `Arc`。这个设计非常关键：**AgentControl 不应该阻止 ThreadManagerState 被释放**。如果所有 Thread 都结束了，ThreadManagerState 应该自然销毁，AgentControl 持有的弱引用会自然失效。

AgentControl 提供的方法包括：
- `list_live_agent_subtree_thread_ids(thread_id)` — 查看 Thread 的所有活跃子 Agent
- 向 Agent 发送控制信号（abort、shutdown）
- 管理 Agent 间的 spawn 关系

---

## 3.6 线程派生：Multi-Agent 的 Thread Tree

Codex 的 Multi-Agent 模型表现为 Thread Tree：

```
Root Thread (用户直接对话)
    │
    ├── Sub-Agent Thread #1 (via ThreadSpawn)
    │       │
    │       ├── Sub-Sub-Agent Thread #1.1
    │       └── Sub-Sub-Agent Thread #1.2
    │
    └── Sub-Agent Thread #2 (via ThreadSpawn)
```

每个 Sub-Agent Thread 有独立的：
- ThreadId
- Session（Codex）
- Context Window（独立的 Token 预算）
- RolloutRecorder（独立的会话录制）

但共享：
- AuthManager（同一个认证）
- ModelsManager（同一个模型目录）
- McpManager（同一组 MCP Server 连接）
- SkillsManager（同一组 Skill）

### 线程派生深度限制

```rust
// agent/registry.rs
pub(crate) fn exceeds_thread_spawn_depth_limit(...) -> bool { ... }
pub(crate) fn next_thread_spawn_depth(...) -> ... { ... }
```

Codex 对 Thread 派生深度有限制——防止无限递归的 Agent 派生。

---

## 3.7 类比：Codex Thread Tree ≈ OS Process Tree

| OS 概念 | Codex 概念 | 关键差异 |
|---------|-----------|---------|
| `fork()` | `fork_thread()` | Codex Fork 共享配置（不可变快照），OS Fork 复制地址空间 |
| `exec()` | `spawn_thread_with_source()` | Codex 的"程序"是 Context (Prompt)，不是二进制 |
| `waitpid()` | `shutdown_and_wait()` | Codex 的"退出状态"是 `ThreadShutdownReport` |
| 进程表 | `HashMap<ThreadId, Arc<CodexThread>>` | Codex 的"进程"更轻（没有地址空间隔离） |
| 线程 | Agent（逻辑抽象） | Agent 是协程级别的，不是 OS 线程 |
| 时间片 | Turn | Turn 不可抢占（没有时间片轮转），只能在 Tool 调用边界"让出" |
| `kill -9` | `TurnAbortReason::Interrupted` | Codex 的中断是协作式的（在下一个 SSE 事件到达时检查） |

最核心的差异：**Codex Agent 是不可抢占的，中断是协作式的。** 你不能像 OS 那样在任意指令边界暂停 Agent。你只能在两个时间点注入中断：
1. LLM 返回的 SSE 事件之间
2. Tool 调用执行前后

这深刻影响了 Codex 的中断响应延迟——最坏情况下，你需要等 LLM 完整输出完当前响应块才能中止。这也是为什么 `shutdown_all_threads_bounded` 需要一个 `timeout` 参数。

---

## 3.8 本章要点

1. **四层抽象**：ThreadManager → CodexThread → Session(Codex) → Agent。层与层之间通过 `Arc<...>` 共享状态，通过 `Weak<...>` 避免循环引用。
2. **ThreadManager 是"进程管理器"**：维护 `HashMap<ThreadId, Arc<CodexThread>>` 线程表，支持创建/查询/关闭/Fork。
3. **CodexThread 是"进程"**：持有不可变的 `ThreadConfigSnapshot`，外壳模式包裹 `Codex` 执行引擎。
4. **Session(Codex) 是"执行引擎"**：管理 Context 装配、ModelClient 通信、Agent 调度、Tool 执行。第一个事件必须是 `SessionConfigured`。
5. **Agent 是"逻辑线程"**：通过 Mailbox 接收指令，状态机驱动（Idle→Running→Completed/Failed/Aborted）。不可抢占。
6. **AgentControl 使用 `Weak` 引用**：避免阻止 ThreadManagerState 的正常释放。
7. **Thread Tree 描述 Multi-Agent 拓扑**：每个 Sub-Agent 有独立的 Context Window，但共享认证、模型、MCP、Skill。
