# 第21章：存储架构概览

> 存储是数据库的"肉体"——SQL 再优雅、优化器再聪明，数据终究要落在磁盘上、读进内存里。DuckDB 的存储架构围绕一个核心约束设计：单文件、零配置、进程内。这个约束塑造了一切。

## 21.1 StorageManager：全局存储入口

```cpp
// src/include/duckdb/storage/storage_manager.hpp
class StorageManager {
public:
    AttachedDatabase &db;           // 所属的附加数据库
    string path;                    // 数据库文件路径，或 IN_MEMORY_PATH
    string wal_path;                // WAL 文件路径
    unique_ptr<WriteAheadLog> wal;  // 写前日志
    mutex wal_lock;                 // WAL 写入互斥锁
    bool read_only;                 // 只读模式
    bool load_complete;             // 加载完成门控
    atomic<idx_t> wal_size;        // WAL 大小（自动 Checkpoint 触发）
    atomic<idx_t> wal_entries_count; // WAL 条目数
    StorageOptions storage_options; // 存储选项（块大小、加密等）

    // 纯虚接口
    virtual void AutomaticCheckpoint(idx_t estimated_wal_bytes) = 0;
    virtual unique_ptr<StorageCommitState> GenStorageCommitState(WriteAheadLog &wal) = 0;
    virtual bool IsCheckpointClean(MetaBlockPointer checkpoint_id) = 0;
    virtual void CreateCheckpoint(QueryContext context, CheckpointOptions options) = 0;
    virtual idx_t GetDatabaseSize() = 0;
};
```

`StorageManager` 是一个抽象基类——唯一的具体实现是 `SingleFileStorageManager`。这不是过度设计，而是为 `StorageExtension`（自定义存储后端）留出了扩展点。

### StorageCommitState：事务提交的存储接口

```cpp
// src/include/duckdb/storage/storage_manager.hpp
class StorageCommitState {
public:
    virtual void RevertCommit() = 0;  // 回滚
    virtual void FlushCommit() = 0;   // 持久化
    // 乐观写入：提交前数据已落盘，成功后复用 Block 指针
    virtual void AddRowGroupData(DataTableInfo &info, idx_t row_group_start,
                                 unique_ptr<PersistentCollectionData> data) = 0;
    virtual PersistentCollectionData *GetRowGroupData(DataTableInfo &info,
                                                       idx_t row_group_start) = 0;
};
```

`StorageCommitState` 中最有趣的设计是**乐观写入（Optimistic Write）**：数据可以在事务提交前就写入磁盘 Block。如果提交成功，这些 Block 指针在下次 Checkpoint 时直接复用；如果回滚，则标记 Block 为空闲。这避免了 Checkpoint 时重写数据，但也增加了提交协议的复杂度。

### 初始化的三条路径

```cpp
// src/storage/storage_manager.cpp
// SingleFileStorageManager::LoadDatabase() 的三条路径：
```

`StorageManager::Initialize()` 调用纯虚 `LoadDatabase()`，而 `SingleFileStorageManager` 根据场景选择三条路径：

**路径 1：内存模式**（`path == IN_MEMORY_PATH`）
- 创建 `InMemoryBlockManager`（所有 I/O 方法直接抛异常——空对象模式）
- 没有 WAL，没有文件，数据随进程消亡

**路径 2：新文件**
- 创建 `SingleFileBlockManager`
- 调用 `CreateNewDatabase()` 写入三文件头结构（MainHeader + DatabaseHeader × 2）
- 创建 WAL 和 `SingleFileTableIOManager`

**路径 3：已有文件**
- 创建 `SingleFileBlockManager`
- 调用 `LoadExistingDatabase()`：读取文件头、验证魔术字节、加载空闲列表
- 通过 `SingleFileCheckpointReader::LoadFromStorage()` 加载 Checkpoint
- 通过 `WriteAheadLog::Replay()` 重放 WAL

> **设计决策**：构造与初始化分离。加载可能需要 `QueryContext`（用于 profiling），而构造函数不接受这个参数。`load_complete` 标志防止在加载阶段访问 WAL。

## 21.2 存储层次：Database → Schema → Table → Segment

DuckDB 的存储层次不是抽象概念——每一层都有对应的 C++ 类，且层与层之间的所有权关系清晰：

