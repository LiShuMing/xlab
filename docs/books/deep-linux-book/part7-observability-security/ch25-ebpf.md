---
chapter: 25
part: 第七篇 可观测性、安全与调试 —— 让系统透明
title: eBPF：内核可编程观测与安全
source_anchor:
  - kernel/bpf/verifier.c
  - kernel/bpf/core.c
  - kernel/bpf/helpers.c
  - kernel/bpf/syscall.c
  - kernel/bpf/trampoline.c
  - kernel/bpf/btf.c
  - kernel/bpf/arraymap.c
  - kernel/bpf/hashtab.c
  - kernel/bpf/ringbuf.c
  - kernel/bpf/bpf_lsm.c
  - kernel/bpf/task_iter.c
  - security/bpf/hooks.c
status: done
---

# 第25章 eBPF：内核可编程观测与安全

## 写作目标

深入理解eBPF的内核实现，从验证器到JIT到Map系统，掌握BPF LSM安全扩展。

## 章节大纲

### 25.1 eBPF的架构概览

- BPF程序的生命周期：编写→编译→加载→验证→JIT→附着→执行
- BPF程序类型：tracing/XDP/cgroup/skb/sched等
- BPF与内核子系统的附着点

### 25.2 验证器：安全的保证

- **精读** `kernel/bpf/verifier.c`（20191行）：
  - 两阶段验证：CFG检查 + 状态探索
  - 寄存器状态追踪：类型/范围/指针来源
  - 路径剪枝：已验证状态的缓存
  - 辅助函数的白名单与参数检查
  - 循环检测与有界循环
  - *为什么验证器是eBPF安全的基石*

### 25.3 BPF核心与JIT

- **精读** `kernel/bpf/core.c`：
  - BPF指令解释器
  - BPF程序的调用约定
- `kernel/bpf/trampoline.c`：
  - ftrace-based trampoline
  - BPF程序的动态附着
  - *JIT技术对数据库JIT引擎的启示*

### 25.4 BTF(BPF Type Format)

- **精读** `kernel/bpf/btf.c`：
  - 类型信息的编码与去重
  - CO-RE(Compile Once - Run Everywhere)
  - btf_relocate：类型重定位

### 25.5 Map系统

- `kernel/bpf/arraymap.c`：数组Map
- `kernel/bpf/hashtab.c`：哈希表Map
- `kernel/bpf/ringbuf.c`：环形缓冲区Map——高效的用户态数据传输
- `kernel/bpf/lpm_trie.c`：最长前缀匹配
- `kernel/bpf/bloom_filter.c`：布隆过滤器
- `kernel/bpf/stackmap.c`：栈追踪Map
- `kernel/bpf/percpu_freelist.c`：per-CPU空闲列表
- `kernel/bpf/local_storage.c`：BPF本地存储

### 25.6 BPF迭代器

- `kernel/bpf/task_iter.c`：任务迭代器
- `kernel/bpf/map_iter.c`：Map迭代器
- `kernel/bpf/bpf_iter.c`：迭代器核心
- `kernel/bpf/kmem_cache_iter.c`：slab缓存迭代器
- `kernel/bpf/cgroup_iter.c`：cgroup迭代器

### 25.7 BPF LSM：用BPF实现安全策略

- `kernel/bpf/bpf_lsm.c`：BPF LSM程序注册
- `security/bpf/hooks.c`：LSM钩子的BPF实现
- *安全视角*：动态安全策略 vs 静态SELinux策略的权衡

### 25.8 BPF系统调用接口

- **精读** `kernel/bpf/syscall.c`：
  - bpf()系统调用：cmd分发
  - BPF_PROG_LOAD/BPF_MAP_CREATE/BPF_OBJ_GET
  - BPF token：`kernel/bpf/token.c`

## 关键源文件清单

| 文件 | 行数 | 关注点 |
|------|------|--------|
| `kernel/bpf/verifier.c` | 20191 | 验证器 |
| `kernel/bpf/core.c` | ~2500 | BPF核心 |
| `kernel/bpf/syscall.c` | ~5000 | 系统调用 |
| `kernel/bpf/btf.c` | ~6000 | BTF |
| `kernel/bpf/trampoline.c` | ~1500 | trampoline |
| `kernel/bpf/ringbuf.c` | ~500 | 环形缓冲区 |

## 跨章依赖

- 依赖第17章（内存序）：BPF程序的原子操作
- 依赖第7章（调度器）：BPF可编程调度器(ext.c)
