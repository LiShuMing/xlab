# 第 7 章 栈与执行帧

> 源码路径：`src/hotspot/share/runtime/frame.hpp`、`src/hotspot/share/runtime/stackOverflow.cpp`、`src/hotspot/cpu/x86/frame_x86.hpp`

方法调用是程序执行的基本单位，而栈帧是方法调用的物理载体。JVM 的栈帧比 C 栈帧复杂得多——它需要支持 GC 的精确栈扫描、异常处理的非局部跳转、JIT 逆优化的帧重建，以及虚拟线程的冻结与解冻。本章深入栈帧的内部结构。

---

## 7.1 `frame.cpp`：栈帧布局与调用链

### 7.1.1 Frame 的核心字段

```cpp
// frame.hpp:63
class frame {
    intptr_t*   _sp;        // 栈指针
    address     _pc;        // 程序计数器（返回地址）
    CodeBlob*   _cb;        // 所属的代码块（nmethod/stub/interpreter）
    bool        _on_heap;   # 是否在堆上（虚拟线程栈块）
};
```

`frame` 是一个值类型，不拥有内存——它只是一个窗口，指向线程栈或堆上的栈块（stack chunk）中的某个位置。

### 7.1.2 x86_64 的栈帧布局

**解释器栈帧**：

```
高地址
┌──────────────────────────┐
│ 局部变量表                │
├──────────────────────────┤
│ 操作数栈                  │
├──────────────────────────┤
│ 方法指针 (methodOop)      │
│ 常量池缓存 (cpCache)      │
│ bcp (字节码指针)           │
│ 局部变量表指针             │
│ 栈指针 (SP)               │  ← _sp 指向此处
├──────────────────────────┤
│ 返回地址 (PC)             │  ← _pc
│ 旧帧指针 (FP)             │  ← _fp
├──────────────────────────┤
│ 参数 (调用者操作数栈)      │
└──────────────────────────┘
低地址
```

**编译器栈帧**：

```
高地址
┌──────────────────────────┐
│ 被调用者保存的寄存器        │
├──────────────────────────┤
│ 局部变量/临时值            │
├──────────────────────────┤
│ SP → 栈顶                 │
├──────────────────────────┤
│ 返回地址                  │
│ 旧 FP                    │
└──────────────────────────┘
低地址
```

编译器栈帧比解释器栈帧更紧凑——没有字节码指针、常量池缓存等解释器专有字段。

### 7.1.3 栈遍历（Stack Walking）

JVM 在多种场景下需要遍历栈：

```cpp
// stackFrameStream.hpp
class StackFrameStream {
    frame _current;  // 当前帧
    // ...
    void next() { _current = _current.sender(&_map); }
};
```

`sender()` 方法根据当前帧的类型（解释器/编译器/原生）计算调用者帧的位置。这是一个复杂的过程：
- 解释器帧：通过帧中的链接指针找到调用者
- 编译器帧：通过 `oop_map` 定位保存的 FP/SP，计算调用者位置
- 原生帧：依赖平台 ABI 的帧指针链

GC 使用栈遍历来扫描每个帧中的 oop 引用，确保不遗漏任何可达对象。

---

## 7.2 `javaThread.cpp`：Java 线程栈的创建与管理

### 7.2.1 JavaThread 的栈结构

每个 `JavaThread` 持有以下栈相关信息：

```cpp
class JavaThread {
    address    _stack_base;       // 栈的最高地址
    size_t     _stack_size;       // 栈的总大小
    JavaFrameAnchor _anchor;      // 最近 Java 帧的锚点（SP/FP/PC）
    StackOverflow   _stack_overflow; // 栈溢出状态
};
```

栈的内存布局（x86_64，栈向低地址增长）：

```
高地址 (stack_base)
┌──────────────────────────┐
│ 栈顶区域                  │  ← 初始 SP
│ ...                      │
│ 活跃帧                   │  ← 当前 SP
│ ...                      │
│ 保护区域                  │
├──────────────────────────┤
│ Shadow Zone (不可访问)    │  ← StackShadowPages
│ Yellow Zone (可访问)      │  ← StackYellowPages（可动态启用/禁用）
│ Red Zone (不可访问)       │  ← StackRedPages
└──────────────────────────┘
低地址 (stack_base - stack_size)
```

### 7.2.2 栈保护区域

栈保护区域的设计（`stackOverflow.cpp`）：

```cpp
// stackOverflow.cpp:37
void StackOverflow::initialize_stack_zone_sizes() {
    size_t page_size = os::vm_page_size();
    size_t unit = 4*K;

    _stack_red_zone_size      = align_up(StackRedPages * unit, page_size);
    _stack_yellow_zone_size   = align_up(StackYellowPages * unit, page_size);
    _stack_reserved_zone_size = align_up(StackReservedPages * unit, page_size);
    _stack_shadow_zone_size   = align_up(StackShadowPages * unit, page_size);
}
```

**四个区域的作用**：

| 区域 | 大小 | 保护属性 | 作用 |
|------|------|---------|------|
| Shadow Zone | 默认 20 页 | 可读可写 | 编译器方法调用的预留空间 |
| Reserved Zone | 默认 1 页 | 可读可写 | 异常处理时的预留空间 |
| Yellow Zone | 默认 3 页 | 动态切换 | 栈溢出检测，触及后抛出 StackOverflowError |
| Red Zone | 默认 1 页 | 不可访问 | 最终保护，触及后 JVM 直接崩溃 |

---

## 7.3 解释器栈帧 vs 编译器栈帧

### 7.3.1 关键差异

