# 第1章 x86：从指令执行到特权级切换

> 源码锚点：`arch/x86/entry/entry_64.S`、`arch/x86/entry/entry_64_fred.S`、`arch/x86/entry/syscall_64.c`、`kernel/entry/common.c`、`arch/x86/mm/pti.c`

理解操作系统的起点，不在软件，而在硬件。Linux内核的每一个关键设计决策——为什么进程切换要保存GS基址、为什么系统调用入口要用swapgs、为什么要有KPTI页表隔离——都根植于x86架构的硬件机制。本章从CPU如何执行指令讲起，逐步聚焦到特权级隔离与系统调用入口，建立对"硬件如何支撑OS"的精确认知。

## 1.1 流水线、乱序执行与分支预测

### 指令执行的本质

一条x86指令从取指到结果写回，并非一步完成。现代x86 CPU的流水线深度超过15级——取指(Fetch)、解码(Decode)、重命名(Rename)、分发(Dispatch)、执行(Execute)、写回(Writeback)，每一级都在不同的硬件单元上并行工作。

流水线的意义在于**吞吐**：虽然单条指令的延迟并未缩短，但每个时钟周期都能完成一条指令的退休(retire)，形成"每周期一指令"的稳态。这就像工厂流水线——产品从原料到成品需要10个工位，但每个工位同时在处理不同的产品，最终每天下线的成品远多于单工位生产。

### 乱序执行：吞吐的进一步优化

流水线面临一个核心问题：如果下一条指令的操作数依赖上一条指令的结果（数据依赖），流水线必须暂停等待( stall)。为了减少stall，现代x86 CPU实现了乱序执行(Out-of-Order Execution)。

乱序执行的关键硬件结构：

- **重排序缓冲区(ROB, Reorder Buffer)**：跟踪所有在飞(in-flight)的指令，确保它们按程序序退休
- **保留站(Reservation Station)**：指令在此等待操作数就绪，就绪后立即发射到执行单元
- **寄存器重命名(Register Renaming)**：消除假依赖(WAR/WAW)，只保留真依赖(RAW)

乱序执行的窗口大小决定了CPU能"看"多远——Intel Skylake的ROB条目数为224，AMD Zen 3为256。窗口越大，能发现的并行度越高，但硬件面积和功耗也越大。

乱序执行的核心原则：**指令可以乱序执行，但必须按序退休**。ROB保证了程序可见的语义不变——只有在前面所有指令都无异常地退休后，当前指令的结果才被提交。

### 分支预测：猜对是关键

条件跳转指令（如`if-else`编译出的`jne`）在解码阶段无法确定下一条指令的地址——条件码要等执行阶段才能计算出来。如果等待，流水线必须stall数十个周期。

分支预测器的解决方案：**猜，然后验证**。

- **静态预测**：最简单的策略——向后跳转预测为taken（循环），向前跳转预测为not taken。准确率约60-70%。
- **动态预测**：基于历史行为的预测。
  - **BTB(Branch Target Buffer)**：记录跳转目标地址。通过PC值索引，直接预测下一条指令地址。
  - **2-bit饱和计数器**：每个分支维护一个2-bit状态机(强不跳转→弱不跳转→弱跳转→强跳转)，只有连续两次预测错误才翻转方向。
  - **RAS(Return Address Stack)**：专门预测函数返回地址。`call`压栈、`ret`弹栈，行为高度规律。
- **混合预测**：现代CPU同时使用多种预测器，最终选择置信度最高的预测。

现代分支预测器的准确率可达95%以上。但5%的误预测代价巨大——流水线必须冲刷(flush)，典型代价是15-20个周期。

### Spectre与Meltdown：乱序执行的硬件侧信道

2018年爆出的Spectre/Meltdown漏洞揭示了乱序执行的一个根本性问题：**虽然乱序执行的结果在误预测时会被丢弃，但微架构状态的变更不会回滚**。

具体机制：

