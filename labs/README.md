# labs —— 按主题组织的实验

这里按「要搞懂的机制」组织，不按「用什么语言写」组织。每个实验自包含：进入目录就能
构建、运行、复现结论，不读父目录，也不依赖同仓库的其它语言目录。

| 主题 | 内容 | 入口 |
| --- | --- | --- |
| `linux/` | 内核机制的用户态镜像：延迟缺页 → 页表遍历 → TLB（Translation Lookaside Buffer）→ RCU（Read-Copy-Update）宽限期 | [linux/README.md](linux/README.md) |
| `llm/` | 大语言模型（Large Language Model）：环境、训练、评测三阶段，外加 PyTorch 与 NumPy/pandas 基础 | [llm/README.md](llm/README.md) |
| `daft/` | Daft 列式执行引擎的可复现实验 | [daft/README.md](daft/README.md) |
| `interpreter/` | 源码到结果的三条路：树遍历解释、自举解释、LLVM（Low Level Virtual Machine）后端 JIT（Just-In-Time compilation，即时编译） | [interpreter/README.md](interpreter/README.md) |
| `async-io/` | Linux 异步 I/O 的库与服务两层：io_uring 协程封装 + io_uring / kqueue 双后端服务器 | [async-io/README.md](async-io/README.md) |
| `runtime/` | 两种调度模型：单线程 reactor 与 work-stealing 线程池 | [runtime/README.md](runtime/README.md) |

## 放什么

| 你手上的东西 | 放哪 | 判据 |
| --- | --- | --- |
| 练某语言的语法、标准库、工具链 | `cc/`、`python/`、`rust/`、`go/` … | 换语言后练习失去意义 |
| 搞懂某个机制、系统或产品 | `labs/<topic>/` | 换语言实现后主题依然成立 |
| 结论性知识，没有可执行代码 | `docs/` | 删掉代码后内容依然成立 |
| 仓库自身的维护脚本 | `tools/` | 服务于仓库，不服务于某个主题 |

`labs/` 只收「以理解机制为目的、需要多语言或多阶段对照」的实验。单一语言的完整应用
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
```
