# 第 2 章 · 自包含与类型系统：为什么 Flink 要自己管理一切

## 导读

- **一句话**：本章回答"Flink 为什么不像 Spark 那样依赖 JVM 序列化/GC/堆内存，而要将序列化、类型表示、内存管理全部自行实现"。
- **前置知识**：Java 序列化机制、JVM 内存模型（堆 vs 直接内存）、泛型类型擦除。
- **读完本章你能回答**：
  - `TypeInformation` 的核心抽象——从 `isBasicType()` 到 `createSerializer()`，它解决了什么问题？
  - Flink 为什么不信任 JVM GC 而要搞自己的 `MemorySegment`？
  - `MemorySegment` 的 `heapMemory` / `offHeapBuffer` / `address` 三字段如何统一堆内/堆外？
  - `sun.misc.Unsafe` 在 MemorySegment 中的作用
  - 序列化层如何支持 State 的 Schema Evolution？

---

## 2.1 — 设计动机：JVM 是能力也是负担

### JVM 的"恩赐"与"诅咒"

Flink 选择 JVM 作为运行时平台：一次编写到处运行、丰富的类库、成熟的 GC。但对于计算引擎来说，JVM 天生有三件事不利于高性能数据处理：

1. **对象头开销**：一个 `java.lang.Integer` = 16 bytes（12 byte 对象头 + 4 byte int，64位压缩指针）——对比原始 int 只需 4 bytes。处理十亿条记录时，4x 的内存膨胀是灾难性的。
2. **GC 不可控**：GC pause 会直接导致反压、checkpoint 超时。如果用堆大量存放数据，GC 就是一颗定时炸弹。
3. **序列化**：Java 原生序列化慢且体积大。Kryo 虽好，但需要 Schema 信息才能反序列化——Flink 需要自己理解数据的 Schema 来做高效的二进制比较、join key 提取等。

### Flink 的回应：三件事自己干

| 问题域 | Flink 方案 | 对应模块 |
|--------|-----------|---------|
| 数据表示 | 自建类型体系 `TypeInformation` → `TypeSerializer` | `flink-core/.../typeinfo` / `typeutils` |
| 内存管理 | 自管二进制内存段 `MemorySegment`，堆外优先 | `flink-core/.../memory` |
| 序列化 | 基于 `TypeSerializer` 的二进制序列化，全链路直写而非反射 | `flink-core/.../typeutils` |

**一句话概括**：Flink 把自己的数据从 JVM 对象系统中抽离出来，自行掌控二进制表示的完全生命周期。

---

## 2.2 — 类型系统：TypeInformation 与 TypeSerializer

### Java 泛型擦除的困境

```java
// 这段代码在 JVM 里，K 和 V 在运行时全部擦除为 Object
public class MyMapFunction implements MapFunction<Tuple2<String, Long>, String> {
    public String map(Tuple2<String, Long> value) { ... }
}
```

Flink 需要知道 `K = String, V = Long` 才能：
- 决定如何序列化 Tuple2
- 在 keyBy 时高效提取 key 并计算 hash
- 在 State 序列化/反序列化时不依赖 Kryo 的反射

### TypeInformation：编译期类型在运行时的存在

`TypeInformation<T>` 是 Flink 类型系统的核心抽象（`flink-core/.../api/common/typeinfo/TypeInformation.java`）：

```java
public abstract class TypeInformation<T> implements Serializable {
    // 类型分类查询
    public abstract boolean isBasicType();
    public abstract boolean isTupleType();
    public abstract int getArity();           // 直接字段数
    public abstract int getTotalFields();      // 递归展平后的总字段数
    public abstract Class<T> getTypeClass();
    public abstract boolean isKeyType();       // 能否作为 key（需 hashable + comparable）

    // 核心：创建序列化器
    public abstract TypeSerializer<T> createSerializer(SerializerConfig config);

    // 泛型参数映射
    public Map<String, TypeInformation<?>> getGenericParameters() {
        return Collections.emptyMap();
    }
}
```

**关键设计点**：`getArity()` vs `getTotalFields()` 的区别。

```java
// 示例来自 TypeInformation 源码 Javadoc:
class InnerType { int id; String text; }     // arity=2, totalFields=2
class OuterType { long timestamp; InnerType nestedType; }  // arity=2, totalFields=3
```

