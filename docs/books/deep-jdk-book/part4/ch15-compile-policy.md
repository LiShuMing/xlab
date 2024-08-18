# 第 15 章 编译策略与代码缓存

> 源码路径：`src/hotspot/share/compiler/`、`src/hotspot/share/code/`

JIT 编译是提升 Java 性能的核心机制，但编译本身消耗 CPU 和内存。编译策略决定哪些方法在何时被编译，代码缓存管理已编译代码的生命周期。本章深入 HotSpot 的分层编译策略、编译调度、代码缓存管理和逆优化机制。

---

## 15.1 `compilationPolicy.cpp`：分层编译策略

### 15.1.1 编译层级

HotSpot 的分层编译定义了 5 个层级：

| 层级 | 执行方式 | 特点 |
|------|---------|------|
| 0 | 解释器 | 收集 Profiling 数据 |
| 1 | C1 编译（无 Profiling） | 简单方法，无需进一步优化 |
| 2 | C1 编译（仅方法计数） | 有限 Profiling |
| 3 | C1 编译（完整 Profiling） | 收集完整类型和分支信息 |
| 4 | C2 编译 | 最高优化级别 |

典型路径：

```
0 (解释) → 3 (C1+Profiling) → 4 (C2)
或
0 (解释) → 3 (C1+Profiling) → 2 (C1 仅计数，C2 队列满时)
或
0 (解释) → 1 (C1 无 Profiling，trivial 方法)
```

### 15.1.2 方法调用计数器

每个方法有两个计数器：

```cpp
// methodData.hpp
class MethodData {
    // 方法调用计数器
    int _invocation_counter;

    // 回边计数器（循环次数）
    int _backedge_counter;
};
```

当方法调用计数器超过阈值时触发编译请求：

```
分层编译的阈值（默认值）：
  Tier 3 (C1+Profiling): ~2500 次调用
  Tier 4 (C2):           ~15000 次调用（Tier 3 编译后累计）

无分层编译（-XX:-TieredCompilation）：
  C2 编译阈值: ~10000 次调用
```

### 15.1.3 计数器的衰减

方法调用计数器会周期性衰减，避免长时间运行的程序为所有方法都触发编译：

```cpp
// compilationPolicy.cpp
// 每次安全点时，计数器减半
void CompilationPolicy::reset_counter_for_back_branch_event(methodHandle m) {
    MethodData* mdo = m->method_data();
    // 衰减因子：-XX:CompilerCountDecayPercentage（默认 50%）
    int decay = (int)(mdo->invocation_count() * CompilerCountDecayPercentage / 100.0);
    mdo->set_invocation_count(mdo->invocation_count() - decay);
}
```

---

## 15.2 `compileBroker.cpp`：编译任务调度

### 15.2.1 CompileBroker 的架构

`CompileBroker` 是编译系统的中央调度器：

```
CompileBroker
├── 编译队列
│   ├── C1 队列（_c1_compile_queue）
│   └── C2 队列（_c2_compile_queue）
├── 编译线程
│   ├── C1 线程池（_c1_compiler_threads）
│   └── C2 线程池（_c2_compiler_threads）
└── 编译策略
    └── CompilationPolicy
```

### 15.2.2 编译线程配置

```
默认编译线程数（CPU 核数相关）：
  C1 线程数 = max(1, log2(CPU_COUNT))
  C2 线程数 = max(1, log2(CPU_COUNT))

手动配置：
  -XX:C1CompilerCount=4
  -XX:C2CompilerCount=4
```

### 15.2.3 编译优先级

```cpp
// compileTask.hpp
enum CompileReason {
    Reason_None,
    Reason_InvocationCount,     // 调用计数触发
    Reason_BackBranchCount,     // 回边计数触发（OSR）
    Reason_Recompilation,       // 逆优化后重编译
    Reason_TierUp,              // 层级提升
};
```

OSR（On-Stack Replacement）编译优先级最高——当循环体在解释器中执行次数过多，需要在不离开方法的情况下替换为编译代码。

---

## 15.3 `compileTask.cpp`：编译优先级与去优化

### 15.3.1 编译队列的排序

编译队列按优先级排序，高优先级任务先执行：

```
优先级排序规则：
1. OSR 编译 > 正常编译（OSR 的影响更直接）
2. 层级提升 > 首次编译（已有 Profiling 数据的方法更值得优化）
3. 等待时间长的任务优先（避免饥饿）
```

### 15.3.2 方法编译的完整流程

```
1. 解释器检测到调用计数器超阈值
2. 提交编译任务到 CompileBroker
3. CompileBroker 将任务入队
4. 编译线程取出任务
5. 调用 C1 或 C2 的 compile_method()
6. 编译产物（nmethod）安装到 CodeCache
7. 方法入口点更新，后续调用走编译代码
```

