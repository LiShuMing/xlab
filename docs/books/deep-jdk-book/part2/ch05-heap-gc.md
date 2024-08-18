# 第 5 章 堆与垃圾收集

> 源码路径：`src/hotspot/share/oops/`、`src/hotspot/share/gc/`

Java 堆是 JVM 最核心的数据结构，GC 是最复杂的子系统。本章从对象模型出发，逐一剖析五种 GC 实现，最终回到 AI 推理场景的 GC 调优实践。

---

## 5.1 `oopsHierarchy`：对象模型与 `oop` 体系

### 5.1.1 oop 类型层次

JVM 用 C++ 的类型系统精确映射 Java 对象的层次结构（`oopsHierarchy.hpp`）：

```
oop (oopDesc*)
├── instanceOop (instanceOopDesc*)       // 普通对象实例
│   └── stackChunkOop (stackChunkOopDesc*) // 虚拟线程栈块
├── arrayOop (arrayOopDesc*)             // 数组基类
│   ├── objArrayOop (objArrayOopDesc*)   // 对象数组
│   └── typeArrayOop (typeArrayOopDesc*) // 基本类型数组
```

在 `CHECK_UNHANDLED_OOPS` 模式下，`oop` 不是裸指针，而是一个包装类，会在构造/析构时注册/注销，用于检测未处理的 oop（悬空引用）。

### 5.1.2 对象头：markWord

每个 Java 对象的头部是一个 `markWord`（64 位），其布局如下：

```
64 位 markWord（正常对象）：
┌──────────────────────────────────┬──────┬──────┬──────┬──────┐
│ unused:22    hash:31             │ gap:4│age:4 │fwd:1 │lock:2│
└──────────────────────────────────┴──────┴──────┴──────┴──────┘
 63                            10  9   6  5   2  1     0

64 位 markWord（紧凑头，JDK 27 新特性）：
┌──────────────────────────────────┬──────┬──────┬──────┬──────┐
│ klass:22     hash:31             │ gap:4│age:4 │fwd:1 │lock:2│
└──────────────────────────────────┴──────┴──────┴──────┴──────┘
```

锁状态编码：

| lock 位 | 状态 | markWord 含义 |
|---------|------|--------------|
| `01` | 无锁（unlocked） | 存储身份哈希和 GC 年龄 |
| `00` | 轻量级锁（locked） | 存储锁记录指针或栈上锁引用 |
| `10` | 重量级锁（monitor） | 存储 ObjectMonitor 指针或查表索引 |
| `11` | 标记（marked） | GC 标记、转发指针等 |

**紧凑头（Compact Headers）**：JDK 27 引入的实验特性（`-XX:+UseCompactObjectHeaders`），将 `Klass*` 指针压缩到 markWord 的高 22 位中，省去了对象头中独立的 `Klass*` 字段（8 字节），每个对象节省 8 字节。对于小对象为主的工作负载，内存节省可达 10-15%。

### 5.1.3 压缩 oop（Compressed Oops）

在 64 位 JVM 上，如果堆大小 ≤ 32GB，可以使用 32 位压缩引用（`narrowOop`）：

```cpp
// compressedOops.hpp
enum Mode {
    UnscaledNarrowOop      = 0,  // 堆 < 4GB，直接使用 32 位地址
    ZeroBasedNarrowOop     = 1,  // 堆 < 32GB，偏移量 << 3
    DisjointBaseNarrowOop  = 2,  // 基址与偏移位不重叠
    HeapBasedNarrowOop     = 3,  // 需要基址 + 偏移
};
```

编码/解码公式：

```cpp
// 编码：oop → narrowOop
narrowOop encode(oop obj) {
    return (narrowOop)((address)obj - _base) >> _shift;
}

// 解码：narrowOop → oop
oop decode(narrowOop n) {
    return (oop)((address)n << _shift + _base);
}
```

`_shift` 通常是 3（`LogMinObjAlignmentInBytes`），因为对象按 8 字节对齐，低 3 位始终为零，无需存储。

**压缩 oop 的性能影响**：
- **节省内存**：引用从 8 字节减为 4 字节，对象图缩小约 40%
- **提升缓存命中率**：更紧凑的对象布局，L1/L2 缓存能容纳更多对象
- **解码开销**：每次引用访问需要一次移位+加法，但现代 CPU 可以在 1 个时钟周期内完成

