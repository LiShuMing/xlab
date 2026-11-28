# 01 — bpftrace 对照实验：Page Cache 预读与 Futex 两段锁延迟

## 前置条件

- Linux（已验证：Linux 7.0.0-38, x86_64）
- `bpftrace >= 0.20`、`gcc`、`sudo`
- 实验 1A 的测试文件需位于块设备文件系统（默认 `/var/tmp`，ext4/xfs），不要放在 `tmpfs`（如 `/tmp`），否则 `drop_caches` 与 `block:block_rq_*` 不会触发。

## 实验内容

### 1A. Page Cache 命中与预读行为
- 负载：`pagecache_bench.c`（对 16 MiB 文件执行 4096 次 4 KiB `pread`，提供 5 种模式：`seq`、`rand`、`fadv_rand`、`fadv_will`、`warm`）。
- 探针：`pagecache.bt` 挂载 `tracepoint:filemap:mm_filemap_add_to_page_cache` 与 `tracepoint:block:block_rq_issue/complete`，观测 folio order 分布、缓存插入次数、块层请求大小直方图与 I/O 延迟直方图。

### 1B. Futex 锁竞争的「两段延迟」拆解
- 负载：`futex_bench.c`（4 线程抢同一把 `pthread_mutex_t`，可配锁内耗时 `hold_us` 与锁外 CPU 计算 `work_us`）。
- 探针：`futex_latency.bt` 同时挂 `syscalls:sys_enter_futex`、`sched:sched_wakeup`、`sched:sched_switch`、`syscalls:sys_exit_futex`，将总等待拆成：
  1. **Stage 1（等持锁者释放）**：`sys_enter_futex(WAIT)` → `sched_wakeup`
  2. **Stage 2（唤醒后在 runqueue 排队上 CPU）**：`sched_wakeup` → `sched_switch(next_pid)`

## 构建与运行

```sh
make all
./run_all.sh
```
