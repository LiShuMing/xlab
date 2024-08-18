# 第 12 章：Tungsten — 硬件感知的内存与计算引擎

## 设计动机

2014 年，Spark 团队在 SIGMOD 上发表了 Project Tungsten 的愿景：**"把硬件性能用到极致"**。当时 Spark 面临一个尴尬的现实：它在 TPC-DS 基准测试中的性能比专有 MPP 数据库慢了数倍，而瓶颈不是 I/O——是 CPU 和内存。

具体来说，JVM 上的数据处理面临四大开销：

1. **对象头开销**：一个 Java Integer 对象占 16-24 字节（对象头 + 引用），而原始 int 只需要 4 字节。1000 万行数据，光是装箱就浪费了 120-200MB
2. **GC 压力**：不可变对象模型 + 频繁的中间结果分配 → GC pause 频繁
3. **虚函数调用**：Volcano 迭代器模型的 `next()` 调用链 → 分支预测失败 → pipeline stall
4. **Cache 不友好**：Java 对象在 Heap 上随机分布 → 空间局部性差 → cache miss 率高

Tungsten 的目标不是替换 JVM——Spark 仍然运行在 JVM 上——而是 **绕过 JVM 的开销路径**。它的策略分为三个层次：

1. **Binary Row（UnsafeRow）**：替换 Java 对象的行表示，使用 off-heap/on-heap byte array + `sun.misc.Unsafe` 直接操作内存
2. **手动内存管理**：绕过 GC，使用显式分配/释放（类似 C 的 malloc/free）
3. **Code Generation**：将解释执行的表达式求值替换为运行时编译的 Java 代码（第 13 章详细讨论）

Tungsten 的设计哲学是 **"知道自己在操作什么"**——不依赖 JVM 的自动内存管理，不依赖虚函数分发，不依赖对象封装。这种"裸机思维"是数据库引擎工程师第一次可以在 JVM 平台上享受到接近 C++ 的内存控制能力。

## 核心原理

### 12.1 UnsafeRow — 二进制行格式

`UnsafeRow` 是 Tungsten 的核心数据结构——它用一块连续的 byte array 表示一行，完全绕过 Java 对象。二进制格式的设计如下：

```
[null-tracking bit set] [8-byte words: fixed-length values] [variable-length portion]
```

一个包含 3 列 (INT, STRING, LONG) 的 UnsafeRow 在内存中的布局：

```
字节 0-7:   null bitmap (8 bytes, 对齐到 8 字节边界)
字节 8-15:  col0: int value (4 bytes, 直接存储)
字节 16-23: col1: offset<<32 | size  (相对基址的偏移 + 长度)
字节 24-31: col2: long value (8 bytes, 直接存储)
字节 32+:   col1 的实际字符串数据 "hello, world"
```

```java
// UnsafeRow.java:63
public final class UnsafeRow extends InternalRow {
  public static final int WORD_SIZE = 8;

  private Object baseObject;   // byte[] 或 null(off-heap)
  private long baseOffset;     // 基地址
  private int numFields;       // 列数
  private int sizeInBytes;     // 行总大小
  private int bitSetWidthInBytes;  // null bitmap 宽度

  private long getFieldOffset(int ordinal) {
    return baseOffset + bitSetWidthInBytes + ordinal * 8L;
  }
}
```

**每条 UnsafeRow 存储在一个 8 字节的 slot** 中——对于固定长度类型（int、long、double），值直接存储在 slot 里。对于可变长度类型（String、binary、array、struct），slot 存储 `(offset << 32) | length` 的复合值——指向可变长度区域的指针。

`pointTo` 方法的语义是 **"将 UnsafeRow 对象视为指向已有内存的指针"**：

```java
// UnsafeRow.java:159
public void pointTo(Object baseObject, long baseOffset, int sizeInBytes) {
  this.baseObject = baseObject;
  this.baseOffset = baseOffset;
  this.sizeInBytes = sizeInBytes;
}
```

这意谓 UnsafeRow 本身是一个"轻量 view"——不拥有数据，只指向数据。Row 的拷贝是 `Platform.copyMemory()` 一次 `memcpy`：

