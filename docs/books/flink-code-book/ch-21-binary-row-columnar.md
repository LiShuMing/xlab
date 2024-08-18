# 第 21 章 · Binary Row 与列式处理

## 导读

- **一句话**：本章深入 Flink 的 RowData 内部表示——从 BinaryRowData 的二进制布局到 ColumnarRowData 的向量化 Batch 处理。
- **前置知识**：第 2 章 MemorySegment、第 20 章 CodeGen。
- **读完本章你能回答**：
  - `RowData` 接口为什么是 Flink SQL 内部数据的共同抽象
  - `BinaryRowData` 的内存布局分析——为什么可变长和定长分别存储
  - `ColumnarRowData` 怎样面向 SIMD 做向量优化
  - 与 Spark `UnsafeRow` 和 `ColumnarBatch` 的异同

---

## 21.1 — 设计动机：行存 vs 列存的双重困境

SQL 引擎这辈子在两个存储方向之间摇摆：
- **行存**：适合 OLTP（快速读/写整行，少量列），不适合 aggregation（只需 2 列但要拖进 10 列）
- **列存**：适合 OLAP（浮列投影，SIMD 优化），不适合连续列修改

Flink 的答案是 **哥都支持**——在不同的算子用不同的内部格式，用 `RowData` 接口统一：

```java
public interface RowData {
    int getArity();                           // 列数
    boolean isNullAt(int pos);
    boolean getBoolean(int pos);
    byte getByte(int pos);
    int getInt(int pos);
    long getLong(int pos);
    String getString(int pos);
    // ...
}
```

运行时实现两个根本不同的类：
- `BinaryRowData` — 行存，用在 State、Shuffle 传输
- `ColumnarRowData` — 列存，用在 Parquet/ORC Vectorized Reader

---

## 21.2 — BinaryRowData：紧凑的二进制行

### 内存布局

```
┌───────────────────────────────────────────────────┐
│                     Header                         │
│  ├── rowKind (1 byte): INSERT/UPDATE/DELETE       │
│  └── arity (header byte 或 从外部提供)            │
├───────────────────────────────────────────────────┤
│              Fixed-Length Section                  │
│  每个固定长度字段直接占位:                         │
│  [int32@pos0] [int32@pos1] [long@pos2] ...        │
│  null bit set 若为 null                             │
├───────────────────────────────────────────────────┤
│            Variable-Length Offset Section          │
│  [offset0][offset1][offset2] ...                   │
│  指向 variable-length section 中各字段的起始        │
├───────────────────────────────────────────────────┤
│             Variable-Length Section                │
│  [binary for String@pos3][binary for byte[]@pos4]  │
└───────────────────────────────────────────────────┘
```

源码入口：`flink-table-runtime/.../data/binary/BinaryRowData.java`

**关键优化**：
- 固定长度字段 = 直接一份，无间接访问（适合 filter、join key 提取）
- 可变长度字段通过 offset 数组索引——支持零长度字段（off=0）
- 占用的内存在 1 个 MemorySegment 中，不需要多个容器
- 可以直接参与 binary copy / compare，不需要反序列化

### BinaryRowData 和 KeyGroup

回顾第 13 章 State 用 `KeyGroupRange`——State 中存储的值也是 Serialized to BinaryRowData 形式（双重二进制：MemorySegment → BinaryRowData → 用户 TypeSerializer）。RocksDB State 中 Value 是 BinaryRowData 的 TypeSerializer 序列后格式。

---

## 21.3 — ColumnarRowData：向量化列 Batch

### WE架构

```
ColumnarRowData 是 "Logical Row" view over Column Vectors:

ColumnarRowData { 
  ColumnVector[] vectors;   // 每列一个列向量
  int rowId;
}

// 当调用 getInt(0) 时：
public int getInt(int pos) { return vectors[pos].getInt(rowId); }
```

每个 `ColumnVector` 是一段连续的同列数据类型（类似 Spark 的 `WritableColumnVector`）：

```java
public interface ColumnVector {
    boolean isNullAt(int rowId);
    boolean getBoolean(int rowId);
    int getInt(int rowId);
    long getLong(int rowId);
    byte[] getBinary(int rowId);
    // ...
}
```

### 向量化处理的核心

Parquet/ORC Reader 批量产出 N 条 record 成为一个 `ColumnarRowData` batch：

```
for (batch of 4096 rows):
  → 调用 ColumnVector 直接 getInt() / getLong() ← 无 binary 解析
  → CodeGen 化的 filter/aggregation 
  → 整体 Batch 处理，不是 row-by-row
```

---

## 21.4 — 格式转换成本

在不同算子之间流转时，两种格式有转换开销：

```
Source (ColumnarReader) → [ColumnarBatch] → Operator (如 Calc)
  → Calc 的 Columnar 过滤 → [保留在 Columnar]
  → 到达 Shuffle 边界 → [转换为 BinaryRowData] → ResultPartition
```

格式转换时机：
- `SortMergeJoin` → 用 BinaryRowData（固定布局便于 binary sort）
- `HashAgg` → 用 BinaryRowData（便于 key extract）
- `ColumnarToRow` / `RowToColumnar` — Flink 内部的 TwoWayAdaptor

源码：`flink-table-runtime/.../data/util/ColumnarToRowUtil.java`

---

## 21.5 — 横向对比

### vs Spark UnsafeRow + ColumnarBatch

Spark 的 `UnsafeRow` 是 BinaryRowData 的等价——固定长度+可变长节，基于 `MemoryBlock`（类似 MemorySegment）。`ColumnarBatch` 是 ColumnarRowData 的等价——都是 WritableColumnVector 批次。

两者与 Spark 的接近度极相似。唯一区别：Flink 的 `RowData` 接口在流处理中添加了 `RowKind`（INSERT/UPDATE/DELETE），以支持 CDC/Changelog 语义。

### vs 列存引擎 (ClickHouse/StarRocks)

ClickHouse 天然 C++ 列存——不需要 JVM 的 Binary/Columnar 双标——直接就是连续的 Column Block。ColumnarRowData 的 0 行格式其实是模仿 ClickHouse 的 Block 结构（多列向量 + 同一行对应 index）。

---

## 本章要点回顾

1. `RowData` = Flink SQL 的共同抽象数据接口——行存（BinaryRowData）和列存（ColumnarRowData）。
2. BinaryRowData = Header + 固定长块 + 偏移表 + 变长块——全在一个 MemorySegment 里。
3. ColumnarRowData = 逻辑行在列向量上的视图——适合批量向量化处理（Parquet/ORC）。
4. 格式转换发生在算子和 Shuffle 边界——Columnar→Row（shuffle） vs Row→Columnar（scan）。

## 源码导航

- RowData 接口：`flink-table-common/.../data/RowData.java`
- BinaryRowData：`flink-table-runtime/.../data/binary/BinaryRowData.java`
- ColumnarRowData：`flink-table-common/.../data/columnar/ColumnarRowData.java`
- ColumnVector：`flink-table-common/.../data/columnar/ColumnVector.java`
- ColumnarToRow：`flink-table-runtime/.../data/util/ColumnarToRowUtil.java`
