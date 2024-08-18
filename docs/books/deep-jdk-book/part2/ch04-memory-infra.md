# 第 4 章 内存管理基础设施

> 源码路径：`src/hotspot/share/memory/`、`src/hotspot/share/runtime/os.cpp`、`src/hotspot/os/linux/os_linux.cpp`

JVM 的内存管理远不止 GC 这一层。在 Java 堆之下，存在一套完整的原生内存管理基础设施——Arena 分配器、虚拟空间抽象、预留-提交两阶段策略。这些机制支撑了编译器的 Node 分配、类加载的元数据存储、运行时的句柄管理，甚至 GC 自身的数据结构。本章深入这些基础设施，它们是理解上层所有子系统的前提。

---

## 4.1 `allocation.cpp / arena.cpp`：Arena 分配器与 ResourceArea

### 4.1.1 JVM 内存分配的五种来源

JVM 内部的 C++ 对象并不都使用 `malloc/free`——根据生命周期和使用场景，有五种分配策略：

| 分配方式 | 基类 | 分配区域 | 生命周期 | 典型用途 |
|---------|------|---------|---------|---------|
| 栈分配 | `StackObj` | C 栈 | 函数作用域 | `ResourceMark`、`HandleMark` |
| Arena 分配 | `ResourceObj` | ResourceArea | `ResourceMark` 作用域 | 编译期临时数据 |
| C 堆分配 | `CHeapObj<mtTag>` | C 堆（malloc） | 手动 delete | `JavaThread`、`OSThread` |
| 元空间分配 | `MetaspaceObj` | Metaspace | 类卸载时释放 | `Klass`、`Method`、`ConstantPool` |
| Java 堆分配 | — | Java Heap | GC 回收 | Java 对象 |

这种分层设计的核心思想：**尽量减少 malloc/free 调用**。malloc 是系统调用，涉及锁竞争和碎片化；Arena 分配器通过批量分配+批量释放，将开销摊销到 O(1)。

### 4.1.2 Arena 分配器的设计

Arena 是一种 bump-pointer 分配器，定义在 `memory/arena.hpp`：

```cpp
// arena.hpp:116
class Arena : public CHeapObjBase {
    Chunk* _first;    // 第一个 Chunk（链表头）
    Chunk* _chunk;    // 当前 Chunk
    char*  _hwm;      // 高水位标记（当前分配位置）
    char*  _max;      // 当前 Chunk 的上限
};
```

**分配过程（`Amalloc`）**：

```cpp
// arena.hpp:172
void* Amalloc(size_t x) {
    x = ARENA_ALIGN(x);  // 对齐到 8 字节
    if (pointer_delta(_max, _hwm, 1) >= x) {
        char *old = _hwm;  // 快速路径：bump pointer
        _hwm += x;
        return old;
    } else {
        return grow(x);    // 慢速路径：分配新 Chunk
    }
}
```

快速路径只是一次指针比较和一次加法——比 `malloc` 快 10-100 倍。

**Chunk 的分级**：

```cpp
// arena.hpp:64
enum {
    tiny_size   =  256 - slack,   // 首次分配的小 Chunk
    init_size   =  1*K - slack,   // 普通 Arena 的首 Chunk
    medium_size = 10*K - slack,   // 中等 Chunk
    size        = 32*K - slack,   // 默认 Chunk 大小
};
```

Arena 使用的 Chunk 从小到大增长：先分配 1KB 的 Chunk，用完后分配 32KB 的 Chunk，之后每次都分配 32KB。这种策略避免了小 Arena 浪费大 Chunk。

**释放过程（`Afree`）**：

```cpp
// arena.hpp:190
bool Afree(void *ptr, size_t size) {
    if (((char*)ptr) + size == _hwm) {
        _hwm = (char*)ptr;  // 只有释放最后一次分配才有效
        return true;
    } else {
        return false;       // 否则无法释放（等批量释放）
    }
}
```

Arena 只支持「栈式释放」——只有释放最后分配的块才能成功。这是 Arena 分配器高效的根本原因：不需要维护空闲列表。

**Chunk 池化（ChunkPool）**：

```cpp
// allocation.cpp:86
class ChunkPool {
    static ChunkPool _pools[4];  // 4 种大小的池
    Chunk* _first;               // 空闲链表
    const size_t _size;          // 池中 Chunk 的大小
};
```

当 Arena 销毁时，Chunk 不直接 `free`，而是归还到 `ChunkPool`。下次创建 Arena 时优先从池中取用，避免频繁的 `malloc/free` 系统调用。

