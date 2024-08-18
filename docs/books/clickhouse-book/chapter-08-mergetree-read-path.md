# Chapter 8: MergeTree 读取路径 — Mark Ranges → Read Pool → 向量化读取

## 8.1 读取概览

```
SELECT * FROM t WHERE date = '2024-01-01' AND user_id = 300
  │
  ├── 1. 解析 WHERE 条件 → KeyCondition
  │
  ├── 2. 主键索引裁剪 → MarkRanges（跳过不满足条件的 Granule）
  │
  ├── 3. Skip Index 裁剪 → 进一步缩小 MarkRanges
  │
  ├── 4. 分区裁剪 → 跳过不满足条件的 Partition
  │
  ├── 5. 构建 ReadPool（并行读取任务分配）
  │
  ├── 6. 多线程并行读取
  │     ├── Thread 1: Part 1, Mark 0-5
  │     ├── Thread 2: Part 1, Mark 6-10
  │     └── Thread 3: Part 2, Mark 0-8
  │
  └── 7. 解压 + 反序列化 → Block
```

## 8.2 KeyCondition 与索引裁剪

`src/Storages/MergeTree/KeyCondition.h` — KeyCondition 是 WHERE 条件对主键索引的可评估表示：

```cpp
class KeyCondition
{
    // 评估 Mark Range 是否可能包含满足条件的数据
    // 返回 true = 可能包含（需要读取）
    // 返回 false = 一定不包含（可以跳过）
    BoolMask mayBeTrueOnGranule(size_t granule_idx) const;
    BoolMask mayBeTrueOnGranulesInRange(const MarkRange & range) const;
};
```

**裁剪过程**：

```
Part: 100 个 Granule
Primary Key: (date, user_id)

WHERE date = '2024-01-01'
  → 使用主键索引第一列裁剪
  → 假设 30% Granule 满足 → 读取 30 个 Granule

WHERE date = '2024-01-01' AND user_id = 300
  → 使用主键索引两列裁剪
  → 假设 5% Granule 满足 → 读取 5 个 Granule
```

### KeyCondition 的构建

KeyCondition 从 WHERE 子句的 `ActionsDAG` 构建：

```
WHERE date = '2024-01-01' AND user_id = 300
  │
  ├── 解析 AND → 两个条件
  ├── date = '2024-01-01' → 主键第 1 列等值 → 可索引
  └── user_id = 300       → 主键第 2 列等值 → 可索引

WHERE date = '2024-01-01' AND event_type = 'click'
  │
  ├── date = '2024-01-01' → 主键第 1 列等值 → 可索引
  └── event_type = 'click' → 非主键列 → 不可索引（交给 Skip Index 或运行时过滤）
```

**不支持的条件类型**（索引无法裁剪）：
- `LIKE '%pattern%'` — 后缀通配符
- `NOT IN` — 否定条件
- 两个不同列的函数比较：`col1 + 1 > col2`

## 8.3 ReadFromMergeTree — 读取入口

`src/Processors/QueryPlan/ReadFromMergeTree.h` — QueryPlan 中的读取 Step：

```cpp
class ReadFromMergeTree : public ISourceStep
{
    // 关键决策：
    // 1. 使用多少个线程读取？
    //    → min(max_threads, parts * marks_per_thread)
    // 2. 读取模式？
    //    → Default / InOrder / InReverseOrder
    // 3. 是否使用 MergeTreeReadPool？
    //    → 多线程时使用，动态分配 Mark Range
};
```

### 读取模式

| 模式 | 说明 | 适用场景 |
|------|------|----------|
| `Default` | 多线程并行读取，结果无序 | 大多数查询 |
| `InOrder` | 按主键顺序读取 | ORDER BY 与主键一致 |
| `InReverseOrder` | 按主键逆序读取 | ORDER BY ... DESC 与主键一致 |

当 ORDER BY 与主键一致时，ClickHouse 自动选择 `InOrder` 模式——这样不需要额外的排序步骤。

### ReadFromMergeTree 的优化决策

```
输入: QueryPlan 上下文 + 表元数据

Step 1: 确定读取的 Parts
  ├── 分区裁剪: 跳过不相关分区
  ├── 主键索引裁剪: KeyCondition → MarkRanges
  └── Skip Index 裁剪: 进一步缩小 MarkRanges

Step 2: 确定读取线程数
  ├── 输入: max_threads, num_parts, num_marks
  ├── 每个线程至少需要 min_marks_for_concurrent_read 个 Mark
  └── threads = min(max_threads, total_marks / min_marks_per_thread)

Step 3: 选择读取模式
  ├── ORDER BY pk AND ASC → InOrder
  ├── ORDER BY pk AND DESC → InReverseOrder
  └── 否则 → Default

Step 4: 选择 ReadPool 类型
  ├── 单线程 → 无 Pool（直接顺序读取）
  ├── 多线程 Default → MergeTreeReadPool
  ├── 多线程 InOrder → MergeTreeReadPoolInOrder
  └── Parallel Replicas → MergeTreeReadPoolParallelReplicas
```

