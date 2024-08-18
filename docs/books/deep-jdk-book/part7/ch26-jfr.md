# 第 26 章 JFR：飞行记录器

> 源码路径：`src/hotspot/share/jfr/`

JFR（Java Flight Recorder）是 JVM 内置的低开销事件记录系统，由瑞典 Malte 公司开发后被 Oracle 收购，从 JDK 11 开始完全开源。JFR 的设计理念是「始终开启」——开销低于 2%，适合生产环境持续运行。本章深入 JFR 的架构和实现。

---

## 26.1 `jfr/` 目录全景：事件模型与缓冲区

### 26.1.1 JFR 的架构

```
jfr/
├── jfr.cpp                      # JFR 入口
├── jfrCompiler.cpp              # 编译器集成
├── recorder/
│   ├── jfrRecorder.cpp          # 记录器主类
│   ├── storage/
│   │   ├── jfrStorage.cpp       # 缓冲区管理
│   │   ├── jfrMemorySpace.cpp   # 内存空间
│   │   └── jfrBuffer.cpp        # 缓冲区实现
│   ├── checkpoint/
│   │   ├── jfrCheckpointManager.cpp  # 检查点管理
│   │   └── jfrMetadataEvent.cpp      # 元数据事件
│   └── repository/
│       └── jfrRepository.cpp    # 存储仓库
├── periodic/
│   └── jfrPeriodic.cpp          # 周期性事件
├── leakprofiler/
│   ├── leakProfiler.cpp         # 内存泄漏检测
│   └── stopTheWorldLeakProfiler.cpp
├── dcmd/
│   └── jfrDcmd.cpp              # 诊断命令
├── instrumentation/
│   └── jfrInstrumentation.cpp   # 字节码插桩
└── support/
    └── jfrThreadLocal.cpp       # 线程本地存储
```

### 26.1.2 JFR 事件模型

JFR 事件由三个要素组成：

```
1. 事件类（Event Class）：定义事件的结构
2. 事件触发点（Event Site）：在代码中触发事件的点
3. 事件处理器（Event Handler）：将事件数据写入缓冲区
```

### 26.1.3 缓冲区层次

JFR 使用多级缓冲区减少锁竞争：

```
线程本地缓冲区（Thread-local Buffer）
  │ 每个线程有独立的 JfrBuffer（~64KB）
  │ 写入无锁，纯 bump-pointer
  │
  ▼ 缓冲区满时
全局缓冲区（Global Buffer）
  │ 多个 JfrBuffer 组成缓冲池
  │ 线程本地缓冲区满时，换取新的全局缓冲区
  │
  ▼ 记录结束时
磁盘文件（.jfr 文件）
  │ 将全局缓冲区刷入磁盘
  │ 二进制格式，高效的序列化
```

---

## 26.2 `jfr/recorder/`：记录引擎

### 26.2.1 记录器的生命周期

```cpp
// jfrRecorder.cpp
bool JfrRecorder::create() {
    // 1. 初始化存储系统
    JfrStorage::create();

    // 2. 初始化检查点管理器
    JfrCheckpointManager::create();

    // 3. 初始化周期性事件
    JfrPeriodicEventSet::create();

    // 4. 启动记录线程
    JfrRecorderThread::start();
}

void JfrRecorder::destroy() {
    // 1. 刷出所有缓冲区
    JfrStorage::flush();

    // 2. 写入最终检查点
    JfrCheckpointManager::flush();

    // 3. 关闭 .jfr 文件
    JfrRepository::close();
}
```

### 26.2.2 事件的写入

```cpp
// jfrEvent.hpp（简化）
class Event {
    JfrBuffer* _buffer;  // 线程本地缓冲区

    void commit() {
        // 1. 检查是否启用
        if (!should_commit()) return;

        // 2. 写入事件头（时间戳、线程 ID、事件类型）
        write_event_header();

        // 3. 写入事件数据
        write_event_data();

        // 4. 提交到缓冲区
        _buffer->commit();
    }
};
```

### 26.2.3 JFR 的低开销设计

