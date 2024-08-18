---
chapter: 17
part: 第四篇 同步与并发 —— 多核的正确性保障
title: 内存序与屏障
source_anchor:
  - kernel/locking/lockdep.c
  - arch/x86/include/asm/barrier.h
  - include/asm-generic/barrier.h
  - include/linux/compiler.h
status: done
---

# 第17章 内存序与屏障

## 写作目标

理解内存序的硬件根源与内核抽象，掌握内存屏障的使用，理解lockdep死锁检测的原理。

## 章节大纲

### 17.1 内存序的硬件根源

- 编译器重排：优化导致指令顺序变化
- CPU重排：Store Buffer/Invalidate Queue导致可见性延迟
- StoreLoad重排：最常见的重排类型
- x86的TSO(Total Store Order)模型：只允许StoreLoad重排
- ARM/RISC-V的弱序模型：允许更多重排
- 为什么多核正确性需要内存序保障

### 17.2 内存屏障

- x86屏障指令：
  - mfence：全屏障
  - sfence：写屏障
  - lfence：读屏障
  - LOCK前缀的屏障语义
- Linux内核的屏障抽象：
  - `smp_mb()`：全屏障
  - `smp_wmb()`：写屏障
  - `smp_rmb()`：读屏障
  - `smp_store_release()`/`smp_load_acquire()`：消息传递模式
- `READ_ONCE()`/`WRITE_ONCE()`：防止编译器优化
  - `include/linux/compiler.h`中的实现
- *数据库视角*：内存序对无锁数据结构正确性的影响——误用屏障导致的并发bug

### 17.3 lockdep：死锁检测

- **精读** `kernel/locking/lockdep.c`：
  - 锁依赖图的构建
  - 死锁模式的检测：AA/ABBA/IRQL等
  - 锁类的抽象与统计
- `kernel/locking/lockdep_internals.h`/`kernel/locking/lockdep_proc.c`
- `kernel/locking/lock_events.c`：锁事件统计
- lockdep的局限性：只能检测执行过的路径

### 17.4 其他检测工具

- `kernel/locking/locktorture.c`：锁压力测试
- `kernel/locking/test-ww_mutex.c`：ww_mutex测试
- `kernel/kcsan/`：并发SANitizer——检测数据竞争

## 关键源文件清单

| 文件 | 行数 | 关注点 |
|------|------|--------|
| `kernel/locking/lockdep.c` | ~5000 | 死锁检测 |
| `arch/x86/include/asm/barrier.h` | ~100 | x86屏障定义 |
| `include/linux/compiler.h` | ~300 | READ_ONCE/WRITE_ONCE |

## 跨章依赖

- 依赖第1章（x86）：LOCK前缀与屏障的硬件语义
- 贯穿第三篇（内存管理）和第四篇（同步）：内存序是正确性的基础
