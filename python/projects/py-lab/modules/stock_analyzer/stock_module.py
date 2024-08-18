"""
Stock Analyzer module - Professional investment analysis report generation.

Based on DESIGN.md specification:
- Multi-perspective analysis (Buffett, Duan Yongping, Trader, Quant)
- 8-section structured report
- Macro environment assessment
- Technical, fundamental, and risk analysis

Uses utils.output layer for report generation and distribution.
"""

import json
import re
from typing import Tuple, Optional, Dict, Any
from datetime import datetime, timedelta
from pathlib import Path

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

from modules.base_module import BaseModule, register_module
from core.llm_factory import get_llm
from config.settings import settings

# Import output layer
from utils.output import (
    Report,
    ReportFormat,
    ReportSection,
    ReportMetadata,
    quick_output,
    create_stock_report,
)


# System prompt based on DESIGN.md
SYSTEM_PROMPT = """You are a senior cross-disciplinary investment analyst with deep expertise in fundamental analysis, 
technical analysis, macro research, and behavioral finance. You serve a retail investor managing approximately 
$30,000 USD in U.S. equities, whose primary objective is capital preservation first, appreciation second.

Analyze every investment through the following lenses simultaneously:

1. Value Investing (Warren Buffett / Charlie Munger): Margin of safety, moat, long-term compounding
2. Business Quality (Duan Yongping): Business model integrity, management quality
3. Technical Analysis (Wall Street Trader): Price action, momentum, key price levels
4. Quant/Risk (Hedge Fund PM): Drawdown control, position sizing, portfolio correlation
5. Fundamental (Sell-side Analyst): EPS, FCF, valuation multiples, peer comparison
6. Long-term (Public Fund Manager): DCF, industry cycle, structural growth
7. Short-term (Active Trader): Catalysts, earnings plays, macro correlation
8. Retail (Individual Investor): Liquidity needs, simplicity, emotional discipline

Output Format (in Chinese, with English annotations for proper nouns):

## 一、公司概览 Company Overview
- 主营业务与商业模式，核心竞争优势（护城河 Moat）
- 行业地位与主要竞争对手
- 管理层质量与历史资本配置表现

## 二、宏观与行业背景 Macro & Sector Context
- 当前宏观环境对该股的具体影响（利率敏感性、汇率风险、政策暴露）
- 行业所处周期阶段：成长期 Growth / 成熟期 Mature / 衰退期 Decline
- 近期关键催化剂（Catalyst）或逆风因素（Headwind）

## 三、技术面分析 Technical Analysis

**当前价格定位 Current Price Position**
- 当前价格相对于52周区间：精确计算 (当前价-52周低)/(52周高-52周低) 百分比位置
- 与MA(50)/MA(200)的偏离度：计算百分比并判断趋势强度
- 关键价格水平：支撑位 Support、压力位 Resistance

**趋势与动量 Trend & Momentum**
- 趋势判断：价格与MA(50)/MA(200)的关系，金叉/死叉状态
- MACD与RSI当前读数及信号
- 成交量结构与异常信号

**短线交易视角 Short-term Trading View**
- 基于当前价格的精确入场点（如"回调至$XX.XX附近买入"）
- 目标价与止损位（基于当前价格计算R/R比）
- 明确的出场节点评估

## 四、基本面与财务健康 Financial Health
- 盈利质量：Revenue 增长趋势、EPS 走势、Net Margin、FCF Yield
- 资产负债表：D/E Ratio、Current Ratio、Interest Coverage Ratio
- 估值水平：P/E、P/S、EV/EBITDA，对比历史均值与同业水平
- 股东回报：Buyback 规模、Dividend 政策、ROIC / ROE 水平

## 五、多视角投资论点 Multi-Lens Investment Case

巴菲特视角 Buffett Lens:
是否具备持久竞争优势？10年后的业务是否更为强大？当前价格是否提供足够的安全边际（Margin of Safety）？

段永平视角 Duan Yongping Lens:
管理层是否"本分"，商业模式是否正直可持续？以当前估值，能否长期持有而无持续性焦虑？

华尔街交易员视角 Trader Lens:
近期核心催化剂为何？期权市场隐含波动率（IV）是否合理定价？当前风险/回报比（Risk/Reward Ratio）是否具备交易价值？

量化与私募视角 Quant / Hedge Fund Lens:
因子暴露如何（成长 Growth / 价值 Value / 动量 Momentum / 质量 Quality）？与现有持仓的相关性？预期最大回撤（Max Drawdown）区间？

## 六、风险矩阵 Risk Matrix
| 风险类型 | 具体描述 | 发生概率 | 潜在影响 | 缓解措施 |
|---|---|---|---|---|
| 基本面风险 Fundamental Risk | | | | |
| 估值风险 Valuation Risk | | | | |
| 宏观与利率风险 Macro / Rate Risk | | | | |
| 行业竞争风险 Competitive Risk | | | | |
| 流动性与尾部风险 Liquidity / Tail Risk | | | | |

## 七、仓位建议 Position Sizing（基于 $30,000 账户，按当前价格 ${data['current_price']} 计算）
- 建议仓位比例：占组合 X%，约 $X,XXX
- 精确建仓方案：
  - 当前价格：$XX.XX
  - 建议购买股数：XXX 股（$X,XXX ÷ $XX.XX = XXX 股）
  - 分批策略：首仓 XXX 股 @ $XX.XX，回调至 $XX.XX 补仓 XXX 股
- 止损位 Stop-Loss：设于 $XX.XX（距离当前价格 -X.X%），潜在损失 $XXX
- 目标价与收益（基于当前价格 ${data['current_price']}）：
  - 短线目标（1—3个月）：$XX.XX (+X.X%)
  - 中线目标（6—12个月）：$XX.XX (+X.X%)
  - 长线目标（2—3年）：$XX.XX (+X.X%)
- 风险/回报比 Risk/Reward Ratio：1:X
- 建议持仓期限：短线 / 中线 / 长线

## 八、综合评级 Overall Recommendation
```
评级：强烈买入 Strong Buy / 买入 Buy / 观望 Hold / 减持 Underweight / 回避 Avoid
置信度：高 High / 中 Medium / 低 Low
核心投资逻辑（1—2句）：
最重要的下行风险（1句）：
```

Output Style Guidelines:
1. 文笔简洁严谨，符合正式书面语，避免口语化与情绪化表达
2. 段落分明，重点内容加粗处理，关键数据以表格呈现
3. 所有专有名词使用英文标注，包括 Ticker、指数名称、财务术语
4. 数据引用须注明来源或时间窗口
5. 避免空泛表述，每项结论须有数据或逻辑支撑
6. 若相关数据不足，明确标注"数据待补充"，不作无依据推断
"""


