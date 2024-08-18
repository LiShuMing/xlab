# 第29章 查询执行的硬件适配

> 源码锚点：`mm/mempolicy.c`、`mm/numa.c`、`kernel/sched/topology.c`、`kernel/bpf/trampoline.c`

查询执行引擎的性能取决于对硬件的适配——Cache Line对齐影响内存访问效率，NUMA感知影响数据局部性，JIT编译消除解释开销，并行查询依赖调度器配合。本章用硬件和内核原理指导查询执行引擎的优化。

## 29.1 向量化执行与Cache Line对齐

### 向量化执行的本质

向量化执行一次处理一组数据(向量)而非一行——充分利用CPU流水线和SIMD指令：

```
行式执行：for each row { eval(row) }     → 逐行分支判断，流水线气泡多
向量化：  for each col_batch { eval_batch() } → 批量处理，流水线满载
```

### Cache Line对齐

CPU以Cache Line(64字节)为单位加载内存——数据跨越Cache Line边界导致两次加载。向量化执行的列数据应Cache Line对齐：

```c
// include/linux/cache.h
#define __cacheline_aligned   __attribute__((__aligned__(SMP_CACHE_BYTES)))
```

列式存储中，每列数据按Cache Line对齐——向量化读取时一次加载连续的8个int64(64字节/8字节=8)，无需跨Cache Line访问。

### prefetch策略

预取指令`__builtin_prefetch`告诉CPU提前加载数据到缓存：

```c
// Hash Join探测阶段的预取
for (int i = 0; i < batch_size; i++) {
    __builtin_prefetch(&hash_table[hash(batch[i+8])], 0, 1);  // 预取8个元素后的hash桶
    result[i] = probe(hash_table, batch[i]);  // 当前元素探测
}
```

预取距离的调优：预取太近来不及加载，预取太远数据可能被驱逐。通常选择8-16个元素的提前量——取决于内存延迟和执行速度的比值。

## 29.2 Hash Join/Sort的内存访问模式

### Hash Join的访问模式

Hash Join分两阶段：
- **构建阶段**：顺序写入Hash表——Cache友好
- **探测阶段**：随机读取Hash表——Cache不友好

Hash表的Cache友好设计：
- **开地址法**比链地址法更Cache友好——数据在连续内存中，不需要指针追踪
- **Robin Hood Hashing**：减少探测长度方差——降低尾延迟
- **分桶预取**：探测前预取目标桶——隐藏内存延迟

### Sort的内存访问模式

- **快排**：分区操作随机访问——Cache不友好
- **归并排序**：顺序访问多个有序序列——Cache友好
- **实用策略**：小数据用快排(数据在Cache内)，大数据用归并(顺序访问)

数据库的实用排序通常混合两者——内存内快排，外部归并。内核的`mm/page_alloc.c`有类似模式——per-CPU pageset用顺序分配(Cache友好)，伙伴系统处理大请求。

## 29.3 JIT编译执行与分支预测

### JIT消除解释开销

查询解释执行每次执行算子都需要函数指针调用和类型判断——JIT编译将查询计划编译为原生代码，消除这些开销：

```
解释执行：while (plan) { plan->next(plan); }  → 函数指针+switch
JIT执行：  直接执行编译后的机器码                → 无间接调用
```

PostgreSQL使用LLVM JIT——编译表达式和元组解构代码。Spark使用Whole-Stage Code Generation——将整个算子链编译为一个函数。

### 分支预测优化

条件分支在预测错误时清空流水线——代价约15-20个周期。JIT可以：
- **消除分支**：将条件判断转换为条件移动(cmov)
- **分支提示**：利用`__builtin_expect`标注大概率路径
- **循环展开**：减少循环条件判断的次数

### 从BPF JIT学查询JIT

`kernel/bpf/trampoline.c`展示了内核中的JIT实践——BPF程序的动态编译和附着：
- BPF JIT将字节码翻译为本机指令——类似查询JIT将IR翻译为机器码
- BPF验证器确保安全——类似查询JIT需要确保不越界访问
- BPF trampoline实现动态挂载——类似查询JIT的运行时代码生成

## 29.4 NUMA感知的数据分区与调度

### NUMA内存策略

`mm/mempolicy.c`实现NUMA内存策略：

```c
// MPOL_BIND：严格绑定到指定NUMA节点
// MPOL_PREFERRED：优先在指定节点分配，失败时回退
// MPOL_INTERLEAVE：交错分配到所有节点——平衡带宽
set_mempolicy(MPOL_BIND, &nodemask, maxnode);
```

数据库的NUMA感知策略：
- **Partition按NUMA节点分布**：每个NUMA节点的数据分区存储在本节点内存
- **Worker线程CPU亲和性**：处理N分区数据的Worker绑定到NUMA节点N
- **内存分配节点亲和性**：`numa_alloc_onnode()`在本节点分配

### NUMA页面迁移

`mm/numa.c`实现自动NUMA平衡——内核检测进程的NUMA访问模式，将页面迁移到访问最频繁的节点：

```
task_numa_work() → 采样页面访问 → 统计各节点的访问频率
→ 如果页面在远端节点 → 标记为待迁移
→ 下次缺页时迁移到本节点
```

数据库通常禁用自动NUMA平衡——迁移引入不可控延迟。改为手动分区+绑定。

### 调度域与NUMA拓扑

`kernel/sched/topology.c`构建调度域层次——从SMT到MC到NUMA：

```
调度域层次：
  SMT域：同一核心的超线程
  MC域：同一socket的核心
  NUMA域：同一NUMA节点的socket
  DIE域：同一封装的NUMA节点
```

CFS在负载均衡时尊重调度域层次——优先在同一域内迁移任务，减少跨NUMA迁移。数据库的Worker绑定应匹配调度域——同一查询的Worker在同一NUMA域内。

## 29.5 并行查询与内核调度

### Worker线程管理

并行查询的Worker线程面临调度问题——如果Worker被调度到错误的CPU或被其他任务抢占，查询延迟增加。

### cgroup资源隔离

cgroup v2的CPU控制器限制查询组的CPU使用——防止大查询饿死小查询：

```
大查询组 → cpu.max=80000 100000 (80% CPU)
小查询组 → cpu.max=20000 100000 (20% CPU)
```

CFS的组调度(`kernel/sched/fair.c`)确保cgroup间的公平分配——同一cgroup内的任务共享该组的CPU配额。

### Worker与CFS的交互

并行查询的Worker应设置适当的调度策略：
- **SCHED_BATCH**：批处理任务——允许更长的时间片，减少上下文切换
- **CPU亲和性**：Worker绑定到NUMA节点对应的CPU——减少远程内存访问
- **cgroup放置**：同一查询的Worker放在同一cgroup——统一限流

> **数据库视角**：并行查询的调度感知。现代数据库(如ClickHouse)使用自管理的线程池处理查询——而非为每个查询创建新线程。线程池中的Worker绑定到固定CPU，减少迁移和缓存失效。这与内核的io-wq(io_uring工作队列)的设计思路一致——per-CPU Worker处理本CPU上的请求。

---

本章建立了对查询执行硬件适配的完整认知：Cache Line对齐和向量化执行充分利用CPU流水线，Hash Join/Sort的内存访问模式需要Cache友好设计，JIT编译消除解释执行开销，NUMA感知分区减少远程内存访问，cgroup和调度策略配合并行查询。性能优化的核心是"适配硬件"——理解CPU/内存/总线的特性，让软件与硬件协同工作。