1. 攻击者构造一段代码，包含一个条件分支
2. 通过训练分支预测器，使其预测taken
3. 在预测执行的路径上，攻击者访问受保护的内核内存，并基于该内存值的位置影响Cache状态
4. 即使预测错误后结果被丢弃，Cache状态的改变已不可逆
5. 攻击者通过计时攻击(Flush+Reload)探测Cache状态，间接读取内核数据

Meltdown的攻击更直接：利用x86的乱序执行特性，在权限检查完成前就执行了内存访问指令，访问了本不应可读的内核页面。

**KPTI——软件缓解方案**

Linux的KPTI(Kernel Page-Table Isolation)是Meltdown的软件缓解，实现在`arch/x86/mm/pti.c`中：

```c
// arch/x86/mm/pti.c — 文件头注释
// "Kernel/User page tables isolation"
// 基于 KAISER: https://github.com/IAIK/KAISER
```

KPTI的核心思想：**用户态运行时，页表中不映射内核地址空间**。每个进程维护两套页表：

- **内核页表**：完整映射，包含用户空间和内核空间
- **用户页表**：只映射用户空间，以及少量必须在用户态可访问的内核入口代码

代价是明显的：每次系统调用和中断都需要切换页表——在`entry_64.S`中可以看到`SWITCH_TO_KERNEL_CR3`和`SWITCH_TO_USER_CR3_STACK`宏的调用。页表切换需要刷新TLB，每次系统调用增加约数百纳秒的开销。

> **数据库视角**：分支预测对向量化执行的影响。在向量化执行引擎中，`if`条件通常被编译为分支或select指令。分支预测失败会导致流水线冲刷，对于选择性低（大量数据通过/不通过）的场景，应优先使用无分支的select(masked load/store)；对于选择性高的场景，分支预测准确率高，分支反而更快。现代CPU的LBR(Last Branch Record)和PMU计数器(BR_MISP_RETIRED)可以量化分支预测失败率，指导优化决策。

## 1.2 SIMD与向量指令

### 向量寄存器的演进

x86的SIMD(Single Instruction Multiple Data)指令集经历了持续的扩展：

| 指令集 | 寄存器 | 位宽 | 数据类型 |
|--------|--------|------|----------|
| SSE/SSE2 | XMM0-15 | 128 bit | 4×float / 2×double / 16×int8 |
| AVX | YMM0-15 | 256 bit | 8×float / 4×double |
| AVX-512 | ZMM0-31 | 512 bit | 16×float / 8×double |

AVX-512还引入了8个opmask寄存器(k0-k7)，支持条件化的向量操作——不通过分支，而是通过掩码选择性地对部分lane执行操作。

### 编码与指令格式

- **VEX前缀**：AVX/AVX2使用VEX(Vector Extension)编码，2字节或3字节前缀替代了传统的操作码前缀
- **EVEX前缀**：AVX-512使用EVEX(Enhanced VEX)编码，4字节前缀，支持更多寄存器、掩码和广播

### 向量宽度的权衡：128/256/512

AVX-512并非"越宽越好"。512位向量运算的功耗显著高于256位——Intel CPU在大量使用AVX-512时会发生降频(license-based frequency scaling)。这也是为什么某些云服务商在虚拟机中禁用了AVX-512。

实践中的选择：
- **通用计算**：AVX2(256 bit)是性价比最优的选择
- **数值密集型**：AVX-512在矩阵乘法等场景收益显著
- **数据库向量化引擎**：多数实现选择AVX2，避免降频对整体吞吐的影响

> **数据库视角**：向量化执行引擎(Volcano/Vectorized Model)的核心设计——每次处理一批(Batch)数据而非一行，利用SIMD指令并行处理Batch中的多行。例如，8个32位整数的同时比较可以用一条`_mm256_cmpeq_epi32`完成，比标量循环快8倍。ClickHouse、Velox等引擎大量使用AVX2/AVX-512加速过滤、投影、聚合算子。

> **AI视角**：LLM推理的算力瓶颈——矩阵乘法，本质上是大量的乘加操作(MAC)。SIMD/向量指令是这些操作的硬件基础。GPU的SIMT模型可以视为SIMD的极端扩展——一条指令驱动数千个线程( lane)执行相同操作，不同线程通过不同的数据地址实现并行。

