# Chapter 7: MergeTree 写入路径 — Insert → Parts → Merge/Mutation

## 7.1 写入概览

```
INSERT INTO t VALUES (...)
  │
  ├── 1. 解析 INSERT 语句
  │     ParserInsertQuery → ASTInsertQuery
  │
  ├── 2. 创建 Sink（写入目标）
  │     InterpreterInsertQuery → SinkToStorage
  │
  ├── 3. 数据写入
  │     ├── 同步写入：直接创建新 Part
  │     └── 异步写入：写入 Buffer → 后台刷盘
  │
  ├── 4. Part 注册
  │     新 Part 加入 DataPartsSet
  │
  └── 5. 后台 Merge
        MergeList → MergeTask → 合并小 Part 为大 Part
```

## 7.2 INSERT 执行路径

### InterpreterInsertQuery

`src/Interpreters/InterpreterInsertQuery.cpp` — INSERT 的入口：

```cpp
BlockIO InterpreterInsertQuery::execute()
{
    // 1. 获取目标表
    auto table = getTable(query);

    // 2. 获取存储引擎的 Sink
    auto sink = table->write(query, metadata, context);

    // 3. 构建 QueryPipeline：Source（输入数据）→ Sink（写入表）
    pipeline = std::make_shared<QueryPipeline>();
    pipeline->init(pulling_pipeline);
    pipeline->addPushingSink(sink);
}
```

### MergeTreeSink — 写入 Part

`src/Storages/MergeTree/MergeTreeSink.h` — MergeTree 的写入目标：

```cpp
class MergeTreeSink : public SinkToStorage
{
    void consume(Chunk chunk) override
    {
        // 1. 排序（如果表有 ORDER BY）
        // 2. 按 index_granularity 切分为 Granule
        // 3. 为每个 Granule 写入 Mark
        // 4. 写入列数据（压缩）
        // 5. 写入主键索引
        // 6. 写入校验和
        // 7. 提交 Part
    }

    void onFinish() override
    {
        // 1. 最终化 Part
        // 2. 将新 Part 注册到 DataPartsSet
        // 3. 通知后台 Merge 调度器
    }
};
```

### Part 写入流程详解

一个 INSERT 批次生成一个 Data Part，写入过程分为以下步骤：

**Step 1: 排序**

```cpp
// 如果表有 ORDER BY，数据需要排序
// 使用 IColumn::permute() 方法按排序键重排列数据
// 排序在内存中完成，使用 Radix Sort 或LSD Sort
```

**Step 2: 计算 Granule 边界**

```cpp
// 按 index_granularity 切分数据为 Granule
// 每个 Granule = 8192 行（或 index_granularity_bytes 达到上限）
// 记录每个 Granule 的行数到 IndexGranularity
```

**Step 3: 写入列数据**

```cpp
// 对每一列：
//   1. 创建压缩写入器（CompressedWriteBuffer）
//   2. 按 Granule 写入列数据
//   3. 每个 Granule 开始时记录 Mark（offset_in_compressed_file, offset_in_decompressed_block）
//   4. 使用配置的 Codec 链进行压缩
```

**Step 4: 写入主键索引**

```cpp
// 取每个 Granule 第一行的主键列值
// 序列化为 primary.cidx 文件
```

**Step 5: 写入跳数索引**

```cpp
// 对每个定义的 Skip Index：
//   按索引粒度聚合数据
//   计算索引值（min/max、set、bloom filter 等）
//   写入 .idx 文件
```

**Step 6: 写入元数据和校验和**

```cpp
// 写入 columns.txt（列定义）
// 写入 count.txt（行数）
// 计算所有文件的 SIP hash 128
// 写入 checksums.txt
```

### Part 写入格式

一个 INSERT 批次生成一个 Data Part：

```
all_{block_number}_{block_number}_0/
  ├── columns.txt          ← 列定义
  ├── count.txt            ← 行数
  ├── checksums.txt        ← 校验和
  ├── primary.cidx         ← 主键索引
  ├── date.bin / date.mrk  ← date 列数据和 Mark
  ├── user_id.bin / user_id.mrk
  ├── event_name.bin / event_name.mrk
  ├── minmax_date.idx      ← minmax 跳数索引
  └── ...
```

## 7.3 Wide Part vs Compact Part 写入

### Wide Part 写入

`src/Storages/MergeTree/MergeTreeDataPartWriterWide.h` — 默认的大 Part 写入方式：

