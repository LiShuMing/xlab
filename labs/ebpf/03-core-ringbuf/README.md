# 03 — `libbpf + CO-RE + RingBuffer` 小工具与 BPF Verifier 拒绝案例集

## 前置条件

- Linux 5.8+ 且开启 BTF（`/sys/kernel/btf/vmlinux`，已验证：Linux 7.0.0-38）
- `clang`、`bpftool`、`libbpf-dev`、`libelf-dev`、`zlib1g-dev`、`gcc`、`python3`、`sudo`

## 实验内容

### 3A. CO-RE + BPF RingBuffer 追踪器（`exec_rw_trace`）
走完现代 eBPF 标准工程闭环：`bpftool btf dump` 生成 `vmlinux.h` → `clang -target bpf` 编译 → `bpftool gen skeleton` 生成骨架头文件 → 用户态加载并消费 `BPF_MAP_TYPE_RINGBUF`：
- 追踪短命进程完整生命周期（`sched_process_exec` → `sched_process_exit`），输出 `pid/ppid/comm/file/exit_code/life_ms`。
- 按 `--pid` 追踪目标进程 `read/write` 系统调用，同时经 RingBuffer 流式上报事件并在内核 `BPF_MAP_TYPE_ARRAY` 中维护 log2 延迟直方图。

### 3B. BPF Verifier 经典拒绝案例集（`verifier_cases/`）
三组「故意触发 Verifier 拒绝 (`*_bad.bpf.c`) + 修复版 (`*_fixed.bpf.c`)」对照，通过 `bpftool prog load` 真实抓取内核 Verifier 日志：
1. **Case 1**：`BPF_MAP_TYPE_HASH` 查找结果未判空直接解引用（`map_value_or_null`）。*注：现代内核对常量合法下标的 `ARRAY` map 可证明非空，因此演示需用 `HASH` map。*
2. **Case 2**：循环上界来自 map 运行时动态值、无法证明终止（超出指令限制/无法证明有界），修复后通过显式上界截断通过验证。
3. **Case 3**：XDP 读取以太网头前未校验 `data + sizeof(*eth) > data_end`（越界包访问）。

## 构建与运行

```sh
make all
./run_demo.sh
# 单独运行 Verifier 案例集：
make verifier
```