### 4.1.3 ResourceArea 与 ResourceMark

`ResourceArea` 是 Arena 的线程本地实例，配合 `ResourceMark` 实现自动化的作用域分配：

```cpp
// resourceArea.hpp:45
class ResourceArea: public Arena {
    DEBUG_ONLY(int _nesting;)  // ResourceMark 嵌套深度
};
```

**使用模式**：

```cpp
void some_function() {
    ResourceMark rm;  // 保存当前 _hwm
    int* foo = NEW_RESOURCE_ARRAY(int, 64);  // 从 ResourceArea 分配
    // ... 使用 foo ...
    // 函数退出时 rm 析构，自动回滚 _hwm，释放 foo
}
```

`ResourceMark` 的构造函数保存 `_chunk / _hwm / _max` 的快照，析构时回滚：

```cpp
// resourceArea.hpp:104
void rollback_to(const SavedState& state) {
    if (state._chunk->next() != nullptr) {
        set_size_in_bytes(state._size_in_bytes);
        Chunk::next_chop(state._chunk);  // 释放后续 Chunk
    }
    _chunk = state._chunk;
    _hwm   = state._hwm;
    _max   = state._max;
}
```

### 4.1.4 HandleArea 与 HandleMark

`HandleArea` 是另一种 Arena 变体，用于管理 JNI 句柄（`Handle` / `oop`）：

```cpp
// 每个 JavaThread 有自己的 HandleArea
class JavaThread: public Thread {
    HandleArea* _handle_area;
};
```

`HandleMark` 与 `ResourceMark` 机制相同，但管理的是 `oop` 句柄，确保 GC 能够正确追踪栈上的对象引用。

### 4.1.5 Arena 在 C2 编译器中的角色

C2 编译器是 Arena 最大的消费者。编译一个方法时，会创建多个 Arena：

| Arena 标签 | 用途 |
|-----------|------|
| `tag_node` | C2 Node 分配（IR 节点） |
| `tag_comp` | C2 Compile 主 Arena |
| `tag_idealloop` | 循环优化临时数据 |
| `tag_type` | C2 Type 系统 |
| `tag_regsplit` | 寄存器分配分裂 |
| `tag_superword` | 自动向量化 |

编译完成后，所有 Arena 一次性释放——比逐个 `delete` Node 快几个数量级。这也是 Arena 分配器存在的核心价值。

---

## 4.2 `virtualspace.cpp`：虚拟内存空间管理

### 4.2.1 VirtualSpace 的三区域模型

`VirtualSpace` 是 JVM 对操作系统虚拟内存的封装，它将一块预留的虚拟地址空间分为三个区域：

```
地址低 →→→→→→→→→→→→→→→→→→→→→→→→→→→→→→ 高

┌──────────┬──────────────────────────┬──────────┐
│  Lower   │       Middle             │  Upper   │
│ (页对齐) │   (大页对齐)              │ (页对齐) │
└──────────┴──────────────────────────┴──────────┘
↑          ↑                          ↑          ↑
low        lower_high_                middle_    high_
boundary   boundary                   high_      boundary
                                      boundary
```

```cpp
// virtualspace.cpp:54
bool VirtualSpace::initialize_with_granularity(
    ReservedSpace rs, size_t committed_size, size_t max_commit_granularity) {

    _lower_alignment  = os::vm_page_size();         // 下区：普通页
    _middle_alignment = max_commit_granularity;      // 中区：大页对齐
    _upper_alignment  = os::vm_page_size();          // 上区：普通页

    _lower_high_boundary  = align_up(low_boundary(), middle_alignment());
    _middle_high_boundary = align_down(high_boundary(), middle_alignment());
}
```

三区域模型的目的是**支持大页**：中间区域以大页粒度提交/回收，上下两个「缝隙」以普通页粒度处理，确保地址空间不浪费。

### 4.2.2 预留与提交的两阶段策略

JVM 的内存管理遵循「先预留，后提交」的模式：

```
1. 预留（Reserve）：占用虚拟地址空间，不分配物理内存
   mmap(addr, size, PROT_NONE, MAP_NORESERVE|MAP_ANONYMOUS|MAP_PRIVATE)

2. 提交（Commit）：映射到物理内存
   mmap(addr, size, PROT_READ|PROT_WRITE, MAP_FIXED|MAP_ANONYMOUS|MAP_PRIVATE)
   或 mprotect(addr, size, PROT_READ|PROT_WRITE)

3. 回收（Uncommit）：释放物理内存但保留虚拟地址
   mmap(addr, size, PROT_NONE, MAP_FIXED|MAP_ANONYMOUS|MAP_NORESERVE|MAP_PRIVATE)
   或 madvise(addr, size, MADV_DONTNEED)
```

