# 第33章 CXL与异构内存

> 源码锚点：`drivers/cxl/`、`mm/memory-tiers.c`、`mm/damon/`、`mm/migrate.c`

CXL(Compute Express Link)连接CPU和异构内存设备——HBM、DDR、CXL内存、持久内存构成多层次的内存金字塔。Linux的内存分层和DAMON热度监控机制实现了热度驱动的页面迁移——热页在快速层，冷页在慢速层。

## 33.1 CXL驱动精读

### CXL核心抽象

`drivers/cxl/core/`提供CXL设备的核心抽象：

- **port**：CXL端口——上游端口(连接主机)和下游端口(连接设备)
- **decoder**：地址解码器——将系统地址映射到CXL设备的物理地址
- **region**：CXL区域——一段连续的系统地址空间，映射到一个或多个CXL设备

### CXL Type 3设备

`drivers/cxl/mem.c`管理CXL Type 3内存设备——提供扩展内存容量：

```
CXL Type 3设备枚举：
  1. PCI枚举发现CXL设备
  2. 读取CDAT(Coherent Device Attribute Table)获取性能特征
  3. 配置decoder——建立系统地址到设备内存的映射
  4. 将CXL内存注册为NUMA节点 → 内核的内存管理感知CXL内存
```

CXL内存作为NUMA节点——这意味着所有NUMA感知的优化(内存策略、调度域)自动适用于CXL内存。

### CXL持久内存

`drivers/cxl/pmem.c`将CXL设备注册为持久内存——与libnvdimm框架集成，提供类似PMEM的DAX访问。

### CXL端口与交换机

`drivers/cxl/port.c`管理CXL交换机——扩展CXL拓扑，允许一个主机端口连接多个CXL设备：

```
Host → CXL Root Port → CXL Switch → Device 0
                             ├→ Device 1
                             └→ Device 2
```

交换机的decoder决定哪些地址范围路由到哪个下游端口——类似PCIe交换机但支持缓存一致性。

## 33.2 内存分层

### memory-tiers框架

`mm/memory-tiers.c`实现内存分层抽象——将不同类型的内存组织为层次：

```
MT_HIGHEST  → HBM (GPU/高带宽内存)    ~3TB/s, ~几十GB
MT_NORMAL   → DDR5 (本地内存)          ~100GB/s, ~几百GB
MT_LOWEST   → CXL DDR (远端内存)       ~50GB/s, ~TB级
             → NVM (持久内存)           ~10GB/s, ~TB级
```

### demotion路径

当快速层内存紧张时，页面自动降级(demote)到慢速层：

```
HBM满 → demote冷页到DDR → DDR满 → demote冷页到CXL → CXL满 → swap到SSD
```

demotion路径是单向的——从快速到慢速。反向提升(promotion)需要显式触发——DAMON热度监控或应用请求。

### 热度驱动的页面迁移

内核结合memory-tiers和DAMON，实现自动的热度感知迁移：

```
DAMON监控页面访问热度
  → 热页在慢速层 → promote到快速层
  → 冷页在快速层 → demote到慢速层
```

## 33.3 DAMON在异构内存中的应用

### 物理地址监控

`mm/damon/paddr.c`监控物理页面的访问热度——不依赖虚拟地址，适用于CXL内存等无进程关联的页面。

### LRU排序

`mm/damon/lru_sort.c`基于DAMON的热度信息重新排序LRU链表——热页移到活跃链表，冷页移到非活跃链表。这加速了冷页的回收——在异构内存场景中，加速了快速层的冷页降级。

### 主动回收

`mm/damon/reclaim.c`在内存压力下主动回收冷页——不等待kswapd被动回收，而是基于DAMON的热度信息提前回收。

### 与memory-tiers的联动

DAMON + memory-tiers的联合工作：

```
1. DAMON检测到CXL内存上的页面被频繁访问
2. 报告给memory-tiers：此页面是"热页"
3. memory-tiers发起promotion：将页面从CXL迁移到DDR
4. DDR上的页面长期未访问
5. DAMON标记为"冷页"
6. memory-tiers发起demotion：将页面从DDR迁移到CXL
```

## 33.4 页面迁移机制

### migrate_pages()

`mm/migrate.c`的`migrate_pages()`是页面迁移的核心——将一组页面从源节点迁移到目标节点：

```
migrate_pages()
  1. 锁定页面(防止并发修改)
  2. 分配新页面(目标节点)
  3. 拷贝页面内容
  4. 更新页表映射(指向新页面)
  5. 刷新TLB(确保CPU使用新映射)
  6. 释放旧页面
```

迁移的挑战：
- **并发访问**：迁移期间其他CPU可能访问该页面——需要适当的锁保护
- **大页面**：2MB/1GB大页的迁移开销远高于4KB页——需要拆分为小页或整体迁移
- **设备内存**：GPU正在使用的页面不能直接迁移——需要先从GPU unmap

### move_pages()系统调用

用户态通过`move_pages()`显式控制页面迁移：

```c
move_pages(pid, nr_pages, addrs, nodes, status, MPOL_MF_MOVE);
// 将指定地址的页面迁移到指定的NUMA节点
```

数据库和推理引擎可以使用`move_pages()`主动将热数据迁移到快速内存。

## 33.5 展望：CXL共享内存池化推理

### CXL内存池化

CXL 3.0支持内存池化——多台主机共享同一个CXL内存池：

```
Host 0 ←→ CXL Switch ←→ CXL Memory Pool (TB级)
Host 1 ←→              ←→
Host N ←→              ←→
```

每台主机可以看到CXL内存池的一部分或全部——通过decoder配置地址映射。

### 多GPU推理共享KV Cache池

CXL共享内存池化推理的架构：

```
GPU 0 (HBM 80GB) ←→ CXL DDR Pool (1TB) ←→ GPU 1 (HBM 80GB)
                       ↕
                   GPU 2 (HBM 80GB)

KV Cache分层：
  - 热KV Block → GPU HBM (3TB/s带宽)
  - 温KV Block → CXL DDR (50GB/s带宽)
  - 冷KV Block → CXL NVM (10GB/s带宽)
```

CXL内存池解决了GPU显存容量瓶颈——80GB HBM只能支持约40K token的KV Cache，而1TB CXL DDR可以支持约500K token。

### CXL.cache：缓存一致性扩展

CXL.cache允许CPU缓存CXL内存的数据——GPU可以直接缓存CXL内存中的KV Block，无需显式拷贝到HBM。这消除了KV Cache换入换出的拷贝开销——GPU通过CXL.cache直接访问远端内存中的数据。

> **AI视角**：热度感知的KV Block放置。结合DAMON的热度监控，推理引擎可以实现KV Block的自动分层：DAMON检测到某请求的KV Block被频繁访问 → promote到GPU HBM；长时间未访问 → demote到CXL DDR。这与内核的memory-tiers自动迁移是同一思想——只是应用对象从CPU页面变为KV Block。

---

本章建立了对CXL与异构内存管理的完整认知：CXL驱动管理CXL设备的枚举和配置，memory-tiers框架将异构内存组织为层次，DAMON监控访问热度驱动页面迁移，页面迁移机制支持数据在异构内存间移动。CXL共享内存池化推理展望了未来——多GPU共享TB级CXL内存池，热度感知的KV Block分层放置，消除GPU显存容量瓶颈。
