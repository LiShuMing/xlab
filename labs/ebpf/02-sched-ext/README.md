# 02 — Linux 7.0 `sched_ext` 极简调度器（Global FIFO + Priority DSQ）

## 前置条件

- Linux 6.12+ 且启用 `CONFIG_SCHED_CLASS_EXT`（已验证：Linux 7.0.0-38，`/sys/kernel/sched_ext/state` 就绪）
- `clang`、`llvm`、`bpftool`、`libbpf-dev`、`libelf-dev`、`zlib1g-dev`、`gcc`、`sudo`

## 设计说明

- **`scx_prio_fifo.bpf.c`**：约 160 行 `struct_ops` 调度器，创建两个自定义 Dispatch Queue：
  - `DSQ_HIGH (id=1)`：面向指定 `--pid`（TGID）以及短突发任务（经 `BPF_MAP_TYPE_TASK_STORAGE` 记录上一次 on-CPU 运行时长 `< short_task_ns`）的高优队列；指定 PID 唤醒时调用 `scx_bpf_kick_cpu(0, SCX_KICK_PREEMPT)` 立即抢占后台计算任务。
  - `DSQ_NORMAL (id=2)`：其余 CPU 密集型任务的全局 FIFO 队列（时间片 20 ms）。
  - 安全网：设置 `.timeout_ms = 5000`，调度器若异常卡顿，内核 watchdog 会自动卸载并切回默认 EEVDF。
- **`scx_prio_fifo.c`**：libbpf skeleton 用户态加载器，配置 `rodata` 参数并实时输出 `local/high/normal/preempt_kicks` 计数。
- **`cpu_compete.c` & `run_bench.sh`**：在 2 核机器上启动 4 个满载 CPU hog + 1 个周期唤醒探测任务，对比默认 EEVDF、纯 Global FIFO 与 Priority DSQ 三种调度策略的唤醒延迟（p50/p95/p99/max）。

## 构建与运行

```sh
make all
./run_bench.sh
```
