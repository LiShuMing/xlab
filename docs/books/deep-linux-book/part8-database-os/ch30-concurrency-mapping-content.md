# 第30章 并发控制与内核同步的映射

> 源码锚点：`kernel/locking/qspinlock.c`、`kernel/rcu/`、`kernel/futex/`、`kernel/locking/rwsem.c`、`kernel/locking/lockdep.c`

数据库并发控制与内核同步看似不同领域，实则思想相通——都在解决"多执行流正确共享资源"的问题。将两者映射对比，既能加深对内核同步的理解，也能为数据库并发控制提供新的设计灵感。

## 30.1 乐观并发控制与RCU

### 数据库OCC

OCC(Optimistic Concurrency Control)的核心思想：读不加锁，写时验证冲突——

```
1. 读阶段：不加锁读取数据，记录读集
2. 验证阶段：提交时检查读集是否被其他事务修改
3. 写阶段：如果验证通过，写入修改；否则回滚重试
```

OCC在低冲突场景下性能优异——读操作零开销(不加锁、不等待)。但高冲突场景下频繁回滚——代价全在写端。

### 内核RCU

RCU的核心思想：读不加锁，写时延迟回收——

```
1. 读端：无锁访问共享数据(rcu_read_lock/unlock)
2. 写端：创建新副本，原子替换指针，等待所有读者离开(宽限期)
3. 回收：宽限期结束后安全释放旧数据
```

### 思想共鸣

| | OCC | RCU |
|--|-----|-----|
| 读端 | 不加锁 | 不加锁 |
| 写端 | 验证+可能回滚 | 延迟回收 |
| 冲突处理 | 回滚重试 | 等待宽限期 |
| 适用场景 | 读多写少 | 读多写少 |
| 代价 | 在写端(回滚) | 在写端(延迟+内存) |

两者的共同哲学：**读多写少场景的最优策略是让读端零开销，代价全部由写端承担**。

### MVCC与RCU的类比

MVCC(Multi-Version Concurrency Control)保留数据的多个版本——读操作访问旧版本快照，写操作创建新版本：

```
MVCC：  旧版本保留直到无活跃事务引用 → 类似RCU的延迟回收
        快照可见性判断(事务ID比较)  → 类似RCU的宽限期检查
```

PostgreSQL的MVCC实现：每个元组头有xmin/xmax事务ID——读取时根据快照可见性判断看到哪个版本。VACUUM清理无事务引用的旧版本——类似RCU的宽限期后回收。

## 30.2 Latch耦合与读写信号量

### 数据库中的latch

latch是数据库中的短持锁——保护内存数据结构的物理一致性：

- **Buffer Pool hash table latch**：查找缓冲页时持latch——保护hash table的并发访问
- **B+树latch coupling**：遍历B+树时逐层获取/释放latch——防止树结构被并发修改

latch的特点：持锁时间短(微秒级)、不参与死锁检测、不允许等待时睡眠。

### 内核读写信号量

`kernel/locking/rwsem.c`实现读写信号量——读者并发、写者独占：

```
rwsem_down_read() → 多个读者可同时持有
rwsem_down_write() → 写者独占，等待所有读者退出
```

rwsem的乐观自旋：写者等待时先自旋——读者通常很快释放。自旋失败后才睡眠。

### 映射

| 数据库latch | 内核同步原语 |
|-------------|-------------|
| 共享latch(读) | rwsem_down_read() |
| 独占latch(写) | rwsem_down_write() |
| try-latch | rwsem_trylock() |
| latch coupling | RCU读端遍历(更轻量) |

**latch coupling与RCU的类比**：B+树的latch coupling逐层获取/释放latch——如果改为RCU保护树遍历，读端完全无锁，只在写端(分裂/合并)时等待宽限期。但这增加了写端延迟——latch coupling在写端更快(微秒级vs毫秒级宽限期)。

## 30.3 事务锁管理器与futex

### 数据库事务锁

事务锁保护逻辑一致性——持锁时间长(整个事务期间)：

- **行锁**：锁定特定行——防止两个事务同时修改同一行
- **表锁**：锁定整张表——DDL操作
- **意向锁**：表示"打算在更低层级加锁"——加速锁冲突检测

事务锁管理器维护锁等待图——检测死锁(超时或主动检测)。

### 映射到futex

| 数据库锁 | 内核futex |
|---------|----------|
| 行锁等待 | FUTEX_WAIT |
| 行锁释放/唤醒 | FUTEX_WAKE |
| 条件变量通知 | FUTEX_REQUEUE |
| 死锁检测 | lockdep |
| 优先级继承 | PI futex |

数据库锁管理器与futex的关键区别：
- **粒度**：futex基于用户态地址——每个int变量一个等待点；数据库锁基于(表ID, 行ID)——逻辑标识
- **持久性**：futex随进程消失；数据库锁可能需要持久化(分布式锁)
- **死锁检测**：lockdep只检测内核锁；数据库需要自己的死锁检测(基于等待图)

## 30.4 无锁数据结构在引擎中的实践

### MCS锁与公平排队

`kernel/locking/mcs_spinlock.h`的MCS锁思想——每个等待者在自己的本地变量上自旋，避免总线风暴：

```
传统自旋锁：所有CPU在同一变量上spin → 总线风暴
MCS锁：     每个CPU在自己的节点上spin → 无总线竞争
```

数据库可以借鉴MCS锁——在多线程Hash Join的构建阶段，如果使用自旋锁保护Hash表，MCS锁比传统spinlock在30+线程时性能好数倍。

### 无锁队列

内核的`include/linux/llist.h`实现单生产者-单消费者的无锁链表——基于CAS操作：

```c
llist_add(new, head)  → CAS(head->first, old, new)
llist_del_first(head) → CAS(head->first, old, old->next)
```

数据库的WAL写入可以使用无锁队列——多个事务并发写入WAL记录，单个刷盘线程消费。类似内核的per-CPU缓冲+批量提交模式。

### 原子操作的正确使用

```c
// 编译器屏障：防止编译器重排
READ_ONCE(x) / WRITE_ONCE(x, val)

// CPU屏障：防止CPU重排
smp_store_release(&flag, 1) / smp_load_acquire(&flag)

// 原子操作：提供全屏障
atomic_cmpxchg()/atomic_xchg()
```

数据库的无锁数据结构常见错误：使用了`READ_ONCE`但遗漏了`smp_store_release`——在ARM/RISC-V上，其他线程可能看到指针更新但数据尚未写入。必须遵循acquire/release语义——与内核RCU的`rcu_assign_pointer`/`rcu_dereference`相同。

> **数据库视角**：无锁B+树的挑战与进展。B+树的并发控制是数据库研究的热点——传统的latch coupling在高并发下成为瓶颈。无锁B+树(如Bw-Tree)使用CAS+分离链(delta chain)实现——修改不直接改节点，而是创建delta记录挂在节点上，类似RCU的"修改创建新版本"思想。但B+树的无锁化比链表/队列困难得多——树结构的分裂/合并涉及多个节点的原子更新。目前大多数生产数据库仍使用latch coupling——简单、正确、延迟可预测。

---

本章建立了数据库并发控制与内核同步的映射：OCC与RCU共享"读端零开销"的哲学，latch与读写信号量解决同类问题，事务锁管理器与futex实现类似的等待/唤醒模式，MCS锁和无锁队列可直接应用于存储引擎。理解映射关系后，数据库设计者可以从内核借鉴成熟的同步模式——内核开发者也可以从数据库的并发控制中获得新思路。