## 8.4 MergeTreeReadPool — 动态任务分配

`src/Storages/MergeTree/IMergeTreeReadPool.h` — 读取线程池的核心：

```cpp
class IMergeTreeReadPool
{
    // 获取下一个读取任务
    virtual MergeTreeReadTaskPtr getTask() = 0;

    // 报告任务完成（用于动态调整分配策略）
    virtual void profileFeedback(const ReadProgressInfo & info) = 0;
};
```

**动态分配策略**：

```
初始分配:
  Thread 1: Part A, Mark 0-5
  Thread 2: Part A, Mark 6-10
  Thread 3: Part B, Mark 0-4

Thread 2 先完成 → 从 Thread 1 偷取:
  Thread 2: Part A, Mark 5-7  ← 从 Thread 1 的范围中分割

这保证了慢线程不会成为瓶颈。
```

### MergeTreeReadPool — 默认读取池

`src/Storages/MergeTree/MergeTreeReadPool.h` — 最常用的读取池实现：

```cpp
class MergeTreeReadPool : public IMergeTreeReadPool
{
    // 将所有 Part 的 MarkRanges 放入一个全局队列
    // 每个线程从队列中获取一批 Mark Range
    // 线程完成后继续获取，直到队列为空

    // 优化:
    // - 尽量让同一线程连续读取同一个 Part（减少 seek）
    // - 每次获取 min_marks_per_request 个 Mark（批量获取减少竞争）
    // - 根据 profileFeedback 调整每个线程的获取量
};
```

### MergeTreeReadPoolInOrder — 有序读取池

`src/Storages/MergeTree/MergeTreeReadPoolInOrder.h` — 保证读取结果按主键有序：

```
保证按主键顺序输出:
  Thread 1: Part A, Mark 0-2 (主键最小)
  Thread 2: Part A, Mark 3-5
  Thread 3: Part B, Mark 0-2

按序输出:
  先输出 Thread 1 的结果（主键最小）
  再输出 Thread 2
  最后输出 Thread 3

实现:
  使用 MergeSorter 在多线程输出间做归并排序
  每个线程的输出本身已经有序（同一个 Part 的 Mark Range 按序读取）
```

### MergeTreeReadPoolParallelReplicas

`src/Storages/MergeTree/MergeTreeReadPoolParallelReplicas.h` — 多副本并行读取的 Pool：

```cpp
class MergeTreeReadPoolParallelReplicas : public IMergeTreeReadPool
{
    // 与 ParallelReplicasReadingCoordinator 协作
    // Coordinator 持有全局 Mark Range 视图
    // 每个 Replica 的 Pool 从 Coordinator 请求任务
    // Coordinator 动态调整分配，实现负载均衡
};
```

## 8.5 MergeTreeSelectProcessor — 单线程读取

`src/Storages/MergeTree/MergeTreeSelectProcessor.h` — 每个 Part 的读取处理器：

```cpp
class MergeTreeSelectProcessor
{
    // 核心读取循环
    Chunk read() override
    {
        while (auto task = reader.getTask())
        {
            // 1. 读取 Mark Range 对应的数据
            auto block = reader.read(task->mark_range);

            // 2. 应用 PREWHERE（如果存在）
            if (prewhere_actions)
                block = prewhere_actions->execute(block);

            // 3. 检查是否需要继续读取
            if (block.rows() > 0)
                return block;
        }
        return {}; // 读取完成
    }
};
```

### MergeTreeReadTask — 读取任务

```cpp
struct MergeTreeReadTask
{
    IMergeTreeDataPartPtr data_part;  // 要读取的 Part
    MarkRange mark_range;              // Mark 范围
    size_t current_mark = 0;           // 当前读取位置
    size_t remaining_marks;            // 剩余 Mark 数

    // 列裁剪信息
    NameSet column_name_set;           // 只读取这些列
};
```

## 8.6 PREWHERE 优化

PREWHERE 是 ClickHouse 独有的优化——在读取所有列之前先读取过滤列：

```sql
SELECT col1, col2 FROM t PREWHERE col3 = 1 WHERE col4 > 0
```

