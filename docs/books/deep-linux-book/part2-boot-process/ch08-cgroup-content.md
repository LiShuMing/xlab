# 第8章 cgroup v2：资源隔离的内核实现

> 源码锚点：`kernel/cgroup/cgroup.c`、`mm/memcontrol.c`、`kernel/cgroup/cpuset.c`、`kernel/cgroup/dmem.c`、`kernel/cgroup/rstat.c`

cgroup是Linux容器的内核基础——它限制、记录和隔离进程组使用的资源。从v1的多层级混乱到v2的统一层级，cgroup的设计哲学发生了根本转变。本章深入cgroup v2的内核实现，理解容器资源隔离的内核支撑。

## 8.1 cgroup核心机制

### 统一层级与委派

cgroup v1有多个独立的层级(hierarchy)，每个控制器可以在不同层级上挂载——这导致进程在不同控制器中属于不同的cgroup组，管理极其混乱。v2的核心改进是**统一层级**——所有控制器在同一个层级上工作：

```
cgroup v2 统一层级：
/sys/fs/cgroup/
├── machine.slice/          # 虚拟机
│   ├── machine-vm1.scope/
│   └── machine-vm2.scope/
├── system.slice/           # 系统服务
│   ├── systemd-journald.service/
│   └── sshd.service/
└── user.slice/             # 用户会话
    └── user-1000.slice/
        └── session-1.scope/
```

**委派(delegation)**：v2允许将子cgroup的管理权委派给非特权用户。`cgroup.type`设为`threaded`或`domain`控制cgroup的类型，非特权用户可以在委派的cgroup下创建和管理子cgroup。

### css_set：进程与cgroup的关联

进程通过`css_set`结构与cgroup关联：

```c
// kernel/cgroup/cgroup.c
struct css_set {
    struct cgroup_subsys_state *subsys[CGROUP_SUBSYS_COUNT];  // 每个子系统的状态
    struct list_head tasks;        // 属于此css_set的进程链表
    struct list_head mg_tasks;     // 迁移中的进程
    struct cgroup *dfl_cgrp;       // 默认cgroup
    ...
};
```

每个进程的`task_struct->cgroups`指向一个`css_set`，`css_set`包含每个子系统的状态指针(`cgroup_subsys_state`)。多个进程可以共享同一个`css_set`（如果它们在所有cgroup中的位置相同），这避免了为每个进程复制完整的子系统状态。

### cgroup文件系统接口

cgroup v2通过cgroup2文件系统暴露接口：

```c
// kernel/cgroup/cgroup.c
// 每个cgroup控制器的接口文件
// memory.current / memory.max / memory.high / memory.low
// cpu.max / cpu.weight / cpu.stat
// cpuset.cpus / cpuset.mems
// io.max / io.weight
```

文件操作通过`kernfs`实现——cgroup的每个控制文件对应一个kernfs节点，读写操作通过`cgroup_file_write()`/`cgroup_file_show()`分派到具体的控制器。

### rstat：递归统计

`kernel/cgroup/rstat.c`实现了高效的递归统计——在层级cgroup中聚合子cgroup的数据：

```
root (total)
├── A (local_A + children)
│   ├── A1 (local_A1)
│   └── A2 (local_A2)
└── B (local_B)
```

rstat的核心优化：不在每次读取时递归遍历所有子cgroup，而是在数据变化时标记更新(cached)，读取时只聚合被标记的路径。`cgroup_rstat_updated()`标记更新，`cgroup_rstat_flush()`执行聚合。

## 8.2 CPU控制器

### cpu.max与cpu.weight

cgroup v2的CPU控制器提供两个接口：

- **cpu.weight**：权重(1-10000)，决定cgroup在CFS中的相对份额。两个cgroup权重分别为100和200，后者获得2倍CPU时间。
- **cpu.max**：带宽限制，格式为`max_quota period`（如`50000 100000`表示每100ms周期内最多运行50ms）。

### CFS组调度的实现

cpu.max底层使用CFS的带宽限制(CFS Bandwidth)：

```c
// cgroup的cpu.max → sched_cfs_period_timer()
// 每个period开始时，给cgroup的运行队列充值quota
// cgroup中的进程消耗quota，耗尽时被throttle
```

当cgroup的CPU配额耗尽时，该cgroup中的所有进程被throttle——从运行队列移除，直到下一个period充值。这在`cpu.stat`中体现为`throttled_time`。

### cpu.stat与PSI的关联

```
# cat /sys/fs/cgroup/.../cpu.stat
usage_usec 123456789
user_usec 98765432
system_usec 24691357
nr_periods 1000
nr_throttled 50
throttled_usec 5000000
```

`nr_throttled`和`throttled_usec`直接反映了CPU限流对进程的影响。PSI的`cpu.some`压力指标与throttle高度相关——频繁throttle的cgroup会有高CPU some压力。

> **AI视角**：推理服务的SLO保障——cgroup CPU限流与延迟抖动。推理服务的P99延迟受CPU throttle直接影响——如果cgroup被throttle 5ms，所有在此期间到达的请求都延迟5ms+。通过`cpu.stat`的`nr_throttled`可以监控throttle频率，通过`cpu.max`调整配额。一个技巧是设置`cpu.max`略高于实际需求，留出burst空间——但过高的burst可能导致其他cgroup饥饿。

