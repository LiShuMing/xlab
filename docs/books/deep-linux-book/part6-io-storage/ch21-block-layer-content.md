# 第21章 通用块层

> 源码锚点：`block/bio.c`、`block/blk-mq.c`、`block/blk-mq-sched.c`、`block/mq-deadline.c`、`block/bfq-iosched.c`、`block/blk-merge.c`、`block/blk-flush.c`

块层是文件系统和存储设备之间的抽象层——文件系统提交bio，块层通过调度和优化后派发给驱动。blk-mq多队列模型是现代块层的核心，它将I/O路径从全局锁扩展到per-CPU无锁队列，支撑NVMe等高速设备的百万级IOPS。

## 21.1 bio与request的抽象

### struct bio：块I/O的通用表示

bio是块I/O的基本单位——描述一个或多个连续/不连续的扇区操作：

```c
// include/linux/blk_types.h
struct bio {
    struct block_device *bi_bdev;     // 目标块设备
    blk_opf_t           bi_opf;       // 操作标志(读/写/flush/fua...)
    struct bio_vec      *bi_io_vec;   // 段数组
    struct bvec_iter    bi_iter;      // 当前迭代位置
    bio_end_io_t        *bi_end_io;   // 完成回调
    unsigned short      bi_vcnt;      // 段数量
    // ...
};

struct bio_vec {
    struct page *bv_page;     // 内存页
    unsigned int bv_len;      // 长度(字节)
    unsigned int bv_offset;   // 页内偏移
};
```

bio的关键设计：
- **多段(Multi-segment)**：一个bio可以包含多个bio_vec——物理不连续但逻辑连续的内存区。这允许散-聚DMA——硬件一次DMA传输完成多个段的读写
- **分裂与克隆**：bio可以分裂(设备限制超出时)和克隆(镜像/快照场景)，各自独立完成

### submit_bio()：I/O提交入口

```
submit_bio(bio)
  → submit_bio_noacct(bio)
    → blk_mq_submit_bio(bio)   // blk-mq路径
      → bio转换为request
      → 插入软件队列或调度器
      → 派发到硬件队列
```

## 21.2 blk-mq：多队列块层

### 三级队列架构

blk-mq采用三级队列架构，消除传统块层的全局锁瓶颈：

```
软件队列(ctx)         → 硬件队列(hctx)       → 驱动
per-CPU, 无锁         per-硬件队列, 自旋锁    NVMe提交队列
blk_mq_ctx            blk_mq_hw_ctx
```

- **软件队列(ctx)**：per-CPU，无锁操作。每个CPU将请求放入自己的ctx，避免跨CPU竞争
- **硬件队列(hctx)**：与硬件提交队列一一对应。NVMe多队列时，每个提交队列对应一个hctx
- **标签(tags)**：每个hctx维护一组标签——驱动用标签跟踪已提交的请求，完成时通过标签找到原始request

### CPU到硬件队列的映射

`blk_mq_map_queues()`建立CPU到hctx的映射——多个CPU可以映射到同一个hctx。NVMe多队列时，映射策略是：CPU N → hctx (N % nr_hw_queues)，确保I/O均匀分布。

### blk_mq_submit_bio()：bio到request的转换

```c
// block/blk-mq.c (简化)
void blk_mq_submit_bio(struct bio *bio)
{
    // 1. 分配request（从标签池或缓存）
    rq = blk_mq_get_request(q, bio, ...);

    // 2. 将bio的数据映射到request
    blk_mq_bio_to_request(rq, bio);

    // 3. 尝试合并到已有request（如果启用了合并）
    // 4. 插入调度器或直接派发
    blk_mq_sched_insert_request(rq, ...);
}
```

### blk_mq_dispatch_rq_list()：请求派发

```c
// block/blk-mq.c (简化)
void blk_mq_dispatch_rq_list(struct blk_mq_hw_ctx *hctx, struct list_head *list)
{
    // 遍历请求列表，逐个提交给驱动
    do {
        rq = list_first_entry(list, struct request, queuelist);
        blk_mq_start_request(rq);          // 设置超时、统计开始时间
        ret = hctx->queue->mq_ops->queue_rq(hctx, rq);  // 调用驱动的提交函数
    } while (!list_empty(list) && ret == BLK_STS_OK);
}
```

NVMe驱动的`queue_rq()`将request转换为NVMe命令，写入提交队列的门铃寄存器。

