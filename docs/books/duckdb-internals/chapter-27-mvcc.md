# 第27章：MVCC 事务模型

> DuckDB 的事务设计遵循一个清醒的约束：OLAP 场景下，读远多于写，且写通常是批量追加。因此，DuckDB 选择了"多版本并发读 + 单写者检测冲突"的 MVCC 模型——没有锁管理器，没有死锁检测，没有 2PL。

## 27.1 三层事务架构

DuckDB 的事务不是一层——它是三层，每层解决不同的问题：

```
Layer 1: MetaTransaction        —— 跨数据库的事务协调
           ↓
Layer 2: Transaction (abstract) —— 事务基类
           ↓
Layer 3: DuckTransaction        —— DuckDB 原生事务
```

### MetaTransaction：跨数据库事务

```cpp
// src/include/duckdb/transaction/meta_transaction.hpp
class MetaTransaction {
    // 每个 ClientContext 一个
    reference_map_t<AttachedDatabase, TransactionReference> transactions; // 每个附加数据库一个子事务
    optional_ptr<AttachedDatabase> modified_database;  // 只能写一个数据库
    // 按创建的逆序提交/回滚
};
```

`MetaTransaction` 是一个**协调者**：一个 SQL 语句可能跨多个附加数据库（如 `INSERT INTO db1.t SELECT * FROM db2.t`），每个数据库需要自己的子事务。关键约束：**一个事务只能写一个附加数据库**（`modified_database` 字段强制执行）。

### DuckTransaction：核心事务状态

```cpp
// src/include/duckdb/transaction/duck_transaction.hpp
class DuckTransaction : public Transaction {
    transaction_t start_time;       // 快照时间戳
    transaction_t transaction_id;   // 唯一 ID（从 2^62 开始）
    transaction_t commit_id;        // 提交后设置，未提交为 0
    atomic<idx_t> catalog_version;  // 开始时的目录版本
    UndoBuffer undo_buffer;         // Undo 日志
    unique_ptr<LocalStorage> storage; // 事务本地存储
    unique_ptr<StorageLockKey> checkpoint_lock; // 阻止 Checkpoint
    unique_ptr<StorageLockKey> vacuum_lock;     // 阻止 Vacuum
};
```

### 事务 ID 空间的巧妙划分

```cpp
// src/common/constants.cpp
constexpr transaction_t TRANSACTION_ID_START = 4611686018427388000;  // 2^62
constexpr transaction_t MAX_TRANSACTION_ID = 2^63 - 1;
constexpr transaction_t NOT_DELETED_ID = 2^64 - 2;
constexpr row_t MAX_ROW_ID = 36028797018960000;  // 2^55
```

提交的数据 `id < TRANSACTION_ID_START`，未提交的数据 `id >= TRANSACTION_ID_START`。这个划分使得可见性检查可以用简单的整数比较完成——不需要维护复杂的事务状态表。

> **与 PostgreSQL 的对比**：PostgreSQL 使用 `xmin`/`xmax` 字段在元组头中标记事务可见性，需要 `hint bits` 和 `freeze` 机制处理事务 ID 回卷。DuckDB 的 ID 空间足够大（2^62 起始），在嵌入式场景下不存在回卷问题。

## 27.2 DuckTransactionManager：事务的生命周期

```cpp
// src/include/duckdb/transaction/duck_transaction_manager.hpp
class DuckTransactionManager : public TransactionManager {
    atomic<transaction_t> current_start_timestamp{2};    // 单调递增
    atomic<transaction_t> current_transaction_id{TRANSACTION_ID_START};
    atomic<transaction_t> lowest_active_id;              // 最低活跃事务 ID
    atomic<transaction_t> lowest_active_start;           // 最低活跃快照时间
    atomic<transaction_t> last_commit;                    // 最后提交时间戳
    vector<unique_ptr<DuckTransaction>> active_transactions;     // 活跃事务
    vector<unique_ptr<DuckTransaction>> recently_committed_transactions; // 已提交未清理
    mutex transaction_lock;                // 保护活跃事务列表和提交协议
    mutex start_transaction_lock;          // FORCE CHECKPOINT 时阻止新事务
    StorageLock checkpoint_lock;           // 读写锁（事务共享，Checkpoint 独占）
    queue<unique_ptr<DuckCleanupInfo>> cleanup_queue; // FIFO 清理队列
};
```

