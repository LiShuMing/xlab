# 第24章：压缩

> 列式存储天然适合压缩——同一列的数据类型相同、分布相似、往往有序。DuckDB 没有辜负这个优势，实现了一套竞技式压缩选择系统：在 Checkpoint 时，所有候选算法同时分析数据，得分最低者（估计压缩后最小）胜出。

## 24.1 压缩策略：轻量、快速、可选择性

DuckDB 的压缩遵循三个原则：

**轻量**：压缩在列段级别（ColumnSegment）上执行，仅在 Checkpoint 写盘时触发。内存中数据不压缩。所有候选算法在单次扫描中并行分析，无需多遍处理。

**快速**：所有算法优先解压速度而非压缩比。使用向量化解压（一次处理 2048 个值），部分算法可跳过解压（如 RLE 可发射 ConstantVector）。

**可选择性**：每种数据类型有专门的候选算法集合。Checkpoint 时，`ColumnDataCheckpointer::DetectBestCompressionMethod` 初始化所有候选的分析状态，将数据送入每个分析器，调用 `final_analyze` 获取得分（估计字节数），最低分胜出。算法可返回 `INVALID_INDEX` 提前退出。

```cpp
// src/function/compression_config.cpp
// CompressionFunctionSet 按物理类型注册候选算法
// Checkpoint 时的压缩选择流程：
// 1. 对每种候选算法调用 init_analyze
// 2. 扫描数据，对每个分析器调用 analyze
// 3. 调用 final_analyze 获取估计大小
// 4. 选择最小估计值的算法
```

## 24.2 压缩算法详解

### Constant：零存储的极致

**目标模式**：列中所有非 NULL 值相同（或全部为 NULL）。

**原理**：磁盘上不存储任何数据。常量值从段统计信息中恢复（`NumericStats::GetMin`）。扫描函数将结果设为 `CONSTANT_VECTOR`，只有一个值。

**取舍**：近乎无限的压缩比（零数据存储）。解压实质免费。

```
原始数据: [5, 5, 5, 5, ..., 5] (2048 个 5)
压缩后:   统计信息中记录 min=5 → CONSTANT_VECTOR
存储大小: 0 字节
```

### RLE：行程编码

**目标模式**：具有长重复值行程的列（排序列、状态标志、有序分类数据）。

**原理**：数据存储为 (value, count) 对。值和 16 位行程计数存储在块内的独立数组中。扫描时，如果单个行程覆盖整个扫描向量，`RLEScanConstant` 发射 `CONSTANT_VECTOR`——零解压开销。

```
原始数据: [A, A, A, B, B, C, C, C, C, C]
压缩后:   [(A,3), (B,2), (C,5)]
```

**取舍**：对有序/重复数据压缩比极好（可压缩到原始大小的极小比例）。高基数数据压缩比差。

**支持类型**：所有整数类型（8-128 位）、float、double、bool、list。

### BitPacking：整数压缩的瑞士军刀

**目标模式**：值域小于原生位宽的整数列（小范围、顺序 ID、年龄字段等）。

**原理**：这是最复杂的整数压缩器，支持四种子模式：

| 子模式 | 适用场景 | 方法 |
|--------|----------|------|
| CONSTANT | 所有值相同 | 只存值 |
| FOR (Frame of Reference) | 值在小范围内 | 减去最小值后位打包残差 |
| CONSTANT_DELTA | 连续值的差值恒定 | 存基准值 + 差值 |
| DELTA_FOR | 单调递增/递减 | 差分编码后应用 FOR + 位打包 |

数据按元数据组（`BITPACKING_METADATA_GROUP_SIZE = 2048`）组织。每组 4 字节元数据编码模式、偏移和参数。数据从块起始向上增长，元数据从块末尾向下增长，最终压缩合并。

```
原始数据 (int64): [1000000, 1000001, 1000002, ..., 1002047]
FOR 编码: min=1000000, residuals=[0, 1, 2, ..., 2047]
位宽: 11 bits (2047 < 2^11)
压缩比: 64 bits → 11 bits ≈ 5.8x
```

**取舍**：通常是最好的通用整数压缩。FOR 可将 64 位整数压缩到几位。解压快速（SIMD 友好的位解包）。

**支持类型**：所有整数类型、bool、list。

### Dictionary：低基数字符串的字典编码

**目标模式**：低到中基数的字符串列（重复值、类别码、国家名等）。

**原理**：唯一字符串在块末尾的字典中存储一次。每个元组存储一个位打包的字典索引。索引 0 保留给 NULL。

```
原始数据: ["US", "EU", "US", "US", "EU", "JP", "US"]
字典:     [NULL, "US", "EU", "JP"]
索引:     [1, 2, 1, 1, 2, 3, 1]  → 2 bits per value
```

**取舍**：低基数字符串压缩比极好（每个唯一字符串只存一次）。近唯一字符串时字典开销反而增加。

### DictFSST：当前主力字符串压缩器

**目标模式**：字符串列。存储版本 >= 5 的默认字符串压缩算法。