这种策略使得 JVM 可以预留数 GB 的虚拟地址空间（如 Java 堆），但只在实际使用时才消耗物理内存。GC 可以在空闲时回收未使用的物理内存（uncommit），在需要时重新提交（recommit）。

### 4.2.3 ReservedSpace 与内存对齐

`ReservedSpace` 封装了虚拟地址空间的预留：

```cpp
// reservedSpace.hpp
class ReservedSpace {
    char*  _base;       // 预留的起始地址
    size_t _size;       // 预留的总大小
    size_t _alignment;  // 对齐粒度
    bool   _special;    // 是否使用大页的特殊映射
    bool   _executable; // 是否可执行（CodeCache 需要）
};
```

Java 堆的预留过程：

```cpp
// universe.cpp（简化）
jint Universe::initialize_heap() {
    CollectedHeap* heap = GCConfig::arguments()->create_heap();
    heap->initialize();  // 内部调用 ReservedSpace::reserve_heap()
}
```

堆的对齐要求取决于 GC 和压缩 oop 策略：
- 未压缩 oop：页对齐（4KB）
- 压缩 oop + 基于偏移的寻址：需要 3GB 或 32GB 对齐
- ZGC 的着色指针：需要特殊的地址空间布局

---

## 4.3 `universe.cpp`：JVM 宇宙——堆的初始化与布局

### 4.3.1 Universe：JVM 的全局状态容器

`Universe` 类（`memory/universe.hpp`）是 JVM 全局状态的命名空间，持有所有「已知」的系统对象和类：

```cpp
class Universe: AllStatic {
    // 已知类
    static TypeArrayKlass* _typeArrayKlasses[T_LONG+1];  // int[]、byte[] 等
    static ObjArrayKlass*  _objectArrayKlass;             // Object[]
    static Klass*          _fillerArrayKlass;              // GC 填充对象

    // 已知对象
    static OopHandle _main_thread_group;          // 主线程组
    static OopHandle _the_empty_class_array;      // 空的 Class[]
    static OopHandle _the_null_string;            // "null" 字符串缓存
    static OopHandle _out_of_memory_errors;       // 预分配的 OOM 错误

    // 堆
    static CollectedHeap* _collectedHeap;          // 唯一的堆实例

    // 初始化状态
    static bool _bootstrapping;       // 正在引导
    static bool _fully_initialized;   // 完全初始化
};
```

### 4.3.2 堆初始化流程

```
universe_init()
├── GCConfig::arguments()->create_heap()      // 根据 GC 类型创建堆
├── heap->initialize()                        // 初始化堆
│   ├── ReservedSpace::reserve_heap()         // 预留虚拟地址空间
│   ├── VirtualSpace::initialize()            // 初始化虚拟空间
│   ├── initialize_tlab()                     // 初始化 TLAB
│   └── OopStorageSet::initialize()           // 初始化 OopStorage
├── initialize_basic_type_mirrors()           // 初始化基本类型镜像
└── genesis()                                 // 创建初始世界
    ├── create_initial_thread_group()         // 创建线程组
    └── create_initial_thread()               // 创建主线程对象
```

`genesis()` 是一个颇具仪式感的函数名——它创建了 JVM 世界的「创世纪」对象：`Object`、`Class`、`String`、`Thread` 等。

### 4.3.3 预分配的 OOM 错误

一个容易被忽略但至关重要的设计：JVM 在启动时预分配了 `OutOfMemoryError` 对象：

```cpp
// universe.hpp:84
static OopHandle _out_of_memory_errors;
static volatile jint _preallocated_out_of_memory_error_avail_count;
```

为什么？因为当 JVM 真的 OOM 时，可能没有内存来创建 `OutOfMemoryError` 对象。预分配确保无论内存多么紧张，都能抛出 OOM 异常。

### 4.3.4 CollectedHeap 接口

所有 GC 实现都继承自 `CollectedHeap`：

```cpp
// gc/shared/collectedHeap.hpp
class CollectedHeap {
    virtual HeapWord* mem_allocate(size_t size, bool* gc_overhead_limit_was_exceeded) = 0;
    virtual HeapWord* allocate_new_tlab(size_t min_size, size_t requested_size,
                                        size_t* actual_size) = 0;
    virtual void collect(GCCause::Cause cause) = 0;
    virtual void do_full_collection(bool clear_all_soft_refs) = 0;
};
```