### 请求完成

NVMe完成中断触发 → `blk_mq_end_request()` → 调用bio的`bi_end_io`回调 → 通知上层（文件系统或io_uring）。

批量完成(`blk_mq_end_request_batch()`)：多个请求在同一次中断中完成时，批量处理减少锁操作。

## 21.3 I/O调度器

### Deadline调度器

`mq-deadline.c`是默认的I/O调度器——简单高效：

```
请求按到达顺序进入FIFO队列
同时按扇区位置进入红黑树(读/写各一棵)

派发策略：
1. 优先派发读请求(读延迟敏感)
2. 读请求到期时(500ms)强制派发——防饿死
3. 写请求到期时(5s)强制派发
4. 红黑树按位置查找——利用局部性合并相邻请求
```

Deadline调度器的核心约束：**读请求优先**——因为读通常是同步的（应用在等待），写通常是异步的（后台写回）。

### BFQ调度器

BFQ(Budget Fair Queueing)为每个进程/组分配I/O预算——确保公平的带宽分配：

```
每个进程一个BFQ队列
按权重分配I/O时间片(预算)
轮转调度——类似CPU的CFS

适合桌面：保证视频播放不被编译任务饿死
不适合数据库：引入额外延迟
```

BFQ的`bfq_cgroup`支持cgroup v2的I/O控制器——容器间公平分配I/O带宽。

### Kyber调度器

Kyber专为NVMe等高速设备设计——基于令牌的拥塞控制：

```
两类令牌：读令牌 + 写令牌
派发请求时消耗令牌
令牌用完时阻塞——防止设备过载

无需排序——NVMe的内部调度更高效
延迟可预测——令牌数控制并发度
```

### 无调度器(none)

NVMe SSD通常使用none调度器——直接派发，不经过任何排序或合并。NVMe控制器内部有自己的调度逻辑，内核侧再排序只会增加延迟。

## 21.4 I/O合并与优化

### 请求合并

`blk-merge.c`实现请求合并——将物理相邻的bio合并为单个request，减少硬件命令数：

- **前合并(Front merge)**：新bio在request之前，扇区连续
- **后合并(Back merge)**：新bio在request之后，扇区连续

合并条件：扇区连续 + 同一设备 + 同一标志位 + 未超出最大段数和大小。

### FLUSH/FUA语义

`blk-flush.c`实现写屏障——确保之前的写操作在之后的写操作之前持久化：

```
fsync()的内核路径：
  1. 提交FLUSH → 设备刷出写缓存
  2. 提交FUA(Force Unit Access)写 → 数据绕过写缓存直接持久化
  3. 提交FLUSH → 确保FUA写已持久化
```

数据库WAL的持久化依赖FLUSH/FUA——WAL写入后必须fsync，确保日志在事务提交前到达稳定存储。

## 21.5 I/O成本控制

### blk-iocost：基于权重的带宽分配

`blk-iocost.c`实现精确的I/O成本模型——不按IOPS或带宽限速，而是按"成本"（考虑寻道、传输等因素）分配：

```
每个cgroup有权重 → 按权重分配I/O时间
vrate(虚拟速率)调整 → 防止设备空闲或过载
周期性校准 → 适应设备性能变化
```

### blk-iolatency：I/O延迟控制

`blk-iolatency.c`监控I/O延迟——超过目标延迟时节流发出I/O的cgroup：

```
设置目标延迟(如5ms)
每次I/O完成测量延迟
滑动窗口内延迟超标 → 节流该cgroup
```

### cgroup I/O控制器

`blk-throttle.c`提供简单的I/O限速——按cgroup限制IOPS和带宽上限。

> **数据库视角**：WAL写路径绕过I/O调度。数据库的WAL写入是顺序的、延迟敏感的——使用O_DIRECT绕过Page Cache，none调度器避免不必要的排序，直接派发到NVMe。数据文件的写入可以使用BFQ或iocost控制——防止后台刷脏页影响前台查询的I/O延迟。

---

本章建立了对块层的完整认知：bio是块I/O的通用表示，blk-mq三级队列消除全局锁瓶颈，调度器在公平性和延迟间取舍，FLUSH/FUA实现写屏障，iocost/iolatency提供精确的I/O控制。块层是存储I/O路径的核心枢纽——理解块层才能理解I/O延迟的来源和优化方向。
