---
chapter: A
part: 附录
title: 源码阅读路线图
status: done
---

# 附录A 源码阅读路线图

## 按本书章节顺序的源码目录导航

### 第一篇 硬件与架构

| 章 | 推荐阅读路径 |
|----|-------------|
| 1 | `arch/x86/entry/entry_64.S` → `arch/x86/entry/entry_64_fred.S` → `arch/x86/entry/syscall_64.c` → `kernel/entry/common.c` → `arch/x86/mm/pti.c` |
| 2 | `arch/x86/mm/init_64.c` → `arch/x86/mm/numa.c` → `arch/x86/mm/tlb.c` → `include/linux/cache.h` |
| 3 | `drivers/nvme/host/pci.c` → `drivers/nvme/host/core.c` → `drivers/dma/dmaengine.c` → `drivers/infiniband/core/` |
| 4 | `drivers/cxl/core/` → `drivers/cxl/mem.c` → `drivers/gpu/drm/drm_atomic.c` → `drivers/accel/drm_accel.c` → `drivers/accel/amdxdna/` |

### 第二篇 启动与进程

| 章 | 推荐阅读路径 |
|----|-------------|
| 5 | `arch/x86/kernel/head_64.S` → `init/main.c` → `init/init_task.c` → `init/initramfs.c` |
| 6 | `include/linux/sched.h` → `kernel/fork.c` → `arch/x86/kernel/process_64.c` → `kernel/exit.c` |
| 7 | `kernel/sched/core.c` → `kernel/sched/sched.h` → `kernel/sched/fair.c` → `kernel/sched/pelt.c` → `kernel/sched/psi.c` |
| 8 | `kernel/cgroup/cgroup.c` → `mm/memcontrol.c` → `kernel/cgroup/cpuset.c` → `kernel/cgroup/dmem.c` |

### 第三篇 内存管理

| 章 | 推荐阅读路径 |
|----|-------------|
| 9 | `mm/memblock.c` → `mm/mm_init.c` → `mm/page_alloc.c` → `mm/slub.c` → `mm/cma.c` |
| 10 | `mm/vma.c` → `mm/mmap.c` → `mm/memory.c` → `mm/rmap.c` → `mm/gup.c` → `mm/mseal.c` |
| 11 | `mm/swap.c` → `mm/workingset.c` → `mm/vmscan.c` → `mm/zswap.c` → `mm/damon/core.c` |
| 12 | `mm/hugetlb.c` → `mm/huge_memory.c` → `mm/khugepaged.c` → `mm/ksm.c` |
| 13 | `mm/kasan/generic.c` → `mm/kfence/core.c` → `arch/x86/mm/mem_encrypt_amd.c` |

### 第四篇 同步与并发

| 章 | 推荐阅读路径 |
|----|-------------|
| 14 | `kernel/locking/mcs_spinlock.h` → `kernel/locking/qspinlock.c` → `kernel/locking/mutex.c` → `kernel/locking/rtmutex.c` → `kernel/locking/rwsem.c` |
| 15 | `kernel/rcu/tree.c` → `kernel/rcu/tree_nocb.h` → `kernel/rcu/srcutree.c` → `kernel/rcu/tree_stall.h` |
| 16 | `kernel/futex/core.c` → `kernel/futex/waitwake.c` → `kernel/futex/pi.c` → `kernel/futex/requeue.c` |
| 17 | `kernel/locking/lockdep.c` → `arch/x86/include/asm/barrier.h` → `include/linux/compiler.h` |

### 第五篇 中断、时间与信号

| 章 | 推荐阅读路径 |
|----|-------------|
| 18 | `kernel/irq/irqdesc.c` → `kernel/irq/irqdomain.c` → `kernel/irq/chip.c` → `kernel/irq/manage.c` → `kernel/irq/msi.c` → `kernel/softirq.c` → `kernel/workqueue.c` |
| 19 | `kernel/time/clocksource.c` → `kernel/time/hrtimer.c` → `kernel/time/tick-sched.c` → `kernel/time/posix-timers.c` |
| 20 | `kernel/signal.c` → `fs/coredump.c` |

### 第六篇 I/O与存储栈

| 章 | 推荐阅读路径 |
|----|-------------|
| 21 | `block/bio.c` → `block/blk-core.c` → `block/blk-mq.c` → `block/mq-deadline.c` → `block/blk-iocost.c` |
| 22 | `fs/super.c` → `fs/inode.c` → `fs/dcache.c` → `mm/filemap.c` → `fs/ext4/` → `fs/iomap/` → `fs/direct-io.c` → `fs/sync.c` |
| 23 | `io_uring/io_uring.c` → `io_uring/rsrc.c` → `io_uring/sqpoll.c` → `io_uring/rw.c` → `io_uring/net.c` → `io_uring/zcrx.c` → `io_uring/uring_cmd.c` |
| 24 | `net/core/skbuff.c` → `net/core/dev.c` → `net/ipv4/tcp_input.c` |

### 第七篇 可观测性、安全与调试

| 章 | 推荐阅读路径 |
|----|-------------|
| 25 | `kernel/bpf/verifier.c` → `kernel/bpf/core.c` → `kernel/bpf/syscall.c` → `kernel/bpf/ringbuf.c` → `kernel/bpf/bpf_lsm.c` |
| 26 | `kernel/trace/` → `kernel/kprobes.c` → `tools/perf/` |
| 27 | `security/security.c` → `security/selinux/` → `arch/x86/coco/sev/` → `arch/x86/coco/tdx/` |

