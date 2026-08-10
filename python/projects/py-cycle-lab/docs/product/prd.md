# LongCycle PRD

## 1. Product Summary

LongCycle 长周期罗盘 is a personal long-term investment value analysis platform. It helps an individual investor understand market cycle state, compare asset valuation, maintain investment hypotheses, and learn research discipline through sample-out validation.

The product is not a short-term trading terminal and does not issue buy/sell recommendations. It is a research workstation for answering four recurring questions:

1. What cycle regime are we in?
2. Which assets are cheap, neutral, or crowded on a long historical basis?
3. Are my current investment hypotheses still valid?
4. Is a strategy actually robust, or just overfit to historical data?

## 2. Target Users

### 2.1 Long-Term Index Investor

- Holds broad index funds, ETFs, bonds, gold, and cash-like assets.
- Wants to avoid buying aggressively during expensive and crowded periods.
- Needs a quiet monthly or weekly dashboard instead of intraday market noise.

Primary jobs:

- Understand whether an asset is in an accumulation, observation, or caution zone.
- Compare major assets using one normalized framework.
- Record why a recurring contribution or rebalance decision was made.

### 2.2 Value-Oriented Stock or Sector Investor

- Studies companies, sectors, and long-term valuation.
- Needs a structured place to maintain thesis, risks, and trigger conditions.
- Wants to avoid thesis drift and post-hoc rationalization.

Primary jobs:

- Convert a research opinion into explicit conditions.
- Track whether valuation, cycle, and sentiment support the thesis.
- Review decisions after the thesis succeeds, fails, or becomes stale.

### 2.3 Quant-Curious Researcher

- Tests factors, timing rules, and allocation rules.
- Has enough skill to overfit and needs guardrails against self-deception.
- Wants Purged CV, walk-forward validation, and sample-out comparison.

Primary jobs:

- Build a strategy hypothesis.
- See sample-in and sample-out results side by side.
- Understand parameter instability and overfitting risk.

## 3. Product Positioning

LongCycle is:

- A cycle-aware personal investment research desk.
- A standardized valuation and risk dashboard.
- A hypothesis journal with evidence and revision history.
- A research discipline trainer for overfitting awareness.

LongCycle is not:

- A brokerage app.
- A real-time trading system.
- A social feed.
- A stock-picking recommendation engine.
- A black-box market prediction product.

## 4. Core Product Principles

### 4.1 State, Not Prediction

The product should describe the current state and its historical context. It should not claim to forecast exact market turning points.

Example:

> Yield curve behavior suggests macro risk premium should be higher than normal.

Avoid:

> A recession will start in September.

### 4.2 Evidence Before Action

Every conclusion must be backed by visible evidence:

- Raw indicator value.
- Historical percentile.
- Directional interpretation.
- Source and update time.
- Limitation or caveat.

### 4.3 Long-Term Language

Avoid trading verbs where possible. Use decision states:

- Observe.
- Accumulate gradually.
- Pause adding.
- Rebalance review.
- Thesis needs review.
- Hypothesis invalidated.

### 4.4 Anti-Overfitting by Design

Strategy research must show sample-in and sample-out performance together. A visually beautiful backtest must be treated as incomplete unless it survives strict out-of-sample validation.

## 5. MVP Scope

### 5.1 Dashboard

The dashboard summarizes cycle, valuation, sentiment, and portfolio/watchlist status.

Core components:

- Cycle temperature.
- Valuation attractiveness.
- Sentiment crowding.
- Cash attractiveness.
- Yield curve chart.
- Markov regime probability chart.
- Key risk signal list.
- Asset valuation heatmap.
- Personal investment hypothesis panel.

### 5.2 Cycle Module

Purpose: reproduce and explain the known relationship between yield curve behavior and recession risk.

MVP indicators:

- US 10Y yield.
- US 2Y yield.
- 10Y-2Y spread.
- Optional recession calendar.

MVP model:

- `statsmodels` Markov Regression or Markov Autoregression.

Outputs:

- Spread chart with recession shading.
- Regime probability chart.
- Current regime interpretation.
- Similar historical periods.
- Model card with training range, update time, and caveats.

### 5.3 Valuation Module

Purpose: turn heterogeneous indicators into comparable percentile-based scores.

MVP asset groups:

- A-share broad indexes.
- US broad indexes.
- Bonds or bond proxies.
- Gold.
- Cash-like assets.

MVP normalized fields:

- `raw_value`
- `z_score`
- `percentile`
- `direction`
- `opportunity_score`
- `risk_score`
- `source`
- `updated_at`

### 5.4 Watchlist and Investment Hypothesis Module

Purpose: make personal investment reasoning explicit and reviewable.

Each watchlist item contains:

- Asset name.
- Asset type.
- Investment thesis.
- Entry or accumulation conditions.
- Exit, trim, or review conditions.
- Risk list.
- Current evidence snapshot.
- Action state.
- Review notes.

### 5.5 Lab Module

Purpose: demonstrate how a beautiful sample-in result can fail out of sample.

MVP validation methods:

- Chronological train/test split.
- Walk-forward validation.
- Purged K-Fold when event labels overlap.

Outputs:

