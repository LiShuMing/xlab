---
chapter: 13
part: 第三篇 内存管理 —— 最复杂的子系统
title: 内存安全与调试
source_anchor:
  - mm/kasan/
  - mm/kfence/
  - mm/kmsan/
  - mm/kmemleak.c
  - mm/page_owner.c
  - mm/page_poison.c
  - mm/page_ext.c
  - mm/debug.c
  - arch/x86/mm/mem_encrypt_amd.c
  - arch/x86/mm/kasan_init_64.c
  - arch/x86/mm/kmsan_shadow.c
status: done
---

# 第13章 内存安全与调试

## 写作目标

掌握Linux内核内存安全的三大工具(KASAN/KFENCE/KMSAN)和内存加密机制，理解内核如何防御内存漏洞。

## 章节大纲

### 13.1 KASAN：地址消毒

- **精读** `mm/kasan/`：
  - `init.c`：shadow memory的映射建立
  - `generic.c`：通用KASAN实现
  - `hw_tags.c`：硬件标签KASAN(MTE)
  - `quarantine.c`：隔离区——延迟释放以检测UAF
  - `report.c`：错误报告
  - `kasan_test_c.c`：测试用例
- KASAN shadow memory原理：
  - 1:8的影子内存映射
  - 每8字节对应1字节影子
  - **精读** `arch/x86/mm/kasan_init_64.c`：x86 shadow映射建立
- KASAN能检测的问题：越界访问/Use-After-Free/越界写
- KASAN不能检测的问题及KFENCE的补充

### 13.2 KFENCE：低开销采样检测

- **精读** `mm/kfence/`：
  - 采样策略：随机选择分配进行监控
  - guard page机制：红区检测越界
  - 与KASAN的互补关系
- KFENCE的部署：持续运行的生产环境安全网

### 13.3 KMSAN：未初始化内存检测

- **精读** `mm/kmsan/`：
  - shadow memory追踪初始化状态
  - origin追踪：记录未初始化值的来源
  - **精读** `arch/x86/mm/kmsan_shadow.c`：x86 shadow映射
- KMSAN与信息泄露防御

### 13.4 内存调试工具

- `mm/kmemleak.c`：内核内存泄露检测
  - 对象扫描与引用查找
- `mm/page_owner.c`：页面所有者追踪
- `mm/page_poison.c`：页面毒化——释放页面的填充检测
- `mm/page_ext.c`：页面扩展框架——支持page_owner/poison等
- `mm/debug.c`：通用内存调试输出

### 13.5 内存加密：SME/SEV

- **精读** `arch/x86/mm/mem_encrypt_amd.c`：
  - SME(System Memory Encryption)：全系统内存加密
  - SEV(Secure Encrypted Virtualization)：虚拟机级加密
  - 加密位(C-bit)与页表项
- Intel TDX：`arch/x86/coco/tdx/`
- 机密计算的安全模型

## 关键源文件清单

| 文件/目录 | 行数 | 关注点 |
|-----------|------|--------|
| `mm/kasan/generic.c` | ~600 | KASAN通用实现 |
| `mm/kfence/core.c` | ~800 | KFENCE核心 |
| `mm/kmsan/` | — | KMSAN全家桶 |
| `mm/kmemleak.c` | ~2000 | 内存泄露检测 |
| `arch/x86/mm/mem_encrypt_amd.c` | ~500 | AMD内存加密 |

## 跨章依赖

- 依赖第9章（物理内存）：shadow memory的映射需要物理页
- 依赖第10章（虚拟内存）：shadow映射使用虚拟地址空间