## 8.3 内存控制器

### 精读 mm/memcontrol.c

内存控制器是cgroup中最复杂的子系统，控制进程组的内存使用：

```c
// mm/memcontrol.c
struct mem_cgroup {
    struct page_counter memory;     // 内存计数器
    struct page_counter memsw;      // 内存+swap计数器
    struct page_counter kmem;       // 内核内存计数器
    unsigned long memory.low;       // 低水位——尽力保护
    unsigned long memory.high;      // 高水位——触发回收
    unsigned long memory.max;       // 最大限制——硬上限
    ...
};
```

### 四级水位控制

内存控制器的四级水位决定了不同的行为：

```
memory.low → memory.current → memory.high → memory.max
   ↑              ↑               ↑              ↑
 尽力保护      正常运行     触发回收+限流    OOM Kill
```

**memory.low**：低水位线。当cgroup内存使用低于low时，内核在全局内存回收时尽量不回收该cgroup的页面。这是"尽力而为"的保障——如果系统整体内存紧张，low保护可能被打破。

**memory.high**：高水位线。超过high后，内核主动回收该cgroup的内存，并且对该cgroup中的进程施加限流——`try_charge()`中调用`try_to_free_mem_cgroup_pages()`进行回收：

```c
// mm/memcontrol.c
static ssize_t memory_high_write(struct kernfs_open_file *of, ...)
{
    page_counter_set_high(&memcg->memory, high);

    for (;;) {
        unsigned long nr_pages = page_counter_read(&memcg->memory);
        if (nr_pages <= high)
            break;
        // 主动回收，直到内存降到high以下
        reclaimed = try_to_free_mem_cgroup_pages(memcg, nr_pages - high,
                    GFP_KERNEL, MEMCG_RECLAIM_MAY_SWAP, NULL);
    }
}
```

**memory.max**：硬上限。超过max后，新的内存分配被拒绝：

```c
// mm/memcontrol.c
static ssize_t memory_max_write(struct kernfs_open_file *of, ...)
{
    xchg(&memcg->memory.max, max);

    for (;;) {
        if (nr_pages <= max)
            break;
        // 先尝试回收
        if (nr_reclaims) {
            try_to_free_mem_cgroup_pages(memcg, nr_pages - max, ...);
            nr_reclaims--;
            continue;
        }
        // 回收失败，触发OOM
        memcg_memory_event(memcg, MEMCG_OOM);
        if (!mem_cgroup_out_of_memory(memcg, GFP_KERNEL, 0))
            break;
    }
}
```

### charge/uncharge机制

每次页面分配都经过cgroup的charge，释放时uncharge：

```c
// mm/memcontrol.c
static int try_charge_memcg(struct mem_cgroup *memcg, gfp_t gfp_mask,
                            unsigned int nr_pages)
{
    // 1. 先尝试从本地stock消耗（per-CPU缓存，无锁快速路径）
    if (consume_stock(memcg, nr_pages))
        return 0;

    // 2. 尝试增加page_counter
    if (page_counter_try_charge(&memcg->memory, batch, &counter))
        goto done_restock;

    // 3. 超限——检查是否可以回收
    mem_over_limit = mem_cgroup_from_counter(counter, memory);

    // 4. PSI追踪内存压力
    psi_memstall_enter(&pflags);
    nr_reclaimed = try_to_free_mem_cgroup_pages(mem_over_limit, ...);
    psi_memstall_leave(&pflags);

    // 5. 回收后重试
    if (mem_cgroup_margin(mem_over_limit) >= nr_pages)
        goto retry;

    // 6. 排空per-CPU stock后重试
    drain_all_stock(mem_over_limit);

    // 7. 回收重试多次后，OOM
    mem_cgroup_out_of_memory(memcg, gfp_mask, order);
}
```

`try_charge_memcg()`是内存控制的关键路径——每次页面分配都经过它。为了降低开销，使用per-CPU stock缓存批量charge——一次charge 32页，后续分配先从stock消耗，避免频繁操作`page_counter`。

### swap与内存控制

cgroup v2通过`memory.swap.max`控制swap使用。当`memory.swap.max=0`时，cgroup完全不使用swap，所有内存压力直接由物理内存承受。这在数据库和推理服务中常见——swap会导致不可预测的延迟抖动。

> **数据库视角**：如何防止Buffer Pool被cgroup OOM杀掉。数据库的Buffer Pool通常是最大的内存消费者。如果cgroup的`memory.max`设置过小，OOM Killer会优先选择内存占用最大的进程——通常是数据库进程本身。防护策略：1) 设置`memory.low`等于Buffer Pool大小，获得内核的尽力保护；2) 使用`oom_score_adj`降低数据库进程的OOM评分；3) 监控`memory.events.oom_kill`及时发现OOM事件。

## 8.4 cpuset与NUMA绑定

### 精读 kernel/cgroup/cpuset.c