---

## 5.2 `objLayout.cpp`：对象布局与字段对齐策略

### 5.2.1 对象的内存布局

```
普通对象（64 位，UseCompressedOops）：
┌─────────────────────────┐
│ markWord (8 bytes)       │  ← 对象头
├─────────────────────────┤
│ Klass* (4 bytes, 压缩)   │  ← 元数据指针
├─────────────────────────┤
│ field1 (4 bytes)         │  ← 实例字段
│ field2 (4 bytes)         │
│ ...                      │
├─────────────────────────┤
│ padding (对齐到 8 字节)   │
└─────────────────────────┘

数组对象：
┌─────────────────────────┐
│ markWord (8 bytes)       │
├─────────────────────────┤
│ Klass* (4 bytes)         │
├─────────────────────────┤
│ length (4 bytes)         │  ← 数组长度
├─────────────────────────┤
│ element0                 │  ← 数组元素
│ element1                 │
│ ...                      │
└─────────────────────────┘
```

### 5.2.2 字段重排序

JVM 会在类初始化时对字段进行重排序（`fieldLayoutBuilder.cpp`），优化布局：

1. 引用字段聚集在一起（减少 GC 扫描的内存范围）
2. 长整型/双精度字段对齐到 8 字节边界
3. 短整型/整型字段填充间隙
4. 父类字段排在前面

---

## 5.3 分代假说与 GC 共同抽象

### 5.3.1 分代假说

JVM GC 的理论基础是「分代假说」：
1. **弱分代假说**：大多数对象很快变为不可达
2. **强分代假说**：越老的对象越可能继续存活

基于此，JVM 将堆分为 Young（Eden + Survivor）和 Old 两代，新对象在 Young 分配，存活足够久后晋升到 Old。

### 5.3.2 GC 共享抽象（`gc/shared/`）

`gc/shared/` 定义了所有 GC 的公共基础设施：

| 组件 | 文件 | 职责 |
|------|------|------|
| `CollectedHeap` | `collectedHeap.cpp` | 堆的抽象接口 |
| `BarrierSet` | `barrierSet.cpp` | 读写屏障的抽象 |
| `GCConfig` | `gcConfig.cpp` | GC 选择逻辑 |
| `OopStorage` | `oopStorage.cpp` | GC 管理的 oop 容器 |
| `PLAB` | `plab.cpp` | Promotion Local Allocation Buffer |
| `TaskTerminator` | `taskTerminator.cpp` | 并行任务终止协议 |
| `ReferenceProcessor` | `referenceProcessor.cpp` | 引用处理（Soft/Weak/Phantom） |

---

## 5.4 Serial GC：最简实现，理解 GC 的起点

Serial GC（`gc/serial/`）是最简单的 GC 实现，单线程执行所有操作：

```
堆布局：
┌──────────────────────┬──────────────────────┐
│   Young Generation    │   Old Generation     │
│ ┌───────┬─────┬─────┐│                      │
│ │ Eden  │ S0  │ S1  ││                      │
│ └───────┴─────┴─────┘│                      │
└──────────────────────┴──────────────────────┘

Young GC：标记-复制（Eden + S0 → S1）
Full GC：标记-清除-压缩（全堆）
```

Serial GC 的价值不在于性能，而在于作为 GC 的参考实现——所有更复杂的 GC 都在 Serial GC 的基础上增加了并行和并发机制。

---

## 5.5 Parallel GC：吞吐量优先的并行标记-复制

Parallel GC 在 Serial GC 基础上增加了多线程并行：

- **Young GC**：多个 GC 线程并行执行标记-复制
- **Full GC**：多个 GC 线程并行执行标记-清除-压缩

适用场景：批处理、离线计算，关注吞吐量而非延迟。

---

## 5.6 G1 GC：Region 化设计与混合收集

### 5.6.1 Region 化堆布局

G1 将堆划分为大小相等的 Region（1-32MB，默认为堆/2048）：

```
┌─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┐
│ E   │ E   │ S   │ O   │ O   │ H   │ E   │ O   │
└─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┘
  E=Eden  S=Survivor  O=Old  H=Humongous

Region 大小 = max(1MB, min(32MB, heap/2048))
```

