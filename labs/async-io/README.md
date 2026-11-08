# async-io：从协程开销到服务端 I/O 路径

两个独立的 C++20 实验，共用本主题的构建依赖发现和测量工具，不互相链接。

| 实验 | 要回答的问题 | 入口 |
| --- | --- | --- |
| [uring](uring/README.md) | 同一组内核操作，协程相对直接 liburing 增加多少成本？批量提交减少多少系统调用？ | NOP、64 B socketpair、超时与取消 |
| [server](server/README.md) | 相同 HTTP 逻辑下，epoll 与 io_uring 的吞吐、尾延迟、CPU 和排队行为如何变化？ | 固定 1024 B 响应、单事件循环 |

Linux 的 io_uring 以运行时操作探测为准，不按内核版本号直接拒绝回移实现。
Linux 还可显式启用 libkqueue 兼容路径 `kqueue-compat`；macOS 保留独立原生 kqueue 路径。
Linux 兼容层的测量不等于 macOS 验证，详见 [服务器构建说明](server/README.md)。

## 构建与验证

需要 CMake 3.22+、Ninja、支持 C++20 协程的编译器，以及 Python 3.9+（仅用于编排）。
Python 脚本只使用标准库，不需要虚拟环境或第三方包。

```sh
cd labs/async-io
make deps                 # 固定 liburing 2.6，校验 SHA-256，安装到 build/deps
make build                # 两个项目分别配置；默认最多 2 个编译任务
make test                 # 原生自检 + 两个后端的真实 loopback 集成测试
make bench                # 5 轮；结果写入 results/latest，已有目录时拒绝覆盖
```

需要在 Linux 运行 kqueue 接口时，额外执行 `make deps-kqueue`，再用
`KQUEUE_COMPAT=ON make build`；测试通过 `BACKENDS='epoll uring kqueue-compat'` 指定三后端。
基准脚本对应 `--backends epoll uring kqueue-compat`，默认仍只测 epoll/uring。

首次构建通过标准的 `CXX`、`CXXFLAGS`、`LDFLAGS` 指定工具链，或直接使用 PATH 中
支持 C++20 的默认编译器。旧 GCC 9 不能编译本实验的协程，不要降级语言标准来掩盖问题。
已有 CMake 配置会保留工具链选择。

在需要显式 libc++ 和 GCC 启动文件位置的老 Linux 上，设置本机的安装前缀后使用：

```sh
: "${CLANG_ROOT:?set the local Clang installation prefix}"
: "${GCC_TOOLCHAIN:?set the local GCC installation prefix}"
CXX="$CLANG_ROOT/bin/clang++" \
CXXFLAGS="-stdlib=libc++ --gcc-toolchain=$GCC_TOOLCHAIN" \
LDFLAGS="-L$CLANG_ROOT/lib64 -Wl,-rpath,$CLANG_ROOT/lib64" make build
```

这些路径只进入被忽略的 build 配置，不写死在源码。无需 sudo、内核升级或修改全局环境。
依赖下载只发生在显式的 `make deps`；CMake 配置从不联网。可用 `LIBURING_ROOT`
指定已有安装前缀。liburing 是外部 LGPL/MIT 许可依赖，不将下载源码或二进制纳入本仓库；
来源为 [官方仓库的 liburing-2.6 标签](https://github.com/axboe/liburing/tree/liburing-2.6)。

## 测量与解释

```sh
python3 scripts/benchmark.py --build build --out results/run-001 \
  --repeats 5 --warmup-ms 300 --duration-ms 2000
```

输出：

- `environment.json`：能力探测、编译器版本、CPU 放置、锁页上限、源码及二进制摘要。
- `results.jsonl`：逐轮原始记录，包括服务端计数差值。
- `summary.json`：分组中位数、min/max、变异系数。
- `syscall-diagnostic.json`、`strace-*.txt`：独立系统调用诊断，不混入性能轮次。
- `report.md`：定量报告、观测开销与解释边界。

HTTP 是每连接一个在途请求的闭环负载，发压端使用 C++ 非阻塞 epoll 客户端并校验完整响应；
客户端和服务端绑定不同 CPU。成功数必须与服务端完整写出响应的次数一致。每组先预热，
再测量，最后排空已发请求；不同实验顺序使用固定随机种子打散，减轻时间顺序偏差。

延迟直方图每个 2 的幂区间分成 8 桶，报告桶上界，量化误差不超过 12.5%。
不将用户态观察到的完成时间称为纯内核执行时间，也不把各阶段 p99 相加。
共享机器结果要结合波动与客户端 CPU 使用量解释，不能当成服务器最大容量或生产 SLO。

## 工程边界

- 构建、依赖和原始数据分别放在被忽略的 `build/`、`results/`，不是待提交源码。
- 后端选择显式且不静默回退；初始化失败会说明原因。
- 本轮不实现 TLS、静态文件、多线程、multishot、SQPOLL 或注册缓冲优化。
- 原来不能工作的占位版不构成性能基线，只比较本轮可验证的实现路径。
- 更详细的实现与指标说明见各实验 README；本机结论见 [可观测性总结](OBSERVABILITY.md)。
