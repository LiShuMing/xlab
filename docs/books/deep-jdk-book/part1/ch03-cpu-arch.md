# 第 3 章 CPU 架构适配：从 x86 到 RISC-V

> 源码路径：`src/hotspot/cpu/`、`src/hotspot/cpu/x86/`、`src/hotspot/cpu/aarch64/`、`src/hotspot/cpu/riscv/`

JVM 的「跨平台」不仅是操作系统的适配，更是 CPU 指令集的适配。从解释器的字节码模板到 JIT 编译器的指令选择，从原子操作的实现到内存屏障的映射，每一行 JVM 生成的机器码都依赖 CPU 架构适配层。本章深入 `hotspot/cpu/` 目录，理解 JVM 如何与 silicon 对话。

---

## 3.1 `hotspot/cpu/` 目录全景：x86 / AArch64 / ARM / PPC / RISC-V / s390 / Zero

### 3.1.1 七种架构适配

```
hotspot/cpu/
├── x86/       # x86_64（Intel / AMD）—— 云端与桌面主流
├── aarch64/   # ARM 64-bit —— 移动端与云实例（AWS Graviton、阿里云倚天）
├── arm/       # ARM 32-bit —— 嵌入式/老旧移动设备（逐步退役）
├── ppc/       # POWER ISA（IBM Power 服务器）
├── riscv/     # RISC-V（新兴开源 ISA）
├── s90/       # IBM Z（大型机）
└── zero/      # 纯 C++ 解释器（无架构特定代码，用于移植验证）
```

每个架构目录下的文件结构高度统一：

| 文件 | 职责 |
|------|------|
| `assembler_<arch>.hpp/cpp` | 最低层指令发射器 |
| `macroAssembler_<arch>.hpp/cpp` | 高层指令序列（函数级） |
| `register_<arch>.hpp/cpp` | 寄存器定义与分配 |
| `vm_version_<arch>.hpp/cpp` | CPU 特性探测（AVX/SVE 等） |
| `frame_<arch>.hpp/cpp` | 栈帧布局 |
| `interpreterRT_<arch>.cpp` | 解释器运行时 |
| `c1_LIRAssembler_<arch>.cpp` | C1 编译器的指令生成 |
| `c2_MacroAssembler_<arch>.cpp` | C2 编译器的指令生成 |
| `<arch>.ad` | C2 指令描述文件（ADLC 输入） |
| `stubGenerator_<arch>.cpp` | 运行时桩代码生成 |
| `globalDefinitions_<arch>.hpp` | 架构特定的常量定义 |

### 3.1.2 编译时选择机制

与 OS 适配类似，CPU 适配通过编译时宏选择：

```cpp
// 全局包含
# include CPU_HEADER(assembler)     // 展开为 "assembler_x86.hpp" 等
# include CPU_HEADER(register)
# include CPU_HEADER(vm_version)
```

编译系统（`make/` 中的 HotSpot 构建逻辑）只为目标架构编译对应的 `.cpp` 文件。

---

## 3.2 `assembler` 与 `macroAssembler`：指令发射的抽象

### 3.2.1 Assembler：指令发射器

`Assembler` 是 JVM 代码生成的最低层抽象，直接操作代码缓冲区（`CodeBuffer`）发射机器码：

```cpp
// assembler_x86.hpp（简化）
class Assembler : public AbstractAssembler {
    // 整数算术指令
    void addq(Register dst, int32_t imm32);
    void addq(Register dst, Register src);
    void subq(Register dst, int32_t imm32);

    // 内存访问指令
    void movq(Register dst, Address src);
    void movq(Address dst, Register src);

    // 条件跳转
    void jcc(Condition cc, Label& label);

    // 原子操作
    void lock();
    void cmpxchgq(Register reg, Address addr);

    // SIMD 指令
    void vaddpd(XMMRegister dst, XMMRegister nds, XMMRegister src, int vector_len);
    void vpmulld(XMMRegister dst, XMMRegister nds, XMMRegister src, int vector_len);
};
```

每条 `Assembler` 方法最终都通过 `emit_int8/16/32/64` 向 `CodeBuffer` 写入机器码编码。例如：

