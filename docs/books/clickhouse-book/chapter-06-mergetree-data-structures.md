# Chapter 6: MergeTree 数据结构 — Parts / Marks / Granules / Skip Index

## 6.1 MergeTree 存储模型概览

MergeTree 是 ClickHouse 的核心存储引擎，所有其他引擎（ReplicatedMergeTree、ReplacingMergeTree、SummingMergeTree 等）都基于它。

```
MergeTree Table
  ├── data/                          ← 数据目录
  │     ├── all_1_1_0/               ← Data Part (Part #1)
  │     │     ├── columns.txt        ← 列定义
  │     │     ├── count.txt          ← 行数
  │     │     ├── primary.cidx       ← 主键索引（稀疏）
  │     │     ├── minmax_<col>.idx   ← 跳数索引 minmax
  │     │     ├── <col>.bin          ← 列数据（压缩）
  │     │     ├── <col>.mrk          ← Mark 文件（Granule 偏移量）
  │     │     └── checksums.txt      ← 校验和
  │     ├── all_2_2_0/               ← Part #2
  │     └── all_3_3_0/               ← Part #3
  │
  └── metadata/                      ← 元数据（ZooKeeper/本地）
```

### MergeTree 家族

所有 MergeTree 变体共享同一套数据结构，区别在于 Merge 行为：

| 引擎 | Merge 行为 | 适用场景 |
|------|-----------|----------|
| `MergeTree` | 仅合并 | 基础引擎 |
| `ReplacingMergeTree` | 去重（保留最新版本） | 点查去重 |
| `SummingMergeTree` | 预聚合（相同主键数值求和） | 指标预聚合 |
| `AggregatingMergeTree` | 预聚合（聚合状态合并） | 物化视图 |
| `CollapsingMergeTree` | 抵消（sign = -1 行删除 sign = 1 行） | 日志抵消 |
| `VersionedCollapsingMergeTree` | 抵消（带版本号） | 有序抵消 |
| `CoalescingMergeTree` | 区间合并（相邻区间合并） | 时间区间 |

> **第一性原理**：为什么用 Merge 而非原地更新？因为追加写入（append-only）是最高吞吐的写入模式——不需要查找、不需要加锁、不需要随机 I/O。所有的复杂操作（去重、聚合、删除）都延迟到后台 Merge 中执行，用空间换时间。这是 LSM-Tree 思想在 OLAP 场景的变体。

## 6.2 Granule — 最小读取单元

MergeTree 将数据按 Granule（颗粒）组织，Granule 是 ClickHouse 读取数据的最小单元：

- **Granule 大小**：由 `index_granularity` 控制（默认 8192 行）
- **稀疏索引**：每个 Granule 记录一条主键值，而非每行
- **压缩单元**：每个 Granule 在 `.bin` 文件中独立压缩

```
数据行:    [row 0] [row 1] ... [row 8191] | [row 8192] ... [row 16383] | ...
                 Granule 0                        Granule 1
主键索引:  key(granule_0)                    key(granule_1)
Mark 文件: mark_0 = {offset, compressed_offset}  mark_1 = ...
```

**为什么是 8192？** 这是 CPU 缓存行大小（64 bytes）× 列数 × 主键大小的综合优化结果。太小的 Granule 导致索引膨胀，太大的 Granule 导致读取浪费。

### IndexGranularity — 粒度管理

`src/Storages/MergeTree/IndexGranularity.h` — 跟踪每个 Granule 的行数：

```cpp
class IndexGranularity
{
    // 大多数情况下所有 Granule 大小相同 (index_granularity = 8192)
    // 但最后一个 Granule 可能不满（adaptive granularity 时更常见）
    std::vector<size_t> marks_to_rows;  // mark_index → 行数累加

    size_t getRowsStartingFrom(size_t starting_mark) const;
    size_t getRowsInRange(const MarkRange & range) const;
    size_t countMarksForRows(size_t from_mark, size_t number_of_rows) const;
};
```

### 自适应 Granule（Adaptive Index Granularity）