- Sample-in metrics.
- Sample-out metrics.
- Performance decay.
- Parameter sensitivity.
- Overfitting risk score.
- Interpretation.

## 5A. Website Experience Expansion

The product should evolve from a single dashboard into a clickable research website. The overview page is the entry layer; every summary module should support drill-down, comparison, or action.

### 5A.1 Interaction Layers

Layer 1: State overview

- Dashboard KPI cards.
- Risk signals.
- Asset heatmap.
- Watchlist summary.

Layer 2: Exploration

- Click an asset to open asset details.
- Click a risk signal to open evidence and caveats.
- Click a KPI to see score decomposition.
- Switch filters by market, asset class, indicator group, and time window.
- Compare selected assets side by side.

Layer 3: Decision and review

- Add asset to watchlist.
- Create or edit an investment hypothesis.
- Save evidence snapshots.
- Run scenario simulations.
- Save monthly review notes.

### 5A.2 New Product Views

#### Asset Detail

Triggered from asset heatmap, valuation matrix, comparison table, or search.

Must show:

- Current action state.
- PE/PB/ERP/sentiment/trend percentiles.
- Long-term interpretation.
- Related watchlist hypotheses.
- Available actions: create hypothesis, compare, save snapshot.

#### Indicator Detail

Triggered from KPI cards, heatmap columns, or risk signal evidence.

Must show:

- Definition.
- Directional interpretation.
- Current contribution to opportunity/risk.
- Data source and limitation.
- Related assets or cycle modules.

#### Compare

Purpose:

Help users compare assets without changing mental models across pages.

Controls:

- Asset multi-select.
- Indicator group selector.
- Time window selector.

Outputs:

- Comparison table.
- Score bars.
- Interpretation text.
- Actions per asset.

#### Scenario Simulator

Purpose:

Let users rehearse decision rules without pretending to forecast the future.

Inputs:

- Rate shock.
- Valuation percentile adjustment.
- Sentiment percentile adjustment.

Outputs:

- Revised action states.
- Changed risks.
- Watchlist conditions likely to trigger.

#### Historical Similar Periods

Purpose:

Make cycle analysis exploratory.

Each period card should be clickable and show:

- Historical context.
- Similarity reason.
- Follow-up market behavior.
- Differences from today.

### 5A.3 Interaction Requirements

- Overview KPI cards navigate or open a drawer.
- Asset rows are clickable.
- Risk signals open evidence details.
- Similar-period cards open a period detail panel.
- Watchlist cards open thesis detail, not only edit form.
- Compare selections update without page reload.
- Scenario sliders update output immediately.
- Empty states must suggest the next action.

### 5A.4 Navigation Upgrade

Expanded navigation:

```text
Overview
Cycle
Valuation
Compare
Scenario
Watchlist
Lab
Reports
Settings
```

The product is still local-first, but the information architecture should feel like a small website rather than a single page.

## 6. Non-Goals

For the first product version:

- No brokerage integration.
- No order placement.
- No real-time tick data.
- No social feed.
- No push notification system.
- No paid data terminal integration.
- No complex user permission system.

## 7. User Journeys

### 7.1 Monthly Allocation Review

1. User opens dashboard.
2. Reviews cycle temperature and valuation attractiveness.
3. Checks asset heatmap for broad indexes, bonds, gold, and cash.
4. Opens watchlist items with triggered conditions.
5. Records a monthly allocation note.
6. Exports or saves a review snapshot.

Success criteria:

- User can explain why they continued, paused, or changed allocation.

### 7.2 Thesis Review

1. User opens a watchlist item.
2. Reads original thesis and conditions.
3. Compares current evidence to original assumptions.
4. Updates action state or invalidates the thesis.
5. Adds a review note.

Success criteria:

- Thesis changes are deliberate and recorded, not rewritten after the fact.

### 7.3 Overfitting Lesson

1. User creates a strategy hypothesis.
2. Runs sample-in optimization.
3. Reviews attractive sample-in performance.
4. Runs strict sample-out validation.
5. Reads overfitting diagnosis.

Success criteria:

- User understands why the strategy should not be trusted as a deployment rule.

## 8. Information Density

The interface should feel like a research workstation:

- Compact tables are acceptable.
- Charts should be legible and annotated.
- Avoid oversized marketing-style cards.
- Use side panels for details instead of full page interruptions.
- Default view should support scanning in 30 seconds.

## 9. Success Metrics

The product should be evaluated by behavior quality, not short-term returns.

Primary metrics:

- Percentage of watchlist items with explicit hypotheses.
- Percentage of decisions with evidence snapshots.
- Number of monthly reviews completed.
- Number of strategy experiments with sample-out validation.
- Reduction in unreviewed action changes.

Qualitative success:

- User can explain current exposure.
- User can distinguish valuation attractiveness from short-term momentum.
- User becomes more skeptical of beautiful backtests.

## 10. Open Questions

- Which markets should be first-class in MVP: A-share only, global indexes, or mixed?
- Should personal portfolio positions be entered manually in MVP?
- Should the product store private cost basis data, or avoid it initially?
- How much Qlib structure is useful before introducing unnecessary complexity?
- Which fallback implementation should be used if `mlfinlab` is unavailable?