```
DatabaseInstance
  └── DatabaseManager
       ├── AttachedDatabase (system)    ── 无 StorageManager
       ├── AttachedDatabase (temp)      ── SingleFileStorageManager (内存)
       └── AttachedDatabase (user)      ── SingleFileStorageManager
            ├── StorageManager
            │    ├── BlockManager (SingleFileBlockManager / InMemoryBlockManager)
            │    ├── WriteAheadLog
            │    └── TableIOManager
            ├── Catalog (DuckCatalog)
            │    └── SchemaCatalogEntry
            │         └── DuckTableEntry
            └── TransactionManager (DuckTransactionManager)

DuckTableEntry
  └── DataTable
       └── RowGroupCollection
            └── RowGroup (SegmentBase<RowGroup>)
                 └── ColumnData (每列一个)
                      └── ColumnSegment (SegmentBase<ColumnSegment>)
                           └── BlockHandle → 磁盘 Block
```

### AttachedDatabase：四种形态

```cpp
// src/include/duckdb/main/attached_database.hpp
enum class AttachedDatabaseType : uint8_t {
    SYSTEM_DATABASE,     // 内置函数、类型——无存储
    TEMP_DATABASE,       // 会话临时表——内存 SingleFileStorageManager
    READ_ONLY_DATABASE,  // 只读附加
    READ_WRITE_DATABASE  // 读写附加
};
```

一个 DuckDB 实例至少有两个 `AttachedDatabase`：系统数据库（SYSTEM_DATABASE）和临时数据库（TEMP_DATABASE）。用户通过 `ATTACH` 语句添加的数据库是 READ_WRITE_DATABASE 或 READ_ONLY_DATABASE。

每种形态有不同的构造路径：

1. **系统/临时**：无文件路径。临时数据库创建内存版 `SingleFileStorageManager`
2. **标准文件**：创建 `DuckCatalog` + `SingleFileStorageManager` + `DuckTransactionManager`
3. **存储扩展**：委托给扩展的 `attach()` 回调创建 Catalog 和 TransactionManager

### DatabaseManager：Attach 的守门人

```cpp
// src/include/duckdb/main/database_manager.hpp
class DatabaseManager {
    shared_ptr<AttachedDatabase> system;        // 系统数据库
    case_insensitive_map_t<shared_ptr<AttachedDatabase>> databases; // 用户数据库
    shared_ptr<DatabaseFilePathManager> path_manager; // 防止同一文件被打开两次
    string default_database;                    // 默认数据库名
    // 事务 ID 和查询编号计数器
};
```

`DatabaseManager::AttachDatabase()` 的完整流程：

1. **远程文件检查**：s3://、https:// 等远程路径自动设为只读
2. **路径去重**：通过 `DatabaseFilePathManager` 注册路径，防止同一文件被同一进程打开两次——这是避免并发写入损坏的关键
3. **数据库类型检测**：通过魔术字节判断文件类型（DuckDB、SQLite 等），需要扩展的自动加载
4. **创建 AttachedDatabase**：委托给 `DatabaseInstance::CreateAttachedDatabase()`
5. **初始化**：对后续附加的数据库，立即调用 `Initialize()` 和 `FinalizeLoad()`
6. **注册**：插入 `databases` map，处理 `REPLACE_ON_CONFLICT`，推送到系统事务管理器

### 路径去重：DatabaseFilePathManager

```cpp
// src/include/duckdb/main/database_file_path_manager.hpp
class DatabaseFilePathManager {
    struct DatabasePathInfo {
        string name;
        AccessMode access_mode;
        reference_set_t<DatabaseManager> attached_databases;
        idx_t reference_count;
    };
    case_insensitive_map_t<DatabasePathInfo> db_paths; // macOS/Windows 大小写不敏感
};
```

这个类防止同一文件被打开两次。它维护路径到 `DatabasePathInfo` 的映射。如果另一个线程正在附加同一路径，调用者等待。`InsertDatabasePath` / `EraseDatabasePath` 生命周期确保独占访问。

> **跨平台细节**：在 macOS/Windows 上，路径比较是大小写不敏感的（因为文件系统如此）。在 Linux 上是大小写敏感的。

## 21.3 单文件存储模式