```
每列独立文件:
  col_a.bin  ← 仅包含 col_a 的压缩数据
  col_a.mrk  ← 仅包含 col_a 的 Mark 偏移量
  col_b.bin
  col_b.mrk
  ...

优点:
  - 读取时只需打开所需列的文件（列裁剪）
  - 单列数据连续存储，压缩率高
  - 并行写入各列

缺点:
  - 文件数量多（2 × 列数 + 元数据文件）
  - 小 Part 场景下文件系统元数据开销大
```

### Compact Part 写入

`src/Storages/MergeTree/MergeTreeDataPartWriterCompact.h` — 小 Part 的紧凑写入方式：

```
所有列打包到一个文件:
  data.bin   ← 所有列的压缩数据，按 Granule 交织存储
  data.mrk   ← 所有列的 Mark，按 Granule 交织存储

数据布局（Granule 交织）:
  [Granule 0: col_a data | col_b data | col_c data]
  [Granule 1: col_a data | col_b data | col_c data]
  ...

优点:
  - 文件数量极少（2 个数据文件）
  - 写入时顺序 I/O（一个文件顺序写）
  - 减少文件系统元数据开销

缺点:
  - 读取单列时需要跳过其他列数据
  - 压缩率略低（不同列数据混合，压缩字典效果差）
```

**自动选择阈值**：

```sql
-- 设置控制
min_bytes_for_compact_part = 10MB    ← Part 小于此值用 Compact
min_rows_for_compact_part = 100K     ← Part 小于此值用 Compact
```

### InMemory Part

不写入磁盘，只存在于内存中。用于 Buffer 引擎和异步 INSERT 的中间状态。当 InMemory Part 被刷盘时，转换为 Compact 或 Wide Part。

## 7.4 异步 INSERT

`src/Interpreters/AsynchronousInsertQueue.h` — ClickHouse 支持异步 INSERT，将多个小 INSERT 批量合并：

```cpp
class AsynchronousInsertQueue
{
    // 异步 INSERT 流程：
    // 1. 客户端发送 INSERT
    // 2. 数据进入 AsynchronousInsertQueue（内存中）
    // 3. 等待 timeout 或队列满
    // 4. 批量写入一个大的 Part
    // 5. 返回客户端确认
};
```

**好处**：减少小 Part 数量，降低后续 Merge 压力。

**设置**：
- `async_insert = 1` — 启用异步 INSERT
- `async_insert_max_data_size` — 批量大小上限
- `async_insert_busy_timeout_ms` — 等待超时
- `async_insert_stale_timeout_ms` — 数据过期时间

### 异步 INSERT 的写入模式

```
模式 1: wait_for_async_insert = 1 (默认)
  Client → INSERT → Queue → 等待后台线程处理 → 返回确认
  客户端确认数据已持久化

模式 2: wait_for_async_insert = 0
  Client → INSERT → Queue → 立即返回
  客户端不等待，可能丢失数据

异步 INSERT 对比同步 INSERT:
  同步: INSERT 1行 → Part 1 (8KB)   × 1000次 = 1000个小 Part
  异步: INSERT 1行 × 1000次 → 合并 → 1个 Part (8MB)
  → 后台 Merge 压力降低 1000×
```

## 7.5 分区（Partition）处理

### Partition Key

```sql
CREATE TABLE t (
    date Date,
    user_id UInt64,
    ...
) ENGINE = MergeTree
PARTITION BY toYYYYMM(date)
ORDER BY (date, user_id);
```

**分区的作用**：
1. **数据管理**：`DROP PARTITION` 可以快速删除整个分区的数据
2. **分区裁剪**：查询时跳过不相关分区
3. **Merge 独立性**：不同分区的 Part 不会合并

### PartitionPruner — 分区裁剪

`src/Storages/MergeTree/PartitionPruner.h` — 查询时根据 WHERE 条件裁剪不相关分区：

```cpp
class PartitionPruner
{
    // 对每个 Part，检查其分区值是否可能满足 WHERE 条件
    // 如果不可能 → 跳过该 Part（不读取）
    bool canBePruned(const IMergeTreeDataPart & part) const;
};
```

### 分区目录结构

```
data/
  ├── 202401_1_1_0/     ← 分区 202401 的 Part
  ├── 202401_2_2_0/
  ├── 202402_1_1_0/     ← 分区 202402 的 Part
  └── 202403_1_1_0/     ← 分区 202403 的 Part

Part 完整名称: {partition}_{min_block}_{max_block}_{level}
```

## 7.6 Merge — 后台合并

`src/Storages/MergeTree/MergeList.h` + `MergeTask.cpp` — Merge 是 MergeTree 名字的由来：

### 为什么需要 Merge？

