# Design System

## 1. Design Direction

Design name: **Calm Research Desk**

The interface should feel like a quiet personal investment research desk:

- Professional but not institutionally cold.
- Dense but readable.
- Calm rather than stimulating.
- Built for recurring review, not compulsive checking.
- Decision-oriented rather than quote-oriented.

The product should not look like:

- A trading terminal.
- A crypto dashboard.
- A news portal.
- A marketing landing page.
- A decorative data visualization gallery.

## 2. Visual Principles

### 2.1 Calm First

Use restrained colors and generous whitespace between functional groups. Risk signals should stand out because the rest of the interface is calm.

### 2.2 Evidence Is Visible

Cards should not hide evidence behind vague scores. Each score must have a visible path to contributing indicators.

### 2.3 Compact Research Density

This is a working product, not a hero page. Compact tables, side drawers, filters, and small multiples are appropriate.

### 2.4 No Daily Return Color Semantics

Green and red should not mean daily up/down. They mean long-term opportunity and risk.

## 3. Color Tokens

```text
--bg-page: #F7F8F6;
--bg-surface: #FFFFFF;
--bg-subtle: #F1F4F2;
--text-primary: #1F2933;
--text-secondary: #6B7280;
--text-muted: #9CA3AF;
--border-subtle: #E5E7EB;
--border-strong: #CBD5E1;

--opportunity: #0F766E;
--opportunity-soft: #D9F3EE;
--caution: #D97706;
--caution-soft: #FEF3C7;
--risk: #DC2626;
--risk-soft: #FEE2E2;
--model: #2563EB;
--model-soft: #DBEAFE;
--neutral: #64748B;
--neutral-soft: #E2E8F0;
```

## 4. Typography

Recommended fonts:

- Chinese: `PingFang SC`, `Noto Sans CJK SC`, `Source Han Sans SC`.
- Latin and numbers: `Inter`, `SF Pro Display`, `SF Pro Text`.

Scale:

```text
Page title: 24px / 32px / 600
Section title: 16px / 24px / 600
Card title: 14px / 20px / 600
Body: 14px / 22px / 400
Small metadata: 12px / 18px / 400
KPI number: 28px / 36px / 650
Table number: 13px / 18px / 500
```

Rules:

- Do not use viewport-scaled font sizes.
- Use tabular numbers for KPI and table values.
- Keep letter spacing at `0`.
- Avoid oversized headings inside dense panels.

## 5. Layout

Desktop target:

- Primary width: 1440px.
- Minimum useful width: 1280px.
- Left navigation: 232px.
- Main content max width: fluid.
- Right side drawer: 320px to 380px.
- Page padding: 24px.
- Card gap: 16px.

Responsive rule:

- MVP may prioritize desktop.
- Tablet should collapse right drawer below main content.
- Mobile is read-only summary first, not full analysis workstation.

## 6. Components

### 6.1 App Shell

Required elements:

- Left navigation.
- Top utility bar.
- Main content region.
- Optional right evidence or hypothesis drawer.

Left navigation sections:

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

MVP may hide Portfolio and Reports.

### 6.2 KPI Cards

Purpose:

Summarize product-level state.

Content:

- Label.
- Score.
- Qualitative state.
- Change vs previous period.
- Main contributing signal.

Example:

```text
周期温度
64 / 100
中性偏热
较上周 +4
```

States:

- Opportunity.
- Neutral.
- Caution.
- Risk.
- Experimental.

### 6.3 Indicator Table

Columns:

```text
Indicator | Current | Percentile | Direction | Opportunity | Risk | Source | Updated
```

Rules:

- Use compact row height.
- Use color chips for percentile interpretation.
- Always show source and update freshness.

### 6.4 Asset Heatmap

Rows:

- Assets.

Columns:

- Valuation indicators.
- Risk premium.
- Sentiment.
- Trend.
- Suggested action state.

Cell states:

- Deep teal: attractive.
- Amber: caution or transition.
- Muted red: risky or crowded.
- Slate gray: neutral or insufficient data.

### 6.5 Hypothesis Card

Fields:

- Asset.
- Thesis summary.
- Current action state.
- Conditions.
- Risks.
- Next review date.
- Evidence snapshot link.

Rules:

- Thesis should be prominent.
- Price or return should be secondary.
- Conditions use checkboxes or status icons.

### 6.6 Model Card

Fields:

- Model name.
- Data range.
- Last trained.
- Current output.
- Confidence or stability.
- Limitations.

Required caveat:

> Model output describes regime likelihood and should not be interpreted as a deterministic market forecast.

### 6.7 Experiment Result Panel

Must show:

- Sample-in performance.
- Sample-out performance.
- Performance decay.
- Overfitting risk.
- Data leakage checks.
- Parameter sensitivity.

The sample-out result should not be visually hidden or secondary.

## 7. Interaction Patterns

### 7.1 Details on Demand

Default view shows summary. Clicking a score opens a detail drawer with:

- Contributing indicators.
- Historical percentile chart.
- Data source.
- Caveat.

### 7.2 Evidence Snapshot

Any watchlist review can save the current dashboard state:

- Scores.
- Charts.
- Indicator values.
- Model state.
- User note.

### 7.3 Action State Change

Changing an action state should prompt a note:

```text
Why are you changing from Observe to Accumulate gradually?
```

This creates a lightweight research journal.

### 7.4 Experimental Label

Any model-driven feature should carry an `Experimental` badge until validated.

## 8. Content Style

Preferred:

- `估值进入观察区`
- `情绪偏拥挤`
- `宏观风险溢价应上调`
- `样本外表现显著衰减`

Avoid:

- `立即买入`
- `精准预测`
- `稳赚`
- `必然反转`

## 9. Accessibility

- Do not rely on color only; use labels and icons.
- Maintain sufficient contrast for text and chips.
- Tables need readable row hover and focus states.
- Tooltips should explain unfamiliar indicators.