DuckDB 将一切——目录、数据、索引、空闲列表——存储在单个文件中。这是与 SQLite 一脉相承的设计选择。

### 文件布局

```
偏移量         内容                     大小
0              MainHeader               4096 字节
4096           DatabaseHeader h1        4096 字节
8192           DatabaseHeader h2        4096 字节
12288+         数据块                   每块 block_alloc_size（默认 262144 = 256KB）
```

### MainHeader：只写一次的文件头

```cpp
// src/include/duckdb/storage/storage_info.hpp
struct MainHeader {
    char magic[4] = {'D', 'U', 'C', 'K'};  // 魔术字节
    idx_t version_number;                    // 存储格式版本
    idx_t flags[4];                          // 位标志（bit 0 = 加密标志）
    char library_git_desc[32];               // Git 描述
    char library_git_hash[32];               // Git Hash
    uint8_t encryption_metadata[8];          // 加密元数据（KDF、密码等）
    char db_identifier[16];                  // 数据库唯一标识（也用作加密盐）
    uint8_t encrypted_canary[8];             // 加密金丝雀 "DUCKKEY"
    uint8_t canary_iv[12];                   // GCM IV
    uint8_t canary_tag[16];                  // GCM Tag
};
```

MainHeader 在文件创建时写入，之后不再修改。加密金丝雀机制：启用加密时，已知明文 "DUCKKEY" 用派生密钥加密。加载时解密金丝雀并比对——不匹配则密钥错误。

### DatabaseHeader：双头切换的崩溃安全

```cpp
// src/include/duckdb/storage/storage_info.hpp
struct DatabaseHeader {
    idx_t iteration;              // 每次	Checkpoint 递增
    MetaBlockPointer meta_block;  // 元数据根指针
    idx_t free_list;              // 空闲块列表指针
    idx_t block_count;            // 文件中的总块数
    idx_t block_alloc_size;       // 块分配大小（默认 262144）
    idx_t vector_size;            // 必须匹配 STANDARD_VECTOR_SIZE
    idx_t serialization_compatibility; // 存储版本
};
```

两个 `DatabaseHeader` 副本（h1、h2）是崩溃安全的核心机制。活跃头是 `iteration` 更大的那个。Checkpoint 时写入非活跃头，然后切换——如果写入过程中崩溃，旧头仍然有效，数据库回退到上一个一致的 Checkpoint。

### SingleFileBlockManager：块的生命周期

```cpp
// src/include/duckdb/storage/single_file_block_manager.hpp
class SingleFileBlockManager : public BlockManager {
    uint8_t active_header;                // 当前活跃头（0 或 1）
    unique_ptr<FileHandle> handle;        // 打开的文件句柄
    set<block_id_t> free_list;            // 可复用的块
    set<block_id_t> free_blocks_in_use;   // 已释放但被 BufferManager 钉住的块
    set<block_id_t> newly_used_blocks;    // 本轮 Checkpoint 新分配的块
    unordered_set<block_id_t> modified_blocks; // 当前 epoch 释放的块
    block_id_t max_block;                 // 已分配的最大块 ID
};
```

块的空闲列表有多个阶段，这是一个精心设计的状态机：

1. **`newly_used_blocks`**：Checkpoint 周期内新分配的块
2. `MarkBlockAsCheckpointed()`：块从 `newly_used_blocks` 移出
3. `MarkBlockAsModified()`：如果块在 `newly_used_blocks` 中，移到 `free_list`；否则移到 `modified_blocks`
4. `WriteHeader()`：所有 `modified_blocks` 合入 `free_list`

这种多阶段设计确保了：被当前磁盘头引用的块不会在头更新前被复用。

### 双 WAL 设计

Checkpoint 期间，DuckDB 使用双 WAL 确保并发事务不被阻塞：

```
WALStartCheckpoint() 流程：
1. 获取 WAL 锁
2. 写 Checkpoint 记录到主 WAL，刷新
3. 关闭主 WAL
4. 打开新的 Checkpoint WAL（<db>.wal.checkpoint）
   → 并发写入在此期间进入 Checkpoint WAL

WALFinishCheckpoint() 流程：
- 如果 Checkpoint WAL 无写入（常见情况）：删除主 WAL，重建空 WAL
- 如果 Checkpoint WAL 有写入（并发提交）：将 Checkpoint WAL 移动为主 WAL
```

