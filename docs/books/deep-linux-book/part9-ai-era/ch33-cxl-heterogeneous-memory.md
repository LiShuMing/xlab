---
chapter: 33
part: 第九篇 AI时代的OS与硬件适配
title: CXL与异构内存
source_anchor:
  - drivers/cxl/
  - mm/memory-tiers.c
  - mm/damon/
  - mm/migrate.c
  - mm/hmm.c
status: done
---

# 第33章 CXL与异构内存

## 写作目标

深入理解CXL驱动实现与异构内存管理，展望CXL共享内存池化推理架构。

## 章节大纲

### 33.1 CXL驱动精读

- **精读** `drivers/cxl/`：
  - `core/`：CXL核心抽象
    - port、decoder、region的管理
  - `mem.c`：CXL内存设备驱动
    - CXL Type 3设备的枚举与管理
  - `pmem.c`：CXL持久内存
    - 与libnvdimm的集成
  - `port.c`：CXL端口/交换机
    - 解码器的配置
  - `pci.c`：CXL PCI设备管理
  - `acpi.c`：ACPI表解析(AC001/CEDT)
  - `security.c`：CXL安全特性
  - `pmu.h`：CXL性能监控单元

### 33.2 内存分层

- **精读** `mm/memory-tiers.c`：
  - HBM/DDR/NVM/CXL内存的分层抽象
  - 热度驱动的页面迁移：热页→快速层、冷页→慢速层
  - `MT_HIGHEST`/`MT_NORMAL`/`MT_LOWEST`等级定义
  - demotion路径的配置

### 33.3 DAMON在异构内存中的应用

- **精读** `mm/damon/`（与第11章呼应）：
  - `paddr.c`：物理地址监控——感知CXL内存的访问热度
  - `lru_sort.c`：基于热度的LRU排序
  - `reclaim.c`：冷页主动迁移/回收
  - 与memory-tiers的联动：热页promote到HBM、冷页demote到CXL

### 33.4 页面迁移机制

- **精读** `mm/migrate.c`：
  - `migrate_pages()`：页面迁移核心
  - `move_pages()`系统调用：用户态控制的迁移
  - NUMA迁移 vs 异构内存迁移的差异

### 33.5 展望：CXL共享内存池化推理

- CXL内存池化：多主机共享CXL内存池
  - *AI视角*：多GPU推理共享KV Cache池
  - 消除GPU显存容量瓶颈
  - 热度感知的KV Block放置：GPU HBM ↔ CXL DDR
- CXL.cache：缓存一致性扩展
  - GPU直接缓存CXL内存数据
  - 减少显存拷贝

## 关键源文件清单

| 文件/目录 | 关注点 |
|-----------|--------|
| `drivers/cxl/` | CXL驱动全家桶 |
| `mm/memory-tiers.c` | 内存分层 |
| `mm/damon/paddr.c` | 物理地址监控 |
| `mm/migrate.c` | 页面迁移 |

## 跨章依赖

- 依赖第4章（CXL硬件）：CXL协议层基础
- 依赖第11章（DAMON）：热度监控机制