```java
// UnsafeRow.java:502
public UnsafeRow copy() {
  UnsafeRow rowCopy = new UnsafeRow(numFields);
  final byte[] rowDataCopy = new byte[sizeInBytes];
  Platform.copyMemory(baseObject, baseOffset, rowDataCopy, BYTE_ARRAY_OFFSET, sizeInBytes);
  rowCopy.pointTo(rowDataCopy, BYTE_ARRAY_OFFSET, sizeInBytes);
  return rowCopy;
}
```

**哈希和相等比较**直接在二进制级别进行，不读出各列：

```java
// UnsafeRow.java:570
public int hashCode() {
  return Murmur3_x86_32.hashUnsafeWords(baseObject, baseOffset, sizeInBytes, 42);
}

public boolean equals(Object other) {
  if (other instanceof UnsafeRow o) {
    return (sizeInBytes == o.sizeInBytes) &&
      ByteArrayMethods.arrayEquals(baseObject, baseOffset, o.baseObject, o.baseOffset, sizeInBytes);
  }
  return false;
}
```

**为什么在二进制上计算 hash？** 因为"一行"在 Hash Aggregate 或 Hash Join 中唯一的操作就是 `hashCode()` 和 `equals()`。不读出各列值→不需要列的类型信息→单条 `memcmp` 完成所有比较→约 10-20 个 CPU 周期完成。

关键在于这种设计的 **零反序列化开销**：数据从 shuffle write 落盘到 shuffle read 读取到 hash table 查询，全程保持 UnsafeRow 二进制格式，永不"解包"为 Java 对象。

### 12.2 Platform — JVM 的 unsafe 层

`Platform` 是 Tungsten 与 JVM 底层 `sun.misc.Unsafe` 之间的桥梁：

```java
// Platform.java:28
public final class Platform {
  private static final Unsafe _UNSAFE;

  static {
    Field unsafeField = Unsafe.class.getDeclaredField("theUnsafe");
    unsafeField.setAccessible(true);
    unsafe = (sun.misc.Unsafe) unsafeField.get(null);
    _UNSAFE = unsafe;
  }

  public static long allocateMemory(long size) { return _UNSAFE.allocateMemory(size); }
  public static void freeMemory(long address) { _UNSAFE.freeMemory(address); }
  public static void copyMemory(Object src, long srcOffset, Object dst, long dstOffset, long length) { ... }
  public static int getInt(Object object, long offset) { return _UNSAFE.getInt(object, offset); }
  public static void putInt(Object object, long offset, int value) { _UNSAFE.putInt(object, offset, value); }
  ...
}
```

`Platform.copyMemory` 是性能关键路径——它被 Shuffle Write、Row Serialization、Hash Table probing 频繁调用。Spark 的 `copyMemory` 有一个自适应方向优化：

```java
// Platform.java:253-277
public static void copyMemory(Object src, long srcOffset, Object dst, long dstOffset, long length) {
  if (dstOffset < srcOffset) {
    // forward copy: dst 在 src 之前，从低地址向高地址拷贝
    while (length > 0) { ... _UNSAFE.copyMemory(src, srcOffset, dst, dstOffset, size); ... }
  } else {
    // backward copy: dst 在 src 之后，从高地址向低地址拷贝（防止覆盖未拷贝数据）
    srcOffset += length; dstOffset += length;
    while (length > 0) { srcOffset -= size; dstOffset -= size; _UNSAFE.copyMemory(...); }
  }
}
```

这个方向选择确保了"src 和 dst 有重叠"的安全（类似 `memmove` 的语义）。

同时 `Platform` 还有一个关键的批量拷贝阈值：

```java
private static final long UNSAFE_COPY_THRESHOLD = 1024L * 1024L; // 1MB
```

每次 `_UNSAFE.copyMemory` 最多拷贝 1MB——这是为了使大副本中有 safepoint polling 点。否则 JVM 的 GC safepoint 会一直等待 unsafe copyMemory 返回，导致长 GC 暂停。

### 12.3 Off-Heap 内存管理

Tungsten 的内存管理系统是一组逐步抽象的内存管理组件：

**MemoryBlock**：

```java
// 表示一块连续内存区域
public class MemoryBlock {
  public Object obj;     // null 表示 off-heap，byte[] 表示 on-heap
  public long offset;    // 该块在 obj 或 off-heap 中的起始地址
  public long length;    // 块大小（字节）
}
```

