# 第16章：核心算子实现剖析（上）—— Scan 与 Filter

## 16.1 PhysicalTableScan：从磁盘到内存的读取链路

```cpp
// PhysicalTableScan 的执行入口
SourceResultType PhysicalTableScan::GetData(ExecutionContext &context,
                                             DataChunk &output,
                                             OperatorSourceInput &input) {
    // 从 LocalScanState 获取下一个 RowGroup
    // 读取指定列的数据到 output DataChunk
    // 应用 table_filters 过滤
}
```

### 读取链路的完整路径

```
PhysicalTableScan::GetData
  → DataTable::Scan(scan_state)
    → RowGroupCollection::Scan(scan_state)
      → RowGroup::Scan(scan_state, column_ids, output)
        → ColumnData::FetchRow(scan_state, column_id, row_idx, output)
          → ColumnSegment::ReadData(scan_state, offset, output)
            → 从 BufferManager 获取 Block → 解压 → 拷贝到 Vector
```

### Parallel Scan 机制

多线程扫描时，每个线程维护自己的 `LocalScanState`，包含当前扫描到哪个 RowGroup 的哪个位置。全局的 `TableScanState` 通过原子变量协调——线程间不会重复扫描同一个 RowGroup。

```
全局状态：current_row_group = 0 (atomic)
Thread 1: fetch-and-add → 获得 RowGroup 0
Thread 2: fetch-and-add → 获得 RowGroup 1
Thread 3: fetch-and-add → 获得 RowGroup 2
...
```

## 16.2 PhysicalFilter 与 AdaptiveFilter

### PhysicalFilter

```cpp
// PhysicalFilter 的 Execute
// 对每个输入 DataChunk，评估过滤表达式
// 满足条件的行索引组成 SelectionVector
// 输出一个 DICTIONARY_VECTOR（零拷贝引用输入数据）
```

PhysicalFilter 不拷贝数据——它输出 DICTIONARY_VECTOR，通过 SelectionVector 间接引用输入 Vector 中的数据。只有当下游算子需要 FLAT_VECTOR（如写入）时，才调用 `Flatten`。

### AdaptiveFilter：运行时动态重排序

```cpp
// src/include/duckdb/execution/adaptive_filter.hpp
class AdaptiveFilter {
    // 记录每个过滤条件的执行时间和选择性
    // 动态调整过滤条件的评估顺序
    // 将选择性最高（淘汰最多行）的条件放在最前面
};
```

`AdaptiveFilter` 是 DuckDB 的一个运行时优化——它在第一次执行时收集每个过滤条件的统计信息，然后在后续执行中动态调整条件的评估顺序。

```
原始顺序：a > 10 AND b LIKE '%pattern%' AND c = 5
运行时发现：c = 5 淘汰 90% 的行，a > 10 淘汰 50%，b LIKE 淘汰 30%
调整后：c = 5 → a > 10 → b LIKE '%pattern%'
```

将选择性最高的条件放在前面，使得后续条件需要处理的行数更少——在 OLAP 场景下（高基数、复杂条件），这个优化可以带来显著的性能提升。

---

# 第17章：核心算子实现剖析（中）—— Join

## 17.1 PhysicalHashJoin：构建端、探测端、溢出处理

HashJoin 是 DuckDB 中最常用的 Join 实现。它分两个阶段执行，跨越两个 Pipeline：

### 阶段1：Build Pipeline（构建端）

```
Source → [左表 Scan] → [Filter] → HashJoin.Sink
                                          ↓
                                    构建 HashTable
```

Sink 阶段将左表的所有数据插入 `JoinHashTable`：

```cpp
// src/include/duckdb/execution/join_hashtable.hpp
class JoinHashTable {
    // Block-Based Hash Table
    // 每个 Block 存储多个 Hash Entry
    // Hash Entry: [hash_value | row_data_pointer]
    // 冲突解决：链地址法（同一桶内的 Entry 通过指针链接）
};
```

