import streamlit as st
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import os

def run_etf_momentum_strategy(etfs: list, start_date: str, end_date: str) -> tuple:
    """
    Run ETF momentum strategy backtest
    
    Args:
        etfs: List of ETF symbols
        start_date: Start date for analysis
        end_date: End date for analysis
        
    Returns:
        tuple: (strategy_cum_returns, benchmark_cum_returns, data)
    """
    # Download data
    data = yf.download(etfs, start=start_date, end=end_date)['Close']
    
    # Calculate daily returns
    returns = data.pct_change().dropna()
    
    # Momentum calculation: past 10-day returns (shifted forward by 1 day to prevent look-ahead bias)
    momentum = data.pct_change(periods=10).shift(1)
    
    # Generate daily positions (hold the ETF with higher returns)
    # Handle NaN values by using skipna=True and providing a fallback
    position = momentum.apply(lambda row: row.idxmax(skipna=True) if not row.isna().all() else None, axis=1)
    
    # Strategy returns calculation
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
    
    return strategy_cum_returns, benchmark_cum_returns, data

def plot_results(strategy_cum_returns: pd.Series, benchmark_cum_returns: pd.Series, etf_list: list):
    """Plot strategy vs benchmark comparison"""
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(strategy_cum_returns, label=f'Momentum Strategy ({", ".join(etf_list)})')
    ax.plot(benchmark_cum_returns, label='Equal-weight Benchmark', linestyle='--')
    ax.set_title('ETF Momentum Strategy Backtest')
    ax.set_xlabel('Date')
    ax.set_ylabel('Cumulative Returns')
    ax.grid(True)
    ax.legend()
    plt.tight_layout()
    return fig

def etf_analyzer_app():
    """Main function for the ETF Analyzer app"""
    st.title("📊 ETF Momentum Analyzer")
    st.markdown("Analyze ETF performance using momentum strategies and backtest trading approaches.")
    
    # ETF selection
    default_etfs = "QQQ,VTV"
    etf_input = st.text_input("Enter ETF symbols (comma separated):", value=default_etfs)
    etfs = [etf.strip() for etf in etf_input.split(",") if etf.strip()]
    
    # Date range selection
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", value=pd.to_datetime("2023-01-01"))
    with col2:
        end_date = st.date_input("End Date", value=pd.to_datetime("2025-01-01"))
    
    # Run analysis button
    if st.button("Run Analysis", type="primary"):
        if not etfs:
            st.warning("Please enter at least one ETF symbol")
            return
        
        try:
            with st.spinner("Running ETF momentum analysis..."):
                # Run the strategy
                strategy_cum_returns, benchmark_cum_returns, data = run_etf_momentum_strategy(
                    etfs, 
                    start_date.strftime("%Y-%m-%d"), 
                    end_date.strftime("%Y-%m-%d")
                )
                
                # Display results
                st.success("Analysis completed!")
                
                # Plot results
                fig = plot_results(strategy_cum_returns, benchmark_cum_returns, etfs)
                st.pyplot(fig)
                
                # Show performance metrics
                strategy_return = (strategy_cum_returns.iloc[-1] - 1) * 100
                benchmark_return = (benchmark_cum_returns.iloc[-1] - 1) * 100
                
                col1, col2 = st.columns(2)
                col1.metric("Strategy Return", f"{strategy_return:.2f}%")
                col2.metric("Benchmark Return", f"{benchmark_return:.2f}%")
                
                # Show data preview
                st.subheader("Data Preview")
                st.dataframe(data.tail(10))
                
        except Exception as e:
            st.error(f"Error in analysis: {str(e)}")
    
    # Example usage
    with st.expander("How to use"):
        st.markdown("""
        1. Enter ETF symbols separated by commas (e.g., QQQ,VTV,VOO)
        2. Select the date range for analysis
        3. Click "Run Analysis" to see the momentum strategy performance
        4. Compare the strategy returns with the equal-weight benchmark
        """)

if __name__ == "__main__":
    etf_analyzer_app()