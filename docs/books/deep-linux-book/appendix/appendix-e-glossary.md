---
chapter: E
part: 附录
title: 术语中英对照表
status: todo
---

# 附录E 术语中英对照表

## 硬件与体系结构

| 英文 | 中文 |
|------|------|
| Out-of-Order Execution | 乱序执行 |
| Branch Prediction | 分支预测 |
| Speculative Execution | 推测执行 |
| Pipeline | 流水线 |
| Cache Line | 缓存行 |
| False Sharing | 伪共享 |
| TLB (Translation Lookaside Buffer) | 旁路转换缓冲/页表缓存 |
| Page Table Walk | 页表遍历 |
| NUMA (Non-Uniform Memory Access) | 非一致性内存访问 |
| SIMD (Single Instruction Multiple Data) | 单指令多数据 |
| Privilege Level | 特权级 |
| System Call | 系统调用 |
| DMA (Direct Memory Access) | 直接内存访问 |
| CXL (Compute Express Link) | 计算快速互连 |
| PCIe (Peripheral Component Interconnect Express) | 外设组件互连快速版 |
| NVMe (Non-Volatile Memory Express) | 非易失性内存快速版 |
| RDMA (Remote Direct Memory Access) | 远程直接内存访问 |

## 进程与调度

| 英文 | 中文 |
|------|------|
| Process | 进程 |
| Thread | 线程 |
| Task | 任务 |
| Context Switch | 上下文切换 |
| CFS (Completely Fair Scheduler) | 完全公平调度器 |
| vruntime | 虚拟运行时间 |
| Scheduling Domain | 调度域 |
| Load Balancing | 负载均衡 |
| PELT (Per-Entity Load Tracking) | 每实体负载追踪 |
| PSI (Pressure Stall Information) | 压力停滞信息 |
| cgroup (Control Group) | 控制组 |
| Namespace | 命名空间 |
| Copy-on-Write (COW) | 写时复制 |

## 内存管理

| 英文 | 中文 |
|------|------|
| Buddy System | 伙伴系统 |
| Page Frame | 页帧 |
| Virtual Memory | 虚拟内存 |
| VMA (Virtual Memory Area) | 虚拟内存区域 |
| Page Fault | 缺页异常 |
| Page Cache | 页缓存 |
| Swap | 交换 |
| Huge Page | 大页 |
| THP (Transparent Huge Page) | 透明大页 |
| KSM (Kernel Samepage Merging) | 内核同页合并 |
| CMA (Contiguous Memory Allocator) | 连续内存分配器 |
| SLUB | SLUB分配器 |
| RMAP (Reverse Mapping) | 反向映射 |
| GUP (get_user_pages) | 获取用户页 |
| OOM (Out of Memory) Killer | 内存不足杀手 |
| DAMON (Data Access MONitor) | 数据访问监控 |
| compaction | 内存压缩 |
| working set | 工作集 |
| memory tier | 内存分层 |
| HMM (Heterogeneous Memory Management) | 异构内存管理 |

## 同步与并发

| 英文 | 中文 |
|------|------|
| Spinlock | 自旋锁 |
| Mutex | 互斥锁 |
| Semaphore | 信号量 |
| RCU (Read-Copy-Update) | 读-拷贝-更新 |
| futex (Fast Userspace Mutex) | 快速用户态互斥锁 |
| Memory Barrier | 内存屏障 |
| Memory Ordering | 内存序 |
| Deadlock | 死锁 |
| Priority Inversion | 优先级反转 |
| Priority Inheritance | 优先级继承 |
| Lockdep | 锁依赖检测 |
| MCS Lock | MCS锁 |
| Optimistic Spinning | 乐观自旋 |

## I/O与存储

| 英文 | 中文 |
|------|------|
| Block Layer | 块层 |
| bio (Block I/O) | 块I/O |
| blk-mq (Block Multi-Queue) | 多队列块层 |
| I/O Scheduler | I/O调度器 |
| O_DIRECT | 直接I/O |
| Page Cache | 页缓存 |
| Writeback | 写回 |
| Flush | 刷新 |
| FUA (Force Unit Access) | 强制单元访问 |
| DAX (Direct Access) | 直接访问 |
| io_uring | io_uring异步I/O |
| SQPOLL (SQ Polling) | SQ轮询 |
| uring_cmd | io_uring命令 |
| WAL (Write-Ahead Log) | 预写日志 |
| fsync | 文件同步 |

## 网络与eBPF

| 英文 | 中文 |
|------|------|
| sk_buff (Socket Buffer) | 套接字缓冲区 |
| NAPI (New API) | 新API(中断轮询混合) |
| XDP (eXpress Data Path) | 快速数据路径 |
| eBPF (Extended Berkeley Packet Filter) | 扩展伯克利包过滤器 |
| BTF (BPF Type Format) | BPF类型格式 |
| CO-RE (Compile Once - Run Everywhere) | 编译一次-到处运行 |
| BPF LSM | BPF安全模块 |
| Verifier | 验证器 |
| Trampoline | 跳板 |

## 安全

| 英文 | 中文 |
|------|------|
| LSM (Linux Security Module) | Linux安全模块 |
| SELinux | 安全增强Linux |
| KASAN (Kernel Address Sanitizer) | 内核地址消毒器 |
| KFENCE (Kernel Electric Fence) | 内核电子围栏 |
| KMSAN (Kernel Memory Sanitizer) | 内核内存消毒器 |
| SEV (Secure Encrypted Virtualization) | 安全加密虚拟化 |
| TDX (Trust Domain Extensions) | 可信域扩展 |
| Confidential Computing | 机密计算 |
| mseal | 内存密封 |

## AI相关

| 英文 | 中文 |
|------|------|
| KV Cache | KV缓存 |
| PagedAttention | 分页注意力 |
| Continuous Batching | 连续批处理 |
| Speculative Decoding | 推测解码 |
| Inference | 推理 |
| Prefill | 预填充 |
| Decode | 解码 |
| Memory Wall | 内存墙 |
| HBM (High Bandwidth Memory) | 高带宽内存 |