**MemoryAllocator**：分配和释放 MemoryBlock 的接口。有两种实现：

- **HeapMemoryAllocator**：在 JVM heap 上分配 `byte[]`。分配快（不需要 `Unsafe.allocateMemory`），但受 GC 影响。
- **UnsafeMemoryAllocator**：通过 `Unsafe.allocateMemory(size)` 在 off-heap 分配。不受 GC 管理，但需要显式 `freeMemory`。

```java
// UnsafeMemoryAllocator
public MemoryBlock allocate(long size) {
  long address = Platform.allocateMemory(size);
  return new MemoryBlock(null, address, size);
}
```

**MemoryConsumer**：内存的使用者（Task 内部的算子）。每个 MemoryConsumer 分配 pages。当内存不足时，通过 `spill()` 溢写到磁盘。

**TaskMemoryManager**：每个 Task 有自己的 TaskMemoryManager，负责：
- 从 Executor 的 `MemoryManager` 获取或释放内存
- 在同一 Task 内的多个 MemoryConsumer 之间协调 spill 顺序
- 对 UnsafeRow 的 8 byte page number + offset 内部寻址（用于MemoryStore shuffle 排序）

**关键的内存组织**：Heap 内存分配快但不可控（谁也不知道 GC 何时回收）；Off-heap 内存可控但分配慢（JNI 调用 `malloc`）。Tungsten 的选择是 **默认用 Heap + Unsafe 操作**（`baseObject = new byte[]`），在需要绝对可控的场景（如大量 UnsafeRow hash table）中切换到 Off-heap。

### 12.4 Unsafe 数组与复杂类型

Tungsten 的 Unsafe 体系不仅包括 UnsafeRow，还包括 UnsafeArrayData 和 UnsafeMapData：

**UnsafeArrayData** 的二进制格式：

```
[8 bytes: numElements] [null bitmap for elements] [8-byte words per element] [variable-length data]
```

**UnsafeMapData** 存储为两个 UnsafeArrayData——keys 和 values，长度相同。格式：

```
[8 bytes: size] [keys (UnsafeArrayData 格式)] [values (UnsafeArrayData 格式)]
```

所有这些复杂类型都支持 "pointTo" 语义——一行 UnsafeRow 中的 Array 列，通过 `getArray(ordinal)` 返回一个 UnsafeArrayData，它直接指向 UnsafeRow 的 variable-length 区域的子区域。**零拷贝、零解包**。

### 12.5 TungstenAggregation — 基于 UnsafeRow 的 Hash 聚合

在 Tungsten 出现之前，Spark 的 HashAggregate 使用 Java `HashMap<Row, Buffer>`。这有巨大的开销：Row 对象、HashMap.Entry 对象、Integer 包装、GC。

TungstenAggregation 完全替换了这个方案——它使用 **Off-Heap / Unsafe 字节数组** 实现的 HashTable：

核心结构是 `BytesToBytesMap`——一个 **开放寻址（open-addressing）线性探测** 的哈希表，键和值都是 UnsafeRow 二进制数据：

```
Hash Table 布局（连续的内存页）:
[page 0]: ... key1_length | key1_bytes | value_bytes | key2_length | key2_bytes | value_bytes...
[page 1]: ... (当 page 0 满时分配)
```

查找过程：
1. 对 key 的 UnsafeRow 计算 hash（Murmur3）
2. 使用 hash 定位到 page 和 offset
3. 比较存储的 key_bytes 和输入 key_bytes（`memcmp` 级别）
4. 匹配 → 更新 value；不匹配 → 线性探测下一个位置

**与 Java HashMap 的关键区别**：
- 键和值连续存储在一起，每次探测只有 1-2 次 cache miss（Java HashMap 有指针追逐）
- Hash Equal 是 bulk binary comparison，不是逐个列的类型化比较
- 内存是手动管理的——需要 spill 时直接 `copyMemory` 到磁盘，回收无需等 GC

**Spill 机制**：

当 hash table 增长超出内存限制时，TungstenAggregation 不是分配更大的表，而是将当前 hash table 的内容按键排序，溢写到磁盘，然后开始新的空 hash table。最终读取多个 spill 文件做归并聚合。

