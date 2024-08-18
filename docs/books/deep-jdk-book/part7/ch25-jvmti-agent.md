# 第 25 章 JVMTI 与 Agent 机制

> 源码路径：`src/hotspot/share/prims/jvmti*.cpp`、`src/hotspot/share/prims/jvmtiExport.cpp`、`src/hotspot/share/prims/jvmtiRedefineClasses.cpp`、`src/hotspot/share/prims/jvmtiTagMap.cpp`

JVMTI（JVM Tool Interface）是 JVM 提供的标准化工具接口，支持调试、性能分析、监控和字节码增强。Java Agent 基于 JVMTI 实现，是 APM（应用性能管理）和字节码增强框架（如 SkyWalking、ByteBuddy）的基础。本章深入 JVMTI 的核心能力。

---

## 25.1 `prims/jvmti*.cpp`：JVMTI 接口全貌

### 25.1.1 JVMTI 功能分类

| 功能分类 | 示例函数 | 用途 |
|---------|---------|------|
| 堆管理 | `IterateOverObjectsReachableFromObject` | 堆遍历、泄漏检测 |
| 线程管理 | `GetAllThreads`, `SuspendThread` | 调试、线程分析 |
| 类管理 | `GetLoadedClasses`, `RedefineClasses` | 热替换、AOP |
| 字段访问 | `GetFieldName`, `GetObjectFieldValue` | 对象检查 |
| 方法管理 | `GetMethodName`, `SetBreakpoint` | 调试 |
| 事件 | `SetEventNotificationMode` | 性能监控、追踪 |
| 定时器 | `GetTime`, `GetCurrentThreadCpuTime` | 性能分析 |

### 25.1.2 JVMTI 事件体系

```
JVMTI 事件分类：

1. 类加载事件
   ClassLoad, ClassPrepare, ClassUnload

2. 线程事件
   ThreadStart, ThreadEnd

3. 方法事件
   MethodEntry, MethodExit
   Breakpoint, SingleStep

4. 异常事件
   Exception, ExceptionCatch

5. GC 事件
   GarbageCollectionStart, GarbageCollectionFinish

6. 监视器事件
   MonitorContendedEnter, MonitorContendedEntered
   MonitorWait, MonitorWaited

7. 字段访问事件
   FieldAccess, FieldModification
```

### 25.1.3 事件的注册与回调

```c
// 注册事件回调
jvmtiEventCallbacks callbacks;
memset(&callbacks, 0, sizeof(callbacks));
callbacks.ClassLoad = &onClassLoad;
callbacks.MethodEntry = &onMethodEntry;

jvmti->SetEventCallbacks(&callbacks, sizeof(callbacks));

// 启用事件
jvmti->SetEventNotificationMode(JVMTI_ENABLE,
    JVMTI_EVENT_CLASS_LOAD, NULL);
```

---

## 25.2 `jvmtiExport`：事件导出机制

### 25.2.1 事件的触发点

JVMTI 事件由 HotSpot 内部的特定点触发：

```cpp
// jvmtiExport.cpp
// 类加载事件触发
void JvmtiExport::post_class_load(JavaThread* thread, Klass* klass) {
    // 遍历所有注册了 ClassLoad 事件的 Agent
    // 调用其回调函数
}

// 方法进入事件触发
void JvmtiExport::post_method_entry(JavaThread* thread,
                                     methodOop method, frame current_frame) {
    // 如果启用了 MethodEntry 事件
    // 在方法入口处插入回调调用
}
```

### 25.2.2 事件的性能影响

| 事件 | 开销 | 适用场景 |
|------|------|---------|
| ClassLoad | ~5μs | 启动分析 |
| MethodEntry/Exit | ~2μs/次 | 方法级 Profiler（开销大） |
| Breakpoint | ~5μs | 调试器 |
| Exception | ~3μs | 异常监控 |
| FieldAccess/Modification | ~3μs | 数据追踪 |
| GarbageCollectionStart/Finish | ~1μs | GC 监控 |
| MonitorContendedEnter | ~2μs | 锁分析 |

`MethodEntry/Exit` 事件的开销最大——每个方法调用都触发，可能使应用慢 10-100 倍。现代 Profiler（如 async-profiler）使用 `AsyncGetCallTrace` 而非 `MethodEntry` 事件来避免这一开销。

---

## 25.3 `jvmtiRedefineClasses`：热替换（HotSwap）

### 25.3.1 热替换的能力

JVMTI 的 `RedefineClasses` 可以在运行时替换类的定义：

```
支持的修改：
1. 方法体的修改（最常见）
2. 增加方法（JDK 6+ 支持）
3. 修改属性（如添加注解）

不支持的修改：
1. 删除方法
2. 修改方法签名
3. 修改类层次（父类、接口）
4. 修改字段
```

### 25.3.2 热替换的实现过程

