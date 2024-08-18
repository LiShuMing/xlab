# 第4章：Vector —— 列式计算的原子单元

> 如果说 LogicalType 回答了"存的是什么"，Vector 则回答了"怎么存的"。它是 DuckDB 执行引擎中数据流动的基本载体，也是列式计算性能的物理基础。理解 Vector 的多种形态和 Unified Format 的抽象，是理解后续所有算子实现的钥匙。

## 4.1 Vector 类的设计全貌

```cpp
// src/include/duckdb/common/types/vector.hpp:35-223
class Vector {
    friend struct ConstantVector;     // 常量向量的零拷贝视图
    friend struct DictionaryVector;   // 字典编码的稀疏向量
    friend struct FlatVector;         // 全物化的稠密向量
    friend struct ListVector;         // 嵌套列表的视图
    friend struct StringVector;       // 字符串向量（内联+溢出堆）
    friend struct FSSTVector;         // 字符串专用压缩向量
    friend struct StructVector;       // 结构体向量（多个子 Vector）
    friend struct UnionVector;        // 联合体向量（标签+值）
    friend struct SequenceVector;     // 等差数列生成器
    friend struct ArrayVector;        // 固定长度数组向量
    friend struct ShreddedVector;     // VARIANT 的 shredded 表示

    friend class DataChunk;           // DataChunk 需要直接操作 Vector 内部
    friend class VectorBuffer;        // 底层 Buffer 的创建与访问
    friend class DictionaryBuffer;
    friend class VectorStructBuffer;
    friend class VectorCacheEntry;

protected:
    LogicalType type;                      // 逻辑类型（第3章）
    mutable buffer_ptr<VectorBuffer> buffer; // 物理存储指针
};
```

Vector 的设计有两个突出的结构特点：

### 第一个特点：16 个 friend 声明

这看起来很"不 C++"。通常 friend 被视为封装破坏者，但 DuckDB 在这里是有意为之——这些 friend 不是随机访问 Vector 内部的任意类，而是 Vector 的**不同视图（View）**。它们代表了 Vector 的多种物理表示，每种视图提供不同的访问方法，但共享同一个 Vector 底层存储。

这不是封装破坏，而是一种**名义上的"多类型"**——C++ 不支持 Algebraic Data Type（和类型），无法表达"这个 Vector 可以是 Flat/Constant/Dictionary 之一"的类型约束。但他们可以通过 friend + 编译期断言（`D_ASSERT(vector.GetVectorType() == FLAT_VECTOR)`）实现运行时的安全多态。

### 第二个特点：`mutable buffer_ptr<VectorBuffer> buffer`

`buffer` 是 `mutable`——这意味着即使在 `const Vector &` 的方法中，也可以修改 buffer。这不是为了绕过 const 保护，而是为了支持一种关键操作：**延迟物化（Lazy Materialization）**。

当你调用 `const Vector &v` 的 `v.Flatten(count)` 时，DuckDB 可能需要在 const Vector 上分配新的 Flat Buffer。这是安全的——因为 Flatten 不改变逻辑内容，只改变物理布局。`mutable` 让这种"物理重排"可以在 const 语义下发生，而不需要在调用方做 const_cast。

## 4.2 多种 Vector 形态：一张统一的心智模型

DuckDB 的 Vector 有三种经典的物理形态，其余形态是这三种的变体：

```
                    Vector (LogicalType + buffer)
                      │
        ┌─────────────┼─────────────┐
        ▼             ▼             ▼
  FLAT_VECTOR   CONSTANT_VECTOR  DICTIONARY_VECTOR
  (全量数组)      (单值广播)       (字典+索引映射)
        │             │             │
        ├─ STRING     │             └── 高效重复值压缩
        ├─ STRUCT     │
        ├─ LIST       ├─ SEQUENCE (数学生成)
        ├─ ARRAY      │
        ├─ SHREDDED   │
        └─ FSST       │
```

### 2.1 FLAT_VECTOR：最平凡也最普遍