**原理**：Dictionary + FSST 的组合拳，三种动态模式：

| 模式 | 条件 | 方法 |
|------|------|------|
| DICTIONARY | 字典太小，FSST 无益 | 纯字典编码 |
| DICT_FSST | 字典达到 4096 字节阈值 | 字典去重 + FSST 编码字典 |
| FSST_ONLY | 所有字符串唯一（去重无益） | 仅 FSST 编码 |

压缩状态机从 `REGULAR`（纯字典）开始，当段填满时调用 `TryEncode()`。如果 FSST 提供足够压缩，切换到 `ENCODED` 或 `ENCODED_ALL_UNIQUE`。

```
原始数据: ["hello world", "hello world", "hello duckdb", ...]
DICT_FSST 编码:
  1. 字典去重: ["hello world", "hello duckdb", ...]
  2. FSST 编码字典: 常见字节序列 "hello " → 单字节码
  3. 位打包字典索引
```

**取舍**：通用字符串压缩最佳。字典消除重复，FSST 压缩唯一值。动态适配三种模式。

> **与 Parquet 字符串压缩的对比**：Parquet 使用 Dictionary + Delta + Snappy/Zstd 的组合。DuckDB 的 DictFSST 更智能——它根据数据特征在三种模式间动态切换，而非依赖用户选择压缩编码。

### FSST：已被 DictFSST 取代

**状态**：存储版本 >= 5 中已弃用（`StringInitAnalyze` 返回 `nullptr`）。旧数据仍可读取。

FSST（Fast Static Symbol Table）用单字节码替换常见字节序列。DictFSST 将 FSST 作为内嵌组件使用，替代了独立的 FSST 压缩。

### ALP：浮点数的主力压缩器

**目标模式**：可以用 10 的幂次乘法表达为整数的浮点列（价格、度量、金融数据等）。

**原理**：ALP（Adaptive Lossless floating-Point compression）分两级采样：

1. **RowGroup 级**：采样约 8 个向量，尝试所有指数/因子组合（如 ×1000、×0.01），找到 Top-K（K=5）最佳组合
2. **Vector 级**：对每个 1024 值的向量，从 Top-K 中找最佳因子/指数

每个值编码为 `value × 10^exponent × 10^factor` 转为 int64。编码后不能精确还原的值存储为例外。然后应用 FOR（减去最小值）+ 位打包。

```
原始数据 (double): [19.99, 29.99, 39.99, 49.99]
ALP 编码: factor=2, exponent=0 → ×100
  → [1999, 2999, 3999, 4999]
  FOR: min=1999, residuals=[0, 1000, 2000, 3000]
  位宽: 12 bits
  压缩比: 64 bits → 12 bits ≈ 5.3x
```

**取舍**：对"类十进制"浮点数压缩比极好（4-8x）。例外率通常很低。对真正随机的浮点数据效果差。

### ALP RD：随机浮点数的压缩方案

**目标模式**：ALP 压缩效果差的浮点列（更随机、非十进制模式）。

**原理**：ALP-RD（Roaring Dictionary）将每个浮点值的二进制表示在选定位置切分为"左部"和"右部"。左部字典编码（最多 8 个条目，3 位索引），右部位打包。左部不在字典中的值存储为例外。

```
原始数据 (double): [3.14159, 2.71828, 1.41421, ...]
切分位置: 高 16 位 / 低 48 位
左部字典: [0x4009, 0x4005, 0x3FF6] → 2 bits 索引
右部: 各 48 位位打包
```

**取舍**：随机浮点数压缩比约 40-60%（不如 ALP 对适配数据的 4-8x，但远好于不压缩）。

### Roaring：有效性掩码的专用压缩

**目标模式**：有效性掩码（PhysicalType::BIT）和布尔列（PhysicalType::BOOL）。

**原理**：适配 Roaring Bitmap 概念。数据组织为 2048 值的容器，三种容器类型动态选择：

| 容器类型 | 适用场景 | 存储 |
|----------|----------|------|
| RUN_CONTAINER | 连续相同位 | (start, length) RLE 对 |
| ARRAY_CONTAINER | 稀疏位集 | 置位位置的 uint16_t 索引 |
| BITSET_CONTAINER | 密集位集 | 原始 64 位字 |

容器可以"反转"（编码 NULL 而非有效位）以最小化空间。

**取舍**：对有效性掩码极好。删除后的 NULL 连续行程压缩为极小的 RLE 条目。稀疏 NULL 只存索引。

### ZSTD：长字符串的通用压缩

**目标模式**：平均长度超过阈值（可配置 `ZstdMinStringLengthSetting`）的字符串列。

**原理**：使用 Zstandard 库。字符串按向量（最多 2048 个值）压缩。字符串长度不压缩；拼接的字符串数据使用 ZSTD 流式压缩。压缩数据可跨多个块（溢出页通过 block_id_t 链接）。

分析阶段对短字符串施加 1000 倍惩罚，使 ZSTD 不太可能被自动选择用于短字符串列。