### StartTransaction

1. 获取 `transaction_lock`（写事务还需 `start_transaction_lock`）
2. 分配 `start_time = current_start_timestamp++` 和 `transaction_id = current_transaction_id++`
3. 创建 `DuckTransaction`，推入 `active_transactions`

### CommitTransaction：最复杂的方法

```
1. 获取 transaction_lock
2. 检查是否可以自动 Checkpoint（CanCheckpoint）
3. 如果需要 WAL 写入：
   a. 释放 transaction_lock
   b. 获取 WAL 锁
   c. 写入 WAL
   d. 重新获取 transaction_lock
   → 这允许只读事务在 WAL 写入期间启动/提交
4. 分配 commit_id = current_start_timestamp++
5. 确定 ActiveTransactionState（OTHER_TRANSACTIONS / NO_OTHER_TRANSACTIONS）
6. 调用 transaction.Commit(db, info, commit_state)
   → 提交 LocalStorage 和 UndoBuffer
7. 成功：更新 last_commit
8. 失败：回滚，设置 commit_id = 0
9. RemoveTransaction()：从 active_transactions 移到 recently_committed 或 cleanup_queue
10. 释放锁，执行清理，可能触发 Checkpoint
```

> **关键设计决策**：提交时间戳与开始时间戳共享同一个计数器（`current_start_timestamp`），因此它们是全序的。这保证了 Snapshot Isolation 的正确性。

## 27.3 UndoBuffer：行级版本链

### 结构

```cpp
// src/include/duckdb/transaction/undo_buffer.hpp
class UndoBuffer {
    // 链表结构，由 BufferManager 分配
    // 每个条目：[UndoFlags (4B)] [length (4B)] [payload]
};

// UndoFlags 枚举
enum class UndoFlags : uint32_t {
    CATALOG_ENTRY = 1,    // 目录修改（DDL）
    INSERT_TUPLE = 2,     // 追踪追加（AppendInfo）
    DELETE_TUPLE = 3,     // 追踪删除（DeleteInfo）
    UPDATE_TUPLE = 4,     // 追踪更新（UpdateInfo）
    SEQUENCE_VALUE = 5,   // 序列值
    ATTACHED_DATABASE = 6 // 附加数据库
};
```

UndoBuffer 是一个**追加写入的日志**——按操作顺序记录，回滚时逆序撤销。

### DeleteInfo：删除的追踪

```cpp
// src/include/duckdb/transaction/delete_info.hpp
struct DeleteInfo {
    DataTable *table;
    RowVersionManager *version_info;
    idx_t vector_idx;
    idx_t count;
    idx_t base_row;
    bool is_consecutive;   // 优化：连续行 [0,1,2,...] 无需存储行 ID
    uint16_t rows[1];      // 变长数组，每向量行偏移
};
```

### UpdateInfo：版本链的核心

```cpp
// src/include/duckdb/transaction/update_info.hpp
struct UpdateInfo {
    UpdateSegment *segment;           // 所属的列段
    DataTable *table;
    idx_t column_index;
    idx_t row_group_start;
    atomic<transaction_t> version_number;  // transaction_id 或 commit_id
    idx_t vector_index;
    sel_t N;                          // 更新的行数
    sel_t max;                        // 容量（= STANDARD_VECTOR_SIZE）
    UndoBufferPointer prev;           // 指向更旧版本
    UndoBufferPointer next;           // 指向更新版本
    // 后跟：sel_t tuples[max] + T values[max]
};
```

版本链是一个**双向链表**，通过 `prev`/`next` 指针（`UndoBufferPointer`）连接。根节点驻留在 `UpdateSegment` 的 `UpdateNode` 中（内存中，固定在列的更新结构上），后续版本存储在 UndoBuffer 中。

### 版本链的遍历与可见性

