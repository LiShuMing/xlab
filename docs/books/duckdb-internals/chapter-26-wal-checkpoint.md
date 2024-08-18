# 第26章：WAL 与 Checkpoint

> 数据库的持久性承诺是"断电不丢数据"。这个承诺由 WAL（Write-Ahead Log）和 Checkpoint 共同实现：WAL 保证每次提交都先落盘，Checkpoint 定期将内存状态刷到数据库文件，两者配合实现崩溃恢复。

## 26.1 WriteAheadLog：日志格式与写入策略

### WAL 条目类型

```cpp
// src/include/duckdb/common/enums/wal_type.hpp
enum class WALType : uint8_t {
    // 目录操作
    CREATE_TABLE = 1,  DROP_TABLE = 2,
    CREATE_SCHEMA = 3, DROP_SCHEMA = 4,
    CREATE_VIEW = 5,   DROP_VIEW = 6,
    CREATE_SEQUENCE = 8, DROP_SEQUENCE = 9, SEQUENCE_VALUE = 10,
    CREATE_MACRO = 11, DROP_MACRO = 12,
    CREATE_TYPE = 13,  DROP_TYPE = 14,
    ALTER_INFO = 20,
    CREATE_INDEX = 23, DROP_INDEX = 24,
    // 数据操作
    USE_TABLE = 25,      // 设置当前表上下文
    INSERT_TUPLE = 26,
    DELETE_TUPLE = 27,
    UPDATE_TUPLE = 28,
    ROW_GROUP_DATA = 29,  // 乐观写入的行组数据
    // 控制
    WAL_VERSION = 98,
    CHECKPOINT = 99,
    WAL_FLUSH = 100
};
```

### WAL 版本与格式

```
Version 1: 无校验和
Version 2 (WAL_VERSION_NUMBER): [size: u64][checksum: u64][data]
Version 3 (WAL_ENCRYPTED_VERSION_NUMBER): [size: u64][nonce: 12B][encrypted(checksum+data)][tag: 16B]
```

每个 WAL 条目通过 `WriteAheadLogSerializer` 写入：
1. 初始化 `ChecksumWriter`，缓冲数据到 `MemoryStream`
2. 写入 `WALType` 作为第一个属性
3. `End()` 时计算校验和，写入 `[size][checksum][data]`

### 写入策略

数据条目遵循 `USE_TABLE` → 数据的模式：
- `WriteSetTable(schema, table)` 设置当前表上下文
- 然后跟 `WriteInsert(chunk)`、`WriteDelete(chunk)` 或 `WriteUpdate(chunk, column_path)`
- 索引条目：`WriteCreateIndex()` 序列化目录条目和完整索引存储信息

WAL 是**惰性初始化**的——写入器只在首次写入时创建。

### 逻辑 WAL vs 物理 WAL

DuckDB 的 WAL 是**逻辑的**（元组级）而非物理的（页级）。INSERT/DELETE/UPDATE 记录的是元组数据而非页面的字节变化。这是因为列式存储没有固定的页面布局可记录变更。

## 26.2 CheckpointManager：全量 Checkpoint 的触发与执行

### Checkpoint 触发条件

1. **大小阈值自动 Checkpoint**：`expected_wal_size > config.checkpoint_wal_size`（默认 16MB）
2. **条目阈值自动 Checkpoint**：`wal_autocheckpoint_entries` 设置大于 0 且条目数超限
3. **手动 Checkpoint**：`CHECKPOINT` SQL 命令
4. **关闭时 Checkpoint**：数据库关闭时

### Checkpoint 执行流程

```
SingleFileCheckpointWriter::CreateCheckpoint():

1. 启动 Checkpoint 事务
   → ActiveCheckpointWrapper 创建新连接，开始只读事务
   → 事务的 start_time 定义可见性边界

2. 写 Checkpoint 标记到 WAL（WALStartCheckpoint）
   → 获取 WAL 锁
   → 写 CHECKPOINT 条目 + planned meta_block 指针
   → 刷新 WAL
   → 关闭主 WAL
   → 创建 .wal.checkpoint 文件用于并发写入

3. 序列化目录
   → 扫描所有 Schema，重排表（FK 依赖），序列化到 MetadataWriter

4. 序列化表数据
   → 绑定未绑定的索引
   → 获取表 Checkpoint 锁
   → 写入行组为部分块

5. 写数据库头（WriteHeader）
   → 递增 iteration
   → 写入新的 DatabaseHeader（包含新的 meta_block 指针）
   → fsync 两次（数据 + 头）
   → 切换活跃头

6. 截断文件
   → 移除未使用的块

7. 完成 WAL Checkpoint（WALFinishCheckpoint）
   → 如果 Checkpoint WAL 无写入：删除主 WAL，创建空 WAL
   → 如果 Checkpoint WAL 有写入：移为主 WAL

8. 合并 Delta 索引
   → MergeCheckpointDeltas() 合并 Checkpoint 期间的变化

9. 提交 Checkpoint 事务
```

### 双 WAL 的并发设计

Checkpoint 期间，主 WAL 被关闭，并发事务的写入进入 `.wal.checkpoint` 文件。这保证了 Checkpoint 不阻塞其他事务的提交——一个精心设计的生产者-消费者解耦。

### 双头切换的原子性

两个 `DatabaseHeader` 副本 + 递增 `iteration` 实现"无日志的原子头切换"：

```
Checkpoint 过程中的崩溃场景：
- 写入新头之前崩溃 → 旧头有效，数据库回退到上一个 Checkpoint
- 写入新头之后崩溃 → 新头有效（iteration 更高），数据库使用新 Checkpoint
- 永远不会出现"半写头"的不一致状态
```

