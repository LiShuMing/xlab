# Chapter 12: HashJoin 实现

## 12.1 JOIN 算法概览

ClickHouse 支持多种 JOIN 算法，通过 `join_algorithm` 设置选择：

| 算法 | 时间复杂度 | 内存 | 适用场景 |
|------|-----------|------|----------|
| Hash | O(M+N) | O(N) | 默认，右表能放入内存 |
| Parallel Hash | O(M+N)/P | O(N) | 大右表，多线程构建 |
| Grace Hash | O(M+N)×passes | O(N/k) | 超大右表，分片溢出到磁盘 |
| Full Sorting Merge | O(MlogM+NlogN) | O(1) extra | 两表已排序 |
| Direct | O(M) | O(1) | 右表是 Lookup 表引擎 |

## 12.2 IJoin 接口

`src/Interpreters/IJoin.h` — 所有 JOIN 实现的基类：

```cpp
class IJoin
{
public:
    virtual ~IJoin() = default;
    virtual const TableJoin & getTableJoin() const = 0;

    // 构建阶段：向哈希表添加右表数据
    virtual bool addBlockToJoin(const Block & block, bool check_limits) = 0;

    // 探测阶段：用左表数据探测哈希表
    virtual void joinBlock(Block & block, std::shared_ptr<ExtraBlock> & extra_block) = 0;

    // RIGHT/FULL JOIN：输出未匹配的右表行
    virtual Block joinTotals(Block & left_totals, const Block & right_totals) const;

    // 设置右表数据源（流式 JOIN）
    virtual void setSource(std::shared_ptr<ISource> source);
};
```

## 12.3 HashJoin — 核心实现

`src/Interpreters/HashJoin/HashJoin.h:108-150` — 最常用的 JOIN 实现：

```cpp
class HashJoin : public IJoin
{
public:
    // 构建阶段：添加右表数据到哈希表
    bool addBlockToJoin(const Block & source_block, bool check_limits) override;

    // 探测阶段：用左表数据探测哈希表
    void joinBlock(Block & block, std::shared_ptr<ExtraBlock> & extra_block) override;

private:
    std::shared_ptr<TableJoin> table_join;  // JOIN 配置
    SharedHeader right_sample_block;         // 右表列结构

    // JOIN 类型组合:
    // Kind: INNER / LEFT / RIGHT / FULL / CROSS
    // Strictness: ALL / ANY / SEMI / ANTI / ASOF

    bool any_take_last_row;       // ANY JOIN 时是否取最后一行
    size_t reserve_num;           // 预分配哈希表大小
    String instance_id;           // 实例标识（用于 Grace Hash 临时文件）
    bool use_two_level_maps;      // 是否使用两级哈希表
};
```

### 支持的 JOIN 类型

`src/Interpreters/HashJoin/HashJoin.h:31-107` — HashJoin 支持丰富的 JOIN 语义：

```
Kind × Strictness 矩阵:

          ALL       ANY       SEMI      ANTI      ASOF
INNER     ✓         ✓         -         -         ✓
LEFT      ✓         ✓         ✓         ✓         ✓
RIGHT     ✓         ✓         ✓         ✓         -
FULL      ✓         -         -         -         -
CROSS     ✓         -         -         -         -

ALL:     标准语义，匹配行相乘
ANY:     每个 KEY 只取一行（优化：减少输出行数）
SEMI:    只返回左表中 KEY 在右表存在的行
ANTI:    只返回左表中 KEY 在右表不存在的行
ASOF:    非等值 JOIN，找最接近的匹配行
```

## 12.4 哈希表实现

`src/Interpreters/HashJoin/HashJoinMethods.h` — 哈希表的模板化实现：

```cpp
// JOIN Kind × Strictness × Map 模板实例化
template <JoinKind KIND, JoinStrictness STRICTNESS, typename MapsTemplate>
class HashJoinMethods
{
    // 根据键类型选择哈希表:
    // 单列 UInt8  → FixedHashMap<UInt8, ...>
    // 单列 UInt64 → HashMap<UInt64, ...>
    // 多列组合    → HashMapWithSavedHash<StringRef, ...>
    // 大表        → TwoLevelHashMap (分片，减少锁竞争)

    // 插入右表数据
    void insertFromBlock(HashMaps & maps, const Block & block);

    // 探测左表数据
    void joinBlock(HashMaps & maps, Block & block);
};
```

### 哈希表类型

| 哈希表 | 适用键类型 | 特点 |
|--------|-----------|------|
| `FixedHashMap<UInt8>` | 单列 UInt8 | 最高性能，256 槽位直接寻址 |
| `HashMap<UInt64>` | 单列 UInt64 | 标准开放寻址哈希表 |
| `HashMapWithSavedHash<StringRef>` | 多列组合键 | 保存哈希值避免重复计算 |
| `TwoLevelHashMap` | 大表（> 2^16 行） | 按 hash 前缀分片，减少锁竞争 |

