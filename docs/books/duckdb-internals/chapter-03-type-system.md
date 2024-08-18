# 第3章：类型系统 —— 一切计算的基石

> 类型系统是数据库的第一语言。所有的 SQL 操作——比较、运算、聚合、存储——最终都建立在类型之上。不理解 DuckDB 的类型系统，就无法理解后续的 Vector、DataChunk、函数分派和表达式计算。

## 3.1 LogicalType 与 PhysicalType 的双层抽象

DuckDB 的类型系统有一个核心设计：**逻辑类型**和**物理类型**是两层不同的抽象。这类似于程序语言中"类型"与"内存布局"的关系——`VARCHAR` 是一种逻辑概念，但它在内存中实际存储为 16 字节的 `string_t` 结构。

### PhysicalType：机器的语言

```cpp
// src/include/duckdb/common/types.hpp:63-180
enum class PhysicalType : uint8_t {
    BOOL = 1,       // 1 字节 bool
    UINT8 = 2,      // uint8_t
    INT8 = 3,       // int8_t
    UINT16 = 4,     // uint16_t
    INT16 = 5,      // int16_t
    UINT32 = 6,     // uint32_t
    INT32 = 7,      // int32_t
    UINT64 = 8,     // uint64_t
    INT64 = 9,      // int64_t
    FLOAT = 11,     // float
    DOUBLE = 12,    // double
    INTERVAL = 21,  // interval_t（两个 64 位整数）
    LIST = 23,      // list_entry_t（offset + length 对）
    STRUCT = 24,    // 子 Vector 的组合
    ARRAY = 29,     // 固定大小的子 Vector 序列
    VARCHAR = 200,  // string_t（长度前缀 + 内联/溢出指针）
    UINT128 = 203,  // uhugeint_t
    INT128 = 204,   // hugeint_t
    UNKNOWN = 205,  // 用户自定义类型的占位符
    BIT = 206,      // 1 位 packed boolean
    INVALID = 255
};
```

`PhysicalType` 回答的是"内存里到底存的是什么"。执行引擎在处理 Vector 时，`switch(physical_type)` 是分派一切计算的分叉口。注意注释中大量被注释掉的 Arrow 类型（`NA`, `HALF_FLOAT`, `STRING`, `BINARY`, `DICTIONARY` 等）——DuckDB 的 `PhysicalType` 枚举是对 Apache Arrow 类型系统的**适配与裁剪**，而非盲目照搬。

其中 DuckDB 独有的扩展：
- `VARCHAR = 200`：DuckDB 自研的字符串表示，不同于 Arrow 的 `STRING` 或 `LARGE_STRING`
- `UINT128/INT128`：DuckDB 的原生 128 位整数
- `BIT = 206`：1 位 per value 的压缩 boolean，比 Arrow 的 1 字节 per bool 节省 8 倍空间

### LogicalType：SQL 世界的语言

```cpp
// src/include/duckdb/common/types.hpp:185-249
enum class LogicalTypeId : uint8_t {
    INVALID = 0,
    SQLNULL = 1,    // 常量 NULL
    UNKNOWN = 2,    // 未解析的参数类型
    ANY = 3,        // 函数的泛型参数
    UNBOUND = 4,    // 已解析但未绑定的类型（AST 阶段）
    TEMPLATE = 5,   // 函数模板占位符（绑定期间存在）
    TYPE = 6,       // 类型的类型（元编程参数）

    // 数值类型
    BOOLEAN = 10, TINYINT = 11, SMALLINT = 12, INTEGER = 13, BIGINT = 14,
    UTINYINT = 28, USMALLINT = 29, UINTEGER = 30, UBIGINT = 31,
    HUGEINT = 50, UHUGEINT = 49,
    FLOAT = 22, DOUBLE = 23,
    DECIMAL = 21,     // 精度 + 标度 → 物理存储由宽度决定

    // 时间类型
    DATE = 15, TIME = 16,
    TIMESTAMP_SEC = 17, TIMESTAMP_MS = 18, TIMESTAMP = 19,  // 微秒
    TIMESTAMP_NS = 20, TIMESTAMP_TZ = 32, TIME_TZ = 34,

    // 字符串与二进制
    VARCHAR = 25, CHAR = 24, BLOB = 26, BIT = 36,

    // 嵌套类型
    STRUCT = 100, LIST = 101, MAP = 102, UNION = 107, ARRAY = 108,

    // 扩展类型
    ENUM = 104, VARIANT = 109, UUID = 54, GEOMETRY = 60,

    // 特殊内部类型
    STRING_LITERAL = 37,   // 常量字符串（仅在绑定阶段存在）
    INTEGER_LITERAL = 38,  // 整数字面量（仅在绑定阶段存在）
    AGGREGATE_STATE = 110, // 聚合中间状态
};
```