## 26.3 Crash Recovery 流程：WAL Replay + Undo

### 恢复入口

```cpp
// src/storage/wal/wal_replay.cpp
// WriteAheadLog::Replay() → WriteAheadLogReplayer::Replay()
```

### 恢复流程

```
1. 第一遍扫描（仅反序列化）
   → 扫描 WAL 文件寻找 CHECKPOINT 条目
   → 确定 Checkpoint 位置和 meta_block 指针
   → 确定 WAL 版本

2. Checkpoint 对账
   a. Checkpoint 完成 + 无 Checkpoint WAL → WAL 过时，无需重放
   b. Checkpoint 完成 + Checkpoint WAL 存在 → 只重放 Checkpoint WAL
   c. Checkpoint 未完成 + Checkpoint WAL 存在 → 合并主 WAL（截至 Checkpoint 位置）
      + Checkpoint WAL 为 .wal.recovery 文件，然后重放
   d. Checkpoint 未完成 + 无 Checkpoint WAL → 正常重放主 WAL

3. 第二遍扫描（实际重放）
   → 重新读取 WAL 并执行每个条目
   → ReplayCreateTable, ReplayDropTable, ReplayInsert, ReplayDelete, ReplayUpdate 等
   → 每个 WAL_FLUSH 条目触发当前事务的提交
   → 未绑定索引的操作缓冲在 BufferedIndexReplays 中
   → 序列化异常（损坏的 WAL）视为截断（除非 abort_on_wal_failure 设置）

4. 加载数据库文件
   → SingleFileCheckpointReader::LoadFromStorage()
   → 从 DatabaseHeader 读取 meta_block，反序列化整个目录和表数据
```

### Undo 机制

DuckDB 在崩溃恢复中不使用传统的 UNDO 日志。原因：

- WAL 重放对已提交事务是幂等的
- 未提交事务的 WAL 条目在 `WAL_FLUSH` 边界之外，不会被重放
- `SingleFileStorageCommitState` 的析构函数自动回滚未提交的状态——如果状态仍为 `IN_PROGRESS`，调用 `RevertCommit()` 截断 WAL

### 提交协议

```
1. WriteToWAL(): 创建 StorageCommitState，提交 LocalStorage，写入 UndoBuffer 到 WAL
2. Commit(): 提交 UndoBuffer（使变更可见），然后 FlushCommit() 刷新 WAL
3. 如果步骤 2 失败: RevertCommit() 截断 WAL 到提交前位置
```

## 26.4 与 PostgreSQL WAL 机制的对比

| 维度 | DuckDB WAL | PostgreSQL WAL |
|------|-----------|---------------|
| 目的 | 单进程 OLAP 的持久性 | 多进程 OLTP 的持久性 + 复制 |
| 架构 | 单写入者，单 .wal 文件 | 共享 WAL，多插入器（WALInsertLock） |
| 条目格式 | 二进制序列化（size + checksum + data） | XLogRecord + RMGR ID + CRC |
| 逻辑 vs 物理 | 逻辑（INSERT/DELETE/UPDATE 元组） | 物理（页级变更） |
| Checkpoint | 仅全量 Checkpoint；冻结写入 | 增量 Checkpoint + bgwriter |
| Checkpoint 期间并发 | 写入进入 .wal.checkpoint | WAL 继续正常；Checkpoint 跟踪 redo 位置 |
| 恢复 | 从头重放所有 WAL 条目 | 从最后 Checkpoint 的 REDO + UNDO |
| WAL 回收 | 每次 Checkpoint 替换文件 | WAL 段回收/归档 |
| 复制 | 无 WAL 复制 | 流复制、逻辑解码 |
| FSYNC 频率 | 每事务提交 | 每提交 + 组提交 |
| 加密 | WAL 版本 3：每条目 AES-GCM/CTR | 无内置 WAL 加密 |

### 关键设计差异

1. **逻辑 WAL**：DuckDB 记录元组级操作，因为列存没有固定页面布局。PostgreSQL 记录页级变更，因为行存的页面是自包含的

2. **无复制需求**：DuckDB 是单进程嵌入式引擎，不需要 WAL 复制。PostgreSQL 的整个复制生态（流复制、逻辑解码、WAL 归档）在 DuckDB 中不存在

3. **全量 vs 增量 Checkpoint**：DuckDB 每次 Checkpoint 写入完整的数据库状态。PostgreSQL 使用 bgwriter 增量刷脏页。这是嵌入式与服务器端的根本差异——嵌入式可以接受"暂停写入做 Checkpoint"，服务器端不能

4. **双 WAL 策略**：DuckDB 用文件级交换（main WAL ↔ checkpoint WAL）避免阻塞写入者。PostgreSQL 用位置跟踪（redo 位置）实现同样的目标，但更复杂

## 本章小结

DuckDB 的 WAL/Checkpoint 机制是"为嵌入式 OLAP 定制"的典型：

- **逻辑 WAL**：元组级而非页级，匹配列存的特性
- **全量 Checkpoint**：简单可靠，嵌入式场景下可接受
- **双 WAL + 双头**：在不牺牲并发性的前提下实现崩溃安全
- **无复制**：嵌入式不需要

与 Spark 的对比：Spark 没有内置的 WAL/Checkpoint——它依赖 HDFS 的副本机制和 RDD 血统重算。DuckDB 需要自己保证持久性，因为没有外部存储系统可以依赖。这是"计算就是存储"与"计算靠近存储"的根本差异——前者必须自己管理持久性，后者可以委托给存储层。
