"""
Enhanced data collection tools for Stock Analyzer.

Provides additional data sources for:
- A-shares (A 股) via AkShare
- HK stocks (港股) via yfinance HK
- Macro economic data via FRED API (optional)
- Enhanced technical indicators via pandas-ta
"""

import json
import re
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

import pandas as pd
import numpy as np

try:
    import akshare as ak
    AKSHARE_AVAILABLE = True
except ImportError:
    AKSHARE_AVAILABLE = False
    print("Warning: akshare not installed. A-share data will be limited.")

try:
    import pandas_ta as ta
    PANDAS_TA_AVAILABLE = True
except ImportError:
    PANDAS_TA_AVAILABLE = False
    print("Warning: pandas_ta not installed. Using basic technical indicators.")


class AShareDataCollector:
    """
    A 股数据收集器 (A-Share Data Collector)

    Supports Shanghai (上证) and Shenzhen (深证) stocks.
    Stock code format: sh600519, sz000001
    """

    @staticmethod
    def get_stock_info(stock_code: str) -> Dict[str, Any]:
        """
        Get A-share stock basic information.

        Args:
            stock_code: Stock code with prefix (sh600519, sz000001)

        Returns:
            Dictionary with stock information
        """
        if not AKSHARE_AVAILABLE:
            return {"error": "akshare not installed"}

        try:
            # Remove prefix if present
            code = re.sub(r'^(sh|sz)', '', stock_code)

            # Get real-time quote
            quote = ak.stock_zh_a_spot_em()
            stock_data = quote[quote['代码'] == code]

            if stock_data.empty:
                return {"error": f"Stock {stock_code} not found"}

            row = stock_data.iloc[0]

            return {
                "ticker": stock_code,
                "company_name": row.get('名称', 'N/A'),
                "current_price": float(row.get('最新价', 0)),
                "change": float(row.get('涨跌幅', 0)),
                "change_amount": float(row.get('涨跌额', 0)),
                "volume": float(row.get('成交量', 0)),
                "turnover": float(row.get('成交额', 0)),
                "market_cap": float(row.get('总市值', 0)),
                "pe_ratio": float(row.get('市盈率 - 动态', 0)),
                "pb_ratio": float(row.get('市净率', 0)),
                "52_week_high": float(row.get('52 周最高', 0)),
                "52_week_low": float(row.get('52 周最低', 0)),
            }

        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def get_stock_history(stock_code: str, period: str = "1y") -> pd.DataFrame:
        """
        Get A-share historical price data.

        Args:
            stock_code: Stock code with prefix
            period: Time period (1y, 2y, 5y, max)

        Returns:
            DataFrame with OHLCV data
        """
        if not AKSHARE_AVAILABLE:
            return pd.DataFrame()

        try:
            code = re.sub(r'^(sh|sz)', '', stock_code)

            # Get daily data
            df = ak.stock_zh_a_hist(symbol=code, period="daily", start_date="20200101")

            # Standardize column names
            df.columns = [
                'date', 'open', 'close', 'high', 'low', 'volume',
                'turnover', 'amplitude', 'pct_change', 'change_amount', 'turnover_rate'
            ]

            # Convert date
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)

            # Filter by period
            if period != "max":
                years = int(period.replace('y', ''))
                cutoff = datetime.now() - timedelta(days=365 * years)
                df = df[df.index >= cutoff]

            return df

        except Exception as e:
            print(f"Error fetching A-share history: {e}")
            return pd.DataFrame()

    @staticmethod
    def get_financial_metrics(stock_code: str) -> Dict[str, Any]:
        """
        Get A-share financial metrics.

        Args:
            stock_code: Stock code with prefix

        Returns:
            Dictionary with financial metrics
        """
        if not AKSHARE_AVAILABLE:
            return {"error": "akshare not installed"}

        try:
            code = re.sub(r'^(sh|sz)', '', stock_code)

            # Get main financial indicators
            metrics = ak.stock_financial_analysis_indicator(symbol=code)

            # Get latest quarter
            latest = metrics.iloc[0] if not metrics.empty else None

            if latest is None:
                return {"error": "No financial data available"}

            return {
                "revenue_growth": float(latest.get('营业总收入同比增长率', 0)),
                "earnings_growth": float(latest.get('净利润同比增长率', 0)),
                "roe": float(latest.get('净资产收益率', 0)),
                "gross_margin": float(latest.get('销售毛利率', 0)),
                "debt_to_equity": float(latest.get('资产负债率', 0)),
                "current_ratio": float(latest.get('流动比率', 0)),
                "eps": float(latest.get('每股收益', 0)),
                "bvps": float(latest.get('每股净资产', 0)),
            }

        except Exception as e:
            return {"error": str(e)}


