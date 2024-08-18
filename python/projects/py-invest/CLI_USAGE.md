# py-invest CLI 使用指南

## 快速开始

### 1. 激活虚拟环境

```bash
cd /Users/lishuming/work/xlab/python/projects/py-invest
source ../.venv/bin/activate
```

### 2. 运行分析

```bash
# 直接使用 Python 运行
python cli.py analyze sh600519 "综合分析"

# 或使用详细模式
python cli.py analyze sh600519 "综合分析" -v

# 分析美股
python cli.py analyze AAPL "估值分析"

# 分析港股
python cli.py analyze 00700.HK "技术分析"
```

### 3. 安装为命令行工具（可选）

```bash
# 在虚拟环境中安装
pip install -e .

# 然后可以直接使用命令
py-invest analyze sh600519 "综合分析"
py-invest version
```

## CLI 命令

### analyze - 股票分析

```bash
py-invest analyze <股票代码> [分析请求] [-v]
```

**参数：**
- `<股票代码>`: 股票代号
  - A 股：`sh600519`, `sz000858`
  - 美股：`AAPL`, `GOOGL`
  - 港股：`00700.HK`, `9988.HK`
- `[分析请求]`: 分析类型（可选，默认：综合分析）
  - `综合分析` - 完整分析报告
  - `技术分析` - K 线和技术指标
  - `估值分析` - 估值和基本面
  - `风险分析` - 风险评估
- `-v, --verbose`: 显示详细进度

**输出：**
- Markdown 格式的投资分析报告
- 包含：投资论点、价格目标、牛/熊/基案例、技术分析、基本面、行业对比、催化剂、风险、评级

### version - 版本信息

```bash
py-invest version
```

## 输出示例

```bash
$ python cli.py analyze sh600519 "综合分析" -v
正在分析股票：sh600519
分析请求：综合分析

# 贵州茅台 (sh600519) Investment Analysis Report

**Generated**: 2026-03-23 15:30
**Model**: qwen3.5-plus
**Duration**: 45.23s

## Summary

核心投资论点...

## Investment Rating

| Metric | Value |
|--------|-------|
| Rating | 👍 Buy |
| Confidence | high |
| Target Price | ¥1850.00 |

## Scenario Analysis

### Bull Case
乐观情景...

### Base Case
基准情景...

### Bear Case
悲观情景...

## Detailed Analysis

### Investment Thesis
...

### Price Target & Methodology
...

### Technical Picture
...

### Fundamental Analysis
...

### Sector & Comparables
...

### Key Catalysts
...

### Risk Factors
...

### Recommendation
...

✓ 分析完成
  股票代码：sh600519
  目标价格：1850.0
  评级：Buy
  章节数：9
```

## 保存报告到文件

```bash
# 保存为 Markdown
python cli.py analyze sh600519 "综合分析" > report.md

# 保存为 JSON
python -c "
from agents.orchestrator import SimpleAgentOrchestrator
from modules.report_generator.formatter import ReportFormatter, ReportFormat
import asyncio

async def main():
    o = SimpleAgentOrchestrator()
    s = await o.analyze('sh600519', '综合分析')
    print(ReportFormatter.format(s.report, ReportFormat.JSON))

asyncio.run(main())
" > report.json
```

## 环境配置

确保 `~/.env` 文件包含有效的 LLM 配置：

```bash
LLM_API_KEY=sk-xxxxxxxxx
LLM_BASE_URL=https://coding.dashscope.aliyuncs.com/v1
LLM_MODEL=qwen3.5-plus
```

## 常见问题

### Q: 分析需要多长时间？
A: 通常 30-60 秒，取决于网络状况和 LLM 响应速度。

### Q: 支持哪些市场？
A: A 股、港股、美股都支持。

### Q: 如何更改分析模型？
A: 修改 `~/.env` 中的 `LLM_MODEL` 配置。

### Q: 为什么 AKShare 数据不可用？
A: AKShare 需要稳定的中国大陆网络连接。如果不可用，系统会自动使用 LLM 估计值并标注 "(estimated)"。
