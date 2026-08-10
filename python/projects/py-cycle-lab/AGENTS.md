# Repository Guidelines

## Project Role

This project is a personal long-term investment research product, not a trading signal system. Prioritize explainability, disciplined research workflows, and source-anchored evidence over short-term prediction.

## Product Principles

- Do not present outputs as investment advice.
- Avoid "buy/sell now" language. Prefer action states such as `observe`, `pause adding`, `rebalance review`, `hypothesis invalidated`.
- Every model result must include data range, model version, and limitations.
- Every score must be traceable to raw indicators and transformation logic.
- Sample-in and sample-out results must be shown together for strategy experiments.

## Project Structure

- `docs/product/`: PRD, research, information architecture.
- `docs/design/`: design system, prototype specs, visual assets.
- `docs/implementation/`: engineering roadmap and build notes.
- `src/cycle_lab/`: future Python package.
- `scripts/`: future command-line workflows.
- `notebooks/`: future exploratory notebooks.
- `tests/`: future pytest suites.

## Coding Style

- Use Python type hints.
- Prefer `pathlib.Path` for paths.
- Keep data-fetching, feature engineering, modeling, and UI code separated.
- Cache raw data locally and record source/update metadata.
- Write tests for scoring logic, percentile transforms, and CV splitting.

## Data and Security

- Do not commit private portfolios, broker exports, secrets, tokens, or local database files.
- Keep generated datasets under ignored data folders once implementation begins.
- Public market data may still have provider terms; preserve source names and timestamps.
