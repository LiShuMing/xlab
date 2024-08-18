# py-invest 快速使用指南

## 运行方式

### 方式 1: 直接运行（推荐）

```bash
cd /Users/lishuming/work/xlab/python/projects/py-invest
source ../.venv/bin/activate

# 分析股票
python cli.py analyze sh600519 "综合分析"
```

### 方式 2: 保存报告

```bash
# 保存到 Markdown 文件
python cli.py analyze sh600519 "综合分析" > report.md

# 查看报告
cat report.md
```

### 方式 3: 详细模式

```bash
python cli.py analyze sh600519 "综合分析" -v
```

## 输出示例

运行成功后会看到类似输出：

```
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
...

### Base Case
...

### Bear Case
...

## Detailed Analysis
...
```

## 常用命令

```bash
# A 股
python cli.py analyze sh600519 "综合分析"     # 贵州茅台
python cli.py analyze sh600036 "综合分析"     # 招商银行

# 美股
python cli.py analyze AAPL "估值分析"          # 苹果
python cli.py analyze NVDA "技术分析"          # 英伟达

# 港股
python cli.py analyze 00700.HK "综合分析"     # 腾讯
```

## 环境检查

确保配置正确：

```bash
# 检查 ~/.env 文件
cat ~/.env | grep LLM

# 应该看到类似：
# LLM_API_KEY=sk-xxx
# LLM_BASE_URL=https://coding.dashscope.aliyuncs.com/v1
# LLM_MODEL=qwen3.5-plus
```

## 故障排除

### 问题：API key is required
**解决**：检查 `~/.env` 文件中是否有 `LLM_API_KEY` 配置

### 问题：分析超时
**解决**：分析通常需要 30-60 秒，耐心等待。如果超过 2 分钟，检查网络连接。

### 问题：找不到模块
**解决**：确保激活了虚拟环境 `source ../.venv/bin/activate`
