# LLM Benchmark

基于 OpenAI-compatible API 的 LLM 量化评测框架，自动评估模型的数学推理和编程能力。

## 当前本地 Strata：推荐入口

新增 `strata` 命令用于本机部署模型的可审计评测。它不读取 `~/.env`，不需要 Key，
默认访问 `http://127.0.0.1:8080/v1`，禁用代理继承和推理重试，严格串行调用。
没有修改 Strata 的服务配置、GPU 驱动或系统代理。

在 WSL 中运行：

```bash
cd python/llm_benchmark
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'

# 同一组固定抽样问题，对比不同思考等级。
.venv/bin/llm-bench strata --dataset gsm8k --max-samples 8 --seed 42 --effort none
.venv/bin/llm-bench strata --dataset gsm8k --max-samples 8 --seed 42 --effort low

# Ubuntu amd64：仅在项目 .tools 中解包校验过的 Bubblewrap，不安装系统包。
.venv/bin/python -m llm_benchmark.prepare_bwrap
.venv/bin/llm-bench strata --dataset humaneval --max-samples 8 --seed 42 --effort none

# 按需扩大样本，默认每题最多 2048 输出 tokens、600 秒超时。
.venv/bin/llm-bench strata --dataset gsm8k --max-samples 100 --effort low
.venv/bin/python -m pytest -q
```

数据取自官方仓库固定 commit，并检查 SHA256：GSM8K 共 1319 道测试题，
HumanEval 共 164 道。抽样采用 `random.Random(seed).sample`，不包含重复题；
更改样本数会更改选中列表，以 JSON 中记录的 indices 为准。
生成提示词不含参考解答或隐藏测试。可用 `--data-path` 提供同格式本地 JSONL，
报告会明确标记为用户数据，而不是官方版本。

GSM8K 只比较最后的 `####` 数字（或纯数字回答），不用推理中间数字判分。
HumanEval 每题生成一次、执行官方 check，报告实际 pass@1；不虚构 pass@5/10。
代码评测先检查隔离策略，并验证选中题目的标准解答都能通过测试。
没有隔离执行器就拒绝运行，不退回旧的子进程执行方式。

隔离策略包括用户/进程/网络命名空间、只读系统运行库、无 home/项目目录挂载、
清空环境、禁止新用户命名空间和移除 capabilities。每次候选执行限制为
256 MiB 地址空间、5 秒 CPU、10 秒墙钟时间，tmpfs 8 MiB，输出文件 1 MiB。
它不是虚拟机，不适合用于执行刻意攻击内核或破坏评分器的恶意代码。

每次运行创建独立结果目录，逐题即时保存 `samples.jsonl`，最后生成完整 JSON 和
`report.html`。JSON 包含数据版本、抽样题号、参数、响应正文、思考、截断状态、
API 耗时、token 数和服务端 timings。截断答案记 0 分；传输异常会停止提交，
保留已完成的结果。API 延迟包含排队、输入和思考，不能当成纯 decode 速度。
HTML 的图表使用外部 Chart.js CDN，离线时仍可阅读表格和指标。

### 首轮实测：2026-10-07

当前模型：`qwen3.8-flash-next-coder-iq1_m`；温度 0、seed 42、repeat 1、并发 1。

| 数据集 | 思考等级 | 官方评分 | 平均 API 耗时 | 超时/截断 |
|---|---|---|---|---|
| GSM8K 抽样 8 题 | none | 7/8（87.5%） | 11.38 秒/题 | 0/0 |
| GSM8K 同样 8 题 | low | 7/8（87.5%） | 9.89 秒/题 | 0/0 |
| HumanEval 抽样 8 题 | none | pass@1 = 8/8 | 5.33 秒/题 | 0/0 |

报告保存在 `results/strata-20261007/` 的独立运行目录中。
GSM8K 的两组 indices 都是 `[1309, 228, 51, 563, 501, 457, 285, 209]`；
HumanEval 是 `[163, 28, 6, 70, 62, 57, 35, 26]`。