```cpp
// src/include/duckdb/common/vector/flat_vector.hpp:17-59
class StandardVectorBuffer : public VectorBuffer {
protected:
    ValidityMask validity;       // NULL bitmap
    data_ptr_t data_ptr;         // 指向实际数据
    AllocatedData allocated_data; // 拥有所有权的数据块
public:
    data_ptr_t GetData() override { return data_ptr; }
    ValidityMask &GetValidityMask() override { return validity; }
};
```

FlatVector 是一块连续内存数组。对于固定宽度类型（`INT32`, `DOUBLE` 等），`data_ptr` 指向一个 `T[2048]` 数组。索引 `i` 的值在 `((T*)data_ptr)[i]`。

**NULL 的处理：ValidityMask。**FlatVector 不使用"哨兵值"（如 `INT32_MIN` 表示 NULL），而是用一个独立的 bitmap——`ValidityMask`。`ValidityMask::RowIsValid(idx)` 返回 `idx` 行是否为非 NULL。这个 bitmap 用来做向量化高效操作的基础——可以做批量 NULL 检查（64 位一次 AND 操作），而不是逐行 if 分支。

`FlatVector::GetData<T>(vector)` 是一个带模板的静态辅助方法：
```cpp
// src/include/duckdb/common/vector/flat_vector.hpp:83-90
static inline const_data_ptr_t GetData(Vector &vector) {
    VerifyFlatOrConst(vector);  // DEBUG 下断言；RELEASE 下跳过
    return GetDataUnsafe(vector);
}
```

这里 `GetData` vs `GetDataUnsafe` 的区别是 DuckDB 性能和安全性的经典折中：`GetData` 在 DEBUG 构建中做类型和向量类型的运行时检查（O(1) 开销），`GetDataUnsafe` 跳过检查（零开销）。热路径使用 Unsafe 版本，外部 API 使用带检查的版本。

注意一个非常重要的细节：`GetData` 同时接受 `FLAT_VECTOR` 和 `CONSTANT_VECTOR`——因为常向量和全量向量在底层共享同样的 StandardVectorBuffer 结构（只是 Constant 只使用索引 0）。这个设计决策简化了大量算子的实现：它们可以通过同一套 `GetData<T>` 接口同时处理两种向量。

### 2.2 CONSTANT_VECTOR：单值的广播

```cpp
// src/include/duckdb/common/vector/constant_vector.hpp:15-89
struct ConstantVector {
    static inline bool IsNull(const Vector &vector) {
        D_ASSERT(vector.GetVectorType() == VectorType::CONSTANT_VECTOR);
        return !vector.buffer->GetValidityMask().RowIsValid(0);
    }
    static void SetNull(Vector &vector);
    static const SelectionVector *ZeroSelectionVector(idx_t count, SelectionVector &owned_sel);
    // 将 vector 设为引用 source 中 position 位置的常量向量
    static void Reference(Vector &vector, const Vector &source, idx_t position, idx_t count);
};
```

`CONSTANT_VECTOR` 的物理存储和 `FLAT_VECTOR` 完全一样——一个 `StandardVectorBuffer`。唯一的区别是 `vector_type` 字段标记为 `CONSTANT_VECTOR`，表示"只有索引 0 是有效值，该值适用于所有行"。

这意味着表达式求值 `SELECT a + 1 FROM t` 不需要构造一个充满"1"的 2048 行数组。优化器会给常量 `1` 分配一个 CONSTANT_VECTOR，只需要一个 `int32_t` 存储。在计算 `a + 1` 时，执行引擎知道：对于 CONSTANT_VECTOR 的右侧，重复使用 `((int32_t*)right_data)[0]`。

`ConstantVector::Reference` 是一个精巧的操作：它从另一个向量的某个位置提取单个值，构造一个"引用该数据的"常向量。这不需要数据拷贝——它只是将 buffer 指针指向源向量的 buffer，并设置 vector_type = CONSTANT_VECTOR。