cpuset控制器限制cgroup可以在哪些CPU和NUMA节点上运行：

```
# 限制在CPU 0-3和NUMA节点0上
cpuset.cpus = 0-3
cpuset.mems = 0
```

cpuset的关键约束：**子cgroup的掩码必须是父cgroup的子集**。这通过"有效掩码"机制实现：

```c
// kernel/cgroup/cpuset.c
// parent: cpuset.cpus = 0-7
//   ├── child1: cpuset.cpus = 0-3  (有效)
//   └── child2: cpuset.cpus = 4-11 (有效部分: 4-7, 超出父的部分被裁剪)
```

`cpuset.cpus.effective`和`cpuset.mems.effective`是实际生效的掩码——由父cgroup的掩码和当前cgroup的请求掩码取交集得到。当父cgroup的掩码缩小时，子cgroup的有效掩码自动调整。

### NUMA绑定的容器实践

NUMA绑定对性能敏感的工作负载至关重要：

- **数据库**：将数据库cgroup绑定到特定NUMA节点，避免跨节点访存的延迟惩罚
- **AI推理**：将推理进程绑定到GPU所在的NUMA节点，减少PCIe跨节点传输
- **大页应用**：绑定NUMA节点确保大页从本地节点分配

Kubernetes的CPU Manager static策略利用cpuset实现独占CPU分配——每个Guaranteed QoS的Pod获得独占的CPU核心，其他Pod不能使用。

## 8.5 设备内存控制器

### 精读 kernel/cgroup/dmem.c

dmem控制器是Linux 7.0引入的新控制器，隔离**设备内存**(GPU/NPU显存)的使用：

```c
// kernel/cgroup/dmem.c
struct dmemcg_state {
    struct cgroup_subsys_state css;
    struct list_head pools;      // 该cgroup的设备内存池
};

struct dmem_cgroup_pool_state {
    struct dmem_cgroup_region *region;   // 设备内存区域
    struct page_counter cnt;             // 页面计数器
    struct dmem_cgroup_pool_state *parent;  // 父cgroup的池
};
```

dmem控制器的架构与memory控制器类似——使用`page_counter`追踪设备内存使用，支持charge/uncharge机制。但有一个关键区别：dmem需要为每个**设备内存区域**维护独立的计数器——一个系统可能有多个GPU，每个GPU的显存需要独立限制。

dmem控制器通过`dmem_cgroup_register_region()`注册设备内存区域：

```
GPU0: dmem.region = "gpu0-vram", size = 24GB
GPU1: dmem.region = "gpu1-vram", size = 80GB
NPU0: dmem.region = "npu0-sram", size = 48MB
```

每个cgroup对每个区域有独立的`dmem.max`限制：

```
# 限制cgroup在GPU0上最多使用8GB显存
dmem.max = gpu0-vram 8GB
```

dmem控制器与memory控制器的类比：

| 特征 | memory控制器 | dmem控制器 |
|------|-------------|-----------|
| 管理对象 | 系统RAM | 设备内存(GPU/NPU) |
| 计数器 | `page_counter` | `page_counter` |
| Charge时机 | 页面分配 | 显存分配 |
| 回收机制 | 页面回收/swap | 驱动回调(evict) |
| OOM处理 | kill进程 | 驱动处理 |

> **AI视角**：GPU显存隔离——多租户推理的关键能力。在多租户推理集群中，不同租户的推理任务共享GPU。没有显存隔离，一个租户的大模型可能耗尽GPU显存，导致其他租户OOM。dmem控制器为每个租户的cgroup设置显存上限，确保公平共享。结合memory控制器和dmem控制器，可以实现CPU内存和GPU显存的全面隔离——这是容器化AI推理的内核基础。

## 8.6 其他控制器

### pids：进程数限制

`kernel/cgroup/pids.c`限制cgroup中的进程数量。每个fork/clone调用`pids_fork()`进行charge，`pids_release()`进行uncharge。超过`pids.max`后fork失败，返回`-EAGAIN`。这是防御fork炸弹(fork bomb)的有效手段。

### freezer：进程冻结

`kernel/cgroup/freezer.c`冻结cgroup中的所有进程——将进程状态设为`TASK_FROZEN`，阻止其运行。这是容器checkpoint/restore和容器暂停的基础机制。

冻结通过信号实现：向目标进程发送一个伪信号(`fake signal`)，进程在下一个安全点检查`TIF_FREEZE`标志，然后将自己设为`TASK_FROZEN`。

### rdma：RDMA资源限制

`kernel/cgroup/rdma.c`限制RDMA资源的使用——包括Protection Domain、Memory Region、Completion Queue、Queue Pair等。RDMA资源有限且昂贵，需要精确控制。

---

本章建立了对cgroup v2内核实现的认知：统一层级简化了管理，CSS关联进程与cgroup，CPU/内存/设备内存控制器提供不同维度的资源隔离，rstat高效聚合层级数据。cgroup是容器的内核基础——没有cgroup，Docker/Kubernetes无法实现资源限制和隔离。第九篇将回到cgroup，讨论面向AI工作负载的资源管理演进。
