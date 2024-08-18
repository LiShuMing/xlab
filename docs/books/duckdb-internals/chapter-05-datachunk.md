# 第5章：DataChunk —— 批量计算的执行载体

> Vector 是一列 2048 行的数据，DataChunk 是一组等长的 Vector。但把 DataChunk 仅仅理解为 `vector<Vector>` 就完全错过了它的设计精妙之处。本章从内存管理、零拷贝切片、Arrow 互通三个维度深度解析这个 DuckDB 执行引擎中最核心的数据结构。

## 5.1 DataChunk 的结构

```cpp
// src/include/duckdb/common/types/data_chunk.hpp:44-181
class DataChunk {
public:
    vector<Vector> data;        // 列向量集合（唯一公开成员）

private:
    idx_t count;                 // 当前 Chunk 中实际的行数（≤ capacity）
    idx_t capacity;              // 当前分配的容量
    idx_t initial_capacity;      // Initialize 时设置的初始容量（Reset 时恢复）
    vector<VectorCache> vector_caches;  // 每列一个缓存，支持零分配重置
};
```

DataChunk 只有五个字段。`data` 是唯一公开成员——DuckDB 的执行算子直接通过 `chunk.data[i]` 访问第 i 列的 Vector。其余三个私有字段管理生命周期和容量。

### count vs capacity vs initial_capacity

```cpp
// 示例：DataChunk 初始化后
Initialize(allocator, {INT, VARCHAR}, 2048);
// → capacity = 2048, initial_capacity = 2048, count = 2048 (所有 Vector 都是 FULL)

// 经过 Filter 后
// → data: 所有 Vector 变成 DICTIONARY_VECTOR，但 count 可能减少到 500
//   (只有 500 行满足过滤条件)
//   capacity 仍然是原始 DataChunk 的 2048

// Reset()
// → count = 0, capacity = initial_capacity = 2048
//   所有数据从 VectorCache 重新恢复为 FLAT_VECTOR
```

`count` 和 `capacity` 的分割是 DuckDB 中微妙但重要的设计。`capacity` 是内存分配的大小，`count` 是语义上"这个 Chunk 包含多少行"。当一个 Pipeline 中的算子消费 Chunk 时，它只看 `count`，不知道也不需要知道 `capacity` 是多少。但内存管理和复用（Reset）时，`capacity` 告诉系统"这块内存可以容纳多少行"。

## 5.2 从 Columnar 到 Chunk：数据布局的物理直觉

DataChunk 是行式逻辑和列式物理的桥梁：

```
逻辑视图（用户眼中的表）：
  row 0:  (23, "Alice",   "NY")
  row 1:  (45, "Bob",     "CA")
  row 2:  (31, "Charlie", "NY")

DataChunk 的物理存储（列式内存布局）：
  data[0]: Vector<INT32>     → [23, 45, 31]         ← 连续 INT 数组
  data[1]: Vector<VARCHAR>   → ["Alice", "Bob", "Charlie"]  ← string_t 数组 + Heap
  data[2]: Vector<VARCHAR>   → ["NY", "CA", "NY"]          ← string_t 数组 + Heap

访问 data[0][1] 就是读取 age 列的第 2 个值（Bob 的 age = 45）
```

这个布局意味着：
1. **读取全列的聚合操作**只需要连续的内存访问——`COUNT(age)` 就是遍历 `data[0]` 的连续 INT 数组
2. **读取单行全列的操作**（如写入或输出）则需要跳到三个不同的内存位置——每个 `data[i][row_idx]`
3. **将数据输出到 Arrow/Python/JSON 时**才需要"按行重组"，这是最后一公里的事情

### DataChunk 不是普通容器

DataChunk 禁止拷贝构造：
```cpp
DataChunk(const DataChunk &) = delete;
```

这不是技术限制，而是语义意图——DataChunk 应该被视为一种"资源"而不是"值"。拷贝一个 DataChunk 不仅涉及海量数据移动，还会产生两个独立的 VectorBuffer 副本，破坏 Vector 的零拷贝引用语义。正确的"复制"方式是通过 Copy 方法：

```cpp
// 正确的 DataChunk 复制
DataChunk result;
result.Initialize(allocator, chunk.GetTypes());
chunk.Copy(result);  // 逐列拷贝数据到 result 预先分配好的 FLAT_VECTOR 中
```

## 5.3 分阶段初始化与数据延迟分配

DataChunk 的 Initialize 有两级：

### Level 1：InitializeEmpty — 只分配类型，不分配数据

```cpp
// src/common/types/data_chunk.cpp:29-35
void DataChunk::InitializeEmpty(const vector<LogicalType> &types) {
    D_ASSERT(data.empty());
    capacity = STANDARD_VECTOR_SIZE;
    for (idx_t i = 0; i < types.size(); i++) {
        data.emplace_back(types[i], nullptr);  // 创建空 Vector，buffer = nullptr
    }
}
```