### 阶段2：Probe Pipeline（探测端）

```
HashTable → [右表 Scan] → [Filter] → HashJoin.Execute(Probe)
                                          ↓
                                    探测 HashTable，输出匹配行
```

探测阶段逐行（实际是逐 DataChunk）扫描右表，对每行计算 Join 键的 Hash 值，在 HashTable 中查找匹配项。

### 溢出处理（Overflow）

当 HashTable 超过内存限制时，DuckDB 使用 **Partition-based Hash Join**：
1. 将构建端和探测端的数据按 Hash 值分区
2. 将超出内存的分区溢出到磁盘
3. 逐个分区重新加载并执行 Join

## 17.2 JoinHashTable 的数据结构

```
JoinHashTable 内存布局：
┌─────────────────────────────────┐
│ Block 0: [Entry][Entry]...[Entry] │  ← 第一个数据块
├─────────────────────────────────┤
│ Block 1: [Entry][Entry]...[Entry] │  ← 第二个数据块
├─────────────────────────────────┤
│ ...                              │
├─────────────────────────────────┤
│ Bucket Directory:                │  ← 桶目录（指针数组）
│ [ptr→Block0] [ptr→Block1] ...   │
└─────────────────────────────────┘

每个 Entry 包含：
  - hash_value (64 bit)
  - 指向 Block 中行数据的偏移
  - 同一桶内下一个 Entry 的指针
```

Block-Based 设计的优势：内存按需分配，不需要预分配一个巨大的连续数组。每个 Block 的大小等于 DuckDB 的 Block 大小（256KB），与 BufferManager 的管理粒度一致。

## 17.3 PerfectHashJoin

```cpp
// src/include/duckdb/execution/operator/join/perfect_hash_join_executor.hpp
class PerfectHashJoinExecutor {
    // 当 Join 键的 NDV ≤ 256 时使用
    // 直接用键值作为数组索引，O(1) 查找
    // 无 Hash 冲突，无 Hash 计算
};
```

当优化器发现 Join 键的不同值数量很少（如性别列只有 2 个值），PerfectHashJoin 用一个数组替代 HashTable——键值直接作为数组索引。这消除了 Hash 计算和冲突处理的开销，对小基数 Join 是一个数量级的提升。

## 17.4 ASOF Join

```sql
SELECT a.ts, a.price, b.rate
FROM trades a ASOF JOIN rates b
  ON a.symbol = b.symbol AND a.ts >= b.ts;
```

ASOF Join 是时序数据场景的专用 Join——对左表每行，找到右表中"不超过左表时间戳的最近一行"。DuckDB 使用 `PhysicalAsOfJoin` 实现，核心算法是对右表按时间排序后使用二分查找。

---

# 第18章：核心算子实现剖析（下）—— Aggregation 与 Window

## 18.1 PhysicalHashAggregate

```cpp
// Hash Aggregate 的三阶段：
// 1. Sink：将每行数据插入 Hash Table，按分组键聚合
// 2. Finalize：合并所有线程的部分聚合结果
// 3. Source：从 Hash Table 中读出最终结果
```

分组聚合的 Hash Table 与 Join Hash Table 结构类似，但每个 Entry 额外存储聚合中间状态（如 SUM 的部分和、COUNT 的部分计数）。

### 多线程聚合的合并

当多个线程并行执行聚合时，每个线程维护自己的 Hash Table。Finalize 阶段需要合并这些 Hash Table：

```
Thread 1: {US: SUM=1000, COUNT=50}, {EU: SUM=2000, COUNT=80}
Thread 2: {US: SUM=1500, COUNT=60}, {EU: SUM=1800, COUNT=70}

Finalize 合并：
  US: SUM=1000+1500=2500, COUNT=50+60=110
  EU: SUM=2000+1800=3800, COUNT=80+70=150
```

## 18.2 PhysicalPerfectHashAggregate

当分组键的 NDV ≤ 256 时，使用数组代替 Hash Table：