## 1.3 特权级与模式切换

### Ring 0/1/2/3

x86架构定义了4个特权级(Ring 0-3)，数字越小权限越高：

```
Ring 0 ─── 内核模式 (Kernel Mode)
Ring 1 ─── (未使用)
Ring 2 ─── (未使用)
Ring 3 ─── 用户模式 (User Mode)
```

Linux只使用Ring 0和Ring 3。Ring 1和Ring 2在历史上用于OS/2等微内核系统，现代操作系统几乎不用。但有趣的是，虚拟化场景下VMX的root/non-root模式与Ring的概念正交——VMM运行在VMX root模式下的Ring 0，而客户机内核运行在VMX non-root模式的Ring 0。

### CPL/DPL/RPL

硬件如何检查特权级？x86通过三组位域实现：

- **CPL(Current Privilege Level)**：当前正在执行的代码段的特权级，存储在CS寄存器的低2位。用户态CPL=3，内核态CPL=0。
- **DPL(Descriptor Privilege Level)**：目标段/门的特权级，定义在GDT/LDT的段描述符中。
- **RPL(Requestor Privilege Level)**：请求者的特权级，存储在段选择子的低2位。

访问规则：**CPL ≤ DPL 且 RPL ≤ DPL**，即当前权限必须不低于目标权限。这确保了Ring 3的代码无法直接访问Ring 0的数据段。

### 模式切换的触发点

从用户态(Ring 3)到内核态(Ring 0)的切换只能通过以下三种硬件机制触发：

1. **系统调用(SYSCALL)**：用户程序主动请求内核服务
2. **中断(Interrupt)**：外部设备或定时器信号
3. **异常(Exception)**：CPU执行指令时检测到错误（缺页、除零、一般保护错误等）

这三种机制共同的特点是：**切换由硬件原子完成**——CPU在一条指令内完成CS/RIP/RFLAGS的切换，不存在"半用户半内核"的中间态。这是特权级隔离的硬件根基。

### 为什么要特权级？

保护的本质是隔离。没有特权级，任何用户程序都可以直接读写内核数据结构、修改页表、配置硬件设备——一个buggy程序就能让整个系统崩溃。特权级让内核拥有仲裁者地位：所有涉及全局状态的请求都必须经过内核检查，内核可以拒绝非法请求。

当然，特权级也带来代价：每次系统调用都需要Ring切换，涉及寄存器保存、栈切换、页表切换——这是系统调用开销的硬件根源。

## 1.4 系统调用入口：从int 0x80到FRED

### int 0x80：中断门时代

32位Linux最早的系统调用机制是`int 0x80`——软件中断。CPU通过IDT(Interrupt Descriptor Table)查找0x80号中断门，从中获取内核代码段的段选择子和入口地址，然后切换到内核栈执行。

`int 0x80`的代价：
- 查IDT需要至少一次内存访问
- 需要切换栈（用户栈→内核栈）
- 需要保存完整的寄存器上下文
- 中断门会自动清除IF标志（关中断）
- 返回使用`iret`，需要恢复所有状态

典型开销：200-300个时钟周期。

### sysenter/sysexit：快速系统调用指令对

Intel在Pentium Pro中引入了`sysenter/sysexit`，AMD在K7中引入了`syscall/sysret`。这些"快速系统调用"指令直接从MSR(Model Specific Register)读取入口地址，跳过IDT查找。

Linux在2.6内核中引入了`sysenter`支持，通过vDSO机制让用户态程序无需硬编码入口指令。

### syscall/sysret：64位时代的标准路径

x86-64规范规定`syscall`/`sysret`是64位代码的系统调用机制。硬件行为精确定义：