`LogicalTypeId` 回答的是"SQL 语义上这是什么类型"。注意一些精妙的细节：

**字面量类型（`STRING_LITERAL`, `INTEGER_LITERAL`）仅在绑定阶段存在。** 它们不是"真正的"类型——绑定完成后，它们会被 `NormalizeType` 转换为具体的物理类型（`VARCHAR`, `TINYINT`/`SMALLINT`/`INTEGER`/`BIGINT` 按值范围选）。这是 DuckDB 处理"无类型常量"的方式：给未标注的字面量一个临时的、带值的逻辑类型，由 Binder 在上下文推导中确定最终的物理类型。

**`TIMESTAMP` = 微秒是第一个 timestamp 的默认精度**。4 种 timestamp 分辨率的共存（`TIMESTAMP_SEC`/`MS`/`TIMESTAMP`/`NS`）说明了 DuckDB 在"物理精准"和"SQL 优雅"之间的权衡——物理上时间戳需要明确的存储格式，但 SQL 用户不想要每次写 `TIMESTAMP_NS(3)`。

**`ENUM` 的物理类型是小整数**——`PhysicalType::UINT8`/`UINT16`/`UINT32` 自动根据枚举值数量选择最小宽度。`EnumType::GetPhysicalType` 在创建 ENUM 时计算：
- 值数 ≤ 256 → `UINT8`
- 值数 ≤ 65536 → `UINT16`
- 其余 → `UINT32`

### LogicalType：两层的粘合剂

```cpp
// src/include/duckdb/common/types.hpp:256-388
struct LogicalType {
private:
    LogicalTypeId id_;
    PhysicalType physical_type_;
    shared_ptr<ExtraTypeInfo> type_info_;

public:
    LogicalType(LogicalTypeId id);  // 简单类型：仅需 id
    LogicalType(LogicalTypeId id, shared_ptr<ExtraTypeInfo> type_info);  // 复杂类型：带额外信息

    inline LogicalTypeId id() const { return id_; }
    inline PhysicalType InternalType() const { return physical_type_; }
    inline const optional_ptr<ExtraTypeInfo> AuxInfo() const { return type_info_.get(); }
};
```

`LogicalType` 是一个 24 字节的值类型（value type）——三个成员均可平凡拷贝。关键在于 `type_info_` 是一个**共享指针**：当你拷贝一个 `LogicalType(LIST(INTEGER))` 时，`type_info_` 指向同一个 `ListTypeInfo` 对象。这对性能很重要——Binder 期间会产生海量的类型副本，共享 `ExtraTypeInfo` 避免了深拷贝嵌套类型树的巨大开销。

但这也带来一个微妙的问题：如果你修改了 `type_info_` 指向的内容，所有持有同类型副本的对象都会受影响。这就是 `DeepCopy()` 存在的理由——当你确实需要独立的类型副本时。大多数场景拷贝共享同一 `type_info_` 就够了，因为类型的属性（列名、精度）是稳定不变的。

