# Chapter 2: 核心数据结构 — 列式内存模型

## 2.1 IColumn：COW 列抽象

### 源码导航

| 文件 | 作用 |
|------|------|
| `src/Columns/IColumn.h` | 列基类接口定义，~300 行 |
| `src/Columns/IColumn.cpp` | 基类默认实现 |
| `src/Columns/ColumnVector.h` | 数值列模板实现 |
| `src/Columns/ColumnString.h` | 字符串列（offset 数组 + 数据块） |
| `src/Columns/ColumnArray.h` | 数组列（offset + 嵌套列） |
| `src/Columns/ColumnNullable.h` | Nullable 列（null bitmap + 嵌套列） |
| `src/Columns/ColumnLowCardinality.h` | 低基数列（字典编码） |
| `src/Columns/COW.h` | Copy-on-Write 智能指针框架 |
| `src/Common/PODArray.h` | 高性能 POD 数组（PaddedPODArray） |

### COW 框架：列的根本性质

IColumn 继承自 `COW<IColumn>`（`src/Columns/IColumn.h:98` `class IColumn : public COW<IColumn>`）。COW 是 Copy-on-Write 的缩写，这是 ClickHouse 列操作性能的核心保证：

```cpp
// src/Common/COW.h — 简化语义
template <typename T>
class COW
{
public:
    using Ptr = intrusive_ptr<const T>;        // 不可变共享指针
    using MutablePtr = intrusive_ptr<T>;        // 可变独占指针

    // 获取可变引用：如果引用计数 > 1，先深拷贝
    static MutablePtr mutate(Ptr & ptr);
    static MutablePtr mutate(Ptr && ptr);
};
```

这意味着：
- 多个 `Block` 可以共享同一个 `IColumn` 而不发生拷贝
- 当需要修改列时，`mutate()` 自动检测引用计数，仅在共享时触发深拷贝
- 单引用场景完全零拷贝

```cpp
// 典型用法模式
ColumnPtr src = someColumn;
MutableColumnPtr modified = IColumn::mutate(std::move(src));
// 如果 src 的引用计数 == 1，则 modified 直接复用原内存
modified->insert(42);  // 直接修改
```

> **第一性原理**：列式存储的 COW 比行式存储的 COW 收益更大。在行式模型中，对一行中任何列的修改都需要复制整行；列式模型中，修改一列只触及一列。这意味着 ClickHouse 的表达式中，`SELECT a+1, b, c FROM t` 只需要拷贝 `a` 列的内存——`b` 和 `c` 的 `ColumnPtr` 只是引用计数 +1。

### IColumn 核心接口

```cpp
// src/Columns/IColumn.h:98-219 — 核心方法精选
class IColumn : public COW<IColumn>
{
public:
    virtual size_t size() const = 0;              // 行数
    virtual Field operator[](size_t n) const = 0; // 第 n 个值（慢路径）
    virtual StringRef getDataAt(size_t n) const = 0; // 第 n 个值（快路径）
    virtual UInt64 get64(size_t n) const;          // 数值快速获取

    // 插入
    virtual void insert(const Field & x) = 0;
    virtual void insertFrom(const IColumn & src, size_t n) = 0;
    virtual void insertRangeFrom(const IColumn & src, size_t start, size_t length) = 0;
    virtual void insertDefault() = 0;
    virtual void insertManyDefaults(size_t length) = 0;

    // 过滤（最频繁的操作之一）
    virtual void filter(const Filter & filt, ssize_t result_size_hint) = 0;
    virtual ColumnPtr compress() const = 0;

    // 比较
    virtual int compareAt(size_t n, size_t m, const IColumn & rhs, int nan_direction_hint) const = 0;

    // 内存
    virtual size_t byteSize() const = 0;
    virtual size_t allocatedBytes() const = 0;

    // 嵌套列支持
    virtual bool hasDynamicStructure() const = 0;
    virtual void forEachSubcolumn(ColumnCallback callback) const;
    virtual void forEachMutableSubcolumn(MutableColumnCallback callback);
};
```

**`Filter` 操作的性能秘密**：

