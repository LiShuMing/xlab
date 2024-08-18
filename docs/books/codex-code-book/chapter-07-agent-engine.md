# 第7章：Agent 引擎——主 Agent 与子 Agent 的协作调度

> 源码版本：2026-05-04
> 关键文件：`core/src/agent/control.rs`, `core/src/agent/registry.rs`, `core/src/agent/status.rs`, `core/src/agent/mailbox.rs`, `core/src/agent/role.rs`

---

## 7.1 Agent 的本质：带有身份的异步执行单元

在 Codex 中，Agent 不是操作系统线程，而是一个**带有身份（Identity）、状态（Status）、路径（Path）和命名（Nickname）的逻辑抽象**。它的生命周期嵌入在 Session 的 Turn 流程中，通过 Mailbox 接收消息，通过 AgentControl 被外部管理和协调。

Agent 的核心数据：

```rust
// agent/control.rs:60-64 — LiveAgent
pub(crate) struct LiveAgent {
    pub(crate) thread_id: ThreadId,
    pub(crate) metadata: AgentMetadata,  // 身份信息
    pub(crate) status: AgentStatus,      // 当前状态
}
```

AgentMetadata 包含：
- **agent_id**: 对应的 ThreadId
- **agent_path**: 层次化路径（如 `root/sub1/sub2`），类比文件系统路径
- **agent_nickname**: 人类可读名称（从 `agent_names.txt` 选取，如 "moss", "hal", "r2d2"）
- **agent_role**: 角色名（决定 Agent 的行为配置）
- **last_task_message**: 最近的任务描述

### Agent 名称系统：从预设列表中分配

```rust
// agent/control.rs:43
const AGENT_NAMES: &str = include_str!("agent_names.txt");
```

`agent_names.txt` 在编译时嵌入二进制，包含数百个预设名称。Agent 的昵称不是 LLM 随意取的——系统从预设列表中按需分配，并通过 `reserve_agent_nickname_with_preference()` 确保同一棵树中昵称唯一。如果用户或 Role 配置了偏好昵称列表，优先使用偏好列表。

Agent Path 采用文件系统式的层级命名：
```
.root              → 主 Agent (Root Thread)
.root/explorer     → 子 Agent "explorer"
.root/explorer/reader → 孙 Agent "reader"
```

这种命名方案让 Agent 间通信时可以精确寻址——就像文件系统中的绝对路径。

---

## 7.2 Agent 状态机

```rust
// agent/status.rs + protocol/src/protocol.rs
pub enum AgentStatus {
    Idle,        // 空闲，等待输入
    Running,     // 正在执行（与 LLM 交互中）
    Waiting,     // 等待用户输入（如等待命令批准）
    Completed,   // 任务完成
    Failed,      // 任务失败
    Aborted,     // 被用户中断
    Shutdown,    // 已关闭
    NotFound,    // Agent 未找到（查询状态时的返回值）
}
```

状态转换由事件驱动：

```
┌──────────┐
│   Idle   │ ← Session 创建后的初始状态
└────┬─────┘
     │ Op::UserTurn / Op::InterAgentCommunication
     ▼
┌──────────┐
│ Running  │◄──────────────────────────┐
└────┬─────┘                           │
     │                                 │
     ├─→ LLM 返回 completed     → Completed
     ├─→ LLM 返回 error         → Failed
     ├─→ LLM 请求 tool (需审批)  → Waiting
     │     │
     │     └─→ 用户批准  → Running ────┘
     │     └─→ 用户拒绝  → 继续 Running (跳过该 tool)
     │
     └─→ Op::Interrupt          → Aborted
           Op::Shutdown          → Shutdown
```

`is_final(status)` 判断 Agent 是否已结束：
```rust
pub(crate) fn is_final(status: &AgentStatus) -> bool {
    matches!(status, Completed | Failed | Aborted | Shutdown)
}
```

---

## 7.3 AgentControl：多 Agent 协调的中枢

`AgentControl` 是 Codex 整个多 Agent 系统的控制平面。它的设计有四个关键决策：

### 决策一：Weak 引用解耦生命周期