### LogicalTypeId → PhysicalType 的映射

```cpp
// src/common/types/type_manager.cpp
// LogicalType::GetInternalType() 的核心逻辑：
// LogicalTypeId → PhysicalType 的映射是有损的
// 例如：TINYINT→INT8, SMALLINT→INT16, INTEGER→INT32, BIGINT→INT64
//       UTINYINT→UINT8, USMALLINT→UINT16, UINTEGER→UINT32, UBIGINT→UINT64
//       DATE→INT32       (32位整数存储自1970-01-01的天数)
//       TIME→INT32       (32位整数存储自零点起的微秒数)
//       TIMESTAMP→INT64  (64位整数存储自1970-01-01的微秒数)
//       HUGEINT→INT128, UHUGEINT→UINT128
//       VARCHAR→VARCHAR, BLOB→VARCHAR (字符串和二进制共用物理类型!!)
//       STRUCT→STRUCT, LIST→LIST, MAP→LIST (Map 物理上是 List)
//       DECIMAL→INT16/INT32/INT64/INT128 (根据宽度选择)
//       ENUM→UINT8/UINT16/UINT32 (根据值数选择)
```

值得特别关注的点：

**BLOB 和 VARCHAR 共用 `PhysicalType::VARCHAR`。** 这意味着在物理存储层，二进制数据和文本数据以完全相同的方式管理——都是 `string_t` 结构的前缀+内联/溢出。区别仅在于逻辑语义：字符串有排序规则（collation），二进制没有。

**MAP 的物理类型是 `LIST`。** DuckDB 把 MAP 表示为 `LIST(STRUCT(key, value))`——一组键值对的列表，物理上与 LIST 完全一样。这不是"偷懒"，而是对 MAP 语义的精确定性：有序的键值对集合，而不是无序的字典（后者是 `MapType` 的独立逻辑类型）。当你写 `SELECT map['key'] FROM t` 时，Planner 生成的是对 LIST 中的 STRUCT 成员进行过滤的表达式树，而不是"字典查找"。

## 3.2 嵌套类型：Columnar 如何表达嵌套

DuckDB 的嵌套类型设计遵循一个核心原则：**嵌套不引入任何新的物理表示**。一切都是 Vector 的组合。

### LIST：两级存储

```cpp
// src/include/duckdb/common/types.hpp:41-54
struct list_entry_t {
    uint64_t offset;  // 在子 Vector 中的起始位置
    uint64_t length;  // 元素个数
};
```

LIST 的存储方式不是"每个值一个独立的小数组"，而是一个扁平化的数组+偏移对：

```
逻辑值:      [1,2,3]     [4,5]       [6]
物理表示:
  list_entry: {0,3}       {3,2}       {5,1}
  child_data: [1, 2, 3,  4,  5,  6]
```

这带来两个优势：
1. **随机访问是 O(1)**：通过 `child_data[list_entry[i].offset + k]` 直接获取元素
2. **向量化操作无分支**：对整列的所有元素做操作（如 `list_sum`），只需要遍历 child vector，而 entry 向量指示边界

在 `src/common/types/list_segment.cpp` 中，LinkedList 结构用于高效地追加构建 LIST 列——每次只需要往 child vector 追加新元素，再更新最后一个 entry 的 length 或创建新 entry。

### STRUCT：多列的组合

```cpp
// src/include/duckdb/common/types.hpp:506-513
struct StructType {
    static const child_list_t<LogicalType> &GetChildTypes(const LogicalType &type);
    static const LogicalType &GetChildType(const LogicalType &type, idx_t index);
    static const string &GetChildName(const LogicalType &type, idx_t index);
    static idx_t GetChildCount(const LogicalType &type);
};
```

STRUCT 在 DuckDB 中的物理存储实际上是**多个并列的子 Vector**——`VectorStructBuffer` 持有一个 `vector<Vector>`：

