# rcu —— 用线程模拟 RCU 宽限期的三个关键机制

所属目录：[labs/linux](../README.md)，构建入口是上级目录的 `Makefile`。

内核基线：Linux **7.0.0**，`1d51b370a0f8`（`~/xwork/linux`）。下面每个 `文件:行号` 都在该树上回查过。

这个目录回答一个问题：

> 宽限期要等"每个 CPU 都上报过一次静止状态"，可静止状态是各 CPU 自己悄悄记的 ——
> kthread 到底怎么知道的？如果某个 CPU 一直不上报，谁会先发现、靠什么发现？

先说结论，再看代码：

1. **kthread 不是被"通知"的，它是去读位图的。** 宽限期开始时 `rcu_gp_init()`
   （`kernel/rcu/tree.c:1804`）把每层 `rcu_node` 的 `qsmask` 置成"所有在线 CPU 的位"
   （`:1959`）。某个 CPU 过了静止状态，就由它自己清掉自己那一位：
   `rcu_report_qs_rdp()`（`:2443`）→ `rcu_report_qs_rnp()`（`:2339`）逐层向上合并，
   直到根节点 `qsmask` 变 0。
2. **kthread 靠超时醒来 + 看根节点位图**：`rcu_gp_fqs_loop()`（`:2064`）里
   `swait_event_idle_timeout_exclusive()`（`:2095`）带超时地睡，醒来就检查
   `rnp->qsmask`。所以它不是被动等待，也不是靠消息，而是"定时看一眼台账"。
3. **一直不上报的 CPU，kthread 先自己兜底**：每一轮 `rcu_gp_fqs()`（`:2028`）→
   `force_qs_rnp()`（`:2732`）按位扫描，对仍挂着的 CPU 调
   `rcu_watching_snap_recheck()`（`kernel/rcu/tree.c:855`）：
   - 头 1 个 `jiffies_to_sched_qs` 后置 `rdp->rcu_urgent_qs`，该 CPU 下一拍时钟中断就
     `set_need_resched_current()`（`:2712`）；
   - 宽限期过半（`rcu_state.jiffies_resched`）之后返回 `-1`，外层
     `force_qs_rnp()` 统一跑 `resched_cpu(cpu)`（`:2783` → `kernel/sched/core.c:1243`），
     发重调度 IPI 把它踹进调度器，`rcu_note_context_switch()`
     （`kernel/rcu/tree_plugin.h:324`）顺手记一次 QS。
4. **真发现不了的时候，发现者是「别的 CPU 的时钟 tick」，不是 kthread**：
   `rcu_pending()`（`tree.c:3670`）每次 tick 都调 `check_cpu_stall()`
   （`kernel/rcu/tree_stall.h:772`）。当 `jiffies >= rcu_state.jiffies_stall` 时，
   谁先跑到这里谁用一次 `cmpxchg`（`tree_stall.h:835`）抢到"报告权"：
   - 自己的位还挂着 → `print_cpu_stall()`（`:709`）：**自己打自己的栈**；
   - 否则 → `print_other_cpu_stall()`：打出还挂着的 CPU（`print_cpu_stall_info()` `:518`）
     并让它们抓栈。

   打印出来就是 `INFO: rcu detected stalls on CPUs/tasks:`（`tree_stall.h:656`）。
   期限由 `rcu_jiffies_till_stall_check()`（`tree_stall.h:111`，下限 3s、默认 21s、
   上限 300s）算出，宽限期开始时由 `record_gp_stall_check_time()`
   （`tree_stall.h:199`）写进 `rcu_state.jiffies_stall`，同时把
   `jiffies_resched` 设为它的一半。

一句话边界：**如果那个 CPU 连中断都进不去（IRQs 关死、真硬锁死），它自己永远不会发现**；
是别的 CPU 在自己的 tick 上发现的，栈要靠 NMI 去抓。如果**所有** CPU 都卡死，就没人报——
那已经属于 hard lockup（NMI watchdog）的地盘。

## 目录结构

```
labs/linux/
├── Makefile
├── README.md
├── pagetable/          # 缺页 / 页表 / TLB 实验
├── rcu/
│   ├── rcu_lab.c       # 全部逻辑，约 330 行，单文件
│   └── README.md       # 本文件
└── bin/                # 构建产物，不入库
```

构建与运行：

```sh
make -C labs/linux rcu      # 编译到 labs/linux/bin/rcu_lab
./labs/linux/bin/rcu_lab    # 三个场景全跑
```

也可以进目录后 `cd labs/linux && make run_rcu`。

## 用户态元素 ↔ 内核元素

| 本 demo | 内核对应 |
| --- | --- |
| 一个 `pthread` = 一个 CPU | 每个 CPU 一个 `struct rcu_data` |
| `cpus[i].qs_seq`（"我报到第几个 GP 了"） | `rcu_data.gp_seq` + `rcu_node.qsmask` 里的那一位 |
| 读线程 `rcu_read_unlock()` 里顺手自报 | `rcu_qs()`（`tree_plugin.h:298`）→ `rcu_report_qs_rdp()`（`tree.c:2443`） |
| `gp_round()` 每 20 ms 扫一遍位图 | `rcu_gp_fqs_loop()`（`tree.c:2064`）超时醒来后的那轮扫描 |
| `pthread_sigqueue(SIGRTMIN)` | `resched_cpu()`（`tree.c:2783` → `sched/core.c:1243`） |
| 读线程里 `SIG_BLOCK` 掉 SIGRTMIN | 关中断 / 屏蔽 IPI 的内核死循环 |
| `maybe_check_stall()` 在健康 CPU 的循环里 | `rcu_pending()` → `check_cpu_stall()`（`tree.c:3679` / `tree_stall.h:772`） |
| `g_stall_claimed` 的 CAS | `check_cpu_stall()` 里对 `jiffies_stall` 的 `cmpxchg`（`tree_stall.h:835`） |
| `stall_ms` | `rcu_jiffies_till_stall_check()` 换算出来的 stall 期限 |

