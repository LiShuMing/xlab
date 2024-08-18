# 深入 JDK 底层原理：从硬件到应用的 Java 虚拟机全景

> 基于 JDK 27 (JDK Source Build) 源码深度研究
> 结合计算机体系结构思维，面向 AI 时代计算范式

---

## 第一篇：基石——执行环境与启动

### 第 1 章 JVM 启动全流程：从 `java` 命令到 `main()` 执行

- [x] 1.1 `libjli/java.c`：JVM 启动器源码剖析
- [x] 1.2 `CreateJavaVM`：JNI 规范与 HotSpot 入口
- [x] 1.3 `init.cpp`：JVM 全局初始化链路
- [x] 1.4 `arguments.cpp`：JVM 参数解析与校验机制
- [x] 1.5 `thread.cpp`：主线程的诞生与 `Threads::create_vm()`
- [x] 1.6 [体系结构视角] 启动阶段的 CPU 分支预测与 I-Cache 行为

### 第 2 章 操作系统适配层：JVM 与 OS 的契约

- [x] 2.1 `hotspot/os/` 目录全景：Linux / Windows / BSD / AIX / POSIX
- [x] 2.2 `os.cpp`：操作系统抽象接口设计
- [x] 2.3 内存映射与 `reservedSpace.cpp`：虚拟地址空间预留
- [x] 2.4 线程模型：`osThread` 与 OS 线程的映射
- [x] 2.5 信号处理机制：异常与 `safepoint` 的信号协同
- [x] 2.6 [体系结构视角] NUMA 感知与内存亲和性（`os::numa_*`）

### 第 3 章 CPU 架构适配：从 x86 到 RISC-V

- [x] 3.1 `hotspot/cpu/` 目录全景：x86 / AArch64 / ARM / PPC / RISC-V / s390 / Zero
- [x] 3.2 `assembler` 与 `macroAssembler`：指令发射的抽象
- [x] 3.3 `register` 定义与调用约定（ABI 适配）
- [x] 3.4 条件标志与内存屏障的跨架构实现
- [x] 3.5 [专题] RISC-V 向量扩展（V 扩展）与 JDK Vector API 的适配路径
- [x] 3.6 [AI 时代思考] 异构计算：当 JVM 遇到 NPU/GPU——Foreign API 的硬件意义

---

## 第二篇：内存——从堆到栈的全景

### 第 4 章 内存管理基础设施

- [x] 4.1 `allocation.cpp / arena.cpp`：Arena 分配器与 ResourceArea
- [x] 4.2 `virtualspace.cpp`：虚拟内存空间管理
- [x] 4.3 `universe.cpp`：JVM 宇宙——堆的初始化与布局
- [x] 4.4 `os.cpp` 内存接口：`mmap` / `mprotect` / `madvise` 的封装
- [x] 4.5 [体系结构视角] TLB、大页（Huge Pages）与内存访问延迟模型

### 第 5 章 堆与垃圾收集

- [x] 5.1 `oopsHierarchy`：对象模型与 `oop` 体系（`markWord / klass / compressedOops`）
- [x] 5.2 `objLayout.cpp`：对象布局与字段对齐策略
- [x] 5.3 分代假说与 GC 共同抽象（`gc/shared/`）
- [x] 5.4 Serial GC：最简实现，理解 GC 的起点
- [x] 5.5 Parallel GC：吞吐量优先的并行标记-复制
- [x] 5.6 G1 GC：Region 化设计与混合收集（`gc/g1/` 深度剖析）
- [x] 5.7 ZGC：着色指针与读屏障（`gc/z/` 深度剖析）
- [x] 5.8 Shenandoah：Brooks 指针与并发压缩（`gc/shenandoah/` 深度剖析）
- [x] 5.9 [AI 时代思考] 大模型推理场景的 GC 调优：高吞吐 vs 低延迟的权衡

### 第 6 章 元空间与类元数据

- [x] 6.1 `metaspace/` 目录全景：Metaspace 架构重构
- [x] 6.2 `classLoaderMetaspace.cpp`：类加载器级别的元空间隔离
- [x] 6.3 `metaspaceCriticalAllocation`：关键路径的元空间分配
- [x] 6.4 常量池（`constantPool`）与方法元数据（`methodData`）的元空间占用
- [x] 6.5 [体系结构视角] 元空间碎片化与 Arena 分配器的内存效率

### 第 7 章 栈与执行帧

- [x] 7.1 `frame.cpp`：栈帧布局与调用链
- [x] 7.2 `javaThread.cpp`：Java 线程栈的创建与管理
- [x] 7.3 解释器栈帧 vs 编译器栈帧
- [x] 7.4 `stackOverflow.cpp`：栈溢出检测机制
- [x] 7.5 [体系结构视角] 栈缓存（Stack Cache）与函数调用热的硬件行为

