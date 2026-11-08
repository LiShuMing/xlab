# uring：结构化协程与原生 liburing 对照

前置：Linux、实际可用的 io_uring、C++20 协程编译器、liburing。
先运行 `uring_probe`，再运行真实操作测试；探测成功本身不是读写测试通过。

## 独立构建

```sh
cmake -S uring -B build/uring -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DLIBURING_ROOT="$PWD/build/deps"
cmake --build build/uring --parallel 2
ctest --test-dir build/uring --output-on-failure
build/uring/uring_probe
build/uring/uring_bench raw 32 32 131072 1 nop
build/uring/uring_bench coroutine 32 32 131072 1 nop
build/uring/uring_bench coroutine 32 32 131072 1 socketpair
```

以上从本主题目录运行；也可直接配置本目录并指定绝对依赖前缀。工具链说明见
[主题入口](../README.md)。

参数依次是模式、并发操作深度、单批完成上限、总操作数、详细计时 0/1、负载。
总操作数须能被深度整除；socketpair 还须能被 4×深度整除。NOP 不传输字节；
socketpair 每条流顺序执行写 A → 读 B → 写 B → 读 A，每个操作 64 B，
每个读取都核验内容。成功数的单位是 I/O 操作，不是完整往返次数。

## 设计约束

`IoService` 只保留本实验实际使用的 Nop/Read/Write/Timeout/Cancel。
移除未被验证的大量操作包装和 fmt 依赖，不伪装成完整的通用异步框架。
旧的小写 task/io_service 类型名保留别名，但旧的操作方法、detach/callback 接口不再支持；
仓库内示例已同步更新。

`Task<T>` 是惰性任务，显式 Run 或被 co_await 后才启动。嵌套任务通过 continuation
返回父任务；异常在结果消费时重新抛出。没有 detach：
已启动而尚未完成的任务若被释放，会立即终止进程，避免悬空 user_data 继续被内核使用。

完成循环在恢复任何协程前先消费当前整个 CQ 批次，避免恢复期间再次提交时重复推进队列。
RunAll 分组启动任务，将同时在途任务数限制在配置深度；不能先启动任意多任务再假设 CQ
永远不会满。不可恢复的底层提交/等待错误仍属于 fail-fast 边界，不是生产级错误恢复框架。

## 验证与指标

- basic_test：深度 2 上执行 100 个嵌套任务，检查完成计数、结果、异常传递。
- delay_and_print：真实 10 ms 定时器；取消确认和目标的 ECANCELED 都必须完成。
- ping_pong：真实 socketpair 双端 100 轮，处理短读写并逐字节校验。
- uring_bench：原生/协程执行等量操作，输出吞吐、CPU ns/op、p50/p95/p99、
  提交次数、完成数、等待函数调用数和上下文切换。

提交次数与等待函数调用数是用户态计数，不直接等于系统调用数。
微基准包含 ring/task 设置和销毁；NOP 的数字不能代替网络或磁盘性能结论。
详细延迟从准备操作前到用户态观察到完成，包含封装、排队、内核和调度开销。
正式重复测量和独立 syscall 诊断由主题脚本编排。