```cpp
// x86 的 addq 指令编码
void Assembler::addq(Register dst, int32_t imm32) {
    // REX.W prefix + opcode + ModRM + imm32
    emit_int8(0x48);  // REX.W
    emit_int8(0x81);  // ADD Ev, Iz
    emit_int8(0xC0 | dst->encoding());  // ModRM
    emit_int32(imm32);
}
```

### 3.2.2 MacroAssembler：高层指令序列

`MacroAssembler` 在 `Assembler` 之上构建函数级指令序列：

```cpp
// macroAssembler_x86.hpp
class MacroAssembler : public Assembler {
    // 对象操作
    void load_klass(Register dst, Register src);
    void store_klass(Register dst, Register src);

    // 锁操作
    void lock_object(Register hdr, Register obj, Register disp_hdr, Label& slow_case);

    // GC 屏障
    void g1_write_barrier_pre(Register obj, Register pre_val, Register tmp, bool needs_frame);
    void g1_write_barrier_post(Register store_addr, Register new_val, Register tmp);

    // 安全点
    void safepoint_poll(Label& slow_path, Register thread_reg);

    // 数组拷贝
    void arraycopy(...);
};
```

`MacroAssembler` 的方法通常包含条件分支、循环和子例程调用，是一段完整的「微程序」。它们是 JVM 运行时（解释器、GC、编译器）共享的代码生成基础设施。

### 3.2.3 跨架构 Assembler 对比

同一操作在不同架构上的编码完全不同。以「原子比较并交换」（CAS）为例：

**x86_64**：
```cpp
void MacroAssembler::cmpxchgptr(Register oldval, Register newval, Address addr) {
    Lock();
    cmpxchgq(oldval, addr);  // 使用 x86 的 lock cmpxchg 指令
}
```

**AArch64**：
```cpp
void MacroAssembler::cmpxchgptr(Register oldval, Register newval, Address addr) {
    // AArch64 使用 LDXR/STXR（独占加载/存储）实现 CAS
    Label retry;
    bind(retry);
    ldxr(rscratch1, addr);
    cmp(rscratch1, oldval);
    br(Assembler::NE, fail);
    stxr(rscratch1, newval, addr);  // 独占存储
    cbnzw(rscratch1, retry);        // 如果被干扰则重试
}
```

**RISC-V**：
```cpp
void MacroAssembler::cmpxchgptr(Register oldval, Register newval, Address addr) {
    // RISC-V 使用 LR/SC（Load Reserved / Store Conditional）
    Label retry;
    bind(retry);
    lr_d(t0, addr);                // Load Reserved
    bne(t0, oldval, fail);
    sc_d(t0, newval, addr);        // Store Conditional
    bnez(t0, retry);               // 如果 store 失败则重试
}
```

三种架构的 CAS 体现了不同的硬件哲学：
- **x86**：硬件提供原子的 `lock cmpxchg`，一条指令完成
- **AArch64/RISC-V**：使用 LL/SC（Load-Link/Store-Conditional）模式，需要循环重试

---

## 3.3 `register` 定义与调用约定（ABI 适配）

### 3.3.1 寄存器定义

每个架构的 `register_<arch>.hpp` 定义了该架构的所有寄存器：

**x86_64**（16 个通用寄存器 + 32 个 XMM 寄存器）：

```cpp
// register_x86.hpp
constexpr Register rax = { 0 };
constexpr Register rcx = { 1 };
constexpr Register rdx = { 2 };
constexpr Register rbx = { 3 };
constexpr Register rsp = { 4 };
constexpr Register rbp = { 5 };
constexpr Register rsi = { 6 };
constexpr Register rdi = { 7 };
constexpr Register r8  = { 8 };
// ...
constexpr Register r15 = { 15 };

constexpr XMMRegister xmm0 = { 0 };
// ...
constexpr XMMRegister xmm31 = { 31 };
```

**AArch64**（31 个通用寄存器 + 32 个 NEON/FP 寄存器）：

```cpp
constexpr Register r0  = { 0 };
// ...
constexpr Register r30 = { 30 };  // LR (Link Register)
constexpr Register sp  = { 31 };  // 栈指针（特殊编码）

constexpr FloatRegister v0 = { 0 };
// ...
constexpr FloatRegister v31 = { 31 };
```