---

## 第三篇：类加载与链接

### 第 8 章 Class 文件解析

- [x] 8.1 `classFileParser.cpp`：字节码解析全流程
- [x] 8.2 `classFileStream.cpp`：类文件流的读取与校验
- [x] 8.3 字段布局构建（`fieldLayoutBuilder.cpp`）
- [x] 8.4 `stackMapTable` 与字节码验证（`verifier.cpp`）
- [x] 8.5 [专题] `record`、`sealed class`、`pattern matching` 的 class 文件表示

### 第 9 章 类加载器体系

- [x] 9.1 `classLoader.cpp`：双亲委派的 HotSpot 实现
- [x] 9.2 `classLoaderData.cpp`：加载器数据结构与生命周期
- [x] 9.3 `systemDictionary.cpp`：类型解析与符号表
- [x] 9.4 `dictionary.cpp`：已加载类的查找与并发安全
- [x] 9.5 模块化系统（`moduleEntry / packageEntry`）

### 第 10 章 CDS 与 AOT：启动加速

- [x] 10.1 CDS（Class Data Sharing）原理与 `cds/` 源码剖析
- [x] 10.2 `archiveBuilder.cpp`：归档构建流程
- [x] 10.3 `aotClassLinker / aotConstantPoolResolver`：AOT 链接优化
- [x] 10.4 `aotMappedHeap / aotStreamedHeap`：堆对象的归档与映射
- [x] 10.5 `dynamicArchive.cpp`：动态归档
- [x] 10.6 [AI 时代思考] AOT 预热：LLM 推理服务的 Java 启动优化范式

---

## 第四篇：执行引擎

### 第 11 章 字节码解释器

- [x] 11.1 `interpreter/` 目录全景：模板解释器架构
- [x] 11.2 `bytecodes.cpp`：字节码定义与分类
- [x] 11.3 `templateInterpreter.cpp`：模板解释器生成
- [x] 11.4 `templateTable.cpp`：字节码到机器码模板的映射
- [x] 11.5 `interpreterRuntime.cpp`：解释器运行时辅助
- [x] 11.6 [体系结构视角] 解释器的分支预测惩罚与 Dispatch Table 优化

### 第 12 章 C1 编译器：客户端即时编译

- [x] 12.1 `c1/` 目录全景与编译流水线
- [x] 12.2 `c1_GraphBuilder`：字节码到 HIR 的构建
- [x] 12.3 `c1_Instruction`：HIR 指令体系
- [x] 12.4 `c1_Optimizer`：值编号、常量折叠、全局值编号
- [x] 12.5 `c1_LIRGenerator`：HIR 到 LIR 的 lowering
- [x] 12.6 `c1_LinearScan`：线性扫描寄存器分配
- [x] 12.7 `c1_RangeCheckElimination`：范围检查消除
- [x] 12.8 [体系结构视角] C1 生成的代码质量与流水线效率

### 第 13 章 C2 编译器：服务端即时编译

- [x] 13.1 `opto/` 目录全景与 C2 编译流水线
- [x] 13.2 `parse1/2/3`：字节码解析与 Ideal Graph 构建
- [x] 13.3 Node 体系（`node.hpp / addnode / memnode / connode` 等）
- [x] 13.4 `loopnode / loopTransform / loopUnswitch`：循环优化全景
- [x] 13.5 `escape.cpp`：逃逸分析与标量替换
- [x] 13.6 `chaitin.cpp`：图着色寄存器分配
- [x] 13.7 `superword / vectorIntrinsics`：自动向量化
- [x] 13.8 `idealKit / idealGraphPrinter`：Ideal Graph 可视化与调试
- [x] 13.9 [专题] Vector API（`jdk.incubator.vector`）与 C2 向量化的协同
- [x] 13.10 [体系结构视角] SIMD 指令选择与 CPU 微架构的耦合

### 第 14 章 JVMCI 与 Graal：编译器扩展

- [x] 14.1 `jvmci/` 源码剖析：JVM 编译器接口
- [x] 14.2 `jvmciCompiler.cpp`：Graal 编译器的嵌入
- [x] 14.3 `jvmciCodeInstaller`：编译产物安装
- [x] 14.4 Graal 与 C2 的对比：架构选择
- [x] 14.5 [AI 时代思考] Truffle/GraalVM 多语言运行时的编译策略

### 第 15 章 编译策略与代码缓存

