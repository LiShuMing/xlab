# server：相同 HTTP 逻辑下对照 I/O 后端

前置：C++20 编译器、CMake 3.22+。Linux 默认 epoll，可显式构建和选择 io_uring；
macOS 单独构建 kqueue。本轮只在 Linux 验证，不能据此宣称 macOS 路径可用或性能相当。

## 构建与运行

```sh
cmake -S server -B build/server -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DRINGSERVER_ENABLE_URING=ON -DLIBURING_ROOT="$PWD/build/deps"
cmake --build build/server --parallel 2
ctest --test-dir build/server --output-on-failure
build/server/ringserver -b epoll -p 8080
# 另一个终端
build/server/ringserver_bench 8080 64 2000
```

省略 RINGSERVER_ENABLE_URING 或设为 OFF 可以构建不依赖 liburing 的 epoll 版本。
选择 uring 却没有编译该后端会明确失败，不静默退回 epoll。
macOS 不编译 Linux 压测器；需要在对应系统单独补充构建/运行证据。

### 在 Linux 编译运行 kqueue 接口

Linux 没有原生 kqueue。显式启用上游 libkqueue 兼容层后，同一服务器二进制可以选择
`epoll`、`uring` 或 `kqueue-compat`，不会将兼容层伪装成原生 `kqueue` 或静默回退。
从主题目录运行：

```sh
make deps-kqueue
KQUEUE_COMPAT=ON make build
make test BACKENDS='epoll uring kqueue-compat'
build/server/ringserver -b kqueue-compat -p 8080
# 三后端在同一轮次、相同负载下测量；输出目录必须是新的
python3 scripts/benchmark.py --build build --out results/linux-three-backends \
  --backends epoll uring kqueue-compat --repeats 3 --duration-ms 1000
```

