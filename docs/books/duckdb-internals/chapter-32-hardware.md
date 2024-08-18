# 第32章：与计算硬件的适配

> 数据库性能不是算法的问题，而是算法与硬件对话的问题。Cache 延迟、SIMD 宽度、NUMA 拓扑——这些硬件现实决定了"好算法"和"快算法"之间的差距。

## 32.1 SIMD 在 DuckDB 中的应用

### 一个反直觉的发现：DuckDB 不使用显式 SIMD 内联函数

DuckDB 的核心执行引擎中没有 `_mm_`、`__m256i`、NEON 内联函数等显式 SIMD 代码。这是刻意的设计选择，而非能力缺失。DuckDB 依赖三种方式获得 SIMD 加速：

**1. 编译器自动向量化**

```cpp
// src/include/duckdb/common/vector_operations/unary_executor.hpp
// ExecuteFlat 方法产生紧凑的 for 循环，编译器可以自动向量化：
for (idx_t i = 0; i < count; i++) {
    result[i] = OP(input[i]);
}
// 编译器在 -O2/-O3 下生成 SIMD 指令（AVX2/AVX-512/NEON）
```

`UnaryExecutor` 和 `BinaryExecutor` 框架产生编译器友好的循环——没有虚函数调用、没有分支、没有指针追逐。这是"让编译器做重活"的哲学。

**2. FastPFor 位打包库**

```cpp
// third_party/fastpforlib/
// 用于 BitPacking 压缩/解压
// duckdb_fastpforlib::fastpack / fastunpack
// 该库包含编译时根据 CPU 特性选择的 SIMD 优化打包/解包例程
```

这是 DuckDB 中唯一使用显式 SIMD 的地方，但封装在第三方库中。

**3. 设计为可向量化的算法**

- **MurmurHash64**（`src/include/duckdb/common/hash.hpp`）：
  ```cpp
  x ^= x >> 32;
  x *= 0xd6e8feb86659fd93U;
  x ^= x >> 32;
  x *= 0xd6e8feb86659fd93U;
  x ^= x >> 32;
  ```
  乘法-异或-移位的设计具有良好的雪崩行为，且可自动向量化。

- **字符串比较优化**（`src/include/duckdb/common/types/string_type.hpp`）：
  将前 8 字节（长度 + 4 字节前缀）作为单个 64 位加载比较，利用 CPU 的 8 字节比较能力。

- **De Bruijn 序列位操作**（`src/include/duckdb/common/bit_utils.hpp`）：
  用 De Bruijn 序列实现无分支的前导/后导零计数，比 `__builtin_clz` 更可移植。

### 为什么不用显式 SIMD？

1. **可移植性**：DuckDB 支持 x86、ARM、WASM——显式 SIMD 需要为每个平台写不同代码
2. **维护成本**：SIMD 内联函数随 ISA 演进（SSE → AVX2 → AVX-512 → SVE），维护多版本代码代价高
3. **编译器进步**：现代编译器（GCC 12+, Clang 15+）的自动向量化能力已接近手写
4. **向量化执行模型**：2048 元素的向量天然适配 SIMD——编译器"看到"的循环足够长，值得向量化

## 32.2 Cache Line 友好的数据结构设计

### TupleDataLayout：行式内部表示

```
行布局：
[validity bits][data columns][aggregate states][heap size (if variable-length)]
```

- 有效性掩码每值 1 位，紧凑在行起始
- 数据列无对齐填充
- 聚合字段对齐（`AlignValue(row_width)`）
- 排序键固定宽度：8、16、24 或 32 字节——自然适配缓存行

### ht_entry_t：8 字节条目

```cpp
// src/include/duckdb/execution/join_hashtable/ht_entry.hpp
// 每条目 8 字节，恰好一个条目占一个槽
// IncrementAndWrap 使用无分支 AND 操作：
// ++offset &= capacity_mask  // 代替取模，避免分支误预测
```

### BloomFilter：缓存行对齐

```cpp
// src/planner/filter/bloom_filter.cpp
// 64 字节对齐分配
// 每扇区 64 位
// 每个哈希设置 4 位 → 每次探测恰好一个缓存行
```

### PrefixRangeBitmap：缓存行对齐

```cpp
// src/planner/filter/prefix_range_filter.cpp
// 64 字节对齐分配
// 无分支查找：& (0U - in_range) 掩码操作
```

### Vector 大小的 Cache 意义

```cpp
// src/include/duckdb/common/constants.hpp
STANDARD_VECTOR_SIZE = 2048
```

2048 元素 × 8 字节 = 16KB，恰好适合 L1 缓存（通常 32-64KB）。这提供了足够的并行度让 SIMD 和乱序执行发挥作用，同时不溢出 L1。大多数系统使用 1024 或更小的向量大小——DuckDB 选择 2048 是刻意的性能权衡。

## 32.3 NUMA 意识：Partition-Based 并行模式的硬件适配