```cpp
// jvmtiRedefineClasses.cpp（简化）
jvmtiError JvmtiEnv::RedefineClasses(jint class_count,
                                      const jvmtiClassDefinition* class_definitions) {
    for (int i = 0; i < class_count; i++) {
        // 1. 解析新的 class 文件
        InstanceKlass* new_klass = parse_class_file(class_definitions[i]);

        // 2. 验证兼容性
        check_compatibility(old_klass, new_klass);

        // 3. 替换方法体
        for (each method in old_klass) {
            method->swap_method_data(new_method);
        }

        // 4. 更新常量池
        old_klass->swap_constant_pool(new_klass);

        // 5. 逆优化依赖旧类定义的编译代码
        Deoptimization::deoptimize_dependents();
    }
}
```

### 25.3.3 热替换与 JIT 编译

热替换后，依赖旧类定义的 JIT 编译代码必须逆优化：

```
1. 检查哪些 nmethod 引用了被替换的类
2. 将这些 nmethod 标记为 not_entrant
3. 后续调用回退到解释器
4. 解释器使用新的方法体
5. 热点方法重新被 JIT 编译
```

---

## 25.4 `jvmtiTagMap`：堆遍历与对象标记

### 25.4.1 TagMap 的功能

`TagMap` 允许 Agent 为堆中的对象附加标签（tag），用于堆分析和泄漏检测：

```c
// 为对象设置标签
jvmti->SetTag(object, tag_value);

// 获取对象的标签
jlong tag;
jvmti->GetTag(object, &tag);

// 遍历堆中所有带标签的对象
jvmti->IterateOverHeap(JVMTI_HEAP_OBJECT_TAGGED,
                        &heap_callback, NULL);
```

### 25.4.2 堆遍历的实现

```cpp
// jvmtiTagMap.cpp
void JvmtiTagMap::iterate_over_heap(JvmtiHeapObjectCallback callback) {
    // 1. 获取全局安全点（STW）
    // 2. 遍历 Java 堆
    // 3. 对每个对象：
    //    a. 检查是否有标签
    //    b. 调用回调函数
    // 4. 释放安全点
}
```

堆遍历需要 STW——这是 `jmap -histo` 等工具在大型堆上耗时的原因。

---

## 25.5 Java Agent：`premain` / `agentmain` 与字节码增强

### 25.5.1 Agent 的加载方式

```
启动时加载（premain）：
  java -javaagent:myagent.jar -jar app.jar
  → 在 main() 之前调用 premain()

运行时加载（agentmain）：
  VirtualMachine vm = VirtualMachine.attach(pid);
  vm.loadAgent("myagent.jar");
  → 在运行时调用 agentmain()
```

### 25.5.2 字节码增强的原理

Java Agent 的核心用途是字节码增强——在类加载时修改字节码：

```java
// Agent 代码
public class MyAgent {
    public static void premain(String args, Instrumentation inst) {
        inst.addTransformer(new ClassFileTransformer() {
            @Override
            public byte[] transform(ClassLoader loader, String className,
                                     byte[] classfileBuffer) {
                if (className.startsWith("com/myapp/")) {
                    // 使用 ASM/Javassist 修改字节码
                    return enhance(classfileBuffer);
                }
                return null;  // 不修改
            }
        });
    }
}
```

### 25.5.3 字节码增强框架

| 框架 | 原理 | 适用场景 |
|------|------|---------|
| ASM | 低层字节码操作 | 高性能，精细控制 |
| ByteBuddy | 高层 API | 简单易用 |
| Javassist | 源码级 API | 快速原型 |
| SkyWalking Agent | ASM + 插件 | APM 监控 |

---

## 25.6 [AI 时代思考] 基于 JVMTI 的 LLM 推理性能 Profiler 设计

### 25.6.1 推理服务的 Profiling 需求

```
LLM 推理服务需要 Profile 的指标：
1. 每个推理请求的延迟分解（Tokenization → 推理 → 解码）
2. GC 暂停对推理延迟的贡献
3. 内存分配热点（KV Cache 管理的分配模式）
4. 线程等待时间（锁竞争、I/O 等待）
5. 方法级 CPU 时间（推理核心路径的时间分布）
```

### 25.6.2 推理专用 Profiler 的设计

```
1. 使用 AsyncGetCallTrace（非 STW 采样）
   - 定时器中断 → 采集调用栈
   - 不暂停应用线程
   - 开销 < 5%

2. 自定义 JVMTI 事件
   - GC 事件：记录每次 GC 的时间和原因
   - 监视器事件：记录锁竞争
   - 线程事件：跟踪虚拟线程的挂载/卸载

3. 与 JFR 集成
   - 自定义 JFR 事件记录推理请求
   - 与 GC、CPU、内存事件关联分析

4. 输出格式
   - 火焰图（CPU 时间）
   - 分配火焰图（内存分配）
   - GC 时间线
   - 锁竞争热力图
```

---

## 小结

本章深入了 JVMTI 和 Java Agent 机制：

1. **JVMTI** 提供了丰富的观察和控制能力，但事件的性能开销差异巨大
2. **热替换**可以在运行时修改方法体，但需要逆优化相关 JIT 代码
3. **TagMap** 支持对象标记和堆遍历，需要 STW
4. **Java Agent** 通过 `ClassFileTransformer` 实现字节码增强
5. **推理 Profiler** 可以基于 `AsyncGetCallTrace` + JVMTI 事件设计，开销 < 5%

下一章将深入 JFR——飞行记录器。