对于 OSR 编译，第 7 步变为：在循环回边处检查是否有编译版本，如果有则跳转。

---

## 15.4 `codeCache.cpp / nmethod.cpp`：代码缓存与已编译方法管理

### 15.4.1 CodeCache 的结构

CodeCache 是 JVM 管理已编译代码的内存区域：

```
CodeCache 内存布局：
┌─────────────────────────────────────────┐
│ CodeHeap (non-nmethod)                  │  ← 解释器桩、运行时桩
├─────────────────────────────────────────┤
│ CodeHeap (profiled nmethod)             │  ← C1 编译的方法
├─────────────────────────────────────────┤
│ CodeHeap (non-profiled nmethod)         │  ← C2 编译的方法
└─────────────────────────────────────────┘

分段配置：
-XX:NonNMethodCodeHeapSize=5m
-XX:ProfiledCodeHeapSize=30m
-XX:NonProfiledCodeHeapSize=90m
```

分段的目的：
1. **非方法堆**：固定大小，存放不会失效的代码
2. **Profiled 堆**：C1 代码，生命周期短（可能被 C2 替换）
3. **非 Profiled 堆**：C2 代码，生命周期长，但不可移动

### 15.4.2 nmethod 的生命周期

```cpp
// nmethod.hpp
class nmethod : public CodeBlob {
    Method*     _method;           // 对应的 Java 方法
    int         _entry_point;      // 入口点
    int         _verified_entry;   // 已验证入口点
    int         _osr_entry;        // OSR 入口点
    int         _comp_level;       // 编译层级（1-4）
    int         _state;            // 状态：in_use / not_entrant / unloaded / zombie
    ExceptionInfo* _exception_table; // 异常表
    OopMapSet*  _oop_maps;         // GC 引用映射
};
```

nmethod 的状态转换：

```
in_use（活跃）
  │
  │ 方法不再被调用 / 类卸载 / 更高层级编译完成
  ▼
not_entrant（不可进入）
  │
  │ 所有正在执行的实例完成
  ▼
zombie（僵尸，可回收）
  │
  │ CodeCache 空间不足时
  ▼
freed（释放）
```

### 15.4.3 代码缓存的 GC

当 CodeCache 接近满时，`CodeCacheSweeper` 线程回收不可进入和僵尸的 nmethod：

```cpp
// codeCache.cpp
void CodeCacheSweeper::sweep_code_cache() {
    // 遍历所有 nmethod
    // 回收 not_entrant 且无活跃栈帧的 nmethod
    // 标记僵尸 nmethod 为可释放
}
```

---

## 15.5 `hotCodeCollector / hotCodeSampler`：热点代码采样

### 15.5.1 热点代码的识别

除了方法级调用计数器，JVM 还维护方法级的时间戳，用于识别「持续热点」：

```cpp
// 编译策略在安全点时检查方法的热度
// 如果方法在最近的 N 毫秒内被频繁调用，标记为热点
```

### 15.5.2 代码缓存的预热

JVM 可以在启动时预编译指定方法：

```
-XX:CompileOnly=java/lang/String::length
-XX:CompileCommand=compileonly,com/example/Main::*
```

---

## 15.6 `deoptimization.cpp`：逆优化与回边

### 15.6.1 逆优化的触发条件

逆优化（Deoptimization）将执行从编译代码转回解释器，发生在以下情况：

| 触发原因 | 说明 |
|---------|------|
| 类依赖失效 | 被内联方法的接收者类发生了变化（新子类加载） |
| 推测不成立 | C2 基于类型 Profile 做的假设不成立 |
| 未初始化的类 | 编译时假设类已初始化，运行时发现未初始化 |
| 监视器偏斜 | 偏向锁撤销 |
| 逆优化攻击 | 安全相关的逆优化 |

### 15.6.2 逆优化的过程

```
1. 编译代码检测到逆优化条件
2. 调用 Deoptimization::deoptimize()
3. 构建逆优化帧（vframeArray）
   - 为每个编译栈帧重建对应的解释器栈帧
   - 使用 nmethod 中的 oop_map 恢复所有值
4. 跳转到解释器入口
5. 继续在解释器中执行
6. 后续可能重新编译（使用更新的 Profiling 数据）
```

### 15.6.3 栈帧重建

逆优化最复杂的部分是栈帧重建——从编译器栈帧恢复出完整的解释器栈帧：

