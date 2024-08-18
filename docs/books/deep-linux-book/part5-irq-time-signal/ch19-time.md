---
chapter: 19
part: 第五篇 中断、时间与信号 —— 异步事件的内核处理
title: 时间子系统
source_anchor:
  - kernel/time/clocksource.c
  - kernel/time/clockevents.c
  - kernel/time/hrtimer.c
  - kernel/time/posix-timers.c
  - kernel/time/posix-cpu-timers.c
  - kernel/time/tick-sched.c
  - kernel/time/timekeeping.c
  - kernel/time/timer.c
  - kernel/time/timer_migration.c
  - kernel/time/ntp.c
status: done
---

# 第19章 时间子系统

## 写作目标

理解Linux时间子系统的分层架构，从硬件时钟源到高精度定时器到POSIX定时器。

## 章节大纲

### 19.1 时钟源与时间保持

- **精读** `kernel/time/clocksource.c`：
  - `struct clocksource`：硬件时钟源抽象
  - TSC/HPET/ACPI PM Timer的精度与稳定性
  - 时钟源选择与watchdog
- **精读** `kernel/time/timekeeping.c`：
  - 系统时间的维护：CLOCK_REALTIME/CLOCK_MONOTONIC
  - `getnstimeofday()`的实现
  - NTP频率调整：`kernel/time/ntp.c`

### 19.2 时钟事件与tick

- **精读** `kernel/time/clockevents.c`：
  - `struct clock_event_device`：可编程定时器
  - oneshot vs periodic模式
- **精读** `kernel/time/tick-sched.c`：
  - tick设备管理
  - NOHZ_IDLE：空闲CPU关闭tick
  - NOHZ_FULL：孤立CPU的tickless
  - tick广播：`kernel/time/tick-broadcast.c`

### 19.3 hrtimer：高精度定时器

- **精读** `kernel/time/hrtimer.c`：
  - 红黑树组织定时器
  - `hrtimer_start()`/`hrtimer_cancel()`
  - 定时器回调的执行上下文
  - 高精度模式与低精度模式的切换
- *数据库视角*：查询超时的内核定时器支撑——statement_timeout的实现

### 19.4 POSIX定时器

- **精读** `kernel/time/posix-timers.c`：
  - timer_create/timer_settime/timer_delete
  - 信号通知 vs 线程通知
- **精读** `kernel/time/posix-cpu-timers.c`：
  - CPU时间追踪：CLOCK_PROCESS_CPUTIME_ID/CLOCK_THREAD_CPUTIME_ID
  - 资源限制(RLIMIT_CPU)的实现

### 19.5 轮转定时器

- **精读** `kernel/time/timer.c`：
  - TIMEWHEEL：多级时间轮
  - `add_timer()`/`mod_timer()`/`del_timer()`
  - 定时器迁移：`kernel/time/timer_migration.c`

### 19.6 vDSO与快速时间获取

- `arch/x86/entry/vdso/`：vDSO中的gettimeofday实现
- 不进入内核的时间获取路径
- *数据库视角*：高精度时间戳获取的开销——vDSO vs syscall

## 关键源文件清单

| 文件 | 行数 | 关注点 |
|------|------|--------|
| `kernel/time/hrtimer.c` | ~2500 | 高精度定时器 |
| `kernel/time/timer.c` | ~2000 | 时间轮 |
| `kernel/time/timekeeping.c` | ~2000 | 时间保持 |
| `kernel/time/tick-sched.c` | ~1500 | tick管理 |
| `kernel/time/posix-timers.c` | ~1500 | POSIX定时器 |

## 跨章依赖

- 依赖第18章（中断）：定时器中断驱动时间子系统