```
1. 无锁写入：线程本地缓冲区，bump-pointer 分配
2. 延迟序列化：事件以二进制格式直接写入缓冲区
3. 条件检查：事件的 should_commit() 内联，未启用时零开销
4. 时间戳优化：使用快照缓存，避免每次事件调用 os::elapsed_counter()
5. 字符串去重：常量字符串只写入一次，后续使用 ID 引用

典型开销：~1-2%（GC 事件、编译事件、类加载事件）
          ~5-10%（方法采样、分配采样）
```

---

## 26.3 `jfr/periodic/`：周期性事件采集

### 26.3.1 周期性事件列表

| 事件 | 默认周期 | 内容 |
|------|---------|------|
| `GCHeapSummary` | 每 1s | 堆使用摘要 |
| `GCPHase` | GC 时 | GC 各阶段时间 |
| `CPUInformation` | 每 1s | CPU 使用率 |
| `ThreadAllocationStatistics` | 每 1s | 线程分配统计 |
| `CompilerStatistics` | 每 1s | JIT 编译统计 |
| `ClassLoadingStatistics` | 每 1s | 类加载统计 |
| `JavaMonitorWait` | 事件驱动 | 监视器等待 |
| `ThreadCPULoad` | 每 10s | 线程 CPU 负载 |

### 26.3.2 采样事件

JFR 的采样事件不是全量记录，而是周期性采样：

```
方法采样（Method Sampling）：
  - 执行采样：每隔 N 毫秒（默认 10ms）采集一次线程栈
  - 使用 AsyncGetCallTrace 获取栈追踪
  - 开销 < 2%

分配采样（Allocation Sample）：
  - 每分配 N 字节（默认可配置）记录一次分配事件
  - 使用 TLAB 的分配计数器触发
  - 开销 < 1%
```

---

## 26.4 `jfr/leakprofiler/`：内存泄漏检测

### 26.4.1 泄漏检测器的工作原理

JFR 的泄漏检测器在 GC 后检查哪些对象存活了但「不应该」存活：

```
1. 启动泄漏检测：jcmd <pid> JFR.start settings=leakprofiler
2. 记录所有对象分配的栈追踪
3. 在 GC 后，检查哪些 Old 区对象仍然存活
4. 追踪这些对象的引用链到 GC Root
5. 输出可能的泄漏路径
```

### 26.4.2 STW 泄漏检测 vs 采样检测

```
STW 泄漏检测（stopTheWorldLeakProfiler）：
  - 精确遍历对象图
  - 需要 STW（暂停所有线程）
  - 适合离线分析

采样泄漏检测：
  - 采样分配事件
  - 不需要 STW
  - 开销更低，但可能遗漏
```

---

## 26.5 自定义 JFR 事件与 CI/CD 集成

### 26.5.1 自定义事件

```java
// 定义自定义事件
@Name("com.example.InferenceRequest")
@Category("LLM")
@Label("Inference Request")
public class InferenceRequestEvent extends Event {
    @Label("Model Name")
    String modelName;

    @Label("Input Tokens")
    int inputTokens;

    @Label("Output Tokens")
    int outputTokens;

    @Label("Latency (ms)")
    long latencyMs;
}

// 使用
InferenceRequestEvent event = new InferenceRequestEvent();
event.modelName = "llama-7b";
event.inputTokens = tokens.length;
event.latencyMs = elapsed;
event.commit();
```

### 26.5.2 CI/CD 中的 JFR

```
1. 测试阶段启用 JFR：
   java -XX:StartFlightRecording=settings=profile,duration=60s,filename=test.jfr \
        -jar test-suite.jar

2. 提取关键指标：
   jfr print --events CPULoad,GarbageCollection,JavaMonitorWait test.jfr

3. 回归检测：
   - GC 暂停时间是否增加
   - 分配速率是否异常
   - 锁竞争是否加剧

4. 归档 .jfr 文件用于趋势分析
```

---

## 小结

本章深入了 JFR 飞行记录器：

1. **JFR** 的多级缓冲区设计实现无锁写入，总开销 < 2%
2. **周期性事件**自动采集 GC、CPU、内存等指标
3. **采样事件**使用 `AsyncGetCallTrace` 和 TLAB 计数器，避免全量记录
4. **泄漏检测器**追踪存活对象的引用链，定位内存泄漏
5. **自定义事件**可以记录推理请求的延迟和吞吐，与 CI/CD 集成

下一章将深入 NMT——原生内存追踪。