```cpp
// UpdateInfo::AppliesToTransaction
bool AppliesToTransaction(transaction_t start_time, transaction_t transaction_id) {
    if (version_number == TRANSACTION_ID_START - 1) return true;  // 根节点
    return version_number > start_time && version_number != transaction_id;
}
```

一个版本对当前事务"可见"意味着：它是在我们快照之后提交的（`version_number > start_time`），或者是我们自己做的（`version_number == transaction_id`）。`UpdatesForTransaction` 从最新到最老遍历链，对每个可见的 `UpdateInfo` 调用回调。

## 27.4 可见性规则：Snapshot Isolation

DuckDB 实现 **Snapshot Isolation**（不是完全的 Serializable）。每个事务看到 `start_time` 时刻的一致快照。

### 插入的可见性

```
行有 insert_id → 可见当 insert_id < start_time || insert_id == transaction_id
含义：行在我们快照之前已提交，或者我们自己插入的
```

### 删除的可见性

```
行有 delete_id → 已删除当 delete_id < start_time || delete_id == transaction_id
NOT_DELETED_ID (2^64-2) 表示未删除
```

### 更新的可见性

```
更新版本 → 应用当 version_number > start_time && version_number != transaction_id
注意：这是"反向"逻辑——返回 true 的版本是比快照更新的
遍历时从最新到最老应用可见的更新
```

## 27.5 提交、回滚与清理

### CommitState::CommitEntry

```cpp
// src/transaction/commit_state.cpp
// CATALOG_ENTRY: 更新目录条目时间戳为 commit_id
// INSERT_TUPLE: 调用 table->CommitAppend(commit_id, start_row, count)
//   → 在 RowVersionManager 中标记行为已提交
// DELETE_TUPLE: 调用 CommitDelete，更新 RowVersionManager 删除标记为 commit_id
// UPDATE_TUPLE: 设置 info->version_number = commit_id
//   → 这是使更新对其他事务可见的关键步骤
```

`UPDATE_TUPLE` 的处理特别精妙：将 `version_number` 从 `transaction_id` 改为 `commit_id`。由于 `commit_id < TRANSACTION_ID_START` 且 `commit_id > start_time`（对于之后开始的事务），这个赋值原子性地使更新对所有新事务可见。

### RollbackState::RollbackEntry

```cpp
// src/transaction/rollback_state.cpp
// CATALOG_ENTRY: 撤销目录变更
// INSERT_TUPLE: 调用 table->RevertAppend() → 物理删除追加的行
// DELETE_TUPLE: 将删除标记设回 NOT_DELETED_ID
// UPDATE_TUPLE: 调用 segment->RollbackUpdate() → 恢复基础数据，从链中摘除 UpdateInfo
```

### CleanupState::CleanupEntry

当没有活跃事务需要旧版本时调用。从链中移除 `UpdateInfo`，清理追加元数据，处理删除行的索引清理。

> **与 PostgreSQL VACUUM 的对比**：PostgreSQL 需要独立的 VACUUM 进程回收死元组空间。DuckDB 在每次提交后主动清理（通过 `cleanup_queue`），因为 `ChunkInfo` 元数据很紧凑（只是事务 ID，不是完整行数据），不需要单独的 VACUUM 来回收可见性空间。

## 27.6 LocalStorage：事务私有缓冲区

```cpp
// src/include/duckdb/transaction/local_storage.hpp
class LocalStorage {
    LocalTableManager table_manager; // DataTable → LocalTableStorage 映射
};

class LocalTableStorage {
    OptimisticWriteCollection row_groups; // 实际数据行
    TableIndexList append_indexes;        // 本地索引（约束检查）
    TableIndexList delete_indexes;        // 删除索引（唯一性检查）
    OptimisticDataWriter optimistic_writer; // 可提前写入磁盘
    idx_t deleted_rows;                   // 从本地存储删除的行数
};
```

LocalStorage 是**未提交追加的事务私有缓冲区**。新行对其他事务不可见，存储在独立的 `RowGroupCollection` 中。行 ID 从 `MAX_ROW_ID + offset` 开始。

### 追加路径

```
DataTable::LocalAppend():
1. 验证约束（唯一索引、NOT NULL、CHECK、FK）——检查全局和本地索引
2. 追加到 LocalStorage 的 RowGroupCollection
3. 本地行的 RowID 从 MAX_ROW_ID + offset 开始
```