为什么排序溢写而不是简单序列化？因为排序后等值 key 在文件中是连续存储的——后续的归并阶段只需要顺序读取，不需构建完整 hash table。这对内存的需求降到 O(k) 而不是 O(n)。

### 12.6 Variant/JSON 类型的 Unsafe 支持

Spark 4.0 引入了 Variant 类型（对标 BigQuery SQL JSON 类型），Tungsten 提供了 `VariantVal`——一个完全二进制化的 JSON 表示：

```java
// UnsafeRow.java:450
public VariantVal getVariant(int ordinal) {
  if (isNullAt(ordinal)) return null;
  return VariantVal.readFromUnsafeRow(getLong(ordinal), baseObject, baseOffset);
}
```

VariantVal 不解析 JSON 文本——它在二进制层面索引 JSON 路径（类似 Parquet/ORC 的 shredded column 编码）。这使得 `getVariant("$.user.name")` 路径提取像一个 Binary Search（O(log N)）而不是 JSON Parse（O(N)）。

## 关键代码片段

### 示例：HashAggregateExec 使用 Tungsten 的完整链路

```scala
// TungstenAggregationIterator 的核心循环

// 1. 输入行是 UnsafeRow 格式
while (inputIter.hasNext) {
  val inputRow = inputIter.next()  // UnsafeRow (pointing to shuffle data or previous stage)

  // 2. 生成 aggregation key (UnsafeRow)
  // 将 Grouping Key 列的值复制到 output key
  groupingProjection.target(row, key)  // key = new UnsafeRow

  // 3. 在 BytesToBytesMap 中查找或创建 entry
  val loc = hashMap.lookup(key)  // binary hash + memcmp

  if (loc.isDefined) {
    // 4a. 已存在: 更新 aggregation buffer
    val buffer = loc.getValueAddress  // 指向 hash table 内部的内存地址
    aggFunctions.foreach(fn => fn.update(buffer, inputRow))
  } else {
    // 4b. 不存在: 创建新 entry
    val newLoc = hashMap.insert(key)
    val buffer = newLoc.getValueAddress
    aggFunctions.foreach(fn => fn.initialize(buffer))  // 初始化
    aggFunctions.foreach(fn => fn.update(buffer, inputRow))  // 聚合并第一次值
  }
}
```

### 示例：Murmur3 哈希函数的使用

```java
// Murmur3_x86_32.hashUnsafeWords — 直接在二进制数据上计算 hash
public static int hashUnsafeWords(Object base, long offset, int lengthInBytes, int seed) {
  // 读取 UnsafeRow 的二进制区域，每 4 字节处理一次
  // 不需要知道 column types、schema、nullability
}
```

## 硬件视角

Tungsten 的本质是一次 **从软件到硬件的"阻抗匹配"**。

**UnsafeRow 的 Cache 友好性**：

Java Row 对象：32 列 × (12 字节对象头 + 8 字节引用) = 640 字节 + 实际数据分散在 heap 各处
UnsafeRow：bitmap(8) + fixed(32×8=256) + variable area = 约 300 字节，**全部连续**

对于 L1 cache（32KB），Java Row 只能放约 50 行；UnsafeRow 能放约 100 行。**2 倍的 L1 命中率提升**直接转化为约 1.5 倍的吞吐——因为 L1 access 是 4 cycles，L2 是 12 cycles，L3 是 40 cycles。

**Unsafe copyMemory 的 SIMD 加速**：

`Unsafe.copyMemory` 在 JVM HotSpot 中被编译为 `intrinsic`——直接展开为 CPU 的 `REP MOVS` 指令（x86/x64）或 SIMD-based memcpy（aarch64）。这意味着一次 UnsafeRow 哈希表 insert 中的 memory copy 是 **单条 CPU 指令**（不计循环开销），而不是 Java 字节码循环。

**Memory Boundedness**：

TungstenAggregation 的瓶颈是内存带宽，不是 CPU。对于一个 10GB/s 内存带宽的实例，500 列 × 10 亿行的聚合在 UnsafeRow 上的内存扫描时间是 150GB ÷ 10GB/s = 15 秒。如果是 Java Row 对象模式，往返在序列化/反序列化之间可能导致 2-5× 额外的内存拷贝和带宽消耗。