```rust
// agent/control.rs:134-140
pub(crate) struct AgentControl {
    manager: Weak<ThreadManagerState>,    // ★ Weak! 不阻止 ThreadManager 释放
    state: Arc<AgentRegistry>,            // Agent 注册表
}
```

为什么是 `Weak`？考虑这个引用链：

```
ThreadManagerState
  → threads: HashMap<ThreadId, Arc<CodexThread>>
    → CodexThread
      → Session(Codex)
        → SessionServices
          → AgentControl
            → manager: Weak<ThreadManagerState>  ← 必须 Weak!
```

如果是 `Arc`，这会形成循环引用，导致 ThreadManagerState 永远无法被释放。`Weak` 解决了这个问题：当 ThreadManagerState 的所有外部 `Arc` 都 drop 后，它自然销毁，AgentControl 持有的 `Weak` 升级（`upgrade()`）失败，Agent 操作返回 `UnsupportedOperation`。

### 决策二：AgentRegistry 管理 Agent 命名空间

```rust
// agent/registry.rs
pub(crate) struct AgentRegistry { ... }
pub(crate) struct SpawnReservation { ... }
```

`AgentRegistry` 管理三样东西：
1. **Agent 名称表**：已分配的昵称，保证不重复
2. **Agent 路径表**：已使用的 Path，保证 Agent 可被精确寻址
3. **线程派生槽位**：限制同时运行的 Agent 总数（`config.agent_max_threads`）

`SpawnReservation` 是两阶段提交模式：
```rust
let mut reservation = self.state.reserve_spawn_slot(config.agent_max_threads)?;
// ... 准备 agent_path, agent_nickname ...
reservation.commit(agent_metadata);
```

先预留，再提交。如果在预留和提交之间失败，预留自动回滚（通过 Drop）。这保证了原子性——不会出现"名字被占但 Agent 没创建"的状态。

### 决策三：一对一的 AgentControl 共享

AGENTS.md 没有直接说明这点，但从代码中可以看到：

```rust
// agent/control.rs:131-133 — doc comment
// An `AgentControl` instance is intended to be created at most once per root
// thread/session tree. That same `AgentControl` is then shared with every
// sub-agent spawned from that root, which keeps the registry scoped to that
// root thread rather than the entire `ThreadManager`.
```

所有从同一个 Root Thread 派生的子 Agent **共享同一个 AgentControl 实例**。这意味着一个会话树中的所有 Agent 看到的是同一个注册表——它们可以互相寻址、互相通信。但不同 Root Thread 之间的 Agent 互相不可见。

---

## 7.4 子 Agent 派生：spawn_agent_internal

子 Agent 的完整派生流程（`agent/control.rs:181-326`）：

### Phase 1: 准备

```rust
// 1. 升级 Weak → Arc（失败则无法操作）
let state = self.upgrade()?;

// 2. 预留一个派生槽位
let mut reservation = self.state.reserve_spawn_slot(config.agent_max_threads)?;

// 3. 从父 Agent 继承 Shell 快照和 ExecPolicy
let inherited_shell_snapshot = self.inherited_shell_snapshot_for_source(...).await;
let inherited_exec_policy = self.inherited_exec_policy_for_source(...).await;
```

Shell 快照的继承很关键：子 Agent 从父 Agent 继承 Shell 状态（环境变量、别名、当前目录），这样它看到的 Shell 环境和父 Agent 一致。这类似于 OS `fork()` 对文件描述符的继承。

### Phase 2: 身份分配

```rust
// 4. prepare_thread_spawn → 分配 Agent 身份
let (session_source, agent_metadata) = self.prepare_thread_spawn(
    &mut reservation, &config, parent_thread_id, depth,
    agent_path, agent_role, preferred_agent_nickname,
)?;
```

`prepare_thread_spawn` 负责：
- 验证 depth 是否为 1（第一次派生时将父线程注册为 Root）
- 保留 agent_path（检查是否冲突）
- 从候选名称列表中分配唯一 agent_nickname
- 构造 `SessionSource::SubAgent(ThreadSpawn { ... })`