`index_granularity_bytes` 设置启用自适应粒度——当某个 Granule 的数据量超过阈值时提前切分：

```
固定粒度: 每 8192 行一个 Granule
           [8192行] [8192行] [8192行]

自适应粒度: 按字节大小动态切分
           [8192行, 1MB] [4000行, 1MB] [8192行, 1MB]
                        ↑ 宽列，提前切分

设置:
  index_granularity = 8192          ← 行数下限
  index_granularity_bytes = 10485760 ← 字节上限 (10MB, 0 = 禁用)
```

自适应粒度在宽表（1000+ 列）场景下特别有用，避免单个 Granule 过大导致读取浪费。

## 6.3 Mark 文件 — 定位 Granule

`src/Storages/MergeTree/MarkRange.h` — Mark 是 Granule 在压缩数据文件中的定位信息：

```cpp
struct MarkInCompressedFile
{
    size_t offset_in_compressed_file;    // 在 .bin 压缩文件中的偏移
    size_t offset_in_decompressed_block; // 在解压块内的偏移
};
```

每个 `.mrk` 文件存储所有 Granule 的 Mark，使得读取第 N 个 Granule 只需：
1. 读取 `mark[N]` 获取偏移量
2. Seek 到 `.bin` 文件对应位置
3. 解压该块

### MarkRange — 读取范围

```cpp
struct MarkRange
{
    size_t begin;  // 起始 Mark 编号（包含）
    size_t end;    // 结束 Mark 编号（不包含）
};

// 例如: MarkRange{0, 3} 表示读取 Mark 0, 1, 2 对应的 3 个 Granule
```

查询时，`KeyCondition` 评估每个 MarkRange 是否可能包含满足条件的数据，排除不可能的 MarkRange。

### Mark 文件格式

`.mrk` 文件是简单的二进制序列化——每个 Mark 占 16 字节（两个 `size_t`）：

```
mark_0: [offset_in_compressed=0x0000] [offset_in_decompressed=0x0000]
mark_1: [offset_in_compressed=0x1A2B] [offset_in_decompressed=0x0000]
mark_2: [offset_in_compressed=0x3C4D] [offset_in_decompressed=0x0000]
...
```

注意 `offset_in_decompressed_block` 在非自适应粒度模式下通常为 0（每个 Granule 起始于压缩块边界），在自适应粒度模式下可能非零。

## 6.4 Primary Key Index — 稀疏索引

`src/Storages/MergeTree/KeyCondition.h` — 主键索引是 MergeTree 最重要的加速结构：

```
Primary Key: (date, user_id)

Granule 0: (2024-01-01, 100)     ← 索引条目
Granule 1: (2024-01-01, 500)
Granule 2: (2024-01-02, 100)
Granule 3: (2024-01-03, 200)

查询: WHERE date = '2024-01-01' AND user_id = 300
→ 使用索引排除 Granule 2 和 3
→ 只读取 Granule 0 和 1
```

**关键特性**：
- 稀疏（不是每行一条索引，而是每 Granule 一条）
- 主键不唯一（允许重复）
- 排序键 ≠ 主键（ORDER BY 定义排序，PRIMARY KEY 定义索引，默认相同）
- 完全驻留内存（索引常驻 RAM，Mark 文件按需加载）

### KeyCondition：索引条件评估

```cpp
class KeyCondition
{
    // 评估查询条件是否可以借助主键索引裁剪
    BoolMask mayBeTrueOnGranule(size_t granule_idx) const;
    BoolMask mayBeTrueOnGranulesInRange(const MarkRange & range) const;

    // 将 WHERE 条件转换为索引可评估的形式
    // 支持 =, >, <, >=, <=, IN, BETWEEN, LIKE (前缀)
};
```

**支持的索引条件**：