`CollectedHeap` 定义了 GC 的公共接口，但具体实现由各 GC 子类完成。这是一个经典的策略模式。

---

## 4.4 `os.cpp` 内存接口：`mmap` / `mprotect` / `madvise` 的封装

### 4.4.1 三层内存操作

JVM 的内存操作通过 `os` 类统一封装，最终调用 POSIX API：

| JVM 方法 | Linux 实现 | 用途 |
|---------|-----------|------|
| `os::reserve_memory()` | `mmap(PROT_NONE, MAP_NORESERVE)` | 预留虚拟地址空间 |
| `os::commit_memory()` | `mmap(PROT_READ\|PROT_WRITE, MAP_FIXED)` 或 `mprotect()` | 提交物理内存 |
| `os::uncommit_memory()` | `mmap(PROT_NONE, MAP_NORESERVE, MAP_FIXED)` 或 `madvise(MADV_DONTNEED)` | 回收物理内存 |
| `os::protect_memory()` | `mprotect()` | 修改内存保护属性 |
| `os::release_memory()` | `munmap()` | 释放虚拟地址空间 |
| `os::pretouch_memory()` | 逐页写入零 | 预填充内存 |

### 4.4.2 commit 的两种实现路径

`commit_memory` 在 Linux 上有两条实现路径：

**路径 1：`mmap` + `MAP_FIXED`**（替换映射）

```c
// os_linux.cpp
mmap(addr, size, PROT_READ|PROT_WRITE, MAP_PRIVATE|MAP_FIXED|MAP_ANONYMOUS, -1, 0);
```

完全替换原有的 `PROT_NONE` 映射，创建新的可读写映射。

**路径 2：`mprotect`**（修改保护属性）

```c
mprotect(addr, size, PROT_READ|PROT_WRITE);
```

只修改已有映射的保护属性，不创建新映射。

JDK 27 默认使用路径 1（`mmap`），因为 `MAP_FIXED` 映射保证了内核会正确处理大页和 NUMA 策略。`mprotect` 在某些场景下可能不会触发预期的 NUMA 行为。

### 4.4.3 `madvise` 的使用

`madvise` 是 JVM 与内核内存管理器通信的重要接口：

| `madvise` 参数 | 含义 | JVM 使用场景 |
|---------------|------|-------------|
| `MADV_DONTNEED` | 立即释放页面 | GC uncommit |
| `MADV_REMOVE` | 删除映射 | ZGC 堆回收 |
| `MADV_HUGEPAGE` | 启用透明大页 | 堆和 CodeCache |
| `MADV_NOHUGEPAGE` | 禁用透明大页 | 禁止合并的内存区域 |
| `MADV_POPULATE_WRITE` | 预填充写 | JDK 27 新特性，替代手动 pretouch |

`MADV_POPULATE_WRITE`（Linux 5.14+）是 JDK 27 利用的新特性。传统方式是逐页写零来触发物理分配（pretouch），而 `MADV_POPULATE_WRITE` 让内核一次性完成，避免了用户态逐页写入的开销：

```cpp
// os_linux.cpp:4483
FLAG_SET_DEFAULT(UseMadvPopulateWrite,
    (::madvise(nullptr, 0, MADV_POPULATE_WRITE) == 0));
```

### 4.4.4 大页的预分配与映射

JVM 支持的两种大页模式映射方式不同：

**透明大页（THP）**：

```c
// 预留时使用普通页
mmap(addr, size, PROT_NONE, MAP_ANONYMOUS|MAP_NORESERVE);

// 提交时提示内核合并为大页
madvise(addr, size, MADV_HUGEPAGE);
mmap(addr, size, PROT_READ|PROT_WRITE, MAP_FIXED|MAP_ANONYMOUS);
```

**显式大页**：

```c
// 直接映射到大页
mmap(addr, size, PROT_READ|PROT_WRITE,
     MAP_ANONYMOUS|MAP_HUGETLB|MAP_HUGETLB_2MB, -1, 0);
```

---

## 4.5 [体系结构视角] TLB、大页（Huge Pages）与内存访问延迟模型

### 4.5.1 虚拟地址翻译与 TLB

每次内存访问都需要将虚拟地址翻译为物理地址，这通过页表完成。TLB（Translation Lookaside Buffer）是页表项的缓存：

