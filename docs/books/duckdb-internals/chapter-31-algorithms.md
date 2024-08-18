# 第31章：DuckDB 的算法与数据结构精华

> 数据库不是"用了什么算法"的问题，而是"在什么约束下选择了什么算法"的问题。DuckDB 的算法选择始终围绕三个约束：嵌入式（内存有限）、列式（向量友好）、单进程（无需分布式协调）。

## 31.1 PerfectHashTable 与分治聚合

### PerfectHashTable：消除哈希的哈希表

当 Join 键的值域很小时，DuckDB 用一个直接映射数组替代通用哈希表：

```cpp
// src/include/duckdb/execution/operator/join/perfect_hash_join_executor.hpp
using PerfectHashTable = vector<buffer_ptr<DictionaryEntry>>;

struct PerfectHashJoinStats {
    int64_t build_min;
    int64_t build_max;
    bool is_build_small;
    bool is_build_dense;  // 所有槽位都被占用
    idx_t build_range;
};
```

**触发条件**（`CanDoPerfectHashJoin`）：
- INNER Join，单个整数等值条件
- 无残余谓词
- 无嵌套类型（STRUCT/LIST/ARRAY）
- 构建端值域 `max - min <= 1,048,576`（`MAX_BUILD_SIZE`）
- 行数不超过值域（无重复溢出）

**构建**：每个构建端输出列分配 `build_range + 1` 个条目。当所有槽位都被占用（`unique_keys == build_size && !ht.has_null`），`is_build_dense` 标志设为 true，启用探测快速路径。

**探测**：`idx = input_value - min_value`，检查位图 `bitmap_build_idx.RowIsValid(idx)`。如果构建端密集且所有探测键匹配，左表列直接引用无需拷贝——极致的零拷贝。

```
普通 HashJoin 探测:
  hash(key) → 桶查找 → 链遍历 → 键比较 → 行匹配
  平均 3-4 次内存访问

PerfectHashJoin 探测:
  key - min → 数组下标 → 位图检查 → 直接引用
  恰好 1 次内存访问
```

**过滤器下推**：`PerfectHashJoinFilter` 将完美哈希位图的知识下推到探测端表扫描——在扫描阶段就过滤不可能匹配的行，避免在 Join 阶段处理无效数据。

### 分治聚合：RadixPartitionedHashTable

当数据量超过单哈希表容量时，DuckDB 使用**基数分区**将聚合分散到多个独立分区：

```cpp
// src/include/duckdb/common/radix_partitioning.hpp
constexpr idx_t MAX_RADIX_BITS = 12;  // 最多 4096 个分区

// 分区使用哈希值的高位（高于 16 位盐区域）
static constexpr idx_t Shift(radix_bits) {
    return (sizeof(hash_t) - sizeof(uint16_t)) * 8 - radix_bits;
}
```

**自适应策略**：

```cpp
// src/execution/radix_partitioned_hashtable.cpp
// 线程数决定策略：
// 1-2 个线程 → 哈希表增长
// 更多线程 → 分区并放弃

// 行宽阈值：
// row_width >= 64 → 减少 2 位基数（4x 更少分区）→ 减少缓存抖动
// row_width >= 32 → 减少 1 位基数（2x 更少分区）

// 自适应去重：看到 1,048,576 个元组后，用 HyperLogLog 估算唯一值
// 如果 >95% 唯一 → 跳过查找，只追加（推迟去重到合并阶段）
// 如果去重率 >2x → 增大哈希表容量
```

**外部聚合**：当内存不足时，`MaybeRepartition` 增加基数位数将数据溢出到磁盘。每个分区经历状态机：`READY_TO_FINALIZE` → `FINALIZE_IN_PROGRESS` → `READY_TO_SCAN`。

## 31.2 Arena Allocator + Linked List：批量分配的技巧

### ArenaAllocator：O(1) 批量分配与释放

```cpp
// src/include/duckdb/storage/arena_allocator.hpp
struct ArenaChunk {
    AllocatedData data;           // 原始内存块
    idx_t current_position;       // 块内当前偏移
    idx_t maximum_size;           // 块总大小
    unsafe_unique_ptr<ArenaChunk> next;  // 指向更老的块
    ArenaChunk *prev;             // 指向更新的块
};

// 关键常量
ARENA_ALLOCATOR_INITIAL_CAPACITY = 2048  // 初始块大小
ARENA_ALLOCATOR_MAX_CAPACITY = 16MB      // 最大块大小
```

分配是 O(1) 的：如果当前头块有空间，只需移动指针（bump allocation）。如果没有，调用 `AllocateNewBlock`。

**增长策略**：容量每次翻倍，直到 16MB 上限。新块成为链表的新头。prev/next 指针形成双向链表，头总是最近分配的块。

**Reset 的魔力**：`Reset()` 销毁除头块外的所有块，将头的位置重置为 0。这是关键性能技巧——不是逐个释放，而是一次性重置指针。所有从 Arena 分配的内存在 O(1) 内全部释放。

```
普通分配器: malloc/free × N 次 = O(N)
Arena:      Allocate × N 次 + Reset 1 次 = O(1) 总释放
```

**ArenaLinkedList**：单向链表，每个 `Node` 在 Arena 上分配。要求元素类型 `T` 是平凡可析构的（`static_assert`）——因为 Arena 从不单独释放，有非平凡析构函数的类型会泄漏资源。

