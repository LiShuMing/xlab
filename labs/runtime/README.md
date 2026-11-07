# runtime —— 两种调度模型的正面对照

同一类问题的两种答案：任务之间要不要共享状态、负载不均时谁来搬运工作。

| 目录 | 模型 | 前置 | 入口 |
| --- | --- | --- | --- |
| `reactor/` | 单线程协程调度器：一个事件循环 + 无共享，用 `co_await` 表达挂起 | C++23 协程、CMake | [reactor/README.md](reactor/README.md) |
| `pool/` | work-stealing 线程池：每线程一队列，空闲线程从别人尾部偷任务 | C++20、CMake | [pool/README.md](pool/README.md) |

## 为什么放在一起

两者都在回答"多核上怎么把任务排完"，但取舍相反：

- `reactor/` 选择**不要多核**：单线程跑事件循环，靠"不共享"直接消除数据竞争，代价是
  一个核只能吃满一个核。
- `pool/` 选择**要多核但避免抢锁**：每个线程维护自己的双端队列，本地操作近似无锁，
  只在队列空时跨线程偷取。

并排读才能看清这条分界线：并发问题的消除方式，要么由结构保证（share-nothing），要么
由算法保证（work-stealing）。单看任何一个都会漏掉另一种可能。

## 独立边界

- 两个目录各自带 CMake 与测试，可单独构建、单独删除。
- `pool/` 由仓库根 `CMakeLists.txt` 通过 `XLAB_BUILD_THREAD_POOL` 选项纳入统一构建；
  `reactor/` 独立配置，不进根构建（它的协程标志与主构建的编译选项不同）。
- 两者通过 `cmake/XlabDependencies.cmake` 取 GoogleTest，不写死第三方源码路径。
