# 第25章 eBPF：内核可编程观测与安全

> 源码锚点：`kernel/bpf/verifier.c`、`kernel/bpf/core.c`、`kernel/bpf/syscall.c`、`kernel/bpf/btf.c`、`kernel/bpf/trampoline.c`、`kernel/bpf/ringbuf.c`、`kernel/bpf/bpf_lsm.c`

eBPF(extended Berkeley Packet Filter)将可编程性引入内核——用户编写安全的沙箱程序，内核验证后JIT编译为本机代码执行。eBPF从网络过滤起步，已扩展到跟踪、安全、调度等几乎所有内核子系统，成为内核可扩展性的标准接口。

## 25.1 eBPF的架构概览

### BPF程序的生命周期

```
编写(C) → 编译(clang -target bpf) → 加载(bpf系统调用)
  → 验证器检查 → JIT编译为本机代码 → 附着到钩子点 → 执行
```

关键阶段：
- **验证**：确保程序安全——不会越界访问、不会无限循环、不会崩溃内核
- **JIT**：将BPF字节码编译为x86/ARM本机指令——接近原生性能
- **附着**：将程序挂载到特定钩子点(kprobe/tracepoint/XDP/cgroup/...)

### BPF程序类型

| 类型 | 附着点 | 用途 |
|------|--------|------|
| BPF_PROG_TYPE_XDP | 网卡RX | 高速包处理 |
| BPF_PROG_TYPE_SCHED_CLS | tc | 流量控制 |
| BPF_PROG_TYPE_KPROBE | 内核函数 | 跟踪 |
| BPF_PROG_TYPE_TRACEPOINT | tracepoint | 事件跟踪 |
| BPF_PROG_TYPE_CGROUP_SKB | cgroup | 网络策略 |
| BPF_PROG_TYPE_LSM | 安全钩子 | 安全策略 |
| BPF_PROG_TYPE_PERF_EVENT | PMU | 性能监控 |
| BPF_PROG_TYPE_SCHED | 调度器 | 可编程调度 |

## 25.2 验证器：安全的保证

`kernel/bpf/verifier.c`(20191行)是eBPF安全的基石——任何BPF程序必须通过验证器的检查才能执行。

### 两阶段验证

**第一阶段：CFG(控制流图)检查**
- 构建程序的控制流图——基本块和边
- 检测不可达代码
- 确保没有循环(或有界循环)——防止无限循环
- 检测栈深度——不超过512字节

**第二阶段：状态探索**
- 模拟执行每条指令，追踪寄存器和栈的状态
- 寄存器状态追踪：类型(指针/标量)、范围(可能值)、指针来源(哪个map/ctx)
- 路径剪枝：已验证状态的缓存——如果两条路径在汇合点的状态相同，剪去重复探索

### 寄存器状态追踪的核心

验证器为每个寄存器维护精确的状态信息：

```c
struct bpf_reg_state {
    enum bpf_reg_type type;     // PTR_TO_MAP_VALUE, PTR_TO_CTX, SCALAR_VALUE, ...
    struct bpf_map *map_ptr;    // 指向哪个map
    u32 off;                    // 偏移量
    u64 range;                  // 可能的值范围
    // ...
};
```

当程序执行`r1 = r2 + 3`时，验证器更新r1的类型和范围。当程序执行`*r1`时，验证器检查r1是否是有效指针、偏移是否在map范围内——越界访问直接拒绝。

### 辅助函数白名单

BPF程序不能调用任意内核函数——只能调用验证器白名单中的辅助函数(`bpf_helper`)。每个程序类型有不同的白名单——XDP程序可以调用网络相关helper，kprobe程序可以调用跟踪相关helper。验证器还检查helper的参数类型和范围。

### 有界循环

早期eBPF完全禁止循环——验证器无法保证终止。后来引入有界循环——循环的迭代次数必须有可验证的上界。验证器通过展开循环或追踪迭代变量来确认上界。

## 25.3 BPF核心与JIT

### BPF指令解释器

`kernel/bpf/core.c`实现BPF字节码的解释器——64位寄存器、固定指令集。当JIT不可用或调试时使用解释器。

### JIT编译

各架构实现BPF JIT——将BPF字节码编译为本机指令。x86的JIT将BPF寄存器映射到x86寄存器，将BPF指令翻译为x86指令序列。JIT后的代码性能接近原生C代码——比解释器快5-10倍。

### Trampoline