### 键序列化

多列组合键需要序列化为连续内存（StringRef），以便作为哈希表键：

```cpp
// src/Interpreters/HashJoin/KeyGetter.h
class KeyGetter
{
    // 将多个列的值序列化为连续字节流
    // 例如: (UInt64, String, UInt32)
    //   → [8 bytes UInt64][4 bytes string length][N bytes string data][4 bytes UInt32]

    // 使用 Arena 分配内存（避免频繁 malloc）
    Arena pool;

    // 哈希函数: 使用 SipHash 或 Hash128
    size_t hash = sipHash64(key_data, key_size);
};
```

## 12.5 NULL 值处理

`HashJoin.h:94-99` — ClickHouse 的 NULL 处理规则：

```
NULL 永远不会 JOIN 到任何值，包括 NULL 本身。

构建阶段: 跳过 KEY 中包含 NULL 的行
探测阶段: KEY 中包含 NULL 的行视为未匹配
  → INNER JOIN: 过滤掉
  → LEFT JOIN: 右表补 NULL（或默认值）
  → RIGHT JOIN: 在二次扫描中输出
  → FULL JOIN: 两侧都补 NULL

设置:
  join_use_nulls = 1 → 未匹配行总是补 NULL（SQL 标准语义）
  join_use_nulls = 0 → 未匹配行补数据类型默认值（ClickHouse 原始语义）
```

## 12.6 Parallel Hash Join

多线程构建哈希表：

```
右表数据
  │
  ├── 按 JOIN KEY 哈希分片（ScatteredBlock）
  │     ├── Shard 0 → Thread 0 构建哈希表
  │     ├── Shard 1 → Thread 1 构建哈希表
  │     └── Shard K → Thread K 构建哈希表
  │
  └── 探测时按相同哈希分片，在对应分片中查找

ScatteredBlock (src/Interpreters/HashJoin/ScatteredBlock.h):
  一个 Block 按 sharding_key 分片为多个子 Block
  每个子 Block 包含原 Block 中属于该分片的行
```

### ConcurrentHashJoin

`src/Interpreters/ConcurrentHashJoin.h` — 并发 JOIN 包装器：

```cpp
class ConcurrentHashJoin : public IJoin
{
    // 内部维护多个 HashJoin 实例（每个分片一个）
    std::vector<std::unique_ptr<HashJoin>> joins;

    // 构建阶段：并行调用各分片的 addBlockToJoin
    bool addBlockToJoin(const Block & block, bool check_limits) override;

    // 探测阶段：并行调用各分片的 joinBlock
    void joinBlock(Block & block, std::shared_ptr<ExtraBlock> & extra_block) override;
};
```

## 12.7 Grace Hash Join

`src/Interpreters/GraceHashJoin.h` — 当右表超过内存限制时，使用 Grace Hash Join：

```
构建阶段:
  1. 右表数据按 JOIN KEY 分片
     → 使用 hash(key) % num_buckets
  2. 内存中的分片直接构建哈希表
  3. 溢出的分片写入磁盘临时文件
     → TemporaryDataOnDisk 管理

探测阶段:
  1. 左表数据按相同方式分片
  2. 内存中的分片正常探测
  3. 溢出的分片写入磁盘临时文件

后续 Pass:
  1. 从磁盘读取溢出分片
  2. 重复构建/探测
  3. 直到所有分片处理完毕

分片数自适应:
  初始: grace_hash_join_initial_buckets (默认 1)
  溢出时: buckets × 2（倍增策略）
  上限: grace_hash_join_max_buckets (默认 1024)
```

### TemporaryDataOnDisk — 磁盘临时数据

```cpp
// 管理溢出到磁盘的数据
class TemporaryDataOnDisk
{
    // 为每个分片创建临时文件
    // 使用压缩写入（减少磁盘 I/O）
    // 支持异步 I/O（提升吞吐）
};
```

## 12.8 Full Sorting Merge Join

`src/Interpreters/FullSortingMergeJoin.h` — 两表已排序时的归并 JOIN：

```
适用条件:
  1. 两表按 JOIN KEY 排序
  2. 或 ClickHouse 可以在 JOIN 前排序

算法:
  1. 双指针归并：
     left_ptr 指向左表当前行
     right_ptr 指向右表当前行
  2. 比较 JOIN KEY:
     left_key < right_key → left_ptr++
     left_key > right_key → right_ptr++
     left_key == right_key → 输出匹配行
  3. 适合已排序的大表 JOIN（不需要哈希表）

设置:
  join_algorithm = 'full_sorting_merge'
```