`ZeroSelectionVector` 的返回值是一个全零的固定数组 `ZERO_VECTOR[2048]`：
```cpp
// src/include/duckdb/common/vector/constant_vector.hpp:87
static const sel_t ZERO_VECTOR[STANDARD_VECTOR_SIZE];
```
这用于将常向量的值广播到任意大小——选择向量全都是 0，意味着每次都读索引 0 的值。

### 2.3 DICTIONARY_VECTOR：延迟过滤的利器

```cpp
// src/include/duckdb/common/vector/dictionary_vector.hpp
class DictionaryBuffer : public VectorBuffer {
private:
    SelectionVector sel_vector;          // 索引映射表
    buffer_ptr<DictionaryEntry> entry;   // 字典数据（一个 Vector）
    optional_idx dictionary_size;        // 字典大小（用于缓存优化）
    string dictionary_id;                // 字典唯一标识（查找等价字典）
};

class DictionaryEntry {
    Vector data;                         // 字典中的实际数据
    optional_idx size;                   // 字典大小
    string id;                           // 字典标识
    mutex cached_hashes_lock;
    unique_ptr<Vector> cached_hashes;    // 字符串哈希缓存
};
```

DICTIONARY_VECTOR 的语义是：`value[i] = entry.data[sel_vector[i]]`。选择向量的每个元素是字典中的索引。

它在 DuckDB 中的主要用途有两个：

**用途 1：过滤结果的延迟物化。** 当执行 `SELECT * FROM t WHERE a > 10` 时，过滤产生一个 SelectionVector（满足条件的行的索引列表），这个 SelectionVector 可以被直接用于构造 DICTIONARY_VECTOR——不需要将数据从满足条件的行实际拷贝出来，只需一个索引映射。只有当下游算子真的需要 FLAT_VECTOR（比如做写入或排序）时，才调用 `Flatten` 拷贝。

**用途 2：高效表达重复值。** 对于低基数列（如性别列 `'M'/'F'`），字典编码可以将列压缩为两个值的字典 + 2048 字节的索引。DICTIONARY_VECTOR 自动支持这种优化——当从存储层读取字符串列时，如果压缩方式包含字典编码，Vector 可以直接保持为 DICTIONARY_VECTOR 形态，而不是提前解压。

**优化：CachedHashes。** 对于字符串的 DICTIONARY_VECTOR，如果字典大小合理，DictionaryEntry 可以预计算并缓存字典中每个字符串的哈希值。当这个字典向量被用于 HashJoin 或 HashAggregate 时，哈希计算可以完全跳过——直接从 `cached_hashes` 中读取。

`CanCacheHashes` 检查两个条件：
```cpp
static inline bool CanCacheHashes(const Vector &vector) {
    return DictionarySize(vector).IsValid() &&  // 字典大小已知
           CanCacheHashes(vector.GetType());     // 物理类型是 VARCHAR
}
```

### 2.4 SEQUENCE_VECTOR：不需存储的等差数列

```cpp
// src/include/duckdb/common/vector/sequence_vector.hpp
class SequenceBuffer : public VectorBuffer {
    int64_t start;       // 起始值
    int64_t increment;   // 增量
};

struct SequenceVector {
    static void GetSequence(const Vector &vector, int64_t &start, int64_t &increment);
};
```

这是 DuckDB 最巧妙的优化之一。当 `SELECT generate_series(1, 2048)` 或其他原因产生一个等差数列的 Vector 时，不需要分配 2048 × 8 = 16KB 的内存。只需要存储 `start` 和 `increment` 两个 64 位整数。值 `i` 要按公式 `start + i * increment` 计算。

但数学公式本身不是免费的——每一次值访问都要做乘法。所以 SEQUENCE_VECTOR 通常只在**暂态**存在——一旦它被参与运算（如 `seq + 100`），就会物化为 FLAT_VECTOR。

### 2.5 嵌套类型的 Vector 形态

嵌套类型（LIST, STRUCT, ARRAY, UNION）的 Flat 版本使用专门的 Buffer 子类，因为它们需要一个额外的子 Vector（child vector）：