InitializeEmpty 创建的 Chunk 有类型但没有分配的存储。这些 Vector 的 buffer 指针都是 nullptr。它存在的理由：某些算子（如 `PhysicalColumnDataScan`）会产生引用外部数据的 DICTIONARY_VECTOR，不需要自己的内存分配。InitializeEmpty 让这些算子声明"我输出这些列类型"，但不浪费内存。

### Level 2：Initialize — 全量分配（带 vector_caches）

```cpp
// src/common/types/data_chunk.cpp:51-75
void DataChunk::Initialize(Allocator &allocator, const vector<LogicalType> &types,
                           const vector<bool> &initialize, idx_t capacity_p) {
    capacity = capacity_p;
    initial_capacity = capacity_p;
    for (idx_t i = 0; i < types.size(); i++) {
        auto copied_type = types[i].Copy();
        if (!initialize[i]) {
            data.emplace_back(copied_type, nullptr);
            vector_caches.emplace_back();  // 空缓存
            continue;
        }
        // 从 VectorCache 创建，预分配全量内存
        VectorCache cache(allocator, copied_type, capacity);
        data.emplace_back(cache);
        vector_caches.push_back(std::move(cache));
    }
}
```

两个细节值得深入：

#### 1. `types[i].Copy()` —— 消除多核原子竞争

```cpp
// 源码注释原文（第 59-62 行）：
// We copy the type here so we don't create another reference to the same shared_ptr<ExtraTypeInfo>
// Otherwise, threads will constantly increment/decrement the atomic ref count to the same shared_ptr
// This is necessary to avoid heavy contention on the atomic on many-core machines
```

这是一个在生产环境中发现并修复的微妙性能问题。如果所有线程的 DataChunk 共享同一个 `type_info_`（由于 `shared_ptr` 的引用计数），在多核机器上会导致严重的 cache line 争用——每个 `DataChunk::Reset()` 或析构都会触发 `shared_ptr` 的原子递减操作，所有核心竞争同一 cache line。

`Copy()` 创建了一个浅复制（shallow copy），子代 ExtraTypeInfo 仍然共享，但至少父层的 shared_ptr 引用计数页面被独立出来。这是一个针对多核 NUMA 架构的工程调优，体现了 DuckDB 在性能上的较真程度。

#### 2. `initialize` 向量 — 差异化分配

`initialize` 是一个每列的 bool 数组，控制"这一列要不要预分配内存"。默认全 true——所有列都分配。但某些算子可以选择性地只分配实际需要的列：

```cpp
// 示例：某个算子只需要从 DataChunk 读取 col_0 和 col_2，不碰 col_1
initialize = {true, false, true};
chunk.Initialize(allocator, types, initialize);
// col_1 的 Vector 被创建但 buffer = nullptr，节省 col_1 的 2048-row 内存分配
```

## 5.4 内存使用的全景：三种大小概念

DataChunk 有三种不同的"大小"指标：

### Cardinality（count）：逻辑行数

```cpp
size() → count;  // 这个 Chunk 表示了多少行数据
```

### DataSize：未压缩的数据大小

```cpp
// src/common/types/data_chunk.cpp:77-83
idx_t DataChunk::GetDataSize() const {
    idx_t total_size = 0;
    for (auto &vec : data) {
        total_size += vec.GetDataSize(count);  // 各 Vector 的纯数据字节数
    }
    return total_size;
}
```

`GetDataSize` 返回的是"如果把这些数据序列化到磁盘/网络需要多少字节"。它计算的是未压缩的数据量——VARCHAR 列是实际字符串的字面内容，不包含 string_t 的开销元数据。这在网络传输和内存监控中很有用。

### AllocationSize：实际分配的内存大小

```cpp
// src/common/types/data_chunk.cpp:85-91
idx_t DataChunk::GetAllocationSize() const {
    idx_t total_size = 0;
    for (auto &vec : data) {
        total_size += vec.GetAllocationSize();  // 各 Vector 的实际内存占用
    }
    return total_size;
}
```

`GetAllocationSize` 是程序员关心的问题——"这个 Chunk 实际占用了多少堆内存"。它包括：
- VectorBuffer 的开销（vtable 指针、validity mask 分配的字节）
- StringHeap 中已分配但未使用的空间（StringHeap 是 append-only 的，可能预留了额外容量）
- 字典向量的额外字典数据

两者通常不同：`AllocationSize` > `DataSize`，差值就是各种内部数据结构的开销。

## 5.5 VectorCache：消除分配开销的魔法

