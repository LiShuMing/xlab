# Chapter 11: 向量化表达式求值 — ActionsDAG / JIT / SIMD

## 11.1 ActionsDAG — 表达式求值图

`src/Interpreters/ActionsDAG.h` — ClickHouse 的表达式求值引擎使用 DAG（有向无环图）而非表达式树：

```cpp
class ActionsDAG
{
    // DAG 中的节点
    struct Node
    {
        enum class Type
        {
            INPUT,      // 输入列
            COLUMN,     // 常量列
            FUNCTION,   // 函数调用
            ARRAY_JOIN, // ARRAY JOIN
        };

        Type type;
        String result_name;
        DataTypePtr result_type;
        ColumnPtr column;           // 常量值或结果缓存
        FunctionBasePtr function;   // 函数实现
        ColumnsWithTypeAndName arguments; // 子节点
    };

    // DAG 节点集合
    Nodes nodes;
    // 输出列（DAG 的叶节点子集）
    NameToIndexMap required_joints;
};
```

**为什么用 DAG 而不是树？** 公共子表达式消除（CSE）：

```
表达式: (a + b) * (a + b) + c

AST 树:            DAG:
    +                +
   / \              / \
  *   c            *   c
 / \              |
+    +            +  (共享节点)
/ \  / \         / \
a b  a b         a   b
```

DAG 中 `a + b` 只计算一次，结果被 `*` 和后续操作共享。

### ActionsDAG::execute()

```cpp
ColumnPtr ActionsDAG::execute(const Block & block)
{
    // 拓扑排序遍历 DAG
    for (auto & node : nodes)
    {
        if (node.type == Type::INPUT)
            node.column = block.getByName(node.result_name).column;
        else if (node.type == Type::FUNCTION)
            node.column = node.function->execute(arguments); // 向量化执行
    }
    return output_columns;
}
```

### ActionsDAG 的优化方法

`src/Interpreters/ActionsDAG.cpp` — DAG 支持多种优化：

```cpp
class ActionsDAG
{
    // 移除未被输出列引用的中间节点（死代码消除）
    void removeUnusedActions(const NameSet & required_names);

    // 常量折叠：编译时可计算的表达式提前求值
    // 例如: 1 + 2 → 3, now() → 具体时间戳
    void foldConstantActions();

    // 合并连续的 ActionsDAG（减少中间 Block 构造）
    void merge(ActionsDAG && other);

    // 物化常量列（将 ColumnConst 展开为 ColumnVector）
    void addMaterializingOutput();

    // 拆分可短路求值的表达式
    // 例如: if(cond, expensive_func(x), 0) — cond=false 时不计算 expensive_func
    void splitActionsByShortCircuit();
};
```

### 常量折叠示例

```
原始 DAG:
  INPUT(a) ────┐
               ├── FUNCTION(plus) ──── FUNCTION(multiply) ── OUTPUT
  COLUMN(2) ───┘                      │
                                      │
  COLUMN(3) ──────────────────────────┘

常量折叠后:
  COLUMN(6) ── OUTPUT   ← 2 * 3 = 6 已在编译时计算
```

## 11.2 IFunction — 函数接口

`src/Functions/IFunction.h` — ClickHouse 的函数全部是**向量化**的：

```cpp
class IFunction
{
public:
    // 核心接口：一次处理整个列
    virtual ColumnPtr executeImpl(
        const ColumnsWithTypeAndName & arguments,
        const DataTypePtr & result_type,
        size_t input_rows_count) const = 0;

    // 函数属性
    virtual bool isSuitableForShortCircuitArgumentsExecution() const;
    virtual bool isSuitableForConstantFolding() const;
    virtual bool isInjective() const;
    virtual bool isDeterministic() const;
    virtual bool isVariadic() const;     // 是否支持变参
    virtual size_t getNumberOfArguments() const; // 固定参数数
    virtual bool useDefaultImplementationForNulls() const;
    virtual bool useDefaultImplementationForLowCardinalityColumns() const;
};
```

**向量化求值**：`plus(UInt64, UInt64)` 不是逐行调用，而是一次处理 65536 行：

```cpp
// 简化实现
ColumnPtr FunctionPlus::executeImpl(const ColumnsWithTypeAndName & args)
{
    const auto & col_left = assert_cast<const ColumnVector<UInt64> &>(args[0].column);
    const auto & col_right = assert_cast<const ColumnVector<UInt64> &>(args[1].column);

    auto col_result = ColumnVector<UInt64>::create();
    auto & result = col_result->getData();

    // 向量化循环 — 编译器自动 SIMD 化
    const size_t n = col_left.size();
    for (size_t i = 0; i < n; ++i)
        result[i] = col_left.getData()[i] + col_right.getData()[i];

    return col_result;
}
```

