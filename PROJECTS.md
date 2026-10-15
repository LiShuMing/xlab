# xlab 项目路由索引

更新日期：2026-10-14。相对路径属于 xlab；外部链接指向已迁移项目的当前仓库。

本表按当前目录、实际源码和构建清单整理，包含语言实验室、独立项目、
工作区成员、跨语言应用及第三方子模块。目录存在不代表已验证构建成功；
Windows 原生支持范围以 [WINDOWS.md](WINDOWS.md) 为准。

## 使用方式

1. 已知项目名：搜索项目名或路径，例如 `query-engine`、`py-email`。
2. 已知需求：先查下面的“按任务路由”，再进入对应语言表。
3. 修改代码前：读取目标目录的 `AGENTS.md`、`RULES.md` 和构建清单；
   README 中的历史设计不一定等于当前实现。
4. “旧目录”保留用于定位，不应当作为可运行项目入口。
5. 第三方声明不等于 gitlink；先查本文末尾的状态说明，不要默认递归下载全部依赖。

## 已迁移项目

以下旧路径仅供追溯；代码、构建与后续任务应在目标仓库进行。

| Former xlab path | Current home |
| --- | --- |
| `liminalis/` | [lyra](https://github.com/LiShuMing/lyra/tree/main) |
| `panming/` | [carina](https://github.com/LiShuMing/carina/tree/main) |
| `python/projects/tech-radar/` | [carina/modules/tech-radar](https://github.com/LiShuMing/carina/tree/main/modules/tech-radar) |
| `cc/projects/kv-store/` | [vela/storage](https://github.com/LiShuMing/vela/tree/main/storage) |
| `cc/projects/query-engine/` | [vela/execution](https://github.com/LiShuMing/vela/tree/main/execution) |
| `optimizer-learning/` | [vela/optimizer](https://github.com/LiShuMing/vela/tree/main/optimizer) |
| `swift/projects/daylog/` | [carina/apps/daylog](https://github.com/LiShuMing/carina/tree/main/apps/daylog) |
| `python/projects/py-cli/` | [lyra/modules/developer-tools](https://github.com/LiShuMing/lyra/tree/main/modules/developer-tools) |
| `python/projects/py-tools/` | [lyra/modules/developer-tools](https://github.com/LiShuMing/lyra/tree/main/modules/developer-tools) |
| `python/projects/py-optimizer1/` | [vela/research/optimizer-evidence](https://github.com/LiShuMing/vela/tree/main/research/optimizer-evidence) |
| `python/projects/py-optimizer2/` | [vela/research/optimizer-scanner](https://github.com/LiShuMing/vela/tree/main/research/optimizer-scanner) |
| `python/projects/py-pia/` | [carina/modules/product-intelligence](https://github.com/LiShuMing/carina/tree/main/modules/product-intelligence) |
| `python/projects/py-report/` | [carina/modules/research-report](https://github.com/LiShuMing/carina/tree/main/modules/research-report) |

知识资料的维护归属、Cygnus 184 份文档路由、源正文退役及保留边界见 [docs/README.md](docs/README.md)。

## 按任务路由

| 需求或关键词 | 优先定位 |
| --- | --- |
| 工作日记、菜单栏、提醒、SwiftUI | [carina/apps/daylog](https://github.com/LiShuMing/carina/tree/main/apps/daylog)（刻白，已迁移） |
| Kubernetes、控制面、MVCC、Informer | [go/k8s-lab/](go/k8s-lab/) |
| LLM 训练与推理实验 | [python/projects/llm-lab/](python/projects/llm-lab/)、[rust/projects/llm-runtime/](rust/projects/llm-runtime/)（后者仅设计骨架） |
| C++ 数据结构、并发、协程、COW、一致性哈希 | [cc/cclab/](cc/cclab/) |
| LeetCode、LCR、面试题、基础算法 | [cc/algo/](cc/algo/)、[rust/rlab/tools/leetcode/](rust/rlab/tools/leetcode/)、[python/pylab/](python/pylab/) |
| KV、MemTable、SkipList、Arena | [vela/storage/](https://github.com/LiShuMing/vela/tree/main/storage/) |
| 向量化执行、Hash Aggregate、Join、Sort、Top-N | [vela/execution/](https://github.com/LiShuMing/vela/tree/main/execution/) |
| 线程池、work stealing、任务调度 | [cc/projects/thread-pool/](cc/projects/thread-pool/)、[rust/rlab/tools/thread-pool/](rust/rlab/tools/thread-pool/) |
| MPMC、MPSC、队列内存回收 | [rust/rlab/tools/lockfree-queue/](rust/rlab/tools/lockfree-queue/) |
| Bloom、Split Block、XOR Filter | [rust/rlab/tools/bloom_filter/](rust/rlab/tools/bloom_filter/) |
| Rust 数据库、SQL、存储引擎 | [rust/rdb/](rust/rdb/) |
| AI 记忆数据库、向量索引、Arrow、gRPC | [rust/projects/umbra/](rust/projects/umbra/) |
| Volcano、Cascades、优化器算法对照 | [vela/optimizer/](https://github.com/LiShuMing/vela/tree/main/optimizer/) |
| 多数据库优化器源码分析 | [vela/research/optimizer-evidence](https://github.com/LiShuMing/vela/tree/main/research/optimizer-evidence)、[vela/research/optimizer-scanner](https://github.com/LiShuMing/vela/tree/main/research/optimizer-scanner) |
| LLVM、JIT、表达式编译 | [cc/projects/llvm-jit/](cc/projects/llvm-jit/) |
| SQL Parser、Haskell、规则优化 | [haskell/projects/sql-parser/](haskell/projects/sql-parser/) |
| DSL、Monad Transformers | [haskell/projects/dsl-transform/](haskell/projects/dsl-transform/) |
| STM、并发 KV、事务组合 | [haskell/projects/stm-engine/](haskell/projects/stm-engine/) |
| 增量计算、IVM、DBSP、差分数据流 | [python/ivm/](python/ivm/)、[python/pylab/dbsp/](python/pylab/dbsp/)，第三方见 `rust/thirdparty/` |
| Linux io_uring、异步 I/O、Reactor | [cc/projects/io-uring/](cc/projects/io-uring/)、[cc/projects/mini-seastar/](cc/projects/mini-seastar/)、[cc/projects/web-server/](cc/projects/web-server/) |
| Python C API、Cython、嵌入式 Python | [cc/projects/cpython/](cc/projects/cpython/) |
| Iceberg、Java/JVM、Spark、Scala、Groovy | [java/xlab-iceberg/](java/xlab-iceberg/)、[java/xlab-itest/](java/xlab-itest/) |
| LLM 数学/代码评测、Strata benchmark | [python/llm_benchmark/](python/llm_benchmark/) |
| Strata 只读代码审查 | [python/projects/strata-review/](python/projects/strata-review/) |
| 论文处理、学术工具 | [python/projects/py-academic/](python/projects/py-academic/) |
| AI 沙盒、Streamlit、LangChain | [python/projects/py-lab/](python/projects/py-lab/) |
| 邮件、newsletter、Gmail 摘要 | [Lyra email-digest](https://github.com/LiShuMing/lyra/tree/main/modules/email-digest) |
| 产品 release notes、数据库产品情报 | [carina/modules/product-intelligence](https://github.com/LiShuMing/carina/tree/main/modules/product-intelligence) |
| 技术信号、X/Reddit、OpenCLI、日报 | [carina/modules/tech-radar/](https://github.com/LiShuMing/carina/tree/main/modules/tech-radar/) |
| LLM 深度研究报告 | [carina/modules/research-report](https://github.com/LiShuMing/carina/tree/main/modules/research-report) |
| Git 变更分析、仓库收集 | [lyra/modules/developer-tools](https://github.com/LiShuMing/lyra/tree/main/modules/developer-tools)、[lyra/modules/developer-tools](https://github.com/LiShuMing/lyra/tree/main/modules/developer-tools) |
| 投资、周期、股票 | [python/projects/py-cycle-lab/](python/projects/py-cycle-lab/)、[python/projects/py-stock/](python/projects/py-stock/)、[lyra/backend/invest/](https://github.com/LiShuMing/lyra/tree/main/backend/invest/) |
| 心理陪护、对话记忆、微信 | [python/projects/py-ego/](python/projects/py-ego/)、[lyra/backend/ego/](https://github.com/LiShuMing/lyra/tree/main/backend/ego/)、[lyra/backend/wechat/](https://github.com/LiShuMing/lyra/tree/main/backend/wechat/) |
| 个人知识工作台、采集、日报、博客与文库 | [carina](https://github.com/LiShuMing/carina/tree/main) |
| 统一个人工作台、技术雷达、投资与对话 | [lyra/](https://github.com/LiShuMing/lyra/tree/main/) |
| 个人上下文、llm-wiki、Go API | [lyra/llm-wiki/](https://github.com/LiShuMing/lyra/tree/main/llm-wiki/) |
| 桌面学习助手、Tauri | [rust/projects/fragment-tutor/](rust/projects/fragment-tutor/) |
| 地铁线路问答、儿童学习游戏 | [rust/projects/subway-game/](rust/projects/subway-game/) |
| PyTorch、micrograd、自动求导 | [python/projects/py-torch/](python/projects/py-torch/) |
| NumPy、pandas、Jupyter | [python/projects/py-numpy-pandas/](python/projects/py-numpy-pandas/) |
| GPU、CUDA/ROCm、本地模型 | [llm/cuda/](llm/cuda/) |
| Windows 构建、兼容性 | [tools/build-windows.ps1](tools/build-windows.ps1)、[WINDOWS.md](WINDOWS.md) |

## C、C++、汇编及扩展工具

`cc/projects/` 是独立项目集合；其余目录是语言实验室或辅助工具。
保留磁盘上的原始拼写，例如 `extentions`、`py-extention`、`learn-balel`。

| 项目目录 | 用途 | 入口 |
| --- | --- | --- |
| [cc/cclab/](cc/cclab/) | 核心 C++ 实验室；数据结构、并发、协程、COW | [README](cc/cclab/README.md)、[AGENTS](cc/cclab/AGENTS.md)、[CMakeLists](cc/cclab/CMakeLists.txt) |
| [cc/algo/](cc/algo/) | 算法与刷题集合 | [README](cc/algo/README.md)、[Makefile](cc/algo/Makefile) |
| [cc/ccbench/](cc/ccbench/) | C++ benchmark 实验室 | [CMakeLists](cc/ccbench/CMakeLists.txt)、[build.sh](cc/ccbench/build.sh) |
| [cc/srlab/](cc/srlab/) | SR Lab CMake scaffold 与实验；共享第三方依赖 | [README](cc/srlab/README.md)、[CMakeLists](cc/srlab/CMakeLists.txt) |
| [cc/simd/](cc/simd/) | SIMD 指令与性能实验 | [Makefile](cc/simd/Makefile) |
| [go/k8s-lab/](go/k8s-lab/) | 纯标准库 mini Kubernetes 控制面，Go 1.26.2；MVCC、apiserver、informer、controller、kubelet 模拟 | [README](go/k8s-lab/README.md)、[go.mod](go/k8s-lab/go.mod)、[AGENTS](go/k8s-lab/AGENTS.md) |
| [cc/golab/](cc/golab/) | 实际为 Go 算法实验，放在 cc 目录下 | [Makefile](cc/golab/Makefile)、[源码](cc/golab/src/leetcode/) |
| [cc/nasm/](cc/nasm/) | NASM 汇编 hello 与教程 | [Makefile](cc/nasm/Makefile)、[源码](cc/nasm/src/) |
| [cc/projects/cpython/](cc/projects/cpython/) | Python/C/C++ 互操作项目集合 | [README](cc/projects/cpython/README.md) |
| [cc/projects/cpython/cpython/](cc/projects/cpython/cpython/) | 在 C++ 中嵌入 Python | [CMakeLists](cc/projects/cpython/cpython/CMakeLists.txt)、[main.cc](cc/projects/cpython/cpython/main.cc) |
| [cc/projects/cpython/py-extention/](cc/projects/cpython/py-extention/) | Python C API 与 Cython 扩展示例 | [setup.py](cc/projects/cpython/py-extention/setup.py) |
| [cc/projects/cpython/skiplist-extention/](cc/projects/cpython/skiplist-extention/) | SkipList 的 Python 原生扩展 | [CMakeLists](cc/projects/cpython/skiplist-extention/CMakeLists.txt)、[setup.py](cc/projects/cpython/skiplist-extention/setup.py) |
| [cc/projects/interpreter/](cc/projects/interpreter/) | Flex/Bison 词法、语法、AST 与解释执行 | [README](cc/projects/interpreter/README.md)、[CMakeLists](cc/projects/interpreter/CMakeLists.txt) |
| [cc/projects/io-uring/](cc/projects/io-uring/) | Linux io_uring C++20 协程封装 | [README](cc/projects/io-uring/README.md)、[CMakeLists](cc/projects/io-uring/CMakeLists.txt) |
| [vela/storage/](https://github.com/LiShuMing/vela/tree/main/storage/) | TinyKV；MemTable、SkipList、Arena | [README](https://github.com/LiShuMing/vela/blob/main/storage/README.md)、[CMakeLists](https://github.com/LiShuMing/vela/blob/main/storage/CMakeLists.txt) |
| [cc/projects/learn-balel/](cc/projects/learn-balel/) | Bazel 构建学习；主程序、数学库与测试 | [TASK](cc/projects/learn-balel/TASK.md)、[BUILD](cc/projects/learn-balel/BUILD)、[MODULE.bazel](cc/projects/learn-balel/MODULE.bazel) |
| [cc/projects/llvm-jit/](cc/projects/llvm-jit/) | LLVM JIT 表达式编译与性能比较 | [CMakeLists](cc/projects/llvm-jit/CMakeLists.txt)、[源码](cc/projects/llvm-jit/src/) |
| [cc/projects/mini-seastar/](cc/projects/mini-seastar/) | 协程调度、Reactor、Seastar-lite 实验 | [README](cc/projects/mini-seastar/README.md)、[CMakeLists](cc/projects/mini-seastar/CMakeLists.txt) |
| [vela/execution/](https://github.com/LiShuMing/vela/tree/main/execution/) | vagg 向量化查询执行引擎 | [README](https://github.com/LiShuMing/vela/blob/main/execution/README.md)、[CMakeLists](https://github.com/LiShuMing/vela/blob/main/execution/CMakeLists.txt) |
| [cc/projects/thread-pool/](cc/projects/thread-pool/) | WSTP 全局队列与 work-stealing 线程池 | [README](cc/projects/thread-pool/README.md)、[CMakeLists](cc/projects/thread-pool/CMakeLists.txt) |
| [cc/projects/web-server/](cc/projects/web-server/) | Linux/macOS 网络与 I/O 后端实验 | [README](cc/projects/web-server/README.md)、[CMakeLists](cc/projects/web-server/CMakeLists.txt) |
| [cc/projects/write-a-C-interpreter/](cc/projects/write-a-C-interpreter/) | C 编写的自解释 C interpreter | [README](cc/projects/write-a-C-interpreter/README.md)、[xc.c](cc/projects/write-a-C-interpreter/xc.c) |
| [cc/extentions/gdb-extension/](cc/extentions/gdb-extension/) | GDB/StarRocks 调试脚本 | [sr_gdbinit.py](cc/extentions/gdb-extension/sr_gdbinit.py) |
| [cc/extentions/gpt-extension/](cc/extentions/gpt-extension/) | JavaScript/HTML Chrome AI 侧边栏扩展 | [README](cc/extentions/gpt-extension/README.md)、[AGENTS](cc/extentions/gpt-extension/AGENTS.md) |
| [cc/tools/duckdb/](cc/tools/duckdb/) | DuckDB/DuckLake SQL 实验脚本 | [duckdb.sql](cc/tools/duckdb/duckdb.sql) |

算法集合的进一步路由：

| 路径 | 分区 |
| --- | --- |
| [cc/algo/src/algo/](cc/algo/src/algo/) | 基础算法与数据结构 |
| [cc/algo/src/cpp/](cc/algo/src/cpp/) | C++ 语言实验 |
| [cc/algo/src/dailyprogrammer/](cc/algo/src/dailyprogrammer/) | Daily Programmer |
| [cc/algo/src/hackerrank/](cc/algo/src/hackerrank/) | HackerRank |
| [cc/algo/src/highfun/](cc/algo/src/highfun/) | 当前本地新增实验目录；未纳入既有构建清单的可能性需检查 |
| [cc/algo/src/lcr/](cc/algo/src/lcr/) | LCR |
| [cc/algo/src/leetcode/](cc/algo/src/leetcode/) | LeetCode |
| [cc/algo/src/linux/](cc/algo/src/linux/) | Linux 相关练习 |
| [cc/algo/src/msjd/](cc/algo/src/msjd/) | 面试经典题目 |
| [cc/algo/src/oi/](cc/algo/src/oi/) | 竞赛练习 |

`cc/algo/src/include/` 是共享头文件，不是独立项目。

## Rust

| 项目目录 | 用途 | 入口 |
| --- | --- | --- |
| [rust/rlab/](rust/rlab/) | Rust 算法、异步、并发工具工作区 | [README](rust/rlab/README.md)、[workspace Cargo.toml](rust/rlab/Cargo.toml) |
| [rust/rlab/lib/rlab/](rust/rlab/lib/rlab/) | 核心库；排序、数学及语言实验 | [Cargo.toml](rust/rlab/lib/rlab/Cargo.toml) |
| [rust/rlab/tools/rlab-tools/](rust/rlab/tools/rlab-tools/) | 排序 benchmark CLI、DWARF addr2line | [Cargo.toml](rust/rlab/tools/rlab-tools/Cargo.toml)、[源码](rust/rlab/tools/rlab-tools/src/) |
| [rust/rlab/tools/thread-pool/](rust/rlab/tools/thread-pool/) | Rust 线程池、builder 与并发任务 | [README](rust/rlab/tools/thread-pool/README.md)、[Cargo.toml](rust/rlab/tools/thread-pool/Cargo.toml) |
| [rust/rlab/tools/lockfree-queue/](rust/rlab/tools/lockfree-queue/) | MPMC/MPSC API 与 Crossbeam 队列 | [README](rust/rlab/tools/lockfree-queue/README.md)、[Cargo.toml](rust/rlab/tools/lockfree-queue/Cargo.toml) |
| [rust/rlab/tools/bloom_filter/](rust/rlab/tools/bloom_filter/) | Bloom、Split Block、XOR Filter | [Cargo.toml](rust/rlab/tools/bloom_filter/Cargo.toml) |
| [rust/rlab/tools/leetcode/](rust/rlab/tools/leetcode/) | Rust 算法题与题目工具 | [Cargo.toml](rust/rlab/tools/leetcode/Cargo.toml) |
| [rust/rdb/](rust/rdb/) | Rust 数据库；SQL 到执行与存储 | [README](rust/rdb/README.md)、[Cargo.toml](rust/rdb/Cargo.toml) |
| [rust/projects/umbra/](rust/projects/umbra/) | 当前源码是 AI 记忆数据库工作区；README 保留 JIT PoC 规格 | [Cargo.toml](rust/projects/umbra/Cargo.toml)、[源码](rust/projects/umbra/umbra-core/src/lib.rs) |
| [rust/projects/umbra/umbra-core/](rust/projects/umbra/umbra-core/) | AI memory 核心引擎、实体、查询、索引与存储 | [Cargo.toml](rust/projects/umbra/umbra-core/Cargo.toml) |
| [rust/projects/umbra/umbra-server/](rust/projects/umbra/umbra-server/) | Umbra 服务端 | [Cargo.toml](rust/projects/umbra/umbra-server/Cargo.toml) |
| [rust/projects/fragment-tutor/](rust/projects/fragment-tutor/) | FragmentTutor 学习助手；TypeScript/React + Tauri | [README](rust/projects/fragment-tutor/README.md)、[package.json](rust/projects/fragment-tutor/package.json) |
| [rust/projects/fragment-tutor/src-tauri/](rust/projects/fragment-tutor/src-tauri/) | FragmentTutor Rust 桌面后端 | [Cargo.toml](rust/projects/fragment-tutor/src-tauri/Cargo.toml) |
| [rust/projects/subway-game/](rust/projects/subway-game/) | 地铁线路问答游戏；TypeScript/React + Tauri | [README](rust/projects/subway-game/README.md)、[package.json](rust/projects/subway-game/package.json) |
| [rust/projects/subway-game/src-tauri/](rust/projects/subway-game/src-tauri/) | 地铁游戏 Rust 桌面后端 | [Cargo.toml](rust/projects/subway-game/src-tauri/Cargo.toml) |
| [rust/projects/subway-game/subway-data/](rust/projects/subway-game/subway-data/) | 地铁数据构建辅助目录 | [build.sh](rust/projects/subway-game/subway-data/build.sh) |
| [rust/projects/llm-runtime/](rust/projects/llm-runtime/) | LLM 推理、KV cache 与调度设计骨架；尚无 Cargo.toml 或可执行源码 | [README](rust/projects/llm-runtime/README.md)、[TASKS](rust/projects/llm-runtime/TASKS.md) |

## Python

| 项目目录 | 用途 | 入口 |
| --- | --- | --- |
| [python/projects/llm-lab/](python/projects/llm-lab/) | LLM 训练与参考实现 | [README](python/projects/llm-lab/README.md)、[pyproject.toml](python/projects/llm-lab/pyproject.toml) |
| [python/pylab/](python/pylab/) | 核心 Python 实验室、算法、数据库及 benchmark 工具 | [README](python/pylab/README.md)、[AGENTS](python/pylab/AGENTS.md) |
| [python/pylab/dbsp/](python/pylab/dbsp/) | DBSP 增量计算子实验 | [dbsp.py](python/pylab/dbsp/dbsp.py) |
| [python/ivm/](python/ivm/) | 增量视图维护与 join 实验 | [ivm.py](python/ivm/ivm.py) |
| [python/llm_benchmark/](python/llm_benchmark/) | LLM 数学/代码量化评测，含本地 Strata 入口 | [README](python/llm_benchmark/README.md)、[pyproject.toml](python/llm_benchmark/pyproject.toml) |
| [python/projects/py-academic/](python/projects/py-academic/) | 学术论文与 LLM 工具 | [README](python/projects/py-academic/README.md)、[main.py](python/projects/py-academic/main.py) |
| [python/projects/py-cycle-lab/](python/projects/py-cycle-lab/) | LongCycle 长周期投资研究工作台 | [README](python/projects/py-cycle-lab/README.md)、[pyproject.toml](python/projects/py-cycle-lab/pyproject.toml) |
| [python/projects/py-ego/](python/projects/py-ego/) | 对话陪护与记忆；README 同时保留 StarRocks 监控背景 | [README](python/projects/py-ego/README.md)、[main.py](python/projects/py-ego/main.py) |
| [python/projects/py-ego/miniprogram/](python/projects/py-ego/miniprogram/) | 微信小程序前端 | [README](python/projects/py-ego/miniprogram/README.md)、[package.json](python/projects/py-ego/miniprogram/package.json) |
| [python/projects/py-ego/py-ego-miniapp/](python/projects/py-ego/py-ego-miniapp/) | miniapp 服务与部署辅助项目 | [部署说明](python/projects/py-ego/py-ego-miniapp/deploy/README.md) |
| [Lyra email-digest](https://github.com/LiShuMing/lyra/tree/main/modules/email-digest) | Gmail/newsletter 邮件摘要；安装后命令 `my-email` | [README](https://github.com/LiShuMing/lyra/blob/main/modules/email-digest/README.md)、[pyproject.toml](https://github.com/LiShuMing/lyra/blob/main/modules/email-digest/pyproject.toml) |
| [python/projects/py-lab/](python/projects/py-lab/) | Streamlit/LangChain AI 实验平台 | [README](python/projects/py-lab/README.md)、[app.py](python/projects/py-lab/app.py) |
| [Lyra daily-learning](https://github.com/LiShuMing/lyra/tree/main/modules/daily-learning) | Telegram/SQLite 每日学习 Agent | [README](https://github.com/LiShuMing/lyra/blob/main/modules/daily-learning/README.md)、[源码](https://github.com/LiShuMing/lyra/tree/main/modules/daily-learning/src/) |
| [python/projects/py-numpy-pandas/](python/projects/py-numpy-pandas/) | NumPy/pandas Jupyter 学习空间 | [README](python/projects/py-numpy-pandas/README.md)、[notebooks](python/projects/py-numpy-pandas/notebooks/) |
| [python/projects/py-stock/](python/projects/py-stock/) | 股票历史价格采集、SQLite 存储与 Web/CLI 查询 | [README](python/projects/py-stock/README.md)、[cli.py](python/projects/py-stock/cli.py) |
| [python/projects/py-torch/](python/projects/py-torch/) | PyTorch 学习、micrograd、自动求导 | [README](python/projects/py-torch/README.md)、[micrograd](python/projects/py-torch/micrograd/) |
| [python/projects/py-toydb/](python/projects/py-toydb/) | ToyDB 文档数据库 | [README](python/projects/py-toydb/README.md)、[pyproject.toml](python/projects/py-toydb/pyproject.toml) |
| [python/projects/strata-review/](python/projects/strata-review/) | 本地 Strata 只读 Git diff/代码审查 | [README](python/projects/strata-review/README.md)、[strata_review.py](python/projects/strata-review/strata_review.py) |
| [carina/modules/tech-radar/](https://github.com/LiShuMing/carina/tree/main/modules/tech-radar/) | 技术信号采集、SQLite、日报；命令 `tech-radar` | [README](https://github.com/LiShuMing/carina/blob/main/modules/tech-radar/README.md)、[pyproject.toml](https://github.com/LiShuMing/carina/blob/main/modules/tech-radar/pyproject.toml) |
| [python/tools/](python/tools/) | StarRocks 分区/锁日志分析及 Hacker News 示例脚本 | [目录](python/tools/) |
| [vela/optimizer/](https://github.com/LiShuMing/vela/tree/main/optimizer/) | Vela Python 模块；Volcano/Cascades 对照与 join reorder | [README](https://github.com/LiShuMing/vela/blob/main/optimizer/README.md)、[核心代码](https://github.com/LiShuMing/vela/tree/main/optimizer/optimizer/) |
| [lyra/backend/](https://github.com/LiShuMing/lyra/tree/main/backend/) | Lyra 跨语言应用的 Python/FastAPI 后端 | [app.py](https://github.com/LiShuMing/lyra/blob/main/backend/app.py)、[项目配置](https://github.com/LiShuMing/lyra/blob/main/pyproject.toml) |

旧目录与遗留位置：

| 当前目录 | 扫描结果与路由建议 |
| --- | --- |
| `python/projects/py-invest/`（历史路径，当前不存在） | 未发现项目源码或构建清单；投资功能优先查 [lyra/backend/invest/](https://github.com/LiShuMing/lyra/tree/main/backend/invest/) 和 `py-cycle-lab` |
| `python/projects/py-paper/`（历史路径，当前不存在） | `paper-agent/` 下未发现项目源码或构建清单；论文工具优先查 `py-academic` |
| `python/projects/py-radar/`（历史路径，当前不存在） | 不恢复历史输出数据；当前雷达功能见 [lyra/backend/radar/](https://github.com/LiShuMing/lyra/tree/main/backend/radar/) |
| `python/projects/py-scrapy/`（历史路径，当前不存在） | `blog_crawler/` 下未发现项目源码或构建清单 |

## Java、Scala、Groovy

| 项目目录 | 用途 | 入口 |
| --- | --- | --- |
| [java/xlab-iceberg/](java/xlab-iceberg/) | Apache Iceberg 实验 | [README](java/xlab-iceberg/README.md)、[build.gradle.kts](java/xlab-iceberg/build.gradle.kts) |
| [java/xlab-itest/](java/xlab-itest/) | JVM 学习、数据库集成测试和 benchmark 集合 | [README](java/xlab-itest/README.md)、[settings.gradle.kts](java/xlab-itest/settings.gradle.kts) |
| [java/xlab-itest/xlab-framework/](java/xlab-itest/xlab-framework/) | 集成测试框架 | [build.gradle.kts](java/xlab-itest/xlab-framework/build.gradle.kts) |
| [java/xlab-itest/xlab-itest/](java/xlab-itest/xlab-itest/) | 集成测试实现 | [build.gradle.kts](java/xlab-itest/xlab-itest/build.gradle.kts) |
| [java/xlab-itest/xlab-benchmark/](java/xlab-itest/xlab-benchmark/) | JVM/数据库 benchmark | [build.gradle.kts](java/xlab-itest/xlab-benchmark/build.gradle.kts) |
| [java/xlab-itest/xlab-groovy/](java/xlab-itest/xlab-groovy/) | Groovy 实验 | [build.gradle](java/xlab-itest/xlab-groovy/build.gradle) |
| [java/xlab-itest/xlab-interview/](java/xlab-itest/xlab-interview/) | JVM、并发、类加载、面试实验 | [pom.xml](java/xlab-itest/xlab-interview/pom.xml) |
| [java/xlab-itest/xlab-jlib/](java/xlab-itest/xlab-jlib/) | Java 库与数据结构 | [pom.xml](java/xlab-itest/xlab-jlib/pom.xml) |
| [java/xlab-itest/xlab-scala/](java/xlab-itest/xlab-scala/) | Scala 学习实验 | [build.sbt](java/xlab-itest/xlab-scala/build.sbt) |
| [java/xlab-itest/xlab-spark/](java/xlab-itest/xlab-spark/) | Spark/Scala 测试实验 | [pom.xml](java/xlab-itest/xlab-spark/pom.xml) |
| [java/xlab-itest/xlab-spring/](java/xlab-itest/xlab-spring/) | Spring 应用实验 | [README](java/xlab-itest/xlab-spring/README.md)、[pom.xml](java/xlab-itest/xlab-spring/pom.xml) |

当前 Gradle settings 只声明 `xlab-framework`、`xlab-itest`、
`xlab-benchmark`、`xlab-groovy` 四个子项目。其他目录存在独立 Maven/SBT
清单，不能假定根 Gradle 命令会构建它们。

## Go

| 项目目录 | 用途 | 入口 |
| --- | --- | --- |
| [go/k8s-lab/](go/k8s-lab/) | 纯标准库 mini Kubernetes 控制面，Go 1.26.2；MVCC、apiserver、informer、controller、kubelet 模拟 | [README](go/k8s-lab/README.md)、[go.mod](go/k8s-lab/go.mod)、[AGENTS](go/k8s-lab/AGENTS.md) |
| [cc/golab/](cc/golab/) | Go 算法实验，位于 C++ 顶层目录下 | [Makefile](cc/golab/Makefile)、[源码](cc/golab/src/leetcode/) |
| [lyra/llm-wiki/](https://github.com/LiShuMing/lyra/tree/main/llm-wiki/) | 个人上下文维护 POC、CLI 与服务 | [README](https://github.com/LiShuMing/lyra/blob/main/llm-wiki/README.md)、[go.mod](https://github.com/LiShuMing/lyra/blob/main/llm-wiki/go.mod)、[Makefile](https://github.com/LiShuMing/lyra/blob/main/llm-wiki/Makefile) |

[go/SKILL.md](go/SKILL.md) 是语言指南；`go/k8s-lab` 的并发测试应运行 `go test -race ./...`。旧 `go/hello/` 不存在。

## Haskell

| 项目目录 | 用途 | 入口 |
| --- | --- | --- |
| [haskell/hslab/](haskell/hslab/) | Haskell 基础 hello 实验 | [hello.hs](haskell/hslab/hello.hs) |
| [haskell/projects/dsl-transform/](haskell/projects/dsl-transform/) | 数据处理 DSL、Monad Transformers | [dsl-transform.cabal](haskell/projects/dsl-transform/dsl-transform.cabal)、[设计与测试](haskell/projects/dsl-transform/DESIGN_BUILD_TEST_DOC.md) |
| [haskell/projects/sql-parser/](haskell/projects/sql-parser/) | SQL AST、parser 与规则优化实验 | [sql-parser.cabal](haskell/projects/sql-parser/sql-parser.cabal)、[IMPLEMENTATION](haskell/projects/sql-parser/IMPLEMENTATION.md) |
| [haskell/projects/stm-engine/](haskell/projects/stm-engine/) | STM 并发 KV 与聚合引擎 | [README](haskell/projects/stm-engine/README.md)、[stm-engine.cabal](haskell/projects/stm-engine/stm-engine.cabal) |

## JavaScript、TypeScript 与跨语言应用

这些项目分布于 xlab 的其他语言目录和已迁移的独立仓库，前后端应按所属应用一起定位。

| 项目目录 | 技术与用途 | 入口 |
| --- | --- | --- |
| [carina](https://github.com/LiShuMing/carina/tree/main) | Python/FastAPI + PostgreSQL + React/TypeScript；原 Panming | [README](https://github.com/LiShuMing/carina/blob/main/README.md)、[pyproject.toml](https://github.com/LiShuMing/carina/blob/main/pyproject.toml)、[web](https://github.com/LiShuMing/carina/tree/main/web/) |
| [lyra/](https://github.com/LiShuMing/lyra/tree/main/) | React/Vite + Python/FastAPI + Go；统一个人工作台 | [package.json](https://github.com/LiShuMing/lyra/blob/main/package.json)、[pyproject.toml](https://github.com/LiShuMing/lyra/blob/main/pyproject.toml)、[部署说明](https://github.com/LiShuMing/lyra/blob/main/docs/deployment.md) |
| [lyra/src/](https://github.com/LiShuMing/lyra/tree/main/src/) | React 前端页面、组件与客户端逻辑 | [pages](https://github.com/LiShuMing/lyra/tree/main/src/pages/)、[components](https://github.com/LiShuMing/lyra/tree/main/src/components/) |
| [lyra/backend/ego/](https://github.com/LiShuMing/lyra/tree/main/backend/ego/) | 对话、记忆与陪护业务模块 | [目录](https://github.com/LiShuMing/lyra/tree/main/backend/ego/) |
| [lyra/backend/invest/](https://github.com/LiShuMing/lyra/tree/main/backend/invest/) | 投资业务模块 | [cli.py](https://github.com/LiShuMing/lyra/blob/main/backend/invest/cli.py) |
| [lyra/backend/radar/](https://github.com/LiShuMing/lyra/tree/main/backend/radar/) | 技术雷达业务模块 | [cli.py](https://github.com/LiShuMing/lyra/blob/main/backend/radar/cli.py) |
| [lyra/backend/wechat/](https://github.com/LiShuMing/lyra/tree/main/backend/wechat/) | 微信集成业务模块 | [目录](https://github.com/LiShuMing/lyra/tree/main/backend/wechat/) |
| [lyra/llm-wiki/](https://github.com/LiShuMing/lyra/tree/main/llm-wiki/) | Go 个人上下文维护子项目 | [README](https://github.com/LiShuMing/lyra/blob/main/llm-wiki/README.md) |
| [rust/projects/fragment-tutor/](rust/projects/fragment-tutor/) | FragmentTutor TypeScript/React 前端与 Rust/Tauri 后端 | [package.json](rust/projects/fragment-tutor/package.json) |
| [rust/projects/subway-game/](rust/projects/subway-game/) | 地铁游戏 TypeScript/React 前端与 Rust/Tauri 后端 | [package.json](rust/projects/subway-game/package.json) |
| [python/projects/py-ego/miniprogram/](python/projects/py-ego/miniprogram/) | 微信小程序前端 | [package.json](python/projects/py-ego/miniprogram/package.json) |
| [cc/extentions/gpt-extension/](cc/extentions/gpt-extension/) | Chrome AI side panel 扩展 | [README](cc/extentions/gpt-extension/README.md) |

## Shell、GPU 与仓库辅助入口

| 目录或文件 | 用途 | 入口 |
| --- | --- | --- |
| [shell/bin/](shell/bin/) | SSH/SCP、历史记录导出、SQLite 等个人脚本 | [README](shell/bin/README.md) |
| [shell/docker/](shell/docker/) | Docker 与 Folly 构建脚本 | [Dockerfile](shell/docker/Dockerfile)、[build_folly.sh](shell/docker/build_folly.sh) |
| [shell/fio/](shell/fio/) | fio I/O 测试配置 | [1.fio](shell/fio/1.fio)、[build.sh](shell/fio/build.sh) |
| [shell/mysql/](shell/mysql/) | MySQL 并发、TPCH benchmark 脚本 | [目录](shell/mysql/) |
| [llm/cuda/](llm/cuda/) | GPU 诊断、本地模型与 CUDA/ROCm 实验 | [PYTORCH_SETUP.md](llm/cuda/PYTORCH_SETUP.md)、[diagnose_gpu.sh](llm/cuda/diagnose_gpu.sh) |
| [tools/](tools/) | 仓库级工具 | [build-windows.ps1](tools/build-windows.ps1)、[healthcheck.sh](tools/healthcheck.sh) |
| [cmake/](cmake/) | 共享 CMake 依赖与编译选项 | [XlabDependencies.cmake](cmake/XlabDependencies.cmake) |
| [docs/](docs/) | 知识库、技术报告、书籍笔记与技能 | [文档导航与归属](docs/README.md)、[books](docs/books/)、[reports](docs/reports/)、[skills](docs/skills/) |

## 第三方依赖与历史参考目录

下面的路径保留原有参考目录，不能仅凭列表判断源码已恢复。归档决定和消费证据见 [逐项依赖审计](docs/meta/dependency-declarations.md)。
当前 `.gitmodules` 有 **40 个声明、2 个 mode 160000 gitlink、38 个未解决孤立声明**。
29 个经逐项审查的参考/独立包声明已移入完整审计清单，下面仍保留全部历史目录供检索。
其中 5 个孤立路径涉及遗留构建/手工 bootstrap，33 个用途尚未确定；健康检查继续报告失败。
仅 googletest 与 benchmark 可按已固定版本定向初始化；不得批量下载、删除或猜测版本。
见 [依赖消费审计](docs/meta/dependency-declarations.md) 和 [便携依赖](docs/meta/cpp-test-dependencies.md)。

### C 参考项目

历史目录条目共 2 个。

| 名称 | 声明路径 |
| --- | --- |
| chibicc | `c/chibicc` |
| minilisp | `c/minilisp` |

### C++ 依赖与参考项目

历史目录条目共 49 个。

| 名称 | 声明路径 |
| --- | --- |
| C-Plus-Plus | `cc/thirdparty/C-Plus-Plus` |
| ClangBuildAnalyzer | `cc/thirdparty/ClangBuildAnalyzer` |
| Clickhouse | `cc/thirdparty/Clickhouse` |
| Radix-Hash-Join | `cc/thirdparty/Radix-Hash-Join` |
| abseil-cpp | `cc/thirdparty/abseil-cpp` |
| arrow | `cc/thirdparty/arrow` |
| babylon | `cc/thirdparty/babylon` |
| benchmark | `cc/thirdparty/benchmark` |
| boost | `cc/thirdparty/boost` |
| brpc | `cc/thirdparty/brpc` |
| btop | `cc/thirdparty/btop` |
| clang_combined_time_trace | `cc/thirdparty/clang_combined_time_trace` |
| concurrentqueue | `cc/thirdparty/concurrentqueue` |
| datasketch-cpp | `cc/thirdparty/datasketch-cpp` |
| dlmalloc | `cc/thirdparty/dlmalloc` |
| doris | `cc/thirdparty/doris` |
| duckdb | `cc/thirdparty/duckdb` |
| duckdb_ivm | `cc/thirdparty/duckdb_ivm` |
| fast_float | `cc/thirdparty/fast_float` |
| fastgrind | `cc/thirdparty/fastgrind` |
| flight-benchmark | `cc/thirdparty/flight-benchmark` |
| fmt | `cc/thirdparty/fmt` |
| folly | `cc/thirdparty/folly` |
| glog | `cc/thirdparty/glog` |
| googletest | `cc/thirdparty/googletest` |
| gperftools | `cc/thirdparty/gperftools` |
| hardware-effects | `cc/thirdparty/hardware-effects` |
| json | `cc/thirdparty/json` |
| junction | `cc/thirdparty/junction` |
| leveldb | `cc/thirdparty/leveldb` |
| libchef | `cc/thirdparty/libchef` |
| libcoro | `cc/thirdparty/libcoro` |
| liburing4cpp | `cc/thirdparty/liburing4cpp` |
| lua | `cc/thirdparty/lua` |
| mimalloc | `cc/thirdparty/mimalloc` |
| muduo | `cc/thirdparty/muduo` |
| noisepage | `cc/thirdparty/noisepage` |
| parquet-format | `cc/thirdparty/parquet-format` |
| perf-tools | `cc/thirdparty/perf-tools` |
| robin-hood-hashing | `cc/thirdparty/robin-hood-hashing` |
| rocksdb | `cc/thirdparty/rocksdb` |
| seastar | `cc/thirdparty/seastar` |
| simde | `cc/thirdparty/simde` |
| simple-sqlite | `cc/thirdparty/simple-sqlite` |
| sqlite | `cc/thirdparty/sqlite` |
| templight-tools | `cc/thirdparty/templight-tools` |
| velox | `cc/thirdparty/velox` |
| wren | `cc/thirdparty/wren` |
| x86-simd-sort | `cc/thirdparty/x86-simd-sort` |

### Rust 参考项目

历史目录条目共 14 个。

| 名称 | 声明路径 |
| --- | --- |
| arroyo | `rust/thirdparty/arroyo` |
| datafusion | `rust/thirdparty/datafusion` |
| dbeel | `rust/thirdparty/dbeel` |
| denormalized | `rust/thirdparty/denormalized` |
| differential-dataflow | `rust/thirdparty/differential-dataflow` |
| feldera | `rust/thirdparty/feldera` |
| materialize | `rust/thirdparty/materialize` |
| optd | `rust/thirdparty/optd` |
| osblog | `rust/thirdparty/osblog` |
| risingwave | `rust/thirdparty/risingwave` |
| sqleibniz | `rust/thirdparty/sqleibniz` |
| tantivy | `rust/thirdparty/tantivy` |
| timely-dataflow | `rust/thirdparty/timely-dataflow` |
| toydb | `rust/thirdparty/toydb` |

### Python 参考项目

历史目录条目共 4 个。

| 名称 | 声明路径 |
| --- | --- |
| Python | `python/thirdparty/Python` |
| parquet-python | `python/thirdparty/parquet-python` |
| pydbsp | `python/thirdparty/pydbsp` |
| tinydb | `python/thirdparty/tinydb` |

## 索引维护

- 新建、移动或删除项目时，同步更新本文件的目录、用途、入口与任务路由。
- Rust 工作区成员以 `Cargo.toml` 为准，JVM 子项目以各自 Gradle/Maven/SBT 清单为准。
- Python 项目不能只靠 `pyproject.toml` 发现：无打包清单的脚本项目也应保留。
- 有独立业务用途或清单的嵌套项目单独列出；`src/`、`tests/`、`docs/`、
  构建产物、虚拟环境、数据输出通常不是独立项目。
- 第三方目录与依赖审计清单同步；仅需保留的声明在 `.gitmodules` 中。状态必须实际检查，不把参考路径视为已下载。
- 本文件承担项目路由；仓库规则仍以 [AGENTS.md](AGENTS.md) 为准，
  当前工作计划仍以 [TASKS.md](TASKS.md) 为准。

Current retained-project decisions and cleanup boundaries: [classification](docs/meta/retained-projects.md), [consolidated cleanup](docs/meta/repository-cleanup.md).
