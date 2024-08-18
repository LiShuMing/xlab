# 第 2 章 操作系统适配层：JVM 与 OS 的契约

> 源码路径：`src/hotspot/os/`、`src/hotspot/share/runtime/os.cpp`、`src/hotspot/os/linux/os_linux.cpp`、`src/hotspot/os/posix/`

JVM 的"一次编写，到处运行"不仅依赖于字节码的跨平台性，更深层的支撑在于 HotSpot 源码中精心设计的操作系统抽象层。本章深入这个适配层，理解 JVM 如何与 Linux、Windows、POSIX 交互，以及这种设计如何影响性能。

---

## 2.1 `hotspot/os/` 目录全景：Linux / Windows / BSD / AIX / POSIX

### 2.1.1 目录结构

```
hotspot/os/
├── aix/          # IBM AIX 适配（PowerPC 服务器）
├── bsd/          # FreeBSD / OpenBSD / macOS 适配
├── linux/        # Linux 适配（生产环境最主流）
├── posix/        # POSIX 共享层（Linux/BSD/AIX 的公共抽象）
└── windows/      # Windows 适配
```

JVM 的 OS 适配分为三层：

**第一层：`os.cpp / os.hpp`（共享接口层）**

定义在 `src/hotspot/share/runtime/os.hpp` 中，是所有平台统一的接口。关键方法包括：

```cpp
class os : AllStatic {
  // 内存管理
  static char*  allocate_memory(size_t bytes, MemTag mem_tag);
  static bool   commit_memory(char* addr, size_t bytes, bool executable);
  static bool   uncommit_memory(char* addr, size_t bytes);
  static bool   protect_memory(char* addr, size_t bytes, prot_t prot);
  static bool   map_memory_to_aligned(size_t bytes, char* requested_addr);

  // 线程管理
  static bool   create_thread(Thread* thread, ThreadType thr_type, size_t stack_size = 0);
  static void   start_thread(Thread* thread);
  static void   free_thread(OSThread* osthread);

  // 系统信息
  static int    processor_count();
  static size_t page_size();
  static size_t physical_memory();

  // NUMA
  static size_t numa_get_groups_num();
  static int    numa_get_group_id();
  static void   numa_make_local(char* addr, size_t bytes, int lgrp_hint);
  static void   numa_make_global(char* addr, size_t bytes);
};
```

**第二层：`os/posix/`（POSIX 共享层）**

Linux、BSD、AIX 都是 POSIX 兼容系统，大量逻辑可以共享。`os_posix.cpp` 实现了：
- 信号处理框架（`signals_posix.cpp`）
- 线程创建与同步原语（`pthread` 封装）
- 内存映射（`mmap` 封装）
- 文件系统操作
- Park/Unpark 机制（`park_posix.hpp`）

**第三层：`os/linux/`（平台特定层）**

只有 Linux 特有的逻辑才放在这一层：
- cgroup v1/v2 感知（容器环境）
- NUMA 亲和性管理
- 大页支持
- /proc 文件系统解析

### 2.1.2 编译时选择

HotSpot 在编译时通过预处理器宏选择平台实现：

```cpp
// os.hpp 中的条件包含
# include OS_HEADER(os)

// 展开后（Linux 平台）：
# include "os_linux.hpp"
```

链接时，只有 `os_linux.o` 被链接，其他平台的 `.o` 文件不参与编译。

---

## 2.2 `os.cpp`：操作系统抽象接口设计

### 2.2.1 `os::init()`：第一次与 OS 对话

`os::init()` 在 `Arguments::parse()` 之前调用，是最早的 OS 交互：

```cpp
// os_linux.cpp:4445
void os::init(void) {
    char dummy;   // 用于获取栈地址的猜测
    int sys_pg_size = checked_cast<int>(sysconf(_SC_PAGESIZE));
    // ...
    OSInfo::set_vm_page_size(page_size);
    OSInfo::set_vm_allocation_granularity(page_size);
    _page_sizes.add(os::vm_page_size());

    Linux::initialize_system_info();  // 处理器数、物理内存
    Linux::_main_thread = pthread_self();

    // 检测 MADV_POPULATE_WRITE 可用性（Linux 5.14+）
    FLAG_SET_DEFAULT(UseMadvPopulateWrite,
        (::madvise(nullptr, 0, MADV_POPULATE_WRITE) == 0));

    os::Posix::init();
}
```

关键操作：
1. **页大小探测**：通过 `sysconf(_SC_PAGESIZE)` 获取，通常是 4KB
2. **系统信息收集**：处理器数、物理内存大小
3. **特性检测**：如 `MADV_POPULATE_WRITE`（预填充内存，避免页面错误）
4. **主线程记录**：`pthread_self()` 保存原始线程 ID

