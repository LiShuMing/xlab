# 第22章：Block 与 Buffer 管理

> 内存是战场。DuckDB 需要在有限的内存中同时容纳扫描数据、Hash 表、排序缓冲、中间结果——而操作系统、其他进程也在争抢同一块物理内存。BufferManager 就是这场战争的指挥官。

## 22.1 Block：256KB 的基础 IO 单元

```cpp
// src/include/duckdb/storage/block.hpp
class Block : public FileBuffer {
    block_id_t id;  // 唯一标识
    // 构造函数断言：(AllocSize() & (SECTOR_SIZE - 1)) == 0
};
```

Block 是 DuckDB 所有磁盘 I/O 的基本单位。它继承自 `FileBuffer`——后者是所有扇区对齐内存缓冲区的基类：

```cpp
// src/include/duckdb/common/file_buffer.hpp
class FileBuffer {
    data_ptr_t buffer;           // 用户数据指针（跳过 header）
    uint64_t size;               // 用户可见大小
    data_ptr_t internal_buffer;  // 实际分配指针（包含 header）
    uint64_t internal_size;      // 总分配大小，扇区对齐
    FileBufferType type;         // BLOCK / MANAGED_BUFFER / TINY_BUFFER / EXTERNAL_FILE
};
```

### 为什么是 256KB？

```cpp
// src/include/duckdb/storage/storage_info.hpp
constexpr idx_t DEFAULT_BLOCK_ALLOC_SIZE = 262144;   // 256KB
constexpr idx_t DEFAULT_BLOCK_HEADER_STORAGE_SIZE = 8; // 8 字节校验和
constexpr idx_t DEFAULT_BLOCK_SIZE = 262136;          // 可用载荷 = 256KB - 8
constexpr idx_t SECTOR_SIZE = 4096;                   // 磁盘扇区大小（O_DIRECT 对齐）
```

256KB 是一个刻意权衡的选择：
- **足够大**：减少每 MB 的系统调用次数，提升顺序 I/O 吞吐
- **足够小**：避免块部分填充时的内存浪费
- **2 的幂**：简化对齐（编译时断言验证，`storage_info.hpp` 第 243-245 行）
- 每块的 8 字节 header 存储校验和，读写时由 `SingleFileBlockManager` 计算和验证

### BlockPointer 与 MetaBlockPointer：两级寻址

```cpp
// src/include/duckdb/storage/block.hpp
struct BlockPointer {
    block_id_t block_id;  // 块 ID
    uint32_t offset;      // 块内偏移
};

struct MetaBlockPointer {
    idx_t block_pointer;  // 编码了 block_id 和 block_index 的 64 位值
    uint32_t offset;      // 偏移
};
```

`BlockPointer` 是直接引用，`MetaBlockPointer` 是元数据层的间接引用——将块 ID 和块索引编码在一个 64 位值中，用于目录元信息的寻址。

## 22.2 BufferManager 与 BufferPool

### BufferManager：抽象接口

```cpp
// src/include/duckdb/storage/buffer_manager.hpp
class BufferManager {
    // 核心接口
    virtual BufferHandle Pin(shared_ptr<BlockHandle> &handle) = 0;
    virtual void Unpin(shared_ptr<BlockHandle> &handle) = 0;
    virtual shared_ptr<BlockHandle> Allocate(MemoryTag tag, idx_t block_size,
                                              DestroyBufferUpon can_destroy) = 0;
    // 临时内存
    virtual shared_ptr<BlockHandle> RegisterTransientMemory(idx_t size, ...) = 0;
    virtual shared_ptr<BlockHandle> RegisterSmallMemory(MemoryTag tag, idx_t size) = 0;
};
```

`DestroyBufferUpon` 策略控制缓冲区的生命周期：
- `BLOCK`（默认）：可以驱逐（需要时写入临时文件）
- `EVICTION`：驱逐时销毁而非写入临时文件（用于可重算的数据）
- `UNPIN`：Unpin 后立即销毁（极短命数据）

### BufferPool：全局内存仲裁器

