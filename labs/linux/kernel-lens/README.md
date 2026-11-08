# kernel-lens：Linux 与容器观测学习台

基于 Rust 的 Linux 配置总览、实时监控与可选基准测试 TUI（Terminal User Interface，终端交互界面）。默认只读，基准测试需主动选择。把「当前看到了什么」
与「数据来自哪里、属于谁、能说明什么」放在同一屏，为学习 Linux 内核子系统提供入口。

环境：**Linux、Rust 1.94+、UTF-8 交互终端**；推荐 120×35 或更大。
使用 Ratatui 0.29 / Crossterm 0.28，依赖版本由 `Cargo.lock` 固定。
首次构建需下载 Cargo 依赖；缓存齐全后可加 `--offline`。
运行时无需 root、无需守护进程，不修改 sysctl、挂载、cgroup 或网络配置。
缺失、被权限限制或无法定位的数据会显示 `N/A`，选中该行可查看原因。

## 运行

```sh
# 在本实验目录内
cargo run --release --locked
cargo run --release --locked -- --interval-ms 500
cargo run --release --locked -- --summary

# 非交互观察：每行一个 JSON 快照；第二次采样开始才有速率
cargo run --locked -- --snapshot --samples 2 --interval-ms 1000

cargo fmt -- --check
cargo clippy --locked --all-targets -- -D warnings
cargo test --locked
```

也可以在 `labs/linux` 下使用 `make run_kernel_lens` 和 `make test_kernel_lens`。
本实验使用独立 Cargo 入口；上层 Makefile 仅做调度。
编译产物位于本实验 `target/`，由仓库根 `.gitignore` 忽略。
程序不会自动保存运行数据（文件基准的临时工作区除外，完成/取消后清理）；手动导出的快照可能包含主机名、接口名和 cgroup 路径，属于本地数据。

| 操作 | 按键 |
| --- | --- |
| 切换主题 | `1`–`9`、`Tab` / `Shift-Tab`、左右箭头 |
| 选指标、查看来源和解释 | 上下箭头、`j` / `k` |
| 展开指标完整值、范围和错误原因 | `Enter`；上下 / `PgUp` / `PgDn` 滚动，`Enter` / `Esc` 返回 |
| 翻十行 / 首尾 | `PgUp` / `PgDn`、`Home` / `End` |
| 按指标名或值筛选当前页 | `/`，输入后 `Enter`；`Esc` 清除 |
| 暂停 / 继续采样 | 空格；暂停时显示旧快照年龄 |
| 操作帮助 | `?` |
| 退出并恢复终端 | `q`、`Ctrl-C` |

## 总览与专项观察

| 页面 | 已实现 | 从观测继续学习 |
| --- | --- | --- |
| 机器总览（首页 / `1`） | 六块卡片：CPU/NUMA、内存与容器限制、网络、存储、系统环境、当前负载；`Enter` 展开全部指标及来源 | 型号、拓扑、CPU 许可和时间配额分别展示，避免把可见硬件当成全部可用资源 |
| 环境 / 容器 | 内核版本、uptime、进程 namespace 标识、CPU/节点许可、seccomp/capability、cgroup 成员关系 | namespace 决定可见资源，cgroup 决定资源约束；单个 namespace 编号不能证明容器身份 |
| CPU / 调度 | 每 CPU busy、上下文切换和创建任务速率、运行/阻塞任务、load、CPU PSI、cgroup 配额与限流 | busy、load、压力和限流是不同维度；计数不能代替调度等待时间分布 |
| NUMA | 节点 CPU 列表、距离矩阵、节点内存和分配计数、自动平衡开关、cgroup 节点许可 | NUMA（Non-Uniform Memory Access，非一致内存访问）的本地/远端分配与访问延迟不同 |
| 内存 | MemAvailable、缓存、swap、脏页、写回、透明大页策略、内存 PSI、cgroup 用量/限制/事件 | 系统可用内存与容器剩余额度可能完全不同；PSI（Pressure Stall Information）是任务停顿比例 |
| 网络 | 当前网络 namespace 内各接口 RX/TX 字节速率、累计错误/丢包、socket 汇总 | 接口吞吐、TCP 重传、RTT 与应用请求耗时需要分别测量 |
| 存储 | 可见块设备读写字节速率、IOPS、进行中请求、I/O PSI、cgroup I/O 计数 | 区分文件系统、页缓存、块层与设备；不要把分区和映射设备重复求和 |
| Benchmark（`9`） | 五类可选测试、每轮结果、median/min/max、运行前后负载、配置与编译模式 | 范围和工作集决定结果含义；不计算通用整机分数 |
| perf / BPF | perf 和 BPF 策略、BTF/tracefs 可见性、现有工具发现、后续命令 | 工具存在、内核提供接口、权限允许与实际采集成功是四件事 |