### 2.2.2 `os::init_2()`：参数感知后的二次初始化

`os::init_2()` 在参数解析之后调用，可以进行依赖参数的 OS 配置：

```cpp
// os_linux.cpp:4584
jint os::init_2(void) {
    os::Posix::init_2();

    if (PosixSignals::init() == JNI_ERR) {  // 信号处理初始化
        return JNI_ERR;
    }

    if (set_minimum_stack_sizes() == JNI_ERR) {
        return JNI_ERR;
    }

    Linux::libpthread_init();
    Linux::sched_getcpu_init();

    if (UseNUMA || UseNUMAInterleaving) {
        Linux::numa_init();       // NUMA 初始化
    }

    if (MaxFDLimit) {
        // 将文件描述符限制调到最大
        struct rlimit nbr_files;
        getrlimit(RLIMIT_NOFILE, &nbr_files);
        nbr_files.rlim_cur = nbr_files.rlim_max;
        setrlimit(RLIMIT_NOFILE, &nbr_files);
    }

    // 注册 atexit 钩子
    atexit(perfMemory_exit_helper);
}
```

`os::init()` vs `os::init_2()` 的分界线在于：`init()` 不知道用户参数，`init_2()` 知道。例如 NUMA 初始化需要检查 `UseNUMA` 标志。

---

## 2.3 内存映射与 `reservedSpace.cpp`：虚拟地址空间预留

### 2.3.1 JVM 的虚拟地址空间布局

JVM 在启动时需要预留大块连续的虚拟地址空间，用于 Java 堆。这个过程由 `reservedSpace.cpp` 封装：

```cpp
// reservedSpace.hpp
class ReservedSpace {
  char*  _base;       // 起始地址
  size_t _size;       // 总大小
  size_t _alignment;  // 对齐粒度
  bool   _special;    // 是否使用特殊映射
};
```

**预留过程的核心调用链**：

```
universe_init()
  → CollectedHeap::create()
    → ReservedSpace::reserve_heap()
      → os::attempt_reserve_memory_at_aligned()
        → mmap(addr, size, PROT_NONE, MAP_PRIVATE|MAP_NORESERVE|MAP_ANONYMOUS)
```

关键参数：
- `PROT_NONE`：不分配任何访问权限（延迟提交）
- `MAP_NORESERVE`：不为映射预留交换空间
- `MAP_ANONYMOUS`：不关联文件

这种「预留但不提交」的策略是 JVM 内存管理的核心：先占用虚拟地址空间，物理内存按需提交（commit），避免一次性分配全部物理内存。

### 2.3.2 大页（Huge Pages）支持

JVM 支持两种大页机制：

**1. 透明大页（THP - Transparent Huge Pages）**

```cpp
// Linux 内核自动合并 4KB 页为 2MB 页
// JVM 通过 madvise(MADV_HUGEPAGE) 提示内核
```

**2. 显式大页（Explicit Huge Pages）**

```cpp
// 需要预分配（如 /proc/sys/vm/nr_hugepages）
// JVM 通过 mmap(MAP_HUGETLB) 直接分配
```

大页适配代码在 `os/linux/hugepages.cpp` 中，它会探测系统的大页配置（2MB 或 1GB），并选择最优策略。

---

## 2.4 线程模型：`osThread` 与 OS 线程的映射

### 2.4.1 三层线程抽象

```
JavaThread (HotSpot 层)
    ↕ 一对一映射
OSThread (OS 抽象层)
    ↕ 一对一映射
pthread (Linux 层) / Windows Thread
```

**JavaThread**：JVM 内部的线程表示，包含 Java 栈帧、锁记录、OopHandle 等 Java 语义信息。

**OSThread**：对 OS 原生线程的封装，定义在 `runtime/osThread.hpp`：

```cpp
class OSThread: public CHeapObj<mtThread> {
  pthread_t _pthread_id;          // Linux pthread ID
  pid_t     _thread_id;           // Linux thread ID (gettid)
  sigset_t  _caller_sigmask;      // 调用者的信号掩码
  int       _vm_created_tid;      // 用于线程同步
};
```

**线程创建流程**（Linux）：

```cpp
// os_linux.cpp
bool os::create_thread(Thread* thread, ThreadType thr_type, size_t stack_size) {
    // 1. 分配 OSThread
    OSThread* osthread = new OSThread(NULL, NULL);

    // 2. 设置线程属性
    pthread_attr_t attr;
    pthread_attr_init(&attr);
    pthread_attr_setstacksize(&attr, stack_size);
    pthread_attr_setguardsize(&attr, os::vm_page_size());

    // 3. 创建 pthread
    int ret = pthread_create(&osthread->pthread_id(), &attr,
                             java_start, thread);

    // 4. 等待子线程初始化完成
    {
        MonitorLocker ml(sync_with_child, Mutex::_no_safepoint_check_flag);
        while (osthread->get_state() == ALLOCATED) {
            ml.wait_without_safepoint_check();
        }
    }
}
```