`arity` 是直接字段数，`totalFields` 是递归展平后的总字段数。Flink 内部用 `totalFields` 来计算 key 的偏移量——比如 `keyBy("nestedType.id")` 知道这个 key 在展平后的第 2 个位置。

关键子类：

| TypeInfo 子类 | 对应 Java 类型 | 典型场景 |
|----------------|---------------|---------|
| `BasicTypeInfo` | Integer, Long, String 等基本类型 | 简单字段 |
| `TupleTypeInfo` | `Tuple2`, `Tuple3` ... | DataStream 常用 |
| `PojoTypeInfo` | 任何 POJO | 面向对象的用户代码 |
| `RowTypeInfo` | `Row` | Table API 的行 |
| `ListTypeInfo` / `MapTypeInfo` | `List`, `Map` | 嵌套集合 |
| `GenericTypeInfo` | 其它一切 | 最终 fallback 到 Kryo |

### TypeExtractor：如何从擦除的泛型中恢复类型信息

用户不需要手动声明 `TypeInformation`——Flink 的 `TypeExtractor` 通过反射分析你写的 Lambda / 匿名类签名来推导类型。

流程：
```
1. 分析函数签名上的泛型参数
   e.g. MapFunction<Tuple2<String, Long>, String>
2. 递归解析泛型参数的具体类型
3. 为最外层类型创建 TypeInformation
4. 对嵌套类型递归创建并组装
```

**什么时候会失败？** Lambda 表达式如果类型参数不够明确（比如 `Collector<T>` 中的 T 无法推断），TypeExtractor 会 fallback 到返回 `GenericTypeInfo`——最终使用 Kryo 序列化。Kryo 是个优秀的框架，但它的序列化格式是"黑盒"的——Flink 无法理解里面的结构来做 key 提取等优化。

### TypeSerializer：Flink 自己的序列化协议

每个 `TypeInformation` 可以创建一个 `TypeSerializer<T>`：

```java
// 核心接口
public abstract class TypeSerializer<T> {
    public abstract T createInstance();
    public abstract T copy(T from);
    public abstract T copy(T from, T reuse);
    public abstract void serialize(T record, DataOutputView target) throws IOException;
    public abstract T deserialize(DataInputView source) throws IOException;
    public abstract T deserialize(T reuse, DataInputView source) throws IOException;
    // ...
}
```

关键方法对比：

| 方法 | 语义 | 适用场景 |
|------|------|---------|
| `serialize()` | 对象 → 二进制 | 网络传输、写磁盘 |
| `deserialize()` | 二进制 → 对象 | 读网络/磁盘 |
| `copy(from)` | 对象 → 对象拷贝 | State 复制（不经过序列化） |
| `copy(from, reuse)` | 拷贝并复用对象 | 减少对象分配 |

`copy()` 是 Flink 序列化体系的独特优势——在很多场景（例如网络缓冲复制、State 复制）中，Flink 不需要走"反序列化成对象 → 修改 → 重新序列化"的路径——直接用 `copy()` 方法在对象层完成复制，或者直接在二进制层完成（zero-deserialization copy）。

### CompositeTypeSerializer 和嵌套结构

对于 `Tuple2`、`Row`、`Pojo` 这种复合类型，`TypeSerializer` 是**分解式**的：

```
Tuple2<String, Long> serializer
  fieldSerializers[0]: StringSerializer
  fieldSerializers[1]: LongSerializer
// Tuple2 的 serialize() 内部调用 fieldSerializers[0].serialize(f0) + fieldSerializers[1].serialize(f1)
```

这是一个朴素但高效的设计：对比 XML/JSON 序列化中的自描述协议，Flink 的二进制格式**简约到极致**——没有 field name、没有 type tag，只有顺序知道这是什么字段。

---

## 2.3 — MemorySegment：Flink 对 JVM 堆的叛逃

### 源码级设计

`MemorySegment` 是 Flink 自定义的二进制缓冲区。源码在 `flink-core/.../core/memory/MemorySegment.java`：

