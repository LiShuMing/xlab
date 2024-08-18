# 第 10 章 CDS 与 AOT：启动加速

> 源码路径：`src/hotspot/share/cds/`、`src/hotspot/share/cds/archiveBuilder.cpp`、`src/hotspot/share/cds/aotClassLinker.cpp`、`src/hotspot/share/cds/dynamicArchive.cpp`

启动速度是 Java 在云原生时代的核心短板。CDS（Class Data Sharing）和 AOT（Ahead-of-Time）链接通过将类解析和链接的成果持久化，让后续启动跳过这些步骤。JDK 27 的 CDS/AOT 子系统已远超最初版本——它不仅归档类元数据，还归档堆对象和编译产物。

---

## 10.1 CDS（Class Data Sharing）原理与 `cds/` 源码剖析

### 10.1.1 CDS 的演进

| 版本 | 能力 |
|------|------|
| JDK 5 | 仅 Bootstrap ClassLoader 的类元数据归档 |
| JDK 9 | AppCDS：应用类的元数据归档 |
| JDK 12 | Dynamic CDS：运行时动态归档 |
| JDK 19 | AOT 链接：提前解析类依赖 |
| JDK 22+ | AOT 堆归档：堆对象归档与映射 |
| JDK 27 | 进一步优化 AOT 堆映射（流式堆） |

### 10.1.2 `cds/` 目录结构

```
cds/
├── archiveBuilder.cpp/hpp        # 归档构建器
├── aotClassLinker.cpp/hpp        # AOT 类链接
├── aotConstantPoolResolver.cpp   # AOT 常量池解析
├── aotLinkedClassBulkLoader.cpp  # AOT 链接类批量加载
├── aotMappedHeap.cpp/hpp         # 映射式堆归档
├── aotStreamedHeap.cpp/hpp       # 流式堆归档
├── dynamicArchive.cpp/hpp        # 动态归档
├── filemap.cpp/hpp               # 归档文件映射
├── heapShared.cpp/hpp            # 堆共享
└── cdsConfig.cpp/hpp             # CDS 配置
```

### 10.1.3 CDS 归档的工作原理

**归档阶段**（`-Xshare:dump` 或 AOT 配置）：

```
1. 启动 JVM，加载指定的类列表
2. 解析类 → InstanceKlass / ConstantPool / Method 等
3. 将元数据序列化到归档文件（JSAMP 格式）
4. 将堆中的预分配对象（字符串、异常等）序列化
5. 生成归档文件（classes.jsa / aotcache）
```

**使用阶段**（`-Xshare:on`）：

```
1. mmap 归档文件到虚拟地址空间
2. 直接映射为 Metaspace 的一部分（无需解析）
3. 堆对象映射为 Java 堆的一部分（无需分配）
4. 类加载请求 → 检查归档 → 命中则直接使用
```

---

## 10.2 `archiveBuilder.cpp`：归档构建流程

### 10.2.1 ArchiveBuilder 的工作

```cpp
class ArchiveBuilder {
    // 第一阶段：收集要归档的对象
    void gather_klass(InstanceKlass* klass);
    void gather_heap_object(oop obj);

    // 第二阶段：排序和分配地址
    void relocate_klass();

    // 第三阶段：写入归档文件
    void write_archive(FileMapInfo* mapinfo);
};
```

归档构建的核心挑战是**地址重定位**——归档中的指针必须在运行时指向正确的地址。ArchiveBuilder 使用**缓冲区分配**策略：先在虚拟缓冲区中分配对象，然后计算所有指针的偏移量，最后一次性写入。

---

## 10.3 `aotClassLinker / aotConstantPoolResolver`：AOT 链接优化

### 10.3.1 传统类加载 vs AOT 链接

传统类加载在运行时解析常量池中的符号引用为直接引用。AOT 链接在归档阶段完成这一工作：

```
传统加载：
  ConstantPool[5] = Methodref(class_idx, name_and_type_idx)  → 符号引用
  首次使用时：resolve → 查找 → 验证 → 替换为直接引用

AOT 链接：
  归档时已完成 resolve
  ConstantPool[5] = ResolvedMethodEntry(method_ptr, ...)      → 直接引用
  运行时：直接使用，跳过解析
```

`aotConstantPoolResolver` 在归档时遍历所有类的常量池，将可解析的条目替换为已解析状态。这消除了运行时的符号解析开销——对于数千个类，节省的解析时间可达数百毫秒。

---

## 10.4 `aotMappedHeap / aotStreamedHeap`：堆对象的归档与映射

### 10.4.1 映射式堆归档（Mapped Heap）

将堆对象直接映射到归档文件中的内存：

```
归档文件：
┌─────────────────────┐
│ Metaspace Region     │  ← 类元数据
├─────────────────────┤
│ Heap Region          │  ← 堆对象（字符串、异常等）
│   "null" String      │
│   StackOverflowError  │
│   EmptyClassArray     │
└─────────────────────┘

运行时：mmap → 堆对象直接可用，无需 new
```

### 10.4.2 流式堆归档（Streamed Heap）

JDK 27 引入的流式堆归档解决了映射式堆的局限性：

```
映射式堆：对象地址固定，不能移动，不能 GC
流式堆：归档序列化 → 运行时反序列化到堆 → 可被 GC 管理
```

`aotStreamedHeap` 允许归档更复杂的对象图（如包含循环引用的对象），因为这些对象在运行时通过反序列化创建，而非直接映射。

---

## 10.5 `dynamicArchive.cpp`：动态归档

动态归档（Dynamic CDS）允许在应用运行后生成归档：

```
1. 启动 JVM：java -XX:ArchiveClassesAtExit=app.jsa -cp app.jar Main
2. 应用运行，加载类
3. 应用退出时，将已加载的类写入 app.jsa
4. 后续启动：java -XX:SharedArchiveFile=app.jsa -cp app.jar Main
```

动态归档使用「基础归档 + 顶层归档」的两层结构——顶层归档增量引用基础归档中的类，避免重复存储。

---

## 10.6 [AI 时代思考] AOT 预热：LLM 推理服务的 Java 启动优化范式

### 10.6.1 冷启动问题的本质

云原生环境中的冷启动延迟由三部分组成：

```
总延迟 = JVM 启动 + 类加载 + 应用初始化

典型值（无 CDS）：
  JVM 启动：200-400ms
  类加载：  300-800ms（Spring Boot 等框架）
  应用初始化：500-2000ms

典型值（有 AOT CDS）：
  JVM 启动：200-400ms（不变）
  类加载：  50-100ms（AOT 链接 + 堆归档）
  应用初始化：200-500ms（堆归档减少对象分配）
```

### 10.6.2 推理服务的 AOT 优化方案

```
1. 录制阶段：
   java -XX:ArchiveClassesAtExit=inference.aot \
        -cp inference-server.jar \
        com.inference.Server

2. 后续启动：
   java -XX:SharedArchiveFile=inference.aot \
        -Xshare:on \
        -XX:+AlwaysPreTouch \
        -cp inference-server.jar \
        com.inference.Server
```

AOT 归档可以将推理服务的启动时间减少 40-60%，使得 Java 在 Serverless 场景中具备竞争力。

---

## 小结

本章剖析了 JVM 的启动加速技术：

1. **CDS** 从元数据归档演进到堆对象归档，覆盖范围不断扩大
2. **AOT 链接**在归档时完成常量池解析，消除运行时符号查找
3. **流式堆归档**突破了映射式堆的限制，支持更复杂的对象图
4. **动态归档**允许运行后生成，降低了 CDS 的使用门槛
5. **AI 推理**场景下，AOT CDS 可将启动时间减少 40-60%
