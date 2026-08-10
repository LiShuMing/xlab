# PRD: Praxis Invest

## 1. Product Positioning

Praxis Invest is an AI-assisted long-term investment research and review workspace for individual investors.

It is not a stock-picking or trading-signal product. It helps users turn scattered market information into structured judgment, record investment hypotheses, track whether those hypotheses remain valid, and review decision quality over time.

Core promise:

> Help individual investors convert research into disciplined, reviewable long-term investment decisions.

## 2. Target Users

Primary users:

- Individual investors with some investing experience.
- Long-term, value-oriented, or fundamentals-oriented investors.
- Users who want a stable research framework rather than short-term price signals.
- Users who want to reduce emotional trading and build a personal investing knowledge base.

Non-target users:

- High-frequency traders.
- Short-term momentum-only users.
- Users seeking direct buy/sell instructions.
- Users expecting regulated investment advice.

## 3. Core Pain Points

### Information Overload

Users see news, financial metrics, prices, analyst opinions, and social commentary, but struggle to identify which information affects long-term value.

### Lack Of Stable Framework

Users often switch reasoning frameworks depending on price movement. A good product should repeatedly guide them through business model, moat, financial quality, valuation, margin of safety, risks, and disconfirming evidence.

### Emotion-Driven Decisions

FOMO, panic selling, loss aversion, and confirmation bias often hurt individual investors more than lack of data.

### Missing Review Loop

Users rarely record their original thesis, expected outcomes, risk conditions, or exit criteria. Later they only know profit/loss, not whether the process was good.

### Fragmented Tools

Market data, reports, notes, AI chat, portfolio tracking, and reviews live in different tools. Users need a research workspace rather than another isolated report generator.

## 4. Product Goals

MVP goals:

- Generate a structured long-term investment research report.
- Convert a report into an editable investment thesis.
- Create watch items tied to the thesis.
- Record journal entries for attention, buy, sell, and review decisions.
- Preserve historical reports and thesis revisions.

Medium-term goals:

- Track thesis-changing events over time.
- Build a personal investment profile.
- Prompt disciplined review before user actions.
- Turn repeated research into a personal investment system.

Non-goals:

- Automated trading.
- Guaranteed returns.
- Direct personalized investment advice.
- Real-time trading alerts as the core product.

## 5. Core Product Loop

```text
Discover stock
  -> Structured research
  -> Draft investment thesis
  -> Add watch items / position state
  -> Track material changes
  -> Review thesis
  -> Update decision and personal investing knowledge
```

The core product value is the loop, not a single generated report.

## 6. Core Modules

### 6.1 Research Workspace

Input:

- Stock code.
- User research question.
- Language.
- Analysis depth: fast or deep.

Output:

- Company overview.
- Business model.
- Moat.
- Financial quality.
- Valuation and margin of safety.
- Industry and competitors.
- Risks and bear case.
- Questions requiring further verification.
- Long-term conclusion.

Design rules:

- Separate facts from model judgment.
- Mark missing data explicitly.
- Keep a disclaimer visible.

### 6.2 Investment Thesis Card

Each stock can have an active thesis:

- `stock_code`
- `stock_name`
- `status`: watchlist, researching, small_position, holding, trimming, exited
- `core_thesis`
- `supporting_evidence`
- `counter_evidence`
- `disconfirming_signals`
- `margin_of_safety`
- `expected_holding_period`
- `confidence`
- `source_report_id`

The thesis card is the primary artifact users review later.

### 6.3 Watch Items

Watch items track material changes:

- Financial reporting dates.
- Revenue/profit margin changes.
- Free cash flow changes.
- Valuation level.
- Important news.
- Management changes.
- Industry policy.
- Competitor changes.
- Price approaching desired valuation range.
- Disconfirming evidence.

This is a hypothesis watchlist, not a generic ticker list.

### 6.4 Investment Journal

Journal entry types:

- watch
- buy
- add
- trim
- sell
- pass
- review
- emotion

Each entry records:

- Time.
- Stock.
- Action.
- Price.
- Reason.
- Emotion.
- Linked thesis/report.
- Next review date.

### 6.5 Review

Review questions:

- Is the original thesis still valid?
- Did supporting evidence improve or weaken?
- Did counter-evidence appear?
- Did valuation change materially?
- Did the user follow the plan?
- Was the outcome process-driven or luck-driven?

Review decisions:

- keep
- increase_confidence
- reduce_confidence
- research_more
- exit_triggered
- no_action

### 6.6 Personal Investment Profile

Later versions should learn:

- Preferred markets.
- Preferred styles.
- Typical holding period.
- Risk tolerance.
- Common mistakes.
- Position sizing habits.
- Emotional patterns.

## 7. MVP Scope

Included:

- Existing report generation.
- Investment thesis creation and editing.
- Watch item CRUD.
- Journal entry CRUD.
- Review record CRUD.
- Report-to-thesis draft generation.
- Simple Invest page integration.

Deferred:

- Real-time alerts.
- Broker integration.
- Portfolio accounting.
- Backtesting.
- Community features.
- Regulated advice workflows.

## 8. Success Metrics

Usage:

- Number of generated reports.
- Thesis creation rate after report generation.
- Watch item creation rate.
- Journal entry frequency.
- Review completion rate.
- Repeat visits to the same stock.

Quality:

- Percentage of reports linked to thesis cards.
- Number of thesis updates.
- Number of decisions with recorded reason.
- User corrections to AI-generated thesis drafts.

Long-term value:

- Reduced impulse actions.
- More consistent decision notes.
- Better ability to explain why a stock is owned, watched, or rejected.

## 9. Risks And Constraints

Compliance:

- Must not promise returns.
- Must not present output as direct investment advice.
- Must show disclaimers.

AI quality:

- Avoid fabricated numbers.
- Mark unavailable data.
- Distinguish facts from inference.

Product risks:

- Reports become too long to read.
- Users do not maintain journals.
- The product feels like a generic chatbot.
- The product becomes a market-data dashboard instead of a research system.

## 10. Version Plan

### V0.1: Research Report Tool

- Generate fast/deep research reports.
- Store historical reports.

### V0.2: Investment Thesis

- Draft thesis from report.
- Edit thesis.
- Track thesis status and confidence.

### V0.3: Journal

- Record attention/buy/sell/pass/review/emotion entries.
- Link journal to thesis and report.

### V0.4: Watch And Review

- Watch material changes.
- Record structured reviews.

### V0.5: Personal Profile

- Learn user style and recurring mistakes.
- Personalize review prompts.

## 11. Immediate Implementation Target

The first implementation target is:

> After a report is generated, automatically create or update an investment thesis draft, expose thesis/watch/journal/review APIs, and show the thesis card in the Invest page.