```cpp
// src/include/duckdb/common/types/vector_buffer.hpp
class VectorStructBuffer : public VectorBuffer {
public:
    vector<Vector> children;  // 每个子字段一个独立的列式 Vector
};
```

这意味着 `STRUCT(a INT, b VARCHAR)` 的物理存储是：
- `children[0]`: INT32 Vector（a 列的全部值）
- `children[1]`: VARCHAR Vector（b 列的全部值）

这不同于 Arrow 的结构体（将字段值交织存放），也不同于 Parquet 的 shredding（分列存储）。DuckDB 的方式最大化利用了列式内存的局部性——对 `struct.a` 的批量操作等同于对一整列的 INT32 Vector 操作。

**STRUCT 实现的演进：** 源码中有一个重要转变——`AGGREGATE_STATE` 类型从最初的 `LogicalTypeId::LEGACY_AGGREGATE_STATE` 演进到了新的基于 STRUCT 的版本 (`LogicalTypeId::AGGREGATE_STATE = 110`)。旧版的聚合状态是一个不透明的 blob，新版本将聚合中间状态暴露为命名字段的 STRUCT。这让聚合状态的序列化和调试变得可行，不会影响性能因为每个聚合函数已经在自己的内部数据结构中管理状态。

### MAP：语法糖

```cpp
// src/include/duckdb/common/types.hpp:441-442
static LogicalType MAP(const LogicalType &child);    // 简单 MAP
static LogicalType MAP(LogicalType key, LogicalType value);  // 指定 key/value 类型
```

MAP 是通过 `ExtraTypeInfo` 中的 `MapTypeInfo` 来区分于普通 LIST 的。逻辑上 `MAP(INT, VARCHAR)` 等价于 `LIST(STRUCT(key INT, value VARCHAR))`，但 MAP 有自己的类型 ID 和独立的函数重载（如 `map_extract`）。

这种"逻辑独特、物理复用"的做法是 DuckDB 类型系统的通用模式：ARRAY 物理上使用 `PhysicalType::ARRAY = 29`，但内部结构嵌套 child vector。

### UNION：异构列

```cpp
// src/include/duckdb/common/types.hpp:520-526
struct UnionType {
    static const idx_t MAX_UNION_MEMBERS = 256;
    static idx_t GetMemberCount(const LogicalType &type);
    static const LogicalType &GetMemberType(const LogicalType &type, idx_t index);
    static const string &GetMemberName(const LogicalType &type, idx_t index);
};
```

DuckDB 的 UNION 类似于 C 中的 tagged union：每个值有标签（哪个成员类型）+ 值本身。在物理上，UNION 由一个 tag Vector (`union_tag_t = uint8_t`) 加上成员 Vector 的组合构成。最多 256 个成员——`uint8_t` 标签的自然上限。

## 3.3 大整数：128 位运算的内核

### hugeint_t 的数据结构

```cpp
// src/include/duckdb/common/types/hugeint.hpp
struct hugeint_t {
    uint64_t upper;  // 高 64 位
    int64_t lower;   // 低 64 位

    string ToString() const;  // 转字符串：需要除法+取模循环（非常慢）
};
```

128 位整数在 `DECIMAL(38, s)` 和 `HUGEINT` 类型中使用。它的运算全部手写——没有依赖编译器内置的 `__int128`（出于可移植性）：

```cpp
// src/common/types/hugeint.cpp
// 加法的核心实现：
static hugeint_t Add(hugeint_t lhs, hugeint_t rhs) {
    uint64_t low = (uint64_t)lhs.lower + (uint64_t)rhs.lower;
    bool overflow = low < (uint64_t)lhs.lower;  // 无符号加法溢出检测
    int64_t high = lhs.upper + rhs.upper + (overflow ? 1 : 0);
    return {static_cast<uint64_t>(high), static_cast<int64_t>(low)};
}

// 乘法用分治算法：
// upper = a_hi * b_lo + a_lo * b_hi + carry
// lower = a_lo * b_lo
// 需要处理符号反转（负数的补码）
```

