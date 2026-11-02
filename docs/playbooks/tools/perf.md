# Perf

Linux 上性能分析的默认入口。有效的顺序是**先定性、再定位、最后落到指令**：

1. `perf stat` —— 判断瓶颈类别（CPU 密集 / cache 未命中 / 分支预测 / 等锁等 IO）；
2. `perf record` —— 采样定位到具体函数；
3. `perf annotate` —— 落到具体指令。

跳过第 1 步直接抓火焰图，通常只能得到"CPU 很忙"这种无法行动的结论。

```bash
perf top                                    # 实时看当前热点，不必先落盘
perf script                                 # perf.data 转成文本栈
perf report                                 # 交互浏览：+/- 展开，a 进 annotate，/ 搜索
perf annotate                               # 指令级热点，要求二进制带符号
```

## 0. 前置：权限与符号

```bash
# 默认值 2：非 root 只能采到用户态栈，内核部分是空白
cat /proc/sys/kernel/perf_event_paranoid
sudo sysctl -w kernel.perf_event_paranoid=-1

# 栈帧显示 [unknown]：地址被隐藏或符号缺失
sudo sysctl -w kernel.kptr_restrict=0
```

容器内采集需要 `--privileged` 或 `CAP_PERFMON`，且默认只看到本 PID 命名空间
内的进程；要观察宿主进程需共享 host PID namespace。

## 1. 先定性：perf stat

不做采样，只读 PMU 计数器，开销极小。

```bash
perf stat -e cycles,instructions,cache-references,cache-misses,\
branches,branch-misses,task-clock ./prog
```

读输出先看两个导出指标：

| 指标 | 含义 | 判读 |
| --- | --- | --- |
| `insn per cycle` | IPC = instructions / cycles | < 1 说明大量周期耗在等待，往 memory stall 查 |
| `branch-misses` 的百分比 | 分支预测失败率 | > 5% 时考虑消除不可预测分支 |

`task-clock` 与 wall time 的比值决定是不是 CPU-bound：比值远小于 1 说明大量
时间在阻塞，应直接看第 6 节的 off-CPU，此时抓 on-CPU 火焰图没有意义。

## 2. 再定位：perf record

```bash
sudo perf record -F 999 -g -p <pid> -- sleep 20      # 单进程
sudo perf record -F 999 -ag -o sys.data -- sleep 20  # 全系统（-a 含内核与其他进程）
sudo perf record -F 999 -g -o run.data -- ./prog     # 直接拉起被测程序
```

| 参数 | 取值 | 说明 |
| --- | --- | --- |
| `-F` | 99 / 999 / 4000 | 采样频率。用 999 而非 1000，避免与内核时钟中断同频锁相产生系统性偏差 |
| `-g` | `fp` / `dwarf,8192` / `lbr` | `fp` 开销最小但要求 `-fno-omit-frame-pointer`；`-O2` 默认省略帧指针，此时拿到的是断栈 |
| `-e` | `cycles`（默认）/ `cache-misses` / `sched:sched_switch` | 想证明某类事件是瓶颈就直接采它 |
| `-m` | 页数 | 默认 ring buffer 偏小，出现 `Lost N events` 时加大 |
| `-o` | 文件名 | 默认写 `perf.data`，多次采集必须显式区分，否则互相覆盖 |

`dwarf` 需要沿 DWARF 信息 unwind，会复制用户栈（默认 8192 字节/样本），开销
显著高于 `fp`，只在 `fp` 栈明显断裂时使用。

## 3. 分析：report 与 annotate

```bash
perf report -i run.data                       # 平铺视图
perf report -i run.data --hierarchy           # 层级视图，从外层函数逐层下钻
perf report -i run.data --sort dso,symbol     # 按模块聚合，先确认是哪个 so
perf annotate -i run.data -s <symbol>         # 指令级，需带调试信息
```

`--hierarchy` 是自顶向下读的首选：先看根节点哪个子调用占了大部分，再逐层
展开，避免在平铺视图里被叶子函数的高占比误导。

## 4. 火焰图（on-CPU）

```bash
git clone --depth 1 https://github.com/brendangregg/FlameGraph
sudo perf script -i run.data | ./FlameGraph/stackcollapse-perf.pl | \
  ./FlameGraph/flamegraph.pl --title "on-CPU" > oncpu.svg
```

读图规则：横轴是采样占比（**宽度代表耗时，不是时间先后**），纵轴是调用深度。
找"宽而平"的塔——那才是真正吃掉时间的路径；矮而宽的 `[unknown]` 帧是符号
缺失，先回去修第 0 节的问题。