| 操作符 | 索引裁剪 | 说明 |
|--------|----------|------|
| `=` | 完全裁剪 | 精确匹配主键前缀 |
| `>`, `<`, `>=`, `<=` | 范围裁剪 | 利用主键排序性 |
| `IN` | 集合裁剪 | 转换为多个等值条件的 OR |
| `BETWEEN` | 范围裁剪 | 等价于 `>= AND <=` |
| `LIKE 'prefix%'` | 前缀裁剪 | 字符串前缀匹配 |
| `LIKE '%pattern%'` | **不支持** | 后缀通配符无法利用排序 |
| `NOT IN` | **不支持** | 否定条件无法裁剪 |
| 函数比较 `col1 + 1 > col2` | **不支持** | 非直接列比较 |

### 主键前缀匹配规则

主键索引遵循**最左前缀匹配**原则（类似 B+ 树索引）：

```
Primary Key: (date, user_id, event_type)

WHERE date = '2024-01-01'                              → 使用 date 列裁剪 ✓
WHERE date = '2024-01-01' AND user_id = 300            → 使用 date + user_id 裁剪 ✓
WHERE date = '2024-01-01' AND event_type = 'click'     → 只使用 date 裁剪（跳过 user_id）
WHERE user_id = 300                                     → 无法使用索引裁剪 ✗
```

## 6.5 Skip Index — 跳数索引

`src/Storages/MergeTree/` 下的 `IMergeTreeDataPart` 管理跳数索引。Skip Index 为非主键列提供额外的裁剪能力：

| 索引类型 | 作用 | 实现 |
|----------|------|------|
| `minmax` | 记录每个 Granule 的 min/max 值 | `minmax_<col>.idx` |
| `set` | 记录每个 Granule 的唯一值集合（有上限） | `set_<col>.idx` |
| `bloom_filter` | 布隆过滤器（等值 / IN / LIKE） | `bloom_filter_<col>.idx` |
| `ngrambf_v1` | N-gram 布隆过滤器（LIKE/Contains） | `ngrambf_v1_<col>.idx` |
| `tokenbf_v1` | Token 布隆过滤器（分词匹配） | `tokenbf_v1_<col>.idx` |
| `inverted` | 倒排索引（全文搜索） | `inverted_<col>.idx` |
| `vector_similarity` | 向量相似度索引（HNSW） | `<col>_vsidx` |

**评估流程**：对每个 Granule，使用 Skip Index 判断该 Granule 是否可能包含满足条件的数据。如果所有索引都返回 "不可能"，跳过该 Granule。

### minmax 索引

最简单也最实用的跳数索引：

```sql
ALTER TABLE t ADD INDEX idx_date minmax(date) TYPE minmax GRANULARITY 1;
```

每个 Granule 记录 `min(date)` 和 `max(date)`。查询时：
- `WHERE date > '2024-06-01'`：如果 `max(date) < '2024-06-01'`，跳过该 Granule
- `WHERE date = '2024-03-15'`：如果 `min(date) > '2024-03-15'` 或 `max(date) < '2024-03-15'`，跳过

**GRANULARITY 参数**：控制索引粒度——`GRANULARITY 2` 表示每 2 个 Granule 共享一条索引记录，减少索引大小但降低精度。

### set 索引

记录每个 Granule 中的唯一值集合（有上限）：

```sql
ALTER TABLE t ADD INDEX idx_region set(region) TYPE set(100) GRANULARITY 1;
```

`set(100)` 表示最多记录 100 个唯一值。当唯一值超过上限时，索引退化（无法确定某个值不在集合中）。

适用场景：低基数的等值过滤，如区域、状态码等。

### bloom_filter 索引

基于布隆过滤器的概率索引，支持等值和 IN 查询：

```sql
ALTER TABLE t ADD INDEX idx_user bloom_filter(user_id) TYPE bloom_filter(0.01, 5, 256) GRANULARITY 1;
```

参数含义：
- `0.01`：假阳性率（1%）
- `5`：哈希函数数量
- `256`：布隆过滤器位数（以 filter 数为单位）

**优点**：内存占用小，O(1) 查询
**缺点**：有假阳性（可能误报存在，但不会误报不存在）

### ngrambf_v1 / tokenbf_v1 — 全文布隆过滤器