**数据质量发现：** GSM8K 的零基索引 1309 存在参考解答错误。题目给出的金额为
750、430、700、300，应合计 2180；原始解答求和时把 Sarah 的 300 写成 400，
因而参考标签为 2280。模型在 none/low 两组都回答 2180，因此被官方标签判错。
保留原始 7/8 分数，不悄悄修改标签；人工核对备注应与原始评分分开看。
原始数据来源：
[固定版本 GSM8K](https://github.com/openai/grade-school-math/blob/3101c7d5072418e28b9008a6636bde82a006892c/grade_school_math/data/test.jsonl)。

样本太小，不能据此推断完整基准分数或排名。思考对照按 none 后 low 的顺序运行，
没有随机交错或独立热身，耗时差异可能受缓存和系统负载影响，不能证明 low 更快。
温度 0 的 repeat 也不等于独立随机采样。

**旧路径提醒：** 下方旧 `run` / `compare-models` 命令保留兼容性，但其原有
`CodeSandbox` 只是临时目录和子进程，不隔离文件系统/网络，也未执行声明的内存限制。
不要用旧路径在普通用户环境中执行未经审核的模型代码；本地代码评测应使用新 `strata` 入口。

## 评测能力

| 维度 | 数据集 | 题数 | 指标 |
|------|--------|------|------|
| 数学推理 | MATH (5 级难度) | 5,000 | Exact Match / Numeric Tolerance |
| 数学推理 | GSM8K | 1,319 | Exact Match |
| 编程能力 | HumanEval | 164 | pass@k (k=1,5,10) |
| 编程能力 | MBPP | 500 | pass@k (k=1,5,10) |

## 快速开始

### 1. 安装

```bash
cd python/llm_benchmark
pip install -e ".[dev]"
```

### 2. 配置 API

在 `~/.env` 中添加 LLM API 配置：

```bash
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-your-api-key
LLM_MODEL=gpt-4
LLM_MAX_CONCURRENT=4
```

支持多模型（用于横向对比）：

```bash
LLM_MODEL_1=gpt-4,https://api.openai.com/v1,sk-key-1
LLM_MODEL_2=deepseek-v3,https://api.deepseek.com/v1,sk-key-2
```

### 3. 运行评测

```bash
# 运行所有数据集
llm-bench run --dataset all

# 运行单个数据集
llm-bench run --dataset math --model gpt-4

# 稳定性验证（重复 3 次）
llm-bench run --dataset humaneval --repeat 3 --num-samples 5

# 限制样本数（快速测试）
llm-bench run --dataset gsm8k --max-samples 10

# 并发请求提升吞吐
llm-bench run --dataset gsm8k --max-samples 100 --max-concurrent 8
```

### 4. 查看结果

```bash
# 列出所有数据集
llm-bench list

# 对比两次结果
llm-bench compare results/math_model-a.json results/math_model-b.json

# 在同一个 OpenAI-compatible endpoint 下对比多个模型
llm-bench compare-models \
  --models qwen3.7-max,qwen3.8 \
  --dataset all \
  --max-samples 10 \
  --max-concurrent 8 \
  --repeat 1

# 生成 HTML 可视化报告
llm-bench report results/math_gpt-4_2026-01-01T00-00-00.json
```

## 项目结构

```
llm_benchmark/
├── cli.py                  # CLI 入口 (click)
├── config.py               # ~/.env 配置加载
├── api/
│   ├── client.py           # OpenAI-compatible 客户端
│   └── retry.py            # 指数退避重试
├── datasets/
│   ├── base.py             # 抽象基类 + 注册机制
│   ├── math_dataset.py     # MATH
│   ├── gsm8k_dataset.py    # GSM8K
│   ├── humaneval_dataset.py
│   └── mbpp_dataset.py
├── metrics/
│   ├── math_metrics.py     # exact_match, numeric_match
│   └── code_metrics.py     # pass@k
├── runner/
│   ├── executor.py         # 评测编排器
│   └── sandbox.py          # 代码执行沙箱
└── reporter/
    ├── json_reporter.py    # 版本化 JSON 输出
    └── html_reporter.py    # HTML 可视化报告
```

## 扩展新数据集

添加新数据集仅需 3 步，约 15 分钟：

```python
# 1. 创建 datasets/my_dataset.py
from llm_benchmark.datasets.base import Dataset, register_dataset

@register_dataset("my_dataset")
class MyDataset(Dataset):
    name = "my_dataset"

    def load(self):
        # 加载数据
        ...

    def __len__(self):
        return len(self._data)

    def get_prompt(self, idx: int) -> str:
        # 构建 prompt
        ...

    def get_reference(self, idx: int) -> str:
        # 返回参考答案
        ...

    def get_category(self) -> str:
        return "math"  # 或 "code"

# 2. 在 datasets/__init__.py 中导入
from llm_benchmark.datasets import my_dataset

# 3. 运行
llm-bench run --dataset my_dataset
```

## 配置参考

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `LLM_BASE_URL` | `https://api.openai.com/v1` | API 基础 URL |
| `LLM_API_KEY` | (必填) | API 密钥 |
| `LLM_MODEL` | (必填) | 默认模型名 |
| `LLM_MAX_CONCURRENT` | 4 | 最大并发请求数 |
| `LLM_TIMEOUT` | 120 | 单次请求超时（秒） |
| `LLM_MAX_TOKENS` | 4096 | 单次响应最大 token 数 |

## 运行测试

```bash
pytest tests/ -v
```

## 许可证

MIT
