import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt

# 1. Download data
etfs = ['QQQ', 'VTV']  # Can be replaced with other combinations, such as ['ARKK', 'VTV']
data = yf.download(etfs, start="2023-01-01", end="2025-01-01")['Close']

# 2. Calculate daily returns
returns = data.pct_change().dropna()

# 3. Momentum calculation: past 10-day returns (shifted forward by 1 day to prevent look-ahead bias)
momentum = data.pct_change(periods=10).shift(1)

# 4. Generate daily positions (hold the ETF with higher returns)
# Handle NaN values by using skipna=True and providing a fallback
position = momentum.apply(lambda row: row.idxmax(skipna=True) if not row.isna().all() else None, axis=1)

# 5. Strategy returns calculation
strategy_returns = []
# Only iterate over dates that exist in both position and returns
common_dates = position.index.intersection(returns.index)

for date in common_dates:
    selected = position.loc[date]
    if selected is not None and pd.notna(selected):
        strategy_returns.append(returns.loc[date, selected])
    else:
        # If no position is selected, use equal weight
        strategy_returns.append(returns.loc[date].mean())

strategy_cum_returns = (pd.Series(strategy_returns, index=common_dates) + 1).cumprod()
benchmark_cum_returns = (returns.mean(axis=1) + 1).cumprod()

# 6. Visualize strategy vs benchmark comparison
plt.figure(figsize=(12, 6))
plt.plot(strategy_cum_returns, label='Momentum Strategy (QQQ vs VTV)')
plt.plot(benchmark_cum_returns, label='Equal-weight Benchmark', linestyle='--')
plt.title('ETF Momentum Strategy Backtest')
plt.xlabel('Date')
plt.ylabel('Cumulative Returns')
plt.grid(True)
plt.legend()
plt.tight_layout()
plt.show()