### 3.3.2 调用约定（ABI）

JVM 需要同时遵守两种调用约定：

**1. C 调用约定（与 JNI 交互）**

x86_64 Linux（System V AMD64 ABI）：
- 整数参数：`rdi, rsi, rdx, rcx, r8, r9`
- 浮点参数：`xmm0 - xmm7`
- 返回值：`rax`（整数），`xmm0`（浮点）

x86_64 Windows（Microsoft x64 ABI）：
- 整数参数：`rcx, rdx, r8, r9`
- 浮点参数：`xmm0 - xmm3`
- **差异**：参数更少，且需要 32 字节影子空间

```cpp
// assembler_x86.hpp 中的 ABI 感知
#ifdef _WIN64
    n_int_register_parameters_c   = 4,  // Windows: rcx, rdx, r8, r9
    n_float_register_parameters_c = 4,
#else
    n_int_register_parameters_c   = 6,  // Linux: rdi, rsi, rdx, rcx, r8, r9
    n_float_register_parameters_c = 8,
#endif
```

**2. Java 调用约定（JVM 内部）**

JVM 定义了自己的 Java 调用约定，与 C ABI 不同：

x86_64 Java 调用约定：
- 整数参数：`j_rarg0 - j_rarg5`（映射到 `rdi, rsi, rdx, rcx, r8, r9`）
- 浮点参数：`j_farg0 - j_farg7`（映射到 `xmm0 - xmm7`）
- callee-saved 寄存器比 C ABI 更多，减少编译器保存/恢复开销

AArch64 Java 调用约定：
- 整数参数：`j_rarg0 - j_rarg7`（映射到 `r0 - r7`）
- 浮点参数：`j_farg0 - j_farg7`（映射到 `v0 - v7`）

### 3.3.3 帧指针与调用链

```
x86_64 栈帧布局：
  +-------------------+
  | 返回地址          | ← call 指令自动压入
  | 旧 RBP           | ← push rbp
  | ...               |
  RBP → 局部变量      |
  | ...               |
  RSP → 栈顶          |
  +-------------------+

AArch64 栈帧布局：
  +-------------------+
  | 返回地址 (LR)     | ← stp x29, x30, [sp, #-16]!
  | 旧 FP (X29)       |
  | ...               |
  FP → 局部变量       |
  | ...               |
  SP → 栈顶           |
  +-------------------+
```

AArch64 使用 `STP/LDP`（Store/Load Pair）指令高效地保存/恢复帧指针和链接寄存器，一条指令完成两个 64 位寄存器的操作。

---

## 3.4 条件标志与内存屏障的跨架构实现

### 3.4.1 条件标志

JVM 的条件判断需要映射到各架构的条件标志：

**x86_64**：使用 `RFLAGS` 寄存器中的标志位：
- `ZF`（Zero Flag）：相等比较
- `CF`（Carry Flag）：无符号比较
- `SF`/`OF`（Sign/Overflow Flag）：有符号比较

```cpp
enum Condition {
    zero          = 0x4,  // ZF=1
    notZero       = 0x5,  // ZF=0
    equal         = 0x4,  // ZF=1
    notEqual      = 0x5,  // ZF=0
    less          = 0xc,  // SF≠OF
    lessEqual     = 0xe,  // ZF=1 or SF≠OF
    greater       = 0xf,  // ZF=0 and SF=OF
    greaterEqual  = 0xd,  // SF=OF
};
```

**AArch64**：没有独立的标志寄存器，条件作为指令的一部分（`CMP` → `B.cond`）：

```cpp
enum Condition {
    eq, ne,   // equal / not equal
    lt, le,   // signed less / less-or-equal
    gt, ge,   // signed greater / greater-or-equal
    lo, ls,   // unsigned lower / lower-or-same
    hi, hs,   // unsigned higher / higher-or-same
};
```

**RISC-V**：没有条件标志寄存器，条件分支直接比较两个寄存器：
- `beq rs1, rs2, offset`（branch if equal）
- `blt rs1, rs2, offset`（branch if less than）

### 3.4.2 内存屏障

JVM 的 `OrderAccess` 抽象了四种内存屏障：