```cpp
// src/include/duckdb/storage/buffer/buffer_pool.hpp
class BufferPool {
    // 多队列驱逐架构
    static constexpr idx_t EVICTION_QUEUE_TYPES = 3;
    // BLOCK_AND_EXTERNAL_FILE: 驱逐优先级最高（直接释放内存）
    // MANAGED_BUFFER: 驱逐优先级居中（需写入临时文件），6 个子队列
    // TINY_BUFFER: 驱逐优先级最低（最后手段）
};
```

BufferPool 是单个 DuckDB 实例中所有数据库共享的全局内存管理器。它的驱逐架构采用**多优先级队列**设计：

```
驱逐优先级（从高到低）：
┌─────────────────────────────────────────────┐
│ BLOCK_AND_EXTERNAL_FILE (1个子队列)          │  ← 直接释放内存
├─────────────────────────────────────────────┤
│ MANAGED_BUFFER (6个子队列)                    │  ← 需写入临时文件
├─────────────────────────────────────────────┤
│ TINY_BUFFER (1个子队列)                       │  ← 最后手段
└─────────────────────────────────────────────┘
```

### 无锁驱逐队列

```cpp
// src/storage/buffer/buffer_pool.cpp
typedef duckdb_moodycamel::ConcurrentQueue<BufferEvictionNode> eviction_queue_t;
```

驱逐队列使用 moodycamel 的无锁并发队列。每个 `BufferEvictionNode` 持有 `weak_ptr<BlockMemory>` 和一个序列号。序列号的关键作用：当一个块被 Unpin 又被 Pin 时，序列号递增，使队列中的旧条目失效。

### 死节点管理

队列中的死节点（BlockHandle 已销毁或被更新的条目替代）通过定期清理机制处理：

- 每 4096 次插入触发一次清理（`INSERT_INTERVAL`）
- 清理算法：批量出队，过滤存活节点，批量重新入队
- 如果存活:死亡比率低于 1:4，则继续积极清理

### Per-CPU 内存计数器

```cpp
// src/storage/buffer/buffer_pool.cpp
struct MemoryUsage {
    static constexpr idx_t MEMORY_USAGE_CACHE_COUNT = 64;      // 64 个 CPU 本地缓存
    static constexpr idx_t MEMORY_USAGE_CACHE_THRESHOLD = 32768; // 32KB 刷新阈值
};
```

频繁的小额内存分配/释放（如 `BufferPoolReservation::Resize()`）如果每次都原子更新全局计数器，会导致严重的缓存行争用。Per-CPU 缓存的设计：小更新进入 CPU 本地缓存，超过 32KB 阈值时才刷新到全局计数器。

## 22.3 BlockHandle 与 BlockMemory

```cpp
// src/include/duckdb/storage/buffer/block_handle.hpp
class BlockMemory {
    atomic<BlockState> state;      // BLOCK_LOADED / BLOCK_UNLOADED
    atomic<idx_t> readers;         // 活跃 BufferHandle 引用计数
    unique_ptr<FileBuffer> buffer; // 缓冲区（卸载时为 null）
    idx_t eviction_seq_num;        // Unpin 时递增，使旧驱逐条目失效
    DestroyBufferUpon destroy_buffer_upon; // 销毁策略
    BufferPoolReservation memory_charge;   // 内存"账单"
};

class BlockHandle {
    shared_ptr<BlockMemory> block; // 共享引用
};
```

`BlockHandle` 是客户端持有的共享引用计数句柄。`BlockMemory` 是内部状态——两者分离使得 BufferPool 可以持有 `weak_ptr<BlockMemory>` 而不阻止块被驱逐。

### Pin 流程

```
1. 锁定 BlockMemory
2. 如果已加载 → 快速路径：递增 readers
3. 如果未加载：
   a. 调用 EvictBlocksOrThrow 腾出空间
   b. 重新锁定并双重检查（另一个线程可能已加载）
   c. 如果仍然未加载：调用 BlockHandle::Load()
      - 持久块（block_id < MAXIMUM_BLOCK）：分配 Block，从磁盘读取
      - 临时块且 MustWriteToTemporaryFile：从临时文件读取
      - 临时块且非 MustWriteToTemporaryFile：返回无效句柄（已销毁）
   d. 转移 BufferPoolReservation 到 BlockMemory 的 memory_charge
```

### Unpin 流程

```
1. 锁定 BlockMemory，递减 readers
2. 如果 readers 降为 0：
   a. 如果 MustAddToEvictionQueue()：加入驱逐队列
   b. 否则（DestroyBufferUpon::UNPIN）：立即 Unload()
3. 如果需要清理队列：调用 PurgeQueue
```

