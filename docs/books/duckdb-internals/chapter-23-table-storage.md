# 第23章：表存储格式

> 从一行 SQL 到磁盘上的字节，中间经过四层抽象。每一层都有独立的生命周期、独立的压缩策略、独立的并发控制。理解这四层结构，是理解 DuckDB 存储引擎的钥匙。

## 23.1 DataTable → RowGroupCollection → RowGroup → ColumnData 的四层结构

```
DataTable                  逻辑表入口
  └── RowGroupCollection   行组容器（管理行组的生命周期和统计）
       └── RowGroup        固定大小数据块（122,880 行，含 MVCC 版本信息）
            └── ColumnData 列存储容器（每列一个，管理段树和更新）
                 └── ColumnSegment  物理存储单元（压缩后的列数据，关联磁盘 Block）
```

### DataTable：逻辑表入口

```cpp
// src/include/duckdb/storage/data_table.hpp
class DataTable : public enable_shared_from_this<DataTable> {
    AttachedDatabase &db;
    shared_ptr<DataTableInfo> info;               // 共享的表元数据
    vector<ColumnDefinition> column_definitions;   // 列模式
    mutex append_lock;                             // 保护追加操作
    shared_ptr<RowGroupCollection> row_groups;     // 数据容器
    atomic<DataTableVersion> version;              // MAIN_TABLE / ALTERED / DROPPED
};
```

**ALTER 的 Copy-on-Write**：当表被修改（增加列、删除列、改变类型、增加约束），创建一个新的 `DataTable`。旧表的 `version` 设为 `ALTERED`。新表共享同一个 `DataTableInfo`（通过 `shared_ptr`）。这是表级别的写时复制——旧版本对进行中的事务有效，新事务看到新模式。

**追加协议**：三阶段：
1. `AppendLock()` — 获取互斥锁，确定行起始位置
2. `InitializeAppend()` — 设置 RowGroupCollection 追加状态
3. `Append()` + `FinalizeAppend()` + `CommitAppend()` — 数据流入行组

**行 ID 的分界**：`MAX_ROW_ID = 2^55`。低于此值的行属于持久表，高于此值的属于事务本地存储。

### RowGroupCollection：行组容器

```cpp
// src/include/duckdb/storage/table/row_group_collection.hpp
class RowGroupCollection {
    BlockManager &block_manager;
    const idx_t row_group_size;                     // 默认 122,880
    atomic<idx_t> total_rows;                       // 跨所有行组的总行数
    shared_ptr<DataTableInfo> info;
    shared_ptr<RowGroupSegmentTree> owned_row_groups; // 行组段树
    TableStatistics stats;                          // 列统计
    MetaBlockPointer metadata_pointer;              // 磁盘元数据根指针
};
```

**RowGroupSegmentTree**：行组的延迟加载。数据库从磁盘加载时，行组不全部加载——`LoadSegment()` 按需从 `MetadataReader` 流反序列化单个 `RowGroup`。

**Checkpoint 架构**：`Checkpoint` 方法支持并行——每个行组的 Checkpoint 任务通过 `TaskExecutor` 并行执行。未变更的行组可以复用元数据指针（避免重写未变更的元数据块）。

## 23.2 RowGroup：122,880 行的固定大小数据块

### 为什么是 122,880？

```cpp
// src/include/duckdb/storage/storage_info.hpp
DEFAULT_ROW_GROUP_SIZE = 122880  // = 60 × STANDARD_VECTOR_SIZE
// 编译时强制：DEFAULT_ROW_GROUP_SIZE % STANDARD_VECTOR_SIZE == 0
```

122,880 = 60 × 2048——恰好是 60 个满 Vector。这个选择平衡了：
- **足够大**：每个行组的统计信息（min/max）足够代表性，Zone Map 裁剪效果好
- **足够小**：不会因为一个大行组阻塞其他操作
- **Vector 对齐**：行组边界与 Vector 边界对齐，简化扫描逻辑

### RowGroup 结构

