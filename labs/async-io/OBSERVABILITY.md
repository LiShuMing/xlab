# async-io：本机构建与可观测性报告

2026-11-08 补充：已在 Linux 编译运行 `kqueue-compat`，见
[三后端兼容层补测](#linux-kqueue-compat)。它不是 macOS/BSD 原生 kqueue；下文原有双后端
5 轮测量作为独立历史数据保留，不与本次 3 轮数据合并。

两个项目现在都有真实的构建、功能检查和测量入口：`uring` 对照原生 liburing 与协程封装，
`server` 在相同 HTTP 逻辑下对照 epoll 与 io_uring。原来的占位测试和无法工作的旧实现
不作为性能基线，因此本报告不声称“重构后比重构前快多少”。

## 实现落点

| 层次 | 本轮实现 | 可核验入口 |
| --- | --- | --- |
| 依赖与构建 | 固定 liburing 2.6 与 SHA-256；本主题局部安装；配置不联网；移除占位测试框架依赖 | [依赖脚本](scripts/bootstrap-liburing.sh)、[构建脚本](scripts/build.sh)、[依赖发现](common/dependencies.cmake) |
| 协程生命周期 | 惰性 Task、嵌套结果/异常、无 detach；完整消费完成批次后再恢复任务；按深度限制启动数 | [Task](uring/include/liburing/task.hpp)、[IoService](uring/include/liburing/io_service.hpp) |
| 服务端 I/O | accept 返回已接收连接；处理短读写和 EAGAIN；连接 ID 防 fd 复用混淆；取消后保留操作缓冲直至排空 | [epoll](server/src/io/epoll_backend.cpp)、[io_uring](server/src/io/uring_backend.cpp)、[事件循环](server/src/server/server.cpp) |
| 协议与资源上限 | 有界 GET 子集、半包/流水、400、完整写出后再读；连接上限和 5 秒闲置关闭 | [连接解析](server/src/server/connection.cpp)、[集成测试](scripts/integration_test.py) |
| 热路径成本 | 缓存固定响应、复用连接写缓冲、复用 io_uring Operation；显式记录复制而非称为零拷贝 | [事件循环](server/src/server/server.cpp)、[io_uring](server/src/io/uring_backend.cpp) |
| 测量 | 原生 C++ 发压器逐响应核验；随机顺序重复；JSON 原始记录；计数对账；独立 syscall trace | [微基准](uring/bench/uring_bench.cpp)、[HTTP 客户端](server/bench/http/http_bench.cpp)、[编排与报告](scripts/benchmark.py) |

对外接口有所收缩：保留小写 `task` / `io_service` 类型别名，但不兼容旧的操作方法、
detach 和 callback 接口。这里交付的是可测量的实验，不是完整通用异步库。

## 环境与实验口径

- Linux 基础版本 4.19.91、glibc 2.17；Clang 20.1.8 + libc++，Release 构建。
- 默认 GCC 9 不支持所需的 C++20 协程，未通过降低语言标准绕过。
- 运行时探测 io_uring features=511，支持 opcode 0–34；真实超时、取消、socketpair 和
  TCP 操作均执行成功。不能凭“4.19”版本号判断本机没有 io_uring。
- 锁页内存 soft/hard 均为 65,536 B。深度 1024 的服务器 ring 初始化曾返回 ENOMEM；
  深度 512 已验证，默认连接上限 256，并要求小于 ring 深度。没有修改全局限制或升级内核。
- CPU 0 跑服务端/微基准，CPU 1 跑 HTTP 客户端；单事件循环、本机 loopback、1024 B 响应体。
- HTTP 每连接一个在途请求；每组 5 轮，每轮预热 300 ms、测量 2000 ms，排空时间计入实际时长。
  固定种子打乱顺序；不是固定到达率实验，不能用于生产延迟承诺或最大容量估算。
- 微基准每轮 131,072 个操作，包含 ring/task 设置与销毁。socketpair 每次 I/O 64 B，
  四次操作构成一次完整往返；ops/s 不是 roundtrips/s。
- 延迟从用户态发起/观察到完成，不是纯内核执行时间。直方图桶上界量化误差至多 12.5%；
  表中的 p99 是各轮 p99 的中位数，不是合并所有请求后重新计算的 p99。

NOP 的 raw/coroutine 差异包括封装、事件循环、结果校验与设置/销毁成本，
不能把整个差值解释为单次 `co_await` 指令成本。HTTP 两个后端的对象管理和缓冲策略也不同，
不能将差异全部归因于某一种内核接口。

## 已执行的验证

| 阶段 | 结果 | 覆盖与边界 |
| --- | --- | --- |
| 两个项目独立 Release 构建 | 通过 | Ninja；无配置期依赖下载 |
| Release 原生自检 | uring 3/3，server 1/1 通过 | 深度 2 的 100 个任务、嵌套/异常、10 ms 超时/取消、100 次 socketpair 往返、解析/写游标/直方图 |
| 真实 loopback 集成 | epoll、io_uring 均通过 | 半包、4 条流水、7 B 强制短写、400、100 次断开/描述符复用、连接限额、闲置超时、32 个未完成读的退出排空 |
| 发压器反向检查 | 通过 | 空响应、错误 body 必须失败；不是只计 socket 读次数 |
| epoll-only 独立构建 | 构建和 1/1 自检通过 | 不指定 liburing 安装前缀，关闭 uring 选项 |
| AddressSanitizer + UndefinedBehaviorSanitizer | Debug 原生自检 3+1、双后端集成均通过 | 检查内存/未定义行为；不把这一构建的数据用作性能结果 |

功能测试有意覆盖错误路径，而非只检查“程序能启动”。这仍不等于长期稳态验证、
全面 HTTP 协议正确性或生产级故障恢复验证。

## 最终测量结果

正式数据集为 [results/verified/report.md](results/verified/report.md)，开始于
2026-11-07 23:59:44 +08:00，结束于次日；主机为 UTC 时区的读者应按偏移换算。
共 48 组 × 5 轮 = **240 条测量**：160 条微基准、80 条 HTTP。
成功 I/O 操作 20,971,520 次，成功 HTTP 请求 26,617,740 次，错误为 0。
80 条 HTTP 记录均满足客户端成功数 = 服务端完整成功数、结束活动连接为 0，
且预热后与测量后打开的描述符数量相同。

### HTTP：中位数与尾延迟

以下均为 detailed 模式；完整 min/max、各轮记录和基础模式在生成报告中。

| 连接数 | epoll req/s | io_uring req/s | epoll / uring p99 µs | epoll / uring CPU ns/req |
| ---: | ---: | ---: | --- | --- |
| 1 | 54,933 | 53,008 | 24.6 / 24.6 | 12,288 / 13,613 |
| 16 | 186,967 | 219,040 | 106.5 / 90.1 | 5,346 / 4,563 |
| 64 | 192,835 | 223,499 | 393.2 / 327.7 | 5,178 / 4,473 |
| 256 | 182,132 | 213,211 | 1,703.9 / 1,441.8 | 5,485 / 4,690 |

64 连接组的 req/s 范围：epoll 189,921–193,564，uring 218,756–224,963。
这说明本次实现和负载下，多连接 uring 路径更高效；单连接则 epoll 更快。
64 连接 uring 的中位吞吐高约 15.9%，服务 CPU/请求低约 13.6%，
但其客户端已消耗约 1.00 核，epoll 客户端约 0.95 核，不能把该结果解释为后端容量上限。
256 连接吞吐反而低于 64 连接、p99 更高，增加连接数并非无代价。

增加详细观测后的吞吐中位数相对基础模式变化为 **−2.48% 至 +0.83%**。
正值不表示监控让程序变快：共享机器噪声和轮次差异可覆盖较小开销，
也不能把这个范围当作统计置信区间。

### 微基准：封装成本随批量变化

| 负载与深度/批量 | raw ops/s | coroutine ops/s | raw / coroutine CPU ns/op |
| --- | ---: | ---: | --- |
| NOP 1/1 | 2,400,050 | 1,390,600 | 416 / 718 |
| NOP 32/1 | 2,397,010 | 1,351,530 | 416 / 739 |
| NOP 32/32 | 5,116,570 | 4,864,060 | 195 / 205 |
| socketpair 1/1 | 1,223,210 | 907,145 | 816 / 1,101 |
| socketpair 32/32 | 1,736,810 | 1,721,810 | 575 / 580 |

封装在低并发 NOP 中并非零成本；批量操作摊薄了循环与提交开销。
但 socketpair 32/32 两组变异系数均约 17%，NOP coroutine 32/32 也约 16%，
不能把约 0.9% 的 socketpair 吞吐差异宣称为稳定性能差距。
变异系数是轮次标准差/均值，值越大表示波动越明显；CPU 时间比墙钟吞吐更能辅助区分抢占，
但本轮没有调度轨迹，不能断言波动的唯一原因。

### 系统调用：直接 trace 验证批量收益

对 raw 和 coroutine 分别跟踪 2048 次 NOP、深度 32，结果一致：

| 完成批量上限 | io_uring_enter 实际次数 | enter/op |
| ---: | ---: | ---: |
| 1 | 2,017 | 0.98486 |
| 32 | 64 | 0.03125 |

实际调用减少约 **96.8%**，约为原来的 1/31.5；不是假定“每批恰好一次”算出来的。
本机 strace 4.24 的 `-c` 会漏计未知的新系统调用，因此解析独立完整 trace，
在 x86_64 上识别 `io_uring_enter` 或 `syscall_0x1aa`。跟踪轮次不参与上述性能表。
这只验证 NOP 的 enter 调用，不冒充 HTTP 全量系统调用数。

### 队列、复制与内存

64 连接详细模式中，epoll/uring 每次轮询中位完成数为 62.09/63.65，
每千请求上下文切换为 0.22/0.17；单连接两者每千请求约有 999 次切换。
这些是事件聚合/调度行为，不足以独立证明具体热点根因。

uring 测量窗口中新建 Operation 均为 0，说明预热后的对象复用已生效；
每请求仍有约 **1124 B** 后端复制（请求 35 B + 带头部的响应 1089 B）。
这不是全程序零分配，也不是零拷贝。

正式各组 getrusage 峰值 RSS 中位数均为 19,452 KiB，不能据此声称内存等价。
另做了独立的 256 连接、500 ms 诊断，按 10 ms 间隔读取服务端自身 `/proc/<pid>/status`：

| 后端 | 负载前 VmRSS KiB | 运行中采样最大 VmRSS KiB | 结束 VmRSS / VmHWM KiB |
| --- | ---: | ---: | --- |
| epoll | 1,596 | 7,436 | 7,468 / 7,468 |
| uring | 2,960 | 11,624 | 11,624 / 11,624 |

这是额外诊断而非 5 轮主实验，采样最大值只是峰值下界。该次 epoll 的 getrusage 峰值
11,448 KiB 与 `/proc` 的 VmHWM 不同，也说明启动/执行链的峰值口径不能混为一谈。
uring 的 ring 与独立操作缓冲具有可见的内存代价；未做分配剖析，不能将差值精确归给单一结构。
两后端结束均为 5 个打开描述符、零请求错误；原始证据见
[resource-diagnostic.json](results/verified/resource-diagnostic.json)。

## 指标如何解释

| 指标 | 来源/单位 | 不代表什么 |
| --- | --- | --- |
| success、errors | 客户端完整内容校验；服务端合法响应完整写出后计数，两端对账 | 不是收到头部、读完成或开始发送就算成功 |
| p50/p95/p99 | 客户端逐请求直方图；ns | 不是内核独占耗时；不把多个阶段 p99 相加 |
| CPU ns/req、CPU 核 | getrusage 时间差；后者是 CPU 时间/墙钟时间 | 不是整机 CPU 利用率 |
| service_p99_ns | 服务器首段数据可见至完整写出；累计含预热 | 不是独立测量窗口的客户端 p99 |
| completions/poll、queue_full、EAGAIN | 后端计数和窗口差值 | 不是全部系统调用数 |
| operation_allocations | 只统计 io_uring Operation 新建 | 不是全程序 malloc 次数；epoll 的 0 不是零分配 |
| copied_bytes | 只统计 io_uring 后端安全缓冲复制 | 不是全程序、内核或网卡的所有复制 |
| max_rss_kib | getrusage 生命周期峰值，含预热/启动阶段 | 不是窗口平均内存，也不能据相同峰值断言两后端内存相同 |
| fd_count | 每轮预热后与测量后的 /proc 描述符数量 | 不是峰值采样；另有 peak_connections 记录连接高水位 |

`basic` 保留必要计数，`detailed` 增加服务端计时与直方图；客户端两组均照常核验和计时。
其吞吐差值衡量的是增加这部分服务端观测的成本，不是“关闭所有监控”的收益。

## 复现与证据位置

从本主题目录执行，首次工具链选择见 [README](README.md)：

```sh
make deps
make build
make test
python3 scripts/benchmark.py --build build --out results/new-run \
  --repeats 5 --warmup-ms 300 --duration-ms 2000
```

输出目录已有内容时拒绝覆盖。依赖、构建产物和运行数据留在被忽略的 `build/`、`results/`；
本报告和复现脚本可以被版本管理，但本轮没有执行 Git 提交或推送。

最终证据位于 `results/verified/`：`environment.json`、`results.jsonl`、`summary.json`、
`syscall-diagnostic.json`、`strace-*.txt`、`resource-diagnostic.json`、`report.md`。
早先 `results/latest/` 是收尾前的完整测量，不与最终数据合并；两个 smoke 目录也不纳入结论。
这些被忽略的文件只保留在本机，复制报告到其他机器时需重新运行或单独保留证据。

基于未提交工作区，base commit 为 `9d61e44b3cffc7efd5f9a8bdf01da931b938a200`，
测量源码摘要为 `b2334038502d859bf0ff410b46200c80fa1cb33e9a4218390ebb35c364dc3aa6`。
该轮收尾时已重新计算源码摘要及 3 个性能二进制的 SHA-256，均与 environment.json 相同。
随后新增 Linux kqueue 兼容层与后端选择参数，以下补测记录新源码与二进制摘要；
不将旧摘要当作当前代码的摘要。文档不在测量源码摘要内。

## Linux kqueue-compat

2026-11-08 09:15:58 +08:00 开始，仍在同一 Linux 基础版本 4.19.91 / glibc 2.17 主机，
没有转到 Mac。使用官方 [libkqueue v2.7.0](https://github.com/mheily/libkqueue/tree/v2.7.0)
编译现有 [kqueue 后端](server/src/io/kqueue_backend.cpp)，通过真实 kqueue/kevent 函数执行，
不是改名调用本项目的 EpollBackend。

libkqueue 是用户态兼容库，在 Linux 内部使用 epoll 等机制。其语义和资源管理存在
[上游已知差异](https://github.com/mheily/libkqueue/blob/v2.7.0/BUGS.md)，因此以下结论
只适用于当前兼容层实现。原生 Apple 构建路径保留但本轮没有执行。

### 构建与正确性

- 上游源码归档校验 SHA-256，局部安装到 build/deps，无系统安装和内核修改。
- Release 构建通过，uring 原生自检 3/3、server 自检 1/1 通过。
- epoll、uring、kqueue-compat 三后端均通过同一组真实 loopback 集成测试：半包、流水、
  7 B 强制短写、400、描述符反复开关、连接上限、闲置超时和未完成读的退出清理。
- 修正 kqueue 关闭清理：分别删除读/写过滤器，不能因不存在的读过滤器返回 ENOENT 而
  跳过仍存在的写过滤器；在关闭 fd 前显式移除监听，满足兼容层清理要求。
- server 的 ASan/UBSan Debug 自检和三后端集成通过。libkqueue 静态依赖仍为 Release，
  没有将第三方库内部视为已获得完整 sanitizer 覆盖。
- epoll-only 无兼容层构建仍通过；选择未编译的 uring/kqueue/kqueue-compat 明确失败，
  不静默回退。依赖下载仍仅发生在显式 bootstrap 命令中。

### 同轮三后端性能

相同 Release 二进制、CPU 0/1 放置、1024 B body、闭环单在途请求；预热 300 ms，
每轮测量 1000 ms，3 轮重复，随机打乱顺序。下表为 detailed 吞吐中位数，单位 req/s：

| 连接数 | epoll | uring | kqueue-compat |
| ---: | ---: | ---: | ---: |
| 1 | 54,459 | 53,944 | 42,661 |
| 16 | 187,992 | 218,692 | 98,380 |
| 64 | 191,560 | 224,538 | 93,754 |
| 256 | 178,836 | 210,967 | 86,367 |

64 连接组 p99 为 epoll 393.2、uring 327.7、兼容层 983.0 µs；服务 CPU ns/req
分别为 5212、4452、10468。兼容层本次吞吐约为直接 epoll 路径的 48.9%，
但没有进行剖析或逐项对照，不能把全部差异归因于某个锁、线程或系统调用。
16 连接组 uring 吞吐更高，但 p99 为 122.9 µs，高于 epoll 的 98.3 µs；
不能概括成“uring 在所有多连接配置下尾延迟都更低”。

测量后进程线程数 epoll/uring/兼容层分别为 1/1/3，打开描述符分别为 5/5/8。
兼容层有内部辅助线程，CPU 数据包含全进程；一条业务事件循环不等于全进程单线程。
各轮描述符前后相同且结束活动连接为 0，这不是对所有路径永不泄漏的证明。

### 证据与复现

本轮共 56 组 × 3 轮 = 168 条记录，其中微基准 96 条、HTTP 72 条；成功 I/O 操作
12,582,912 次、HTTP 请求 9,903,851 次，错误为 0。逐轮成功数对账、描述符检查、
源码/三个性能二进制/libkqueue 静态库摘要复核均通过。

详细报告和原始数据在被忽略的
[results/linux-kqueue-compat-20261108/](results/linux-kqueue-compat-20261108/report.md)。
源码摘要为 `a589cb4f01051662d771e0e51e6090008bf82cd879f1aa46fe4c03be274e4f6a`，
libkqueue 静态库摘要为 `5d7fe48aa2dfbd2f486947bff6a8e6272c5ffbe9de8333b310f387fc62d0d2c3`。
复现命令及依赖来源/许可见 [server README](server/README.md)。本轮仍未 commit/push。

## Linux 监听生命周期对齐实验

2026-11-08 09:32:06 +08:00 开始的新一轮实验，同一 Linux、同一 Release 二进制、
同一 libkqueue 静态库。以下只比较本轮的四组，不与前一份三后端报告跨时间计算收益。
实验矩阵及复现命令见 [server README](server/README.md#对齐监听生命周期的实验)。

### 控制变量与剩余差异

四组均使用同一 HTTP 处理、1024 B body、每连接一个在途请求、完成批量 64、
逐项更新监听、单业务事件循环；客户端/服务端固定在 CPU 1/0。
每组预热 300 ms、测量 1000 ms，basic/detailed 各 5 轮，固定种子随机打散顺序。
不改第三方库，不混入批量 changelist、立即读写或连接数/响应体优化。

| 后端 | 用户态监听对象 | Linux 内核监听 |
| --- | --- | --- |
| epoll | 本地索引保留至 close | EPOLLONESHOT 停用，MOD 重新启用 |
| epoll-recreate | 同样保留本地索引至 close | 就绪后 DEL，下次 ADD |
| kqueue-compat | EV_ONESHOT，删除后重建 knote | DEL/ADD |
| kqueue-compat-dispatch | EV_DISPATCH，保留 knote，EV_ENABLE 重新启用 | 兼容库仍使用 DEL/ADD |

knote 是 libkqueue 内部保存过滤器状态的对象。dispatch 不是原生 EPOLLONESHOT 的等价
内核实现：它保留库内对象，却仍需删除/重新添加底层 epoll 监听。因此用 epoll-recreate
控制底层增删，用原始 kqueue 与 dispatch 比较对象生命周期；这不是完全正交的 2×2 实验。
兼容库的 ioctl、锁、索引、事件转换以及连接初始化差异仍然保留，不能单独归因于某一项。

第一次试跑主动中止：最初 epoll-recreate 同时删除了本地 registered_ 索引，会额外混入
索引重建成本。修正后重新构建并重测；[未完成试跑说明](results/linux-readiness-aligned-20261108/ABORTED.md)
及原始数据保留，不参与本节统计，不与正式轮次合并。

### 同轮结果

64 连接、detailed 模式，5 轮中位数；CPU 是全服务进程每请求消耗，不是响应延迟：

| 后端 | req/s | 5 轮 min–max | CPU µs/请求 | p99 µs |
| --- | ---: | --- | ---: | ---: |
| epoll | 189,031 | 184,708–193,140 | 5.27 | 491.5 |
| epoll-recreate | 158,670 | 155,050–162,003 | 6.26 | 655.4 |
| kqueue-compat | 95,103 | 90,695–96,804 | 10.39 | 917.5 |
| kqueue-compat-dispatch | 126,058 | 125,469–127,404 | 7.87 | 720.9 |

吞吐变异系数依次为 1.78%、1.72%、2.52%、0.67%。三个对照分别说明：

- epoll → epoll-recreate：吞吐下降 16.1%。显式删除/重新注册这一实现路径有可测成本，
  但该比例不是某一条 epoll_ctl 指令的独立耗时占比。
- kqueue-compat → dispatch：吞吐提高 32.5%，每请求 CPU 降低约 24.3%。保留对象有收益，
  但同时避免了重复类型探测和分配，不能把收益全部称为 calloc 成本。
- dispatch 对比 epoll-recreate：相同底层 ADD/DEL 模式下，仍有 20.6% 吞吐差距。
  因此“仅仅监听删除重建导致慢一半”不成立；兼容语义与库内管理仍有剩余成本。

保留对象在 1 连接时仅提高约 6.2%，16/256 连接提高约 25.4%/30.7%；
不能把 64 连接的 32.5% 当成所有负载的固定收益。所有吞吐与尾延迟均为闭环本机回环结果，
不是固定到达率延迟或生产容量；p99 为直方图桶上界，有至多 12.5% 的量化误差。

### 独立系统调用诊断

每后端单独跟踪 1 连接、200 ms、basic，完全不混入上述性能轮次。
下面为每成功请求的近似次数，连接建立、排空和关闭会带来小量偏差：

| 后端 | epoll ADD | epoll MOD | epoll DEL | ioctl | fstat | getsockopt |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| epoll | 0 | 2 | 0 | 0 | 0 | 0 |
| epoll-recreate | 2 | 0 | 2 | 0 | 0 | 0 |
| kqueue-compat | 2 | 0 | 2 | 2 | 2 | 6 |
| kqueue-compat-dispatch | 2 | 0 | 2 | 2 | 约 0 | 约 0 |

dispatch 的整轮 fstat/getsockopt 为 2/6 次，只在读/写过滤器首次创建时探测；
原兼容路径分别为 828/2484 次，对应 413 个成功请求。
保留对象确实去掉了反复的类型查询，但仍有读/写事件的 ioctl。尚无热点剖析或单项消融，
不能把剩余 20.6% 全部归给 ioctl、锁竞争或辅助线程，也不据此评价原生 BSD/macOS kqueue。

### 验证与证据

- 四组 Release 功能集成通过：半包、流水、7 B 短写、错误请求、FD churn、限额、
  闲置超时、32 个未完成读的取消/退出；服务端原生自检 1/1、uring 原生自检 3/3 通过。
- 服务端 ASan/UBSan 自检与四组集成通过；修正控制组后重新执行其 Release/ASan 集成。
  libkqueue 静态库仍为 Release，不宣称库内部获得完整 sanitizer 覆盖。
- 无兼容依赖的 epoll-only 构建与自检通过；不可用后端明确拒绝，不回退。
- 正式数据为 64 组 × 5 轮 = 320 条，其中微基准 160 条、HTTP 160 条。
  成功 I/O 20,971,520 次、HTTP 请求 18,554,910 次，错误 0；逐轮双端计数、活动连接归零、
  FD 前后相同、组数/轮数、源码/三个性能二进制/依赖库摘要均已复核。

本机原始结果：[正式报告](results/linux-readiness-aligned-v2-20261108/report.md)、
[HTTP 系统调用诊断](results/linux-readiness-aligned-v2-20261108/http-syscall-diagnostic.json)。
这些文件位于被忽略的 results/，未纳入 Git。
实验源码 SHA-256：`ccdabe4ad208e8299247edef6e00b2890ad30e3229d9140098c4a219e4abf839`。
旧报告、依赖和其他工作区改动保留；本轮未 commit/push。

## 尚未覆盖

macOS 原生 kqueue 没有实机编译/运行证据，Linux 兼容层成功不能替代它；
未测真实磁盘、远端网络、TLS、多事件循环、固定到达率负载，
也未启用 SQPOLL、multishot、注册文件/缓冲。
perf 不可用，未提供火焰图或缓存未命中数据；不将 CPU 时间降低当作已经定位到某条热点指令。

`IoService` 遇到不可恢复提交/等待错误仍是 fail-fast：已启动但未完成的任务不能被随意销毁。
服务端退出会尝试有界取消/排空，底层失败不伪装成正常完成。完整的系统故障恢复、
解析器模糊测试和跨平台持续集成仍需后续验证。
