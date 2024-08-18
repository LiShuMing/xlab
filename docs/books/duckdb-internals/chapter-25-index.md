# 第25章：索引

> DuckDB 的索引哲学与 OLTP 数据库截然不同：索引不是查询加速的主要手段——Zone Map 才是。ART 索引存在的唯一理由是约束强制（UNIQUE、PRIMARY KEY、FOREIGN KEY）。

## 25.1 DuckDB 的索引哲学：Zone Map 优先

### Zone Map：隐式的"索引"

DuckDB 的主要数据跳过机制是 **Zone Map**——每个 `ColumnSegment` 的 min/max 统计信息。它永远存在，无需显式创建。

```cpp
// src/include/duckdb/storage/statistics/base_statistics.hpp
// BaseStatistics 持有每段统计：NumericStatsData (min/max)、StringStatsData (截断 min/max)、
// GeometryStatsData 等

// src/include/duckdb/storage/statistics/numeric_stats.hpp
FilterPropagateResult NumericStats::CheckZonemap(const Value &constant,
                                                  ExpressionType comparison_type);
// 返回：FILTER_ALWAYS_TRUE / FILTER_ALWAYS_FALSE / NO_PRUNING_POSSIBLE
```

Zone Map 在**段级别**工作：如果一个 `ColumnSegment` 的 `amount` 列范围是 [50, 80]，而过滤条件是 `amount > 100`，整个段被标记为"可跳过"。

这是列式存储最强大的 Data Skipping 机制——不是索引，而是"隐式索引"。

### 为什么 ART 而非 B-Tree？

1. **列存使 B-Tree 二级索引查找低效**：OLTP 行存中，B-Tree 返回元组指针直接访问行。列存中没有"行"可指向——必须从多个列段重建行
2. **Zone Map 已覆盖数据跳过**：B-Tree 的主要 OLTP 优势（避免全表扫描）已被段级 min/max 覆盖
3. **ART 在内存中点查/范围查找更优**：自适应节点大小（4/16/48/256）最小化内存开销，保持 O(k) 查找（k = 键长）
4. **ART 天然处理变长键**：字符串键和复合键是拼接的字节数组，ART 的前缀压缩和惰性扩展比 B-Tree 固定大小键槽更节省空间

## 25.2 ART（Adaptive Radix Tree）索引的实现

### 三层索引抽象

```
Index (抽象基类)                  —— column_ids, table_io_manager
  └── BoundIndex (抽象)           —— types, expressions, executor, lock
       └── ART (具体)             —— tree, allocators, prefix_count
  └── UnboundIndex (具体)         —— 绑定前的包装器，缓冲 WAL 重放操作
```

### 10 种节点类型

```cpp
// src/include/duckdb/execution/index/art/node.hpp
enum class NType : uint8_t {
    // 内部节点（键 → 子指针）
    NODE_4,     // 最多 4 个子节点，排序键数组 + 子数组
    NODE_16,    // 最多 16 个子节点
    NODE_48,    // 最多 48 个子节点，256 条目间接数组 + 48 子槽
    NODE_256,   // 最多 256 个子节点，直接 256 子槽数组
    // 叶子节点（存储行 ID）
    LEAF_INLINED,  // 行 ID 直接存储在 Node 指针的 56 位载荷中（无单独分配）
    LEAF,          // 已弃用的行 ID 链表（向后兼容）
    NODE_7_LEAF,   // 最多 7 个排序字节
    NODE_15_LEAF,  // 最多 15 个排序字节
    NODE_256_LEAF, // 256 位位掩码
    // 前缀节点
    PREFIX         // 最多 prefix_count 字节的链 + 子指针
};
```

### 自适应大小转换

```
Node4  → Node16   当 count > 4
Node16 → Node48   当 count > 16
Node48 → Node256  当 count > 48

Node256 → Node48  当 count <= 36 (SHRINK_THRESHOLD)
Node48  → Node16  当 count <= 12 (SHRINK_THRESHOLD)
Node16  → Node4   当 count < 16
```

这种自适应大小选择是 ART 的核心优势：稀疏区域用小节点节省内存，密集区域自动扩展为大节点保持性能。

### IndexPointer：64 位紧凑表示

```
位布局:
63         56 55                      32 31                                  0
+------------+--------------------------+------------------------------------+
|  Metadata  |           Offset         |           Buffer ID                |
|   8 bits   |          24 bits         |            32 bits                 |
+------------+--------------------------+------------------------------------+

Metadata: 存储 NType + GateStatus
Offset:   FixedSizeBuffer 内的段偏移
Buffer ID: 标识 FixedSizeBuffer
```