```cpp
// src/include/duckdb/storage/table/row_group.hpp
class RowGroup : public SegmentBase<RowGroup> {
    reference<RowGroupCollection> collection;
    atomic<optional_ptr<RowVersionManager>> version_info;  // MVCC 版本信息
    mutable vector<shared_ptr<ColumnData>> columns;        // 列式数据
    mutable unique_ptr<atomic<bool>[]> is_loaded;          // 每列延迟加载标志
    vector<MetaBlockPointer> column_pointers;              // 磁盘列元数据指针
    vector<MetaBlockPointer> deletes_pointers;             // 删除元数据指针
};
```

### 延迟列加载

RowGroup 从磁盘反序列化时，`columns` 向量填充为空 `shared_ptr`，`is_loaded` 标志全部为 false。`LoadColumn` 在首次访问时加载：

```cpp
// src/storage/table/row_group.cpp
void RowGroup::LoadColumn(storage_t c) const {
    // 双重检查锁定模式
    auto &metadata_manager = GetCollection().GetMetadataManager();
    MetadataReader column_data_reader(metadata_manager, column_pointers[c]);
    this->columns[c] = ColumnData::Deserialize(...);
    is_loaded[c] = true;
}
```

这意味着 100 列的表，只读 3 列的查询只从磁盘加载 3 列。这是列式存储最根本的优势之一——DuckDB 在 RowGroup 级别实现了它。

### RowVersionManager：行组的 MVCC

```cpp
// src/include/duckdb/storage/table/row_version_manager.hpp
// 使用 vector<unique_ptr<ChunkInfo>> 追踪行可见性
// 每个 ChunkInfo 对应一个 Vector（2048 行）

// 三种 ChunkInfo：
// ChunkConstantInfo — 整个 Vector 由同一事务插入/删除（常见情况）
// ChunkVectorInfo   — 每行独立的事务 ID（混合事务的罕见情况）
// Empty             — 无版本信息
```

扫描时，`GetSelVector` 产生选择向量，过滤当前事务不可见的行。

### Checkpoint 写入优化

Checkpoint 时按列写入所有行组（而非按行组写入所有列）：

```
按行组写入：RG0[col0, col1, ...] → RG1[col0, col1, ...] → ...
按列写入：  col0[RG0, RG1, ...] → col1[RG0, RG1, ...] → ...  ← DuckDB 选择
```

按列写入使得同一列的压缩数据在磁盘上连续——更好的 I/O 局部性。

## 23.3 ColumnData 与 ColumnSegment：列存储的物理实现

### ColumnData 类型层次

```cpp
// src/include/duckdb/storage/table/column_data.hpp
// CreateColumn 工厂方法根据逻辑类型创建子类：

| 逻辑类型   | 类                  | 特殊行为                            |
|-----------|--------------------|------------------------------------|
| STRUCT    | StructColumnData   | vector<ColumnData> sub_columns + validity |
| LIST      | ListColumnData     | child_column (offsets + child) + validity  |
| ARRAY     | ArrayColumnData    | child_column + validity                  |
| VALIDITY  | ValidityColumnData | NULL 位图存储                           |
| GEOMETRY  | GeoColumnData      | 几何专用存储                            |
| VARIANT   | VariantColumnData  | 细粒变体存储                            |
| 默认       | StandardColumnData | validity + 数据段                      |
```

这个层次结构让每种嵌套类型管理自己的子列树。例如，`STRUCT(A INT, B VARCHAR)` 创建三个子 `ColumnData`：一个 `ValidityColumnData`（结构 null 掩码），一个 `StandardColumnData` 用于 A，一个 `StandardColumnData` 用于 B。

### ColumnData 核心结构

```cpp
class ColumnData : public enable_shared_from_this<ColumnData> {
    atomic<idx_t> count;               // 值数量
    ColumnSegmentTree data;            // ColumnSegment 段树
    unique_ptr<UpdateSegment> updates; // 原地更新追踪
    unique_ptr<SegmentStatistics> stats; // 列统计（Zone Map）
    atomic<ColumnDataType> data_type;  // MAIN_TABLE / TRANSACTION_LOCAL
    optional_ptr<ColumnData> parent;   // 父列（嵌套类型）
};
```