`kernel/bpf/trampoline.c`实现BPF程序的动态附着——通过ftrace机制在内核函数入口/出口插入跳板代码，跳转到BPF程序：

```
内核函数foo()入口 → trampoline → BPF程序 → 返回trampoline → 继续foo()
```

trampoline支持动态添加/移除BPF程序——无需修改内核代码，无需重启。

> **JIT技术对数据库JIT引擎的启示**：数据库(如PostgreSQL)的JIT表达式编译使用LLVM将查询表达式编译为本机代码——与eBPF JIT的思路相同：将解释执行改为编译执行。eBPF验证器的"安全编译"思路也适用于数据库——验证查询不会越界访问、不会无限循环。

## 25.4 BTF(BPF Type Format)

### 类型信息的编码

BTF是BPF的类型信息格式——编码内核数据结构的布局(字段名、偏移量、大小)。`kernel/bpf/btf.c`实现BTF的解析和管理。

### CO-RE(Compile Once - Run Everywhere)

BTF使CO-RE成为可能——BPF程序编译一次，在不同内核版本上运行：

```
编译时：记录访问的字段名和类型(通过BTF)
运行时：根据当前内核的BTF重定位字段偏移
→ 内核版本不同导致结构体布局变化 → 自动调整偏移量
```

CO-RE解决了BPF程序的可移植性问题——不再需要为每个内核版本编译不同版本。

## 25.5 Map系统

BPF Map是BPF程序与用户态(或其他BPF程序)共享数据的机制：

| Map类型 | 特点 | 用途 |
|---------|------|------|
| ARRAY | 固定大小数组 | 快速索引查找 |
| HASH | 哈希表 | 通用键值存储 |
| RINGBUF | 环形缓冲区 | 高效数据传输到用户态 |
| LPM_TRIE | 最长前缀匹配 | 路由表 |
| BLOOM_FILTER | 布隆过滤器 | 快速排除 |
| STACK_TRACE | 栈追踪 | 调用栈采集 |
| PERCPU_ARRAY | per-CPU数组 | 无锁快速路径 |
| LOCAL_STORAGE | BPF本地存储 | per-inode/per-task数据 |

`kernel/bpf/ringbuf.c`的环形缓冲区Map是用户态数据传输的高效方式——BPF程序写入数据，用户态mmap后直接读取，无需系统调用。替代了perf_event的性能开销。

## 25.6 BPF迭代器

BPF迭代器允许BPF程序遍历内核数据结构——将内核内部状态导出到用户态：

- **task_iter**：遍历所有进程/线程
- **map_iter**：遍历Map的所有条目
- **kmem_cache_iter**：遍历slab缓存信息
- **cgroup_iter**：遍历cgroup层次

迭代器通过seq_file接口导出到用户态——`cat /proc/fs/bpf/<iter>`触发BPF程序执行并输出结果。

## 25.7 BPF LSM：用BPF实现安全策略

`kernel/bpf/bpf_lsm.c`将BPF程序注册为LSM钩子——用BPF实现动态安全策略：

```
安全事件(如inode_permission) → LSM钩子 → BPF LSM程序
  → 检查策略(从BPF Map读取规则) → 允许/拒绝
```

BPF LSM vs SELinux：
- **SELinux**：静态策略，编译时确定，需要root配置——适合固定安全需求
- **BPF LSM**：动态策略，运行时可修改，可用BPF Map存储规则——适合快速迭代的安全需求

两者可以堆叠——SELinux提供基线安全策略，BPF LSM提供动态补充策略。

## 25.8 BPF系统调用接口

```c
// kernel/bpf/syscall.c
// bpf()系统调用的cmd分发：
// BPF_MAP_CREATE     → 创建Map
// BPF_PROG_LOAD      → 加载BPF程序(含验证和JIT)
// BPF_OBJ_GET/PUT    → 获取/释放pinned对象
// BPF_PROG_ATTACH    → 附着程序到cgroup/iter等
// BPF_LINK_CREATE    → 创建link(程序+附着点的绑定)
```

BPF token(`kernel/bpf/token.c`)允许非特权用户在受控范围内使用BPF——解决了"谁可以使用eBPF"的权限问题。

---

本章建立了对eBPF的完整认知：验证器通过两阶段检查确保程序安全，JIT将BPF字节码编译为接近原生的本机代码，BTF和CO-RE解决可移植性问题，Map系统提供丰富的数据共享机制，BPF LSM实现动态安全策略。eBPF是内核可扩展性的未来——从观测到安全到网络，越来越多的内核功能通过eBPF实现。