@register_module
class StockAnalyzerModule(BaseModule):
    """
    Professional Stock Analyzer module based on DESIGN.md specification.
    
    Generates comprehensive investment analysis reports with:
    - Multi-perspective analysis (Buffett, Duan Yongping, Trader, Quant)
    - Macro environment assessment
    - Technical analysis with indicators
    - Fundamental financial health analysis
    - Risk matrix and position sizing recommendations
    
    Uses utils.output layer for report generation and distribution.
    """
    
    name = "Stock Analyzer"
    description = "Professional investment analysis with multi-perspective framework"
    icon = "📈"
    order = 20
    
    def render(self) -> None:
        """Render the stock analyzer interface."""
        self.display_header()
        
        # User query input
        query = st.text_input(
            "Enter your investment query:",
            placeholder="e.g., Should I invest in Apple (AAPL) now?",
            help="Ask about any stock or investment decision"
        )
        
        # Model configuration
        with st.expander("⚙️ Analysis Configuration"):
            col1, col2 = st.columns(2)
            with col1:
                temperature = st.slider(
                    "Temperature",
                    min_value=0.0,
                    max_value=1.0,
                    value=0.3,
                    step=0.1,
                    key="stock_temp",
                    help="Lower for more consistent analytical output"
                )
            with col2:
                max_tokens = st.slider(
                    "Max Tokens",
                    min_value=2000,
                    max_value=8000,
                    value=4000,
                    step=500,
                    key="stock_tokens",
                    help="Increase for complete deep-dive report"
                )
            
            # Data range selection
            data_range = st.selectbox(
                "Historical Data Range",
                options=["1y", "2y", "5y", "max"],
                index=1,
                help="Price history to include in analysis"
            )
            
            # Output format selection
            output_format = st.selectbox(
                "Report Output Format",
                options=["markdown", "html", "json"],
                index=0,
                help="Format for download (display is always Markdown)"
            )
        
        # Analyze button
        if st.button("Generate Analysis Report", type="primary", use_container_width=True):
            if not query:
                st.warning("Please enter an investment query")
                return
            
            # Check API configuration
            from core.llm_factory import get_available_providers
            if not get_available_providers():
                st.error("Please configure at least one API key (DashScope, OpenAI, or Anthropic).")
                return
            
            try:
                self._run_analysis(query, temperature, max_tokens, data_range, output_format)
            except Exception as e:
                st.error(f"Error during analysis: {str(e)}")
                import traceback
                st.error(traceback.format_exc())
        
        # Usage guide
        with st.expander("ℹ️ How to Use"):
            st.markdown("""
            **Investment Analysis Framework**
            
            This analyzer generates professional-grade investment reports with:
            
            1. **Macro Assessment** - Current market environment and risk level
            2. **Company Overview** - Business model, moat, management quality
            3. **Technical Analysis** - Support/resistance, moving averages, momentum
            4. **Financial Health** - Profitability, balance sheet, valuation metrics
            5. **Multi-Lens View** - Perspectives from Buffett, Duan Yongping, Trader, Quant
            6. **Risk Matrix** - Comprehensive risk assessment with mitigation
            7. **Position Sizing** - Specific allocation for $30K portfolio
            8. **Rating & Price Targets** - Clear actionable recommendation
            
            **Tips:**
            - Be specific in your query (include ticker if known)
            - Use longer data range (2y/5y) for better trend analysis
            - Lower temperature (0.2-0.3) for more consistent output
            """)
    
    def _run_analysis(
        self, 
        query: str, 
        temperature: float, 
        max_tokens: int, 
        data_range: str,
        output_format: str
    ) -> None:
        """
        Run the complete stock analysis workflow.
        
        Args:
            query: User's investment query
            temperature: LLM temperature
            max_tokens: Max tokens for response
            data_range: Historical data range
            output_format: Output format for download
        """
        # Step 1: Extract ticker
        with st.spinner("🔍 Identifying stock..."):
            company_name, ticker = self._extract_ticker(query)
        
        if not ticker:
            st.error("Could not identify stock ticker. Please include the ticker symbol (e.g., AAPL).")
            return
        
        st.info(f"📊 Analyzing: **{company_name}** ({ticker})")
        
        # Step 2: Collect data
        with st.spinner("📥 Collecting market data..."):
            data_package = self._collect_data(ticker, data_range)
        
        if data_package.get("error"):
            st.error(f"Data collection failed: {data_package['error']}")
            return
        
        # Step 3: Generate analysis
        with st.spinner("🤖 Generating comprehensive report (this may take 30-60 seconds)..."):
            report_content = self._generate_report(
                query, company_name, ticker, data_package, temperature, max_tokens
            )
        
        # Step 4: Create structured report and output
        st.success("✅ Analysis Complete!")
        st.divider()
        
        # Create Report object
        report = create_stock_report(
            ticker=ticker,
            company_name=company_name,
            content=report_content,
            title=f"{ticker} Investment Analysis Report",
            data={
                "current_price": data_package.get("current_price"),
                "market_cap": data_package.get("market_cap"),
                "sector": data_package.get("sector"),
                "technical": data_package.get("technical"),
            }
        )
        
        # Determine output format
        format_map = {
            "markdown": ReportFormat.MARKDOWN,
            "html": ReportFormat.HTML,
            "json": ReportFormat.JSON,
        }
        report_format = format_map.get(output_format, ReportFormat.MARKDOWN)
        
        # Use output layer for rendering and distribution
        result = quick_output(
            report=report,
            format=report_format,
            filename=f"{ticker}_analysis_{datetime.now().strftime('%Y%m%d')}.{report_format.value}",
            show_streamlit=True,
            show_download=True,
        )
        
        if not result["success"]:
            st.error(f"Failed to save report: {result.get('error', 'Unknown error')}")
    
    def _extract_ticker(self, query: str) -> Tuple[str, str]:
        """
        Extract company name and ticker from user query.
        
        Args:
            query: User's natural language query
        
        Returns:
            Tuple of (company_name, ticker_symbol)
        """
        # Common company name to ticker mapping for quick lookup
        common_companies = {
            'APPLE': 'AAPL', 'MICROSOFT': 'MSFT', 'GOOGLE': 'GOOGL', 'ALPHABET': 'GOOGL',
            'AMAZON': 'AMZN', 'TESLA': 'TSLA', 'META': 'META', 'FACEBOOK': 'META',
            'NVIDIA': 'NVDA', 'NETFLIX': 'NFLX', 'AMD': 'AMD', 'INTEL': 'INTC',
            'BERKSHIRE': 'BRK-B', 'BERKSHIRE HATHAWAY': 'BRK-B',
            'JPMORGAN': 'JPM', 'JP MORGAN': 'JPM', 'BANK OF AMERICA': 'BAC',
            'WELLS FARGO': 'WFC', 'CITIBANK': 'C', 'CITI': 'C',
            'VISA': 'V', 'MASTERCARD': 'MA', 'AMERICAN EXPRESS': 'AXP',
            'WALMART': 'WMT', 'TARGET': 'TGT', 'COSTCO': 'COST',
            'COCA-COLA': 'KO', 'COCA COLA': 'KO', 'PEPSI': 'PEP',
            'MCDONALDS': 'MCD', 'MCDONALD': 'MCD', 'STARBUCKS': 'SBUX',
            'DISNEY': 'DIS', 'WALT DISNEY': 'DIS',
            'BOEING': 'BA', 'LOCKHEED': 'LMT', 'LOCKHEED MARTIN': 'LMT',
            'EXXON': 'XOM', 'EXXONMOBIL': 'XOM', 'CHEVRON': 'CVX',
            'JOHNSON': 'JNJ', 'JOHNSON & JOHNSON': 'JNJ',
            'PFIZER': 'PFE', 'MERCK': 'MRK', 'ABBVIE': 'ABBV',
            'UNITEDHEALTH': 'UNH', 'UNITED HEALTH': 'UNH',
            'PROCTER': 'PG', 'PROCTER & GAMBLE': 'PG', 'P&G': 'PG',
            'HOME DEPOT': 'HD', 'LOWES': 'LOW', 'LOWE': 'LOW',
            'VERIZON': 'VZ', 'AT&T': 'T',
            'SALESFORCE': 'CRM', 'ORACLE': 'ORCL', 'ADOBE': 'ADBE',
            'IBM': 'IBM', 'CISCO': 'CSCO', 'QUALCOMM': 'QCOM',
            'PAYPAL': 'PYPL', 'SQUARE': 'SQ', 'BLOCK': 'SQ',
            'ZOOM': 'ZM', 'SHOPIFY': 'SHOP', 'UBER': 'UBER', 'LYFT': 'LYFT',
            'AIRBNB': 'ABNB', 'DOORDASH': 'DASH',
            'ALIBABA': 'BABA', 'TENCENT': 'TCEHY', 'BAIDU': 'BIDU',
            'JD': 'JD', 'PINDUODUO': 'PDD', 'NETEASE': 'NTES',
            'TAIWAN SEMICONDUCTOR': 'TSM', 'TSMC': 'TSM',
            'SAMSUNG': '005930.KS', 'SONY': 'SONY', 'TOYOTA': 'TM',
        }
        
        query_upper = query.upper()
        
        # Check for exact match in common companies
        for company_name, ticker in common_companies.items():
            if company_name in query_upper:
                try:
                    stock = yf.Ticker(ticker)
                    info = stock.info
                    company = info.get('longName', info.get('shortName', company_name.title()))
                    return company, ticker
                except:
                    pass
        
        # Try to extract ticker using regex (all caps pattern like AAPL, MSFT)
        ticker_pattern = r'\b([A-Z]{2,5})\b'
        matches = re.findall(ticker_pattern, query_upper)
        
        # Common words to exclude
        exclude_words = {'I', 'AM', 'AN', 'THE', 'IS', 'ARE', 'NOW', 'USD', 'AI', 'ETF', 'AND', 'OR', 'FOR', 'IN', 'ON', 'AT', 'TO', 'OF', 'UP', 'DOWN', 'BUY', 'SELL', 'HOLD', 'GOOD', 'BAD', 'BEST', 'NEW', 'OLD', 'BIG', 'SMALL'}
        potential_tickers = [m for m in matches if m not in exclude_words]
        
        # Validate each potential ticker
        for ticker in potential_tickers:
            try:
                stock = yf.Ticker(ticker)
                info = stock.info
                if info and 'longName' in info:
                    company_name = info.get('longName', info.get('shortName', ticker))
                    return company_name, ticker
            except:
                continue
        
        # If no ticker found, use LLM to extract
        prompt = f"""
Given the user query, identify the company name and stock ticker symbol.
The ticker symbol should be 1-5 uppercase letters (e.g., AAPL for Apple, MSFT for Microsoft).
Respond ONLY in JSON format with keys "company_name" and "ticker_symbol".

User Query: {query}

Example Response:
{{"company_name": "Apple Inc.", "ticker_symbol": "AAPL"}}

JSON Response:"""
        
        try:
            llm = get_llm(temperature=0.1, max_tokens=200, streaming=False)
            response = llm.invoke(prompt)
            content = response.content
            
            # Extract JSON
            start = content.find('{')
            end = content.rfind('}') + 1
            if start != -1 and end > start:
                json_str = content[start:end]
                data = json.loads(json_str)
                ticker = data.get("ticker_symbol", "").upper()
                company_name = data.get("company_name", "")
                
                # Validate the ticker
                if ticker:
                    try:
                        stock = yf.Ticker(ticker)
                        info = stock.info
                        if info and 'longName' in info:
                            return info.get('longName', company_name), ticker
                    except:
                        pass
                
                return company_name, ticker
        except Exception as e:
            st.warning(f"Ticker extraction warning: {e}")
        
        return "", ""
    
    def _collect_data(self, ticker: str, period: str) -> Dict[str, Any]:
        """
        Collect comprehensive stock data for analysis.
        
        Args:
            ticker: Stock ticker symbol
            period: Data period (1y, 2y, 5y, max)
        
        Returns:
            Dictionary containing all collected data
        """
        try:
            stock = yf.Ticker(ticker)
            
            # Basic info
            info = stock.info
            
            # Price history
            hist = stock.history(period=period)
            
            # Technical indicators
            technical_data = self._calculate_technical_indicators(hist)
            
            # Financial statements
            financials = {
                "income_stmt": stock.income_stmt,
                "balance_sheet": stock.balance_sheet,
                "cash_flow": stock.cashflow,
            }
            
            # Recent news
            news = stock.news[:5] if hasattr(stock, 'news') else []
            
            # Format for report
            data_package = {
                "ticker": ticker,
                "company_name": info.get('longName', info.get('shortName', ticker)),
                "sector": info.get('sector', 'N/A'),
                "industry": info.get('industry', 'N/A'),
                "market_cap": info.get('marketCap', 0),
                "employees": info.get('fullTimeEmployees', 0),
                "website": info.get('website', 'N/A'),
                "business_summary": info.get('longBusinessSummary', 'N/A'),
                
                # Price data
                "current_price": info.get('currentPrice', info.get('regularMarketPrice', 0)),
                "52_week_high": info.get('fiftyTwoWeekHigh', 0),
                "52_week_low": info.get('fiftyTwoWeekLow', 0),
                "50_day_ma": info.get('fiftyDayAverage', 0),
                "200_day_ma": info.get('twoHundredDayAverage', 0),
                "volume": info.get('volume', 0),
                "avg_volume": info.get('averageVolume', 0),
                
                # Valuation metrics
                "pe_ratio": info.get('trailingPE', info.get('forwardPE', 0)),
                "forward_pe": info.get('forwardPE', 0),
                "ps_ratio": info.get('priceToSalesTrailing12Months', 0),
                "pb_ratio": info.get('priceToBook', 0),
                "ev_ebitda": info.get('enterpriseToEbitda', 0),
                
                # Financial metrics
                "profit_margin": info.get('profitMargins', 0),
                "revenue_growth": info.get('revenueGrowth', 0),
                "earnings_growth": info.get('earningsGrowth', 0),
                "roe": info.get('returnOnEquity', 0),
                "roa": info.get('returnOnAssets', 0),
                "debt_to_equity": info.get('debtToEquity', 0),
                "current_ratio": info.get('currentRatio', 0),
                "quick_ratio": info.get('quickRatio', 0),
                "free_cash_flow": info.get('freeCashflow', 0),
                "dividend_rate": info.get('dividendRate', 0),
                "dividend_yield": info.get('dividendYield', 0),
                "payout_ratio": info.get('payoutRatio', 0),
                
                # Technical analysis
                "technical": technical_data,
                
                # Historical price data summary
                "price_history": self._format_price_history(hist),
                
                # News
                "recent_news": news,
                
                # Raw data for LLM
                "raw_financials": {
                    "income": financials["income_stmt"].to_string() if financials["income_stmt"] is not None else "N/A",
                    "balance": financials["balance_sheet"].to_string() if financials["balance_sheet"] is not None else "N/A",
                    "cashflow": financials["cash_flow"].to_string() if financials["cash_flow"] is not None else "N/A",
                }
            }
            
            return data_package
            
        except Exception as e:
            return {"error": str(e)}
    
    def _calculate_technical_indicators(self, hist: pd.DataFrame) -> Dict[str, Any]:
        """
        Calculate technical indicators from price history.
        
        Args:
            hist: Price history DataFrame
        
        Returns:
            Dictionary of technical indicators
        """
        if hist.empty:
            return {}
        
        # Moving averages
        hist['MA20'] = hist['Close'].rolling(window=20).mean()
        hist['MA50'] = hist['Close'].rolling(window=50).mean()
        hist['MA200'] = hist['Close'].rolling(window=200).mean()
        
        # RSI (14-day)
        delta = hist['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        hist['RSI'] = 100 - (100 / (1 + rs))
        
        # MACD
        exp1 = hist['Close'].ewm(span=12).mean()
        exp2 = hist['Close'].ewm(span=26).mean()
        hist['MACD'] = exp1 - exp2
        hist['Signal'] = hist['MACD'].ewm(span=9).mean()
        
        # Bollinger Bands
        hist['BB_middle'] = hist['Close'].rolling(window=20).mean()
        bb_std = hist['Close'].rolling(window=20).std()
        hist['BB_upper'] = hist['BB_middle'] + (bb_std * 2)
        hist['BB_lower'] = hist['BB_middle'] - (bb_std * 2)
        
        # Support and Resistance (simple method - recent lows/highs)
        recent = hist.tail(60)  # Last 60 days
        support = recent['Low'].min()
        resistance = recent['High'].max()
        
        # Volume analysis
        avg_volume = hist['Volume'].mean()
        recent_volume = hist['Volume'].tail(20).mean()
        volume_trend = "Above Average" if recent_volume > avg_volume * 1.2 else \
                       "Below Average" if recent_volume < avg_volume * 0.8 else "Average"
        
        latest = hist.iloc[-1]
        
        return {
            "current_price": round(latest['Close'], 2),
            "ma_20": round(latest['MA20'], 2) if not pd.isna(latest['MA20']) else None,
            "ma_50": round(latest['MA50'], 2) if not pd.isna(latest['MA50']) else None,
            "ma_200": round(latest['MA200'], 2) if not pd.isna(latest['MA200']) else None,
            "rsi": round(latest['RSI'], 2) if not pd.isna(latest['RSI']) else None,
            "macd": round(latest['MACD'], 4) if not pd.isna(latest['MACD']) else None,
            "macd_signal": round(latest['Signal'], 4) if not pd.isna(latest['Signal']) else None,
            "bb_upper": round(latest['BB_upper'], 2) if not pd.isna(latest['BB_upper']) else None,
            "bb_lower": round(latest['BB_lower'], 2) if not pd.isna(latest['BB_lower']) else None,
            "support_level": round(support, 2),
            "resistance_level": round(resistance, 2),
            "volume_trend": volume_trend,
            "trend_20d": "Above" if latest['Close'] > latest['MA20'] else "Below" if not pd.isna(latest['MA20']) else "N/A",
            "trend_50d": "Above" if latest['Close'] > latest['MA50'] else "Below" if not pd.isna(latest['MA50']) else "N/A",
            "trend_200d": "Above" if latest['Close'] > latest['MA200'] else "Below" if not pd.isna(latest['MA200']) else "N/A",
        }
    
    def _format_price_history(self, hist: pd.DataFrame) -> str:
        """Format price history for LLM consumption."""
        if hist.empty:
            return "No price data available"
        
        # Get key statistics
        latest = hist['Close'].iloc[-1]
        start_price = hist['Close'].iloc[0]
        total_return = ((latest - start_price) / start_price) * 100
        
        # Volatility (annualized)
        daily_returns = hist['Close'].pct_change().dropna()
        volatility = daily_returns.std() * np.sqrt(252) * 100
        
        # Monthly performance (last 6 months)
        monthly = hist['Close'].resample('ME').last().tail(6)
        monthly_changes = monthly.pct_change().dropna() * 100
        
        summary = f"""
Price Performance Summary:
- Period: {len(hist)} trading days
- Total Return: {total_return:.2f}%
- Annualized Volatility: {volatility:.2f}%
- 52-Week Range: ${hist['Low'].min():.2f} - ${hist['High'].max():.2f}

Recent Monthly Returns:
{monthly_changes.to_string()}

Last 10 Days Price Action:
{hist[['Open', 'High', 'Low', 'Close', 'Volume']].tail(10).to_string()}
"""
        return summary
    
    def _generate_report(
        self,
        query: str,
        company_name: str,
        ticker: str,
        data: Dict[str, Any],
        temperature: float,
        max_tokens: int
    ) -> str:
        """
        Generate the comprehensive investment analysis report.
        
        Args:
            query: Original user query
            company_name: Company name
            ticker: Stock ticker
            data: Collected data package
            temperature: LLM temperature
            max_tokens: Max tokens
        
        Returns:
            Formatted analysis report content (markdown)
        """
        # Prepare user prompt with all data
        user_prompt = f"""
User Query: {query}

=== COMPANY INFORMATION ===
Name: {data['company_name']} ({ticker})
Sector: {data['sector']} | Industry: {data['industry']}
Market Cap: ${data['market_cap']:,.0f}
Employees: {data['employees']:,}
Website: {data['website']}

Business Summary: {data['business_summary'][:1000]}

=== CURRENT PRICE ANALYSIS (CRITICAL) ===
Current Price: ${data['current_price']}
52-Week Range: ${data['52_week_low']:.2f} - ${data['52_week_high']:.2f}

Price Position Calculations:
- Position in 52W Range: {((data['current_price'] - data['52_week_low']) / (data['52_week_high'] - data['52_week_low']) * 100):.1f}% (100% = 52W high, 0% = 52W low)
- Distance to 52W High: {((data['52_week_high'] - data['current_price']) / data['current_price'] * 100):.1f}% upside to reach ${data['52_week_high']:.2f}
- Distance to 52W Low: {((data['current_price'] - data['52_week_low']) / data['52_week_low'] * 100):.1f}% above 52W low of ${data['52_week_low']:.2f}

Moving Averages (Current Price: ${data['current_price']}):
- 50-Day MA: ${data['50_day_ma']:.2f} ({((data['current_price'] - data['50_day_ma']) / data['50_day_ma'] * 100):+.1f}%)
- 200-Day MA: ${data['200_day_ma']:.2f} ({((data['current_price'] - data['200_day_ma']) / data['200_day_ma'] * 100):+.1f}%)
- Trend: {'Bullish (Price > MA50 > MA200)' if data['current_price'] > data['50_day_ma'] > data['200_day_ma'] else 'Bearish (Price < MA50 < MA200)' if data['current_price'] < data['50_day_ma'] < data['200_day_ma'] else 'Mixed/Mixed Signal'}

Valuation Metrics:
- P/E Ratio: {f"{data['pe_ratio']:.2f}" if data['pe_ratio'] else 'N/A'}
- Forward P/E: {f"{data['forward_pe']:.2f}" if data['forward_pe'] else 'N/A'}
- P/S Ratio: {f"{data['ps_ratio']:.2f}" if data['ps_ratio'] else 'N/A'}
- P/B Ratio: {f"{data['pb_ratio']:.2f}" if data['pb_ratio'] else 'N/A'}
- EV/EBITDA: {f"{data['ev_ebitda']:.2f}" if data['ev_ebitda'] else 'N/A'}

=== FINANCIAL METRICS ===
Profit Margin: {f"{data['profit_margin']*100:.2f}%" if data['profit_margin'] else 'N/A'}
Revenue Growth: {f"{data['revenue_growth']*100:.2f}%" if data['revenue_growth'] else 'N/A'}
Earnings Growth: {f"{data['earnings_growth']*100:.2f}%" if data['earnings_growth'] else 'N/A'}
ROE: {f"{data['roe']*100:.2f}%" if data['roe'] else 'N/A'}
ROA: {f"{data['roa']*100:.2f}%" if data['roa'] else 'N/A'}
Debt/Equity: {f"{data['debt_to_equity']:.2f}" if data['debt_to_equity'] else 'N/A'}
Current Ratio: {f"{data['current_ratio']:.2f}" if data['current_ratio'] else 'N/A'}
Free Cash Flow: {f"${data['free_cash_flow']:,.0f}" if data['free_cash_flow'] else 'N/A'}

Dividend Rate: {f"${data['dividend_rate']:.2f}" if data['dividend_rate'] else 'N/A'}
Dividend Yield: {f"{data['dividend_yield']*100:.2f}%" if data['dividend_yield'] else 'N/A'}

=== TECHNICAL ANALYSIS (Use these for price targets) ===
{json.dumps(data['technical'], indent=2)}

Position Sizing Calculations (Portfolio: $30,000):
- Conservative Position (5%): $1,500 ÷ ${data['current_price']:.2f} = {int(1500/data['current_price'])} shares
- Moderate Position (10%): $3,000 ÷ ${data['current_price']:.2f} = {int(3000/data['current_price'])} shares  
- Aggressive Position (15%): $4,500 ÷ ${data['current_price']:.2f} = {int(4500/data['current_price'])} shares

Suggested Stop-Loss Levels (based on technical support):
- Tight Stop (2% risk): ${data['current_price'] * 0.98:.2f} (potential loss: $XX per share)
- Normal Stop (5% risk): ${data['current_price'] * 0.95:.2f} (potential loss: $XX per share)
- Wide Stop (8% risk): ${data['current_price'] * 0.92:.2f} (potential loss: $XX per share)
- Technical Support Stop: ${data['technical'].get('support_level', data['current_price'] * 0.90):.2f}

=== PRICE HISTORY ===
{data['price_history']}

=== RECENT NEWS ===
{json.dumps(data['recent_news'], indent=2)[:2000]}

=== FINANCIAL STATEMENTS ===
Income Statement:
{data['raw_financials']['income'][:3000]}

Balance Sheet:
{data['raw_financials']['balance'][:3000]}

Cash Flow:
{data['raw_financials']['cashflow'][:3000]}

=== ANALYSIS DATE ===
Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

CRITICAL INSTRUCTION - PRICE DATA USAGE:
You MUST explicitly reference and analyze the current stock price (${data['current_price']}) and recent price action in your report. Specifically:

1. In Technical Analysis section - Compare current price to MA(50) and MA(200), calculate exact percentage distance
2. In Valuation section - Calculate implied valuations using current price vs. 52-week range
3. In Position Sizing - Use current price for exact share calculation ($X,XXX / current price = X shares)
4. In Price Targets - Show percentage upside/downside from current price
5. In Risk Matrix - Calculate potential $ loss at stop-loss level from current position

Make the analysis actionable based on TODAY's price, not generic.

Please generate a comprehensive investment analysis report following the 8-section framework.
"""
        
        # Get LLM and generate report
        llm = get_llm(
            temperature=temperature,
            max_tokens=max_tokens,
            streaming=False
        )
        
        from langchain_core.messages import SystemMessage, HumanMessage
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_prompt)
        ]
        
        response = llm.invoke(messages)
        return response.content