候选名称列表来自 `agent_nickname_candidates()`：
```rust
// agent/control.rs:81-96
fn agent_nickname_candidates(config: &Config, role_name: Option<&str>) -> Vec<String> {
    let role_name = role_name.unwrap_or(DEFAULT_ROLE_NAME);
    if let Some(candidates) = resolve_role_config(config, role_name)
        .and_then(|role| role.nickname_candidates.clone())
    {
        return candidates;  // Role 配置的自定义名称列表
    }
    default_agent_nickname_list()  // 回退到 agent_names.txt
}
```

### Phase 3: Fork 模式 vs 新建模式

```rust
// 5. 根据是否指定 Fork 模式，选择创建路径
let new_thread = match (session_source, options.fork_mode.as_ref()) {
    (Some(session_source), Some(_)) => {
        // Fork 模式：从父线程的 rollout 历史中 fork
        self.spawn_forked_thread(&state, config, session_source, &options, ...).await?
    }
    (Some(session_source), None) => {
        // 新建模式：全新的线程
        state.spawn_new_thread_with_source(config, self.clone(), session_source, ...).await?
    }
    (None, _) => state.spawn_new_thread(config, self.clone()).await?,
};
```

Fork 模式下（`spawn_forked_thread`, line 328-435），子 Agent 继承父 Agent 的对话历史。关键步骤：

1. **Flush rollout**：确保父线程的 rollout 已写入磁盘
2. **读取父历史**：从 ThreadStore 读取
3. **过滤历史项**：`keep_forked_rollout_item()` 过滤掉不需要的项（如 tool call、reasoning 细节）
4. **截断**：`truncate_rollout_to_last_n_fork_turns()` 只保留最近 N 轮
5. **过滤 MultiAgentV2 hint**：移除父线程的 MultiAgentV2 使用提示，子线程会生成自己的

`keep_forked_rollout_item()` 策略很有趣：
```rust
// agent/control.rs:98-125
fn keep_forked_rollout_item(item: &RolloutItem) -> bool {
    match item {
        // 保留 system/developer/user 消息
        ResponseItem::Message { role, .. } if role is "system"|"developer"|"user" => true,
        // assistant 只保留 FinalAnswer 阶段
        ResponseItem::Message { role: "assistant", phase: Some(FinalAnswer), .. } => true,
        // 丢弃所有 tool call / tool output / reasoning
        ResponseItem::FunctionCall { .. } | ResponseItem::FunctionCallOutput { .. } | ...  => false,
        // 保留事件和 compacted 内容
        RolloutItem::Compacted(_) | RolloutItem::EventMsg(_) | RolloutItem::SessionMeta(_) => true,
    }
}
```

### Phase 4: 启动与通知

```rust
// 6. 提交 reservation
reservation.commit(agent_metadata.clone());

// 7. 发送初始 Op 给子 Agent
self.send_input(new_thread.thread_id, initial_operation).await?;

// 8. 启动 Completion Watcher（非 MultiAgentV2 模式）
self.maybe_start_completion_watcher(new_thread.thread_id, ...);
```

`completion_watcher` 是关键机制：它在后台监控子 Agent 的状态，当子 Agent 完成（进入 final 状态）时，自动将完成通知注入父 Agent。这让父 Agent 不需要轮询子 Agent 状态。

---

## 7.5 Agent 间通信：InterAgentCommunication

```rust
// agent/control.rs:658-679
pub(crate) async fn send_inter_agent_communication(
    &self, agent_id: ThreadId, communication: InterAgentCommunication,
) -> CodexResult<String>
```

`InterAgentCommunication` 包含：
- 源 Agent Path
- 目标 Agent Path
- 消息内容
- 是否触发 Turn（`trigger_turn`）

当设置为 `trigger_turn: true`，消息会作为新的 Turn 触发目标 Agent 开始处理。否则只是注入到目标的 Context 中，等下一个 Turn 才被看到。这类似于同步 vs 异步消息发送。

---

## 7.6 Agent 树的生命周期管理

### 关闭一棵 Agent 树