执行顺序：
1. 只读取 `col3` 的数据 → 应用 `col3 = 1` 过滤
2. 对通过过滤的 Granule，再读取 `col1, col2, col4` → 应用 `col4 > 0`

**好处**：如果 `col3 = 1` 过滤掉 90% 的行，那么 90% 的 `col1, col2, col4` 数据不需要读取。

### 自动 PREWHERE

ClickHouse 可以自动将 WHERE 条件中高选择率的列提升为 PREWHERE（`optimize_move_to_prewhere` 设置）：

```
原始查询:
  SELECT * FROM t WHERE status = 'active' AND large_column > 0

自动优化:
  PREWHERE status = 'active'          ← 先读 status 列（小列，高选择率）
  WHERE large_column > 0              ← 再读 large_column（大列，低选择率）

选择标准:
  1. 列的数据大小（小列优先做 PREWHERE）
  2. 过滤选择率（高选择率优先）
  3. 是否是主键列（主键列天然高效，不需要 PREWHERE）
```

### PREWHERE 的实现

```cpp
// MergeTreeSelectProcessor 中的 PREWHERE 执行
Chunk read()
{
    // Phase 1: 只读取 PREWHERE 列
    auto pre_cols = getPrewhereColumns();
    auto block = reader.readColumns(pre_cols, mark_range);

    // 应用 PREWHERE 过滤
    auto filter = prewhere_actions->execute(block);
    auto filter_column = block.getByName(filter.result_name).column;

    // 计算 filter mask
    Filter bitmask(block.rows(), 0);
    for (size_t i = 0; i < block.rows(); ++i)
        bitmask[i] = filter_column->getBool(i);

    // Phase 2: 只读取通过 PREWHERE 的行所需的其他列
    auto remaining_cols = getRemainingColumns();
    auto full_block = reader.readColumns(remaining_cols, mark_range, bitmask);

    // 应用 WHERE 过滤
    if (where_actions)
        full_block = where_actions->execute(full_block);

    return full_block;
}
```

## 8.7 列读取与解压

`src/Storages/MergeTree/IMergeTreeReader.h` — 列数据读取器：

```cpp
class IMergeTreeReader
{
    // 读取一个 Mark Range 的数据
    virtual void readRange(
        size_t from_mark,       // 起始 Mark
        size_t to_mark,         // 结束 Mark
        const Names & columns,  // 要读取的列
        MutableColumns & result) = 0;
};
```

### Wide Part 读取

`src/Storages/MergeTree/MergeTreeReaderWide.h` — 每列独立文件，读取特定列时只需打开对应的 `.bin` 和 `.mrk` 文件：

```
读取 user_id 列 (Mark 3-7):
  1. 打开 user_id.mrk → 读取 mark[3] 和 mark[7]
     → offset_in_compressed = {0x3C4D, 0x7A8B}
  2. 打开 user_id.bin → seek(0x3C4D)
  3. 读取压缩数据 (0x7A8B - 0x3C4D 字节)
  4. 解压 → 填充 result 列
  5. 跳过 offset_in_decompressed 之前的行
```

### Compact Part 读取

`src/Storages/MergeTree/MergeTreeReaderCompact.h` — 所有列打包在一起，需要按 Granule 读取并提取目标列：

```
读取 user_id 列 (Mark 3-7):
  1. 打开 data.mrk → 读取 mark[3] 中 user_id 列的偏移量
  2. 打开 data.bin → seek 到对应位置
  3. 读取该 Granule 的所有列数据（按列交织存储）
  4. 只提取 user_id 列的数据
  5. 跳过其他列的数据
```

Compact Part 的列读取比 Wide Part 多了"跳过其他列"的开销，但由于数据是按 Granule 交织存储的，实际上每个 Granule 内的数据是连续的，跳过的开销很小。

### 读取流程详解

```
1. 定位: mark[N] → {offset_in_compressed, offset_in_decompressed}
2. Seek: file.seek(offset_in_compressed)
3. 读取压缩块: 从当前位置读取到下一个 Mark 的偏移量
4. 解压: CompressedReadBuffer → 原始数据
   ├── 检查压缩方法 (LZ4/ZSTD/Delta/etc.)
   ├── 创建对应 Decompressor
   └── 解压到内存缓冲区
5. 裁剪: 跳过 offset_in_decompressed 之前的行
6. 提取: 取 [from_mark, to_mark) 范围内的行
7. 反序列化: 二进制数据 → IColumn
   ├── 数值列: memcpy 到 PaddedPODArray
   ├── 字符串列: 读取 offsets + chars
   └── 复杂类型: 递归反序列化
```

### 压缩算法

`src/Compression/` — 解压是读取路径上的关键环节：