这保证了 Checkpoint 期间，其他事务可以继续提交。

### 自动 Checkpoint 触发

两个阈值触发自动 Checkpoint：
1. **大小阈值**：`expected_wal_size > config.checkpoint_wal_size`
2. **条目阈值**（如果启用）：`GetWALEntriesCount() >= entry_limit`

## 21.4 加密：每块独立加密

```cpp
// DuckDB 支持 AES-GCM 和 AES-CTR 加密
// 每个块独立加密——允许随机访问加密块而无需解密整个文件
// 每块的 IV/Tag 开销：40 字节
```

加密流程：

1. 用户通过 `ATTACH ... (ENCRYPTION_KEY '...')` 提供密钥
2. 生成随机 `db_identifier`（16 字节）作为盐
3. 通过 `EncryptionKeyManager::DeriveKey()` 使用 SHA-256 派生密钥
4. 加密已知明文 "DUCKKEY" 存入 MainHeader 的金丝雀
5. 加载时解密金丝雀验证密钥
6. 每个块的读写通过 `EncryptionEngine::EncryptBlock/DecryptBlock`

MainHeader 本身不加密（包含盐和金丝雀用于密钥验证），两个 DatabaseHeader 和所有数据块都加密。

## 21.5 MetadataManager：小块管理器

```cpp
// src/include/duckdb/storage/metadata/metadata_manager.hpp
class MetadataManager {
    // 每个存储块被划分为 64 个元数据块
    static constexpr idx_t METADATA_BLOCK_COUNT = 64;
    // 元数据块大小 = block_alloc_size / 64 = 256KB / 64 = 4KB
};
```

元数据块用于存储目录元信息（Schema 定义、表定义、RowGroup 指针等）。`MetadataWriter` / `MetadataReader` 提供在这些小块上的流式序列化。大块分小块的设计避免了为几 KB 的元数据分配一整块 256KB 的空间。

## 21.6 InMemoryBlockManager：空对象模式

```cpp
// src/include/duckdb/storage/in_memory_block_manager.hpp
class InMemoryBlockManager : public BlockManager {
    // 所有 I/O 方法直接抛出 InternalException("Cannot perform IO in in-memory database")
};
```

内存数据库的 BlockManager 是空对象模式的典范——所有 I/O 方法直接抛异常。这避免了在代码中到处检查 `if (in_memory)` 的条件分支，代价是内存场景下的意外 I/O 是运行时错误而非编译时检查。

## 21.7 关闭与清理

```cpp
// src/main/attached_database.cpp
void AttachedDatabase::Close() {
    // 可选 Checkpoint（由 DatabaseCloseAction 和 config 控制）
    // 然后调用 Cleanup()，按序销毁：
    // transaction_manager → catalog → storage → stored_database_path
}
```

`InvokeCloseIfLastReference()` 模式使用共享互斥锁：获取 `close_lock`，检查 `use_count` 是否为 1（最后一个引用），如果是则调用 `Close()`。这防止了一个线程关闭数据库而另一个线程仍在使用的竞争。

## 本章小结

DuckDB 的存储架构围绕三个核心选择：

1. **单文件**：一切在一个文件中——简化部署，避免文件系统开销，但限制了 I/O 层面的并行度
2. **双头切换**：两个 DatabaseHeader + 递增 iteration 实现无日志的原子头切换——只恢复到最后一个 Checkpoint，没有头的 undo log
3. **延迟加载**：RowGroup 中的列数据首次访问时才加载，用每列原子标志实现线程安全——减少启动时间和内存占用

与 PostgreSQL 的对比：PostgreSQL 每个表一个文件（甚至每个索引一个文件），数据目录下有上千个文件。DuckDB 一个文件包打天下。这是嵌入式与服务器端的根本差异——嵌入式追求"一个文件走天下"，服务器端追求"并行 I/O 最大化"。

与 Spark 的对比：Spark 根本没有自己的存储格式——它依赖 Parquet/ORC 文件 + Hive Metastore。DuckDB 既有自己的存储格式，又能无缝读取 Parquet。这种"自有格式 + 开放格式双修"是嵌入式分析引擎的独特定位。