```cpp
// src/include/duckdb/common/types/vector_buffer.hpp:30-38
enum class VectorBufferType : uint8_t {
    STANDARD_BUFFER,     // FLAT/CONSTANT, 固定大小类型——单个数组
    STRING_BUFFER,       // FLAT/CONSTANT, VARCHAR——string_t 数组 + StringHeap
    STRUCT_BUFFER,       // FLAT/CONSTANT, Struct——子 Vector 集合
    LIST_BUFFER,         // FLAT/CONSTANT, List——list_entry_t 数组 + 子 Vector
    ARRAY_BUFFER,        // FLAT/CONSTANT, Array——子 Vector
    DICTIONARY_BUFFER,   // DICTIONARY——SelectionVector + 字典子 Vector
    FSST_BUFFER,         // FSST——带有压缩额外数据的字符串
    SHREDDED_BUFFER,     // SHREDDED——shredded VARIANT
    SEQUENCE_BUFFER      // SEQUENCE——start + increment
};
```

**STRUCT Buffer 的核心实现：**
```cpp
class VectorStructBuffer : public VectorBuffer {
public:
    vector<Vector> children;  // 每个子字段一个独立 Vector
};
```

`STRUCT(a INT, b VARCHAR)` 在 Flat 模式下存储为：
- `children[0]`: INT Vector（a 列全部 2048 个值）
- `children[1]`: VARCHAR Vector（b 列全部 2048 个值）

**LIST Buffer 的核心实现：**
```cpp
class VectorListBuffer : public VectorBuffer {
public:
    Vector child;             // 扁平化的子元素 Vector
    // 父 Vector 的 data_ptr 是 list_entry_t 数组
};
```

LIST 的数据布局在第 3 章已经介绍过——list_entry_t 的数组 + 扁平化的子元素数组。这里的关键是 child Vector 是直接持有的，不是通过指针——`Vector child` 是一个完整的 Vector 对象，嵌套类型的递归遍历不需要解引用。

**STRING Vector 的特殊性：**

STRING_BUFFER 不是在第 3 章的类型系统中定义的，而是在 Buffer 层。Fixed-size string 在 Arrow 中是独立的物理类型，但 DuckDB 把它合入了 STRING_BUFFER——因为内存布局完全相同（一个 16 字节的结构 + 溢出值在 StringHeap 中）：

```cpp
// src/include/duckdb/common/types/string_type.hpp
struct string_t {
    // 如果长度 ≤ 12，数据直接存储在 data 字段（内联）
    // 如果长度 > 12，data 存储的是 StringHeap 中的指针和长度
    static constexpr idx_t INLINE_LENGTH = 12;
    static constexpr idx_t PREFIX_LENGTH = 4;     // 前缀字节数
    static constexpr idx_t PREFIX_BYTES = 4;      // 压缩后的前缀
};
```

`string_t` 的大小是 16 字节（4 字节长度 + 12 字节数据/前缀）。短字符串（≤ 12 字节）不需要堆分配——数据直接内联在 string_t 的 `data` 字节数组中。长字符串溢出到 `StringHeap`，string_t 存储指针。StringHeap 是 append-only 的（在查询执行期间不需要释放单个字符串），这消除了字符串内存管理的复杂度。

内联阈值 12 字节的选择是经过仔细计算的：大部分 SQL 字符串（整数/日期的文本表示、常见的键值、枚举名）都 ≤ 12 字节，可以完全避免堆分配。

`FlatVector::FlatStringWriter` 是为高效写入字符串而设计的辅助类：
```cpp
// 使用示例：向 Vector 写入字符串
FlatVector::FlatStringWriter writer = FlatVector::Writer<string_t>(vector, count);
writer[0] = "hello";         // 如果 ≤ 12 字节，内联；否则进 Heap
writer[1] = "world world!";  // > 12 字节 → 分配在 StringHeap
writer.SetInvalid(2);        // 标记索引 2 为 NULL
```