| 算法 | 压缩比 | 解压速度 | 适用场景 |
|------|--------|----------|----------|
| LZ4 | 低 | 极快（~4 GB/s） | 默认 |
| ZSTD | 高 | 中等（~1 GB/s） | 归档/冷数据 |
| Delta | 取决于数据 | 快 | 递增数值 |
| DoubleDelta | 取决于数据 | 快 | 时间序列 |
| Gorilla | 取决于数据 | 快 | 浮点数时间序列 |
| FPC | 取决于数据 | 快 | 浮点数 |
| DeflateQPress | 高 | 慢 | 兼容性 |

### I/O 调度

ClickHouse 对远程存储（S3/HDFS）的读取使用异步 I/O：

```
本地磁盘:
  同步读取 → 直接 read() 系统调用

远程存储 (S3):
  异步读取 → 异步提交读取请求 → 回调处理
  预取: 预测下一个 Mark Range → 提前发起读取请求
  并行: 同时预取多个列的数据

设置:
  remote_read_min_bytes_for_seek = 4KB  ← 小于此值不 seek，继续读
  remote_fs_read_max_backoff_ms = 10000 ← 读取失败退避上限
  remote_read_backoff_max_tries = 5     ← 读取失败重试次数
```

## 8.8 Part 裁剪全流程

一个完整的 SELECT 查询在读取前会经过多层裁剪：

```
原始数据: 1000 个 Parts, 100 万个 Granules

Level 1: 分区裁剪 (PartitionPruner)
  WHERE toYYYYMM(date) = 202401
  → 只保留 202401 分区的 Parts: 200 个 Parts

Level 2: 主键索引裁剪 (KeyCondition)
  WHERE date = '2024-01-01' AND user_id = 300
  → 对每个 Part 的 primary.cidx 评估
  → 保留可能满足条件的 MarkRanges: 50 个 Parts, 5000 个 Granules

Level 3: 跳数索引裁剪 (Skip Index)
  minmax(date): 排除日期范围不满足的 Granules
  bloom_filter(user_id): 排除 user_id 不可能存在的 Granules
  → 保留: 50 个 Parts, 2000 个 Granules

Level 4: PREWHERE 裁剪
  PREWHERE status = 'active'
  → 先读 status 列 → 过滤掉 status ≠ 'active' 的行
  → 保留: 50 个 Parts, 约 500 个 Granules 的有效行

Level 5: 运行时过滤 (WHERE)
  WHERE col4 > 0
  → 对剩余行执行最终过滤
```

这个多层裁剪是 ClickHouse 查询性能的核心——每一层都减少了下一层需要处理的数据量。

## 8.9 本章小结

```
查询 → KeyCondition（索引裁剪）→ MarkRanges → ReadPool（动态分配）
  → MergeTreeSelectProcessor（读取+解压）→ Block → Pipeline

三层裁剪:
  分区裁剪 → 主键索引裁剪 → 跳数索引裁剪 → PREWHERE → 运行时过滤

读取模式:
  Default → 多线程并行，结果无序
  InOrder → 按主键顺序，MergeSorter 归并
  InReverseOrder → 按主键逆序

三个关键优化:
  1. 稀疏索引裁剪 — 按 Granule 粒度跳过不满足条件的数据
  2. PREWHERE — 先读过滤列再读数据列，减少 I/O
  3. 动态 ReadPool — 慢线程的任务被快线程偷取，保证负载均衡

列读取:
  Wide Part → 每列独立文件，按需打开
  Compact Part → 所有列交织存储，按 Granule 读取
  远程存储 → 异步 I/O + 预取
```

**关键文件地图**：
```
src/Storages/MergeTree/KeyCondition.h                  → 索引条件评估
src/Processors/QueryPlan/ReadFromMergeTree.h           → 读取 Step
src/Storages/MergeTree/IMergeTreeReadPool.h            → 读取池接口
src/Storages/MergeTree/MergeTreeReadPool.h             → 默认读取池
src/Storages/MergeTree/MergeTreeReadPoolInOrder.h      → 有序读取池
src/Storages/MergeTree/MergeTreeReadPoolParallelReplicas.h → 并行副本读取池
src/Storages/MergeTree/MergeTreeSelectProcessor.h      → 读取处理器
src/Storages/MergeTree/IMergeTreeReader.h              → 列数据读取器接口
src/Storages/MergeTree/MergeTreeReaderWide.h           → Wide Part 读取器
src/Storages/MergeTree/MergeTreeReaderCompact.h        → Compact Part 读取器
src/Storages/MergeTree/PartitionPruner.h               → 分区裁剪
src/Compression/                                        → 压缩/解压实现
```
