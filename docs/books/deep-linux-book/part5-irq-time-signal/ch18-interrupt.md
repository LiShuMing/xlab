---
chapter: 18
part: 第五篇 中断、时间与信号 —— 异步事件的内核处理
title: 中断子系统
source_anchor:
  - kernel/irq/irqdesc.c
  - kernel/irq/irqdomain.c
  - kernel/irq/handle.c
  - kernel/irq/chip.c
  - kernel/irq/manage.c
  - kernel/irq/affinity.c
  - kernel/irq/msi.c
  - kernel/irq/migration.c
  - kernel/irq/ipi.c
  - kernel/softirq.c
  - kernel/workqueue.c
status: done
---

# 第18章 中断子系统

## 写作目标

深入理解Linux中断子系统的分层架构，从硬件中断到软中断到workqueue的完整链路。

## 章节大纲

### 18.1 中断描述符与域

- **精读** `kernel/irq/irqdesc.c`：
  - `struct irq_desc`：中断描述符
  - 中断号的分配与管理
  - radix tree索引
- **精读** `kernel/irq/irqdomain.c`：
  - 中断域：硬件中断号→Linux IRQ号的映射
  - DT(Device Tree)/ACPI的中断映射
  - 层级域(Hierarchical Domain)

### 18.2 中断控制器与处理

- **精读** `kernel/irq/chip.c`：irq_chip抽象
  - mask/unmask/ack/eoi/mask_ack
  - 中断控制器的操作集
- **精读** `kernel/irq/handle.c`：
  - `handle_irq()`：高层中断处理入口
  - 边沿触发 vs 电平触发处理

### 18.3 中断管理

- **精读** `kernel/irq/manage.c`：
  - `request_irq()`/`free_irq()`：中断注册与注销
  - 中断线程化(threaded IRQ)
  - 共享中断(Shared IRQ)
  - 中断亲和性设置

### 18.4 中断亲和性与均衡

- **精读** `kernel/irq/affinity.c`：
  - IRQ亲和性：将中断绑定到特定CPU
  - 自动均衡：irqbalance策略
  - `kernel/irq/migration.c`：中断迁移
- *数据库视角*：NVMe中断与查询线程的CPU亲和性对齐

### 18.5 MSI/MSI-X

- **精读** `kernel/irq/msi.c`：
  - MSI/MSI-X的域管理
  - 多向量中断：NVMe多队列的硬件基础
  - MSI描述符管理

### 18.6 软中断、tasklet与workqueue

- `kernel/softirq.c`：软中断
  - 9种软中断类型
  - `raise_softirq()`与`do_softirq()`
  - softirqd守护进程
  - tasklet：基于软中断的延迟机制
- `kernel/workqueue.c`：工作队列
  - 从工作队列到io-wq：`io_uring/io-wq.c`
  - `kernel/workqueue_internal.h`
- 分层架构的意义：硬中断快进快出、延迟处理放软中断/workqueue

### 18.7 IPI与核间中断

- `kernel/irq/ipi.c`：IPI(Inter-Processor Interrupt)
  - RESCHEDULE/TLB_FLUSH/CALL_FUNCTION
  - `kernel/smp.c`：smp_call_function系列

### 18.8 *源码精读*：NVMe中断的完整路径

- 硬件中断 → NVMe MSI-X向量 → `nvme_irq()` → 完成队列处理
- 软中断 → block softirq → 请求完成回调
- 与第21章块层的衔接

## 关键源文件清单

| 文件 | 行数 | 关注点 |
|------|------|--------|
| `kernel/irq/irqdesc.c` | ~600 | 中断描述符 |
| `kernel/irq/irqdomain.c` | ~1500 | 中断域 |
| `kernel/irq/chip.c` | ~500 | irq_chip |
| `kernel/irq/manage.c` | ~2000 | 中断管理 |
| `kernel/irq/affinity.c` | ~300 | 中断亲和性 |
| `kernel/irq/msi.c` | ~800 | MSI/MSI-X |
| `kernel/softirq.c` | ~700 | 软中断 |
| `kernel/workqueue.c` | ~5000 | 工作队列 |

## 跨章依赖

- 依赖第1章（x86入口）：中断入口与syscall入口的统一性
- 前置第19章（时间）：定时器中断是时间子系统的驱动
