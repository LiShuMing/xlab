# Implementation Roadmap

## 0. Current Prototype

Status: implemented as a usable local Flask product.

Run:

```bash
cd python/projects/py-cycle-lab
./scripts/run_dev.sh
```

Open:

```text
http://127.0.0.1:19021
```

Implemented:

- Product-style dashboard UI based on the Calm Research Desk design system.
- Overview, Cycle, Valuation, Watchlist, Lab, and Settings pages.
- Native SVG charts and asset valuation heatmap.
- Local sample data payload for first visual validation.
- Local DuckDB persistence at `data/longcycle.duckdb`.
- Watchlist CRUD for investment hypotheses.
- Evidence snapshots for hypothesis review.
- Experiment history for anti-overfitting workflow.
- Monthly review records.
- LLM brief generation and brief history.
- Clickable drill-down drawer for KPI, risk, asset, and historical-period details.
- Asset comparison page with multi-select controls.
- Scenario simulator for rate, valuation, and sentiment rule rehearsal.
- Real-data refresh pipeline using AKShare and local DuckDB cache.
- `~/.env` LLM configuration detection.
- `~/.env` PostgreSQL configuration detection and `psql` CLI probe.
- Optional LLM market-state brief endpoint with saved results.

Real data coverage:

- `bond_zh_us_rate`: US/CN yield curves.
- `stock_index_pe_lg` and `stock_index_pb_lg`: CSI 300 and CSI 500 valuation percentiles.
- `stock_zh_index_daily`: CSI 300 and CSI 500 price-derived sentiment/trend.
- `spot_hist_sge`: gold price-derived sentiment/trend.
- Yield-curve-derived bond/cash proxies.

Not yet implemented:

- Stable S&P 500 / Nasdaq 100 valuation source. Current public endpoints were unavailable in this environment.
- Real statsmodels Markov switching model. Current regime line is derived from real 10Y-2Y spread.
- Real Qlib dataset integration.
- PostgreSQL-backed product storage. The current product uses local DuckDB and only probes PostgreSQL status.

## 1. Build Strategy

Start with a local-first research application. The first implementation should validate the product workflow, not the full technology ambition.

Recommended MVP stack:

- UI: Streamlit.
- Dataframes: pandas.
- Local storage: DuckDB + Parquet.
- Charts: Plotly.
- Macro data: akshare.
- Regime model: statsmodels.
- ML validation: scikit-learn + local PurgedKFold fallback.

Qlib can be introduced once indicator schemas and experiments are stable. It should not block the first visible product loop.

## 2. Milestones

### M0: Product and Design Foundation

Status: current.

Deliverables:

- PRD.
- Product research.
- Information architecture.
- Design system.
- Prototype spec.
- Dashboard concept image.

Exit criteria:

- Engineering can build a Streamlit skeleton from the documents.

### M1: Data Foundation

Goal:

Build local, reproducible data pipelines for the first cycle and valuation indicators.

Deliverables:

- `scripts/fetch_macro_data.py`
- `scripts/build_indicator_panel.py`
- Raw data cache under `data/raw/`.
- Processed indicator panel under `data/processed/`.
- Data source metadata.

Initial data:

- US 10Y yield.
- US 2Y yield.
- 10Y-2Y spread.
- A-share broad index valuation proxies if available.
- US index valuation proxies if available.

Exit criteria:

- One command can refresh sample data.
- Indicator panel includes raw value, percentile, score, source, and update time.

### M2: Cycle Model

Goal:

Reproduce the yield-curve-to-recession mechanism with a visible regime model.

Deliverables:

- Markov switching notebook.
- Scripted model run.
- Model output table.
- Cycle page charts.
- Model card.

Exit criteria:

- User can view yield curve spread, recession shading, and regime probability.
- The UI clearly explains model limitations.

### M3: Valuation Dashboard

Goal:

Create standardized valuation and risk score views across assets.

Deliverables:

- Asset registry.
- Indicator scoring module.
- Valuation matrix.
- Asset detail drawer.

Exit criteria:

- At least 5 assets show comparable percentile-based scores.
- Heatmap colors match the design system and include text labels.

### M4: Watchlist and Hypothesis Journal

Goal:

Turn user views into explicit and reviewable investment hypotheses.

Deliverables:

- Local hypothesis storage.
- Watchlist page.
- Condition checklist.
- Risk list.
- Review note flow.
- Evidence snapshot schema.

Exit criteria:

- User can create, edit, review, and version a hypothesis.
- Action state changes require a note.

### M5: Lab and Anti-Overfitting Workflow

Goal:

Make sample-in vs sample-out fragility visible.

Deliverables:

- Experiment schema.
- PurgedKFold fallback implementation.
- Walk-forward split.
- Sample-in/sample-out metrics.
- Overfitting diagnosis panel.

Exit criteria:

- A demonstration strategy can show attractive sample-in results and weaker sample-out results.
- The report includes leakage and parameter sensitivity warnings.

## 3. Proposed Python Package Layout

```text
src/cycle_lab/
├── data/
│   ├── sources.py
│   ├── registry.py
│   └── storage.py
├── features/
│   ├── percentiles.py
│   ├── scoring.py
│   └── indicators.py
├── regimes/
│   ├── yield_curve.py
│   └── markov.py
├── watchlist/
│   ├── models.py
│   └── store.py
├── cv/
│   ├── purged.py
│   └── walk_forward.py
├── ui/
│   ├── app.py
│   ├── pages/
│   └── components/
└── utils/
    ├── dates.py
    └── logging.py
```

## 4. Data Schema Draft

### 4.1 Indicator Observations

```text
date
asset_id
indicator_id
raw_value
unit
source
updated_at
```

### 4.2 Indicator Scores

```text
date
asset_id
indicator_id
lookback_window
percentile
z_score
opportunity_score
risk_score
data_quality
```

### 4.3 Hypotheses

```text
hypothesis_id
asset_id
title
thesis
action_state
entry_conditions_json
review_conditions_json
risks_json
created_at
updated_at
```

### 4.4 Evidence Snapshots

```text
snapshot_id
hypothesis_id
as_of_date
scores_json
model_state_json
note
created_at
```

### 4.5 Experiments

```text
experiment_id
name
features_json
label_config_json
model_config_json
cv_config_json
sample_in_metrics_json
sample_out_metrics_json
diagnosis_json
created_at
```

## 5. Scoring Rules

Every indicator needs an interpretation direction:

```text
lower_is_opportunity
higher_is_opportunity
lower_is_risk
higher_is_risk
two_sided_extreme_is_risk
```

Example:

- PE percentile: lower can mean more opportunity.
- Sentiment percentile: higher can mean more risk.
- Yield curve inversion: lower spread can mean more macro risk.
- Volatility: extremely high may indicate stress; extremely low may indicate complacency.

Scores must preserve raw values. Never store only the final score.

## 6. Engineering Guardrails

- Keep all data-source functions deterministic and easy to mock.
- Do not let UI pages fetch remote data directly; call service functions.
- Cache raw data before transformation.
- Record source and timestamp for every indicator.
- Separate model fitting from model interpretation.
- Treat `mlfinlab` as optional. Provide local fallback splitters.
- Tests should focus on transformations, scoring, and CV boundaries.

## 7. First Implementation Slice

The first slice should be:

1. Fetch yield curve data.
2. Build 10Y-2Y spread.
3. Compute percentile score.
4. Fit a simple Markov regime model.
5. Render a Streamlit Overview + Cycle page.

This produces a visible product loop before expanding into valuation, watchlist, and Lab.
