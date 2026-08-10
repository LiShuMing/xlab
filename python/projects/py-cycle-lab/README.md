# py-cycle-lab

LongCycle 长周期罗盘：面向个人长期投资者的价值分析与周期研究工作台。

本项目先从产品与研究原型出发，后续再逐步实现数据管道、指标表盘、周期模型、观察清单和过拟合实验室。

## Product Scope

- 周期识别：用收益率曲线和 Markov switching 模型验证宏观周期状态。
- 估值表盘：把估值、利差、情绪、资产表现统一转成历史分位和机会/风险评分。
- 投资假设：把个人长期投资观点结构化为可复盘的观察清单。
- 反过拟合：通过 Purged CV、walk-forward 和样本外验证训练研究纪律。

## Documents

- [Product PRD](docs/product/prd.md)
- [Product Research](docs/product/research.md)
- [Information Architecture](docs/product/information-architecture.md)
- [Design System](docs/design/design-system.md)
- [Prototype Spec](docs/design/prototype.md)
- [Implementation Roadmap](docs/implementation/roadmap.md)

## Current Stage

Stage 2: usable local product.

## Run

```bash
cd python/projects/py-cycle-lab
./scripts/run_dev.sh
```

Then open `http://127.0.0.1:19021`.

The app reads LLM and PostgreSQL settings from environment variables or `~/.env`, but only exposes redacted integration status in the UI.

## Usable Features

- 总览：周期、估值、情绪、现金吸引力、风险信号和资产热力图。
- 下钻抽屉：点击 KPI、风险信号、资产行、历史阶段查看证据和解释。
- 周期：收益率曲线、regime 概率原型图、历史相似阶段详情。
- 估值：统一展示大类资产分位与动作状态，支持权益/防守筛选。
- 对比：多选资产，按估值、情绪、趋势或全部指标横向比较。
- 情景：调整利率、估值、情绪假设，查看动作状态和观察清单触发条件。
- 观察清单：新建、编辑、删除投资假设，维护触发条件、风险清单和复盘备注。
- 证据快照：为投资假设保存当时的市场状态，形成可复盘记录。
- 实验室：保存策略实验和样本内/样本外诊断。
- 复盘：保存月度复盘和关键决策。
- LLM：读取 `~/.env` 中的 LLM 配置，生成并保存市场状态简报。
- 设置：展示 LLM、PostgreSQL 和本地 DuckDB 存储状态。
- 真实数据：通过 AKShare 刷新收益率曲线、A股指数估值/行情、黄金价格、美债/现金收益率代理。

## Implementation Notes

The implementation uses Flask plus native HTML/CSS/JavaScript to avoid a heavy frontend toolchain. Product state is persisted in local DuckDB at `data/longcycle.duckdb`.

Real data can be refreshed with:

```bash
./scripts/refresh_real_data.py --start-date 20100101
```

Current real-data coverage:

- Yield curve: `akshare.bond_zh_us_rate`.
- CSI 300 / CSI 500 PE, PB, ERP proxy, trend, sentiment proxy: `stock_index_pe_lg`, `stock_index_pb_lg`, `stock_zh_index_daily`.
- Gold trend and sentiment proxy: `spot_hist_sge`.
- US bond and cash proxy: `bond_zh_us_rate`.

Current limitation: S&P 500 and Nasdaq 100 public endpoints were unavailable from the current environment, so their PE/PB fields are intentionally shown as unavailable rather than filled with seed values.