`scope` 列说明统计范围。`/proc/stat`、`/proc/meminfo`、`/proc/diskstats`、系统 PSI 和
NUMA 数据标为系统可见视图，**不能直接当成容器独立统计**；宿主环境也可能通过虚拟文件系统
改写这些文件。网络数据通常属于当前网络 namespace，`sockstat` 部分内存字段可能是内核全局。
未进入宿主机 namespace，也没有宿主机独立对照，因此不推断容器外的实际配置。

cgroup v1/v2 根据 `/proc/self/cgroup` 和 `/proc/self/mountinfo` 的挂载根映射定位，
不默认读取 `/sys/fs/cgroup` 根节点。不能映射到当前进程的可见子树时明确显示缺失。
v2 `cpu.max` 的 quota/period 可折算为配额核数；v1 `-1`、v2 `max` 表示该层不设限。
祖先 cgroup 仍可能限制资源；当前版本不遍历祖先，不声称计算了最终有效上限。
空的 v1 cpuset 可能从祖先继承；进程有效许可可在环境页查看。

## 架构与扩展边界

```text
/proc ── ProcCollector ──────┐
/sys  ── SysCollector ───────┤
cgroup ─ CgroupCollector ───┼─ Kernel.sample() ─ Snapshot v1 ─ TUI / JSON Lines
policy/PATH ─ Capability... ┘
```

- [model.rs](src/model.rs)：主题、观测值、单位、范围、来源、解释与状态；统一快照带时间、
  序号、采集耗时和 schema 版本。当前值是面向展示的文本，尚无数值查询/直方图协议。
- [collectors/mod.rs](src/collectors/mod.rs)：`Collector` 是实际使用的采集接口，五种采集器各自
  实现；配置总览来自 `InventoryCollector` 并复用已采集的 cgroup 限额与当前负载。`Kernel::register` 支持注册新采集器。采集器保存自身差分基线，界面不解析内核文件。
- `LinuxFs` 提供可替换的文件根与单文件 4 MiB 读取上限，用同一套解析逻辑处理真实文件和
  独立测试夹具。CLI 固定读取当前 Linux 环境，没有切换到宿主机的隐式行为。
- [procfs.rs](src/collectors/procfs.rs)：CPU、网络、块设备差分使用真实单调时间；首次采样、
  计数下降或无有效时间差时等待新基线。CPU 排除重复的 guest tick，busy 不含 idle/iowait。
- [cgroup.rs](src/collectors/cgroup.rs)：处理 v1/v2、组合控制器、挂载子树、路径转义和路径边界。
- [sysfs.rs](src/collectors/sysfs.rs)：NUMA 拓扑和能力线索；只发现 PATH 中的工具，不执行它们。
- [bench.rs](src/bench.rs)：固定工作负载、独立子进程、重复采样、结果与运行环境、取消/超时及临时工作区清理。
- [inventory.rs](src/collectors/inventory.rs)：系统/CPU 拓扑、缓存、频率策略、NUMA 许可、内存容量、网卡与块设备配置。
- [ui.rs](src/ui.rs)：仅消费快照，提供选中行解释、筛选、暂停和终端尺寸降级。
  `--snapshot` 复用同一采集链，便于无交互环境验证。

轮询在当前进程中同步执行：单文件大小有限，但文件系统异常时没有硬实时保证。
基准已放在独立子进程中并限制输出和执行窗口。后续引入慢速外部工具或事件采集时，同样需要单独工作线程/进程、有界通道和超时，
不把阻塞调用塞进绘制循环。现阶段不做通用插件加载器或特权代理。

### 复用 Linux 现有工具