```cpp
// src/Columns/ColumnVector.h — ColumnVector::filter 简化实现
void filter(const Filter & filt, ssize_t result_size_hint) override
{
    const UInt8 * filt_pos = filt.data();
    const UInt8 * filt_end = filt_pos + size;
    const T * data_pos = data.data();

    if (result_size_hint < 0)
    {
        // 默认路径：使用 SIMD 加速的 prefix-sum 计算结果大小
        result_size_hint = countBytesInFilter(filt);
    }

    // 如果过滤前后大小相同，无需操作
    if (result_size_hint == size) return;

    if (result_size_hint == 0) { data.clear(); return; }

    // 使用 x86 SSE4.2 / AVX2 指令加速过滤
    // __m128i / __m256i 一次处理 16/32 行的 mask
    size_t result_size_hint_32 = result_size_hint;
    data.resize_fill(result_size_hint_32);

    // SIMD 实现：
    // 1. 计算每个 1 的 prefix sum（偏移量）
    // 2. 按偏移量 scatter 写入
}
```

> **侧边栏 · 与 Spark 对比**：Spark 的 ColumnVector 使用 Apache Arrow 格式，过滤操作通常返回新的 ColumnVector（分配新数组）。ClickHouse 的 `filter` 方法直接原地修改（如果 `mutate()` 提供了独占所有权），减少了内存分配次数。在 OLAP 场景的百万次过滤操作中，这个差异累积明显。

---

## 2.2 列族谱：核心列类型

### ColumnVector<T> — 数值列

`src/Columns/ColumnVector.h` — ClickHouse 使用 **显式模板实例化**，不支持运行时扩展的数值类型：

```cpp
// src/Columns/ColumnVector.h:365-380
extern template class ColumnVector<UInt8>;
extern template class ColumnVector<UInt16>;
extern template class ColumnVector<UInt32>;
extern template class ColumnVector<UInt64>;
extern template class ColumnVector<Int8>;
// ... 共 18 种类型，从 8 bit 到 256 bit
extern template class ColumnVector<Float32>;
extern template class ColumnVector<Float64>;
extern template class ColumnVector<BFloat16>;
extern template class ColumnVector<UUID>;
```

底层存储使用 `PaddedPODArray`（`src/Common/PODArray.h`），一个为 SIMD 对齐而设计的动态数组：

```cpp
// PaddedPODArray 的关键特性
template <typename T>
class PaddedPODArray
{
    // 分配时自动对齐到 SIMD 边界（通常 64 字节）
    // 尾部预留 padding 防止 SIMD load/store 越界
    // 内存使用 JeMalloc 进行分配跟踪

    T * c_start;   // 分配起始
    T * c_end;     // 已使用结束
    T * c_end_of_storage; // 分配容量结束
};
```

**数值列的 compact 性**：`ColumnVector<UInt64>` 存储 1 亿行只需要 800MB（纯数据，无 overhead）。这是列式存储对比行式存储的根本优势——每个值不需要存储 length/tag/offset。

### ColumnString — 字符串列

`src/Columns/ColumnString.h` — 采用经典的"offset 数组 + 数据块"结构：

```
ColumnString:
  offsets:  [0, 5, 12, 12, 20, ...]    ← UInt64 数组，每个值是前缀长度
  chars:    "helloClickHouseworld..."   ← UInt8 数组，所有字符串拼在一起

// 第 i 个字符串的字节：
//   chars.data() + offsets[i-1] 到 chars.data() + offsets[i]
//   长度 = offsets[i] - offsets[i-1]
```

关键优化：
- **变长字符串连续存储**：所有字符串数据在一个连续 `chars` 数组中，有利于 CPU 缓存预取
- **批量获取**：通过 `getDataAt(n)` 返回 `StringRef{chars+offsets[n-1], offsets[n]-offsets[n-1]}`，零拷贝

### ColumnArray — 数组列

`src/Columns/ColumnArray.h` — 与 ColumnString 同构的 offset + data 模式：

```
ColumnArray:
  offsets: [0, 3, 5, 5, 9, ...]   ← 每个数组的元素数前缀和
  data:    ColumnX                 ← 嵌套列，存储展平的元素

// 第 i 个数组 = data[offsets[i-1] : offsets[i]]
```

这种设计的美妙之处：嵌套列可以是任何类型，包括 `ColumnArray`（多维数组通过嵌套递归实现）。

### ColumnNullable — NULL 支持

`src/Columns/ColumnNullable.h` — **NULL 不是 bit flag 内联在值中，而是独立列 + 嵌套列**：

```
ColumnNullable:
  null_map: [0,0,1,0,1,...]       ← UInt8 数组，1=null
  nested:   ColumnX               ← 数据列（non-null 值有效，null 位置可能是垃圾）
```

