# Linux —— 内核机制的用户态实验

把内核里某个子系统压缩成几十到几百行用户态代码，观察它的行为边界。
这里的实验都不需要编译内核、不进 QEMU（Quick EMUlator，快速模拟器）、不需要 root，
只依赖 libc / pthread 与 `/proc`。

| 子目录 | 主题 | 入口 |
| --- | --- | --- |
| `pagetable/` | 虚拟内存：延迟缺页、RSS（Resident Set Size，常驻内存集）、页表遍历、TLB（Translation Lookaside Buffer，地址转换旁路缓冲） | `l_page1.cc`、`l_page2.cc`、`l_pagetable.cc`、`l_tlb1.cc` |
| `rcu/` | RCU（Read-Copy-Update，读-复制-更新）宽限期、强制静止状态、stall 检测 | [rcu/README.md](rcu/README.md)、`rcu_lab.c` |

## 构建与运行

```sh
cd labs/linux
make            # 编译全部实验，产物在 bin/
make pagetable  # 只编页表 / TLB 实验
make rcu        # 只编 RCU 实验
make run_rcu    # 编译并运行 RCU 的三个场景
make clean
```

单独跑某个实验：

```sh
./bin/l_page1
./bin/l_pagetable
./bin/l_tlb1                              # 计数看输出，缺失看 perf
perf stat -e dTLB-load-misses,cycles ./bin/l_tlb1
```

产物统一落在 `bin/`（已由本目录 `.gitignore` 忽略），不要把二进制提交进来。

## 阅读顺序

1. `pagetable/l_page1.cc`：`malloc(1)` 的 usable 为什么是 24 字节；分配不等于占物理页。
2. `pagetable/l_page2.cc`：写入才触发缺页；`madvise(MADV_DONTNEED)` 与 `mlock` 的差别。
3. `pagetable/l_pagetable.cc`：4 级 / 5 级页表 + LRU TLB 模拟器，看多级页表为什么省内存。
4. `pagetable/l_tlb1.cc`：stride 从 64 B 走到 2 MB 时 TLB 缺失如何变化（需 `perf`）。
5. `rcu/README.md`：从 `rcu_gp_init()` 的 `qsmask` 位图到 stall 报告权，逐行对照 Linux 7.0.0。

## 约定

- 文件名沿用历史前缀 `l_`（linux lab）；`pagetable/` 下是 C 风格代码，统一用
  `g++ -std=c++17` 编译，因此文件后缀是 `.cc` 而不是 `.c`。
- 与内核逐条对照的说明写在各子目录 README 里，附 `文件:行号` 和内核版本基线；
  改动实验逻辑时要同步核对，不要让注释里的行号悄悄失效。
- 构建选项沿用 `cc/algo` 的调试口径（`-O0 -g -fno-omit-frame-pointer`）。
  需要额外告警时显式传入，例如 `make CXXFLAGS='-std=c++17 -O2 -Wall -Wextra'`。