**取舍**：长字符串压缩比最好（通常比 DictFSST 高 2-5x）。解压慢于 DictFSST。每向量的开销对短字符串不利。

### 已弃用：Chimp 和 Patas

Chimp（Gorilla 风格浮点压缩）和 Patas（更简单的 XOR 浮点压缩）已被弃用（`init_analyze` 返回 `nullptr`），ALP/ALPRD 取代了它们。旧数据仍可读取。

## 24.3 CompressionInfo 与压缩元信息存储

```cpp
// src/include/duckdb/function/compression_function.hpp
struct CompressionInfo {
    BlockManager &block_manager;
    idx_t GetBlockSize();        // 块大小用于决策
    idx_t GetBlockHeaderSize();  // 头部开销
    idx_t GetCompactionFlushLimit(); // block_size * 4/5，低于此阈值的段会被压缩
};
```

每个段的元信息存储在 `DataPointer` 中：

```cpp
// src/include/duckdb/storage/data_pointer.hpp
struct DataPointer {
    idx_t row_start;          // 起始行
    idx_t tuple_count;        // 行数
    BlockPointer block_pointer; // 压缩块位置
    CompressionType compression_type; // 使用的压缩算法
    BaseStatistics statistics;  // 段级统计（min, max, null count 等）
    unique_ptr<ColumnSegmentState> segment_state; // 算法特定的序列化状态
};
```

## 24.4 压缩对 Vector 读取的影响

### 延迟解压 vs 全量解压

**DictFSST（延迟解压）**：全向量扫描时，`ScanToDictionaryVector` 创建 `DictionaryVector`——结果向量通过选择向量引用预解码的字典字符串。不发生字符串拷贝。只有当下游需要 FlatVector 时才实际查找并拷贝。

**RLE（常量向量优化）**：当单个行程覆盖整个扫描向量时，发射 `CONSTANT_VECTOR`。下游算子只看到一个值并处理一次。

**BitPacking（选择性解压）**：只解压当前扫描位置所需的元数据组和位打包块。`FetchRow` 创建临时扫描状态，只解压所需的单个值。

**Roaring（容器级扫描）**：只加载覆盖当前扫描位置的容器。容器间跳转几乎免费。

**ZSTD（向量级流式）**：一次解压一个向量。顺序扫描利用缓存避免重复解压。`FetchRow` 从头创建临时扫描状态。

### 过滤下推

多种算法支持 `filter` 和 `select` 函数指针：

- **RLE**：`RLEFilter` 对所有行程值一次性应用过滤，然后标记匹配行——可跳过整个行程
- **DictFSST**：`DictFSSTFilter` 对字典值应用过滤一次，构建匹配字典条目的布尔数组
- **Constant**：对单个常量值评估过滤，可能不扫描任何数据就消除所有行

### 有效性列优化

当基础数据压缩器设置 `CompressionValidity::NO_VALIDITY_REQUIRED`（目前只有 DictFSST 这样做），有效性列使用 `COMPRESSION_EMPTY`——零字节段。这对字符串列是显著优化：字符串列通常极少 NULL，避免了每段存储完整的有效性掩码。

## 24.5 压缩算法选择总结

| 物理类型 | 候选算法 |
|----------|----------|
| BOOL | Constant, Uncompressed, RLE, BitPacking, Roaring |
| INT8/16/32/64, UINT8/16/32/64 | Constant, Uncompressed, RLE, BitPacking |
| INT128, UINT128 | Constant, Uncompressed, RLE, BitPacking |
| FLOAT, DOUBLE | Constant, Uncompressed, RLE, ALP, ALPRD |
| VARCHAR | Uncompressed, Dictionary, DictFSST, ZSTD |
| BIT (有效性) | Constant, Uncompressed, Roaring, Empty |
| LIST | Uncompressed, RLE, BitPacking |

## 本章小结

DuckDB 的压缩系统体现了一个核心洞察：**没有"最佳"压缩算法，只有"最适配"的**。竞技式选择让每段数据找到自己的最优压缩方案。

与 Parquet 的对比：Parquet 让用户选择压缩编码（SNAPPY/ZSTD/GZIP 等），一种编码覆盖整个文件。DuckDB 在每个列段级别自动选择——同一列的不同段可能使用不同压缩算法，因为数据分布可能随时间变化。

与 ClickHouse 的对比：ClickHouse 提供多种编解码器（LZ4/ZSTD/DoubleDelta/Gorilla 等），也需要用户手动指定。DuckDB 的自动选择降低了使用门槛，代价是分析阶段的开销——但由于 k 很小（通常 3-5 个候选），这个开销可忽略。

三个关键设计模式值得记住：
1. **竞技式分析**：O(n × k) 复杂度，k 小，效率高
2. **元数据在末尾**：BitPacking 和 Roaring 的元数据从块末尾向下增长，数据从起始向上增长——避免预计算精确的元数据大小
3. **段压缩**：段使用低于 80% 块大小时，压缩字典/元数据消除浪费空间