为 `LIKE` 和字符串搜索优化的布隆过滤器：

```sql
-- N-gram 布隆过滤器：将文本切为 n-gram，每个 n-gram 插入布隆过滤器
ALTER TABLE t ADD INDEX idx_body ngrambf_v1(body, 3, 512, 2, 0) TYPE ngrambf_v1 GRANULARITY 1;

-- Token 布隆过滤器：将文本按空格/标点切为 token，每个 token 插入布隆过滤器
ALTER TABLE t ADD INDEX idx_msg tokenbf_v1(msg, 512, 3, 0) TYPE tokenbf_v1 GRANULARITY 1;
```

`ngrambf_v1` 参数：`(col, ngram_size, filter_size, hash_funcs, seed)`
`tokenbf_v1` 参数：`(col, filter_size, hash_funcs, seed)`

### inverted — 倒排索引

`src/Storages/MergeTree/MergeTreeIndexFullText.h` — 最强大的全文索引：

```sql
ALTER TABLE t ADD INDEX idx_text inverted(body) TYPE inverted(2) GRANULARITY 1;
```

倒排索引为每个 token 维护一个 posting list（包含该 token 的 Granule 列表）。支持：
- `WHERE body = 'hello'` — 精确匹配
- `WHERE hasToken(body, 'hello')` — token 级别匹配
- `WHERE hasPhrase(body, 'hello world')` — 短语匹配（PR #101997 新增）

参数 `inverted(2)` 中的数字表示 tokenizer 类型。

### vector_similarity — 向量相似度索引

`src/Storages/MergeTree/MergeTreeIndexVectorSimilarity.h` — 基于 HNSW 的向量检索索引：

```sql
ALTER TABLE t ADD INDEX idx_vec vector_similarity(vec, 'hnsw', 'cosine', 512)
TYPE vector_similarity GRANULARITY 1;
```

这是 ClickHouse 向量搜索能力的基础设施。支持的距离函数：
- `cosine` — 余弦距离
- `dotProduct` — 点积（PR #102254 新增）
- `L2Distance` — 欧几里得距离

索引在 Merge 时构建，查询时利用 HNSW 图结构进行近似最近邻搜索。

### 跳数索引评估流程

```
查询: WHERE region = 'US' AND user_id = 42
索引: minmax(date), set(region), bloom_filter(user_id)

对每个 Granule:
  1. minmax(date): 本索引无法评估 region/user_id 条件 → 返回 may_be_true
  2. set(region): region='US' 不在该 Granule 的 set 中 → 返回 may_be_false
  3. 跳过该 Granule（有索引返回 false 即可跳过）

如果 set(region) 返回 may_be_true:
  4. bloom_filter(user_id): 可能包含 user_id=42 → 返回 may_be_true
  5. 需要实际读取该 Granule 的数据验证
```

## 6.6 Data Part 生命周期

```cpp
// src/Storages/MergeTree/IMergeTreeDataPart.h
class IMergeTreeDataPart
{
    String name;                     // Part 名称: all_{min}_{max}_{level}
    MergeTreeDataPartType type;      // Wide / Compact / InMemory
    time_t modification_time;        // 修改时间
    UInt64 bytes_on_disk;            // 磁盘占用
    size_t rows_count;               // 行数
    IndexGranularity index_granularity;  // Granule 大小信息
    std::optional<String> min_date, max_date;  // 日期范围
    NamesAndTypesList columns;       // 列定义

    // 校验和
    MergeTreeDataPartChecksums checksums;

    // 跳数索引
    MergeTreeIndexFlagIndices skip_indices;

    // Part 状态
    std::atomic<State> state = State::Temporary;
};
```

### Part 状态机