### 自动线程钉选

```
当 hardware_concurrency() > 64（THREAD_PIN_THRESHOLD）时自动启用：
1. GetProcessCPUMask() → sched_getaffinity 获取可用 CPU
2. SetThreadAffinity() → pthread_setaffinity_np 绑定线程到特定 CPU
3. 核数少于线程数时跳过钉选，让 OS 调度器处理
```

线程钉选确保分区的数据留在处理它的 CPU 本地——这是 NUMA 架构上避免远程内存访问的关键。

### 自适应分区数量

```
行宽对分区数的影响：
- row_width >= 64 字节 → 减少 2 位基数（4x 更少分区）
- row_width >= 32 字节 → 减少 1 位基数（2x 更少分区）

原因：宽行分区数据可能超过每线程缓存预算
```

### 倾斜检测与回退

```
KeysAreSkewed(): 最大分区 > 33% 总大小 → 强制单线程 Finalize
very_very_skewed: > 80% → 完全避免重分区

原因：倾斜分区导致原子竞争，单线程反而更快
```

### 外部 Join 的内存适应

```
HashJoinRepartitionEvent:
  repartition_threads = max(reservation / thread_memory, 1)
  如果局部哈希表多于重分区线程 → 先合并再分区
```

## 32.4 向量化执行 vs 编译执行：DuckDB 的第三条路

### 两条传统路径

| 路径 | 代表 | 优势 | 劣势 |
|------|------|------|------|
| 向量化（Volcano + 批量） | MonetDB/X100 | 缓存友好、实现简单 | 虚函数开销、无法消除不必要物化 |
| 编译执行（JIT） | Hyper/Umbra | 消除虚函数、融合算子 | 编译延迟、代码膨胀、调试困难 |

### DuckDB 的第三条路：Morsel-Driven 向量化 + 自适应

**1. 向量类型多态消除不必要工作**

```cpp
enum class VectorType : uint8_t {
    FLAT_VECTOR,       // 标准未压缩
    FSST_VECTOR,       // FSST 压缩字符串（延迟解压）
    CONSTANT_VECTOR,   // 单值重复 → 只处理一次
    DICTIONARY_VECTOR, // 选择向量 → 字典小时只操作字典
    SEQUENCE_VECTOR,   // 等差数列 → 无需物化
    SHREDDED_VECTOR    // 细粒变体
};
```

ConstantVector 避免 2048 次重复处理。DictionaryVector 在字典足够小时只操作字典（而非 2048 个值）。SequenceVector 表示 `1, 2, 3, ...` 而不物化。

**2. 编译时模板特化**

```cpp
// RadixBitsSwitch: 对每个基数位数的编译时模板特化
// 避免 Hot Path 中的运行时分支

// 类型切换的行匹配器
// 哈希表查找的编译时特化
```

**3. 行式内部表示 + 列式执行**

数据在 `TupleDataCollection` 中以行式存储（哈希表操作时缓存效率高），在 `DataChunk` 向量中以列式处理（SIMD 效率高）。`Gather`/`Scatter` 操作在两种表示间转换。

**4. 选择性物化**

```cpp
// PhysicalHashJoin 中的 lhs_probe_columns vs lhs_output_columns
// 探测端数据只物化谓词和输出实际需要的列
// 避免不必要的数据移动
```

**5. 自适应查找策略**

```cpp
// RadixPartitionedHashTable::DecideAdaptation
// 如果 >95% 值唯一（HLL 估算）→ 跳过哈希表查找，只追加
// 推迟去重到合并/定稿阶段
// 避免高基数数据的大量失败查找
```

### 第三条路的本质

DuckDB 避免了 JIT 编译的开销，同时通过以下方式获得了许多编译执行的好处：

1. **大批量（2048）**：分摊每个 Chunk 的固定开销
2. **编译时特化**：模板在编译期选择代码路径
3. **向量类型多态**：运行时选择最快路径
4. **Morsel 驱动并行**：自适应策略匹配硬件特征
5. **预编译快速路径**：Perfect Hash Join、Dictionary Vector、Constant Vector

```
传统向量化:    固定 1024 行 + 统一处理 → 简单但浪费
编译执行:      JIT 编译 → 最优但有延迟
DuckDB 第三条路: 2048 行 + 多态向量 + 自适应路径 → 接近最优且无延迟
```

## 本章小结

DuckDB 的硬件适配策略可以用一句话概括：**让编译器做重活，让数据驱动选择**。

- 不手写 SIMD，但设计可自动向量化的循环
- 不依赖 NUMA API，但通过分区和钉选自然适配 NUMA
- 不做 JIT，但通过向量类型多态获得编译执行的许多好处

这种"隐式硬件适配"的哲学与 DuckDB 的"嵌入式"定位一致——嵌入式场景下不能假设特定硬件特性，但可以通过数据结构和算法设计自然利用硬件能力。