```cpp
// 分组键值直接作为数组索引
// 数组元素存储聚合中间状态
// 无 Hash 冲突、无内存碎片
double sums[256];    // SUM 的中间结果
int64_t counts[256]; // COUNT 的中间结果
```

这对 `GROUP BY gender`、`GROUP BY status_code` 等低基数分组极其高效。

## 18.3 PhysicalWindow

```cpp
// Window 函数执行的两阶段：
// 1. Sink：收集所有输入数据（Window 函数需要看到全部数据）
// 2. Source：按分区和排序规则计算窗口函数值
```

DuckDB 区分两种 Window 执行策略：

- **Streaming Window**：`ROW_NUMBER()`, `RANK()`, `LEAD/LAG` 等不需要回溯的函数，可以流式计算
- **Full Window**：`PERCENT_RANK()`, `NTILE()`, 自定义聚合窗口函数，需要看到整个分区的数据

---

# 第19章：表达式计算引擎

## ExpressionExecutor

```cpp
// src/include/duckdb/execution/expression_executor.hpp
class ExpressionExecutor {
    // 执行一棵表达式树，输入一个 DataChunk，输出结果 Vector
    void Execute(Expression &expr, DataChunk &input, Vector &result);

    // 内部为每种表达式类型有专门的 Execute 重载
    void Execute(BoundComparisonExpression &expr, ...);
    void Execute(BoundFunctionExpression &expr, ...);
    void Execute(BoundCastExpression &expr, ...);
    // ...
};
```

### 向量化表达式执行

DduckDB 的表达式计算不是"逐行"的，而是"逐批"的——一个 DataChunk（最多 2048 行）的所有值在一次函数调用中计算完毕：

```
输入 DataChunk: [1, 2, 3, ..., 2048] (a 列)
                [10, 20, 30, ..., 20480] (b 列)

表达式 a + b：
  → 调用 VectorOperations::Add(int32_vector, int32_vector, result_vector)
  → 一次循环处理 2048 个加法
  → 输出: [11, 22, 33, ..., 22528]
```

### NULL 传播

表达式计算必须正确处理 NULL：

```cpp
// NULL 传播规则：
// a + NULL → NULL
// a > NULL → NULL
// a AND NULL → NULL (if a is TRUE) / FALSE (if a is FALSE)
// a IS NULL → TRUE/FALSE (不传播，而是检测)
```

`ValidityMask` 在向量化计算中实现了高效的 NULL 传播——对两个输入 Vector 的 ValidityMask 做 AND 操作即可得到结果的 NULL bitmap。

---

# 第20章：Function 框架与内置函数

## 20.1 函数注册与分派

```cpp
// 三类函数，三种注册方式
class ScalarFunction {     // 标量函数：每行独立计算
    scalar_function_t function;  // 函数指针
};
class AggregateFunction {  // 聚合函数：状态化计算
    aggregate_size_t state_size;
    aggregate_initialize_t initialize;
    aggregate_update_t update;
    aggregate_combine_t combine;
    aggregate_finalize_t finalize;
};
class TableFunction {      // 表函数：返回表（如 read_csv）
    table_function_t function;
    table_function_bind_t bind;
    table_function_init_global_t init_global;
    table_function_init_local_t init_local;
};
```

### TableFunction：数据源抽象的根基

`read_csv`、`read_parquet`、`read_json` 都是 TableFunction——它们在 Catalog 中注册为特殊的表函数，Binder 将 `FROM 'data.csv'` 转换为 `FROM read_csv_auto('data.csv')`。

TableFunction 的四个回调：
1. **bind**：绑定阶段，解析参数，确定输出列名和类型
2. **init_global**：创建全局扫描状态（如文件句柄）
3. **init_local**：创建线程本地扫描状态（如当前读取位置）
4. **function**：执行扫描，产出 DataChunk

这种设计让外部数据源只需要实现四个回调，就能与 DuckDB 的执行引擎无缝集成。
