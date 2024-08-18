# 第 6 章 元空间与类元数据

> 源码路径：`src/hotspot/share/memory/metaspace/`、`src/hotspot/share/oops/klass.hpp`、`src/hotspot/share/oops/constantPool.hpp`

Java 堆存储对象实例，元空间（Metaspace）存储类的元数据——`Klass`、`Method`、`ConstantPool` 等结构。元空间的管理策略与堆截然不同：没有分代、没有移动、依赖类卸载回收。JDK 27 的元空间经过多次重构，其架构已与早期版本大不相同。

---

## 6.1 `metaspace/` 目录全景：Metaspace 架构重构

### 6.1.1 目录结构

```
memory/metaspace/
├── metaspaceArena.cpp/hpp           # 线程本地的分配 Arena
├── metaspaceArenaGrowthPolicy.cpp   # Arena 增长策略
├── metaspaceContext.cpp/hpp         # 全局上下文
├── chunkManager.cpp/hpp             # Chunk 管理器（全局池化）
├── metachunk.cpp/hpp                # Chunk 实现
├── virtualSpaceList.cpp/hpp         # 虚拟空间链表
├── virtualSpaceNode.cpp/hpp         # 虚拟空间节点
├── commitLimiter.cpp/hpp            # 提交限制器
├── commitMask.cpp/hpp               # 提交位图
├── blockTree.cpp/hpp                # 空闲块树
├── freeBlocks.cpp/hpp               # 空闲块管理
├── freeChunkList.cpp/hpp            # 空闲 Chunk 链表
├── rootChunkArea.cpp/hpp            # 根 Chunk 区域
├── chunklevel.cpp/hpp               # Chunk 层级定义
└── counters.cpp/hpp                 # 统计计数器
```

### 6.1.2 架构概览

元空间采用分层架构：

```
ClassLoaderData
    ↓ 每个类加载器一个
MetaspaceArena（线程本地分配）
    ↓ 从全局池获取 Chunk
ChunkManager（全局 Chunk 池）
    ↓ 需要时扩展
VirtualSpaceList（虚拟空间链表）
    ↓ mmap 预留/提交
操作系统虚拟内存
```

### 6.1.3 Chunk 层级系统

元空间的 Chunk 采用伙伴系统式的层级管理：

```cpp
// chunklevel.hpp
// 层级从 0（最大）到 14（最小）
// 每级大小 = 2^(level + 12) 字节
// Level 0:  4MB   (root chunk)
// Level 1:  2MB
// Level 2:  1MB
// ...
// Level 14: 256 bytes (最小分配粒度)
```

分配时按需从大 Chunk 分裂（split），释放时合并（merge），减少内存碎片。

---

## 6.2 `classLoaderMetaspace.cpp`：类加载器级别的元空间隔离

### 6.2.1 ClassLoaderData 与 MetaspaceArena

每个类加载器（`ClassLoader`）对应一个 `ClassLoaderData`，其中持有独立的 `MetaspaceArena`：

```cpp
// classLoaderData.hpp
class ClassLoaderData {
    MetaspaceArena* _non_class_space_arena;  // 非 Klass 元数据
    MetaspaceArena* _class_space_arena;      // Klass 元数据（压缩 Klass 指针）
};
```

两个 Arena 的区分源于压缩 Klass 指针的需求：`Klass*` 必须存储在一个连续的地址空间中（Class Space），以便用 32 位窄指针表示；其他元数据（`Method`、`ConstantPool` 等）没有此约束。

### 6.2.2 分配过程

```
Metaspace::allocate(loader_data, word_size, type)
    ↓
MetaspaceArena::allocate(word_size)
    ↓ 尝试从当前 Chunk 分配
    ↓ 如果空间不足
MetaspaceArena::allocate_from_chunk_pool(word_size)
    ↓ 从 ChunkManager 获取新 Chunk
    ↓ 如果池中没有合适的 Chunk
VirtualSpaceNode::allocate_root_chunk()
    ↓ mmap 提交新内存
```

### 6.2.3 类卸载与元空间回收

当类加载器被回收时（GC 检测到加载器不可达），其 `MetaspaceArena` 中的所有 Chunk 被归还到 `ChunkManager`：

```
GC → ClassLoaderDataGraph::unload_class_loader_data()
    → ClassLoaderData::~ClassLoaderData()
        → MetaspaceArena::~MetaspaceArena()
            → ChunkManager::return_chunk(chunk)
```

