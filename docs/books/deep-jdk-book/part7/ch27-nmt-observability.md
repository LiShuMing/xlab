# 第 27 章 NMT 与可观测性

> 源码路径：`src/hotspot/share/nmt/`、`src/hotspot/share/runtime/memTracker.cpp`、`src/hotspot/share/logging/`

JVM 的原生内存（非 Java 堆）泄漏是线上故障的常见原因——元空间膨胀、线程栈溢出、DirectByteBuffer 泄漏都发生在原生内存中。NMT（Native Memory Tracking）是 HotSpot 内置的原生内存追踪系统，配合统一日志框架，为 JVM 的原生内存提供了完整的可观测性。

---

## 27.1 `nmt/` 源码剖析：Native Memory Tracking 架构

### 27.1.1 NMT 的启用

```
启用 NMT：
  -XX:NativeMemoryTracking=summary  # 摘要模式（开销低）
  -XX:NativeMemoryTracking=detail   # 详细模式（开销较高）

查看 NMT 数据：
  jcmd <pid> VM.native_memory summary
  jcmd <pid> VM.native_memory detail
  jcmd <pid> VM.native_memory baseline  # 建立基线
  jcmd <pid> VM.native_memory summary.diff  # 与基线对比
```

### 27.1.2 NMT 的内存分类

```
NMT 将原生内存分为以下类别：

Total: reserved = 5000MB, committed = 1500MB

- Java Heap:       reserved 2048MB, committed 512MB
- Class:           reserved 1024MB, committed 128MB   ← Metaspace
- Thread:          reserved 512MB,  committed 64MB    ← 线程栈
- Code:            reserved 256MB,  committed 32MB    ← CodeCache
- GC:              reserved 512MB,  committed 256MB   ← GC 数据结构
- Internal:        reserved 128MB,  committed 64MB    ← 内部分配
- Symbol:          reserved 64MB,   committed 16MB    ← 符号表
- Native Memory Tracking: reserved 8MB, committed 4MB ← NMT 自身
```

### 27.1.3 NMT 的实现原理

```cpp
// memTracker.hpp
class MemTracker {
    static const NMT_TrackingLevel _tracking_level;

    // malloc 的 NMT 包装
    static void* record_malloc(void* ptr, size_t size, MEMFLAGS flag,
                               const NativeCallStack& stack);

    // free 的 NMT 包装
    static void record_free(void* ptr, MEMFLAGS flag);
};
```

NMT 通过包装 `malloc/free` 和 `mmap/munmap` 来追踪所有原生内存分配：

```
原始 malloc:
  void* p = malloc(size);

NMT 包装后的 malloc:
  void* p = malloc(size + header_size);
  MallocHeader* header = (MallocHeader*)p;
  header->set_size(size);
  header->set_flag(flag);
  header->set_stack(stack);    // detail 模式记录调用栈
  MallocTracker::add(header);
  return p + header_size;
```

---

## 27.2 `mallocTracker / virtualMemoryTracker`：分配追踪

### 27.2.1 MallocTracker

```cpp
// mallocTracker.hpp
class MallocTracker {
    // 按类别统计 malloc 内存
    static size_t _malloc_counts[mt_number_of_tags];
    static size_t _malloc_sizes[mt_number_of_tags];

    // detail 模式下，记录每个分配的调用栈
    static MallocSiteTable* _site_table;
};
```

### 27.2.2 VirtualMemoryTracker

```cpp
// virtualMemoryTracker.hpp
class VirtualMemoryTracker {
    // 按类别统计虚拟内存（mmap）
    static VirtualMemorySummary _summary;

    // detail 模式下，记录每个映射区域
    static VirtualMemoryRegionTracker* _region_tracker;
};
```

### 27.2.3 NMT 的开销

```
Summary 模式：
  - 每次分配/释放多 ~10ns（计数器更新）
  - 内存开销 < 1MB
  - 适合生产环境

Detail 模式：
  - 每次分配/释放多 ~50-100ns（调用栈采集）
  - 内存开销可能达 50-100MB
  - 适合诊断场景
```

---

## 27.3 `vmatree`：虚拟内存区域树

### 27.3.1 VMATree 的设计

JDK 27 引入 `VMATree`（Virtual Memory Area Tree）优化 NMT 的虚拟内存追踪：

```cpp
// vmatree.hpp
class VMATree {
    // 红黑树，按地址排序
    // 每个节点记录一段虚拟内存区域的状态
    struct VMANode {
        address   _start;
        address   _end;
        MEMFLAGS  _flag;
        size_t    _committed_size;
    };
};
```

### 27.3.2 VMATree 的查询效率

```
旧实现：线性扫描链表 → O(n)
VMATree：红黑树 → O(log n)

典型场景（1000 个内存区域）：
  旧实现：~500 次比较
  VMATree：~10 次比较

这在使用大页、多 GC 分代时尤其重要——ZGC 可能创建数千个虚拟内存区域。
```

---

## 27.4 `memMapPrinter`：内存映射可视化

### 27.4.1 MemMapPrinter 的功能