### BufferHandle：RAII Pin

```cpp
// src/include/duckdb/storage/buffer/buffer_handle.hpp
class BufferHandle {
    shared_ptr<BlockHandle> handle;  // 持有引用
    FileBuffer *buffer;              // 原始指针（不持有）
    // 析构函数调用 BufferManager::Unpin()
    // 不可复制，只可移动——符合 RAII Pin 语义
};
```

## 22.4 StandardBufferManager

```cpp
// src/include/duckdb/storage/standard_buffer_manager.hpp
class StandardBufferManager : public BufferManager {
    DatabaseInstance &db;
    BufferPool &buffer_pool;                           // 共享的 BufferPool
    unique_ptr<InMemoryBlockManager> temp_block_manager; // 临时块 ID 分配
    TemporaryDirectoryHandle temporary_directory;      // 临时文件目录
    atomic<block_id_t> temporary_id{MAXIMUM_BLOCK};    // 临时块 ID 计数器
};
```

`StandardBufferManager` 是 `BufferManager` 的唯一具体实现。它的关键设计决策：临时块使用 `InMemoryBlockManager` 分配 ID（因为临时块由 BufferManager 直接管理，不需要文件支持的 BlockManager）。

### 临时文件写入

```cpp
// src/storage/standard_buffer_manager.cpp
// WriteTemporaryBuffer：
// - 标准大小缓冲区 → 分组 .tmp 文件（由 TemporaryFileManager 管理）
// - 超大缓冲区 → 独立的 .block 文件
// - 支持可选加密（EncryptionEngine）
```

## 22.5 TemporaryMemoryManager：临时内存的管控策略

```cpp
// src/include/duckdb/storage/temporary_memory_manager.hpp
class TemporaryMemoryManager {
    // 由 BufferPool 拥有（非按数据库）
    // 在并发运行的算子之间动态分配内存
};

class TemporaryMemoryState {
    idx_t remaining_size;          // 算子理想需要的内存
    idx_t minimum_reservation;     // 保底保证
    idx_t reservation;             // 当前已授权内存
    idx_t materialization_penalty; // 物化代价权重
};
```

`TemporaryMemoryManager` 解决的核心问题：多个并发算子（如 HashJoin 构建、排序、聚合）如何分配有限的内存？

### 注册与最低保证

```
DefaultMinimumReservation():
    min(threads * 512 * 256KB, memory_limit / 16)
```

每个算子注册时获得一个最低内存保证。这是硬保证——即使总需求超过内存限制，每个算子至少能拿到这么多。

### UpdateState 算法

```
1. 如果 force_external：只给最低保证（外部处理模式）
2. 如果无临时目录：给全部 remaining_size（无法卸载，必须全部保留在内存中）
3. 如果超出（其他预约 + 下界 >= memory_limit）：只给最低保证
4. 否则：
   - 计算上界 = min(remaining_size, query_max_memory, 0.9 * free_memory)
   - 如果下界 >= 上界：给下界
   - 如果 remaining_size > memory_limit：调用 ComputeReservation（代价优化）
   - 否则：给上界（内存足够，人人满足）
```

### ComputeReservation：梯度下降优化

当总需求超过供给时，`TemporaryMemoryManager` 使用数值优化：

**代价函数**：
```
C = Σ(penalty_i × (1 - reservation_i/size_i)) × (1 - geomean(reservation_i/size_i))
```

这平衡两个目标：
- 最小化物化代价：`Σ(penalty_i × (1 - throughput_i))`
- 最大化整体吞吐：`1 - geomean(throughputs)`（几何平均保证公平性）

**梯度下降**（5 × n 次迭代）：
1. 每次迭代：计算导数，找到导数最低的算子（边际收益最高）
2. 分配 `ceil(remaining_memory / remaining_iterations)` 给它
3. 这是坐标下降法——总是把内存给收益最大的算子

> **与 Spark 内存管理的对比**：Spark 使用静态的 `spark.memory.fraction` 将执行内存和存储内存硬分割。DuckDB 的 `TemporaryMemoryManager` 使用动态的、基于代价优化的分配——每个算子根据其"物化代价"获得不同份额，而不是平均分配。