**Humongous Region**：当对象大小超过 Region 的 50% 时，使用连续的 Humongous Region 存储。

### 5.6.2 混合收集

G1 的核心创新是「混合收集」——不只收集 Young 区，还收集回收价值最高的 Old Region：

```
Young GC:  回收所有 Eden + Survivor Region
Mixed GC:  回收所有 Young + 部分 Old Region（CSet 选择）
Full GC:   全堆压缩（退化场景）
```

**CSet（Collection Set）选择算法**：

G1 为每个 Region 维护一个「回收价值」指标：

```
回收价值 = Region 中垃圾比例 / 预计回收时间

选择目标：在设定的最大暂停时间（-XX:MaxGCPauseMillis）内，
选择回收价值最高的 Region 组成 CSet。
```

### 5.6.3 写屏障与 RSet

G1 使用写前屏障（pre-barrier）维护 RSet（Remember Set），记录跨 Region 引用：

```cpp
// g1BarrierSet.cpp
// 每次引用写入时：
void write_ref_field_pre(oop* field, oop new_val) {
    // 记录 field 所在 Region → 引用来源 Region 的映射
    // 用于 GC 时不需要扫描整个堆找跨代引用
}
```

RSet 使 G1 可以独立回收任意 Region 组合，而不需要全堆扫描。这是 G1 Region 化设计的关键支撑。

---

## 5.7 ZGC：着色指针与读屏障

### 5.7.1 着色指针

ZGC 最核心的创新是「着色指针」——将 GC 元数据编码到指针的未用高位中：

```
64 位 ZGC 指针布局（x86_64）：
┌──────┬────────┬────────┬─────────┬───────────────────────┐
│unused│ 000000 │ final  │remap    │   object offset       │
│ 4bit │ 6bit   │ 1bit   │1bit     │   44bit               │
└──────┴────────┴────────┴─────────┴───────────────────────┘
        ↑ GC 颜色位           ↑ 虚拟地址

颜色位组合（2 bit 有效）：
00 → 正常映射（remapped）
01 → 待重映射（remap 阶段使用）
10 → 待标记（mark 阶段使用）
11 → 终结器标记（finalizable）
```

着色指针的优势：
1. **无需读屏障中的对象头检查**：颜色信息直接在指针中
2. **无转发指针**：对象移动时只修改页表映射，不需要在对象头中设置转发指针
3. **并发移动**：GC 线程移动对象时，应用线程可以继续访问旧指针（通过多映射）

### 5.7.2 读屏障

ZGC 使用读屏障（load barrier）而非写屏障：

```cpp
// zBarrier.cpp
// 每次从堆加载引用时：
oop load_barrier(oop* ref) {
    oop o = *ref;
    if (is_good(o)) return o;        // 快速路径：指针颜色正确
    return slow_path(ref, o);         // 慢速路径：自愈或转发
}
```

读屏障确保应用线程永远只看到「好的」指针。如果遇到「坏的」指针，屏障会：
1. 通过多映射视图找到正确地址
2. 自愈（self-heal）：将坏指针修正为好指针

### 5.7.3 ZGC 的并发阶段

```
ZGC 并发周期：
 1. 标记开始（STW，极短）   → 根扫描
 2. 并发标记                → 遍历对象图
 3. 标记结束（STW，极短）   → 处理少量 SATB 缓冲
 4. 并发选择回收 Region
 5. 重定位开始（STW，极短）  → 选择要移动的 Region
 6. 并发重定位               → 移动对象、更新引用
```

ZGC 的 STW 暂停时间通常 < 1ms，与堆大小无关。

---

## 5.8 Shenandoah：Brooks 指针与并发压缩

### 5.8.1 Brooks 指针

Shenandoah 使用 Brooks 指针实现并发移动：

```
对象头中的 Brooks 指针：
┌──────────────────────────────────────────┐
│ markWord │ forwarding pointer (8 bytes)  │  ← Shenandoah 额外开销
├──────────────────────────────────────────┤
│ 实例数据                                  │
└──────────────────────────────────────────┘
```

每个对象额外占用 8 字节存储转发指针，正常情况下指向自己。GC 移动对象后，旧对象的转发指针指向新对象。

