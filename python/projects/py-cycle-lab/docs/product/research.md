# Product Research

## 1. Market Context

Personal investors already have access to abundant data: quotes, valuation ratios, macro charts, fund tools, backtests, and social commentary. The pain point is not lack of information. The pain point is the absence of a disciplined decision loop.

Most tools answer one fragment of the workflow:

- What happened to the market?
- Which asset went up or down?
- Is a valuation ratio high or low?
- How did a portfolio backtest look?
- What are other investors saying?

LongCycle focuses on the missing loop:

```text
Cycle state -> Asset valuation -> Personal thesis -> Allocation decision -> Review -> Validation
```

## 2. Reference Products

### 2.1 Koyfin

Strengths:

- Professional multi-asset research workspace.
- Market dashboards, watchlists, charts, portfolio analytics.
- Strong custom screen and report orientation.

Limitations for this product:

- More general market research than personal investment discipline.
- Less focused on thesis journaling and anti-overfitting education.

Takeaways:

- Dense professional dashboard.
- Asset-level comparison.
- Watchlist as a research hub.

### 2.2 Portfolio Visualizer

Strengths:

- Portfolio backtesting.
- Asset allocation analysis.
- Monte Carlo simulation and factor analysis.

Limitations for this product:

- More tool-like than daily research workstation.
- Less focused on macro cycle and thesis management.

Takeaways:

- Make backtests explicit and parameterized.
- Keep allocation analysis transparent.
- Provide sample period and assumptions clearly.

### 2.3 MacroMicro

Strengths:

- Macro charts.
- Cycle-oriented economic data.
- Strong chart storytelling.

Limitations for this product:

- Limited personal watchlist and portfolio discipline.
- More browsing-oriented than thesis-review-oriented.

Takeaways:

- Use annotated macro charts.
- Show current values in long historical context.
- Make cycle phase readable without overclaiming.

### 2.4 TradingView

Strengths:

- Excellent chart interaction.
- Watchlists, screeners, alerts, community scripts.

Limitations for this product:

- Trading-centric mental model.
- Easy to overemphasize short-term price action.

Takeaways:

- Fast chart interactions.
- Watchlist UX.
- Indicator discoverability.

### 2.5 Xueqiu

Strengths:

- Chinese investor community.
- Watchlists, portfolio display, market information.

Limitations for this product:

- Social feed creates attention noise.
- Not optimized for quiet long-term research discipline.

Takeaways:

- Familiar watchlist language for Chinese users.
- Portfolio and discussion context are valuable, but should not dominate.

### 2.6 ETF/Fund Tools and Valuation Platforms

Examples include fund dashboards, valuation percentile products, and data platforms such as Lixinger-like tools.

Strengths:

- Valuation percentiles.
- Fund comparison.
- Index and company fundamentals.

Limitations for this product:

- Often stop at data display.
- Thesis, review, and anti-overfitting workflow remain outside the product.

Takeaways:

- Standardized percentile display is useful.
- Indicator definitions and data source clarity are essential.

## 3. Opportunity

The product opportunity is to combine four capabilities in one coherent workflow:

1. Macro/cycle state.
2. Standardized valuation and sentiment scoring.
3. Personal investment hypothesis management.
4. Robustness testing and overfitting diagnosis.

This creates a product that is less noisy than a market app, more personal than a macro chart site, and more disciplined than a standalone backtesting tool.

## 4. Differentiation

### 4.1 Decision Language

Use long-term investment states rather than trading commands:

- `Observe`
- `Accumulate gradually`
- `Pause adding`
- `Review thesis`
- `Rebalance review`
- `Invalidated`

### 4.2 Evidence Snapshot

Every decision or note should be able to save the current evidence:

- Indicator table.
- Relevant charts.
- Percentile scores.
- Model state.
- User note.

### 4.3 Anti-Overfitting as a Product Feature

Instead of hiding model fragility, the Lab module surfaces it:

- Sample-in vs sample-out gap.
- Parameter sensitivity.
- Feature count vs data size.
- Performance decay.
- Label leakage warnings.

## 5. Product Risks

### 5.1 False Precision

Scores such as 64/100 can appear more precise than they are. The UI must show confidence, data range, and caveats.

### 5.2 Data Availability

Some indicators may not be available through public sources or may have inconsistent histories. The product needs `data_quality` status.

### 5.3 Model Misinterpretation

Markov switching output can be mistaken for deterministic forecasts. Model cards and language constraints are required.

### 5.4 Overbuilding

Trying to build a full financial terminal would dilute the product. MVP should focus on the decision loop.

## 6. MVP Research Hypotheses

Hypothesis 1:

> A normalized cycle and valuation dashboard helps long-term investors make calmer allocation decisions.

Hypothesis 2:

> Explicit thesis conditions reduce after-the-fact rationalization.

Hypothesis 3:

> Showing sample-in and sample-out results side by side helps users internalize overfitting risk.

## 7. Design Implications

- The dashboard should open with state summary, not price action.
- Color should encode decision risk, not daily return.
- Watchlist items should be thesis-first, quote-second.
- Backtest screens should visually contrast sample-in and sample-out.
- Every chart needs an explanation panel and data metadata.