### Decimal：精度驱动的物理选择

```cpp
// src/include/duckdb/common/types.hpp:432,475-478
static LogicalType DECIMAL(uint8_t width, uint8_t scale);
struct DecimalType {
    static uint8_t GetWidth(const LogicalType &type);
    static uint8_t GetScale(const LogicalType &type);
    static uint8_t MaxWidth();  // 返回 38
};
```

DECIMAL 是 DuckDB 中唯一一个"物理类型由宽度决定"的逻辑类型：

```cpp
// src/common/types/type_manager.cpp
// DECIMAL 的物理类型映射：
// width <= 4  → PhysicalType::INT16  (smallint)
// width <= 9  → PhysicalType::INT32  (integer)
// width <= 18 → PhysicalType::INT64  (bigint)
// width <= 38 → PhysicalType::INT128 (hugeint)
```

这里的设计是**精确但不浪费**——不会因为定义了 `DECIMAL(5,2)` 就分配 16 字节。

DECIMAL 运算的核心都在 `src/common/types/decimal.cpp` 中——加减法需要先对齐 scale，乘除后需要 re-scale。关键的性能优化是运算前检测溢出——提前判断结果是否需要升级到更宽的物理类型，而不是盲目运算后检查。

## 3.4 ENUM：自动压缩的字典编码

```cpp
// src/include/duckdb/common/types.hpp:444
static LogicalType ENUM(Vector &ordered_data, idx_t size);
```

ENUM 类型在创建时接受一个包含所有合法枚举值的 Vector。DuckDB 自动选择最小物理类型：

```cpp
// src/common/types/type_manager.cpp
PhysicalType EnumType::GetPhysicalType(const LogicalType &type) {
    auto size = EnumType::GetSize(type);
    if (size <= NumericLimits<uint8_t>::Maximum())   return PhysicalType::UINT8;
    if (size <= NumericLimits<uint16_t>::Maximum())  return PhysicalType::UINT16;
    return PhysicalType::UINT32;
}
```

枚举值在内部用小整数表示，但 SQL 层面操作时自动在整数和字符串之间转换。`EnumType::GetValuesInsertOrder` 返回插入顺序的字符串 Vector——这使得 `ORDER BY enum_col` 可以按定义顺序而非字典序排序。

一个值得注意的实现细节：ENUM 的 `type_info_` 中存储的是**插入顺序的字符串 Vector**，而不是按字典排序的。这意味着 `ENUM('large', 'medium', 'small')` 和 `ENUM('small', 'medium', 'large')` 是两个不同的类型，尽管字符串集合相同。在 `UNION ALL` 或类型推导中合并两个不同顺序的 ENUM 时，会抛出类型不兼容错误。

## 3.5 VARIANT：半结构化的动态类型

DuckDB 在 1.5.x 系列中引入了 VARIANT 类型——在列式存储中存储异构半结构化数据。VARIANT 的实现是列式引擎处理"非列式数据"的一次重要实验：

```cpp
// src/include/duckdb/common/types/variant_value.hpp
// src/common/types/variant/
// 核心结构：VariantValue 可以存储任意 LogicalType 的值
// 在列中，每个 VARIANT 单元包含：类型标签 + 值（内联或指针）
```

与 ClickHouse 的 `Variant` 或 BigQuery 的 `JSON` 类型的区别在于，DuckDB 的 VARIANT **可以无损存储任何 DuckDB 类型**——不是先转 JSON 再存，而是直接在 VARIANT 的内部 union 中持有原生值。`VariantVisitor` 模式允许在不知道具体类型的情况下安全地操作 VARIANT 列。

## 3.6 类型系统的"助手类型"群

DuckDB 的类型系统中还有几种"不是给人用"的特殊类型，它们是 Planner 和 Binder 内部的"元类型"：