- [x] 15.1 `compilationPolicy.cpp`：分层编译策略
- [x] 15.2 `compileBroker.cpp`：编译任务调度
- [x] 15.3 `compileTask.cpp`：编译优先级与去优化
- [x] 15.4 `codeCache.cpp / nmethod.cpp`：代码缓存与已编译方法管理
- [x] 15.5 `hotCodeCollector / hotCodeSampler`：热点代码采样
- [x] 15.6 `deoptimization.cpp`：逆优化与回边
- [x] 15.7 [体系结构视角] I-Cache 污染、代码局部性与编译内联的硬件影响

---

## 第五篇：并发与同步

### 第 16 章 Java 线程模型

- [x] 16.1 `javaThread.cpp`：Java 线程的 HotSpot 表示
- [x] 16.2 `thread.cpp / threads.cpp`：线程生命周期管理
- [x] 16.3 `threadSMR.cpp`：线程安全的 hazard pointer
- [x] 16.4 `osThread`：OS 线程映射与调度亲和性
- [x] 16.5 [体系结构视角] 线程调度、Cache 一致性与 MESI 协议

### 第 17 章 同步原语：Monitor 与锁

- [x] 17.1 `markWord`：对象头与锁状态（无锁 / 偏向锁 / 轻量级锁 / 重量级锁）
- [x] 17.2 `basicLock / lockStack`：锁记录与栈上锁
- [x] 17.3 `objectMonitor.cpp`：重量级 Monitor 实现
- [x] 17.4 `synchronizer.cpp`：`synchronized` 的字节码到 Monitor 的映射
- [x] 17.5 [体系结构视角] CAS 指令、LL/SC 与锁的硬件成本模型

### 第 18 章 安全点与内存屏障

- [x] 18.1 `safepoint.cpp`：安全点机制与 STW
- [x] 18.2 `safepointMechanism.cpp`：安全点轮询的实现（内存页保护）
- [x] 18.3 `orderAccess.cpp`：内存序与 CPU 屏障映射
- [x] 18.4 `handshake.cpp`：线程握手——安全点的替代
- [x] 18.5 [体系结构视角] Store Buffer、Load Buffer 与 Java Memory Model 的硬件映射

### 第 19 章 虚拟线程：协程的 JVM 实现

- [x] 19.1 `VirtualThread.java`：虚拟线程的 Java API
- [x] 19.2 `continuation.cpp / continuationFreezeThaw.cpp`：Continuation 的冻结与解冻
- [x] 19.3 `continuationEntry / continuationWrapper`：Continuation 栈帧
- [x] 19.4 `stackChunkOop`：栈 chunks 的堆存储
- [x] 19.5 `lockStack / mountUnmountDisabler`：虚拟线程的挂载与锁
- [x] 19.6 `jdk.internal.vm.Continuation`：JDK 内部 API
- [x] 19.7 [AI 时代思考] 百万级虚拟线程与 LLM Agent 并发模型

---

## 第六篇：JDK 核心类库

### 第 20 章 `java.lang` 核心

- [x] 20.1 `Object / Class / ClassLoader`：类型系统的 Java 入口
- [x] 20.2 `String` 与字符串紧凑化（Compact Strings）
- [x] 20.3 `Thread / ThreadLocal / InheritableThreadLocal`
- [x] 20.4 `Reference` 体系：Soft / Weak / Phantom / FinalReference
- [x] 20.5 `StackTraceElement` 与异常机制

### 第 21 章 `java.lang.invoke`：方法句柄与 Lambda

- [x] 21.1 `MethodHandle` 体系与 `invokeExact` 的字节码生成
- [x] 21.2 `LambdaForm / LambdaFormEditor`：Lambda 形式优化
- [x] 21.3 `InnerClassLambdaMetafactory`：Lambda 的内部类生成
- [x] 21.4 `InvokerBytecodeGenerator`：方法句柄的字节码生成
- [x] 21.5 `VarHandle`：变量句柄与内存访问模式
- [x] 21.6 [专题] `invokedynamic` 从 class 文件到 HotSpot 的完整链路

### 第 22 章 `java.util.concurrent` 并发框架

- [x] 22.1 `ForkJoinPool`：工作窃取调度器源码剖析
- [x] 22.2 `CompletableFuture`：异步编程模型
- [x] 22.3 `ConcurrentHashMap`：并发哈希表的分段与 CAS
- [x] 22.4 `StampedLock`：乐观读锁
- [x] 22.5 `atomic / VarHandle`：原子变量与底层映射
- [x] 22.6 [体系结构视角] `@Contended` 与 False Sharing 的硬件真相

### 第 23 章 NIO 与内存映射