```
                    ┌──────────────┐
                    │  Temporary   │ ← 正在写入
                    └──────┬───────┘
                           │ 写入完成
                    ┌──────▼───────┐
           ┌───────│  PreActive   │ ← 已提交，等待加载
           │       └──────┬───────┘
           │              │ 加载到内存
           │       ┌──────▼───────┐
           │       │   Active     │ ← 可被查询
           │       └──────┬───────┘
           │              │ 被 Merge 替代
           │       ┌──────▼───────┐
           │       │  Outdated    │ ← 等待清理
           │       └──────┬───────┘
           │              │ 清理完成
           │       ┌──────▼───────┐
           └───────│  Deleting    │ ← 正在删除文件
                   └──────┬───────┘
                          │
                   ┌──────▼───────┐
                   │  Deleted     │ ← 已删除
                   └──────────────┘
```

### Part 命名规则

`all_{min_block}_{max_block}_{level}`

- `min_block` / `max_block`：合并前 Part 的编号范围
- `level`：合并次数（每合并一次 level + 1）

**示例**：

```
all_1_1_0     ← block 1，从未合并
all_2_2_0     ← block 2，从未合并
all_1_2_1     ← block 1-2 合并后的结果，level=1
all_3_3_0     ← block 3
all_1_3_2     ← block 1-3 合并后的结果，level=2
```

### Part 类型

| 类型 | 列存储方式 | 文件数 | 适用场景 |
|------|-----------|--------|----------|
| `Wide` | 每列一个 `.bin` + `.mrk` | 2×列数 | 大 Part（默认） |
| `Compact` | 所有列打包到一个 `.bin` + 一个 `.mrk` | 2 | 小 Part（INSERT 后初期） |
| `InMemory` | 只在内存中 | 0 | Buffer 引擎、异步 INSERT |

**自动选择逻辑**：

```
写入新 Part 时:
  if rows < min_rows_for_compact_part AND bytes < min_bytes_for_compact_part:
      → Compact Part
  else:
      → Wide Part

Merge 后:
  if 结果 Part 大小超过阈值:
      → 自动转为 Wide Part
```

Compact Part 的优势：减少文件数量。一个 10 列的表，Wide Part 需要 20+ 个文件，Compact Part 只需要 2 个数据文件 + 元数据文件。在大量小 Part 的场景下（如高频小批量 INSERT），这显著减少了文件系统压力。

## 6.7 Checksums — 数据完整性

`src/Storages/MergeTree/MergeTreeDataPartChecksums.h` — 每个 Part 的 `checksums.txt` 文件记录了该 Part 中所有文件的校验和：

```cpp
struct MergeTreeDataPartChecksums
{
    struct Checksum
    {
        UInt128 hash128;     // SIP hash 128-bit
        size_t file_size;    // 文件大小
    };

    // 每个文件（.bin, .mrk, .idx 等）的校验和
    std::map<String, Checksum> files;

    // 计算整个 checksums 文件自身的校验和
    UInt128 computeTotalChecksum128() const;
};
```

**用途**：
1. **Part 传输验证**：副本间传输 Part 后验证数据完整性
2. **启动检测**：Server 启动时检查 Part 文件是否损坏
3. **Merge 验证**：Merge 完成后验证输出 Part 的完整性

## 6.8 列压缩编码

`src/Compression/` — ClickHouse 的列数据压缩不仅是全列统一算法，还支持列级别的压缩编码（Compression Codec）：

```sql
CREATE TABLE t (
    timestamp DateTime CODEC(Delta, ZSTD),
    value Float64 CODEC(Gorilla),
    tags Array(String) CODEC(ZSTD(3)),
    user_id UInt64 CODEC(DoubleDelta, LZ4)
) ENGINE = MergeTree ORDER BY timestamp;
```

### 压缩算法对比

| 算法 | 压缩比 | 解压速度 | 适用场景 | 文件 |
|------|--------|----------|----------|------|
| LZ4 | 低 | 极快（~4 GB/s） | 默认 | `CompressionLZ4.h` |
| ZSTD | 高 | 中等（~1 GB/s） | 归档/冷数据 | `CompressionZSTD.h` |
| Delta | 取决于数据 | 快 | 递增数值 | 不独立使用，作为预处理 |
| DoubleDelta | 取决于数据 | 快 | 时间序列（单调递增） | 同上 |
| Gorilla | 取决于数据 | 快 | 浮点数时间序列 | 同上 |
| FPC | 取决于数据 | 快 | 浮点数 | `CompressionFPC.h` |
| DeflateQPress | 高 | 慢 | 兼容性 | `CompressionDeflateQPL.h` |

