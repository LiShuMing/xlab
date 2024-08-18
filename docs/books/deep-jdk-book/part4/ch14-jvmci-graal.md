# 第 14 章 JVMCI 与 Graal：编译器扩展

> 源码路径：`src/hotspot/share/jvmci/`、`src/jdk.internal.vm.ci/share/classes/`

JVMCI（JVM Compiler Interface）是 HotSpot 提供的编译器接口，允许用 Java 编写的编译器替代或补充 C2。Graal 是最著名的 JVMCI 编译器实现，它不仅是 GraalVM 的核心，还为 Truffle 多语言运行时提供了优化基础。本章从 JVMCI 接口出发，追踪 Graal 编译器的嵌入过程。

---

## 14.1 `jvmci/` 源码剖析：JVM 编译器接口

### 14.1.1 JVMCI 的设计目标

JVMCI 的核心思想：将编译器的核心逻辑用 Java 实现，而保留与 HotSpot 的 C++ 接口。

优势：
1. **开发效率**：Java 比 C++ 更安全、更易调试
2. **热替换**：编译器代码可以像普通 Java 代码一样更新
3. **丰富生态**：可以利用 Java 的工具链（IDE、测试框架）
4. **多语言支持**：Graal + Truffle 可以在 JVM 上运行多种语言

### 14.1.2 JVMCI 的接口层次

```
JVMCI 接口分为三层：

1. JVMCI C++ 接口（HotSpot 侧）
   jvmciCompiler.cpp       → 编译请求入口
   jvmciCodeInstaller.cpp  → 编译产物安装
   jvmciEnv.cpp            → JVMCI 环境

2. JVMCI Java 接口（jdk.internal.vm.ci）
   JVMCICompiler           → 编译器 Java 接口
   HotSpotJVMCIRuntime     → 运行时服务
   HotSpotCompilationRequest → 编译请求

3. Graal 编译器（jdk.internal.vm.compiler）
   GraalCompiler           → Graal 编译器实现
   StructuredGraph         → Graal IR
   Backend                 → 代码生成
```

### 14.1.3 JVMCI 的启用

```
启用 JVMCI + Graal：
-XX:+UnlockExperimentalVMOptions
-XX:+UseJVMCICompiler
-XX:+EnableJVMCI

Graal 作为 C2 的替代：
-XX:+UseJVMCICompiler    # Graal 替代 C2

Graal 作为 C2 的补充（分层编译）：
-XX:+UseJVMCICompiler
-XX:TieredStopAtLevel=3  # C1 编译 + Graal 代替 C2
```

---

## 14.2 `jvmciCompiler.cpp`：Graal 编译器的嵌入

### 14.2.1 编译请求的流转

当 `CompileBroker` 决定编译一个方法时，如果启用了 JVMCI，编译请求流转如下：

```
CompileBroker::compile_method()
  │
  ▼
JVMCICompiler::compile_method()
  │
  ▼ (JNI 调用)
HotSpotJVMCIRuntime.compileMethod()
  │
  ▼ (Java 调用)
GraalCompiler.compile()
  │
  ▼
[Graph 构建 → 优化 → 代码生成]
  │
  ▼
HotSpotCompiledCode (Java 对象)
  │
  ▼ (JNI 回调)
CodeInstaller::install()
  │
  ▼
nmethod (HotSpot 已编译方法)
```

### 14.2.2 JVMCICompiler 的实现

```cpp
// jvmciCompiler.cpp（简化）
void JVMCICompiler::compile_method(ciEnv* env, ciMethod* target, int entry_bci) {
    // 1. 准备编译环境
    JVMCIEnv jvmci_env(env);

    // 2. 通过 JNI 调用 Java 侧的编译器
    JavaThread* THREAD = JavaThread::current();
    HandleMark hm(THREAD);

    HotSpotJVMCIRuntime::compile_method(
        &jvmci_env, target, entry_bci, &_compilation_id);

    // 3. 编译结果已通过 CodeInstaller 安装到 CodeCache
}
```

### 14.2.3 编译超时机制

JVMCI 编译可能耗时较长（Graal 的编译速度比 C2 慢），因此有超时机制：

```cpp
// jvmciCompiler.cpp
// 编译任务在独立的编译线程中执行
// 如果超过 -XX:JVMCICompilerThreadTimeout 毫秒，取消编译
```

---

## 14.3 `jvmciCodeInstaller`：编译产物安装

### 14.3.1 CodeInstaller 的职责

`CodeInstaller` 将 Graal 生成的机器码和元数据安装到 HotSpot 的 `CodeCache` 中：

```
CodeInstaller 接收：
  - 机器码字节数组
  - 异常处理器表
  - 栈帧信息（oop_map）
  - 数据引用（常量池引用、Klass 引用等）
  - 调试信息

CodeInstaller 产出：
  - nmethod（HotSpot 的已编译方法）
  - 已注册到 CodeCache
```

### 14.3.2 安装过程

