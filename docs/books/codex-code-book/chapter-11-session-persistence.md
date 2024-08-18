# 第11章：会话持久化——Thread Store 的存储抽象

> 源码版本：2026-05-04
> 关键文件：`thread-store/src/`, `rollout/src/`, `core/src/rollout.rs`, `core/src/compact.rs`, `core/src/thread_rollout_truncation.rs`

---

## 11.1 持久化的本质：Agent 的"文件系统"

如果说 Context 是 Agent 的虚拟内存，Tool 是 Agent 的系统调用，那么持久化就是 Agent 的"文件系统"——它让会话状态在进程重启后继续存在。在 OS 中，文件系统让数据跨越进程生命周期；在 Codex 中，Thread Store 让对话历史跨越 Session 生命周期。

关键设计理念：**ThreadId 是唯一的持久化句柄**。所有存储操作都围绕 ThreadId 展开，存储后端（本地文件、远程 RPC、内存）对上层透明。

---

## 11.2 ThreadStore trait：存储无关的持久化接口

```rust
// thread-store/src/store.rs:20-60
#[async_trait]
pub trait ThreadStore: Any + Send + Sync {
    async fn create_thread(&self, params: CreateThreadParams) -> ThreadStoreResult<()>;
    async fn resume_thread(&self, params: ResumeThreadParams) -> ThreadStoreResult<()>;
    async fn append_items(&self, params: AppendThreadItemsParams) -> ThreadStoreResult<()>;
    async fn persist_thread(&self, thread_id: ThreadId) -> ThreadStoreResult<()>;
    async fn flush_thread(&self, thread_id: ThreadId) -> ThreadStoreResult<()>;
    async fn shutdown_thread(&self, thread_id: ThreadId) -> ThreadStoreResult<()>;
    async fn discard_thread(&self, thread_id: ThreadId) -> ThreadStoreResult<()>;
    async fn load_history(&self, params: LoadThreadHistoryParams) -> ThreadStoreResult<StoredThreadHistory>;
    async fn read_thread(&self, params: ReadThreadParams) -> ThreadStoreResult<StoredThread>;
    async fn list_threads(&self, params: ListThreadsParams) -> ThreadStoreResult<ThreadPage>;
    async fn update_metadata(&self, params: UpdateThreadMetadataParams) -> ThreadStoreResult<()>;
    async fn archive_thread(&self, params: ArchiveThreadParams) -> ThreadStoreResult<()>;
}
```

这是典型的策略模式——三个实现：

| 实现 | 存储位置 | 用途 |
|------|---------|------|
| `LocalThreadStore` | 本地文件系统（jsonl rollout 文件） | 默认方式 |
| `RemoteThreadStore` | 远程 API（通过 RPC） | 云端同步、团队协作 |
| `InMemoryThreadStore` | 内存 HashMap | 测试、一次性会话 |

---

## 11.3 三层存储模型

```
LiveThread (内存层)
  │  活跃的会话写入通道
  │  持有 LiveThreadInitGuard（生命周期哨兵）
  │
  ▼
Rollout 文件 (持久化层)
  │  jsonl 格式，每行一个 JSON 事件
  │  路径: <codex_home>/threads/<thread_id>/rollout.jsonl
  │
  ▼
StateDB (索引层，可选)
  │  SQLite 数据库，存储线程元数据和索引
  │  路径: <codex_home>/state.db
  │  用途: 快速查询、跨会话信息
```

---

## 11.4 LiveThread：活跃会话的写入句柄

```rust
// thread-store/src/live_thread.rs
pub struct LiveThread {
    // 持有线程的写入通道
}

pub struct LiveThreadInitGuard {
    // RAII guard: drop 时自动 flush 或 discard
}
```

`LiveThread` 是写入会话事件的唯一入口。它实现了"write-ahead"模式：事件先写入内存缓冲区，再批量写入磁盘。`LiveThreadInitGuard` 是 RAII 守卫——如果会话初始化失败，drop 时自动清理未持久化的数据。

### 关键操作的生命周期

```
create_thread()
  │ 创建 rollout 文件
  │ 写入 SessionConfigured 事件（必须是第一条）
  │ 创建 LiveThread 写入句柄
  │
  ▼
append_items() — 在 Turn 期间反复调用
  │ 将 ResponseItem 追加到内存缓冲区
  │ 定期 flush 到磁盘
  │
  ▼
resume_thread() — 会话恢复
  │ 打开已有 rollout 文件
  │ 重建 LiveThread 写入句柄
  │ 从上次中断的位置继续追加
  │
  ▼
shutdown_thread()
  │ flush 所有缓冲数据
  │ 关闭文件句柄
  │ 释放 LiveThread
  │
  ▼
discard_thread()
  │ 丢弃未持久化的内存数据
  │ 保留已有的磁盘数据
  │ 用于会话初始化失败时的清理
```

---

## 11.5 Rollout：jsonl 事件流