**syscall指令执行时硬件做了什么：**
1. `RCX ← RIP`（保存返回地址到RCX）
2. `R11 ← RFLAGS`（保存标志位到R11）
3. `RIP ← IA32_LSTAR_MSR`（从MSR加载内核入口地址）
4. `CS ← IA32_STAR_MSR[47:32]`（加载内核代码段）
5. `SS ← IA32_STAR_MSR[47:32] + 8`（加载内核数据段）
6. `RFLAGS ← RFLAGS AND NOT IA32_FMASK_MSR`（清除FMASK指定的标志位）

**注意：syscall不保存RSP，不切换栈。** 这是设计者有意为之——减少硬件做的事，把栈切换留给软件完成，保持灵活性。

**sysret指令执行时硬件做了什么：**
1. `RIP ← RCX`（恢复返回地址）
2. `RFLAGS ← R11`（恢复标志位）
3. `CS/SS`恢复为用户态段选择子

### 精读 entry_64.S：syscall入口的汇编流程

`arch/x86/entry/entry_64.S`中的`entry_SYSCALL_64`是64位系统调用的入口。让我们逐行分析其关键步骤：

```asm
SYM_CODE_START(entry_SYSCALL_64)
    UNWIND_HINT_ENTRY
    ENDBR                          // CET间接分支追踪标记

    swapgs                         // ① 交换GS基址
    movq  %rsp, PER_CPU_VAR(cpu_tss_rw + TSS_sp2)  // ② 保存用户RSP到TSS
    SWITCH_TO_KERNEL_CR3 scratch_reg=%rsp            // ③ 切换到内核页表(KPTI)
    movq  PER_CPU_VAR(cpu_current_top_of_stack), %rsp // ④ 加载内核栈顶
```

**① swapgs**——这是整个入口最关键的一条指令。

x86-64的GS寄存器有两份基址：一份由`MSR_GS_BASE`寻址，另一份由`MSR_KERNEL_GS_BASE`寻址。用户态运行时，`MSR_GS_BASE`指向用户态的thread-local storage，`MSR_KERNEL_GS_BASE`指向内核的per-CPU数据区。`swapgs`指令交换这两个MSR的值——执行后，GS基址立即指向内核per-CPU数据区，内核可以通过`PER_CPU_VAR`宏访问当前CPU的独占数据。

为什么不直接写MSR？因为写MSR需要两次`wrmsr`，而`swapgs`是一条指令原子完成，不可中断。

**② 保存用户RSP**——syscall不保存RSP，所以软件必须自己保存。用户RSP被暂存到TSS(Task State Segment)的`sp2`字段——这是一个scratch空间，因为TSS是per-CPU数据，不会被其他CPU的入口路径干扰。

**③ 切换内核页表**——这是KPTI的页表切换。在Meltdown缓解开启时，用户态页表不映射内核地址空间，必须在入口第一时间切换到内核页表。

**④ 加载内核栈**——从per-CPU变量`cpu_current_top_of_stack`获取当前进程的内核栈顶。此时已经在使用内核GS基址，所以能正确访问per-CPU变量。

接下来，入口代码构建`pt_regs`结构——在内核栈上保存完整的寄存器上下文：

```asm
    pushq  $__USER_DS                   // pt_regs->ss
    pushq  PER_CPU_VAR(cpu_tss_rw + TSS_sp2)  // pt_regs->sp (用户RSP)
    pushq  %r11                          // pt_regs->flags (R11=原RFLAGS)
    pushq  $__USER_CS                    // pt_regs->cs
    pushq  %rcx                          // pt_regs->ip (RCX=原RIP)
    pushq  %rax                          // pt_regs->orig_ax (系统调用号)
    PUSH_AND_CLEAR_REGS rax=$-ENOSYS     // 保存所有通用寄存器，RAX初始化为-ENOSYS
```

`PUSH_AND_CLEAR_REGS`保存所有15个通用寄存器，并清除它们（防止内核代码意外使用用户态寄存器值，这也是Spectre缓解的一部分——`CLEAR_REGS`清除寄存器内容，防止推测执行泄漏用户态数据）。

随后，调用C函数`do_syscall_64`：