## 12.9 Direct Join

`src/Interpreters/DirectJoin.h` — 右表是 Lookup 表引擎时的直接查找：

```
适用条件:
  右表是 Join / Dictionary 引擎

算法:
  1. 左表每行直接查找右表
  2. 无需构建哈希表
  3. 类似于字典查找

设置:
  join_algorithm = 'direct'
```

## 12.10 JoinUsedFlags — RIGHT/FULL JOIN 追踪

`src/Interpreters/HashJoin/JoinUsedFlags.h` — 追踪右表哪些行被匹配：

```cpp
class JoinUsedFlags
{
    // 为每个哈希桶维护一个 bit flag 数组
    // 标记右表的每一行是否被左表匹配

    // 在探测阶段，每匹配一行右表数据，标记对应的 flag
    void markUsed(size_t row);

    // 在二次扫描中，输出未被标记的右表行
    // → 实现 RIGHT JOIN 和 FULL JOIN
};
```

## 12.11 JoinStepLogical → JoinStep 转换

`src/Processors/QueryPlan/JoinStepLogical.h` → `JoinStep.h` — 逻辑 JOIN 到物理 JOIN 的选择：

```cpp
std::shared_ptr<JoinStep> JoinStepLogical::makeJoinStep(
    const Context & context,
    const Block & left_header,
    const Block & right_header) const
{
    // 根据 join_algorithm 设置选择:
    // 'hash'           → HashJoin
    // 'parallel_hash'  → ConcurrentHashJoin
    // 'grace_hash'     → GraceHashJoin
    // 'full_sorting_merge' → FullSortingMergeJoin
    // 'direct'         → DirectJoin
    // 'auto'           → 根据右表大小和类型自动选择
}
```

### 自动选择逻辑

```
auto 模式:
  1. 右表是 Join/Dictionary 引擎 → Direct
  2. 右表能放入内存 → Hash
  3. 右表较大 → Parallel Hash
  4. 右表超过内存限制 → Grace Hash
  5. 两表已排序 → Full Sorting Merge
```

## 12.12 Build Side 选择

`query_plan_join_swap_table` 设置决定哪一侧作为 Build 表：

- `auto`（默认）：Planner 根据统计信息选择较小的一侧作为 Build 表
- `true`：强制左表作为 Build 表
- `false`：强制右表作为 Build 表

**选择依据**：Build 表越小，哈希表越小，内存占用越低。`use_hash_table_stats_for_join_reordering = true` 时，ClickHouse 收集哈希表统计来辅助决策。

## 12.13 本章小结

```
JOIN 实现矩阵:
  ├── Hash Join        → 默认，O(M+N)，内存 O(N)
  │     ├── 单列键: FixedHashMap / HashMap
  │     ├── 多列键: HashMapWithSavedHash
  │     └── 大表: TwoLevelHashMap
  │
  ├── Parallel Hash    → 多线程构建分片哈希表 (ConcurrentHashJoin)
  ├── Grace Hash       → 溢出到磁盘，分片倍增 (TemporaryDataOnDisk)
  ├── Full Sorting Merge → 双指针归并（两表已排序）
  └── Direct           → Lookup 表直接查找

JOIN 语义:
  Kind × Strictness: ALL / ANY / SEMI / ANTI / ASOF
  NULL 处理: 永不 JOIN，外连接补 NULL
  RIGHT/FULL: JoinUsedFlags 追踪匹配状态
```

**关键文件地图**：
```
src/Interpreters/IJoin.h                          → JOIN 接口
src/Interpreters/HashJoin/HashJoin.h              → Hash Join 主类
src/Interpreters/HashJoin/HashJoinMethods.h       → 哈希表方法模板
src/Interpreters/HashJoin/HashJoinMethodsImpl.h   → 哈希表方法实现
src/Interpreters/HashJoin/KeyGetter.h             → 键序列化
src/Interpreters/HashJoin/ScatteredBlock.h        → 分片 Block
src/Interpreters/HashJoin/JoinUsedFlags.h         → 匹配状态追踪
src/Interpreters/ConcurrentHashJoin.h             → 并发 Hash Join
src/Interpreters/GraceHashJoin.h                  → Grace Hash Join
src/Interpreters/FullSortingMergeJoin.h           → 排序归并 Join
src/Interpreters/DirectJoin.h                     → 直接查找 Join
src/Processors/QueryPlan/JoinStepLogical.h        → 逻辑 JOIN Step
src/Processors/QueryPlan/JoinStep.h               → 物理 JOIN Step
```