注意步骤 4——父线程会阻塞等待子线程完成初始化。这是通过 `sync_with_child` 互斥锁实现的，确保子线程完全就绪后父线程才继续。

### 2.4.2 线程类型

JVM 内部有多种线程类型，它们的创建参数不同：

| 类型 | 说明 | 栈大小 |
|------|------|--------|
| `java_thread` | Java 应用线程 | `-Xss` 指定，默认 1MB |
| `vm_thread` | VM 操作线程 | 默认 512KB |
| `cgc_thread` | 并发 GC 线程 | 默认 512KB |
| `pgc_thread` | 并行 GC 线程 | 默认 512KB |
| `compiler_thread` | JIT 编译线程 | 默认 512KB |
| `watcher_thread` | 周期任务线程 | 默认 512KB |
| `os_thread` | 其他内部线程 | 默认 512KB |

---

## 2.5 信号处理机制：异常与 `safepoint` 的信号协同

### 2.5.1 信号在 JVM 中的角色

在 Linux/POSIX 上，JVM 大量使用信号（signal）来实现关键机制：

| 信号 | 用途 |
|------|------|
| `SIGSEGV` | 空指针异常、栈溢出检测、安全点轮询页保护 |
| `SIGBUS` | 未对齐的内存访问 |
| `SIGFPE` | 除零异常 |
| `SIGPIPE` | 套接字写断开 |
| `SIGUSR2` | 线程挂起/恢复（Suspend/Resume） |
| `SIGQUIT` | 线程转储（Ctrl+\） |
| `SIGILL` | 非法指令 |

### 2.5.2 安全点轮询的信号实现

JVM 的安全点机制使用 `SIGSEGV` 的一种精巧实现：

```
安全点轮询的两种机制：

1. 页保护机制（默认）：
   - 每个线程有本地轮询页
   - 正常运行时：页可读，轮询操作是普通内存读取（零开销）
   - 需要安全点时：保护页为不可读，轮询触发 SIGSEGV
   - 信号处理器检查是否为安全点触发，若是则让线程进入安全点

2. 逐线程信号机制：
   - 需要安全点时，向每个线程发送 SIGUSR2
   - 线程在信号处理器中自行进入安全点
```

默认的页保护机制更高效：运行时完全零开销（只是一次内存读取），只在需要安全点时才通过内存保护触发信号。

```cpp
// safepointMechanism.cpp
void SafepointMechanism::initialize() {
    // 为每个线程分配本地轮询页
    // _poll_page_armed_value   = 轮询页不可读时的值
    // _poll_page_disarmed_value = 轮询页可读时的值
}
```

### 2.5.3 信号处理器注册

```cpp
// signals_posix.cpp:1770+
void PosixSignals::install_signal_handler() {
    struct sigaction act;
    act.sa_handler = SR_handler;         // SIGUSR2 处理器
    act.sa_flags   = SA_RESTART | SA_SIGINFO;
    sigemptyset(&act.sa_mask);
    sigaction(PosixSignals::SR_signum, &act, nullptr);

    // SR_signum 默认为 SIGUSR2
    // 但可通过 -XX:+UseSIGUSR1 改为 SIGUSR1
}
```

JVM 要求 `SR_signum` 必须大于 `SIGSEGV` 和 `SIGBUS`，以保证安全点信号不会被异常信号覆盖。

### 2.5.4 栈溢出检测

Linux 的栈扩展机制与 JVM 的栈保护页之间有一个微妙的交互：

```
Linux 栈扩展行为：
  1. 线程访问栈保护区 → 触发 SIGSEGV
  2. 内核检查是否为栈增长 → 是则自动扩展栈
  3. 如果栈已到极限 → SIGSEGV 传递给进程

JVM 的栈保护页：
  1. 在线程栈底部设置保护页（PROT_NONE）
  2. Java 方法调用时检查栈剩余空间（stack banging）
  3. 如果触及保护页 → SIGSEGV → JVM 信号处理器判断为 StackOverflowError
```

在容器环境中，栈大小可能受 cgroup 限制，JVM 需要正确识别这种情况。

---

## 2.6 [体系结构视角] NUMA 感知与内存亲和性

### 2.6.1 NUMA 拓扑探测

在现代多路服务器上，内存访问延迟取决于 CPU 与内存的物理距离。JVM 的 NUMA 感知通过 `os/linux/` 层实现：

