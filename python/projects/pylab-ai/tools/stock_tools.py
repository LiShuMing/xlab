"""
Stock Agent Tools - Tool definitions for LLM agent usage.

These tools are automatically discovered and used by the LLM agent
during stock analysis workflows.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from modules.base_module import BaseAgentTool, ToolInfo, ToolParameter


class QueryStockPriceTool(BaseAgentTool):
    """
    股价查询工具 - Get real-time stock price data.

    Usage:
        - Single stock: QueryStockPriceInfo(stockCodes="AAPL")
        - Multiple stocks: QueryStockPriceInfo(stockCodes="AAPL,MSFT,GOOGL")
        - A-shares: QueryStockPriceInfo(stockCodes="sh600519,sz000001")
        - HK stocks: QueryStockPriceInfo(stockCodes="0700.HK,9988.HK")
    """

    def get_info(self) -> ToolInfo:
        return ToolInfo(
            name="QueryStockPriceInfo",
            description="批量获取股票的实时股价、涨跌幅、成交量等数据",
            parameters=[
                ToolParameter(
                    name="stockCodes",
                    type="string",
                    description="股票代码列表，多个代码用逗号分隔。格式：AAPL(美股), sh600519(A 股), 0700.HK(港股)",
                    required=True
                )
            ]
        )

    async def execute(self, arguments: Dict[str, Any]) -> str:
        from tools.stock_data_tools import get_enhanced_data, detect_market

        stock_codes = [c.strip() for c in arguments.get("stockCodes", "").split(",")]
        results = []

        for code in stock_codes:
            try:
                market = detect_market(code)
                data = get_enhanced_data(code, period="1y")

                result = f"""
**{data.get('company_name', code)} ({code})**
- Market: {market}
- Current Price: ${data.get('current_price', 0)}
- Change: {data.get('change', 0):.2f}%
- Volume: {data.get('volume', 0):,}
- Market Cap: ${data.get('market_cap', 0):,.0f}
- P/E Ratio: {data.get('pe_ratio', 0):.2f}
- 52W Range: ${data.get('52_week_low', 0):.2f} - ${data.get('52_week_high', 0):.2f}
"""
                results.append(result)

            except Exception as e:
                results.append(f"**{code}**: Error - {str(e)}")

        return "\n---\n".join(results)

    def validate_params(self, params: Dict[str, Any]) -> bool:
        codes = params.get("stockCodes", "")
        return bool(codes) and len(codes) > 0


class QueryKLineDataTool(BaseAgentTool):
    """
    K 线数据查询工具 - Get historical K-line (candlestick) data.

    Usage:
        QueryStockKLine(stockCode="AAPL", days=90, period="day")
    """

    def get_info(self) -> ToolInfo:
        return ToolInfo(
            name="QueryStockKLine",
            description="获取股票的历史 K 线数据，包括开盘价、最高价、最低价、收盘价、成交量",
            parameters=[
                ToolParameter(
                    name="stockCode",
                    type="string",
                    description="股票代码（A 股：sh 或 sz 开头；港股：hk 开头；美股：直接写代码如 AAPL）",
                    required=True
                ),
                ToolParameter(
                    name="days",
                    type="integer",
                    description="获取 K 线的天数，默认 90 天，最大 365 天",
                    required=False,
                    default=90
                ),
                ToolParameter(
                    name="period",
                    type="string",
                    description="K 线周期：day(日线), week(周线), month(月线)",
                    required=False,
                    default="day",
                    enum=["day", "week", "month"]
                )
            ]
        )

    async def execute(self, arguments: Dict[str, Any]) -> str:
        from tools.stock_data_tools import get_enhanced_data

        stock_code = arguments.get("stockCode")
        days = min(arguments.get("days", 90), 365)
        period = arguments.get("period", "day")

        # Convert days to period string
        if days <= 30:
            period_str = "1mo"
        elif days <= 90:
            period_str = "3mo"
        elif days <= 180:
            period_str = "6mo"
        elif days <= 365:
            period_str = "1y"
        else:
            period_str = "2y"

        try:
            data = get_enhanced_data(stock_code, period=period_str)
            history = data.get("price_history", [])

            if hasattr(history, 'tail'):
                # Pandas DataFrame
                recent = history.tail(days)
                table = recent[['Open', 'High', 'Low', 'Close', 'Volume']].to_string()
            else:
                table = "No price data available"

            return f"""