class HKShareDataCollector:
    """
    港股数据收集器 (HK Share Data Collector)

    Supports HKEX stocks via yfinance.
    Stock code format: 0700.HK (Tencent), 9988.HK (Alibaba)
    """

    @staticmethod
    def get_stock_info(stock_code: str) -> Dict[str, Any]:
        """
        Get HK stock information.

        Args:
            stock_code: HK stock code (e.g., 0700.HK)

        Returns:
            Dictionary with stock information
        """
        try:
            import yfinance as yf

            stock = yf.Ticker(stock_code)
            info = stock.info

            return {
                "ticker": stock_code,
                "company_name": info.get('longName', info.get('shortName', stock_code)),
                "current_price": info.get('currentPrice', info.get('regularMarketPrice', 0)),
                "change": info.get('regularMarketChangePercent', 0),
                "market_cap": info.get('marketCap', 0),
                "pe_ratio": info.get('trailingPE', 0),
                "pb_ratio": info.get('priceToBook', 0),
                "dividend_yield": info.get('dividendYield', 0),
                "52_week_high": info.get('fiftyTwoWeekHigh', 0),
                "52_week_low": info.get('fiftyTwoWeekLow', 0),
                "sector": info.get('sector', 'N/A'),
                "industry": info.get('industry', 'N/A'),
            }

        except Exception as e:
            return {"error": str(e)}