```java
public final class MemorySegment {
    // 堆内：byte[] 引用（非 null 时表示堆内）
    @Nullable private final byte[] heapMemory;

    // 堆外：Direct ByteBuffer 引用（非 null 时表示堆外）
    @Nullable private ByteBuffer offHeapBuffer;

    // 统一地址：堆内 = BYTE_ARRAY_BASE_OFFSET，堆外 = absolute address
    private long address;

    // 地址上限 = address + size（越界检查用）
    private final long addressLimit;

    // 大小（字节）
    private final int size;

    // 所有者（如 NetworkBufferPool）
    @Nullable private final Object owner;

    // 释放标记
    private final AtomicBoolean isFreedAtomic;
}
```

**关键设计**：`address` 是统一寻址的关键——堆内时它是 `BYTE_ARRAY_BASE_OFFSET`（`Unsafe.arrayBaseOffset(byte[].class)`），堆外时它是 `ByteBuffer` 的 native address。所有 `putInt()`/`getLong()` 方法都通过 `address + offset` 计算，**同一个方法体同时支持堆内和堆外**——不需要 if-else 分支。

### Unsafe 的角色

```java
// MemorySegment 使用 sun.misc.Unsafe 做原生级内存操作
private static final sun.misc.Unsafe UNSAFE = MemoryUtils.UNSAFE;
private static final long BYTE_ARRAY_BASE_OFFSET = UNSAFE.arrayBaseOffset(byte[].class);

// 读一个 long（64 bit）——堆内堆外完全统一
public long getLong(int offset) {
    final long pos = address + offset;
    if (pos >= addressLimit || pos < address) {
        throw new IndexOutOfBoundsException(...);
    }
    return UNSAFE.getLong(heapMemory, pos);  // heapMemory=null 时走 native path
}
```

**为什么用 Unsafe 而不是 ByteBuffer？**
1. **统一寻址**：`UNSAFE.getLong(heapMemory, pos)` 在 `heapMemory != null` 时自动读堆内，`heapMemory == null` 时自动读 native address——零分支。
2. **无边界检查**：ByteBuffer 每次操作都做 boundary check——MemorySegment 自己做一次 `addressLimit` 检查就够了。
3. **byte order 优化**：`LITTLE_ENDIAN` 是 static final boolean——JIT 编译器会直接消除不匹配的分支。

### 为什么不用 `java.nio.ByteBuffer` 直接操作

ByteBuffer 的抽象层次比 MemorySegment 低——它可以满足 API 需求，但 Flink 在 ByteBuffer 之上包了一层的主要原因是：

1. **统一的堆内/堆外接口**：不需要在代码里 ∞ if-else `isDirect()` 判断
2. **跨 Buffer 边界的比较/拷贝**：Flink 的 Sort 算法在一个 MemorySegment 满了以后要跨 Segment 比较，ByteBuffer 没有现成的工具
3. **内存所有权管理**：MemorySegment 被 `Buffer` 包装在 Network Stack 中，带有引用计数和释放回调

### 内存层级全景

```
                    ┌──────────────────────────────────┐
                    │       TaskManager JVM Process      │
                    ├──────────────────────────────────┤
                    │  Heap Memory                       │
                    │  ├─ Framework Heap (RPC, etc.)     │
                    │  └─ Task Heap (user code)          │
                    ├──────────────────────────────────┤
                    │  Direct Memory (堆外)              │
                    │  ├─ Network Buffer Pool            │  ← MemorySegment (offHeapBuffer)
                    │  │   └─ LocalBufferPool x N        │
                    │  └─ Framework Direct                │
                    ├──────────────────────────────────┤
                    │  Native Memory (JVM 不可见)        │
                    │  └─ RocksDB State Backend           │  ← C++ 内存
                    └──────────────────────────────────┘
```

---

## 2.4 — 横向对比

### vs Spark Tungsten

| 维度 | Spark Tungsten | Flink |
|------|---------------|-------|
| **目标** | 将 Java 对象替换为 UnsafeRow | 全链路掌控二进制表示 |
| **核心抽象** | `UnsafeRow`（基于 `sun.misc.Unsafe`） | `MemorySegment`（基于 `byte[]` 或 `ByteBuffer`） |
| **堆外** | 可选 | 默认堆外 |
| **序列化** | 部分（仅在 Shuffle 和 Cache 路径） | 全局（Network/State/Disk 全部走 TypeSerializer） |
| **代码生成** | WholeStageCodeGen | Janino 动态编译代码段 |