```rust
// agent/control.rs:736-746
async fn shutdown_agent_tree(&self, agent_id: ThreadId) -> CodexResult<String> {
    let descendant_ids = self.live_thread_spawn_descendants(agent_id).await?;
    let result = self.shutdown_live_agent(agent_id).await;
    for descendant_id in descendant_ids {
        match self.shutdown_live_agent(descendant_id).await {
            Ok(_) | Err(ThreadNotFound) | Err(InternalAgentDied) => {}  // 容错
            Err(err) => return Err(err),
        }
    }
    result
}
```

关闭顺序：先父后子（DFS 遍历）。如果某个子孙已经不在或已死，忽略错误继续。

### Agent Resume 的级联

```rust
// agent/control.rs:438-512
pub(crate) async fn resume_agent_from_rollout(...) -> CodexResult<ThreadId> {
    // 1. Resume 目标 Agent
    let resumed_thread_id = self.resume_single_agent_from_rollout(...).await?;
    // 2. 从 StateDB 找到所有持久化的子 Agent
    // 3. 逐个 Resume（BFS 遍历 Agent Tree）
    let mut resume_queue = VecDeque::from([(thread_id, root_depth)]);
    while let Some((parent_thread_id, parent_depth)) = resume_queue.pop_front() {
        let child_ids = state_db_ctx.list_thread_spawn_children_with_status(
            parent_thread_id, DirectionalThreadSpawnEdgeStatus::Open,
        ).await?;
        for child_thread_id in child_ids {
            // Resume 子 Agent，成功则加入队列继续找孙子
            self.resume_single_agent_from_rollout(config, child_thread_id, child_session_source).await?;
            resume_queue.push_back((child_thread_id, parent_depth + 1));
        }
    }
}
```

一个 Session Resume 动作会级联恢复整棵 Agent 树——不仅是目标 Agent，还有它的所有子孙 Agent。这是一个递归的广度优先恢复过程。

---

## 7.7 类比视角

### OS 视角

| OS 概念 | Codex Agent 系统 |
|---------|-----------------|
| 进程 | Thread (有独立 ID 和 Session) |
| 线程 | Agent (嵌入在 Session 中) |
| PID 命名空间 | AgentRegistry (名称不重复) |
| fork() | fork_thread (从 rollout 历史中 Fork) |
| waitpid() | CompletionWatcher (监控子 Agent 结束) |
| 进程间通信 (pipe/signal) | InterAgentCommunication (Agent Path 寻址) |
| 进程树 | Agent Tree (Agent Path 层级) |
| 孤儿进程回收 | shutdown_agent_tree (DFS 清理) |

### Query Engine 视角

| Query Engine 概念 | Codex Agent 系统 |
|------------------|-----------------|
| 查询计划 | Goal 分解 (拆成子任务) |
| 并行扫描 (Scatter-Gather) | 并行 Agent 派生 |
| Stage 依赖 | Agent 依赖链 (父等子结果) |
| Exchange (Shuffle) | InterAgentCommunication (Agent 间数据传递) |
| 查询超时 | Turn Interrupt |
| 资源组 (Resource Group) | Reservation (agent_max_threads) |

---

## 7.8 本章要点

1. **Agent 是有身份的异步执行单元**：ThreadId + AgentPath + AgentNickname + AgentStatus。
2. **AgentPath 是文件系统式的层级命名**：`root/sub1/sub2`，支持精确 Agent 间寻址。
3. **AgentControl 是整个多 Agent 系统的控制面**：
   - `Weak<ThreadManagerState>` 解耦生命周期
   - 共享一份 AgentRegistry（同树 Agent 互相可寻址）
   - Reservation 机制保证 Agent 名称/路径/槽位的原子性分配
4. **子 Agent 派生支持两种模式**：新建（全新 Context）和 Fork（继承父历史并过滤）。
5. **CompletionWatcher** 异步监控子 Agent 完成，自动通知父 Agent。
6. **InterAgentCommunication** 支持 Agent 间的定向消息（可触发 Turn 或仅注入 Context）。
7. **Agent 树生命周期**：DFS 关闭（shutdown_agent_tree）+ BFS 恢复（resume 级联）。
8. **图中断是协作式的**：最长延迟 = 一个 LLM Streaming 响应块的持续时间。