```
编译器帧：              重建的解释器帧：
┌─────────────┐        ┌──────────────────────┐
│ 局部变量     │        │ 局部变量表             │
│ (寄存器+栈) │  ───→  ├──────────────────────┤
│             │        │ 操作数栈               │
│             │        ├──────────────────────┤
│ 返回地址    │        │ 方法信息               │
└─────────────┘        │ (bcp, cpCache, ...)   │
                       └──────────────────────┘
```

每个 nmethod 携带了 `DebugInfo`，记录了每个安全点处的完整栈帧映射。逆优化时使用这些映射精确重建解释器状态。

### 15.6.4 Not Entrant 状态的处理

逆优化后，对应的 nmethod 被标记为 `not_entrant`：

```cpp
// deoptimization.cpp
void Deoptimization::deoptimize(JavaThread* thread, frame fr, RegisterMap *map) {
    // 标记 nmethod 为 not_entrant
    nm->make_not_entrant();

    // 创建 vframeArray 用于栈帧重建
    // ...
}
```

后续 `CodeCacheSweeper` 会在所有活跃栈帧都离开该方法后回收 nmethod。

---

## 15.7 [体系结构视角] I-Cache 污染、代码局部性与编译内联的硬件影响

### 15.7.1 代码缓存与 I-Cache 的关系

JVM 的 CodeCache 和 CPU 的 I-Cache 是两个不同层次的概念：

```
CodeCache：JVM 管理的内存区域，存储所有已编译代码
  大小：默认 240MB（-XX:ReservedCodeCacheSize=240m）
  位置：普通内存（可能在大页上）

I-Cache：CPU 内部的指令缓存
  L1 I-Cache：32-64KB（每个核独享）
  L2 Cache：256KB-1MB（可能共享）
  L3 Cache：8-64MB（全核共享）
```

热点方法的编译代码需要在 I-Cache 中才能高效执行。如果 CodeCache 中的活跃代码总量远超 I-Cache 容量，就会发生 I-Cache 抖动。

### 15.7.2 内联对 I-Cache 的影响

内联是双刃剑：

```
正面：消除方法调用开销，暴露更多优化机会
负面：增大编译代码体积，增加 I-Cache 压力

极端案例：
  一个方法内联了 100 个小方法 → 编译代码从 200 字节膨胀到 10KB
  如果该方法不是循环中的热路径 → I-Cache 污染
```

C2 的内联策略通过 `-XX:MaxInlineSize` 和 `-XX:FreqInlineSize` 控制内联上限：

```
-XX:MaxInlineSize=35     # 小方法（≤35 字节）总是内联
-XX:FreqInlineSize=325   # 热点方法（≤325 字节）内联
```

### 15.7.3 编译代码的 I-Cache 足迹优化

```
1. 方法分段（Method Splitting）：
   将冷路径提取为独立的编译方法，热路径更紧凑

2. 冷代码外提（Cold Code Outlining）：
   异常处理路径、罕见分支生成独立的 stub

3. 编译层级选择：
   C1 代码更小但更慢，C2 代码更大但更快
   对于 I-Cache 压力大的场景，可以考虑 -XX:TieredStopAtLevel=1

4. CodeCache 分段：
   热代码和冷代码分开存储，减少 I-Cache 污染
```

### 15.7.4 对 AI 推理服务的启示

LLM 推理服务的热点代码通常集中在少量方法（矩阵运算、softmax、tokenization）。这些方法的编译代码应该完全驻留在 I-Cache 中：

```
优化建议：
1. 预热推理路径：启动时执行一次空推理，触发所有热点方法编译
2. -XX:+PrintCompilation：检查哪些方法被编译，确认推理核心路径已编译
3. -XX:CompileThresholdScaling=0.1：降低编译阈值，更早触发编译
4. -XX:ReservedCodeCacheSize=512m：增大 CodeCache，避免方法被淘汰
5. -XX:-TieredCompilation：如果峰值性能更重要，直接使用 C2
```

---

## 小结

本章剖析了 JVM 的编译策略和代码缓存管理：

1. **分层编译**通过 5 个层级协调解释器、C1 和 C2，平衡编译速度和代码质量
2. **CompileBroker** 调度编译任务，OSR 编译优先级最高
3. **CodeCache** 分三段管理，分别存放运行时桩、C1 代码和 C2 代码
4. **nmethod** 经历 in_use → not_entrant → zombie → freed 的生命周期
5. **逆优化**从编译代码转回解释器，栈帧重建是最复杂的环节
6. **I-Cache 污染**是过度内联的代价，需要平衡内联深度和代码体积

第四篇到此完成。我们已理解了 JVM 执行引擎的全貌：解释器、C1、C2、JVMCI/Graal，以及编译策略的调度。第五篇将深入并发与同步——从线程模型到虚拟线程。