独立 CMake 对应选项为 `-DRINGSERVER_ENABLE_KQUEUE_COMPAT=ON`
和 `-DLIBKQUEUE_ROOT="$PWD/build/deps"`，默认关闭，无配置期下载。
libkqueue 固定 [上游 v2.7.0](https://github.com/mheily/libkqueue/tree/v2.7.0)，源码归档
SHA-256 为 `359702489ded4e466c721c5b02b0e569b914f13806b88c5846341efa5d05081b`，
仅安装到被忽略的 build/deps；本地保留上游 LICENSE，源码主体许可为 ISC，event.h 为 BSD-2-Clause。

兼容层在 Linux 上将 kevent 翻译为 epoll 等机制，并创建内部资源监控线程。
服务器仍只有一个业务事件循环，但不是全进程只有一个线程；CPU 指标包含辅助线程。
显式删除监听后才关闭 fd，避免兼容层保留无效注册状态。
这条路径的构建/功能/性能结果不能用来宣称 macOS 或 BSD 原生 kqueue 已验证。

### 对齐监听生命周期的实验

默认后端不变，增加两个显式实验变体；所有变体共用相同 HTTP 处理、逐项注册、批量完成、
单在途请求和响应内容。不修改 libkqueue，不在这一轮引入批量 changelist 或立即读写。

| 选择 | 事件返回后 | 下一次注册 | 用途 |
| --- | --- | --- | --- |
| `epoll` | EPOLLONESHOT 停用，保留内核监听 | MOD | 原始直接调用基线 |
| `epoll-recreate` | 显式 DEL | ADD | 对齐兼容层的内核监听增删 |
| `kqueue-compat` | EV_ONESHOT 删除库内监听对象 | EV_ADD，新建对象 | 原始兼容基线 |
| `kqueue-compat-dispatch` | EV_DISPATCH 停用，保留库内读/写监听对象 | 已有过滤器用 EV_ENABLE | 隔离对象重建成本 |

EV_DISPATCH 是 kqueue 的官方停用语义，而非本地模拟；读/写过滤器分别登记，在 close 时
显式删除。libkqueue 在 Linux 停用时仍会 epoll DEL，启用时 ADD。因此 dispatch 与原始
epoll 只对齐了“保留监听对象”，并未对齐内核操作；与 epoll-recreate 比较才能控制
底层 ADD/DEL。类型探测、ioctl、锁和库内状态维护仍是剩余差异，不能据此单项归因。
两条 epoll 路径均保留相同的本地 registered_ 索引至 close；不会把本地索引重建
混入“内核监听重建”控制组。连接初始化仍有 accept4 与 accept/fcntl 的差别，
但各组每轮均只建立固定数量的持久连接，不按请求重新连接。

```sh
KQUEUE_COMPAT=ON make build
make test BACKENDS='epoll epoll-recreate kqueue-compat kqueue-compat-dispatch'
python3 scripts/benchmark.py --build build --out results/linux-readiness-aligned \
  --backends epoll epoll-recreate kqueue-compat kqueue-compat-dispatch \
  --repeats 5 --warmup-ms 300 --duration-ms 1000
```

命令从主题目录运行。5 轮随机顺序、相同 CPU 放置，同时比较 basic/detailed；每轮核对
双端成功数、结束活动连接和描述符数量。额外的 `http-syscall-diagnostic.json` 与
`strace-http-*.txt` 是独立 1 连接诊断，不参与性能统计；无法 attach 时明确记录不可用。
保留旧报告，只在同轮结果间比较，不以跨时间差值推导单变量收益。

## 协议与所有权

统一完成语义：

- accept 的结果就是新连接 fd，上层不再二次 accept。
- read/write 的结果是本次实际字节数；EAGAIN 保留/重提操作，不伪装成 EOF。
- 一个连接最多一个收发操作；写完完整响应才读取下一请求，自然限制慢客户端的积压。
- request 使用有上限的 16 KiB 缓冲，支持半包、连续请求与流水请求。
- 只接受 GET HTTP/1.0 或 HTTP/1.1、无请求体，返回 1024 个 x 字节；这是测量用最小子集，
  不是完整 RFC 实现。非零 Content-Length、Transfer-Encoding 和畸形/超长头返回 400 后关闭。
- FD 仅作为表索引，同时核对单调连接 ID，避免把迟到事件应用到复用后的 fd。
- io_uring 操作拥有自己的缓冲，close 先清除用户目的指针再发取消，取消确认和目标完成
  全部排空后才释放内存；操作对象与缓冲可复用。这里的复制成本是可观测的，不隐瞒成零拷贝。
- 固定响应缓存一次生成，连接写缓冲复用容量，不在每请求上重新拼装响应。
- 5 秒无活动连接会关闭，连接数和待处理操作数均有上限。
- SIGINT/SIGTERM 进入有界排空；若底层不能完成排空，失败退出而不将悬空操作伪装成成功。

默认 ring 深度 512、完成批量 64、连接上限 256；uring 连接上限必须小于 ring 深度。
锁页上限过小时，初始化会失败。内核版本号不是能力判断，运行时检查实际操作支持。

## 观测接口

`-m basic|detailed` 切换内部延迟观测；两者都保留正确性与事件计数。
SIGUSR1 输出单行 JSON 快照，终止时输出最终快照：

- success：合法请求的完整响应已全部写出，不是 read 次数或开始发送次数。
- errors / rejected：协议/I/O 错误与连接限额/闲置超时分开。
- active / peak_connections、字节数、短写数、过期事件数。
- submitted / completed、取消数、轮询次数、空轮询、批量提交、EAGAIN、队列满。
- operation_allocations：仅后端 Operation 新建次数；不是全进程 malloc 次数。
- copied_bytes：io_uring 后端缓冲安全复制字节数；不是所有内存复制总量。
- CPU 时间、上下文切换与生命周期峰值 RSS。
- service_p50_ns / service_p99_ns：从首段请求数据被观察到到完整响应写完成，含预热的累计直方图，
  不是独立测量窗口的客户端延迟。

`-w` 仅用于注入单次写长度上限，验证分段完成；不是性能优化开关。
`-t` 只接受 1，避免把未实现的多线程参数算入实验。

`scripts/integration_test.py` 通过真实 loopback 检查半包/流水、强制短写、错误请求、
连接上限、慢连接、FD 复用和带未完成读的退出，检查两后端的最终完成账目。
原来的 GoogleTest / Google Benchmark 占位程序已替换为 Release 下仍有效的原生检查与
真实 C++ 非阻塞发压器，构建不再为占位代码联网获取测试框架。

Linux 基准通过主题脚本运行，参见 [主题入口](../README.md)。