### 字面量类型

```cpp
// src/include/duckdb/common/types.hpp:227-228
STRING_LITERAL = 37,   // SELECT 'hello' 中的 'hello'（绑定前）
INTEGER_LITERAL = 38,  // SELECT 42 中的 42（绑定前）
```

当 Parser 遇到一个没有显式类型标注的字面量时，它不会猜测 "42 是 INTEGER 还是 BIGINT"，而是分配 `LogicalTypeId::INTEGER_LITERAL`，并将值 42 存入 `type_info_`。Binder 在推导上下文后，调用 `IntegerLiteral::FitsInType` 检查值是否适合目标类型——如果上下文期待 `TINYINT` 但值是 42且 `TINYINT_MAX = 127`，那就转成 `TINYINT`。这是 DuckDB 实现"隐式窄化"的方式。

### ANY 和 TEMPLATE

```cpp
// src/include/duckdb/common/types.hpp:189,197
ANY = 3,      // 函数参数：接受任何类型，不做类型推导
TEMPLATE = 5, // 函数参数：接受任何类型，但所有同名 TEMPLATE 实例化为同一类型
```

`ANY` 和 `TEMPLATE` 是函数重载解析的关键。`list_contains(list, element)` 的签名中，`element` 参数可以用 `TEMPLATE`——Binder 需要同时推导 `list` 的元素类型和 `element` 的类型，将它们绑定为同一类型。而 `printf(format, ...)` 的 `format` 参数是 `ANY`，不需要与任何其他参数类型关联。

### UNBOUND

```cpp
// src/include/duckdb/common/types.hpp:190,456
UNBOUND = 4,
static LogicalType UNBOUND(unique_ptr<ParsedExpression> expr);
```

当 Parser 遇到 `SELECT CAST(x AS INT)` 时，`INT` 首先被解析为 `UNBOUND(ParsedExpression)`。Binder 尝试通过 `UnboundType::TryDefaultBind` 解析它——先查内置类型表，再查 Catalog 中的自定义类型。如果成功，替换为具体的 `LogicalType`；如果失败，标记为"无法解析的类型"并以错误形式保持，直到 SQL 执行时抛出异常并显示清晰的错误消息。

### AGGREGATE_STATE

```cpp
// src/include/duckdb/common/types.hpp:110,438-439,589-601
AGGREGATE_STATE = 110,
static LogicalType AGGREGATE_STATE(aggregate_state_t state_type,
                                    child_list_t<LogicalType> struct_child_types);
struct aggregate_state_t {
    string function_name;
    LogicalType return_type;
    vector<LogicalType> bound_argument_types;
};
```

`AGGREGATE_STATE` 是用户自定义聚合函数（UDAF）的核心——它把聚合函数的名称、返回类型和参数类型编码为一个可序列化的类型。在并行聚合中，多个线程各自积累 `AGGREGATE_STATE` 中间结果，由 Sink 算子将它们 COMBINE。新的基于 STRUCT 的实现允许在每个聚合函数内部自由定义中间状态的结构，而不需要系统层知道任何细节。

## 3.7 类型推导与隐式转换

DuckDB 的类型推导发生在两个层面：

### 1. 字面量类型推导

```cpp
// 示例：SELECT 42 + 0.5
// Stage: Binder 发现 42 (INTEGER_LITERAL), 0.5 (DECIMAL(2,1))
//        调用 LogicalType::ForceMaxLogicalType
//        → INTEGER_LITERAL 无法直接参与运算
//        → NormalizeType(INTEGER_LITERAL(42)) → TINYINT (42 ≤ 127)
//        → ForceMaxLogicalType(TINYINT, DECIMAL(2,1)) → DECIMAL(?,?)
//        → 最终表达式类型: Cast(TINYINT→DECIMAL) + DECIMAL
```

### 2. UNION/函数参数的类型推导

