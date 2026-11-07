# llm —— 大语言模型实验：三段主线与两块基础

同一个主题的五块工作：`env/` → `train/` → `bench/` 按「先能装、再能训、后能评」排列，
`torch/` 与 `numpy-pandas/` 是训练前的两项基本功。五者互不依赖：只做评测不需要训练环境，
只做训练也不必先准备 GPU（Graphics Processing Unit）。

| 目录 | 做什么 | 前置 | 入口 |
| --- | --- | --- | --- |
| `env/` | GPU / CUDA（Compute Unified Device Architecture）/ ROCm（Radeon Open Compute）环境搭建、卡诊断脚本与本地模型笔记 | 按需 | [ENABLE_GPU.md](env/ENABLE_GPU.md)、[diagnose_gpu.sh](env/diagnose_gpu.sh) |
| `train/` | 从零实现 UTF-8 字节 tokenizer、bigram、Tiny Transformer 的训练与生成 | Python 3.11+，CPU（Central Processing Unit）即可，MPS（Metal Performance Shaders）/ CUDA 可选 | [train/README.md](train/README.md)、`./scripts/setup.sh` |
| `bench/` | 通过 OpenAI-compatible API 评测 MATH、GSM8K、HumanEval、MBPP | Python 3.11+、可访问模型的 API key | [bench/README.md](bench/README.md) |
| `torch/` | micrograd 从零实现反向自动求导，PyTorch 张量、`nn`、训练循环到 CIFAR-10 的教程与测试 | Python 3.11+，CPU 即可 | [torch/README.md](torch/README.md) |
| `numpy-pandas/` | NumPy 数组与 pandas `DataFrame` 的 Jupyter 学习空间 | Python 3.11+、JupyterLab | [numpy-pandas/README.md](numpy-pandas/README.md) |

## 为什么放在一起

五者回答同一个问题的五个阶段：**模型怎么装起来、基础怎么打、怎么训出来、训完到底多强**。按语言目录
切分会把 `env` 留在顶层 `llm/`、`train` 放进 `python/projects/`、`bench` 放进 `python/`，
于是旧 `PROJECTS.md` 只能写一句话来解释「谁负责什么」才能让人找全。`torch/` 与
`numpy-pandas/` 原先也散在 `python/projects/`，但它们是训练的配套练习而非独立应用，
按语言分类只会把「学 PyTorch」和「训模型」拆到两个入口。

## 独立边界

- `train/` 与 `bench/` 各自带 `pyproject.toml` 和测试，可以单独安装、单独删除：
  删掉 `bench` 不影响 `train` 的 setup，反之亦然。
- `torch/` 与 `numpy-pandas/` 各自带 `requirements.txt`、`.gitignore`，前者还有
  `tests/`，同样可以单独建虚拟环境、单独删除。
- `env/` 只有文档与诊断脚本，没有构建入口，也不需要构建。
- 五者之间不共享代码。真出现共享时上提到 `labs/llm/common/`，不允许 `train` 直接
  import `bench` 的实现。