```cpp
// src/include/duckdb/common/types/vector_cache.hpp
class VectorCache {
private:
    unique_ptr<VectorCacheEntry> cache_entry;  // 内部包装类
public:
    VectorCache(Allocator &allocator, const LogicalType &type, idx_t capacity);
    void ResetFromCache(Vector &result) const;  // 零分配恢复 Vector
};
```

VectorCache 是 DataChunk 内存复用的核心机制。它的工作方式是：

```
第一次初始化：
  VectorCache → 分配 AllocatedData（一段连续堆内存）
              → Vector 引用这个已分配的数据

第一次 Reset：
  result.ResetFromCache(cache) → Vector 的 buffer 指向 cache 已分配的内存
                                → 重置 validity mask（全 valid）
                                → 重置 vector_type = FLAT_VECTOR
                                → 不调用任何 new/malloc！

第二次 Reset：
  同样的流程——只要 cache 不销毁，这块内存就一直可用
```

在 Pipeline 执行循环中，每个 Pipeline 线程处理成百上千个 Chunk：
```cpp
// Pipeline 执行线程的伪代码
for (;;) {
    auto chunk = GetNextChunk();  // 从 VectorCache 复用
    executor.Execute(chunk);      // 处理这个 Chunk
    chunk.Reset();                // 归还内存给 VectorCache（无分配）
}
// 在千次执行中只发生 INITIALIZATION 时的一次内存分配
```

这种"分配一次、重置多次"的模式在 OLAP 查询中节省了大量时间——对于扫描 1 亿行的查询，会产生约 50000 个 Chunk（1亿 / 2048），但没有 50000 次 VectorBuffer 的内存分配，只有第一次初始化的那几次。

### Reset 的细节

```cpp
// src/common/types/data_chunk.cpp:93-105
void DataChunk::Reset() {
    SetCardinality(0);
    if (data.empty() || vector_caches.empty()) {
        return;
    }
    for (idx_t i = 0; i < ColumnCount(); i++) {
        data[i].ResetFromCache(vector_caches[i]);  // 每个 Vector 归还缓存的内存
    }
    capacity = initial_capacity;
}
```

Reset 将 count 降到 0，不释放任何内存。经过一次循环回到算子时，Chunk 可以立即接收新数据。capacity 恢复到 initial_capacity——这意味着在 Append 过程中如果有 resize，Reset 后仍保持原始容量。

## 5.6 零拷贝操作：Reference、Slice、Split/Fuse

### Reference：Button Up 的指针引用

```cpp
// src/common/types/data_chunk.cpp:132-139
void DataChunk::Reference(DataChunk &chunk) {
    SetCapacity(chunk);
    SetCardinality(chunk);
    for (idx_t i = 0; i < chunk.ColumnCount(); i++) {
        data[i].Reference(chunk.data[i]);  // 每列的 Vector 引用源 Chunk 的 Vector
    }
}
```

Reference 让当前 Chunk 的每个 Vector "指向"源 Chunk 对应 Vector 的数据。这是零拷贝的——Vector 的 buffer 指针指向源 Vector 的 buffer，不分配任何新内存。但这也意味着源 Chunk 在引用 Chunk 存续期间不能被销毁。

### Slice：创建字典向量的快捷方式

```cpp
// src/common/types/data_chunk.cpp:318-336
void DataChunk::Slice(const DataChunk &other, const SelectionVector &sel,
                      idx_t count_p, idx_t col_offset) {
    D_ASSERT(other.ColumnCount() <= col_offset + ColumnCount());
    for (idx_t c = 0; c < other.ColumnCount(); c++) {
        data[col_offset + c].Slice(other.data[c], sel, count_p);
    }
    SetCardinality(count_p);
}
```

Slice 在这个 Chunk 上创建了源 Chunk 子集的字典向量。每个 `data[c]` 变成一个 `DICTIONARY_VECTOR`，通过 `sel` 选择源数据的子集。这是物理算子中"只查看部分数据但不拷贝"的标准方式。

### Split/Fuse：Chunk 的柯里化

```cpp
// src/common/types/data_chunk.cpp:173-197
void DataChunk::Split(DataChunk &other, idx_t split_idx) {
    // 将 data[split_idx] 到 data[last} 的 Vector 移动到 other
    for (idx_t col_idx = split_idx; col_idx < num_cols; col_idx++) {
        other.data.push_back(std::move(data[col_idx]));
        other.vector_caches.push_back(std::move(vector_caches[col_idx]));
    }
}

void DataChunk::Fuse(DataChunk &other) {
    // 将 other 的所有 Vector 追加到当前 Chunk
    for (idx_t col_idx = 0; col_idx < num_cols; ++col_idx) {
        data.emplace_back(std::move(other.data[col_idx]));
        vector_caches.emplace_back(std::move(other.vector_caches[col_idx]));
    }
    other.Destroy();
}
```