| 特征 | 解释器帧 | 编译器帧 |
|------|---------|---------|
| 帧大小 | 较大（固定格式） | 较小（仅保存必要数据） |
| 局部变量 | 在帧中固定偏移 | 在寄存器或栈槽中 |
| 操作数栈 | 帧内分配，固定大小 | 不需要（寄存器分配） |
| 方法元数据 | 帧中存储 methodOop、bcp、cpCache | 通过 CodeBlob 间接引用 |
| GC oop 映射 | 固定格式，始终可扫描 | 需要 oop_map 查询 |
| 逆优化 | 不涉及 | 需要重建解释器帧 |

### 7.3.2 编译器帧的 oop_map

编译器帧的 oop 位置不是固定的——JIT 编译器可能将引用放在任意栈槽或寄存器中。每个 `nmethod` 都附带了 `oop_map`，记录了每个 GC 安全点处哪些位置包含 oop 引用：

```cpp
// oopMap.hpp
class OopMap {
    // 位图：每个位对应一个栈槽或寄存器
    // 1 = 该位置包含 oop
    // 0 = 该位置不包含 oop
    CompressedWriteStream* _stream;
};
```

GC 扫描编译器帧时，先查询当前 PC 对应的 `oop_map`，然后只处理标记为 oop 的位置——这比全栈扫描高效得多。

---

## 7.4 `stackOverflow.cpp`：栈溢出检测机制

### 7.4.1 Stack Banging（栈碰撞）

JVM 使用「栈碰撞」技术检测栈溢出——在方法入口处，主动访问栈的 shadow zone 区域：

```cpp
// 解释器方法入口：
// 检查当前 SP 是否接近保护区域
// 如果 SP - shadow_zone_size < stack_base - stack_size + guard_size
// 则触发 SIGSEGV → 信号处理器判断为 StackOverflowError
```

编译器生成的代码在方法入口也会执行类似的栈碰撞检查：

```asm
; x86_64 编译器方法入口
mov rax, [thread + stack_overflow_offset]
cmp rsp, rax
jbe  stack_overflow_handler
```

### 7.4.2 栈溢出恢复

当检测到栈溢出时：

1. `SIGSEGV` 信号处理器检查地址是否在 Yellow Zone
2. 如果是，禁用 Yellow Zone（设为 `PROT_NONE`），抛出 `StackOverflowError`
3. 异常处理需要 Reserved Zone 的空间（此时 Yellow Zone 已不可用）
4. `StackOverflowError` 被捕获后，通过 `StackOverflow::reguard_stack()` 重新启用 Yellow Zone

---

## 7.5 [体系结构视角] 栈缓存与函数调用热的硬件行为

### 7.5.1 栈的缓存特性

栈是最具缓存友好性的数据结构：

1. **空间局部性**：栈帧连续存储，访问模式是顺序的
2. **时间局部性**：频繁访问的局部变量和操作数栈在 L1 缓存中
3. **预取友好**：硬件预取器可以轻松预测栈的访问模式

实验数据表明，Java 线程的 L1 D-Cache 命中率通常 > 98%，其中栈数据贡献了相当比例。

### 7.5.2 函数调用开销的硬件视角

一次方法调用的硬件开销：

```
解释器调用：
1. 压入参数到操作数栈     → L1 命中（~1ns）
2. 保存返回地址到栈       → L1 命中（~1ns）
3. 跳转到目标方法的入口   → 分支预测（~0ns 预测正确）
4. 初始化新帧             → L1 命中（~1ns）
总计：~3-5ns

编译器调用（已内联）：
1. 无帧创建开销
2. 参数在寄存器中传递     → ~0ns
总计：~0ns（完全消除）

编译器调用（未内联）：
1. 保存 callee-saved 寄存器 → L1 命中（~1ns × N）
2. 压入参数               → 寄存器传递 ~0ns
3. call 指令               → 分支预测 + 返回地址压栈 ~1ns
总计：~5-15ns
```

JIT 编译器通过内联消除了绝大多数方法调用开销。C2 编译器的内联决策直接影响 CPU 的分支预测和缓存行为。

### 7.5.3 虚拟线程对栈架构的影响

传统线程的栈在操作系统管理的内存中，大小固定（默认 1MB）。虚拟线程将栈帧存储在 Java 堆上的 `stackChunkOop` 中：

```
传统线程：
OS 栈 (1MB) → 连续内存 → 信号保护页

虚拟线程：
Java 堆 → stackChunkOop → 冻结的帧链表
                        ↓ 挂载时
                     线程栈 (恢复执行)
```

这种设计将栈帧从操作系统内存转移到了 GC 管理的堆内存中，带来了两个硬件层面的影响：

1. **缓存竞争**：栈帧与普通 Java 对象竞争 L3 Cache。当堆很大时，栈帧可能被换出
2. **GC 扫描开销**：每个 `stackChunkOop` 包含的 oop 引用需要在 GC 时扫描

但优点是显著的：虚拟线程的栈按需增长，一个空虚拟线程只占用几百字节，而不是 1MB。

---

## 小结

本章剖析了 JVM 的栈与执行帧：

1. **`frame` 类**：不拥有内存的窗口，指向线程栈或堆上的栈块
2. **栈保护区域**：Shadow/Yellow/Red Zone 分层保护，确保栈溢出安全
3. **解释器 vs 编译器帧**：解释器帧格式固定，编译器帧需要 oop_map 辅助 GC 扫描
4. **栈碰撞检测**：方法入口主动触碰 shadow zone，利用信号机制实现零开销检测
5. **体系结构视角**：栈是缓存友好的，JIT 内联消除了大部分调用开销；虚拟线程将栈帧移入堆，改变了缓存行为

第二篇到此完成。我们已理解了 JVM 内存管理的全貌：Arena 分配器、虚拟空间、堆与 GC、元空间、栈帧。第三篇将深入类加载与链接——从字节码解析到 CDS/AOT 加速。
