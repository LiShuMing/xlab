# Information Architecture

## 1. Navigation Model

Primary navigation:

```text
Overview
Cycle
Valuation
Watchlist
Portfolio
Lab
Reports
Settings
```

MVP navigation:

```text
Overview
Cycle
Valuation
Watchlist
Lab
Settings
```

## 2. Page Responsibilities

### 2.1 Overview

Purpose:

Provide a 30-second summary of market state and personal decision context.

Main questions:

- Is the market environment benign, neutral, or risky?
- Which assets are attractive or crowded?
- Which watchlist items need attention?

Components:

- State KPI strip.
- Yield curve mini chart.
- Regime probability mini chart.
- Key risk signals.
- Asset valuation heatmap.
- Personal hypothesis panel.

### 2.2 Cycle

Purpose:

Explain macro and market regimes using yield curve and related indicators.

Main questions:

- What is the current cycle state?
- How does the yield curve compare with prior recession windows?
- What does the regime model suggest, and what are its limitations?

Components:

- Yield curve spread chart.
- Recession shading.
- Regime probability chart.
- Model card.
- Similar historical periods.
- Indicator table.

### 2.3 Valuation

Purpose:

Normalize valuation, risk premium, sentiment, and trend indicators across assets.

Main questions:

- Which assets are historically cheap or expensive?
- Which assets are crowded?
- Which assets deserve observation, accumulation, caution, or review?

Components:

- Asset class tabs.
- Valuation matrix.
- Indicator detail drawer.
- Percentile history chart.
- Asset detail page.

### 2.4 Watchlist

Purpose:

Maintain structured long-term investment hypotheses.

Main questions:

- What do I believe about this asset?
- What evidence would make me add, pause, trim, or invalidate the thesis?
- Has the thesis changed?

Components:

- Hypothesis cards.
- Condition checklist.
- Risk list.
- Evidence snapshot.
- Review timeline.
- Action state selector.

### 2.5 Portfolio

Purpose:

Track allocation and risk exposure. This can be P1 rather than MVP.

Main questions:

- What is my current allocation?
- Which cycle or valuation risks dominate?
- Does the allocation match my stated rules?

Components:

- Allocation chart.
- Exposure breakdown.
- Drawdown and volatility.
- Rebalance drift.
- Monthly review.

### 2.6 Lab

Purpose:

Validate strategy hypotheses and expose overfitting.

Main questions:

- Does a strategy survive sample-out validation?
- How sensitive is performance to parameters?
- Is there leakage or overlap bias?

Components:

- Strategy setup panel.
- CV method selector.
- Sample-in metrics.
- Sample-out metrics.
- Overfitting diagnosis.
- Experiment report.

## 3. Entity Model

### 3.1 Asset

Fields:

- `asset_id`
- `name`
- `ticker`
- `market`
- `asset_class`
- `currency`
- `data_sources`

### 3.2 Indicator

Fields:

- `indicator_id`
- `name`
- `category`
- `raw_value`
- `unit`
- `direction`
- `source`
- `updated_at`
- `data_quality`

### 3.3 Score

Fields:

- `asset_id`
- `indicator_id`
- `as_of_date`
- `lookback_window`
- `percentile`
- `z_score`
- `opportunity_score`
- `risk_score`

### 3.4 Hypothesis

Fields:

- `hypothesis_id`
- `asset_id`
- `title`
- `thesis`
- `entry_conditions`
- `review_conditions`
- `risk_items`
- `action_state`
- `created_at`
- `updated_at`

### 3.5 Evidence Snapshot

Fields:

- `snapshot_id`
- `hypothesis_id`
- `as_of_date`
- `indicator_values`
- `chart_refs`
- `model_state`
- `user_note`

### 3.6 Experiment

Fields:

- `experiment_id`
- `name`
- `features`
- `labels`
- `model`
- `cv_method`
- `train_range`
- `test_range`
- `sample_in_metrics`
- `sample_out_metrics`
- `overfit_score`

## 4. Content Hierarchy

Every analytical view should follow this order:

1. State summary.
2. Evidence.
3. Interpretation.
4. Caveats.
5. Possible action states.

This avoids burying the conclusion while still making evidence visible.

## 5. Data Freshness States

Use explicit status badges:

- `Fresh`: updated within expected interval.
- `Stale`: delayed but usable.
- `Missing`: unavailable.
- `Partial`: some fields unavailable.
- `Experimental`: model or transformation is not production-stable.

## 6. Permission and Privacy Assumption

MVP is local-first:

- No account system.
- No cloud sync.
- No brokerage login.
- No private portfolio upload requirement.

This keeps the first implementation simple and avoids sensitive data risk.
