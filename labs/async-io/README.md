# async-io —— Linux 异步 I/O 的库与服务两层

同一个内核接口的两种用法：先把 io_uring 的提交/完成环包成可 `co_await` 的对象，再在这个
接口之上搭一个能同时跑 io_uring 与 kqueue 的服务端。

| 目录 | 做法 | 前置 | 入口 |
| --- | --- | --- | --- |
| `uring/` | C++20 协程封装的 io_uring 库：提交队列、完成队列、超时与取消 | Linux 5.1+、CMake | [uring/README.md](uring/README.md) |
| `server/` | 事件循环服务器，io_uring 与 kqueue 双后端可切换 | Linux（io_uring）或 macOS（kqueue）、CMake | [server/README.md](server/README.md) |

## 为什么放在一起

`uring/` 关心的是一次系统调用怎么被表达成协程挂起点；`server/` 关心的是成千上万个连接
怎么挂在同一个事件循环上。前者是后者的地基，但两者刻意不共享代码：`server/` 自带一份
ring 封装，因此可以独立观察"库设计"与"服务设计"各自要解决的问题。

对照阅读时能看清两个平台模型的差异：io_uring 是**提交/完成**（proactor），kqueue 是
**就绪通知**（reactor）。同一个服务器要同时支持两者，就必须把"等什么"抽象出来，这正是
`server/` 存在的价值。

## 独立边界

- 两个目录各自带 CMakeLists，可单独配置、单独构建、单独删除。
- `server/` 不 import `uring/` 的代码，两者没有编译期依赖。
- `uring/` 需要内核 io_uring 支持；`server/` 在无 io_uring 的平台上退回 kqueue，两者共用
  同一份事件循环骨架。