**{stock_code} K-Line Data (Last {days} {period})**

{table}

**Technical Indicators:**
- MA(20): ${data['technical'].get('ma_20', 'N/A')}
- MA(50): ${data['technical'].get('ma_50', 'N/A')}
- MA(200): ${data['technical'].get('ma_200', 'N/A')}
- RSI(14): {data['technical'].get('rsi', 'N/A')}
- MACD: {data['technical'].get('macd', 'N/A')}
- Support: ${data['technical'].get('support_level', 'N/A')}
- Resistance: ${data['technical'].get('resistance_level', 'N/A')}
"""

        except Exception as e:
            return f"Error fetching K-line data: {str(e)}"

    def validate_params(self, params: Dict[str, Any]) -> bool:
        code = params.get("stockCode", "")
        days = params.get("days", 90)
        return bool(code) and 1 <= days <= 365


class QueryMarketNewsTool(BaseAgentTool):
    """
    市场新闻查询工具 - Get market news and announcements.

    Usage:
        QueryMarketNews(category="all", limit=20)
    """

    def get_info(self) -> ToolInfo:
        return ToolInfo(
            name="QueryMarketNews",
            description="获取市场新闻、财经电报、公司公告、行业动态",
            parameters=[
                ToolParameter(
                    name="stockCode",
                    type="string",
                    description="股票代码（可选），仅获取该股票的新闻",
                    required=False
                ),
                ToolParameter(
                    name="category",
                    type="string",
                    description="新闻类别：all(全部), company(公司), sector(行业), macro(宏观)",
                    required=False,
                    default="all",
                    enum=["all", "company", "sector", "macro"]
                ),
                ToolParameter(
                    name="limit",
                    type="integer",
                    description="返回新闻条数，默认 20 条",
                    required=False,
                    default=20
                )
            ]
        )

    async def execute(self, arguments: Dict[str, Any]) -> str:
        import yfinance as yf

        stock_code = arguments.get("stockCode")
        limit = min(arguments.get("limit", 20), 50)

        if not stock_code:
            return "Please provide a stock code for news query."

        try:
            stock = yf.Ticker(stock_code)
            news = getattr(stock, 'news', [])[:limit]

            if not news:
                return f"No recent news found for {stock_code}"

            results = []
            for i, item in enumerate(news[:limit], 1):
                title = item.get('title', 'N/A')
                publisher = item.get('publisher', 'N/A')
                link = item.get('link', '#')
                published = item.get('providerPublishTime', 0)

                from datetime import datetime
                pub_date = datetime.fromtimestamp(published).strftime('%Y-%m-%d %H:%M') if published else 'N/A'

                results.append(f"""
{i}. **{title}**
   - Source: {publisher}
   - Published: {pub_date}
   - Link: [Read More]({link})
""")

            return "\n".join(results)

        except Exception as e:
            return f"Error fetching news: {str(e)}"

    def validate_params(self, params: Dict[str, Any]) -> bool:
        return True  # stockCode is optional


class QueryFinancialMetricsTool(BaseAgentTool):
    """
    财务数据查询工具 - Get financial metrics and statements.

    Usage:
        QueryFinancialMetrics(stockCode="AAPL", report_type="annual")
    """

    def get_info(self) -> ToolInfo:
        return ToolInfo(
            name="QueryFinancialMetrics",
            description="获取股票的财务指标和财务报表数据",
            parameters=[
                ToolParameter(
                    name="stockCode",
                    type="string",
                    description="股票代码",
                    required=True
                ),
                ToolParameter(
                    name="report_type",
                    type="string",
                    description="报告类型：annual(年报), quarterly(季报)",
                    required=False,
                    default="annual",
                    enum=["annual", "quarterly"]
                )
            ]
        )

    async def execute(self, arguments: Dict[str, Any]) -> str:
        import yfinance as yf

        stock_code = arguments.get("stockCode")
        report_type = arguments.get("report_type", "annual")

        try:
            stock = yf.Ticker(stock_code)
            info = stock.info

            # Key metrics
            metrics = {
                "Market Cap": f"${info.get('marketCap', 0):,.0f}",
                "P/E Ratio": f"{info.get('trailingPE', 0):.2f}",
                "Forward P/E": f"{info.get('forwardPE', 0):.2f}",
                "P/S Ratio": f"{info.get('priceToSalesTrailing12Months', 0):.2f}",
                "P/B Ratio": f"{info.get('priceToBook', 0):.2f}",
                "EV/EBITDA": f"{info.get('enterpriseToEbitda', 0):.2f}",
                "Profit Margin": f"{info.get('profitMargins', 0)*100:.2f}%",
                "Operating Margin": f"{info.get('operatingMargins', 0)*100:.2f}%",
                "ROE": f"{info.get('returnOnEquity', 0)*100:.2f}%",
                "ROA": f"{info.get('returnOnAssets', 0)*100:.2f}%",
                "Debt/Equity": f"{info.get('debtToEquity', 0):.2f}",
                "Current Ratio": f"{info.get('currentRatio', 0):.2f}",
                "Free Cash Flow": f"${info.get('freeCashflow', 0):,.0f}",
                "Revenue Growth": f"{info.get('revenueGrowth', 0)*100:.2f}%",
                "Earnings Growth": f"{info.get('earningsGrowth', 0)*100:.2f}%",
                "Dividend Yield": f"{info.get('dividendYield', 0)*100:.2f}%",
            }

            # Format as table
            table = "| Metric | Value |\n|--------|-------|\n"
            for k, v in metrics.items():
                table += f"| {k} | {v} |\n"

            return f"""
