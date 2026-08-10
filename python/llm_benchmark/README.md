# LLM Benchmark

基于 OpenAI-compatible API 的 LLM 量化评测框架，自动评估模型的数学推理和编程能力。

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