JDK 27 的 `MemMapPrinter` 可以输出进程的完整虚拟内存映射：

```
jcmd <pid> VM.memmap

输出示例：
0x0000000100000000 - 0x0000000100400000  rw-  Java Heap [4MB]
0x0000000100400000 - 0x0000000120000000  ---  Java Heap Reserved [508MB]
0x0000000200000000 - 0x0000000200100000  r-x  CodeCache [1MB]
0x0000000300000000 - 0x0000000300200000  rw-  Metaspace [2MB]
...
```

这对诊断内存碎片化和地址空间耗尽非常有用。

---

## 27.5 `logging/`：统一日志框架

### 27.5.1 统一日志的使用

```
JVM 统一日志框架（UL）的语法：
  -Xlog:tag1[+tag2...][=level][:[output][:[decorators]]]

常用示例：
  -Xlog:gc*                        # 所有 GC 日志
  -Xlog:gc+heap=debug              # GC 堆详情
  -Xlog:jit+compilation=info       # JIT 编译日志
  -Xlog:safepoint=info             # 安全点日志
  -Xlog:nmt=debug                  # NMT 调试日志
  -Xlog:os+container=trace         # 容器信息追踪

日志级别：
  off, error, warning, info, debug, trace

输出目标：
  stdout, stderr, file=<filename>

装饰器：
  time, uptime, tid, pid, tags, level
```

### 27.5.2 日志框架的实现

```cpp
// logTagSet.hpp
class LogTagSet {
    // 每个标签组合对应一个 LogTagSet
    // 例如 gc+heap 对应一个 LogTagSet
    // 每个 LogTagSet 有自己的日志级别配置
    LogLevelType _level;
    LogOutput*   _output_list;
};
```

日志消息的写入：

```cpp
// log.hpp
// 极低开销的日志宏
#define LOG_TAG(...) \
    if (log_is_enabled(LEVEL, __VA_ARGS__)) { \
        Log<__VA_ARGS__> log; \
        log.template write<LEVEL>(__VA_ARGS__); \
    }

// 如果日志级别不够，if 检查失败，零开销
```

### 27.5.3 诊断与日志的配合

```
线上问题诊断的组合拳：

1. GC 问题：
   -Xlog:gc*,safepoint=info:file=gc.log

2. 内存泄漏：
   jcmd <pid> VM.native_memory baseline
   # 等待一段时间
   jcmd <pid> VM.native_memory summary.diff

3. 编译问题：
   -Xlog:jit+compilation=info:file=jit.log

4. 线程问题：
   -Xlog:thread+smr=debug

5. 类加载问题：
   -Xlog:class+load,class+unload=info
```

---

## 27.6 [体系结构视角] 内存可观测性的硬件成本：性能计数器与开销

### 27.6.1 NMT 对性能的影响

```
NMT 对 TLAB 分配的影响（基准测试）：

无 NMT：    ~10ns/分配
Summary：   ~10.5ns/分配（+5%）
Detail：    ~11ns/分配（+10%）

NMT 对 malloc 的影响：
无 NMT：    ~50ns/malloc
Summary：   ~60ns/malloc（+20%）
Detail：    ~100ns/malloc（+100%）
```

### 27.6.2 硬件性能计数器

JVM 可以使用 CPU 的硬件性能计数器（PMC）进行精确的性能分析：

```
Intel CPU 的 PMC：
  - INST_RETIRED：已执行指令数
  - CPU_CLK_UNHALTED：CPU 时钟周期
  - L1D_RETIRED.MISS：L1 D-Cache 未命中
  - DTLB_MISSES：数据 TLB 未命中
  - BR_MISP_EXEC：分支预测失败

使用方式：
  -XX:+UsePerfData            # 启用性能数据
  jcmd <pid> PerfCounter.print  # 打印性能计数器
```

### 27.6.3 可观测性的权衡

```
可观测性层次：
1. 无开销：JFR 事件（条件检查后不记录 → 零开销）
2. 低开销：NMT Summary、JFR 采样（1-2%）
3. 中开销：NMT Detail、JVMTI 事件（5-10%）
4. 高开销：JVMTI MethodEntry、Full GC 日志（10-100%）
5. 极高开销：Full Heap Dump、STW 泄漏检测（100%+）

生产环境推荐：
  - JFR 始终开启（settings=default，~1% 开销）
  - NMT Summary 模式
  - 必要时动态开启 Detail 模式
```

---

## 小结

本章深入了 JVM 的可观测性系统：

1. **NMT** 追踪所有原生内存分配，Summary 模式开销 < 5%，适合生产环境
2. **VMATree** 使用红黑树优化虚拟内存区域查询，O(log n) 替代 O(n)
3. **MemMapPrinter** 可视化进程的虚拟内存映射
4. **统一日志框架** 提供灵活的标签组合、级别和输出控制
5. **硬件性能计数器** 可用于精确的微架构级性能分析
6. **可观测性需要权衡**——JFR 始终开启，NMT Summary 常驻，Detail 按需启用

第七篇到此完成。第八篇将深入前沿技术——Value Types、Panama、Vector API 和 AI 推理优化。