```cpp
// os_linux.cpp:4499
void os::Linux::numa_init() {
    if (!Linux::libnuma_init()) {
        disable_numa("Failed to initialize libnuma", true);
    } else {
        Linux::set_configured_numa_policy(Linux::identify_numa_policy());
        if (Linux::numa_max_node() < 1) {
            disable_numa("Only a single NUMA node is available", false);
        } else if (Linux::is_bound_to_single_mem_node()) {
            disable_numa("The process is bound to a single NUMA node", true);
        }
    }
}
```

NUMA 探测三步：
1. **加载 libnuma**：通过 `dlopen("libnuma.so")` 加载 NUMA 库
2. **识别策略**：判断进程运行在 `interleave` 还是 `membind` 模式
3. **构建映射**：建立 CPU → NUMA Node 的映射表

### 2.6.2 NUMA 感知的堆分配

当 `UseNUMA` 启用时，JVM 的 GC 可以将堆分区（Region/Page）绑定到特定的 NUMA 节点：

```cpp
// os_linux.cpp:3059
void os::numa_make_local(char *addr, size_t bytes, int lgrp_hint) {
    Linux::numa_set_bind_policy(USE_MPL_PREFERRED);
    Linux::numa_tonode_memory(addr, bytes, lgrp_hint);
}

void os::numa_make_global(char *addr, size_t bytes) {
    Linux::numa_interleave_memory(addr, bytes);
}
```

- `numa_make_local`：将内存绑定到指定节点（`MPOL_PREFERRED`，非强制）
- `numa_make_global`：在所有节点间交错分配（`MPOL_INTERLEAVE`）

### 2.6.3 NUMA 对 GC 的影响

不同 GC 对 NUMA 的利用程度不同：

| GC | NUMA 策略 |
|----|----------|
| Serial | 不感知 NUMA |
| Parallel | `UseNUMA` 启用时，Eden 区按 NUMA 节点分区 |
| G1 | `UseNUMA` 启用时，Region 优先分配在发起分配的线程所在节点 |
| ZGC | NUMA 感知最完善，每个 NUMA 节点有独立的页面分配器 |
| Shenandoah | NUMA 感知分区，对象分配亲和性 |

### 2.6.4 容器环境下的 NUMA

在 Kubernetes 等容器编排系统中，NUMA 拓扑信息通常被屏蔽。JVM 通过 cgroup 感知来适配：

```cpp
// os_linux.cpp:4495
void os::pd_init_container_support() {
    OSContainer::init();  // 读取 cgroup v1/v2 信息
}
```

`OSContainer::init()` 读取以下 cgroup 文件：
- `/sys/fs/cgroup/memory/memory.limit_in_bytes`（v1）
- `/sys/fs/cgroup/memory.max`（v2）
- CPU 配额和份额信息

当检测到运行在容器中时，JVM 会自动调整：
- `_processor_count` 取 `min(物理CPU数, cgroup CPU配额)`
- 堆大小限制考虑 cgroup 内存限制
- NUMA 感知通常被禁用（容器看不到 NUMA 拓扑）

### 2.6.5 [AI 推理场景] NUMA 对 LLM 推理的影响

LLM 推理是内存带宽密集型工作负载。在多路服务器上：
- KV Cache 的访问模式是流式的（sequential scan）
- 模型参数的读取跨所有层
- 如果 KV Cache 和模型参数分散在不同 NUMA 节点，跨节点访问延迟增加 2-3 倍

优化建议：
1. 使用 `numactl --interleave=all` 启动 JVM，使堆在所有节点交错分配
2. 或使用 `numactl --preferred=nodeX` 绑定到推理请求最多的节点
3. 对于 ZGC，`-XX:ZAllocationInterval=N` 可以配合 NUMA 亲和性

---

## 小结

本章剖析了 JVM 操作系统适配层的架构：

1. **三层适配**：共享接口 → POSIX 公共层 → 平台特定层，最大化代码复用
2. **两阶段初始化**：`os::init()` 在参数解析前，`os::init_2()` 在参数解析后
3. **内存映射**：虚拟地址空间预留 + 按需提交的分层策略
4. **信号机制**：SIGSEGV 同时服务于异常处理和安全点轮询，是 JVM 最精巧的 OS 交互之一
5. **NUMA 感知**：从 libnuma 探测到 GC 分区亲和，跨层协作实现内存本地性
6. **容器适配**：cgroup v1/v2 感知使 JVM 在云原生环境中正确运行

下一章将深入 CPU 架构适配层，看 JVM 如何在 x86、AArch64、RISC-V 等架构上生成和执行机器码。