```cpp
// orderAccess.hpp
class OrderAccess {
    static void loadload();    // LoadLoad 屏障
    static void storestore();  // StoreStore 屏障
    static void loadstore();   // LoadStore 屏障
    static void storeload();   // StoreLoad 屏障（最强，最昂贵）
    static void release();     // = LoadLoad + StoreStore
    static void acquire();     // = LoadLoad + LoadStore
    static void fence();       // = 全屏障
};
```

**各架构实现**：

| 屏障 | x86_64 | AArch64 | RISC-V |
|------|--------|---------|--------|
| LoadLoad | `nop`（TSO 保证） | `dmb ishld` | `fence r,r` |
| StoreStore | `nop`（TSO 保证） | `dmb ish` | `fence w,w` |
| LoadStore | `nop`（TSO 保证） | `dmb ish` | `fence r,w` |
| StoreLoad | `mfence` 或 `lock addl $0,(rsp)` | `dmb ish` | `fence w,r` |
| Full Fence | `mfence` | `dmb ish` | `fence rw,rw` |

x86_64 的优势最为明显：由于其 Total Store Ordering（TSO）内存模型，LoadLoad、StoreStore、LoadStore 屏障都是空操作——硬件已经保证了这些顺序。只有 StoreLoad 屏障需要 `mfence` 指令。

这意味着在 x86 上，`volatile` 读的开销几乎为零（普通读取即可），`volatile` 写只需一条 `mfence`。而在 AArch64 和 RISC-V 上，`volatile` 操作需要真正的内存屏障指令，开销更高。

这个差异直接影响了不同平台上 `ConcurrentHashMap`、`AtomicReference` 等并发原语的性能特征。

---

## 3.5 [专题] RISC-V 向量扩展（V 扩展）与 JDK Vector API 的适配路径

### 3.5.1 RISC-V V 扩展概述

RISC-V 向量扩展（V 扩展）是 RISC-V 指令集中最复杂的扩展之一，提供了可变长度向量（VLEN 可从 128 到 1024 位），与 x86 的固定宽度 SIMD（SSE/AVX）和 AArch64 的 SVE/SVE2 有本质区别。

### 3.5.2 JVM 中的 RISC-V 向量适配

在 `cpu/riscv/` 目录中，向量支持通过以下文件实现：

```
cpu/riscv/
├── assembler_riscv.hpp           # 基础向量指令定义
├── c2_MacroAssembler_riscv.cpp   # C2 编译器的向量代码生成
├── riscv_v.ad                    # C2 向量指令匹配规则
└── vm_version_riscv.cpp          # V 扩展特性探测
```

RISC-V 向量指令的编程模型与 x86/AArch64 有根本差异：

**x86 AVX**：固定宽度向量
```cpp
// 256 位 = 4 个 int，固定
__ vaddpd(ymm0, ymm1, ymm2);  // 4 个 double 加法
```

**AArch64 SVE**：可变长度向量，但编程时用谓词寄存器
```cpp
__ fadd(z0, z1, z2);  // 受 p0 谓词控制
```

**RISC-V V**：可变长度向量 + 配置寄存器
```cpp
// 先配置向量长度和元素类型
__ vsetvli(t0, x0, Assembler::e32, Assembler::m1);  // 32-bit 元素，1 组
// 然后执行向量操作
__ vadd_vv(v0, v1, v2);  // 向量加法
```

`vsetvli`（Vector Set Vector Length Immediate）是 RISC-V V 扩展的核心指令，它根据请求的元素宽度和分组模式，设置当前可用的向量长度。

### 3.5.3 Vector API 的适配挑战

JDK 的 Vector API（`jdk.incubator.vector`）需要在不同架构上提供统一的向量编程接口。RISC-V 的可变长度模型带来了独特的挑战：

1. **向量长度不确定**：编译时不知道 VLEN，需要在运行时查询
2. **配置开销**：每次向量操作前可能需要 `vsetvli` 配置
3. **C2 自动向量化**：`superword` 需要生成正确的 `vsetvli` + 向量操作序列

这些挑战正在被逐步解决——JDK 27 的 RISC-V 向量支持已经覆盖了大部分 Vector API 操作。