```asm
    movq  %rsp, %rdi                     // 第1个参数: pt_regs指针
    movslq  %eax, %rsi                   // 第2个参数: 系统调用号(符号扩展)
    IBRS_ENTER                           // Spectre缓解: 间接分支限制
    UNTRAIN_RET                          // Retpoline: 训练返回预测器
    CLEAR_BRANCH_HISTORY                 // BHI缓解: 清除分支历史
    call  do_syscall_64                   // 进入C代码
```

**返回路径**也值得精读。`do_syscall_64`返回后，代码尝试使用`sysret`快速返回——sysret比iret快，但有严格限制：

```asm
    // do_syscall_64返回true表示可以使用sysret
    ALTERNATIVE "testb %al, %al; jz swapgs_restore_regs_and_return_to_usermode", \
        "jmp swapgs_restore_regs_and_return_to_usermode", X86_FEATURE_XENPV
```

`sysret`的限制条件（在`do_syscall_64`的C代码中检查）：
- `RCX == RIP`（sysret从RCX恢复RIP）
- `R11 == RFLAGS`（sysret从R11恢复RFLAGS）
- CS和SS必须是标准用户段选择子
- RIP必须在非规范地址以下（< TASK_SIZE_MAX），否则Intel CPU会#GP
- RFLAGS中不能有RF或TF位

如果任一条件不满足，走`iret`慢路径——iret更通用但更慢，因为它完整恢复SS:RSP、CS:RIP、RFLAGS。

### FRED：统一入口的新时代

FRED(Flexible Return and Event Delivery)是x86架构的最新入口机制，在Linux 7.0中得到支持。FRED的核心改进是**统一了所有入口类型**——系统调用、中断、异常不再各自有独立的入口路径和不同的硬件行为。

**精读 `arch/x86/entry/entry_64_fred.S`：**

```asm
    .align 4096                    // FRED要求Ring 3入口4K对齐
SYM_CODE_START_NOALIGN(asm_fred_entrypoint_user)
    FRED_ENTER                     // 保存寄存器，设置pt_regs
    call  fred_entry_from_user     // 调用C入口
asm_fred_exit_user:
    FRED_EXIT                      // 恢复寄存器
1:  ERETU                          // 返回用户态

    .org asm_fred_entrypoint_user + 256  // Ring 0入口在Ring 3入口+256处
SYM_CODE_START_NOALIGN(asm_fred_entrypoint_kernel)
    FRED_ENTER
    call  fred_entry_from_kernel
    FRED_EXIT
    ERETS                          // 返回内核态
```

FRED的简洁令人印象深刻——与`entry_64.S`中上千行的入口代码相比，FRED入口只有几十行。原因是FRED将大量工作下放到硬件：

- **硬件自动切换栈**：不再需要软件手动加载内核栈
- **硬件自动保存RSP**：不再需要TSS_sp2的scratch空间
- **硬件自动推送错误码和事件信息**：不再需要软件区分有无错误码的异常
- **统一的ERETU/ERETS返回指令**：不再需要区分sysret和iret

FRED的硬件栈帧格式固定为64字节，包含Error Code、RIP、CS+Aux Info、RFLAGS、RSP、SS+Event Info、Event Data、Reserved。这种固定格式简化了软件的栈帧解析。

FRED消除了传统入口路径中的分支预测失败点——不再需要`swapgs`、不再需要手动判断入口来源、不再需要区分syscall和中断的不同处理路径。每一个分支预测失败都可能成为侧信道攻击的载体，FRED通过减少分支提升了安全性。

> **数据库视角**：高精度时间戳获取的开销。数据库事务的计时（`CURRENT_TIMESTAMP`、`statement_timeout`、WAL时间戳）依赖高精度时钟。传统路径通过`gettimeofday`系统调用获取时间，每次调用约200-300ns。vDSO将`gettimeofday`映射到用户态执行，无需进入内核，开销降至约20ns。对于每秒百万次时间戳获取的高吞吐场景，这个差异是显著的。后续第19章会深入分析时间子系统。

## 1.5 系统调用表的生成与分发

### 系统调用号到函数的映射

**精读 `arch/x86/entry/syscall_64.c`：**