关键接口：
```cpp
class ColumnNullable : public COWHelper<IColumn, ColumnNullable>
{
    WrappedPtr nested_column;
    NullMap null_map;
    // 对非 null 的值才调用 nested_column 的实际操作
};
```

**为什么不在值内嵌入 null flag？** 三个原因：
1. 保持数值列的紧凑性（不需要为 null flag 调整对齐）
2. null bitmap 可以独立加速（popcount / SIMD 过滤）
3. `ColumnNullable(ColumnNullable(X))` 嵌套是幂等的——外层 null 覆盖内层

### ColumnLowCardinality — 字典编码

`src/Columns/ColumnLowCardinality.h` — 类似 Arrow 的 Dictionary Encoding：

```
ColumnLowCardinality:
  dictionary:  UniqueColumn     ← "apple", "banana", "cherry", ...
  positions:   [0,2,1,0,0,2,...] ← UInt8/16/32/64（按基数自适应宽度）
  index:       ReverseIndex     ← 可选的逆向索引加速

// 第 i 个值 = dictionary[positions[i]]
```

关键设计：
- **自适应宽度**：positions 数组根据字典大小自动选择 UInt8 → UInt16 → UInt32 → UInt64
- **临时展开**：`convertToFullColumnIfLowCardinality()` 在需要时展开为普通列
- **共享字典**：两个 `ColumnLowCardinality` 可能共享同一个字典（COW 机制）

```cpp
// 典型的条件路径：如果基数列已经展开，直接使用展开结果
Ptr convertToFullColumnIfLowCardinality() const override
{
    if (!full_state) return getPtr(); // 已经是完整列
    return full_state;                // 已缓存展开结果
}
```

---

## 2.3 DataType：类型系统

### DataType vs IColumn 的关系

```
IDataType = 逻辑类型（编译时/DDL 层）
IColumn   = 物理存储（运行时/内存层）

DataTypeString  →  ColumnString
DataTypeArray   →  ColumnArray(嵌套DataType的Column)
DataTypeNullable → ColumnNullable(嵌套DataType的Column)

// 但并非一一对应！一个 DataType 可能对应多个 IColumn 形式：
DataTypeLowCardinality(String) → ColumnLowCardinality(ColumnString)
                                  或 ColumnString（展开后）
```

### IDataType 核心接口

`src/DataTypes/IDataType.h:65` `class IDataType` — DataType 不仅是类型描述，更是 **工厂**：

```cpp
class IDataType
{
public:
    virtual const char * getFamilyName() const = 0;
    virtual TypeIndex getTypeId() const = 0;

    // 工厂方法：创建对应列
    virtual MutableColumnPtr createColumn() const = 0;
    virtual MutableColumnPtr createColumn(const ISerialization & serialization) const = 0;

    // 序列化：DataType 决定 Serialization 策略
    virtual SerializationPtr getDefaultSerialization() const = 0;
    virtual SerializationPtr getSerialization(const SerializationInfo & info) const;

    // 泛型操作（通过 callOnTypeIndex 分发）
    // ...
};
```

**关键分离**：`IDataType` ↔ `ISerialization`

ClickHouse 将"类型"和"序列化方式"分离为两个独立层级：

```
DataTypeString
  └── 默认序列化: SerializationString
        ├── serializeBinary(): 写字符串长度 + 数据
        └── deserializeBinary(): 读字符串长度 + 数据

DataTypeString
  └── 可选序列化: SerializationStringEscaped
        ├── serializeText(): 写转义字符串
        └── deserializeText(): 读转义字符串
```

同一个 `DataTypeString`，可以通过不同的 `Serialization` 子类实现不同的序列化/反序列化行为。这种分离解耦了"数据是什么"（类型）和"数据如何编码"（序列化）。

---

## 2.4 Block：列集合

### Block 的结构

`src/Core/Block.h` — Block 是 ClickHouse 数据传输和处理的原子单元：

```cpp
class Block
{
    using Container = ColumnsWithTypeAndName;
    // ColumnsWithTypeAndName = COW<IColumn>::Ptr + DataTypePtr + String(列名)
    Container data;
    BlockInfo info;
};
```

```
Block:
  columns:
    [0] { name:"user_id",    type:UInt64,   column:ColumnVector<UInt64>  }
    [1] { name:"event_name", type:String,   column:ColumnString          }
    [2] { name:"timestamp",  type:DateTime, column:ColumnVector<UInt32>  }
  info: { bucket_num:0, is_overflows:false }
```

### Block 的核心操作