- [x] 23.1 `java.nio.Buffer` 体系与 `DirectByteBuffer`
- [x] 23.2 `libnio`：NIO 的 Native 实现
- [x] 23.3 `MappedByteBuffer` 与 `mmap` 的映射
- [x] 23.4 Selector / EPoll 的 JNI 封装
- [x] 23.5 [AI 时代思考] 零拷贝与 LLM 推理中的 KV Cache 传输优化

---

## 第七篇：运行时服务

### 第 24 章 JNI：Java 与 Native 的桥梁

- [x] 24.1 `prims/jni.cpp`：JNI 函数表与实现
- [x] 24.2 `jniHandles`：全局/局部引用管理
- [x] 24.3 `jniFastGetField`：快速字段访问
- [x] 24.4 `nativeLookup.cpp`：Native 方法符号解析
- [x] 24.5 [专题] Panama Foreign Function & Memory API（`downcallLinker / upcallLinker`）

### 第 25 章 JVMTI 与 Agent 机制

- [x] 25.1 `prims/jvmti*.cpp`：JVMTI 接口全貌
- [x] 25.2 `jvmtiExport`：事件导出机制
- [x] 25.3 `jvmtiRedefineClasses`：热替换（HotSwap）
- [x] 25.4 `jvmtiTagMap`：堆遍历与对象标记
- [x] 25.5 Java Agent：`premain` / `agentmain` 与字节码增强
- [x] 25.6 [AI 时代思考] 基于 JVMTI 的 LLM 推理性能 Profiler 设计

### 第 26 章 JFR：飞行记录器

- [x] 26.1 `jfr/` 目录全景：事件模型与缓冲区
- [x] 26.2 `jfr/recorder/`：记录引擎
- [x] 26.3 `jfr/periodic/`：周期性事件采集
- [x] 26.4 `jfr/leakprofiler/`：内存泄漏检测
- [x] 26.5 自定义 JFR 事件与 CI/CD 集成

### 第 27 章 NMT 与可观测性

- [x] 27.1 `nmt/` 源码剖析：Native Memory Tracking 架构
- [x] 27.2 `mallocTracker / virtualMemoryTracker`：分配追踪
- [x] 27.3 `vmatree`：虚拟内存区域树
- [x] 27.4 `memMapPrinter`：内存映射可视化
- [x] 27.5 `logging/`：统一日志框架
- [x] 27.6 [体系结构视角] 内存可观测性的硬件成本：性能计数器与开销

---

## 第八篇：前沿与展望

### 第 28 章 Value Types（Valhalla）的预研

- [x] 28.1 Value Types 对对象模型的冲击
- [x] 28.2 `objLayout.cpp` 中的扁平化线索
- [x] 28.3 对 `oopsHierarchy` 的影响分析

### 第 29 章 Foreign Function & Memory API（Panama）

- [x] 29.1 `scopedMemoryAccess / foreignGlobals`：外部内存访问
- [x] 29.2 `downcallLinker / upcallLinker`：跨语言调用
- [x] 29.3 `nativeEntryPoint / vmstorage`：ABI 级别的桥接
- [x] 29.4 [专题] Panama 调用 CUDA / ONNX Runtime 执行推理

### 第 30 章 Vector API 与 SIMD 计算

- [x] 30.1 `jdk.incubator.vector` 包结构与 API 设计
- [x] 30.2 `vectorIntrinsics / vectorization / superword`：C2 自动向量化
- [x] 30.3 `vtransform / superwordVTransformBuilder`：向量变换构建
- [x] 30.4 跨架构向量适配（`cpu/x86 / cpu/aarch64 / cpu/riscv`）
- [x] 30.5 [AI 时代思考] Java Vector API 在推理算子优化中的应用

### 第 31 章 面向 AI 推理的 JVM 优化方向

- [x] 31.1 LLM 推理瓶颈分析：内存带宽 vs 计算吞吐
- [x] 31.2 ZGC 分代模式与推理服务长尾延迟
- [x] 31.3 虚拟线程 + 结构化并发构建 Agent 调度框架
- [x] 31.4 AOT/CDS 加速推理服务冷启动
- [x] 31.5 向量化计算与量化推理的 JVM 路径
- [x] 31.6 展望：JVM 作为 AI Runtime 的可能性与挑战

---

## 附录

- [x] 附录 A：JDK 27 源码构建与调试环境搭建
- [x] 附录 B：HotSpot 源码目录速查表
- [x] 附录 C：JVM 参数速查（按子系统分类）
- [x] 附录 D：常用诊断工具（`jcmd / jfr / jhsdb / hsdis`）与源码对应
- [x] 附录 E：x86 / AArch64 指令速查（JVM 常用指令子集）