编译器（GCC/Clang + -O2）会自动将上述循环展开为 SSE4.2 / AVX2 / AVX-512 指令。

### Nullable 处理

```cpp
// IFunction 的默认 Nullable 处理
// 如果 useDefaultImplementationForNulls() = true:
//   1. 任意参数为 NULL → 结果为 NULL
//   2. 只对非 NULL 行调用 executeImpl
//   3. 合并 null_map

// 如果 useDefaultImplementationForNulls() = false:
//   函数自行处理 NULL 逻辑
//   例如: ifNull(x, default) — x 为 NULL 时返回 default
```

### LowCardinality 处理

```cpp
// IFunction 的默认 LowCardinality 处理
// 如果 useDefaultImplementationForLowCardinalityColumns() = true:
//   1. 展开字典编码列为完整列
//   2. 调用 executeImpl
//   3. 如果结果基数低，重新编码为 LowCardinality

// 如果 useDefaultImplementationForLowCardinalityColumns() = false:
//   函数自行处理字典编码
//   例如: count() — 直接统计字典大小，无需展开
```

## 11.3 SIMD 优化

ClickHouse 在多个层面利用 SIMD：

### 自动向量化

编译器对简单循环自动生成 SIMD 指令。条件：
- 循环无数据依赖
- 数组对齐（`PaddedPODArray` 保证 64 字节对齐）
- 无分支（或分支可预测）

### 手动向量化

`src/Columns/ColumnsCommon.h` — 过滤操作的手动 SIMD 实现：

```cpp
// 使用 SSE4.2 _mm_movemask_epi8 加速 filter
size_t filterVector(const UInt8 * filt, size_t size, IColumn::Offset & pos, ...)
{
    // 一次处理 16 字节的 filter mask
    __m128i mask = _mm_loadu_si128(reinterpret_cast<const __m128i *>(filt + i));
    UInt16 bits = _mm_movemask_epi8(mask);
    // bits 中每个 bit 表示对应行是否通过过滤
    // 使用 popcount + scatter 快速收集
}
```

### ClickHouse 特有的 SIMD 优化

| 函数 | SIMD 加速 | 文件 |
|------|-----------|------|
| `count()` | AVX-512 `vpopcntb` | `AggregateFunctionCount.cpp` |
| `sum()` | SSE4.2 水平加法 | `AggregateFunctionSum.cpp` |
| `memcmp` | SSE4.2 `_mm_cmpestri` | `ColumnsCommon.cpp` |
| `parseUUID` | SSE4.2 shuffle | `parseUUID.cpp` |
| `lower/upper` | SSE4.2 字符转换 | `LowerUpperImpl.h` |
| `volnitsky` (字符串搜索) | SSE4.2 向量化搜索 | `Volnitsky.h` |
| `hasToken` | SSE4.2 token 匹配 | `FunctionsStringSearch.h` |

### Volnitsky 算法 — 向量化字符串搜索

`src/Common/Volnitsky.h` — ClickHouse 的字符串搜索使用 Volnitsky 算法，比标准 `strstr` 快 5-10 倍：

```
原理:
  1. 预处理 needle，构建两个偏移表
  2. 从 haystack 末尾开始，每次跳 2 个字符检查
  3. 使用 SSE4.2 指令一次比较 16 字节

优化:
  - needle ≤ 16 字节: 使用 SSE4.2 _mm_cmpestri 直接匹配
  - needle > 16 字节: Volnitsky 算法 + SSE4.2 加速跳转
  - 大量同时搜索: 多 needle 并行匹配
```

## 11.4 JIT 编译

`src/Interpreters/JIT/` — ClickHouse 使用 LLVM JIT 在运行时编译表达式，消除虚函数调用和分支：

### JIT 编译流程

```
ActionsDAG
  │
  ├── 1. 将 DAG 转换为 LLVM IR
  │     ├── 每个 INPUT → LLVM load 指令
  │     ├── 每个 FUNCTION → LLVM call 指令（内联候选）
  │     └── 每个 COLUMN → LLVM constant
  │
  ├── 2. LLVM 优化 Pass
  │     ├── 内联（消除函数调用开销）
  │     ├── 常量折叠
  │     ├── 死代码消除
  │     └── 循环展开 + 向量化
  │
  ├── 3. 编译为机器码
  │     └── 目标平台: x86-64 (SSE4.2 / AVX2 / AVX-512)
  │
  └── 4. 缓存并执行
        └── 后续相同表达式直接调用缓存的机器码
```

### CompiledExpressionCache