INSERT 会不断产生新的小 Parts。如果不合并：
1. Part 数量膨胀 → 打开文件描述符耗尽
2. 查询时需要读取更多 Parts → 性能下降
3. 主键索引碎片化 → 裁剪效率降低

### Merge 策略

```cpp
// src/Storages/MergeTree/MergeSelectorAlgorithm.h
enum class MergeSelectorAlgorithm
{
    Simple,          // 简单选择器（默认）
    STCS,            // Space-Time Compression Saving
};
```

**Simple 选择器**：从最老的 Part 开始，贪婪地选择可以合并的相邻 Part。

**STCS 选择器**：考虑空间-时间压缩比，优先合并压缩收益最大的 Part 组合。

### Merge 选择过程

```
当前 Parts (按时间排序):
  Part 1 (10MB, level=0)
  Part 2 (8MB,  level=0)
  Part 3 (12MB, level=0)
  Part 4 (5MB,  level=0)
  Part 5 (9MB,  level=0)

Simple 选择器:
  1. 寻找相邻的小 Part 组
  2. 选择 Part 2+3+4 (8+12+5 = 25MB) → 合并为一个 Part
  3. 新 Part 命名为 all_2_4_1

STCS 选择器:
  1. 计算每组合并的压缩收益 (写入量 / 合并后大小)
  2. 选择收益最大的组合
  3. 考虑写放大（避免反复合并大 Part）
```

### MergeTask 执行

```cpp
// src/Storages/MergeTree/MergeTask.cpp
class MergeTask
{
    // Merge 过程：
    // 1. 读取源 Parts
    // 2. 按主键排序合并（归并排序）
    // 3. 写入新 Part
    // 4. 原子替换：新 Part 替换旧 Parts
    //    - 创建硬链接（同一磁盘上）
    //    - 或复制数据（跨磁盘）
    // 5. 删除旧 Parts
};
```

### Merge 类型

| 类型 | 触发条件 | 作用 |
|------|----------|------|
| 普通合并 | Part 数量超过阈值 | 合并小 Parts |
| TTL 合并 | 数据过期 | 删除过期数据/移动到冷存储 |
| 聚合合并 | SummingMergeTree | 预聚合相同主键行 |
| 去重合并 | ReplacingMergeTree | 去除重复主键行 |
| 变更合并 | ALTER TABLE | 应用列变更 |

### MergeTreeBackgroundExecutor — 后台任务调度

`src/Storages/MergeTree/MergeTreeBackgroundExecutor.h` — 统一的后台任务调度器：

```cpp
class MergeTreeBackgroundExecutor
{
    // 管理 Merge / Mutation / TTL 等后台任务
    // 限制并发执行数
    // 优先级调度：Mutation > Merge > TTL

    void scheduleTask(BackgroundTaskPtr task);
    void removeTask(BackgroundTaskPtr task);

    // 相关设置:
    // background_pool_size         → 并发 Merge 任务数（默认 16）
    // background_merges_mutations_concurrency_ratio → Merge/Mutation 并发比
};
```

**后台任务优先级**：

```
1. Mutation (ALTER TABLE) — 用户显式请求，优先级最高
2. Merge (普通合并) — 保持 Part 数量健康
3. TTL Merge — 数据生命周期管理
4. Part Cleanup — 清理过期 Part 文件
```

## 7.7 TTL — 数据生命周期

TTL（Time To Live）控制数据的自动过期和移动：

```sql
CREATE TABLE t (
    date Date,
    data String,
    ...
) ENGINE = MergeTree
ORDER BY date
TTL date + INTERVAL 30 DAY                    -- 30天后删除
-- 或
TTL date + INTERVAL 7 DAY TO DISK 'cold'      -- 7天后移动到冷存储
-- 或
TTL date + INTERVAL 14 DAY TO VOLUME 'archive' -- 14天后移动到归档卷
;
```

### TTL 执行机制

```
TTL 合并在后台 Merge 中执行:
  1. 检查每个 Part 的 TTL 条件
  2. 如果整个 Part 过期 → 直接删除
  3. 如果 Part 中部分行过期 → 重写 Part（删除过期行）
  4. 如果需要移动到冷存储 → 复制 Part 到目标磁盘

设置:
  merge_with_ttl_timeout = 14400  ← TTL 合并间隔（秒，默认4小时）
  ttl_only_drop_parts = 1         ← 整个 Part 过期时直接删除，不重写
```

## 7.8 Mutation — ALTER TABLE 的执行

`src/Storages/MergeTree/MutateTask.cpp` — Mutation 是 Merge 的变体，用于 ALTER TABLE：