归还的 Chunk 不会立即 `munmap`，而是缓存在 `ChunkManager` 中，供其他类加载器复用。只有当 `ChunkManager` 的缓存超过阈值时，才会通过 `purge()` 释放物理内存。

---

## 6.3 `metaspaceCriticalAllocation`：关键路径的元空间分配

### 6.3.1 元空间耗尽的处理

当元空间接近耗尽时，JVM 需要特殊处理：

```cpp
// metaspaceCriticalAllocation.cpp
// 关键分配：在元空间几乎耗尽时仍需分配的场景
// 例如：加载 OOM 错误类本身需要的元数据
```

关键分配绕过了常规的提交限制（`commitLimiter`），确保即使在极端情况下也能完成必要的类加载。

---

## 6.4 常量池（`constantPool`）与方法元数据（`methodData`）的元空间占用

### 6.4.1 元空间的主要占用者

| 元数据类型 | 大小（典型） | 说明 |
|-----------|-------------|------|
| `InstanceKlass` | ~500 字节 | 类的元数据核心 |
| `Method` | ~200 字节/方法 | 方法元信息 |
| `ConstMethod` | ~100 字节/方法 | 字节码、异常表 |
| `ConstantPool` | 4 字节/条目 × N | 常量池条目 |
| `MethodData` | ~20KB/热点方法 | JIT 编译器的性能数据 |
| `vtable` | 8 字节/虚方法 | 虚方法表 |
| `itable` | 8 字节/接口方法 | 接口方法表 |

### 6.4.2 元空间泄漏的常见原因

1. **动态类生成**：CGLib、Javassist 等字节码增强库不断生成新类
2. **线程上下文类加载器泄漏**：Web 应用重新部署时旧加载器未释放
3. **`MethodData` 增长**：热点方法的方法数据持续积累

监控手段：
```bash
jcmd <pid> GC.class_stats       # 类级别元空间统计
jcmd <pid> GC.class_histogram   # 实例数量统计
jcmd <pid> VM.metaspace         # 元空间详细报告
```

---

## 6.5 [体系结构视角] 元空间碎片化与 Arena 分配器的内存效率

### 6.5.1 碎片化的根源

元空间的碎片化问题比堆更严重，原因：
1. **不移动**：元空间的对象（Klass、Method 等）一旦分配就不移动，无法通过压缩消除碎片
2. **大小不一**：ConstantPool 可能几十 KB，Klass 几百字节，Method 几十字节
3. **类卸载不连续**：一个 Chunk 中可能混合了已卸载和仍存活的类数据

### 6.5.2 JDK 27 的碎片化缓解策略

1. **伙伴系统 Chunk 分裂/合并**：`chunklevel` 层级确保大块可以被分裂使用，释放后可以合并还原
2. **BlockTree 空闲块管理**：`blockTree.hpp` 使用平衡二叉树管理 Chunk 内的空闲块，实现 O(log n) 的最优匹配分配
3. **ClassLoaderData 隔离**：每个类加载器独立的 Arena，卸载时整体归还，避免了跨加载器的碎片传播

### 6.5.3 从体系结构角度看元空间效率

元空间分配的访问模式与堆不同：
- **读多写少**：类元数据加载后几乎只读，JIT 编译器和解释器频繁读取
- **随机访问**：虚方法调用、常量池解析都是随机访问
- **长驻内存**：类不卸载数据不释放，占用 L3 Cache

优化思路：
1. **CDS 归档**：将启动类的元数据映射到只读内存页，减少元空间分配
2. **压缩 Klass 指针**：32 位窄指针减少元数据引用的缓存占用
3. **AOT 链接**：JDK 27 的 AOT 类链接进一步减少了运行时元数据分配

---

## 小结

本章剖析了 JVM 元空间的架构：

1. **分层设计**：MetaspaceArena → ChunkManager → VirtualSpaceList，逐层管理
2. **类加载器隔离**：每个加载器独立的 Arena，卸载时整体回收
3. **伙伴系统 Chunk**：分级分裂/合并，平衡分配效率和碎片化
4. **关键分配**：元空间耗尽时的特殊路径保证 JVM 不崩溃
5. **体系结构视角**：元空间是读多写少的随机访问场景，CDS 归档是最有效的优化

下一章将深入栈与执行帧——方法调用的物理载体。