```cpp
// src/Interpreters/JIT/CompiledExpressionCache.h
class CompiledExpressionCache
{
    // 缓存编译后的机器码
    // Key: 表达式 DAG 的哈希
    // Value: 编译后的函数指针

    // LRU 淘汰策略
    // 设置:
    //   compile_expressions = 1          ← 启用 JIT（默认开启）
    //   min_count_to_compile_expression = 3 ← 执行 3 次后触发编译
    //   compiled_expression_cache_size = 128MB ← 缓存大小
};
```

### JIT 编译示例

```
原始表达式: SELECT a + b * c FROM t

解释执行路径:
  for each row:
    call multiply(b[i], c[i])     ← 虚函数调用 + 函数参数检查
    call plus(a[i], temp)          ← 虚函数调用 + 函数参数检查

JIT 编译后:
  for each row:                    ← 单一循环，无虚函数
    temp = b[i] * c[i]            ← 内联后的直接乘法
    result[i] = a[i] + temp       ← 内联后的直接加法

  进一步优化（SIMD）:
  for (i = 0; i < n; i += 4):     ← 4 路并行
    v_b = load(b + i)             ← AVX2 256-bit load
    v_c = load(c + i)
    v_temp = v_b * v_c            ← AVX2 乘法
    v_a = load(a + i)
    v_result = v_a + v_temp       ← AVX2 加法
    store(result + i, v_result)
```

### JIT 适用场景

JIT 在以下场景收益最大：
1. **复杂表达式**：`SELECT a + b * c - d / e FROM t` — 多个函数调用可以内联消除
2. **聚合函数**：`sum(if(cond, val, 0))` — 条件分支可以消除
3. **WHERE 条件**：`WHERE a > 10 AND b < 20 AND c LIKE '%abc%'` — 短路求值优化
4. **大量行**：JIT 编译有一次性开销，只在处理大量行时划算

**不适用场景**：
- 简单的单列投影（`SELECT a FROM t`）— 原始代码已经足够快
- 常量表达式（已通过常量折叠消除）
- 函数无法内联的场景（如 UDF）

## 11.5 短路求值

`IFunction::isSuitableForShortCircuitArgumentsExecution()` — 某些函数的参数可以延迟求值：

```
if(cond, then_val, else_val)

原始: 先计算 then_val 和 else_val，再根据 cond 选择
短路: 只计算 cond 为 true 时的 then_val，或 cond 为 false 时的 else_val

适用于:
  - if(cond, expensive_func(x), default) — cond=false 时不计算 expensive_func
  - multiIf(cond1, val1, cond2, val2, default)
  - ifNull(x, expensive_default)

实现:
  1. isSuitableForShortCircuitArgumentsExecution() 返回 true
  2. ActionsDAG::splitActionsByShortCircuit() 将表达式拆分
  3. 运行时根据条件列的值选择性执行
```

### 短路求值的实现

```
DAG 拆分前:
  if(cond, func_a(x), func_b(y))

  INPUT(cond) ─────────────────┐
  INPUT(x) ── FUNCTION(func_a) ┤
  INPUT(y) ── FUNCTION(func_b) ┤
                               ├── FUNCTION(if) → OUTPUT

DAG 拆分后:
  Phase 1: 计算 cond
    INPUT(cond) → OUTPUT(cond)

  Phase 2: 对 cond=true 的行计算 func_a
    INPUT(x)[filtered by cond=true] → FUNCTION(func_a) → OUTPUT(result_a)

  Phase 3: 对 cond=false 的行计算 func_b
    INPUT(y)[filtered by cond=false] → FUNCTION(func_b) → OUTPUT(result_b)

  Phase 4: 合并结果
    result_a + result_b → OUTPUT
```

## 11.6 ExpressionTransform — DAG 到 Pipeline 的桥梁

`src/Processors/Transforms/ExpressionTransform.h` — 将 ActionsDAG 包装为 Processor：

```cpp
class ExpressionTransform : public ITransformer
{
    ActionsDAG expression;

    void transform(Chunk & chunk) override
    {
        // 1. 将 Chunk 转为 Block
        auto block = chunk.cloneEmpty();
        block.setColumns(chunk.detachColumns());

        // 2. 执行 ActionsDAG
        auto result = expression.execute(block);

        // 3. 将结果转回 Chunk
        chunk.setColumns(result.getColumns(), result.rows());
    }
};
```

### ExpressionActions — 旧版执行引擎

`src/Interpreters/ExpressionActions.h` — 在 Analyzer v2 之前使用的表达式执行引擎：

