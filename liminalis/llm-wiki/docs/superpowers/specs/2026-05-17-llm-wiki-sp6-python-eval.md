# SP6 — Python eval 层骨架

- **状态**: Draft
- **创建**: 2026-05-17
- **关联**: RFC-001-v2 §9; SP2, SP3

## 当前状态

| 目录 | 状态 |
|------|------|
| `python/` | 3 个子目录全空 |
| `evals/golden/` | 3 个子目录全空 |
| `evals/cases/` | 空 |
| `evals/fixtures/` | 空 |
| `evals/reports/` | 存在但无产出 |
| `Makefile` | 无 `eval-py` 目标 |

## 目标

落成 Python eval 层可运行骨架，能跑通 demo 数据并产出 markdown 报告。

1. **Eval scripts**: 4 个 eval runner（extraction/privacy/matching/bridge）+ report.py
2. **Providers**: 3 个 mock provider（qwen/doubao/local_model），返回固定输出
3. **Schemas**: pydantic models 对齐 Go domain 类型
4. **Golden cases**: bridge/photo_extract/summary 各 1 份
5. **Samples**: cases + fixtures 各 1 份
6. **Makefile**: `make eval-py` 一键运行

## 架构

```
python/
  eval/
    run_extraction_eval.py    — 照片上下文提取评测
    run_privacy_eval.py       — 隐私检查评测
    run_matching_eval.py      — 匹配质量评测
    run_bridge_eval.py        — 桥接生成评测
    report.py                 — 汇总报告生成
  providers/
    __init__.py
    qwen.py                   — 通义千问 mock
    doubao.py                 — 豆包 mock
    local_model.py            — 本地模型 mock
  schemas/
    __init__.py
    domain.py                 — pydantic: ContextItem, MatchResult, BridgeResult, PhotoExtraction

evals/
  golden/
    bridge/                   — bridge 期望输出
    photo_extract/            — 照片提取期望输出
    summary/                  — 摘要期望输出
  cases/                      — eval case 定义
  fixtures/                   — 测试数据
  reports/                    — 报告输出目录
```

## 范围外

- 不实现真实 API 调用（全部 mock）
- 不计算完整指标（BLEU/ROUGE 等）
- 不对接真实 Go 服务（纯 Python 独立运行）

## 成功标准

1. `make eval-py` 跑完 4 个 suite 无 fatal error
2. 每个 suite 至少处理 1 个 case
3. `evals/reports/` 产出 markdown 报告
4. pydantic schema 与 Go domain 字段对齐
5. 所有 Python 文件可 import 无语法错误