场景设计（`main()` 里三个）：

- **A**：两个普通 CPU，`rcu_read_unlock()` 时自报 → 宽限期 50 ms 结束，`forced=0`。
- **B**：`cpu2` 在无 QS 点的长循环里，但信号能到 → 被强制 QS，`forced=1`。
- **C**：`cpu3` 屏蔽了 SIGRTMIN（等价于关中断）→ 强制无效，最后由 **cpu0 的 tick**
  抢到报告权并打印 `INFO: rcu_lab detected stall on cpu3`。

## 实跑输出

```
[rcu_lab      0ms] scenario A: two ordinary CPUs that report on their own
[rcu_lab     20ms] g=1 GP start (bits set for all 2 CPUs, stall deadline 500 ms)
[rcu_lab     23ms]   cpu0: self-reported QS at g=1
[rcu_lab     27ms]   cpu1: self-reported QS at g=1
[rcu_lab     70ms] g=1 GP end (50 ms, forced=0)
[rcu_lab     90ms] g=2 GP start (bits set for all 2 CPUs, stall deadline 500 ms)
[rcu_lab     92ms]   cpu1: self-reported QS at g=2
[rcu_lab     95ms]   cpu0: self-reported QS at g=2
[rcu_lab    140ms] g=2 GP end (50 ms, forced=0)
[rcu_lab    140ms] A done: forced=0 stalled=0
[rcu_lab    140ms] scenario B: cpu2 spins in a QS-less loop, but signals reach it
[rcu_lab    140ms] g=3 GP start (bits set for all 3 CPUs, stall deadline 500 ms)
[rcu_lab    141ms]   cpu1: self-reported QS at g=3
[rcu_lab    144ms]   cpu0: self-reported QS at g=3
[rcu_lab    190ms]   cpu2: still in qsmask -> force QS (resched IPI analogue)
[rcu_lab    210ms] g=3 GP end (70 ms, forced=1)
[rcu_lab    210ms] B done: forced=1 stalled=0
[rcu_lab    210ms] scenario C: cpu3 spins with IRQs masked -> nobody can force it
[rcu_lab    211ms] g=4 GP start (bits set for all 4 CPUs, stall deadline 500 ms)
[rcu_lab    214ms]   cpu1: self-reported QS at g=4
[rcu_lab    215ms]   cpu0: self-reported QS at g=4
[rcu_lab    261ms]   cpu2: still in qsmask -> force QS (resched IPI analogue)
[rcu_lab    461ms]   cpu3: still in qsmask -> force QS (resched IPI analogue)
[rcu_lab    662ms]   cpu3: still in qsmask -> force QS (resched IPI analogue)
[rcu_lab    711ms]   tick on cpu0: jiffies >= jiffies_stall -> check_cpu_stall() claims the report (self_detected=0)
[rcu_lab    711ms] INFO: rcu_lab detected stall on cpu3 (g=4, 500 ms into GP, in_read=0, irqs_masked=1)
[rcu_lab    722ms] g=4 still waiting after 511 ms (forced=25): the real GP kthread does NOT stop on a stall -- it keeps forcing until the CPU checks in or someone fixes it
[rcu_lab    722ms] C done: forced=25 stalled=1 (this is what 'INFO: rcu detected stalls' means)
```

注意 C 里的两行顺序：**先**是 `tick on cpu0 ... self_detected=0`（健康 CPU 的 tick 抢到
报告权），**然后**才打印还挂着的 `cpu3`。kthread 自始至终没有报过警。

## 与真实内核的差异（别把 demo 当模型用）

- `qsmask` 在内核里是 `rcu_node` 树的位图，逐层向上合并；demo 只有一层、一个数组。
- 真实 GP 还要等 `blkd_tasks` 排空（阻塞在 read-side 里的任务），demo 没有任务概念，
  只有"在不在临界区"。
- 真实 `resched_cpu()` 是打断内核态执行、逼它进调度器；`SIGRTMIN` 打断的是用户态线程。
- demo 的 GP 线程在检到 stall 后退出循环；真实 `rcu_gp_kthread()`（`tree.c:2271`）
  不会因为 stall 退出，它会一直循环。
- 时间单位：内核是 jiffies + `HZ` 换算，demo 直接是毫秒。
- 真实内核里这个函数在 7.0 已经改名：老代码里的 `rcu_implicit_dynticks_qs()`
  被拆成了 `rcu_watching_snap_save()`（`:819`，GP 开始时拍快照）和
  `rcu_watching_snap_recheck()`（`:855`，每轮复查）。照 6.x 的文章找函数名会对不上。

## 可以接着玩

- 把 `stall_ms` 调到 3000，看 "sched_resched 频率随宽限期过半而提高" 那段（demo 里是
  200 ms 的日志节流；内核对应 `rdp->last_fqs_resched + jtsq` 的双速率）。
- 给 `BUSY_UNMASKED` 的 CPU 加一个 `cond_resched()` 等价物（每 N 次循环检查一次
  `g_stop` 并主动报 QS），验证"只要代码里有 QS 点就不会 stall"。
- 让两个线程同时抢 `g_stall_claimed`，观察 `cmpxchg` 只有一个赢家。