```
旧路径: AST → ExpressionAnalyzer → ExpressionActionsChain → ExpressionActions
新路径: AST → Analyzer v2 → QueryTree → ActionsDAG → ExpressionTransform

ExpressionActions 使用线性指令序列（类似字节码）：
  ADD_COLUMN(column, name, type)
  ADD_FUNCTION(function, arguments, result_name)
  REMOVE_COLUMN(name)
  PROJECT(names)

ActionsDAG 更优因为:
  1. CSE 自动消除重复计算
  2. 拓扑排序保证依赖顺序
  3. 优化 Pass 可以自由调整 DAG 结构
  4. 更好的 JIT 编译支持
```

## 11.7 聚合函数的向量化

### IAggregateFunction

`src/AggregateFunctions/IAggregateFunction.h` — 聚合函数也是向量化的：

```cpp
class IAggregateFunction
{
    // 创建聚合状态（固定大小内存块）
    virtual size_t sizeOfData() const = 0;
    virtual void create(AggregateDataPtr place) const = 0;

    // 向量化添加行
    virtual void addBatchSinglePlace(
        size_t row_begin,
        size_t row_end,
        AggregateDataPtr place,
        const IColumn ** columns,
        Arena * arena) const = 0;

    // 合并两个聚合状态
    virtual void merge(AggregateDataPtr place, ConstAggregateDataPtr rhs) const = 0;

    // 从聚合状态提取结果
    virtual void insertResultInto(ConstAggregateDataPtr place, IColumn & to) const = 0;
};
```

### 两阶段聚合

```
阶段 1: 分片聚合（每个读取线程独立执行）
  Thread 1: key→state1, key→state2, ...
  Thread 2: key→state3, key→state4, ...

阶段 2: 全局合并
  Merge state1 + state3 → final_state_a
  Merge state2 + state4 → final_state_b

  → 输出: key_a → result_a, key_b → result_b
```

**`addBatchSinglePlace`** 的向量化实现示例（`sum`）：

```cpp
void AggregateFunctionSum::addBatchSinglePlace(
    size_t row_begin, size_t row_end,
    AggregateDataPtr place,
    const IColumn ** columns,
    Arena *) const
{
    // 直接遍历列数据，累加到聚合状态
    const auto & col = assert_cast<const ColumnVector<T> &>(*columns[0]);
    T & sum = this->data(place).value;

    // 编译器自动向量化此循环
    for (size_t i = row_begin; i < row_end; ++i)
        sum += col.getData()[i];
}
```

> **侧边栏 · 与 Spark 对比**：Spark 使用 Volcano 模型（每行一次虚函数调用），从 Spark 3.2 开始通过 Photon 引擎引入向量化。ClickHouse 从第一天就是向量化执行，每个函数处理整个列。JIT 是在向量化基础上的进一步优化——消除虚函数调用，将多个函数融合为一段连续机器码。

> **侧边栏 · 与 StarRocks 对比**：StarRocks 也采用向量化执行模型，但其表达式求值使用纯解释执行（无 JIT）。ClickHouse 的 JIT 编译在复杂表达式上提供了额外的 10-30% 性能提升，代价是 JIT 编译的一次性 CPU 开销和 LLVM 库的内存占用。

## 11.8 本章小结

```
表达式求值架构:
  ActionsDAG → 拓扑排序 → 逐节点执行 → Block 输出
       │
       ├── 向量化: 每个函数处理整列（65536 行）
       │     ├── IFunction::executeImpl → 批量处理
       │     ├── IAggregateFunction::addBatchSinglePlace → 批量聚合
       │     └── Nullable/LowCardinality 自动处理
       │
       ├── 优化: ActionsDAG 级别
       │     ├── CSE（公共子表达式消除）
       │     ├── 常量折叠
       │     ├── 死代码消除
       │     └── 短路求值拆分
       │
       ├── SIMD: 编译器自动 + 手动 intrinsics
       │     ├── PaddedPODArray 对齐保证
       │     ├── SSE4.2/AVX2/AVX-512 指令
       │     └── Volnitsky 字符串搜索
       │
       └── JIT: LLVM 编译消除虚函数 + 内联 + 常量折叠
             ├── min_count_to_compile_expression = 3
             ├── CompiledExpressionCache (LRU)
             └── 适用: 复杂表达式、聚合函数、WHERE 条件
```

**关键文件地图**：
```
src/Interpreters/ActionsDAG.h          → 表达式 DAG
src/Interpreters/ActionsDAG.cpp        → DAG 优化 Pass
src/Functions/IFunction.h              → 函数接口
src/AggregateFunctions/IAggregateFunction.h → 聚合函数接口
src/Interpreters/JIT/                  → JIT 编译
src/Interpreters/JIT/CompiledExpressionCache.h → JIT 缓存
src/Columns/ColumnsCommon.h            → 向量化过滤
src/Common/Volnitsky.h                 → 向量化字符串搜索
src/Processors/Transforms/ExpressionTransform.h → DAG 执行器
```