每页给出下一步命令；在另一个终端运行，按本机版本与权限解释结果。
`vmstat`、`pidstat`、`iostat` 等输出适合人工交叉检查，核心采集优先使用稳定内核文件接口，
避免工具版本、语言和列宽变化影响解析。

| 目标 | 现有工具 | 能补充的证据 |
| --- | --- | --- |
| CPU 时间 / 事件 | `perf stat -e task-clock,context-switches -- sleep 1` | 当前测量进程的性能事件；权限不足应保留报错 |
| 调度 | `vmstat 1`、`pidstat -w 1`；后续 `perf sched` | 队列/切换概览；调度延迟需要事件时间线 |
| NUMA | `lscpu -e=CPU,NODE,SOCKET,CORE`、`numactl --hardware`、`numastat -p <PID>` | 拓扑、进程内存分布；`numastat` 不直接给远程访问延迟 |
| 网络 | `ip -s link`、`ss -s`、`nstat -az` | 接口和协议栈计数；不同 namespace 结果不可直接比较 |
| 块存储 | `iostat -dx 1`、`lsblk`、`findmnt` | 请求延迟/队列、块设备与挂载关系 |
| BPF 能力 | `bpftool feature probe unprivileged`、`bpftrace --info` | 当前调用者可探测的能力；不支持该选项的旧版本会报错 |

计时工具的第一行可能是自开机累计平均，比较时看后续采样。
当前程序**没有**执行 perf、加载 BPF、抓包或安装工具。

### 后续 BPF 路线

BPF（Berkeley Packet Filter，在内核中运行经验证程序的机制）接入按具体问题推进：

1. **调度等待**：通过 `sched_wakeup` / `sched_switch` 配对，按 PID/cgroup 过滤，
   输出运行队列等待时间分布；与当前 `ctxt/s` 和 CPU PSI 对照。
2. **块 I/O 延迟**：以块请求 issue/complete 时间配对，按设备聚合延迟；
   处理请求合并、重试、设备映射和内核事件格式差异。
3. **网络**：补充 TCP 重传和连接延迟，明确网络 namespace、采样对象与地址隐私边界。
4. 根据目标内核选择 Aya（Rust BPF）或 libbpf-rs；需要跨内核类型适配时再验证
   BTF（BPF Type Format，内核类型元数据）和 CO-RE（Compile Once, Run Everywhere）条件。

事件侧负责加载、attach、读取、聚合与退出时 detach；前台 `Collector` 仅取最近完成的聚合窗口。
保留窗口起止、过滤条件、样本数、ring buffer 丢失事件数和错误状态；权限不足不得自动提权或
悄悄退回不同统计范围。新增数值/直方图字段时升级快照 schema，同时适配 TUI 与 JSON 消费者。

这是一条待实现的路线：当前只验证了轮询接口和扩展入口，没有 BPF 程序或事件性能结论。

## 选择与运行基准测试

默认首页只观察，不自动运行测试。按 `9` 进入测试页，`↑↓` 选项目、空格勾选、`r` 依次运行、
`c` 取消整个批次；运行期间可以切回总览观察负载。`Enter` 查看所选项目的结果和环境详情，
`PgUp/PgDn` 滚动；未勾选的项目不执行。默认 250 ms/轮、3 轮、8 MiB 工作集。
内存测试会使用两个指定大小的缓冲区。测试期间其他负载和容器限流会影响结果。

| 项目 ID | 测量对象 | 结果含义 |
| --- | --- | --- |
| `cpu` | 单线程固定整数依赖链 | M iterations/s；不是通用 CPU 算力评分，不做全核压力测试 |
| `memory` | 一个线程拷贝预触页缓冲区 | GiB/s 按有效拷贝字节计，不把读写双倍流量重复计入；可能命中缓存 |
| `scheduler` | 两线程零容量 channel 请求/响应 | µs/roundtrip；每轮先求平均往返时间，再汇总各轮；不是唤醒延迟分布的 p50 |
| `tcp-loopback` | 本 namespace 的 127.0.0.1 临时端口 | GiB/s 按接收端实际收到的字节计；不测物理网卡/外部网络 |
| `file-io` | 指定目录中独占临时文件写入 + sync_data、随后读取 | MiB/s；固定大小、变动内容、顺序 I/O；读取允许页缓存，不测冷读/裸盘峰值 |

