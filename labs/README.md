# labs —— 按主题组织的实验

这里按「要搞懂的机制」组织，不按「用什么语言写」组织。每个实验自包含：进入目录就能
构建、运行、复现结论，不读父目录，也不依赖同仓库的其它语言目录。

| 主题 | 内容 | 入口 |
| --- | --- | --- |
| `linux/` | 内核机制的用户态镜像：延迟缺页 → 页表遍历 → TLB（Translation Lookaside Buffer）→ RCU（Read-Copy-Update）宽限期，以及 Rust kernel-lens 配置总览、实时观测与可选基准 | [linux/README.md](linux/README.md) |
| `llm/` | 大语言模型（Large Language Model）：环境、训练、评测三阶段，外加 PyTorch 与 NumPy/pandas 基础 | [llm/README.md](llm/README.md) |
| `hashmap/` | 哈希表策略、固定键 perfect hash 对照与离线性能报告 | [hashmap/README.md](hashmap/README.md) |
| `daft/` | Daft 列式执行引擎的可复现实验 | [daft/README.md](daft/README.md) |
| `interpreter/` | 源码到结果的三条路：树遍历解释、自举解释、LLVM（Low Level Virtual Machine）后端 JIT（Just-In-Time compilation，即时编译） | [interpreter/README.md](interpreter/README.md) |
| `async-io/` | Linux 异步 I/O 的库与服务两层：io_uring 协程封装 + io_uring / kqueue 双后端服务器 | [async-io/README.md](async-io/README.md) |
| `runtime/` | 两种调度模型：单线程 reactor 与 work-stealing 线程池 | [runtime/README.md](runtime/README.md) |
| `k8s-lab/` | 从零实现的 mini Kubernetes 控制面：MVCC 存储、apiserver、informer、workqueue、ReplicaSet 控制器、kubelet 模拟 | [k8s-lab/README.md](k8s-lab/README.md) |
| `ivm/` | 增量视图维护（Incremental View Maintenance）：join 的增量公式与 DBSP（Database Stream Processing）代数结构原型 | [ivm/README.md](ivm/README.md) |
| `lowlevel/` | 贴硬件的优化：SIMD（Single Instruction Multiple Data，单指令多数据）的标量/SSE（Streaming SIMD Extensions）/AVX2（Advanced Vector Extensions 2）写法对照，NASM（Netwide Assembler）系统调用与 libc 链接教程，LLVM（Low Level Virtual Machine）IR（Intermediate Representation，中间表示）与自写优化 pass 插件 | [lowlevel/README.md](lowlevel/README.md) |

## 放什么

| 你手上的东西 | 放哪 | 判据 |
| --- | --- | --- |
| 练某语言的语法、标准库、工具链 | `cc/`、`python/`、`rust/`、`go/` … | 换语言后练习失去意义 |
| 搞懂某个机制、系统或产品 | `labs/<topic>/` | 换语言实现后主题依然成立 |
| 结论性知识，没有可执行代码 | `docs/` | 删掉代码后内容依然成立 |
| 仓库自身的维护脚本 | `tools/` | 服务于仓库，不服务于某个主题 |

`labs/` 收「以理解机制为目的」的实验：既可以是同一机制的多语言实现，也可以是单一语言的
机制复现（如 `k8s-lab/` 复现 Kubernetes 控制面）。面向交付的完整应用
（`python/projects/py-toydb`、`py-ego`、`py-stock` 等）留在语言目录：语言就是它们的组织维度。

## 内部约定

1. **语言不出现在主题层。** `labs/linux/` 下直接是实验；只有同一实验存在第二种语言实现时，
   才在叶子层出现 `c/`、`rust/`、`python/`。
2. **实验是单元，不是库。** 每个实验自带源码与运行说明；`labs/<topic>/Makefile` 只做调度，
   不写编译细节。
3. **共享代码只能上提。** 同主题共享放 `labs/<topic>/common/`，跨主题共享放 `labs/libs/`；
   禁止用 `..` 越出本主题去引用兄弟语言目录（`python/`、`cc/`、`rust/` 等）。
4. **每个实验可单独删除。** 删掉任一语言目录、或删掉另一个主题，本实验的构建与运行不变。
   这条由 `tools/test_lab_isolation.py` 守着。
5. **环境写清楚。** 前置条件（内核版本、glibc、CUDA（Compute Unified Device Architecture）、
   Python 版本）写在实验 README 顶部，不假设宿主环境。

## 快速开始

```sh
make -C labs/linux all          # 页表 / TLB 实验 + RCU 模拟
make -C labs/linux run_rcu      # 跑 RCU 的三个场景
cd labs/llm/bench && python -m pytest tests -q
cd labs/llm/train && ./scripts/setup.sh
cd labs/daft && ./env.sh
cd labs/k8s-lab && go run ./cmd/demo   # mini Kubernetes 控制面
cd labs/ivm && python3 -m unittest discover -s pyivm -p 'test_*.py'   # IVM join 用例
make -C labs/lowlevel     # SIMD 基准、NASM 教程与 LLVM IR 实验（需 AVX2、NASM 2.x 与 LLVM 18）
```