```
虚拟地址 → TLB 查找 → 命中 → 物理地址
                   → 未命中 → 页表遍历（4 级） → 物理地址
```

**TLB 的典型参数**（Intel Sapphire Rapids）：

| TLB 层级 | 容量 | 覆盖范围（4KB 页） | 覆盖范围（2MB 页） |
|---------|------|-------------------|-------------------|
| L1 ITLB | 64 项 | 256KB | 128MB |
| L1 DTLB | 64 项 | 256KB | 128MB |
| L2 STLB | 2048 项 | 8MB | 4GB |

关键观察：**4KB 页的 L2 STLB 只能覆盖 8MB，而 2MB 大页可以覆盖 4GB**。对于 Java 堆（通常数 GB），使用大页可以将 TLB miss 率降低数个数量级。

### 4.5.2 TLB Miss 的性能影响

一次 TLB miss 的代价：

```
L1 TLB miss → L2 STLB 查找: ~5 个时钟周期
L2 STLB miss → 页表遍历: ~100-200 个时钟周期（4 级页表）
```

对于顺序扫描堆的 GC 来说，TLB miss 可能占 GC 暂停时间的 10-30%。这就是大页对 GC 性能至关重要的原因。

### 4.5.3 JVM 大页的实际效果

| 工作负载 | 4KB 页 GC 暂停 | 2MB 大页 GC 暂停 | 改善 |
|---------|---------------|-----------------|------|
| 4GB 堆 G1 Full GC | ~800ms | ~500ms | 37% |
| 16GB 堆 ZGC 并发标记 | ~20ms | ~12ms | 40% |
| 32GB 堆 Parallel GC | ~3s | ~1.8s | 40% |

（数据为典型值，实际效果取决于硬件和工作负载。）

### 4.5.4 内存访问延迟模型

从 CPU 到不同层级的内存访问延迟：

```
L1 Cache:    ~1ns    (4 cycles @ 4GHz)
L2 Cache:    ~3ns    (12 cycles)
L3 Cache:    ~10ns   (40 cycles)
本地 DDR:     ~80ns   (320 cycles)
跨 NUMA DDR:  ~150ns  (600 cycles)
NVMe SSD:    ~10μs    (40,000 cycles)    ← 比内存慢 100 倍
```

这个延迟层次对 JVM 的设计有深远影响：

1. **压缩 oop 的价值**：使用 32 位引用代替 64 位，减少缓存占用 50%，有效延迟降低约 30%
2. **TLB 优化**：大页减少页表遍历，将「远程内存」延迟降低
3. **NUMA 感知**：将堆分区绑定到本地节点，避免跨节点访问的 2x 延迟
4. **对象对齐**：`ObjectAlignmentInBytes=8` 确保对象不跨越缓存行

### 4.5.5 [AI 推理场景] LLM 推理的内存带宽瓶颈

LLM 推理的核心瓶颈不是计算，而是**内存带宽**：

```
推理延迟 ≈ 模型参数量 × 每参数字节数 / 内存带宽

例：7B 参数模型，FP16
推理一次 token ≈ 7B × 2 bytes / 200 GB/s ≈ 70ms
```

在此场景下，JVM 的内存管理优化方向：

1. **大页必须启用**：减少 TLB miss，确保内存带宽充分利用
2. **压缩 oop 不适用**：推理数据是 `float[]`，不受益于引用压缩
3. **ZGC 分代模式**：短生命周期的推理请求对象在 Young 区快速回收，避免全堆扫描
4. **`AlwaysPreTouch`**：推理服务启动时预填充堆内存，避免推理过程中的页面错误
5. **NUMA 绑定**：KV Cache 和模型参数必须在同一 NUMA 节点

---

## 小结

本章剖析了 JVM 内存管理的基础设施：

1. **Arena 分配器**：bump-pointer 快速分配 + 批量释放，是 C2 编译器和运行时的性能基础
2. **ResourceArea**：线程本地的 Arena，配合 `ResourceMark` 实现自动作用域管理
3. **VirtualSpace 三区域模型**：支持大页粒度的提交和回收
4. **预留-提交两阶段策略**：虚拟地址空间与物理内存的解耦，GC uncommit 的基础
5. **`Universe`**：JVM 全局状态容器，持有堆实例和预分配的 OOM 错误
6. **体系结构视角**：TLB miss 是 GC 暂停的重要贡献者，大页是核心优化手段

下一章将深入 Java 堆和 GC——从 oop 对象模型到 ZGC 的着色指针，这是 JVM 最复杂的子系统。