测试需使用 **release** 构建进行比较；报告会标明 debug/release、工作负载版本、工作集、
轮数、每轮值、median/min/max、测试时间、CPU/NUMA/容器配置、测试前后系统负载和 cgroup CPU 计数。
这些观测能帮助发现限流或共享负载变化，但不能单凭同时变化确定因果。
目前不固定 CPU 或 NUMA 节点，不提供跨 NUMA 访问带宽测试。

```sh
# 非交互方式：输出一个 JSON 报告，可自行重定向到仓库外的本地文件
cargo run --release --locked -- --benchmark cpu
cargo run --release --locked -- --benchmark memory --bench-size-mib 16 --bench-rounds 3
cargo run --release --locked -- --benchmark scheduler
cargo run --release --locked -- --benchmark tcp-loopback

# 文件测试必须显式选择已有目录；启动 TUI 只配置目录，不会自动测试
cargo run --release --locked -- --bench-dir /tmp
# 在确认该目录适合写入后，按需执行文件测试
cargo run --release --locked -- --benchmark file-io --bench-dir /tmp --bench-size-mib 8
```

范围限制：`--bench-duration-ms` 为 100–2000，`--bench-rounds` 为 1–7，
`--bench-size-mib` 为 1–64。文件测试按固定大小读写一次/轮，不使用 duration 参数。
文件系统压缩、虚拟化、overlay、tmpfs、远端存储及设备缓存都会影响文件结果。
指定目录可能与根文件系统不同；文件报告额外通过 statfs 记录实际目录的文件系统类型，不能只看根文件系统配置。

每项测试运行在独立的本程序子进程中，输出有大小限制，30 秒后请求终止；
取消和正常退出会终止并回收该子进程。Linux 的父进程死亡信号用于防止父进程异常退出后继续运行测试。
不可中断内核 I/O 不保证即时停止。文件测试只在指定目录下创建本次私有工作区，
正常完成或取消后，核对目录身份与本次进程文件名再清理，保留未知内容并报告失败。
机器掉电或父进程被强制杀死可能留下 `.kernel-lens-run-*` 工作区，不做全目录自动扫描清理。

## 一个最小学习闭环

1. 启动 TUI，先看进程允许的 CPU/NUMA 节点和 cgroup 上限，再看 CPU 页的系统范围。
2. 在另一个终端运行五秒的单进程 CPU 活动：

   ```sh
   timeout 5s python3 -c 'import time; end=time.monotonic()+5; x=1
   while time.monotonic()<end: x=(x*1664525+1013904223)&0xffffffff'
   ```

3. 对照每 CPU busy、load、cgroup `cpu.stat` 累计用量增量。单任务可能跨 CPU 迁移；
   系统范围还有其他任务，因此不能把全部变化归因于这个实验。
4. 若本机允许，再用 `perf stat` 包住同一命令，观察 task-clock 和 context-switches。
   成功得到事件计数后再进入采样、符号、调用栈与调度跟踪。
5. 网络/存储先观察已有流量，再用各页列出的工具交叉核对；不要为了让图表变化直接压测共享磁盘。

## 验证范围

`cargo test` 还通过短时独立子进程执行 CPU、内存、线程往返、TCP 回环和 1 MiB 文件测试，检查报告结构、参数拒绝、保留无关文件及清理；配置夹具验证系统容量与容器上限分离。

原有测试覆盖计数重置/首次采样、guest tick、cgroup v1/v2 子树与转义、路径越界拒绝、
缺失数据、文件读取大小限制、快照序列化，以及九页在大/小终端尺寸的渲染。
这些是解析和界面测试；真实容器上的 JSON 采样与终端交互验证应另行记录，
它们不证明其他发行版、宿主机视角或 perf/BPF 事件采集已通过。

公开接口参考：
[procfs](https://docs.kernel.org/filesystems/proc.html)、
[cgroup v2](https://docs.kernel.org/admin-guide/cgroup-v2.html)、
[PSI](https://docs.kernel.org/accounting/psi.html)、
[块层统计](https://docs.kernel.org/admin-guide/iostats.html)、
[BPF](https://docs.kernel.org/bpf/)。