**Codec 链式组合**：`CODEC(Delta, ZSTD)` 表示先对数据做 Delta 编码（差值），再对差值做 ZSTD 压缩。这种组合在时间序列数据上效果极佳——差值通常很小，ZSTD 可以高效压缩。

### 压缩数据块格式

`.bin` 文件中的压缩数据按块（Block）组织：

```
[Block Header][Compressed Data][Block Header][Compressed Data]...

Block Header (17 bytes):
  +0:  compressed_size   (UInt32, 4 bytes)
  +4:  uncompressed_size (UInt32, 4 bytes)
  +8:  compression_method(UInt8,  1 byte)
  +9:  checksum          (UInt128, 16 bytes)  ← 可选

每个 Block 通常包含 1 个 Granule 的数据（64KB-1MB）
```

## 6.9 columns.txt 与 count.txt

### columns.txt — 列定义

```
columns format version: 1
2 columns:
`timestamp` DateTime
`user_id` UInt64
```

记录该 Part 包含的列名和类型。不同 Part 可能有不同的列集合（ALTER TABLE ADD COLUMN 后，旧 Part 没有新列）。

### count.txt — 行数

```
819200
```

一个纯文本文件，只包含该 Part 的行数。这是快速获取 Part 行数的捷径——不需要读取索引或数据文件。

## 6.10 本章小结

```
MergeTree Data Part
  ├── Granule (8192 行)       ← 最小读取单元
  │     ├── 自适应粒度          ← index_granularity_bytes
  │     └── IndexGranularity   ← 粒度管理
  ├── Primary Key Index       ← 稀疏索引（每 Granule 一条）
  │     └── KeyCondition       ← 最左前缀匹配裁剪
  ├── Mark 文件 (.mrk)        ← Granule 在压缩文件中的偏移
  │     └── MarkRange          ← 读取范围
  ├── 列数据 (.bin)           ← 压缩存储
  │     └── Codec 链           ← Delta→ZSTD, DoubleDelta→LZ4 等
  ├── Skip Index (.idx)       ← minmax / set / bloom / inverted / vector
  │     ├── minmax             ← 最实用，min/max 范围裁剪
  │     ├── set                ← 低基数等值过滤
  │     ├── bloom_filter       ← 概率索引，等值/IN
  │     ├── ngrambf_v1         ← LIKE 前缀匹配
  │     ├── tokenbf_v1         ← 分词匹配
  │     ├── inverted           ← 全文搜索（倒排索引）
  │     └── vector_similarity  ← 向量检索（HNSW）
  ├── Checksums                ← 数据完整性校验
  ├── Part 状态机              ← Temporary→PreActive→Active→Outdated→Deleting→Deleted
  └── 元数据 (columns.txt, count.txt, checksums.txt)
```

**关键文件地图**：
```
src/Storages/MergeTree/IMergeTreeDataPart.h        → Data Part 定义
src/Storages/MergeTree/IMergeTreeDataPart.cpp       → Part 加载/状态管理
src/Storages/MergeTree/MergeTreeDataPartType.h      → Part 类型枚举
src/Storages/MergeTree/KeyCondition.h               → 主键索引条件评估
src/Storages/MergeTree/MarkRange.h                  → Mark 范围
src/Storages/MergeTree/IndexGranularity.h           → Granule 粒度
src/Storages/MergeTree/MergeTreeDataPartChecksums.h → 校验和
src/Storages/MergeTree/MergeTreeIndexFullText.h     → 倒排索引
src/Storages/MergeTree/MergeTreeIndexVectorSimilarity.h → 向量索引
src/Storages/MergeTree/IMergeTreeReader.h           → Part 读取接口
src/Compression/                                     → 压缩算法实现
```