### 第八篇 数据库与OS的深度对话

| 章 | 推荐阅读路径 |
|----|-------------|
| 28 | `mm/fadvise.c` → `mm/madvise.c` → `fs/sync.c` → `block/blk-flush.c` → `fs/dax.c` |
| 29 | `mm/mempolicy.c` → `mm/numa.c` → `kernel/bpf/trampoline.c` |
| 30 | `kernel/locking/mcs_spinlock.h` → `kernel/rcu/` → `kernel/futex/` |

### 第九篇 AI时代的OS与硬件适配

| 章 | 推荐阅读路径 |
|----|-------------|
| 31 | `mm/vmscan.c` → `mm/ksm.c` → `kernel/sched/fair.c` → `mm/page_table_check.c` |
| 32 | `drivers/accel/drm_accel.c` → `drivers/accel/amdxdna/` → `mm/hmm.c` → `mm/migrate_device.c` → `kernel/cgroup/dmem.c` |
| 33 | `drivers/cxl/` → `mm/memory-tiers.c` → `mm/damon/paddr.c` → `mm/migrate.c` |
| 34 | `kernel/liveupdate/` → `mm/ksan/kexec_handover.c` → `rust/kernel/` → `arch/x86/coco/` |
| 35 | `io_uring/uring_cmd.c` → `drivers/nvme/host/uring_cmd.c` → `kernel/sched/ext.c` |

## 源码基线

本书内容基于以下Linux内核源码版本：

```
远程仓库：https://github.com/torvalds/linux.git
分支：    master
Commit：  1d51b370a0f8f642f4fc84c795fbedac0fcdbbd2
提交信息：Merge tag 'jfs-7.1' of github.com:kleikamp/linux-shaggy
作者：    Linus Torvalds
日期：    2026-04-15
```

### 检测源码变更

当内核源码更新后，以下命令可以列出本书涉及的所有子目录自基线以来的变更：

```bash
git fetch origin
git log 1d51b370a0f8..origin/master --oneline --stat -- \
  arch/x86/entry/ arch/x86/mm/ arch/x86/kernel/ arch/x86/coco/ \
  init/ \
  kernel/entry/ kernel/sched/ kernel/irq/ kernel/time/ kernel/signal/ \
  kernel/locking/ kernel/rcu/ kernel/futex/ kernel/cgroup/ \
  kernel/bpf/ kernel/liveupdate/ kernel/workqueue.c kernel/softirq.c \
  mm/ \
  block/ fs/ io_uring/ net/ \
  drivers/nvme/ drivers/cxl/ drivers/accel/ drivers/gpu/ drivers/dma/ drivers/infiniband/ \
  security/ rust/kernel/
```

### 变更影响评估

| 变更类型 | 影响 | 处理建议 |
|---------|------|---------|
| 函数签名变更 | 书中引用的API不再准确 | 更新代码片段，检查调用链 |
| 文件重命名/移动 | 书中的文件路径失效 | 更新路径引用，检查内容是否重构 |
| 新增子系统/特性 | 书中未覆盖新功能 | 评估是否需要补充章节或节 |
| 删除功能 | 书中描述的功能不再存在 | 标注废弃，补充替代方案 |
| 性能/行为变更 | 书中的性能分析或行为描述过时 | 重新测试验证，更新数据 |

### 按篇关注重点

| 篇 | 核心关注目录 | 典型高变更文件 |
|----|------------|--------------|
| 第一篇 硬件与架构 | `arch/x86/`, `drivers/nvme/`, `drivers/cxl/`, `drivers/accel/` | `entry_64.S`, `pci.c`, `drm_accel.c` |
| 第二篇 启动与进程 | `init/`, `kernel/sched/`, `kernel/cgroup/` | `core.c`, `fair.c`, `cgroup.c` |
| 第三篇 内存管理 | `mm/` | `page_alloc.c`, `vmscan.c`, `slub.c`, `memory.c` |
| 第四篇 同步与并发 | `kernel/locking/`, `kernel/rcu/`, `kernel/futex/` | `qspinlock.c`, `tree.c`, `core.c` |
| 第五篇 中断时间信号 | `kernel/irq/`, `kernel/time/`, `kernel/signal.c` | `irqdesc.c`, `hrtimer.c` |
| 第六篇 I/O与存储栈 | `block/`, `fs/`, `io_uring/`, `net/` | `blk-mq.c`, `io_uring.c`, `tcp_input.c` |
| 第七篇 可观测性安全 | `kernel/bpf/`, `kernel/trace/`, `security/` | `verifier.c`, `security.c` |
| 第八篇 数据库与OS | `mm/`, `block/`, `fs/` | `filemap.c`, `blk-flush.c`, `dax.c` |
| 第九篇 AI时代 | `drivers/accel/`, `drivers/cxl/`, `mm/`, `kernel/liveupdate/` | `hmm.c`, `memory-tiers.c`, `dmem.c` |

## 源码阅读工具推荐

- cscope：C符号跳转
- ctags：标签索引
- Elixir Cross Referencer：在线源码浏览(lxr.linux.no)
- VS Code + C/C++扩展
- vim + cscope + ctags