class TechnicalIndicatorCalculator:
    """
    Enhanced technical indicator calculator using pandas-ta.
    """

    @staticmethod
    def calculate_all(df: pd.DataFrame) -> Dict[str, Any]:
        """
        Calculate comprehensive technical indicators.

        Args:
            df: DataFrame with OHLCV data

        Returns:
            Dictionary of technical indicators
        """
        if df.empty:
            return {}

        # Make a copy to avoid modifying original
        data = df.copy()

        # Basic moving averages
        data['MA20'] = data['Close'].rolling(window=20).mean()
        data['MA50'] = data['Close'].rolling(window=50).mean()
        data['MA200'] = data['Close'].rolling(window=200).mean()

        # Use pandas-ta if available
        if PANDAS_TA_AVAILABLE:
            # RSI
            data['RSI'] = ta.rsi(data['Close'], length=14)

            # MACD
            macd = ta.macd(data['Close'], fast=12, slow=26, signal=9)
            data['MACD'] = macd['MACD_12_26_9']
            data['MACD_Signal'] = macd['MACDs_12_26_9']
            data['MACD_Hist'] = macd['MACDh_12_26_9']

            # Bollinger Bands
            bbands = ta.bbands(data['Close'], length=20, std=2)
            data['BB_Upper'] = bbands['BBU_20_2.0']
            data['BB_Middle'] = bbands['BBM_20_2.0']
            data['BB_Lower'] = bbands['BBL_20_2.0']

            # Stochastic
            stoch = ta.stoch(data['High'], data['Low'], data['Close'], k=14, d=3)
            data['STOCH_K'] = stoch['STOCHk_14_3_3']
            data['STOCH_D'] = stoch['STOCHd_14_3_3']

            # ADX
            data['ADX'] = ta.adx(data['High'], data['Low'], data['Close'], length=14)['ADX_14']

            # CCI
            data['CCI'] = ta.cci(data['High'], data['Low'], data['Close'], length=20)

            # Williams %R
            data['WILLR'] = ta.willr(data['High'], data['Low'], data['Close'], length=14)

            # OBV (On Balance Volume)
            data['OBV'] = ta.obv(data['Close'], data['Volume'])

            # ATR (Average True Range)
            data['ATR'] = ta.atr(data['High'], data['Low'], data['Close'], length=14)

        else:
            # Basic fallback calculations
            delta = data['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            data['RSI'] = 100 - (100 / (1 + rs))

            # MACD (basic)
            exp1 = data['Close'].ewm(span=12).mean()
            exp2 = data['Close'].ewm(span=26).mean()
            data['MACD'] = exp1 - exp2
            data['MACD_Signal'] = data['MACD'].ewm(span=9).mean()

            # Bollinger Bands (basic)
            data['BB_middle'] = data['Close'].rolling(window=20).mean()
            bb_std = data['Close'].rolling(window=20).std()
            data['BB_Upper'] = data['BB_middle'] + (bb_std * 2)
            data['BB_Lower'] = data['BB_middle'] - (bb_std * 2)

        # Calculate support and resistance
        recent = data.tail(60)
        support = recent['Low'].min()
        resistance = recent['High'].max()

        # Volume analysis
        avg_volume = data['Volume'].mean()
        recent_volume = data['Volume'].tail(20).mean()
        volume_trend = "Above Average" if recent_volume > avg_volume * 1.2 else \
                       "Below Average" if recent_volume < avg_volume * 0.8 else "Average"

        # Get latest values
        latest = data.iloc[-1]

        return {
            "current_price": round(latest['Close'], 2),
            "ma_20": round(latest['MA20'], 2) if not pd.isna(latest.get('MA20')) else None,
            "ma_50": round(latest['MA50'], 2) if not pd.isna(latest.get('MA50')) else None,
            "ma_200": round(latest['MA200'], 2) if not pd.isna(latest.get('MA200')) else None,
            "rsi": round(latest['RSI'], 2) if not pd.isna(latest.get('RSI')) else None,
            "macd": round(latest['MACD'], 4) if not pd.isna(latest.get('MACD')) else None,
            "macd_signal": round(latest.get('MACD_Signal', latest.get('MACD_Signal')), 4) if not pd.isna(latest.get('MACD_Signal')) else None,
            "bb_upper": round(latest.get('BB_Upper', latest.get('BB_middle', 0)), 2),
            "bb_lower": round(latest.get('BB_Lower', latest.get('BB_middle', 0)), 2),
            "support_level": round(support, 2),
            "resistance_level": round(resistance, 2),
            "volume_trend": volume_trend,
            "trend_20d": "Above" if latest['Close'] > latest['MA20'] else "Below",
            "trend_50d": "Above" if latest['Close'] > latest['MA50'] else "Below",
            "trend_200d": "Above" if latest['Close'] > latest['MA200'] else "Below",
            # Additional indicators if pandas-ta available
            "adx": round(latest.get('ADX', 0), 2) if PANDAS_TA_AVAILABLE else None,
            "stoch_k": round(latest.get('STOCH_K', 0), 2) if PANDAS_TA_AVAILABLE else None,
            "stoch_d": round(latest.get('STOCH_D', 0), 2) if PANDAS_TA_AVAILABLE else None,
            "cci": round(latest.get('CCI', 0), 2) if PANDAS_TA_AVAILABLE else None,
            "atr": round(latest.get('ATR', 0), 2) if PANDAS_TA_AVAILABLE else None,
        }


def collect_comprehensive_data(
    ticker: str,
    period: str = "2y",
    market: str = "US"
) -> Dict[str, Any]:
    """
    Collect comprehensive market data for any supported market.

    Args:
        ticker: Stock ticker symbol
        period: Historical data period
        market: Market type (US, A, HK)

    Returns:
        Dictionary with all collected data
    """
    if market == "A":
        # A-shares via AkShare
        collector = AShareDataCollector()
        info = collector.get_stock_info(ticker)
        history = collector.get_stock_history(ticker, period)
        financials = collector.get_financial_metrics(ticker)

    elif market == "HK":
        # HK stocks via yfinance
        collector = HKShareDataCollector()
        info = collector.get_stock_info(ticker)
        # Use yfinance for history
        import yfinance as yf
        stock = yf.Ticker(ticker)
        history = stock.history(period=period)
        financials = {}

    else:
        # US stocks via yfinance (default)
        import yfinance as yf
        stock = yf.Ticker(ticker)
        info = stock.info
        history = stock.history(period=period)
        financials = {}

    # Calculate technical indicators
    tech_calculator = TechnicalIndicatorCalculator()
    technical = tech_calculator.calculate_all(history)

    # Combine all data
    data_package = {
        **info,
        "technical": technical,
        "price_history": history,
        "financials": financials,
        "market": market,
    }

    return data_package


def detect_market(ticker: str) -> str:
    """
    Detect market from ticker format.

    Args:
        ticker: Stock ticker symbol

    Returns:
        Market type: "US", "A", or "HK"
    """
    ticker_upper = ticker.upper()

    # A-shares: sh600519, sz000001, 600519.SH, 000001.SZ
    if ticker_upper.startswith(('SH', 'SZ')) or '.SH' in ticker_upper or '.SZ' in ticker_upper:
        return "A"

    # HK stocks: 0700.HK, 700.HK, 0700
    if '.HK' in ticker_upper or (ticker_upper.isdigit() and len(ticker) == 4):
        return "HK"

    # Default to US
    return "US"


# Convenience function for stock_module.py
def get_enhanced_data(ticker: str, period: str = "2y") -> Dict[str, Any]:
    """
    Get enhanced stock data with auto market detection.

    Args:
        ticker: Stock ticker symbol
        period: Historical data period

    Returns:
        Comprehensive data package
    """
    market = detect_market(ticker)
    return collect_comprehensive_data(ticker, period, market)