## 4.3 为什么需要这么多形态？—— 压缩 vs 计算效率的权衡

这是一个深层架构问题。答案是：**物理存储多样性的存在理由，恰恰是一个 Unified Format 让它们可以无差异地被消费。**

如果没有 Unified Format（见 4.5），每种 Vector 形态在表达式计算时需要不同的分支代码。有了 Unified Format，无论输入是什么形态，表达式计算都跑同一套逻辑。这是 DuckDB 向量化执行的核心前提——**在消费端用一种统一的方式对接所有生产端的异构表示**。

### 各种形态的应用场景

| 形态 | 适用场景 | 节省了什么 | 执行成本 |
|------|----------|-----------|---------|
| FLAT | 默认状态，几乎所有操作的结果 | — | 基准 |
| CONSTANT | 字面量常量、标量结果、NULL 传播 | 2048 倍的存储 | 零 |
| DICTIONARY | 过滤结果、低基数列 | 索引映射的零拷贝 | SelectionVector 间接访问 |
| SEQUENCE | generate_series, 递增 ID | 2048 倍的存储 | 按需计算 start+i*inc |
| FSST | 大字符串列的压缩读取 | 读取 I/O + 内存 | 少量符号表访问 |
| SHREDDED | VARIANT 类型的列式分解 | 异构值的列式并行化 | 按类型分派 |

## 4.4 SelectionVector：延迟物化的利器

```cpp
// src/include/duckdb/common/types/selection_vector.hpp
class SelectionVector {
    buffer_ptr<SelectionData> data;  // 实际索引数据
public:
    SelectionVector(idx_t count);     // 初始化为 0,1,2,...,count-1
    SelectionVector(sel_t *dataptr);  // 引用外部数据，不拥有所有权
    void Initialize(idx_t count);     // 重置为 0,1,2,...count-1
    void Initialize(const SelectionVector &other);  // 拷贝另一个 SV
    idx_t &operator[](idx_t index);   // 可读可写
    const idx_t operator[](idx_t index) const;  // 只读
};
```

`SelectionVector` 是 `idx_t` 的数组（`idx_t = uint64_t`），是 DuckDB 中第二频繁使用的数据结构（仅次于 Vector 本身）。它的核心作用是**通过索引重新排列数据**。

### 三个关键用途

**1. 过滤（Filter）的结果。** 
```
输入 Vector: [12, 5, 30, 8, 22]
过滤条件:   element > 10
输出 SelectionVector: [0, 2, 4]  → 指向值 12, 30, 22
```
Filter 操作不移动数据——它只输出一个 SelectionVector。这是"延迟物化"的核心：不会为满足条件的行分配新内存并拷贝值。

**2. 排序的中间状态。** 排序操作需要反复移动数据。有了 SelectionVector，可以通过交换选择向量的元素而不是实际值来避免数据移动。

**3. 字典向量的索引映射。** `DICTIONARY_VECTOR` 内部的 `sel_vector` 就是 SelectionVector，将每个输出位置映射到字典向量中的子索引。

### SelectionVector 的内存管理

`SelectionVector` 使用共享指针（`buffer_ptr<SelectionData>`）管理底层数组，使得拷贝 SelectionVector 是 O(1) 的指针赋值而非 O(n) 的数组拷贝。这在一个查询可能产生几十上百个 SelectionVector 的场景中避免内存膨胀。

## 4.5 UnifiedVectorFormat：Orri Erling 的天才抽象

```cpp
// src/include/duckdb/common/vector/unified_vector_format.hpp
struct UnifiedVectorFormat {
    const_data_ptr_t data;               // 统一的数据指针（always flat）
    optional_ptr<const ValidityMask> validity; // 统一的有效性掩码
    SelectionVector sel;                 // 统一的选择向量
};
```

这是 DuckDB 代码中出现最频繁的一个数据结构之一。它的设计者是 Orri Erling（DuckDB 的代码中 `ToUnifiedFormat` 曾经命名为 `Orrify`，作为对 Orri 的致敬）。