## 5. 差分火焰图

用于回答"这次改动前后，时间挪到哪去了"。两次采集、两次折叠、做差。

```bash
# 基线：改动前的版本
sudo perf record -F 999 -g -o base.data -- sleep 20
perf script -i base.data > base.stacks
./FlameGraph/stackcollapse-perf.pl base.stacks > base.folded

# 新版本：结构与上面完全一致，只换输出名
sudo perf record -F 999 -g -o new.data -- sleep 20
perf script -i new.data > new.stacks
./FlameGraph/stackcollapse-perf.pl new.stacks > new.folded

# 做差并出图（两个 folded 参数缺一不可，顺序即语义）
./FlameGraph/difffolded.pl -n base.folded new.folded | \
  ./FlameGraph/flamegraph.pl > diff.svg
```

解读（语义由两个脚本的源码确定，不是惯例）：

- **参数顺序是基线在前、新采样在后**；`difffolded.pl` 输出三列
  `栈 基线计数 新计数`。
- **红色 = 新比基线多**（回归），**蓝色 = 新比基线少**（被优化掉的路径）。
- **帧宽取自第二个文件**（新采样）的计数，所以这张图回答的是"现在的时间
  花在哪"。
- `-n` 归一化两次采样的总样本数。两次 `sleep` 时长不完全相同、或丢样数量
  不同时**必须**加，否则宽度差异里混进了总量差，整张图失真。
- `-s` 剥离输出里的十六进制地址。符号解析失败时栈帧是 `0x7f...`，ASLR 让
  每次运行都不同，不剥离会被拆成一堆互不相干的栈。

只想证明"优化掉了什么"时反过来写，并翻转配色：

```bash
./FlameGraph/difffolded.pl -n new.folded base.folded | \
  ./FlameGraph/flamegraph.pl --negate > diff_removed.svg
```

## 6. off-CPU：采样不到的时间

on-CPU 火焰图只覆盖 CPU 正在执行的时间。锁等待、page fault、IO 阻塞时线程
是睡着的，采样器根本不会落脚——这类问题表现为 wall time 远大于 CPU time
（回到第 1 节的 `task-clock` 比值）。

```bash
# 追踪上下文切换点，看线程究竟阻塞在哪个调用栈上
sudo perf record -e sched:sched_switch -ag -o offcpu.data -- sleep 20
perf script -i offcpu.data | ./FlameGraph/stackcollapse-perf.pl | \
  ./FlameGraph/flamegraph.pl --title "off-CPU" > offcpu.svg

# 或用 bcc（自带时长聚合，输出直接就是折叠格式）
/usr/share/bcc/tools/offcputime -df -p <pid> 20 > offcpu.folded
```

## 7. 常见坑

- **`[unknown]` 占满图**：二进制被 strip、缺调试信息，或内核符号受限。先按
  第 0 节放开 `kptr_restrict`，再确认二进制未 strip。
- **`fp` 栈断裂**：`-O2` 默认 `-fomit-frame-pointer`，`-g` 采到的栈只剩一两层。
  改用 `--call-graph dwarf`，或给被测程序加 `-fno-omit-frame-pointer`。
- **`Lost N events`**：采样频率过高或 ring buffer 太小，样本被丢弃，占比统计
  随之失真。降低 `-F` 或用 `-m` 加大缓冲后重采。
- **采样频率不是越高越好**：`-F` 拉到 10000 以上会产生 skid（采样点漂移），
  热点分布反而更模糊，同时显著拖慢被测程序。
- **用 `strace` 套 `perf` 没有价值**：`perf script` 的开销在解析符号和栈，不在
  syscall。要看系统调用直接 `perf trace -p <pid>`，开销比 `strace` 低一个量级。
- **JIT 代码无符号**：Java/Python/Lua 生成的代码落在匿名内存，栈里全是地址。
  JVM 需 `-XX:+PreserveFramePointer` 并配合 `perf-map-agent`。

## 8. 补充工具

| 场景 | 工具 |
| --- | --- |
| 实时热点 | `perf top` |
| 系统调用追踪 | `perf trace`（替代 strace） |
| 调度延迟、锁竞争 | `/usr/share/bcc/tools/offcputime`、`runqlat` |
| 单函数耗时分布 | `bpftrace -e 'kprobe:<func> { @[ustack] = count(); }'` |
| 消除测量噪声 | `perf stat -r 5`（重复 5 次，输出 min/mean/stddev） |