```cpp
class Block
{
    // 获取列
    ColumnWithTypeAndName & getByPosition(size_t i);
    ColumnWithTypeAndName & getByName(const std::string & name);

    // 多列同时读取（高效的索引查询）
    MutableColumns getColumns() const;

    // 列级别操作
    void insert(size_t position, ColumnWithTypeAndName elem);
    void erase(size_t position);
    void erase(const std::string & name);

    // 批量获取数据
    const auto & getColumnsWithTypeAndName() const { return data; }

    // 内存估算
    size_t bytes() const;
    size_t allocatedBytes() const;
};
```

### Block 与 Pipeline 的关系

Pipeline 中 Processor 之间传递的就是 `Block`：

```
[Source] ──Block──→ [FilterTransform] ──Block──→ [AggregatingTransform] ──Block──→ [Sink]
```

每个 Processor 的 `work()` 方法消费一个 `Block`，处理后产出另一个 `Block`。Block 的大小由 `max_block_size` 控制（默认 65536 行），这个参数直接影响：
- CPU 缓存利用率（一块够大能摊薄虚函数调用，又不能大到超出 L2/L3 缓存）
- 内存峰值（流水线中多个 Block 同时在处理）
- I/O 粒度（一次从存储引擎读多少行）

---

## 2.5 PODArray：高性能数组实现

### 为什么不用 std::vector？

`src/Common/PODArray.h` — `PaddedPODArray` 替代 `std::vector` 的关键原因：

1. **SIMD 对齐**：分配时对齐到 64 字节边界（AVX-512 缓存行大小）
2. **尾部 padding**：分配额外的 `PADDING_FOR_SIMD - 1` 个元素（通常 15），确保 SIMD load/store 读取到已分配内存（避免访问违规），多读的内容会被丢弃
3. **无元素构造/析构**：POD 类型不需要逐个调用构造函数，`resize_fill` 直接用 `memset` 填充

```cpp
// 实际分配的内存布局：
// [padding | data ... | data ... | padding | extra_padding]
//   ^       ^                      ^         ^
//   对齐    有效数据开始           有效数据结束  防止SIMD尾读越界
```

4. **内存跟踪**：使用 `AllocatorWithMemoryTracking` 包装 JeMalloc，所有分配自动计入 Query/Global MemoryTracker

> **第一性原理**：数据库系统的内存分配器选择不是中性的。ClickHouse 选择 JeMalloc 而不是 glibc 的默认 malloc 有三个原因：(1) 更少的碎片化（线程缓存 + 大小分类）；(2) 可配置的性能分析（prof_active）；(3) 可预测的 OOM 行为。在 1TB 内存的机器上跑 1000 个并发查询时，内存碎片可能浪费掉 20-30% 的物理 RAM——JeMalloc 将这个数字压到了个位数。

---

## 2.6 本章小结

ClickHouse 列式内存模型的核心架构：

```
Block（列集合）
  └── ColumnWithTypeAndName（单列）
        ├── ColumnPtr → IColumn（COW 共享指针）
        │     ├── ColumnVector<T>      数值
        │     ├── ColumnString         offset + chars
        │     ├── ColumnArray          offset + nested
        │     ├── ColumnNullable       null_map + nested
        │     └── ColumnLowCardinality dict + positions
        ├── DataTypePtr → IDataType（类型描述 + 工厂）
        └── String（列名）
```

**三个关键设计原则**：
1. **COW 零拷贝**：通过 `mutate()` 实现，修改时只在多引用时拷贝，单引用原地修改
2. **类型与序列化分离**：`IDataType` 描述数据是什么，`ISerialization` 描述数据如何编码
3. **SIMD 优先内存布局**：`PaddedPODArray` 的对齐和尾部 padding 确保 SIMD 指令始终安全

**关键文件地图**：
```
src/Columns/IColumn.h             → 列抽象基类
src/Columns/ColumnVector.h        → 数值列（18 种显式实例化）
src/Columns/ColumnString.h        → 字符串列
src/Columns/ColumnArray.h         → 数组列
src/Columns/ColumnNullable.h      → Nullable 列
src/Columns/ColumnLowCardinality.h → 低基数列
src/DataTypes/IDataType.h         → 类型系统基类
src/Core/Block.h                  → 数据块
src/Common/PODArray.h             → 高性能数组
```

**下一步阅读**：在掌握了数据如何在内存中组织之后，下一步进入 Part II — SQL 编译管线，理解一条 SQL 如何从文本变成可执行的 QueryPlan。