**arena_stl_allocator**：使 Arena 与 STL 容器兼容。`allocate()` 调用 `arena_allocator.Allocate()`，`deallocate()` 是空操作。这支持 `arena_vector<T>` 和 `arena_unordered_map<T>`。

### 在聚合中的应用

`GroupedAggregateHashTable` 使用 Arena 管理聚合状态内存。`RadixPartitionedHashTable` 在合并阶段维护多个 Arena 分配器——每个合并阶段的 Arena 可以独立 Reset，精确控制内存生命周期。

## 31.3 Radix Partitioned Hash Table：NUMA-Aware 的设计

### 线程钉选

```cpp
// src/parallel/task_scheduler.cpp
// 当 hardware_concurrency() > 64（THREAD_PIN_THRESHOLD）时自动启用
// GetProcessCPUMask() → sched_getaffinity 获取可用 CPU
// SetThreadAffinity() → pthread_setaffinity_np 绑定线程到 CPU
```

线程钉选确保分区的数据留在处理它的 CPU 本地——这是 NUMA 优化的基础。

### 分区到线程的映射

```
每个线程独立处理分配给自己的分区：
1. Finalize：合并局部哈希表
2. Scan：输出结果

分区数量限制：
  min(max_threads_from_scheduler, partitions_that_fit_in_memory)

内存预约决定可以同时处理多少个分区
```

### 倾斜检测

```cpp
// src/execution/operator/join/physical_hash_join.cpp
// KeysAreSkewed(): 最大分区超过总大小的 33% → 强制单线程 Finalize
// very_very_skewed: 80% 阈值 → 完全避免重分区
```

数据倾斜是并行聚合的天敌。DuckDB 的倾斜检测避免了"一个巨型分区拖慢所有线程"的问题。

### Join Hash Table 的盐优化

```cpp
// src/include/duckdb/execution/join_hashtable/ht_entry.hpp
// ht_entry_t: 64 位 = 16 位盐 + 48 位指针

// USE_SALT_THRESHOLD = 8192
// 小表（< 8192 条目）→ 无盐，检查每个占用条目
// 大表（>= 8192 条目）→ 盐预过滤，减少昂贵的行比较
```

盐是一种轻量级布隆过滤器：在哈希表中存储每个条目的 16 位哈希前缀。探测时先比较盐，不匹配则跳过——避免了对不匹配行的昂贵键比较。8192 阈值大约对应 L1 缓存大小——小于此值的表可以全部放入 L1，盐的预过滤没有收益。

## 31.4 解耦 Prefix 的 Join 优化

DuckDB 的"解耦前缀 Join"是指将 Join 构建端的过滤知识下推到探测端表扫描——完全解耦过滤与 Join 执行。

### 多层过滤器层次

```cpp
// src/execution/operator/join/physical_hash_join.cpp
// FinalizeFilters():
// 1. ConstantFilter (min/max) → 始终推送，等值比较时如果 min==max 只需一个
// 2. PerfectHashJoinFilter → 完美哈希 Join 时推送位图
// 3. PrefixRangeFilter → 构建端小（<= 524,288 行）且键跨距小（<= 1,048,576）
// 4. BloomFilter → 大构建端的回退，build/probe ratio <= 1.0
```

### PrefixRangeFilter：前缀范围位图

```cpp
// src/include/duckdb/planner/filter/prefix_range_filter.hpp
// MAX_PREFIX_LENGTH = 20 位 → 最多 ~1M 个桶
// 大跨距时用 shift 降低粒度
// 查找无分支：const uint32_t word_idx = (bit_idx >> WORD_SHIFT) & (0U - in_range)
// 如果超出范围，掩码将 word_idx 清零
// 位图 64 字节对齐（缓存行对齐）
// 字符串：将 4 字节前缀转为整数 → 前缀级字符串过滤
```

### BloomFilter：64 字节扇区设计

```cpp
// src/planner/filter/bloom_filter.cpp
// 每扇区 64 位，每个哈希设置 4 位
// 使用 SHIFT_MASK = 0x3F3F3F3F3F3F3F3F 从哈希提取 8 个 6 位位置
// 插入使用原子 fetch_or（relaxed 内存序）→ 无锁线程安全
// 缓冲区 64 字节对齐 → 每次探测恰好一个缓存行
```

### 过滤器选择逻辑

```
单等值条件 + build/probe <= 1.0 → 可用 BloomFilter
无构建端过滤 + build/probe <= 0.1 + count <= 4,194,304 → 额外条件
```

这些过滤器在扫描阶段就消除不可能匹配的行，减少 Join 阶段处理的数据量——是谓词下推思想在 Join 场景下的延伸。

## 本章小结

DuckDB 的算法选择遵循一个清晰的模式：**先检测数据特征，再选择最优路径**。

- PerfectHashTable：值域小时消除哈希开销
- 分治聚合 + 自适应：大时分区，小时增长，倾斜时回退
- Arena Allocator：O(1) 批量释放，匹配聚合的状态生命周期
- 多层过滤器：从 min/max 到布隆过滤器，逐层提升精度

这种"特征检测 → 路径选择"的模式贯穿 DuckDB——它不是"一种算法打天下"，而是"根据数据走不同的路"。
