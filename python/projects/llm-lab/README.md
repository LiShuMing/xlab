# LLM Lab

可在 CPU / Apple Silicon MPS 上运行的小型语言模型学习项目。实现 UTF-8 字节 tokenizer、bigram、Tiny Transformer、训练与恢复、验证和无缓存生成。

模型用于学习计算与训练链路；内置数据是原创合成句子，不代表通用语言或聊天能力。

## 安装

在本目录执行：

```bash
./scripts/setup.sh
```

安装脚本将 uv、Python 3.12、虚拟环境和下载缓存放在本项目内，不修改系统 Python 或 shell 配置。依赖由 `uv.lock` 固定。首次运行需要网络与磁盘空间。

## 快速运行

```bash
# 环境和 MPS 可用性
.venv/bin/llm-lab doctor

# CPU：2 层、64 维 Tiny Transformer，内置合成数据
.venv/bin/llm-lab train --config configs/tiny.toml --out runs/tiny --device cpu

# 生成和验证
.venv/bin/llm-lab generate --checkpoint runs/tiny/last.pt --prompt "Ada likes "
.venv/bin/llm-lab evaluate --checkpoint runs/tiny/last.pt

# M4 GPU（明确请求 MPS；不可用则报错）
.venv/bin/llm-lab train --config configs/tiny.toml --out runs/tiny-mps --device mps

# Bigram 对照
.venv/bin/llm-lab train --config configs/bigram.toml --out runs/bigram

# 从第 300 步恢复到总计 400 步
.venv/bin/llm-lab train --config configs/tiny.toml --resume runs/tiny/last.pt --steps 400 --out runs/resumed

# 测试与静态检查
.venv/bin/pytest -q
.venv/bin/ruff check src tests
```

也可添加 `--data path/to/corpus.txt`，每个非空行是一篇文档，至少四篇不同文档。先去重并划分文档，再生成窗口；短文档 padding 不参与 loss。验证和恢复必须提供相同的 `--data`。

## 产物与限制

训练输出 `last.pt` 和 `report.json`，记录配置、环境、数据哈希、初始/最终验证 loss 和训练时间。`--steps` 表示总目标步数。CPU 下提供精确恢复测试；暂不承诺跨设备训练完全一致。

生成入口与训练保持一致，显式在 prompt 前添加 BOS（占一个上下文位置）。生成默认 greedy；可用 `--temperature 0.8 --seed 42` 采样。仅生成时屏蔽 BOS/PAD，原始模型 logits 不变。超过上下文的 prompt 报错；生成到容量边界返回 `context_limit`，不滚动截断。随机字节组合可能显示替换字符。

检查点仅用于可信本地文件，采用 restricted weights-only 加载；尚不是跨语言 bundle。KV Cache、导出器、Rust 对照和系统性性能评测尚未实现。

## 文档与目录

- [ARCHITECTURE.md](ARCHITECTURE.md)：计算结构与实现边界。
- [TASKS.md](TASKS.md)：阶段进度。
- [模型产物契约](docs/artifact-contract.md)：未来 Python/Rust 交换格式。
- [experiments/](experiments/)：本机验收记录。
- `src/llm_lab/`：模型、数据、训练、检查点、生成、CLI。
- `configs/`：Tiny / Bigram 配置；`tests/`：数值与恢复测试。

## 与 Rust 的关系

[llm-runtime](../../../rust/projects/llm-runtime/README.md) 仍为独立设计骨架。运行本项目无需 Rust；未来通过模型文件与固定参考 logits 对照，不通过 FFI 绑定。

## 参考

[nanochat](https://github.com/karpathy/nanochat)、[nanoGPT](https://github.com/karpathy/nanoGPT)、[PyTorch MPS](https://docs.pytorch.org/docs/stable/notes/mps.html)。本实现是针对学习场景独立编写的简化模型。