**{info.get('longName', stock_code)} Financial Metrics**
(Report Type: {report_type})

{table}

**Income Statement Summary:**
{stock.income_stmt.to_string() if stock.income_stmt is not None else "N/A"}

**Balance Sheet Summary:**
{stock.balance_sheet.to_string() if stock.balance_sheet is not None else "N/A"}
"""

        except Exception as e:
            return f"Error fetching financial metrics: {str(e)}"

    def validate_params(self, params: Dict[str, Any]) -> bool:
        code = params.get("stockCode", "")
        return bool(code)


class QueryMacroEconomyTool(BaseAgentTool):
    """
    宏观经济数据查询工具 - Get macroeconomic indicators.

    Usage:
        QueryMacroEconomy(indicators=["CPI", "GDP", "Unemployment"])
    """

    def get_info(self) -> ToolInfo:
        return ToolInfo(
            name="QueryMacroEconomy",
            description="获取美国宏观经济指标数据",
            parameters=[
                ToolParameter(
                    name="indicators",
                    type="array",
                    description="指标列表：GDP, CPI, Unemployment, Fed Rate, VIX, 10Y Yield",
                    items={"type": "string"},
                    required=False,
                    default=["CPI", "Fed Rate", "10Y Yield", "VIX"]
                )
            ]
        )

    async def execute(self, arguments: Dict[str, Any]) -> str:
        # Simulated macro data (in production, use FRED API)
        indicators = arguments.get("indicators", ["CPI", "Fed Rate", "10Y Yield", "VIX"])

        # Placeholder data (replace with FRED API in production)
        macro_data = {
            "GDP": {"value": "2.8%", "change": "+0.3%", "date": "2026-Q1"},
            "CPI": {"value": "3.2%", "change": "-0.1%", "date": "2026-02"},
            "Unemployment": {"value": "3.7%", "change": "0.0%", "date": "2026-02"},
            "Fed Rate": {"value": "5.25-5.50%", "change": "0.00%", "date": "2026-03"},
            "10Y Yield": {"value": "4.25%", "change": "+0.08%", "date": "2026-03-14"},
            "VIX": {"value": "15.2", "change": "-0.5", "date": "2026-03-14"},
            "DXY": {"value": "103.5", "change": "+0.2", "date": "2026-03-14"},
        }

        results = []
        for ind in indicators:
            if ind in macro_data:
                data = macro_data[ind]
                results.append(f"- **{ind}**: {data['value']} ({data['change']}) as of {data['date']}")

        return """
**US Macroeconomic Indicators**

""" + "\n".join(results) + """

**Market Risk Assessment:**
- VIX < 20: Low volatility environment
- 10Y Yield > 4%: Higher discount rate pressure on valuations
- DXY > 103: Strong dollar headwind for multinationals
"""

    def validate_params(self, params: Dict[str, Any]) -> bool:
        return True


# Export all tools
STOCK_TOOLS = [
    QueryStockPriceTool(),
    QueryKLineDataTool(),
    QueryMarketNewsTool(),
    QueryFinancialMetricsTool(),
    QueryMacroEconomyTool(),
]


def get_stock_tools() -> List[BaseAgentTool]:
    """Get all available stock analysis tools."""
    return STOCK_TOOLS