### ColumnSegment：两种形态

```cpp
// src/include/duckdb/storage/table/column_segment.hpp
enum class ColumnSegmentType {
    TRANSIENT,   // 内存中，未压缩，支持追加
    PERSISTENT   // 磁盘上，已压缩，只读（更新进入 UpdateSegment）
};
```

**Transient → Persistent 的转换**发生在 Checkpoint 时。`ColumnDataCheckpointer` 运行三阶段压缩流水线：

1. **Analyze**：每个候选压缩函数运行分析，产生得分（估计压缩后大小）
2. **Compress**：得分最低的函数执行压缩
3. **Write**：压缩段写入磁盘

### 压缩函数：策略模式

```cpp
// src/include/duckdb/function/compression_function.hpp
struct CompressionFunction {
    // 分析：init_analyze, analyze, final_analyze
    // 压缩：init_compression, compress, compress_finalize
    // 扫描：init_scan, scan_vector, scan_partial, select, filter, fetch_row, skip
    // 追加：init_segment, init_append, append, finalize_append, revert_append
    // 序列化：serialize_state, deserialize_state, visit_block_ids
};
```

### 共享块：PartialBlockManager

多个压缩列段可以共享一个存储块——这对窄列（如 BOOLEAN 列压缩后仅几百字节）至关重要，避免为每个段分配完整的 256KB 块。

## 23.4 元数据层

### BlockPointer 与 MetaBlockPointer

```cpp
// src/include/duckdb/storage/block.hpp
struct BlockPointer {
    block_id_t block_id;  // 块 ID
    uint32_t offset;      // 块内偏移
};

struct MetaBlockPointer {
    idx_t block_pointer;  // 低 56 位 = 块 ID，高 8 位 = 子块索引
    uint32_t offset;      // 子块内偏移
};
```

### DataPointer：持久列段的磁盘记录

```cpp
// src/include/duckdb/storage/data_pointer.hpp
struct DataPointer {
    uint64_t row_start;                              // 起始行号
    uint64_t tuple_count;                            // 行数
    BlockPointer block_pointer;                      // 数据位置
    CompressionType compression_type;                 // 压缩算法
    BaseStatistics statistics;                        // Zone Map 统计
    unique_ptr<ColumnSegmentState> segment_state;     // 压缩特定状态
};
```

### MetadataManager：键值元数据存储

```cpp
// src/include/duckdb/storage/metadata/metadata_manager.hpp
// 每个存储块划分为 64 个子块（METADATA_BLOCK_COUNT = 64）
// 子块大小 ≈ 262136 / 64 ≈ 4095 字节

struct MetadataPointer {
    idx_t block_index : 56;  // 存储 Block ID
    uint8_t index : 8;       // 子块索引（0-63）
};
```

`MetadataWriter` 将元数据写入子块链表——当一个子块填满，分配新子块并在当前块起始写前向指针。`MetadataReader` 跟随这些前向指针读取任意大的元数据记录。

## 本章小结

DuckDB 的表存储格式体现了一个核心设计模式：**分层延迟**。

| 层 | 延迟什么 | 何时触发 |
|----|----------|----------|
| RowGroup | 列数据加载 | 首次访问列时 |
| ColumnData | 段解压 | 扫描时 |
| ColumnSegment | 块从磁盘读入 | Pin 时 |

与 Parquet 的对比：Parquet 是文件格式，有固定的 RowGroup 大小和列块布局。DuckDB 是数据库存储格式，支持原地更新、MVCC、动态压缩选择。但两者共享"列式存储 + Zone Map + 行组"的核心架构——DuckDB 的存储格式可以视为"可更新的 Parquet"。

与 ClickHouse 的对比：ClickHouse 的 MergeTree 使用更粗粒度的 Part（每个 INSERT 创建一个 Part），后台合并 Part。DuckDB 的 RowGroup 是固定的 122,880 行，不需要后台合并——但这意味着 DuckDB 不适合高频率小 INSERT 的场景（适合批量追加）。
