---
chapter: 5
part: 第二篇 启动与进程 —— 从第一行代码到任务调度
title: 启动：从BIOS到idle进程
source_anchor:
  - arch/x86/kernel/head_64.S
  - arch/x86/kernel/setup.c
  - init/main.c
  - init/do_mounts.c
  - init/initramfs.c
  - init/init_task.c
status: done
---

# 第5章 启动：从BIOS到idle进程

## 写作目标

理解Linux从上电到第一个用户进程的完整启动链路，建立对内核初始化流程的全局视角。

## 章节大纲

### 5.1 实模式→保护模式→长模式

- BIOS/UEFI的预处理：POST、ACPI表、SMBIOS
- **精读** `arch/x86/kernel/head_64.S`：
  - 从实模式到保护模式的切换
  - 分页使能与长模式切换
  - 内核解压与重定位
- `arch/x86/kernel/setup.c`：早期x86平台初始化
  - e820内存映射发现
  - MPS/ACPI表解析

### 5.2 start_kernel()：逐阶段初始化

- **精读** `init/main.c`：`start_kernel()` 函数的完整流程
  - 早期参数解析与架构初始化
  - 内存子系统初始化：mm_init()
  - 调度器初始化：sched_init()
  - 中断与时间子系统初始化
  - 驱动模型与设备树初始化
  - rest_init()：创建kernel_init和kthreadd
- 0号idle进程的诞生：`init/init_task.c`——内核第一个task_struct

### 5.3 initramfs与根文件系统

- initramfs解压：`init/initramfs.c`
- 根文件系统挂载：`init/do_mounts.c`
  - root=参数解析
  - initrd与initramfs的区别
- kernel_init→/sbin/init：1号进程的诞生

## 关键源文件清单

| 文件 | 行数 | 关注点 |
|------|------|--------|
| `arch/x86/kernel/head_64.S` | ~300 | 早期启动汇编 |
| `arch/x86/kernel/setup.c` | ~1200 | x86平台初始化 |
| `init/main.c` | ~1000 | start_kernel主流程 |
| `init/init_task.c` | ~50 | 0号进程定义 |
| `init/initramfs.c` | ~800 | initramfs解压 |
| `init/do_mounts.c` | ~500 | 根文件系统挂载 |

## 跨章依赖

- 本章是第6章（进程）的前置：理解0号和1号进程的来源