```sql
ALTER TABLE t UPDATE col = expr WHERE condition;  -- Lightweight DELETE/UPDATE
ALTER TABLE t DELETE WHERE condition;              -- DELETE
ALTER TABLE t MODIFY COLUMN col Type;              -- 列类型变更
```

Mutation 流程：
1. 记录 Mutation 命令到 `mutations.txt`
2. 后台 Mutation 线程读取每个 Part
3. 对满足 WHERE 条件的行应用变更
4. 生成新 Part 替换旧 Part

**注意**：Mutation 是重量级操作——它需要重写整个 Part，而非只修改匹配行。

### Lightweight Delete（轻量删除）

ClickHouse 24.x 引入了轻量删除，使用行级 mask 而非重写 Part：

```sql
ALTER TABLE t DELETE WHERE condition;  -- 旧方式：重写 Part
DELETE FROM t WHERE condition;         -- 新方式：写入 _row_exists mask
```

新方式只写入一个 `_row_exists` 列（bool mask），查询时自动过滤。真正的物理删除在后续 Merge 中完成。

**_row_exists 列的工作机制**：

```
原始数据:
  Part A: [row0, row1, row2, row3, row4]

DELETE FROM t WHERE user_id = 42;
  → 创建 _row_exists 列: [1, 0, 1, 1, 0]  (0 = deleted)
  → 实际写一个小的 "delete mask" Part

查询时:
  SELECT * FROM t → 读取 Part A + delete mask
  → 过滤 _row_exists = 0 的行
  → 只返回 row0, row2, row3

后续 Merge:
  Part A + delete mask → 合并为新 Part（物理删除已标记行）
```

**轻量删除的优势**：
- 执行速度极快（只写 mask，不重写 Part）
- 不增加 Part 数量（mask 以特殊方式附加）
- 与 SELECT 查询自然兼容

## 7.9 原子性保证

### Part 提交原子性

```
写入过程:
  1. 创建临时目录: tmp_merge_all_1_3_2/
  2. 写入所有文件到临时目录
  3. fsync 所有文件（确保数据落盘）
  4. 原子 rename: tmp_merge_all_1_3_2/ → all_1_3_2/
  5. 在 DataPartsSet 中注册新 Part
  6. 标记旧 Parts 为 Outdated

崩溃恢复:
  - 如果在 step 4 之前崩溃: 临时目录残留，启动时清理
  - 如果在 step 4 之后崩溃: 新 Part 已存在，旧 Part 标记为 Outdated
  - rename 在大多数文件系统上是原子操作
```

### INSERT 幂等性

ReplicatedMergeTree 通过 ZooKeeper 中的 `/blocks/` 节点保证 INSERT 幂等性。普通 MergeTree 没有幂等保证——重复 INSERT 会产生重复数据。

## 7.10 本章小结

```
INSERT 数据流:
  Client → InterpreterInsertQuery → MergeTreeSink → 新 Data Part
                                                        │
                                                        ├── 同步: 直接写盘
                                                        │     ├── Wide Part (大 Part)
                                                        │     └── Compact Part (小 Part)
                                                        └── 异步: AsynchronousInsertQueue → 批量写盘

Part 写入步骤:
  排序 → 切分 Granule → 写入列数据 → 写入 Mark → 写入主键索引
  → 写入跳数索引 → 写入元数据 → 写入校验和 → 原子提交

后台任务:
  Merge (合并小 Part) → MergeTask → 归并排序 → 新 Part 替换旧 Parts
  Mutation (ALTER) → MutateTask → 重写 Part → 新 Part 替换旧 Parts
  TTL → 合并时清理过期数据 / 移动到冷存储
  Lightweight Delete → 写入 _row_exists mask → 后台 Merge 物理删除
```

**关键文件地图**：
```
src/Interpreters/InterpreterInsertQuery.cpp     → INSERT 入口
src/Storages/MergeTree/MergeTreeSink.h          → 写入 Sink
src/Storages/MergeTree/MergeTreeDataPartWriterWide.h    → Wide Part 写入
src/Storages/MergeTree/MergeTreeDataPartWriterCompact.h → Compact Part 写入
src/Interpreters/AsynchronousInsertQueue.h      → 异步 INSERT
src/Storages/MergeTree/MergeTask.cpp            → Merge 任务
src/Storages/MergeTree/MutateTask.cpp           → Mutation 任务
src/Storages/MergeTree/MergeList.h              → Merge 列表管理
src/Storages/MergeTree/MergeTreeBackgroundExecutor.h → 后台任务调度
src/Storages/MergeTree/PartitionPruner.h        → 分区裁剪
```