Split/Fuse 用于物理算子中的列重组——例如 HashJoin 的输出：左侧 3 列 + 右侧 5 列 = 8 列的结果 Chunk。Operator 可以先将左右两边的 Chunk Split，再 Fuse 组装成输出格式。全部是 O(n_columns) 的 move 操作，没有数据拷贝。

## 5.7 Arrow 桥接：DataChunk ↔ RecordBatch

DataChunk 直接支持与 Arrow RecordBatch 的转换——不是通过额外的"适配层"，而是 DuckDB 的结构本身就与 Arrow 兼容：

```cpp
// src/include/duckdb/common/types/data_chunk.hpp:12
#include "duckdb/common/arrow/arrow_wrapper.hpp"

// 转换流程（通过 Arrow 扩展）：
// DataChunk → Arrow Array → RecordBatch（导出到 Python/Pandas/Polars）
// Arrow Array → DataChunk（从 Python/Pandas/Polars 导入）
```

DuckDB 之所以能与 Arrow 无缝互转，不仅仅是技术实现，更是从一开始就设计为兼容的：

1. **列式的 `Vector` 直接对应 Arrow 的 `ChunkedArray` 片段**：每个 Vector 是一个 Arrow Array 的在 DuckDB 内部的等价物
2. **PhysicalType 枚举是 Arrow Type 系统的裁剪版**（如第 3 章所述）
3. **ValidityMask（bitmap）与 Arrow 的 NULL bitmap 完全相同格式**：LSB-packed，位 1 = valid
4. **string_t 的 12 字节内联 + 溢出设计**与 Arrow 的 StringArray 二进制兼容

实际转换在 `src/common/arrow/` 目录中实现，涉及鸭子类型转换和类型映射表。要点是：这不是"序列化-反序列化"——它是纯内存格式转换，速度快至毫秒级。

## 5.8 Appender：从行到 DataChunk 的通路

```cpp
// 通过 Appender API 插入数据
DuckDB db(":memory:");
Connection conn(db);
Appender appender(conn, "t");
appender.BeginRow();
appender.Append<int32_t>(42);
appender.Append<const char*>("hello");
appender.EndRow();
appender.Flush();  // 将行缓冲写入 DataChunk → 底层表
```

Appender 是行式写入到列式存储的翻译器。它内部维护一个 DataChunk，每行追加（`BeginRow/EndRow`）就是将单行的各列值写入对应 Vector 的对应索引位置。当行数达到 `STANDARD_VECTOR_SIZE`（2048）时，Flush 将整个 DataChunk 写入底层存储。

## 5.9 DataChunk 在 Pipeline 中的生命周期

```cpp
// Pipeline 执行循环的真实流程（简化）
// 预备阶段：算子初始化时
output_chunk.Initialize(allocator, output_types);  // 分配 2048 行 × n 列

// 执行循环（处理 1 亿行 = 约 5 万个 Chunk）
while (true) {
    // 1. 从上游管道获取数据
    auto &source = upstream_chunk;  // 可以是 DICTIONARY/FLAT/etc

    // 2. 执行算子逻辑
    AutoStartExecutor.Execute(output_chunk, source);

    // 3. 输出：对 output 取 Slice（可能不是 2048 全满）
    // 根据需要设置 count，不需要全容量

    // 4. 消费后重置
    output_chunk.Reset();  // 内存归还 VectorCache，零分配

    if (no_more_data) break;
}
```

DataChunk 在执行循环中作为"黏合剂"连接物理算子。它是 Pipeline 中的中间表示——Pipeline 的输入是一个 DataChunk，输出也是。Operator 消费输入的 Chunk，在 output Chunk 中产生结果，然后清空 input Chunk、reset output Chunk，继续下一个周期。

---

## 本章小结

DataChunk 是 DuckDB 执行引擎的"心跳"。本章从五个维度剖析它：

1. **双容量设计**（count vs capacity）：将逻辑语义和内存分配解耦，支持内存复用而不丢失信息
2. **VectorCache**：使得成百上千个 Chunk 的处理只需要初始化的那一次内存分配，后续 Reset 全部零开销
3. **零拷贝家族**：Reference、Slice、Split/Fuse——所有数据重组操作都可以通过指针和 move 实现，没有数据移动
4. **Arrow 桥接**：不是后续打补丁的"适配层"，而是从一开始就设计为格式兼容
5. **Pipeline 中的角色**：作为物理算子之间的"消息"，承载一次 Vector 的批量数据

DataChunk 的设计哲学总结：**用极少的内存操作完成极多的数据重组——让 Allocation 成为常数，让拷贝成为 O(1)**。

下一章，我们将从数据表示层进入 SQL 编译前端——Parser 如何将 SQL 文本转化为抽象语法树。