Tungsten 的思路是"在关键路径上避开 Java 对象"。但 Spark 在大多数路径上（例如 UDF 调用）仍然要把 `UnsafeRow` 转换成具体的 Java 对象，这意味着序列化/反序列化是"按需"发生的。**Flink 更进一步：整个运行时管道都是 `TypeSerializer` 驱动的，序列化发生在记录进入管道的瞬间**——之后在管道中转递的过程中，所有操作都在二进制层面进行。

### vs StarRocks/MaxCompute (C++ 引擎)

C++ 引擎没有 JVM 的掣肘，所以不需要这整个层次。它们的内存管理直接就是 `new / delete` 或 `std::shared_ptr` 加上自己管理 Arena/Buffer。

Flink 的 MemorySegment 用 `Unsafe` 统一寻址——本质上是在 Java 里**模拟了 C++ 的裸指针操作**。`address` 就是 C++ 中的 `char*`，`addressLimit` 就是 `char* + size`，`UNSAFE.getLong()` 就是 `*(long*)(ptr + offset)`。

---

## 2.5 — 调优与实战陷阱

### 最常见问题："用 Lambdas → TypeExtractor → fallback 到 Kryo"

如果你在 IDE 中看到警告 `"Type information could not be derived from the lambda"`，你的算子类型会被归结为 GenericType，全链路用 Kryo 序列化。Kryo 的吞吐比 Flink 自定义序列化器低 3-5 倍，且 Kryo 产出的二进制不明结构，Flink 没法做 state 迁移。

解决方案：
```java
// 写法1：实现 ResultTypeQueryable
public class MyMapper implements MapFunction<...>, ResultTypeQueryable<...> { ... }

// 写法2：使用 returns() 声明
dataStream.map(x -> ...).returns(Types.TUPLE(Types.STRING, Types.LONG));
```

### 堆外内存不够

Exception：`java.lang.OutOfMemoryError: Direct buffer memory`

原因：Network Buffer Pool 需要的 Direct Memory 超出了 JVM 分配上限。调优参数：
```yaml
taskmanager.memory.network.min: 64mb
taskmanager.memory.network.max: 1gb
taskmanager.memory.network.fraction: 0.1  # TM 总内存的 10% 给网络
```

### State 序列化从 Kryo 移到 Flink Serializer 怎么办

Kryo 序列化的 State 是基于 Java Serialization UID 的——如果你改了类的包名或者给一个字段改了类型名，Kryo 无法读取旧 State。而 Flink Serializer 支持 `TypeSerializerSnapshot` 机制——你可以显式定义 Schema 迁移路径。这部分在第 14 章展开。

---

## 本章要点回顾

1. **自包含设计的第一性原理**：Flink 不信任 JVM 的 GC 和序列化——数据流中的所有记录都经过自己的类型系统和二进制表示。
2. `TypeInformation` **克服了 Java 泛型擦除**：它是"编译时类型在运行时的存在"——`getArity()` vs `getTotalFields()` 的区分支撑了 key 路径解析。
3. `MemorySegment` **是 Flink 的"first-class memory citizen"**：`heapMemory` / `offHeapBuffer` / `address` 三字段统一了堆内/堆外的寻址，通过 `Unsafe` 实现零分支的内存访问。
4. **序列化器是分拆的**：复合类型的 serializer 由子字段 serializer 组合而成——这让 Flink 能高效提取嵌套字段的值，以及支持 state schema evolution。
5. 对比 Tungsten：Flink 的二进制控制范围更全——所有数据通路（网络/状态/磁盘）都走 TypeSerializer；Spark 只在 shuffle 和 cache 路径替换对象。

## 源码导航

- TypeInformation 抽象：`flink-core/.../api/common/typeinfo/TypeInformation.java`（80 行起）
- TypeSerializer 抽象：`flink-core/.../api/common/typeutils/TypeSerializer.java`
- MemorySegment：`flink-core/.../core/memory/MemorySegment.java`（`heapMemory`/`offHeapBuffer`/`address` 在 104-126 行）
- MemoryUtils (Unsafe)：`flink-core/.../core/memory/MemoryUtils.java`
- NetworkBufferPool：`flink-runtime/.../io/network/buffer/NetworkBufferPool.java`
- LocalBufferPool：`flink-runtime/.../io/network/buffer/LocalBufferPool.java`