### Unified Format 的"咒语"

最核心的理解只需要记住三个元素和一行公式：

```
给定 UnifiedVectorFormat uvf 和索引 i：
  → 数据位置:   uvf.sel[i]        （选择向量：映射外部索引到数据内索引）
  → 数据值:     uvf.data[uvf.sel[i]]  （数据指针：连续的数组）
  → 是否 NULL:  !uvf.validity->RowIsValid(uvf.sel[i])
```

### 各形态到 Unified Format 的转换成本

| 源形态 | 转换方式 | 成本 |
|--------|---------|------|
| FLAT | `data=GetData()`, `sel=0,1,2,...`, `validity=&mask` | O(1) |
| CONSTANT | `data=GetData()`, `sel=ZERO_SEL[0,0,0,...]`, `validity=&mask` | O(1) |
| DICTIONARY | `data=child.data`, `sel=sel_vector`, `validity=&child.validity` | O(1) |
| SEQUENCE | 需要先 Flatten 为 FLAT | O(n) |
| SHREDDED | 需要先 Flatten 为 FLAT | O(n) |

前三种形态（覆盖了 99% 的执行路径）到 Unified Format 都是 O(1) 的"免费"操作——没有数据拷贝，只是指针和选择向量的重新组装。这解释了 DuckDB 向量化执行的巨大性能优势：你可以自由地选择最优的物理表示（产生时），而不需要在消费时增加复杂度。

### 递归 Unified Format for Nested Types

```cpp
// src/include/duckdb/common/vector/unified_vector_format.hpp
struct RecursiveUnifiedVectorFormat {
    UnifiedVectorFormat unified;
    vector<RecursiveUnifiedVectorFormat> children;  // 嵌套类型的子树
};
```

对于嵌套类型，`RecursiveToUnifiedFormat` 递归地转换整棵树——父向量的统一格式加上每个子向量的统一格式。这让嵌套类型的表达式计算（如 `list_extract(l, idx)` 或 `struct.a + 1`）可以和标量类型使用完全相同的统一格式抽象。

## 4.6 VectorBuffer 与内存管理

```cpp
// src/include/duckdb/common/types/vector_buffer.hpp:72-177
class VectorBuffer : public enable_shared_from_this<VectorBuffer> {
    VectorType vector_type;            // FLAT/CONSTANT/DICTIONARY/SEQUENCE/FSST
    VectorBufferType buffer_type;      // STANDARD/STRING/STRUCT/LIST/DICTIONARY/FSST/SEQUENCE
    buffer_ptr<AuxiliaryDataSet> auxiliary_data;  // 额外的生命周期管理数据

public:
    static buffer_ptr<VectorBuffer> CreateStandardVector(PhysicalType type, idx_t capacity);
    static buffer_ptr<VectorBuffer> CreateConstantVector(PhysicalType type);
    virtual data_ptr_t GetData() { return nullptr;  }
    virtual ValidityMask &GetValidityMask();  // 默认抛出异常
    virtual buffer_ptr<VectorBuffer> Flatten(const LogicalType &, const SelectionVector &, idx_t);
    virtual Value GetValue(const LogicalType &type, idx_t index);
};
```

### 双类型标记：VectorType vs VectorBufferType

Buffer 有两个类型字段，各司其职：

- `vector_type`（`VectorType`）：这个 Buffer 在 Vector 的代表什么模式——FLAT, CONSTANT, DICTIONARY 等。这是 Vector 层面的标记。
- `buffer_type`（`VectorBufferType`）：这个 Buffer 的内部数据结构是什么——STANDARD_BUFFER（单个数组）, STRING_BUFFER（字符串堆）, STRUCT_BUFFER（子 Vector 集合）, 等等。

两者是正交的。一个 `FLAT_VECTOR` 的 STRUCT 类型对应 `vector_type=FLAT, buffer_type=STRUCT`。一个 `CONSTANT_VECTOR` 的 INTEGER 对应 `vector_type=CONSTANT, buffer_type=STANDARD`。这种正交性在 Resize/Flatten/Slice 操作中至关重要——方法根据 buffer_type 决定"怎么物理拷贝"，根据 vector_type 决定"语义上怎么做"。