### 5.8.2 读屏障与写屏障

Shenandoah 同时使用读屏障和写屏障：

```cpp
// 读屏障：确保看到最新的对象副本
oop read_barrier(oop obj) {
    oop fwd = obj->forward();
    return (fwd != nullptr) ? fwd : obj;
}
```

### 5.8.3 Shenandoah vs ZGC 对比

| 特性 | Shenandoah | ZGC |
|------|-----------|-----|
| 并发移动机制 | Brooks 转发指针 | 着色指针 + 多映射 |
| 额外内存开销 | 每对象 +8 字节 | 每引用多映射（约 3x 虚拟空间） |
| 屏障类型 | 读+写屏障 | 读屏障 |
| 分代支持 | JDK 21+ 支持 | JDK 21+ 支持（ZGenerational） |
| 回收粒度 | Region 级别 | Page 级别（更细粒度） |

---

## 5.9 [AI 时代思考] 大模型推理场景的 GC 调优：高吞吐 vs 低延迟的权衡

### 5.9.1 LLM 推理的内存特征

LLM 推理服务有独特的内存访问模式：

1. **长驻大对象**：模型参数（GB 级）和 KV Cache（百 MB 级）长期存活
2. **短命请求对象**：每次推理请求创建的 token 序列、中间结果
3. **突发分配**：并发请求可能同时分配大量 KV Cache
4. **延迟敏感**：推理请求的 P99 延迟要求通常 < 500ms

### 5.9.2 GC 选择建议

| 场景 | 推荐 GC | 原因 |
|------|---------|------|
| 批量推理（吞吐优先） | G1 | 混合收集平衡吞吐和延迟 |
| 在线推理（延迟优先） | ZGC | STW < 1ms，不受堆大小影响 |
| 模型参数加载/卸载 | G1 + Humongous 优化 | 大对象直接分配在 Humongous Region |
| 多租户推理服务 | ZGC 分代模式 | 短命请求对象在 Young 区快速回收 |

### 5.9.3 关键调优参数

**ZGC 分代模式**（JDK 21+）：

```
-XX:+UseZGC -XX:+ZGenerational
-XX:SoftMaxHeapSize=4g           # 软限制，空闲时归还内存
-XX:+AlwaysPreTouch              # 预填充，避免推理时页面错误
-XX:+UseLargePages               # 减少TLB miss
```

**G1 模式**：

```
-XX:+UseG1GC
-XX:MaxGCPauseMillis=50          # 目标暂停 50ms
-XX:G1HeapRegionSize=16m         # 大 Region，减少 Humongous 对象
-XX:InitiatingHeapOccupancyPercent=45  # 提前触发并发标记
-XX:+AlwaysPreTouch
-XX:+UseLargePages
```

### 5.9.4 避免的陷阱

1. **`System.gc()` 触发 Full GC**：使用 `-XX:+DisableExplicitGC` 禁止
2. **元空间泄漏**：动态生成的类（如 Lambda、Proxy）可能导致元空间增长，配合 `-XX:MaxMetaspaceSize` 限制
3. **Humongous 分配导致的 Full GC**：G1 模式下，超大对象会触发 Full GC，调整 Region 大小避免
4. **ZGC 的虚拟空间开销**：ZGC 需要约 3x 堆大小的虚拟地址空间，确保 `vm.max_map_count` 足够大

---

## 小结

本章深入了 JVM 的堆和 GC 子系统：

1. **oop 体系**：从 `oopDesc` 到 `instanceOop`，C++ 类型系统精确映射 Java 对象层次
2. **markWord**：64 位对象头承载了锁、哈希、GC 年龄等多重信息，紧凑头是新优化方向
3. **压缩 oop**：32 位引用节省约 40% 内存，是 64 位 JVM 最重要的优化之一
4. **五种 GC**：从 Serial 到 ZGC，复杂度递增，延迟递减
5. **G1 的 Region 化**：混合收集实现暂停时间可控
6. **ZGC 的着色指针**：将 GC 元数据编码到指针中，消除转发指针开销
7. **AI 推理调优**：ZGC 分代模式是在线推理的最佳选择，G1 适合批量推理

下一章将深入元空间——类元数据的存储管理。