**Spill I/O 模式**：

Tungsten 的 sort-based spill 创建的是顺序 I/O 模式——按 hash key 排序后的 UnsafeRow 写入磁盘，后续顺序读取。这与随机 I/O 相比是 100-1000 倍的吞吐差（NVMe SSD: 顺序 3GB/s vs 随机 50MB/s）。

默认 Tungsten 将 spill 文件配置为 **临时文件**，利用 OS page cache。对于频繁 spill/re-load 的场景，page cache 的作用等同于内存扩展——不需要显式管理。

## AI 时代反思

Tungsten 的手动内存管理与 AI 框架（PyTorch/TensorFlow）的内存管理之间存在一个有趣的对比。

AI 框架使用 **Eager-free memory** 策略：tensor 一被使用完立即释放，依赖引用计数。Spark 则使用 **Bulk spill** 策略：不到阈值不释放，一次批量溢写。为什么？

因为数据库聚合和 Join 有 **非对称访问模式**——hash table 中 80% 的访问集中在 20% 的 key 上。在 Java HashMap 中这是自动的（热点 key 在 cache 中）。在 Unsafe HashMap 中，这 20% 的 key 也大概率已在 L1/L2 cache 中——物理页不回收意味着"未来还要用"。而在 AI 推理中，input → output 是单向的——tensor 使用后基本不会再访问。

另一个反思：**Variant 类型和 LLM 的关系**。Spark 4.0 的 Variant（二进制 JSON）的设计目标与 LLM 的 structured output 有直接关系。如果 LLM Agent 生成的输出是 Variant格式，它可以通过 Catalyst 优化的 VariantPath 提取路径进行高效过滤和聚合——不用发出 LLM API 请求来"提取 JSON 路径"。

想象一下：Agent 调用 LLM 生成一匹 JSON 文档 → Spark 将其存储为 Variant 列 → Agent 后续查询"筛选 name='John' 的文档" → Catalyst 优化器将 Variant 路径提取下推到 File Scan → **不读取整个文档，只读取相关字节范围**。

这与 RAG 中的 chunk-level 检索不同——它是列级、路径级的精确数据访问。Variant 格式使 LLM 输出成为 **结构化可查询** 的列，而不只是 blob。这可能是 "LLM Agent + Spark" 结合中最被低估的优势。

## 源码导航

| 文件 | 关键内容 | 行号参考 |
|------|---------|---------|
| `sql/catalyst/src/main/java/org/apache/spark/sql/catalyst/expressions/UnsafeRow.java` | UnsafeRow 完整实现，二进制布局，pointTo，getX/setX 方法 | 63 (类定义), 71 (calculateBitSetWidthInBytes), 118 (getFieldOffset), 159 (pointTo), 570 (hashCode), 502 (copy) |
| `common/unsafe/src/main/java/org/apache/spark/unsafe/Platform.java` | Platform 类，Unsafe 包装，copyMemory 自适应方向优化 | 28 (类定义), 187 (allocateMemory), 253 (copyMemory), 290 (UNSAFE_COPY_THRESHOLD) |
| `core/src/main/java/org/apache/spark/memory/MemoryConsumer.java` | 内存消费者抽象，spill 接口 | |
| `core/src/main/java/org/apache/spark/memory/TaskMemoryManager.java` | Task 级内存管理，分配/释放页 | |
| `core/src/main/java/org/apache/spark/memory/MemoryManager.java` | Executor 级统一内存管理 | |
| `core/src/main/java/org/apache/spark/unsafe/map/BytesToBytesMap.java` | Tungsten 哈希表，开放寻址，连续内存布局 | |
| `core/src/main/java/org/apache/spark/sql/execution/aggregate/TungstenAggregationIterator.scala` | Tungsten 聚合 Iter 实现 | |
| `sql/catalyst/src/main/java/org/apache/spark/sql/catalyst/expressions/UnsafeArrayData.java` | Unsafe 数组二进制格式 | |
| `sql/catalyst/src/main/java/org/apache/spark/sql/catalyst/expressions/UnsafeMapData.java` | Unsafe Map 二进制格式 | |
| `sql/catalyst/src/main/java/org/apache/spark/unsafe/types/VariantVal.java` | Variant 二进制格式，Spark 4.0 引入 | |