## 22.6 BlockAllocator：虚拟内存池

```cpp
// src/include/duckdb/storage/block_allocator.hpp
class BlockAllocator {
    // 预留大块虚拟地址空间（mmap MAP_PRIVATE | MAP_ANONYMOUS）
    // 惰性提交物理页面
    // 线程本地批处理减少全局竞争
};
```

BlockAllocator 管理一个虚拟内存空间，划分为固定大小的块：

- **Linux**：`mmap(MAP_PRIVATE | MAP_ANONYMOUS)` 预留地址空间，惰性提交
- **Windows**：`VirtualAlloc(MEM_RESERVE)` 预留，`VirtualAlloc(MEM_COMMIT)` 提交
- **macOS**：默认惰性（无需显式提交）

释放时使用 `madvise(MADV_DONTNEED)`（Linux）、`madvise(MADV_FREE_REUSABLE)`（macOS）、`VirtualFree(MEM_DECOMMIT)`（Windows）。

线程本地批处理：每个线程维护 `untouched`（未使用）和 `touched`（已使用）的块 ID 本地缓存，减少全局并发队列的竞争。

## 22.7 O_DIRECT：绕过操作系统页缓存

### 扇区对齐的三层保障

1. **FileBuffer::CalculateMemory**：所有可能涉及磁盘 I/O 的缓冲区，分配大小按 `SECTOR_SIZE = 4096` 对齐
2. **Block 构造函数**：断言 `AllocSize()` 是 `SECTOR_SIZE` 的倍数
3. **FileBuffer::Read/Write**：读写整个 `internal_buffer`，起止地址和大小都保证扇区对齐

### 平台差异

```cpp
// src/common/local_file_system.cpp
// Linux: open_flags |= O_DIRECT
// macOS: fcntl(fd, F_NOCACHE, 1)  // macOS 没有 O_DIRECT
// Windows: flags_and_attributes |= FILE_FLAG_NO_BUFFERING
// Solaris: 抛异常——不支持 O_DIRECT
```

### 8 字节 Header 与校验和

每个块的 8 字节 header 存储校验和。`SingleFileBlockManager::ReadAndChecksum` 和 `ChecksumAndWrite` 在每次读写时计算和验证。这对 O_DIRECT 至关重要——没有操作系统页缓存作为安全网，损坏的读取更容易被漏检，显式校验和是必要的防线。

### O_DIRECT 的取舍

DuckDB 的 O_DIRECT 是**可选配置**（`use_direct_io`），默认关闭：

- **不开启**：操作系统页缓存作为 BufferPool 和磁盘之间的额外缓冲。DuckDB 的 BufferPool 管理自己的内存，OS 也会缓存最近读取的块。存在冗余但安全。
- **开启**：BufferPool 是唯一的缓存，无 OS 页缓存重复。DuckDB 完全控制内存使用，但需要扇区对齐的缓冲区。

> **设计哲学**：DuckDB 的 BufferPool 比操作系统更了解访问模式（顺序扫描、随机查找等），绕过 OS 页缓存可以提升性能和内存效率。但不作为默认选项，因为 O_DIRECT 要求扇区对齐且在某些平台上存在兼容性问题。

## 本章小结

DuckDB 的 Block/Buffer 管理体现了一个核心洞察：**嵌入式数据库必须自己管理内存，不能依赖操作系统的"好心"**。

与 PostgreSQL 的对比：PostgreSQL 使用 `shared_buffers`（默认 128MB）+ OS 页缓存的双层架构，DBA 需要调优两个层次的缓存。DuckDB 的 BufferPool 是唯一的缓存层——简单、可控、可预测。

与 Spark 的对比：Spark 的执行内存通过 `MemoryManager`（UnifiedMemoryManager 或 StaticMemoryManager）静态分区。DuckDB 的 `TemporaryMemoryManager` 使用代价优化的动态分配，更适应不同算子的内存需求变化。

三个关键数字值得记住：
- **256KB**：Block 大小——I/O 吞吐与内存浪费的平衡点
- **2048**：`STANDARD_VECTOR_SIZE`——向量化执行的批大小
- **122880**：`DEFAULT_ROW_GROUP_SIZE`——RowGroup 的行数（≈ 60 个满 Vector）