```c
// 声明所有系统调用函数
#define __SYSCALL(nr, sym) extern long __x64_##sym(const struct pt_regs *);
#include <asm/syscalls_64.h>
#undef  __SYSCALL

// 生成传统系统调用表(仅用于追踪)
#define __SYSCALL(nr, sym) __x64_##sym,
const sys_call_ptr_t sys_call_table[] = {
#include <asm/syscalls_64.h>
};
#undef  __SYSCALL

// 生成直接分发函数(实际使用)
#define __SYSCALL(nr, sym) case nr: return __x64_##sym(regs);
long x64_sys_call(const struct pt_regs *regs, unsigned int nr)
{
    switch (nr) {
    #include <asm/syscalls_64.h>
    default: return __x64_sys_ni_syscall(regs);
    }
}
```

这里有一个重要的设计选择：Linux 7.0**不再使用`sys_call_table[]`数组索引进行系统调用分发**，而是使用`x64_sys_call()`的`switch-case`。原因：

1. **安全性**：数组索引可以被Spectre变体利用——通过训练分支预测器，越界读取`sys_call_table`后面的函数指针。`switch-case`编译后使用比较链，更难被利用。
2. **编译器优化**：现代编译器可以将`switch-case`优化为二分查找或跳转表，性能不输数组索引。
3. **`array_index_nospec`**：即使使用数组，也需要此宏屏蔽越界索引的推测执行：

```c
static __always_inline bool do_syscall_x64(struct pt_regs *regs, int nr)
{
    unsigned int unr = nr;
    if (likely(unr < NR_syscalls)) {
        unr = array_index_nospec(unr, NR_syscalls);  // 屏蔽越界索引
        regs->ax = x64_sys_call(regs, unr);
        return true;
    }
    return false;
}
```

### do_syscall_64：C层的完整分发

**精读 `arch/x86/entry/syscall_64.c` 中的 `do_syscall_64`：**

```c
__visible noinstr bool do_syscall_64(struct pt_regs *regs, int nr)
{
    nr = syscall_enter_from_user_mode(regs, nr);   // ① 进入前处理

    instrumentation_begin();
    add_random_kstack_offset();                     // ② 栈随机化

    if (!do_syscall_x64(regs, nr) && !do_syscall_x32(regs, nr) && nr != -1) {
        regs->ax = __x64_sys_ni_syscall(regs);     // ③ 未实现的系统调用
    }

    instrumentation_end();
    syscall_exit_to_user_mode(regs);                // ④ 退出处理

    // 判断是否可以使用SYSRET快速返回
    if (cpu_feature_enabled(X86_FEATURE_XENPV))
        return false;
    if (unlikely(regs->cx != regs->ip || regs->r11 != regs->flags))
        return false;
    if (unlikely(regs->cs != __USER_CS || regs->ss != __USER_DS))
        return false;
    if (unlikely(regs->ip >= TASK_SIZE_MAX))
        return false;
    if (unlikely(regs->flags & (X86_EFLAGS_RF | X86_EFLAGS_TF)))
        return false;
    return true;  // 使用SYSRET
}
```

关键步骤解读：

**① `syscall_enter_from_user_mode`**——定义在`kernel/entry/common.c`的框架中，完成以下工作：
- 标记RCU进入用户态的退出
- 启用lockdep
- 检查线程标志(TIF)是否有pending工作（信号、重调度等）

**② `add_random_kstack_offset`**——在pt_regs之前插入随机大小的padding，使每次系统调用的内核栈位置不同，增加栈溢出攻击的难度。

**④ `syscall_exit_to_user_mode`**——返回用户态前的处理，包含重要的`exit_to_user_mode_loop`：