```cpp
// src/include/duckdb/common/types.hpp:359-363
static LogicalType MaxLogicalType(ClientContext &context,
                                   const LogicalType &left,
                                   const LogicalType &right);
static bool TryGetMaxLogicalType(ClientContext &context,
                                  const LogicalType &left,
                                  const LogicalType &right,
                                  LogicalType &result);
```

`MaxLogicalType` 是一张类型优先级表：`TINYINT → SMALLINT → INTEGER → BIGINT → HUGEINT → DOUBLE`（跳过 FLOAT，因为 FLOAT 精度太低）。对于 VARCHAR 和 BLOB，"max" 结果通常是 VARCHAR——这是合理的默认，因为大多数字符串操作期待文本结果。

谨慎的窄化由 `ForceMaxLogicalType` 保证：它不抛异常，而是返回尽可能合理的类型，最坏情况退化为其中一个输入类型。

## 3.8 Value：单个值的容器

```cpp
// src/include/duckdb/common/types/value.hpp:32-80
class Value {
    LogicalType type_;
    bool is_null;
    union Val {
        bool boolean;
        int8_t tinyint; int16_t smallint; int32_t integer; int64_t bigint;
        uint8_t utinyint; uint16_t usmallint; uint32_t uinteger; uint64_t ubigint;
        hugeint_t hugeint; uhugeint_t uhugeint;
        float float_; double double_;
        date_t date_; dtime_t time_; timestamp_t timestamp_;
        interval_t interval_;
        string_t str;
        list_entry_t list_entry;
        // 指针类型：用于嵌套类型，指向子数据
        vector<Value> *list_value;
    } value_;
    unique_ptr<ExtraValueInfo> value_info_;  // 用于嵌套结构的子信息
};
```

`Value` 是 DuckDB 中唯一一个同时持有类型标签和值的类型——它是 SQL 常量在内存中的完整表示。`Value` 的大小是固定的（type + null flag + union），嵌套类型通过堆分配的 `value_info_` 存储子结构。

`Value` 在以下场景中使用：
- 常量折叠：`SELECT 2+3` → 表达式的优化结果是一个 `Value(5)`
- 函数默认参数：`CREATE FUNCTION f(x INT DEFAULT 0)`
- 配置值：`SET memory_limit='4GB'`
- 字面量表示的绑定阶段(Binder 中)

Efficient 的关键在于：`Value` 不存储 `vector<Value>` 用于列表——它用 `list_entry_t` 指代，实际的子元素列表存储在 `ExtraValueInfo` 中。这让单元素值的 Value 保持紧凑。

---

## 本章小结

本章深入探索了 DuckDB 类型系统的三层结构：

1. **PhysicalType**（机器语言）：定义内存布局——BOOL/UINT8/INT32/VARCHAR/INT128 等 16 种。这是执行引擎中 `switch` 分派的维度。

2. **LogicalTypeId**（SQL 语言）：定义语义——TINYINT/DECIMAL/TIMESTAMP_MS/STRUCT/LIST/MAP 等 50+ 种。包含纯绑定阶段才存在的"字面量类型"和"模板类型"。

3. **LogicalType**（粘合剂）：通过 `ExtraTypeInfo` 共享指针将 LogicalTypeId 与类型元数据（嵌套结构、精度、枚举值）连接。

以及关键的类型家族：
- **嵌套类型**（LIST/STRUCT/MAP/UNION）：物理复用 Vector 组合，不引入新的存储原语
- **128 位整数**（HUGEINT/UHUGEINT）：手写可移植运算，支撑 DECIMAL(38,s)
- **VARIANT**：异构值在列内的原生存储
- **字面量/模板/未绑定类型**：Planner 内部的"人家不会直接操作"的元类型基础设施

下一章，我们将看到这些类型如何"活"在 Vector 中——FlatVector、ConstantVector、DictionaryVector 如何利用 PhysicalType 信息做高效的批量计算。