### AuxiliaryData：生命周期钩子

```cpp
void AddAuxiliaryData(unique_ptr<AuxiliaryDataHolder> data);
```

AuxiliaryData 不参与数据的计算解读，只是"附着"在 Buffer 上用于管理外部资源的生命周期。例如：
- `PinnedBufferHolder`：持有磁盘读取后的 pinned buffer 句柄——确保在 Vector 被销毁前，磁盘 block 的数据不会被 BufferManager 驱逐
- `AuxiliaryDataSetHolder`：持有嵌套类型中的额外数据集合的引用

这样设计的优雅之处：执行引擎不需要知道数据来自磁盘还是内存——它只与 Vector 打交道。AuxiliaryData 透明地将外部资源的生命周期绑定到 Vector 的 RFence 上。

## 4.7 Vector 构造的六种方式

```cpp
// 类型 1: 标准构造——分配 STANDARD_VECTOR_SIZE(2048) 容量的新缓冲区
Vector(LogicalType type, idx_t capacity = STANDARD_VECTOR_SIZE, ...);

// 类型 2: 外部数据引用——不拥有所有权，只读
Vector(LogicalType type, data_ptr_t dataptr);

// 类型 3: 显式 Buffer——传入已构造好的 VectorBuffer
Vector(LogicalType type, buffer_ptr<VectorBuffer> buffer);

// 类型 4: 切片构造——SelectionVector 切片另一个 Vector
Vector(const Vector &other, const SelectionVector &sel, idx_t count);

// 类型 5: 范围切片——[offset, end) 范围引用另一个 Vector
Vector(const Vector &other, idx_t offset, idx_t end);

// 类型 6: 单值构造——创建包含 Passed Value 的 CONSTANT_VECTOR
Vector(const Value &value);
```

### 切片构造的 O(1) 魔力

类型 4 和 5 不拷贝数据——只是在新的 Vector 中创建了对源 Vector 的引用（类似 `string_view` 或 `span` 的概念，但针对列式数据）。这在窗口函数的 `PARTITION BY` 和 `ORDER BY` 处理中至关重要——每几千行被切片的窗口只需要一个零拷贝的 Vector slice，而不是 2048 份独立的数据副本。

```cpp
// 示例：窗口函数中切片当前 window frame
Vector frame_data(source_vector, sel_sv, frame_count);
// frame_data 引用 source_vector 的数据，但只通过 sel_sv 中前 frame_count 个索引访问
// 没有数据拷贝发生
```

---

## 本章小结

Vector 是 DuckDB 执行引擎的原子单元，本章从四个维度深入解构了它的设计：

1. **四种主要形态**：FLAT（默认）、CONSTANT（单值广播）、DICTIONARY（字典编码）、SEQUENCE（数学生成）。每种形态都是空间和时间的折中优化，覆盖不同的使用场景。

2. **SelectionVector**：通过索引重排数据，是 Filter 延迟物化、排序、字典编码等一切"数据重排"操作的基础设施。共享指针管理使其拷贝为 O(1)。

3. **UnifiedVectorFormat（Orrify）**：让所有 Vector 形态在消费端呈现为统一的三元组：data 指针 + validity 掩码 + sel 选择向量。前三种形态的转换是 O(1) 的，为向量化执行消除了分支。

4. **VectorBuffer 层次**：双类型标记（vector_type + buffer_type）的正交设计，加上 AuxiliaryData 的生命周期管理，形成了"物理存储"和"逻辑语义"的清晰分离。

这些设计组合在一起形成了一个优雅的系统：**生产端用最优的物理形态表示数据，消费端用统一格式无差别消费**。这不仅仅是"向量化执行"——它是一套精心设计的数据布局哲学。下一章，我们将看 DataChunk 如何将多个 Vector 组合成批量计算的执行载体。