```cpp
// jvmciCodeInstaller.cpp（简化）
JVMCI::CodeInstallResult CodeInstaller::install(
    JVMCIEnv* jvmci_env,
    Handle compiled_code,
    CodeBlob*& cb) {

    // 1. 解析 HotSpotCompiledCode 对象
    CodeBuffer buffer("Graal", code_size);
    buffer.set_oop_recorder(&_oop_recorder);

    // 2. 复制机器码到 CodeBuffer
    buffer.code_section()->emit_bytes(code_bytes, code_size);

    // 3. 解析并注册数据引用
    for (each site in data_sites) {
        // 处理常量池引用、Klass 引用等
    }

    // 4. 解析异常处理器
    // 5. 解析 oop_map
    // 6. 创建 nmethod
    nm = nmethod::new_nmethod(method, ...);

    // 7. 注册到 CodeCache
    cb = nm;
    return JVMCI::ok;
}
```

### 14.3.3 引用重定位

Graal 生成的代码中，对 Java 对象和类元数据的引用使用占位符。`CodeInstaller` 将这些占位符替换为 HotSpot 运行时的实际地址：

```
Graal 生成代码中的引用：
  mov rax, [0xDEADBEEF]    // 占位符：对某对象的引用

CodeInstaller 重定位后：
  mov rax, [0x7F1234560000] // 实际的堆地址（带 oop 重定位记录）
```

这种重定位机制确保了 GC 可以在对象移动时更新已编译代码中的引用。

---

## 14.4 Graal 与 C2 的对比：架构选择

### 14.4.1 IR 设计对比

| 特性 | C2 | Graal |
|------|-----|-------|
| IR 形式 | Sea of Nodes | Sea of Nodes（变体） |
| 节点粒度 | 较粗（C++ 类继承） | 较细（Java 类继承） |
| 优化框架 | `ideal()` 方法 + GVN | `Canonicalizer` + 固定调度 |
| 循环优化 | 基于 LoopTree | 基于 LoopTree + 更丰富的变换 |
| 逃逸分析 | 基于 BWAlloc | 基于 Partial Escape Analysis |
| 代码生成 | AD 文件 + Matcher | 独立的 Backend 体系 |

### 14.4.2 性能对比

```
典型基准测试（SPECjbb2015 / Renaissance）：

计算密集型：
  C2:  100%（基准）
  Graal: 95-105%（相当）

内存密集型：
  C2:  100%
  Graal: 90-110%（互有胜负）

编译速度：
  C2:  ~50-500ms/方法
  Graal: ~100-2000ms/方法（慢 2-4 倍）

峰值内存：
  C2:  ~100-300MB 编译期堆
  Graal: ~500MB-2GB（Graal 自身是 Java 应用）
```

### 14.4.3 选择建议

| 场景 | 推荐 | 原因 |
|------|------|------|
| 传统 Java 应用 | C2 | 编译更快，内存更少 |
| GraalVM 多语言 | Graal | Truffle 依赖 Graal |
| 极致峰值性能 | 视工作负载而定 | 互有胜负 |
| 编译器研究 | Graal | Java 实现，更易实验 |

---

## 14.5 [AI 时代思考] Truffle/GraalVM 多语言运行时的编译策略

### 14.5.1 Truffle 的 Partial Evaluation

Truffle 是 GraalVM 的语言实现框架。用 Truffle 实现的语言解释器，通过 Graal 的 Partial Evaluation 自动编译为高效机器码：

```
Truffle 语言实现（如 JavaScript、Python、Ruby）：
1. 用 Java 写解释器
2. 解释器使用 Truffle API 标注类型和分支信息
3. Graal 的 Partial Evaluation：
   a. 将解释器的 AST 固化为编译时结构
   b. 折叠所有编译时已知的操作
   c. 剩余的运行时值成为编译产物的参数

结果：解释器 → 高效编译代码，无需手写编译器
```

### 14.5.2 Python/JS 推理脚本在 GraalVM 上的运行

LLM 推理系统中，预处理和后处理常用 Python 脚本实现。GraalVM 的 Python 实现可以让这些脚本在 JVM 中高效运行：

```
传统方式：
  Java 推理引擎 ←→ Python 预处理脚本
  通过进程间通信（gRPC/pipe）→ 延迟 + 序列化开销

GraalVM 方式：
  Java 推理引擎 + GraalPy 预处理
  同一 JVM 进程内 → 零拷贝 + 无序列化
```

### 14.5.3 GraalVM Native Image 与推理服务

GraalVM 的 Native Image 将 Java 应用 AOT 编译为原生可执行文件：

```
传统 Java 推理服务：
  冷启动：2-5 秒（JVM 启动 + 类加载 + 预热）

Native Image 推理服务：
  冷启动：<100ms（无需 JVM 启动）

代价：
  - 失去 JIT 优化（无运行时编译）
  - 反射需要显式配置
  - 峰值吞吐量低于 JIT 模式
```

在 Serverless 场景中，Native Image 的冷启动优势往往比峰值性能更重要。

---

## 小结

本章剖析了 JVMCI 和 Graal 编译器：

1. **JVMCI** 是 HotSpot 的编译器扩展接口，允许 Java 编写的编译器接入
2. **编译请求**通过 JNI 从 C++ 流转到 Java，编译产物通过 CodeInstaller 安装回 C++
3. **CodeInstaller** 处理引用重定位，确保 GC 可以更新已编译代码中的引用
4. **Graal vs C2**：架构相似但实现语言不同，性能互有胜负
5. **Truffle + Graal** 的 Partial Evaluation 让解释器自动获得编译器级别的性能
6. **Native Image** 为推理服务提供亚秒级冷启动，代价是失去 JIT 优化

下一章将深入编译策略——分层编译如何协调 C1、C2 和解释器。