### 删除路径

```
DataTable::Delete():
1. 拆分行 ID：本地 (>= MAX_ROW_ID) 和 全局 (< MAX_ROW_ID)
2. 本地删除 → LocalStorage::Delete()：从本地索引移除，标记为已删除
3. 全局删除 → row_groups->Delete()：在 RowVersionManager 中标记，创建 DeleteInfo 到 UndoBuffer
```

### 提交时的合并

```
LocalStorage::Commit() / Flush():
1. 如果没有剩余行（全部插入+删除）：回滚
2. 如果表为空或批量追加：直接移动 RowGroup 到主表（MergeStorage）
3. 否则：扫描并重新追加到主表
4. 推送 AppendInfo 到 UndoBuffer 用于合并的行
```

> **与 PostgreSQL 的对比**：PostgreSQL 的所有 INSERT 直接写入共享堆，通过 `xmin/xmax` 控制可见性。DuckDB 的 LocalStorage 是一个优化——未提交的行不污染主表，提交时批量合并。这在 OLAP 场景下（批量 INSERT）特别高效。

## 27.7 写写冲突检测：先提交者赢

DuckDB 检测写写冲突的方式是**悲观的行级检查**：

### 删除冲突

```cpp
// src/storage/table/chunk_info.cpp
// ChunkVectorInfo::Delete():
// 如果一行已被另一个事务标记删除（deleted[rows[i]] != NOT_DELETED_ID）
// → 抛出 TransactionException("Conflict on tuple deletion!")
```

### 更新冲突

```cpp
// src/storage/table/update_segment.cpp
// CheckForConflicts():
// 遍历版本链，如果另一个事务更新了同一行
// → 检查行 ID 是否重叠，重叠则抛出 TransactionException
```

### DDL 冲突

```cpp
// 如果一个表已被另一个事务 ALTER 或 DROP
// → 后续写操作抛出 TransactionException
```

### 单数据库写入约束

```cpp
// MetaTransaction::ModifyDatabase():
// 一个事务只能写一个附加数据库
```

这些机制实现了**先提交者赢**语义：第一个修改行的事务成功，并发修改同一行的事务收到冲突错误。

## 27.8 Lock-Free 读取路径

读取在大部分路径上是无锁的：

- `DataTable::Scan()`：调用 `row_groups->Scan()` 然后 `local_storage.Scan()`——基础数据的读路径无锁
- `RowVersionManager::GetSelVector()`：获取 `version_lock`（mutex），但 `ChunkVectorInfo` 的实际数据访问使用无锁的 `FixedSizeAllocator` 句柄
- `UpdateSegment::FetchUpdates()`：使用 `lock.GetSharedLock()`（自旋锁）获取根更新节点，然后不持锁遍历版本链

版本链的遍历设计为无锁：`UndoBufferPointer` 允许钉住（递增引用计数）缓冲区块，然后无锁读取。

## 本章小结

DuckDB 的 MVCC 设计遵循一个清晰的原则：**为 OLAP 场景优化，不为 OLTP 兼容**。

| 特性 | DuckDB | PostgreSQL |
|------|--------|------------|
| 隔离级别 | Snapshot Isolation | Read Committed / Serializable |
| 版本存储 | UndoBuffer（事务私有） | 堆表内（新老版本共存） |
| 追加优化 | LocalStorage + 批量合并 | 直接写入共享堆 |
| 更新方式 | In-place + 版本链 | Delete + Insert（总是创建新元组） |
| 删除标记 | ChunkVectorInfo 数组 | 元组头 xmax 字段 |
| 垃圾回收 | 提交后主动清理 | VACUUM（独立进程） |
| 死锁检测 | 无（单写者约束） | 有（wait-for 图检测） |

DuckDB 放弃了 PostgreSQL 的完全 Serializable 隔离和精细锁管理，换来了更简单的实现和更低的读取开销。在 OLAP 场景下，这是一个正确的取舍——分析查询几乎不修改数据，它们需要的是无阻碍的读取速度。