---

## 3.6 [AI 时代思考] 异构计算：当 JVM 遇到 NPU/GPU——Foreign API 的硬件意义

### 3.6.1 当前的异构计算瓶颈

AI 推理的核心计算已经从 CPU 迁移到 GPU/NPU。但 Java 生态与 GPU 之间始终隔着一层 JNI + 本地库：

```
Java 应用 → JNI → 本地推理库（ONNX Runtime / TensorRT） → GPU 驱动 → GPU
```

这条链路的问题：
1. **JNI 开销**：每次跨 Java-Native 边界都有数微秒开销
2. **数据拷贝**：Java 堆到 Native 内存的拷贝（无法共享 GPU 内存）
3. **编程复杂度**：需要手写 C/C++ 桥接代码

### 3.6.2 Panama Foreign Function & Memory API 的变革

JDK 22 正式引入的 Panama FFM API 从三个层面改变了这个局面：

**1. 内存访问**：直接操作堆外内存，无需 JNI

```java
// 分配堆外内存，可被 GPU 直接访问
Arena arena = Arena.ofShared();
MemorySegment data = arena.allocate(1024 * 1024 * 4, ValueLayout.JAVA_INT);
```

**2. 函数调用**：无需 JNI 桥接代码即可调用本地函数

```java
// 直接链接 CUDA 运行时函数
Linker linker = Linker.nativeLinker();
SymbolLookup cudaLookup = SymbolLookup.libraryLookup("libcuda.so", arena);
MethodHandle cudaMalloc = linker.downcallHandle(
    cudaLookup.find("cuMemAlloc_v2").get(),
    FunctionDescriptor.of(ValueLayout.JAVA_LONG, ValueLayout.JAVA_LONG)
);
```

**3. 向量计算**：Vector API 在 CPU 端进行 SIMD 优化

```java
// CPU 端的向量化预处理
FloatVector a = FloatVector.fromArray(SPECIES_256, inputArray, 0);
FloatVector b = FloatVector.fromArray(SPECIES_256, weightArray, 0);
FloatVector c = a.mul(b).add(bias);  // 一条 FMADD 指令
```

### 3.6.3 JVM 作为 AI Runtime 的可能性

Panama + Vector API + 虚拟线程的组合，为 JVM 成为 AI Runtime 提供了基础：

| 能力 | JVM 技术栈 | AI 推理场景 |
|------|-----------|------------|
| 异构内存 | Panama MemorySegment | GPU/NPU 内存池管理 |
| 低开销调用 | Panama Downcall | 直接调用 CUDA/Vulkan Compute |
| CPU 向量化 | Vector API | 预处理/后处理算子 |
| 高并发调度 | Virtual Thread | 百万级推理请求并发 |
| 零拷贝传输 | MemorySegment + mmap | KV Cache 共享 |

从 CPU 架构的角度看，Panama 的 `MemorySegment` 本质上绕过了 JVM 堆的间接层——应用可以直接操作虚拟地址空间，与 GPU 的 DMA 引擎协作。而 Vector API 则确保在 CPU 端也不会浪费 SIMD 计算能力。

这是一种新的架构范式：**JVM 不再仅仅是「Java 字节码的执行器」，而是「异构计算资源的协调器」**。

---

## 小结

本章剖析了 JVM 的 CPU 架构适配层：

1. **七种架构**各有完整适配，文件结构高度统一
2. **Assembler → MacroAssembler** 两层抽象，从指令编码到函数级代码生成
3. **ABI 适配**是 JVM 与 OS/硬件的协议接口，Windows/Linux 的差异在源码中显式处理
4. **内存屏障**的跨架构差异直接影响了并发原语的性能——x86 的 TSO 模型是最优的
5. **RISC-V 向量扩展**的可变长度模型为 Vector API 带来独特挑战
6. **Panama FFM API** 使 JVM 具备了异构计算协调能力，这是 AI 时代 Java 最重要的基础设施升级之一

第一篇到此结束。我们已经理解了 JVM 启动、OS 适配和 CPU 适配三个基础维度。第二篇将深入内存管理——从 Arena 分配器到 ZGC 的着色指针，这是 JVM 最复杂也最精妙的子系统。