这种 8 字节指针在整个 ART 中使用，实现了紧凑的节点表示。

### Gate 节点：嵌套 ART 的设计模式

当非唯一索引的同一键有多个行 ID 时，叶子变成一个"门"节点，标记进入**嵌套 ART** 的转换——行 ID 作为键。`GateStatus` 存储在 `IndexPointer` 的元数据位中。

```
外层 ART:
  key="US" → Gate Node → 嵌套 ART:
                              row_id=100 → LEAF_INLINED(100)
                              row_id=200 → LEAF_INLINED(200)
```

这种设计避免了非唯一索引中重复键的冲突——嵌套 ART 中行 ID 保证唯一。

### 键生成：基数编码

```cpp
// src/include/duckdb/common/radix.hpp
// 所有值转换为字节可比较的基数键：
// 有符号整数：翻转符号位使负值排在正值之前
// 无符号整数：原样存储（大端）
// 浮点数：IEEE 754 + 符号位操作使浮点排序匹配数值排序
// 字符串：原始字节 + 零填充
// 多列键：ARTKey::Concat() 拼接，任何 NULL 列使整个键为空
```

### 核心操作

**插入**：递归遍历。遇到同键的内联叶子时：
- 非唯一索引：`Leaf::MergeInlined()` 创建 Gate 节点和嵌套 ART
- 唯一索引：返回 `ARTConflictType::CONSTRAINT`

**删除**：追踪 greatgrandparent/grandparent/parent 引用，用于删除后压缩 Node4。

**查找**：通过前缀链和内部节点的线性遍历。

**从有序数据构建**：`ART::Build()` 使用 `ARTBuilder` 从排序键自底向上构造——O(n) 复杂度。

**合并**：`ART::MergeIndexes()` 先合并分配器存储（递增源缓冲区 ID），然后用 `ARTMerger` 做结构性树合并。

## 25.3 索引的创建与维护

### 创建流程

```
ARTBuildBind → ARTBuildSort → ARTBuildGlobalInit → ARTBuildLocalInit
→ ARTBuildSink → ARTBuildCombine → ARTBuildFinalize
```

并行构建：每个线程创建本地 ART，然后通过 `ARTBuildCombine` → `MergeIndexes` 合并。有序构建路径使用 `ART::Build()` 自底向上构造，O(n) 而非 O(n log n)。

### 索引扫描

```cpp
// src/execution/index/art/art.cpp
// ART::TryInitializeScan(): 用 ComparisonExpressionMatcher 匹配比较表达式
// 支持等值、范围（单边和双边）、BETWEEN 谓词
// ART::Scan(): 分派到 SearchEqual, SearchGreater, SearchLess, SearchCloseRange, FullScan
```

### Checkpoint 期间的 Delta 索引

```cpp
// src/include/duckdb/storage/table/table_index_list.hpp
// IndexEntry 持有 added_data_during_checkpoint 和 removed_data_during_checkpoint
// Checkpoint 后，MergeCheckpointDeltas() 合并 delta 索引回主索引
```

Checkpoint 期间，新的追加和删除进入 Delta 索引而非主索引。Checkpoint 完成后，Delta 索引合并回主索引——避免 Checkpoint 期间锁定索引。

## 25.4 为什么没有 B-Tree 索引？与 OLTP 数据库的路径差异

| 维度 | OLTP (PostgreSQL) | OLAP (DuckDB) |
|------|-------------------|---------------|
| 主要加速手段 | B-Tree 索引 | Zone Map + 列裁剪 |
| 索引用途 | 查询加速 + 约束 | 仅约束 |
| 典型查询模式 | 点查、小范围 | 全表扫描、大范围聚合 |
| 行存储访问 | 索引 → 直接行访问 | 不适用（列存无"行"） |
| 索引类型需求 | 等值 + 范围 + 全文 | 等值（UNIQUE/PK） |
| 索引选择性 | 高选择性（1/100万） | 低选择性（1/100） |

DuckDB 放弃 B-Tree 不是偷懒——是列式存储的本质决定的。在列存中，"通过索引找到一行"的开销（读取 N 个列段、重建行）远大于在行存中（直接偏移）。相反，Zone Map 的"跳过整个段"策略完美匹配列存的 I/O 模式。

## 本章小结

DuckDB 的索引设计是"少即是多"的哲学：
- **Zone Map** 是零成本的隐式索引——每个段自动维护
- **ART** 是唯一的显式索引结构——专门用于约束强制
- **没有 B-Tree**——不是能力缺失，而是架构选择

对于从 OLTP 转来的工程师，最重要的心态转换是：**在 OLAP 中，索引不是性能的答案，数据跳过才是。**