```c
// kernel/entry/common.c
static __always_inline unsigned long __exit_to_user_mode_loop(
    struct pt_regs *regs, unsigned long ti_work)
{
    while (ti_work & EXIT_TO_USER_MODE_WORK_LOOP) {
        local_irq_enable();

        if (ti_work & (_TIF_NEED_RESCHED | _TIF_NEED_RESCHED_LAZY))
            schedule();                    // 需要重新调度

        if (ti_work & _TIF_UPROBE)
            uprobe_notify_resume(regs);    // 用户态探针

        if (ti_work & (_TIF_SIGPENDING | _TIF_NOTIFY_SIGNAL))
            arch_do_signal_or_restart(regs); // 信号处理

        if (ti_work & _TIF_NOTIFY_RESUME)
            resume_user_mode_work(regs);    // 通知恢复

        local_irq_disable();
        ti_work = read_thread_flags();      // 重新检查，可能有新标志
    }
    return ti_work;
}
```

这个循环确保：**返回用户态前，所有pending工作必须处理完毕**。这包括信号投递、调度、livepatch等。如果处理过程中又设置了新标志，循环会继续。

### 参数传递约定

x86-64系统调用的参数通过寄存器传递，约定如下：

| 参数 | 寄存器 | 备注 |
|------|--------|------|
| 系统调用号 | RAX | — |
| arg0 | RDI | — |
| arg1 | RSI | — |
| arg2 | RDX | — |
| arg3 | R10 | C ABI用RCX，但RCX被syscall保存返回地址 |
| arg4 | R8 | — |
| arg5 | R9 | — |
| 返回地址 | RCX | 硬件自动保存 |
| 原RFLAGS | R11 | 硬件自动保存 |

注意arg3使用R10而非RCX——因为`syscall`指令将RIP保存到RCX，覆盖了RCX的原值。在入口代码中，`PUSH_AND_CLEAR_REGS`会将R10移动到pt_regs中RCX的位置，使C代码按正常ABI访问参数。

系统调用最多传递6个参数。超过6个参数的系统调用（如`clone3`）通过将参数结构体指针作为单个参数传递，在内核中再解析结构体。

### 完整的系统调用生命周期

将1.4节和1.5节的内容串联起来，一次系统调用的完整生命周期：

```
用户态                              内核态
  │                                   │
  ├─── syscall指令 ──────────────────►│
  │    (RCX←RIP, R11←RFLAGS)          │
  │                                   ├── swapgs
  │                                   ├── 保存用户RSP到TSS
  │                                   ├── SWITCH_TO_KERNEL_CR3 (KPTI)
  │                                   ├── 加载内核栈
  │                                   ├── 构建pt_regs
  │                                   ├── IBRS_ENTER / UNTRAIN_RET
  │                                   ├── call do_syscall_64
  │                                   │   ├── syscall_enter_from_user_mode
  │                                   │   ├── add_random_kstack_offset
  │                                   │   ├── x64_sys_call (switch-case分发)
  │                                   │   │   └── 具体系统调用函数
  │                                   │   └── syscall_exit_to_user_mode
  │                                   │       └── exit_to_user_mode_loop
  │                                   │           ├── 处理信号
  │                                   │           ├── 处理重调度
  │                                   │           └── 处理其他TIF工作
  │                                   ├── POP_REGS
  │                                   ├── SWITCH_TO_USER_CR3 (KPTI)
  │                                   ├── swapgs
  │◄── sysretq / iretq ─────────────┤
  │    (RIP←RCX, RFLAGS←R11)         │
  │                                   │
```

每一次系统调用，这条路径都要完整走一遍。理解这条路径上的每一步，就理解了"系统调用为什么慢"的根本原因——不只是CPU指令的开销，还有安全缓解措施(KPTI/IBRS/UNTRAIN_RET)的叠加代价。在Meltdown之前，一次简单的`gettimeofday`约100ns；KPTI之后增加到约200ns。这也是vDSO如此重要的原因——它绕过了整条路径。

---

本章建立了对x86硬件支撑操作系统的理解：流水线与分支预测的性能影响、SIMD向量的数据库/AI应用、特权级的硬件隔离机制、系统调用入口的完整路径。后续章节将反复引用这些知识——第6章的进程切换依赖GS基址交换、第18章的中断入口与syscall入口的统一性、第25章eBPF JIT与SIMD的关系。理解硬件，是理解内核的起点。
