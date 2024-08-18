---
chapter: 1
part: 第一篇 硬件与架构 —— 计算的物理边界
title: x86：从指令执行到特权级切换
source_anchor:
  - arch/x86/entry/entry_64.S
  - arch/x86/entry/entry_64_fred.S
  - arch/x86/entry/entry_64_compat.S
  - arch/x86/entry/syscall_64.c
  - arch/x86/entry/vdso/
  - arch/x86/entry/vsyscall/
  - kernel/entry/common.c
  - arch/x86/kernel/cpu/
  - arch/x86/kernel/process_64.c
status: done
---

# 第1章 x86：从指令执行到特权级切换

## 写作目标

理解x86架构如何为操作系统提供硬件支撑，特别是特权级隔离与系统调用入口机制，这是所有后续"为什么OS这样设计"的硬件根源。

## 章节大纲

### 1.1 流水线、乱序执行与分支预测

- x86流水线深度与指令解码
- 乱序执行窗口与重排序缓冲区(ROB)
- 分支预测：静态/动态预测器、BTB、RAS
- Spectre/Meltdown：乱序执行的硬件侧信道
  - 为什么乱序执行会泄露信息——微架构侧信道的本质
  - KPTI(Kernel Page Table Isolation)：`arch/x86/mm/pti.c` 的软件缓解
- *数据库视角*：分支预测对向量化执行中if条件的影响

### 1.2 SIMD与向量指令

- SSE/AVX/AVX-512寄存器与指令概览
- VEX/EVEX编码前缀
- 向量宽度的选择：128/256/512 bit的功耗与频率权衡
- *数据库视角*：向量化执行引擎如何利用AVX2/AVX-512
- *AI视角*：LLM推理中矩阵乘法的SIMD/向量化基础

### 1.3 特权级与模式切换

- Ring 0/1/2/3与实际使用：OS只用Ring 0和Ring 3
- CPL/DPL/RPL与段选择子
- 从用户态到内核态的切换触发点：syscall/interrupt/exception
- *为什么硬件要提供特权级*——保护的本质是隔离

### 1.4 系统调用入口：从int 0x80到FRED

- int 0x80时代：中断门调用的代价
- sysenter/sysexit：快速系统调用指令对
- syscall/sysret：64位时代的标准路径
- **精读** `arch/x86/entry/entry_64.S`：syscall入口的汇编流程
  - 交换GS基址（内核per-CPU数据）
  - 保存用户态RSP到per-CPU区域
  - 建立内核栈帧
- FRED(Flexible Return and Event Delivery)：`entry_64_fred.S`
  - Linux 7.0的新入口机制
  - 统一中断/异常/系统调用入口
  - 减少入口路径的分支预测失败
- vDSO与vsyscall：`arch/x86/entry/vdso/`
  - 不进入内核的"系统调用"：gettimeofday的快速路径
  - *数据库视角*：高精度时间戳获取的开销

### 1.5 系统调用表的生成与分发

- **精读** `arch/x86/entry/syscall_64.c`
- `__SYSCALL`宏与系统调用号映射
- 系统调用分发的内核路径：`kernel/entry/common.c`
- 六个参数的传递约定：rdi/rsi/rdx/r10/r8/r9

## 关键源文件清单

| 文件 | 行数 | 关注点 |
|------|------|--------|
| `arch/x86/entry/entry_64.S` | ~1500 | syscall入口汇编 |
| `arch/x86/entry/entry_64_fred.S` | ~600 | FRED新入口 |
| `arch/x86/entry/syscall_64.c` | ~50 | 系统调用表生成 |
| `kernel/entry/common.c` | ~300 | 通用入口分发 |
| `arch/x86/mm/pti.c` | ~600 | KPTI页表隔离 |

## 跨章依赖

- 本章是第6章（进程切换）的前置：理解上下文切换中的GS切换
- 本章是第18章（中断）的前置：理解中断入口与syscall入口的统一性
