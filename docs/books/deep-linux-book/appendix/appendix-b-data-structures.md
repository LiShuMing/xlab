---
chapter: B
part: 附录
title: 关键数据结构速查
status: todo
---

# 附录B 关键数据结构速查

## task_struct（进程描述符）

源码：`include/linux/sched.h`

| 字段 | 类型 | 说明 |
|------|------|------|
| state | volatile long | 进程状态(TASK_RUNNING等) |
| stack | void * | 内核栈 |
| prio | int | 动态优先级 |
| static_prio | int | 静态优先级 |
| mm | struct mm_struct * | 用户地址空间 |
| active_mm | struct mm_struct * | 内核线程借用 |
| pid | pid_t | 进程ID |
| tgid | pid_t | 线程组ID |
| fs | struct fs_struct * | 文件系统信息 |
| files | struct files_struct * | 打开文件表 |
| nsproxy | struct nsproxy * | 命名空间 |
| signal | struct signal_struct * | 信号处理 |
| cgroups | struct css_set * | cgroup归属 |
| sched_class | const struct sched_class * | 调度类 |

## mm_struct（内存描述符）

源码：`include/linux/mm_types.h`

| 字段 | 类型 | 说明 |
|------|------|------|
| pgd | pgd_t * | 顶级页表 |
| mmap | struct vm_area_struct * | VMA链表 |
| mm_mt | struct maple_tree | VMA树(maple tree) |
| start_code/end_code | unsigned long | 代码段 |
| start_data/end_data | unsigned long | 数据段 |
| start_brk/brk | unsigned long | 堆 |
| start_stack | unsigned long | 栈 |
| mmap_base | unsigned long | mmap区基址 |
| total_vm | unsigned long | 总虚拟页数 |
| locked_vm | unsigned long | 锁定页数 |

## vm_area_struct（虚拟内存区域）

源码：`include/linux/mm_types.h`

| 字段 | 类型 | 说明 |
|------|------|------|
| vm_start/vm_end | unsigned long | 虚拟地址范围 |
| vm_mm | struct mm_struct * | 所属mm |
| vm_page_prot | pgprot_t | 页保护属性 |
| vm_flags | unsigned long | VMA标志 |
| vm_ops | struct vm_operations_struct * | VMA操作集 |
| vm_file | struct file * | 关联文件 |
| vm_pgoff | unsigned long | 文件偏移(页单位) |

## bio（块I/O请求）

源码：`include/linux/blk-mq.h`、`include/linux/bio.h`

| 字段 | 类型 | 说明 |
|------|------|------|
| bi_iter | struct bvec_iter | 当前迭代位置 |
| bi_disk | struct gendisk * | 目标磁盘 |
| bi_opf | unsigned int | 操作标志 |
| bi_vcnt | unsigned short | bio_vec数量 |
| bi_io_vec | struct bio_vec * | bio_vec数组 |
| bi_end_io | bio_end_io_t * | 完成回调 |

## sk_buff（网络数据包）

源码：`include/linux/skbuff.h`

| 字段 | 类型 | 说明 |
|------|------|------|
| next/prev | struct sk_buff * | 链表指针 |
| dev | struct net_device * | 网络设备 |
| len | unsigned int | 数据总长度 |
| data_len | unsigned int | 分片数据长度 |
| transport_header | sk_buff_data_t | 传输层头偏移 |
| network_header | sk_buff_data_t | 网络层头偏移 |
| mac_header | sk_buff_data_t | MAC头偏移 |
| cb[48] | char | 控制块(子系统能力) |

## rq（运行队列）

源码：`kernel/sched/sched.h`

| 字段 | 类型 | 说明 |
|------|------|------|
| nr_running | unsigned int | 运行进程数 |
| cfs | struct cfs_rq | CFS运行队列 |
| rt | struct rt_rq | RT运行队列 |
| dl | struct dl_rq | Deadline运行队列 |
| curr | struct task_struct * | 当前运行进程 |
| clock | u64 | 运行队列时钟 |

## zone（内存区域）

源码：`include/linux/mmzone.h`

| 字段 | 类型 | 说明 |
|------|------|------|
| free_area | struct free_area[MAX_ORDER] | 伙伴系统空闲区 |
| watermark | unsigned long[NR_WMARK] | 水位线 |
| per_cpu_pageset | struct per_cpu_pageset __percpu * | per-CPU页面集 |
| nr_free | unsigned long | 空闲页数 |
| zone_pgdat | struct pglist_data * | 所属节点 |

## pglist_data（NUMA节点）

源码：`include/linux/mmzone.h`

| 字段 | 类型 | 说明 |
|------|------|------|
| node_zones | struct zone[MAX_NR_ZONES] | 节点内zone数组 |
| node_zonelists | struct zonelist | zone分配列表 |
| node_id | int | 节点ID |
| node_start_pfn | unsigned long | 起始PFN |
| node_present_pages | unsigned long | 总页数 |
| node_spanned_pages | unsigned long | 跨度页数 |
