"""
ETF Momentum Analyzer module - Backtesting tool for ETF momentum strategies.

Features:
- Compare momentum strategy vs equal-weight benchmark
- Visualize results with interactive charts
- Show performance metrics
- Support customizable date ranges
"""

import warnings
from typing import List, Tuple
import streamlit as st
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt

from modules.base_module import BaseModule, register_module

# Suppress yfinance FutureWarning
warnings.filterwarnings('ignore', category=FutureWarning, module='yfinance')


@register_module
class ETFAnalyzerModule(BaseModule):
    """
    ETF Momentum Analyzer module.
    
    Analyzes ETF performance using momentum strategies and backtests
    trading approaches against equal-weight benchmarks.
    """
    
    name = "ETF Momentum"
    description = "Backtest ETF momentum strategies with visualization"
    icon = "📊"
    order = 50
    
    def render(self) -> None:
        """Render the ETF analyzer interface."""
        self.display_header()
        
        # ETF selection
        st.subheader("📈 ETF Selection")
        default_etfs = "QQQ,VTV"
        etf_input = st.text_input(
            "Enter ETF symbols (comma separated):",
            value=default_etfs,
            help="Enter ETF ticker symbols separated by commas (e.g., QQQ,VTV,VOO)"
        )
        etfs = [etf.strip().upper() for etf in etf_input.split(",") if etf.strip()]
        
        # Display selected ETFs as badges
        if etfs:
            cols = st.columns(len(etfs))
            for col, etf in zip(cols, etfs):
                col.metric(etf, "")
        
        # Date range selection
        st.subheader("📅 Date Range")
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input(
                "Start Date",
                value=pd.to_datetime("2023-01-01"),
                help="Analysis start date"
            )
        with col2:
            end_date = st.date_input(
                "End Date",
                value=pd.to_datetime("2025-01-01"),
                help="Analysis end date"
            )
        
        # Strategy settings
        with st.expander("⚙️ Strategy Settings"):
            momentum_period = st.slider(
                "Momentum Lookback Period (days)",
                min_value=5,
                max_value=30,
                value=10,
                step=1,
                help="Number of days to look back for momentum calculation"
            )
            
            st.markdown("""
            **Strategy Explanation:**
            - Momentum Strategy: Each day, invest in the ETF with the highest returns over the lookback period
            - Equal-Weight Benchmark: Invest equally in all selected ETFs and hold
            """)
        
        # Run analysis button
        if st.button("Run Analysis", type="primary", use_container_width=True):
            if not etfs:
                st.warning("Please enter at least one ETF symbol")
                return
            
            if len(etfs) < 2:
                st.warning("Enter at least 2 ETFs for momentum comparison")
                return
            
            try:
                with st.spinner("📊 Running momentum analysis..."):
                    # Run the strategy
                    strategy_cum_returns, benchmark_cum_returns, data = self._run_momentum_strategy(
                        etfs,
                        start_date.strftime("%Y-%m-%d"),
                        end_date.strftime("%Y-%m-%d"),
                        momentum_period
                    )
                
                st.success("✅ Analysis completed!")
                
                # Display results
                self._display_results(strategy_cum_returns, benchmark_cum_returns, data, etfs)
                
            except Exception as e:
                st.error(f"Error in analysis: {str(e)}")
        
        # How to use
        with st.expander("ℹ️ How to use"):
            st.markdown("""
            1. **Enter ETF symbols** - Add ETFs separated by commas (e.g., QQQ,VTV,VOO)
            2. **Select date range** - Choose analysis period
            3. **Adjust settings** - Modify momentum lookback period if desired
            4. **Run Analysis** - Compare momentum strategy vs benchmark
            
            **Understanding the Results:**
            - **Momentum Strategy**: Dynamically selects the best-performing ETF based on recent momentum
            - **Equal-Weight Benchmark**: Simple buy-and-hold with equal allocation
            - **Cumulative Returns**: Total return over the period including compounding
            
            **Popular ETF Pairs:**
            - QQQ (Nasdaq) + VTV (Value)
            - SPY (S&P 500) + QQQ (Tech)
            - VOO (S&P 500) + VTI (Total Market)
            """)
    
    def _run_momentum_strategy(
        self,
        etfs: List[str],
        start_date: str,
        end_date: str,
        momentum_period: int = 10
    ) -> Tuple[pd.Series, pd.Series, pd.DataFrame]:
        """
        Run ETF momentum strategy backtest.
        
        Args:
            etfs: List of ETF symbols
            start_date: Start date string (YYYY-MM-DD)
            end_date: End date string (YYYY-MM-DD)
            momentum_period: Days to look back for momentum
        
        Returns:
            Tuple of (strategy_cum_returns, benchmark_cum_returns, price_data)
        """
        # Download data
        with st.spinner("📥 Downloading ETF data..."):
            data = yf.download(etfs, start=start_date, end=end_date, progress=False)['Close']
        
        if data.empty:
            raise ValueError("No data retrieved for the specified ETFs and date range")
        
        # Handle single ETF case
        if len(etfs) == 1:
            data = data.to_frame(etfs[0])
        
        # Calculate daily returns
        returns = data.pct_change().dropna()
        
        # Momentum calculation: past N-day returns (shifted to prevent look-ahead bias)
        momentum = data.pct_change(periods=momentum_period).shift(1)
        
        # Generate daily positions (hold the ETF with highest momentum)
        position = momentum.apply(
            lambda row: row.idxmax() if not row.isna().all() else None,
            axis=1
        )
        
        # Strategy returns calculation
        strategy_returns = []
        common_dates = position.index.intersection(returns.index)
        
        for date in common_dates:
            selected = position.loc[date]
            if selected is not None and pd.notna(selected):
                strategy_returns.append(returns.loc[date, selected])
            else:
                # If no position, use equal weight
                strategy_returns.append(returns.loc[date].mean())
        
        strategy_cum_returns = (pd.Series(strategy_returns, index=common_dates) + 1).cumprod()
        benchmark_cum_returns = (returns.mean(axis=1) + 1).cumprod()
        
        return strategy_cum_returns, benchmark_cum_returns, data
    
    def _display_results(
        self,
        strategy_cum_returns: pd.Series,
        benchmark_cum_returns: pd.Series,
        data: pd.DataFrame,
        etf_list: List[str]
    ) -> None:
        """
        Display analysis results.
        
        Args:
            strategy_cum_returns: Cumulative returns of momentum strategy
            benchmark_cum_returns: Cumulative returns of benchmark
            data: Raw price data
            etf_list: List of ETF symbols
        """
        # Performance metrics
        st.subheader("📊 Performance Metrics")
        
        strategy_return = (strategy_cum_returns.iloc[-1] - 1) * 100
        benchmark_return = (benchmark_cum_returns.iloc[-1] - 1) * 100
        outperformance = strategy_return - benchmark_return
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Momentum Strategy", f"{strategy_return:.2f}%")
        col2.metric("Equal-Weight Benchmark", f"{benchmark_return:.2f}%")
        col3.metric(
            "Outperformance",
            f"{outperformance:+.2f}%",
            delta=f"{outperformance:+.2f}%"
        )
        
        # Plot results
        st.subheader("📈 Cumulative Returns")
        fig = self._plot_results(strategy_cum_returns, benchmark_cum_returns, etf_list)
        st.pyplot(fig)
        
        # Data preview
        with st.expander("📋 Data Preview"):
            st.markdown("**Recent Price Data:**")
            st.dataframe(data.tail(10), use_container_width=True)
            
            st.markdown("**Statistics:**")
            stats_df = pd.DataFrame({
                'ETF': etf_list,
                'Start Price': [data[etf].iloc[0] for etf in etf_list],
                'End Price': [data[etf].iloc[-1] for etf in etf_list],
                'Total Return': [f"{((data[etf].iloc[-1] / data[etf].iloc[0]) - 1) * 100:.2f}%" 
                                for etf in etf_list]
            })
            st.dataframe(stats_df, use_container_width=True, hide_index=True)
    
    def _plot_results(
        self,
        strategy_cum_returns: pd.Series,
        benchmark_cum_returns: pd.Series,
        etf_list: List[str]
    ) -> plt.Figure:
        """
        Plot strategy vs benchmark comparison.
        
        Args:
            strategy_cum_returns: Strategy cumulative returns
            benchmark_cum_returns: Benchmark cumulative returns
            etf_list: List of ETF symbols
        
        Returns:
            Matplotlib figure
        """
        fig, ax = plt.subplots(figsize=(12, 6))
        
        ax.plot(
            strategy_cum_returns.index,
            strategy_cum_returns.values,
            label=f'Momentum Strategy ({", ".join(etf_list)})',
            linewidth=2,
            color='#1f77b4'
        )
        ax.plot(
            benchmark_cum_returns.index,
            benchmark_cum_returns.values,
            label='Equal-Weight Benchmark',
            linewidth=2,
            linestyle='--',
            color='#ff7f0e'
        )
        
        ax.set_title('ETF Momentum Strategy Backtest', fontsize=14, fontweight='bold')
        ax.set_xlabel('Date', fontsize=12)
        ax.set_ylabel('Cumulative Returns', fontsize=12)
        ax.grid(True, alpha=0.3)
        ax.legend(loc='upper left', fontsize=10)
        
        # Format y-axis as percentage
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: '{:.0%}'.format(y)))
        
        plt.tight_layout()
        return fig