### 文件格式

每个线程的对话历史存储为一个 rollout 文件（jsonl 格式）。每行是一个 JSON 序列化的事件。关键事件类型：

```
SessionConfigured  — 会话配置信息（必须是第一条）
UserTurn           — 用户输入
ResponseItem       — LLM 响应（message, function_call, function_call_output）
Compacted          — 压缩后的历史摘要
EventMsg           — 系统事件（MCP 启动、子 Agent 通知等）
SessionMeta        — 会话元数据
```

### 第一条事件的校验

```rust
// thread_manager.rs — finalize_thread_spawn 中
// 验证 rollout 的第一条事件必须是 SessionConfigured
// 且 submit_id 必须等于 INITIAL_SUBMIT_ID
```

这是一个关键的不变式：rollout 文件的第一条事件永远是 `SessionConfigured`。如果第一条事件不是它，说明文件损坏或不完整。

### Rollout Recorder

```rust
// core/src/rollout.rs + rollout/src/recorder.rs
pub struct RolloutRecorder {
    // 负责将事件序列化并写入 rollout 文件
}
```

`RolloutRecorder` 是 jsonl 写入的实现细节，处理：
- JSON 序列化
- 原子性写入（先写临时文件再 rename）
- 批量 flush（减少 fsync 次数）
- 写入失败的重试

---

## 11.6 StateDB：SQLite 元数据索引

```rust
// rollout/src/state_db.rs
// SQLite 数据库，存储：
// - 线程元数据（创建时间、最后活跃时间、摘要等）
// - 线程间关系（父子 Agent 关系、spawn edges）
// - 记忆（memories）
```

StateDB 是 rollout 文件的"索引层"。它不存储对话内容（那是 rollout 的事），但存储"关于对话的对话"：
- 这个线程叫什么？（摘要/标题）
- 谁创建了谁？（Agent 派生关系）
- 哪些线程还在运行？（状态追踪）

### Resume 级联恢复

```rust
// agent/control.rs — resume_agent_from_rollout
// 通过 StateDB 查询子 Agent 关系 → BFS 恢复整棵 Agent 树
let child_ids = state_db_ctx.list_thread_spawn_children_with_status(
    parent_thread_id, DirectionalThreadSpawnEdgeStatus::Open,
).await?;
```

---

## 11.7 Token 预算与历史管理

### Compact：上下文压缩

当对话历史接近 LLM 的上下文窗口上限时，早期对话被压缩为摘要：

```rust
// core/src/compact.rs
pub fn content_items_to_text(...) -> ...  // 结构化内容 → 纯文本

// core/src/compact_remote.rs
// CompactionInput → API CompactClient → 压缩结果（由 LLM 自己总结）
```

两种 Compact 模式：
- **本地 Compact**：按字数截断，保留最近 N 轮完整对话，将更早的转换为摘要文本
- **远程 Compact**：将早期对话发送给专门的 Compaction API，让 LLM 生成高质量摘要

类比 OS 的"分代 GC"——新数据保留（年轻代），老数据压缩（老年代）。

### Rollout Truncation：持久化层的截断

```rust
// core/src/thread_rollout_truncation.rs
pub mod thread_rollout_truncation {
    // 当 rollout 文件超过一定大小时，截断旧的 jsonl 事件
    // 保留元数据，丢弃旧的详细事件
}
```

---

## 11.8 类比：数据库系统的存储引擎

| 数据库概念 | Codex 持久化 |
|-----------|------------|
| WAL (Write-Ahead Log) | Rollout jsonl（按时间顺序追加事件） |
| B-Tree 索引 | StateDB（元数据快速查询） |
| 页缓存 | LiveThread 内存缓冲区（批量 flush） |
| Checkpoint | flush_thread（确保数据持久化） |
| 垃圾回收 (GC) | Compact（压缩旧对话） + Truncation（截断旧 rollout） |
| Redo Log | append_items（逐事件追加，可回放） |
| Undo Log | discard_thread（放弃未持久化的更改） |
| 表分区 | ThreadId 隔离（每个线程独立文件） |

---

## 11.9 本章要点

1. **ThreadStore 是存储无关的持久化接口**：LocalThreadStore / RemoteThreadStore / InMemoryThreadStore 三重实现。
2. **三层存储模型**：LiveThread（内存缓冲）→ Rollout jsonl（持久化日志）→ StateDB（SQLite 索引）。
3. **第一条事件不变量**：rollout 文件必须以 `SessionConfigured` 开头。
4. **LiveThreadInitGuard**：RAII 守卫，确保初始化失败时正确清理。
5. **Resume 是幂等的**：如果线程已在运行，返回已有的；否则从 rollout 恢复。
6. **Token 预算管理**：Compact（压缩对话历史）+ Rollout Truncation（截断旧事件）。
7. **多线程独立存储**：每个 ThreadId 独立的 rollout 文件，天然的隔离性。
