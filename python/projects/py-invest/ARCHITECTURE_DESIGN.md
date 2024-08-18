# 基于多Agent的股票投资分析系统架构设计

## 一、整体架构概览

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              股票投资分析系统架构                                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │   用户交互层  │  │  可视化展示  │  │  配置管理   │  │      前端框架            │ │
│  │  (React/Vue)│  │  (ECharts)  │  │  (Settings) │  │   (Ant Design/Element)  │ │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └─────────────────────────┘ │
│         │                │                │                                      │
│  ┌──────▼────────────────▼────────────────▼───────────────────────────────────┐ │
│  │                         API Gateway (FastAPI)                              │ │
│  └──────┬─────────────────────────────────────────────────────────────────────┘ │
│         │                                                                        │
│  ┌──────▼─────────────────────────────────────────────────────────────────────┐ │
│  │                      核心业务逻辑层 (Business Logic)                         │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────────────┐ │ │
│  │  │  股票分析服务 │  │  市场资讯服务 │  │  智能选股服务 │  │   投资组合管理      │ │ │
│  │  │StockAnalyzer│  │ MarketNews  │  │  StockPick  │  │ PortfolioManager  │ │ │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └─────────┬──────────┘ │ │
│  │         │                │                │                    │            │ │
│  │         └────────────────┴────────────────┴────────────────────┘            │ │
│  │                                    │                                         │ │
│  │                         ┌──────────▼──────────┐                             │ │
│  │                         │   多Agent编排引擎    │                             │ │
│  │                         │   (Multi-Agent      │                             │ │
│  │                         │    Orchestrator)    │                             │ │
│  │                         └──────────┬──────────┘                             │ │
│  └────────────────────────────────────┼─────────────────────────────────────────┘ │
│                                       │                                          │
│  ┌────────────────────────────────────▼─────────────────────────────────────────┐ │
│  │                           Agent能力层 (Agent Tools)                           │ │
│  │                                                                              │ │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐            │ │
│  │  │ 股价查询Agent│ │ K线数据Agent │ │ 新闻资讯Agent│ │ 财务数据Agent│            │ │
│  │  │ PriceAgent  │ │  KLineAgent │ │  NewsAgent  │ │ Financial   │            │ │
│  │  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘ └──────┬──────┘            │ │
│  │  ┌──────┴──────┐ ┌──────┴──────┐ ┌──────┴──────┐ ┌──────┴──────┐            │ │
│  │  │行业研究Agent │ │ 宏观经济Agent│ │ 互动交流Agent│ │ 智能选股Agent│            │ │
│  │  │ Industry    │ │  Economic   │ │ Interactive │ │ StockPicker │            │ │
│  │  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘            │ │
│  │                                                                              │ │
│  └────────────────────────────────────┬─────────────────────────────────────────┘ │
│                                       │                                          │
│  ┌────────────────────────────────────▼─────────────────────────────────────────┐ │
│  │                        数据抓取与处理层 (Data Layer)                          │ │
│  │                                                                              │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────────────┐  │ │
│  │  │  实时数据爬虫 │  │  浏览器自动化 │  │  API数据源  │  │   数据缓存层        │  │ │
│  │  │  (Requests) │  │  (Selenium/  │  │  (Tushare/  │  │  (Redis/Cache)     │  │ │
│  │  │             │  │   Playwright)│  │   Sina API) │  │                    │  │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └────────────────────┘  │ │
│  └─────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────────────┐ │
│  │                         大模型交互层 (LLM Layer)                             │ │
│  │                                                                              │ │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────────┐  │ │
│  │  │   OpenAI兼容    │  │   LangChain/    │  │     多模型路由管理           │  │ │
│  │  │    接口封装     │  │    LangGraph    │  │  (OpenAI/DeepSeek/Qwen等)   │  │ │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────────────────┘  │ │
│  └─────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────────────┐ │
│  │                         数据存储层 (Storage)                                 │ │
│  │                                                                              │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────────────┐  │ │
│  │  │  PostgreSQL │  │   MongoDB   │  │    Redis    │  │   向量数据库        │  │ │
│  │  │ (结构化数据) │  │ (日志/文档)  │  │  (缓存/K线) │  │  (知识库/Embeddings)│  │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └────────────────────┘  │ │
│  └─────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                   │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 二、多Agent编排设计核心思想

### 2.1 ReAct (Reasoning + Acting) 模式

系统采用 **ReAct 模式** 作为多Agent编排的核心设计思想：

```
┌─────────────────────────────────────────────────────────────────────┐
│                         ReAct 循环流程                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   用户输入 ──▶ LLM思考 ──▶ 选择工具 ──▶ 执行工具 ──▶ 观察结果 ──▶ │
│                  ▲                                      │           │
│                  └──────────────────────────────────────┘           │
│                              (循环直至完成)                          │
│                                                                     │
│   示例流程：                                                          │
│   1. 用户："分析茅台股票走势"                                          │
│   2. 思考：需要获取股价、K线、新闻等多维度数据                            │
│   3. 行动：调用 QueryStockPriceInfo 工具                               │
│   4. 观察：获取到当前股价 ¥1688.88                                       │
│   5. 思考：还需要K线数据来判断趋势                                       │
│   6. 行动：调用 QueryStockKLine 工具                                   │
│   7. 观察：获取到近90日K线数据                                          │
│   8. 思考：结合新闻资讯进行综合分析                                       │
│   9. 行动：调用 QueryStockNews 工具                                    │
│   10. 完成：整合所有数据生成分析报告                                     │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 Agent设计原则

| 原则 | 说明 | 实践方式 |
|------|------|----------|
| **单一职责** | 每个Agent只负责一个具体领域 | PriceAgent只查询股价，不处理新闻 |
| **工具自描述** | Agent能力通过JSON Schema自描述 | 使用 OpenAPI 规范描述工具参数 |
| **可观测性** | 每个Agent的执行过程可追溯 | 记录思考链（Chain-of-Thought） |
| **可组合性** | Agent可以链式调用 | 使用 LangGraph 构建工作流 |

---

## 三、Agent工具分类与设计

### 3.1 工具分类体系

```python
# Python 技术栈 - Agent 工具基类设计
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field

class ToolParameter(BaseModel):
    """工具参数定义"""
    name: str
    type: str  # string, number, integer, boolean, array, object
    description: str
    required: bool = False
    enum: Optional[List[Any]] = None
    default: Optional[Any] = None

class ToolInfo(BaseModel):
    """工具元信息"""
    name: str
    description: str
    parameters: List[ToolParameter]
    
class BaseAgentTool(ABC):
    """Agent工具基类"""
    
    @abstractmethod
    def get_info(self) -> ToolInfo:
        """获取工具信息，供LLM理解工具用途"""
        pass
    
    @abstractmethod
    async def execute(self, arguments: Dict[str, Any]) -> str:
        """执行工具逻辑"""
        pass
    
    @abstractmethod
    def validate_params(self, params: Dict[str, Any]) -> bool:
        """参数校验"""
        pass
```

### 3.2 具体Agent工具设计

#### 3.2.1 股价查询Agent (PriceAgent)

```python
from typing import Dict, Any
import aiohttp

class QueryStockPriceTool(BaseAgentTool):
    """批量获取实时股价数据"""
    
    def get_info(self) -> ToolInfo:
        return ToolInfo(
            name="QueryStockPriceInfo",
            description="批量获取股票的实时股价、涨跌幅、成交量等数据",
            parameters=[
                ToolParameter(
                    name="stockCodes",
                    type="string",
                    description="股票代码列表，多个代码用逗号分隔。格式：sh600519(茅台),sz000001(平安)",
                    required=True
                )
            ]
        )
    
    async def execute(self, arguments: Dict[str, Any]) -> str:
        stock_codes = arguments.get("stockCodes", "").split(",")
        # 调用数据源API
        data = await self.fetch_realtime_data(stock_codes)
        return self.format_to_markdown(data)
    
    async def fetch_realtime_data(self, codes: list) -> dict:
        """从新浪/腾讯接口获取实时数据"""
        # 示例：使用新浪股票接口
        # http://hq.sinajs.cn/list=sh600519,sz000001
        pass
    
    def validate_params(self, params: Dict[str, Any]) -> bool:
        codes = params.get("stockCodes", "")
        return bool(codes) and all(c[:2] in ["sh", "sz", "hk", "us"] for c in codes.split(","))
```

#### 3.2.2 K线数据Agent (KLineAgent)

```python
class QueryStockKLineTool(BaseAgentTool):
    """获取股票K线数据，用于技术分析"""
    
    def get_info(self) -> ToolInfo:
        return ToolInfo(
            name="QueryStockKLine",
            description="获取股票的历史K线数据，包括开盘价、最高价、最低价、收盘价、成交量",
            parameters=[
                ToolParameter(
                    name="stockCode",
                    type="string",
                    description="股票代码（A股：sh或sz开头；港股：hk开头；美股：us开头）",
                    required=True
                ),
                ToolParameter(
                    name="days",
                    type="integer",
                    description="获取K线的天数，默认90天，最大365天",
                    required=False,
                    default=90
                ),
                ToolParameter(
                    name="period",
                    type="string",
                    description="K线周期：day(日线), week(周线), month(月线)",
                    required=False,
                    default="day",
                    enum=["day", "week", "month"]
                )
            ]
        )
    
    async def execute(self, arguments: Dict[str, Any]) -> str:
        stock_code = arguments.get("stockCode")
        days = arguments.get("days", 90)
        period = arguments.get("period", "day")
        
        kline_data = await self.fetch_kline(stock_code, days, period)
        return self.convert_to_markdown_table(kline_data)
```

#### 3.2.3 新闻资讯Agent (NewsAgent)

```python
class QueryMarketNewsTool(BaseAgentTool):
    """获取市场新闻、财经电报、研报资讯"""
    
    def get_info(self) -> ToolInfo:
        return ToolInfo(
            name="QueryMarketNews",
            description="获取国内外市场资讯、财联社电报、宏观经济事件、行业动态",
            parameters=[
                ToolParameter(
                    name="category",
                    type="string",
                    description="新闻类别：all(全部), telegraph(电报), research(研报), macro(宏观)",
                    required=False,
                    default="all",
                    enum=["all", "telegraph", "research", "macro"]
                ),
                ToolParameter(
                    name="limit",
                    type="integer",
                    description="返回新闻条数，默认20条",
                    required=False,
                    default=20
                )
            ]
        )
    
    async def execute(self, arguments: Dict[str, Any]) -> str:
        category = arguments.get("category", "all")
        limit = arguments.get("limit", 20)
        
        # 多源数据聚合
        news = []
        if category in ["all", "telegraph"]:
            news.extend(await self.fetch_cls_telegraph(limit))
        if category in ["all", "research"]:
            news.extend(await self.fetch_research_reports(limit))
        if category in ["all", "macro"]:
            news.extend(await self.fetch_macro_events(limit))
        
        return self.format_news_to_markdown(news)
```

#### 3.2.4 财务数据Agent (FinancialAgent)

```python
class GetFinancialReportTool(BaseAgentTool):
    """获取股票财务报表数据"""
    
    def get_info(self) -> ToolInfo:
        return ToolInfo(
            name="GetFinancialReport",
            description="查询股票的财务报表，包括资产负债表、利润表、现金流量表",
            parameters=[
                ToolParameter(
                    name="stockCode",
                    type="string",
                    description="股票代码（注意：A股需要sh或sz前缀）",
                    required=True
                ),
                ToolParameter(
                    name="reportType",
                    type="string",
                    description="报表类型：balance(资产负债表), income(利润表), cashflow(现金流量表)",
                    required=False,
                    default="all",
                    enum=["all", "balance", "income", "cashflow"]
                )
            ]
        )
    
    async def execute(self, arguments: Dict[str, Any]) -> str:
        stock_code = arguments.get("stockCode")
        report_type = arguments.get("reportType", "all")
        
        # 从多个数据源聚合财务数据
        reports = await self.fetch_financial_reports(stock_code, report_type)
        return self.format_financial_data(reports)
```

#### 3.2.5 行业研究Agent (IndustryAgent)

```python
class GetIndustryResearchTool(BaseAgentTool):
    """获取行业/板块研究报告"""
    
    def get_info(self) -> ToolInfo:
        return ToolInfo(
            name="GetIndustryResearchReport",
            description="获取特定行业或板块的研究报告、行业排名、板块资金流向",
            parameters=[
                ToolParameter(
                    name="code",
                    type="string",
                    description="行业/板块代码",
                    required=True
                ),
                ToolParameter(
                    name="name",
                    type="string",
                    description="行业名称（可选，用于辅助理解）",
                    required=False
                )
            ]
        )
```

#### 3.2.6 宏观经济Agent (EconomicAgent)

```python
class QueryEconomicDataTool(BaseAgentTool):
    """获取宏观经济数据"""
    
    def get_info(self) -> ToolInfo:
        return ToolInfo(
            name="QueryEconomicData",
            description="获取宏观经济指标：GDP、CPI、PPI、PMI、利率、汇率等",
            parameters=[
                ToolParameter(
                    name="indicator",
                    type="string",
                    description="经济指标类型：GDP, CPI, PPI, PMI, LPR(利率), EXCHANGE(汇率)",
                    required=True,
                    enum=["GDP", "CPI", "PPI", "PMI", "LPR", "EXCHANGE"]
                ),
                ToolParameter(
                    name="period",
                    type="string",
                    description="数据期间，如：2024, 2024Q1, latest",
                    required=False,
                    default="latest"
                )
            ]
        )
```

#### 3.2.7 互动交流Agent (InteractiveAgent)

```python
class GetInteractiveAnswerTool(BaseAgentTool):
    """获取投资者互动问答数据"""
    
    def get_info(self) -> ToolInfo:
        return ToolInfo(
            name="GetInteractiveAnswerData",
            description="获取上市公司与投资者的互动问答内容，了解公司最新动态",
            parameters=[
                ToolParameter(
                    name="stockCode",
                    type="string",
                    description="股票代码",
                    required=True
                ),
                ToolParameter(
                    name="days",
                    type="integer",
                    description="获取最近N天的问答，默认30天",
                    required=False,
                    default=30
                )
            ]
        )
```

#### 3.2.8 智能选股Agent (StockPickerAgent)

```python
class ChoiceStockByIndicatorsTool(BaseAgentTool):
    """基于技术指标筛选股票"""
    
    def get_info(self) -> ToolInfo:
        return ToolInfo(
            name="ChoiceStockByIndicators",
            description="基于技术指标筛选股票：涨幅、换手率、市盈率、资金流向等",
            parameters=[
                ToolParameter(
                    name="indicator",
                    type="string",
                    description="筛选指标：change(涨跌幅), turnover(换手率), pe(市盈率), fund(资金流向)",
                    required=True
                ),
                ToolParameter(
                    name="sort",
                    type="string",
                    description="排序方式：desc(降序), asc(升序)",
                    required=False,
                    default="desc"
                ),
                ToolParameter(
                    name="limit",
                    type="integer",
                    description="返回股票数量",
                    required=False,
                    default=20
                )
            ]
        )
```

---

## 四、数据抓取策略设计

### 4.1 数据源分类

```
┌─────────────────────────────────────────────────────────────────────┐
│                         数据源架构                                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                      实时行情数据                             │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │   │
│  │  │  新浪财经    │  │  腾讯财经    │  │   东方财富(延时)     │  │   │
│  │  │  (免费API)   │  │  (免费API)   │  │   (A股/港股/美股)    │  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                      历史数据                                 │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │   │
│  │  │  Tushare    │  │  AKShare    │  │   Yahoo Finance     │  │   │
│  │  │  (Python SDK)│  │  (Python SDK)│  │   (美股/港股)        │  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                      新闻资讯                                 │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │   │
│  │  │  财联社电报  │  │  TradingView│  │    Reuters/彭博     │  │   │
│  │  │  (网页爬取)  │  │  (API/爬取)  │  │   (国际财经)        │  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                      财务/研究数据                            │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │   │
│  │  │  雪球财经    │  │  东方财富    │  │   券商研报接口       │  │   │
│  │  │  (财报数据)  │  │  (研报数据)  │  │   (Choice/iFinD)    │  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.2 爬虫框架设计

```python
# Python 技术栈 - 数据抓取层
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import aiohttp
import asyncio
from dataclasses import dataclass
from enum import Enum

class DataSourceType(Enum):
    REALTIME_PRICE = "realtime_price"      # 实时股价
    KLINE_DATA = "kline_data"              # K线数据
    NEWS_TELEGRAPH = "news_telegraph"      # 财经电报
    FINANCIAL_REPORT = "financial_report"  # 财务报告
    RESEARCH_REPORT = "research_report"    # 研究报告
    MACRO_DATA = "macro_data"              # 宏观数据

@dataclass
class CrawlConfig:
    """爬虫配置"""
    timeout: int = 30
    retry_times: int = 3
    proxy: Optional[str] = None
    headers: Dict[str, str] = None
    
class BaseDataCrawler(ABC):
    """数据抓取基类"""
    
    def __init__(self, config: CrawlConfig):
        self.config = config
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            headers=self.config.headers or self.get_default_headers(),
            timeout=aiohttp.ClientTimeout(total=self.config.timeout)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    @abstractmethod
    def get_default_headers(self) -> Dict[str, str]:
        """获取默认请求头"""
        pass
    
    @abstractmethod
    async def fetch(self, **kwargs) -> Any:
        """抓取数据"""
        pass
    
    async def fetch_with_retry(self, url: str, **kwargs) -> str:
        """带重试机制的请求"""
        for attempt in range(self.config.retry_times):
            try:
                async with self.session.get(url, **kwargs) as response:
                    if response.status == 200:
                        return await response.text()
                    await asyncio.sleep(2 ** attempt)  # 指数退避
            except Exception as e:
                if attempt == self.config.retry_times - 1:
                    raise e
                await asyncio.sleep(2 ** attempt)
```

### 4.3 浏览器自动化爬虫

```python
from playwright.async_api import async_playwright, Page, Browser
from typing import Optional

class BrowserCrawler:
    """
    基于 Playwright 的浏览器自动化爬虫
    用于抓取需要JavaScript渲染的动态页面
    """
    
    def __init__(self, headless: bool = True, browser_path: Optional[str] = None):
        self.headless = headless
        self.browser_path = browser_path
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
    
    async def __aenter__(self):
        self.playwright = await async_playwright().start()
        
        browser_options = {
            "headless": self.headless,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
            ]
        }
        if self.browser_path:
            browser_options["executable_path"] = self.browser_path
        
        self.browser = await self.playwright.chromium.launch(**browser_options)
        
        context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36...",
            viewport={"width": 1920, "height": 1080},
        )
        
        self.page = await context.new_page()
        await self.page.evaluate("""
            () => {
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined})
            }
        """)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.browser:
            await self.browser.close()
        await self.playwright.stop()
    
    async def get_page_content(self, url: str, wait_for: str = "body") -> str:
        """获取页面HTML内容"""
        await self.page.goto(url, wait_until="networkidle")
        await self.page.wait_for_selector(wait_for)
        return await self.page.content()
    
    async def get_json_data(self, url: str) -> dict:
        """获取API返回的JSON数据"""
        response = await self.page.goto(url)
        return await response.json()
```

### 4.4 数据抓取调度器

```python
import asyncio
from typing import List, Callable
from dataclasses import dataclass
from datetime import datetime
import schedule

@dataclass
class CrawlTask:
    """爬虫任务定义"""
    name: str
    crawler: BaseDataCrawler
    interval_minutes: int
    callback: Callable
    last_run: Optional[datetime] = None

class DataCrawlScheduler:
    """
    数据抓取调度器
    管理多个数据源的定时抓取任务
    """
    
    def __init__(self):
        self.tasks: List[CrawlTask] = []
        self.running = False
        self.cache = {}  # 简单内存缓存
    
    def register_task(self, task: CrawlTask):
        """注册爬虫任务"""
        self.tasks.append(task)
    
    async def run_task(self, task: CrawlTask):
        """执行单个任务"""
        try:
            async with task.crawler as crawler:
                data = await crawler.fetch()
                task.last_run = datetime.now()
                
                # 缓存数据
                self.cache[task.name] = {
                    "data": data,
                    "timestamp": datetime.now()
                }
                
                # 回调处理
                if task.callback:
                    await task.callback(data)
                    
        except Exception as e:
            logger.error(f"Task {task.name} failed: {e}")
    
    async def start(self):
        """启动调度器"""
        self.running = True
        while self.running:
            now = datetime.now()
            for task in self.tasks:
                if (task.last_run is None or 
                    (now - task.last_run).seconds >= task.interval_minutes * 60):
                    asyncio.create_task(self.run_task(task))
            
            await asyncio.sleep(10)  # 每10秒检查一次
    
    def stop(self):
        self.running = False
```

---

## 五、LLM分析框架设计

### 5.1 多模型路由管理

```python
from enum import Enum
from typing import Optional, Dict, Any, AsyncGenerator
import openai
from dataclasses import dataclass

class LLMProvider(Enum):
    OPENAI = "openai"
    DEEPSEEK = "deepseek"
    QWEN = "qwen"
    SILICONFLOW = "siliconflow"
    VOLCANO = "volcano"
    CUSTOM = "custom"

@dataclass
class LLMConfig:
    """LLM配置"""
    provider: LLMProvider
    base_url: str
    api_key: str
    model_name: str
    max_tokens: int = 4096
    temperature: float = 0.1
    timeout: int = 300
    proxy: Optional[str] = None

class LLMRouter:
    """
    LLM路由器
    统一管理多个LLM提供商的调用
    """
    
    def __init__(self):
        self.clients: Dict[LLMProvider, openai.AsyncOpenAI] = {}
        self.configs: Dict[LLMProvider, LLMConfig] = {}
    
    def register_config(self, config: LLMConfig):
        """注册LLM配置"""
        client = openai.AsyncOpenAI(
            base_url=config.base_url,
            api_key=config.api_key,
            timeout=config.timeout,
        )
        self.clients[config.provider] = client
        self.configs[config.provider] = config
    
    async def chat_completion(
        self,
        provider: LLMProvider,
        messages: list,
        tools: Optional[list] = None,
        stream: bool = True
    ) -> AsyncGenerator[str, None]:
        """
        统一的聊天完成接口
        支持流式输出和工具调用
        """
        client = self.clients.get(provider)
        config = self.configs.get(provider)
        
        if not client or not config:
            raise ValueError(f"Provider {provider} not registered")
        
        request_params = {
            "model": config.model_name,
            "messages": messages,
            "max_tokens": config.max_tokens,
            "temperature": config.temperature,
            "stream": stream,
        }
        
        if tools:
            request_params["tools"] = tools
        
        if stream:
            async for chunk in await client.chat.completions.create(**request_params):
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        else:
            response = await client.chat.completions.create(**request_params)
            yield response.choices[0].message.content
```

### 5.2 ReAct Agent实现

```python
from typing import List, Dict, Any, Optional, Callable
import json
from dataclasses import dataclass, field

@dataclass
class AgentStep:
    """Agent执行的每一步记录"""
    thought: str
    action: str
    action_input: Dict[str, Any]
    observation: str
    step_number: int

@dataclass
class AgentResponse:
    """Agent最终响应"""
    final_answer: str
    steps: List[AgentStep]
    total_tokens: int
    execution_time: float

class ReActAgent:
    """
    ReAct (Reasoning + Acting) Agent实现
    核心思想：思考 -> 行动 -> 观察 -> 再思考 -> ...
    """
    
    def __init__(
        self,
        llm_router: LLMRouter,
        tools: List[BaseAgentTool],
        max_iterations: int = 10,
        system_prompt: Optional[str] = None
    ):
        self.llm_router = llm_router
        self.tools = {tool.get_info().name: tool for tool in tools}
        self.max_iterations = max_iterations
        self.system_prompt = system_prompt or self._default_system_prompt()
    
    def _default_system_prompt(self) -> str:
        return """你是一个专业的股票投资分析师，拥有20年实战经验。
你可以使用以下工具来获取数据进行分析：
{tool_descriptions}

请按照以下格式进行思考和行动：
Thought: 我需要分析...，我应该先获取...
Action: 工具名称
Action Input: {"参数名": "参数值"}
Observation: [工具返回的结果]
...
Final Answer: [最终分析结论]
"""
    
    def _format_tool_descriptions(self) -> str:
        """格式化工具描述供LLM理解"""
        descriptions = []
        for name, tool in self.tools.items():
            info = tool.get_info()
            desc = f"- {info.name}: {info.description}\n"
            desc += f"  参数: {[p.name for p in info.parameters]}"
            descriptions.append(desc)
        return "\n".join(descriptions)
    
    async def run(
        self,
        query: str,
        provider: LLMProvider,
        context: Optional[Dict[str, Any]] = None
    ) -> AgentResponse:
        """
        执行Agent分析流程
        """
        steps = []
        messages = [
            {"role": "system", "content": self.system_prompt.format(
                tool_descriptions=self._format_tool_descriptions()
            )},
            {"role": "user", "content": query}
        ]
        
        for step_num in range(self.max_iterations):
            # 1. 调用LLM获取思考和行动
            response = await self._call_llm(provider, messages)
            
            # 2. 解析响应
            parsed = self._parse_response(response)
            
            if "Final Answer" in parsed:
                # 任务完成
                return AgentResponse(
                    final_answer=parsed["Final Answer"],
                    steps=steps,
                    total_tokens=0,  # 实际从API返回获取
                    execution_time=0
                )
            
            # 3. 执行工具
            action = parsed.get("Action")
            action_input = parsed.get("Action Input", {})
            
            if action and action in self.tools:
                tool = self.tools[action]
                observation = await tool.execute(action_input)
                
                step = AgentStep(
                    thought=parsed.get("Thought", ""),
                    action=action,
                    action_input=action_input,
                    observation=observation,
                    step_number=step_num
                )
                steps.append(step)
                
                # 4. 将观察结果加入对话历史
                messages.append({"role": "assistant", "content": response})
                messages.append({
                    "role": "user", 
                    "content": f"Observation: {observation}\n继续分析。"
                })
            else:
                # 工具不存在，让LLM重新选择
                messages.append({"role": "assistant", "content": response})
                messages.append({
                    "role": "user",
                    "content": f"工具 '{action}' 不存在。请从以下工具中选择：{list(self.tools.keys())}"
                })
        
        # 超过最大迭代次数
        return AgentResponse(
            final_answer="分析超时，请简化问题或稍后重试",
            steps=steps,
            total_tokens=0,
            execution_time=0
        )
    
    async def _call_llm(self, provider: LLMProvider, messages: list) -> str:
        """调用LLM获取响应"""
        result = []
        async for chunk in self.llm_router.chat_completion(
            provider=provider,
            messages=messages,
            stream=False
        ):
            result.append(chunk)
        return "".join(result)
    
    def _parse_response(self, response: str) -> Dict[str, Any]:
        """解析LLM响应，提取Thought/Action/Action Input/Final Answer"""
        result = {}
        
        # 使用正则或简单字符串匹配解析
        import re
        
        thought_match = re.search(r"Thought:\s*(.+?)(?=Action:|Final Answer:|$)", response, re.DOTALL)
        if thought_match:
            result["Thought"] = thought_match.group(1).strip()
        
        action_match = re.search(r"Action:\s*(\w+)", response)
        if action_match:
            result["Action"] = action_match.group(1).strip()
        
        action_input_match = re.search(r"Action Input:\s*(\{.*?\})", response, re.DOTALL)
        if action_input_match:
            try:
                result["Action Input"] = json.loads(action_input_match.group(1))
            except:
                result["Action Input"] = {}
        
        final_answer_match = re.search(r"Final Answer:\s*(.+)", response, re.DOTALL)
        if final_answer_match:
            result["Final Answer"] = final_answer_match.group(1).strip()
        
        return result
```

### 5.3 工具调用版Agent (Function Calling)

```python
class FunctionCallingAgent:
    """
    基于OpenAI Function Calling的Agent
比ReAct更高效，直接返回结构化工具调用
    """
    
    def __init__(
        self,
        llm_router: LLMRouter,
        tools: List[BaseAgentTool],
        max_iterations: int = 10
    ):
        self.llm_router = llm_router
        self.tools_map = {tool.get_info().name: tool for tool in tools}
        self.max_iterations = max_iterations
        self.tools_schemas = [self._convert_to_openai_schema(tool) for tool in tools]
    
    def _convert_to_openai_schema(self, tool: BaseAgentTool) -> Dict[str, Any]:
        """将工具定义转换为OpenAI Function格式"""
        info = tool.get_info()
        return {
            "type": "function",
            "function": {
                "name": info.name,
                "description": info.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        p.name: {
                            "type": p.type,
                            "description": p.description,
                            **({"enum": p.enum} if p.enum else {})
                        }
                        for p in info.parameters
                    },
                    "required": [p.name for p in info.parameters if p.required]
                }
            }
        }
    
    async def run(
        self,
        query: str,
        provider: LLMProvider,
        system_prompt: Optional[str] = None
    ) -> AgentResponse:
        """执行Function Calling流程"""
        
        system_prompt = system_prompt or """你是一个专业的股票投资分析师。
你可以调用各种工具来获取数据并进行分析。
请根据用户需求，合理选择工具获取必要信息，然后给出专业分析。"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query}
        ]
        
        steps = []
        
        for step_num in range(self.max_iterations):
            # 调用LLM，传入工具定义
            client = self.llm_router.clients[provider]
            config = self.llm_router.configs[provider]
            
            response = await client.chat.completions.create(
                model=config.model_name,
                messages=messages,
                tools=self.tools_schemas,
                tool_choice="auto",
                max_tokens=config.max_tokens,
                temperature=config.temperature
            )
            
            message = response.choices[0].message
            
            # 检查是否有工具调用
            if message.tool_calls:
                # 执行工具调用
                tool_messages = []
                
                for tool_call in message.tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)
                    
                    if function_name in self.tools_map:
                        tool = self.tools_map[function_name]
                        observation = await tool.execute(function_args)
                        
                        step = AgentStep(
                            thought=f"调用工具: {function_name}",
                            action=function_name,
                            action_input=function_args,
                            observation=observation,
                            step_number=step_num
                        )
                        steps.append(step)
                        
                        tool_messages.append({
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": function_name,
                            "content": observation
                        })
                
                # 将assistant消息和工具结果加入历史
                messages.append({
                    "role": "assistant",
                    "content": message.content or "",
                    "tool_calls": [tc.model_dump() for tc in message.tool_calls]
                })
                messages.extend(tool_messages)
                
            else:
                # LLM直接给出了答案
                return AgentResponse(
                    final_answer=message.content,
                    steps=steps,
                    total_tokens=response.usage.total_tokens if response.usage else 0,
                    execution_time=0
                )
        
        return AgentResponse(
            final_answer="分析超时",
            steps=steps,
            total_tokens=0,
            execution_time=0
        )
```

---

## 六、高级分析功能设计

### 6.1 智能选股工作流

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated, Sequence
import operator

class StockPickState(TypedDict):
    """选股工作流状态"""
    criteria: dict           # 选股条件
    candidates: list         # 候选股票
    analyzed_stocks: list    # 已分析股票
    final_picks: list        # 最终推荐
    current_step: str        # 当前步骤

class StockPickingWorkflow:
    """智能选股工作流 - 使用LangGraph实现"""
    
    def __init__(self, agent: FunctionCallingAgent):
        self.agent = agent
        self.workflow = self._build_workflow()
    
    def _build_workflow(self):
        """构建选股工作流图"""
        
        # 定义工作流步骤
        def filter_by_technical(state: StockPickState) -> StockPickState:
            """技术指标筛选"""
            # 调用技术指标Agent
            result = self.agent.run(
                f"基于以下条件筛选股票：{state['criteria']}",
                provider=LLMProvider.DEEPSEEK
            )
            # 解析结果，更新candidates
            return state
        
        def filter_by_fundamental(state: StockPickState) -> StockPickState:
            """基本面筛选"""
            # 财务数据分析
            return state
        
        def sentiment_analysis(state: StockPickState) -> StockPickState:
            """情感分析"""
            # 新闻情感分析
            return state
        
        def risk_assessment(state: StockPickState) -> StockPickState:
            """风险评估"""
            return state
        
        def generate_report(state: StockPickState) -> StockPickState:
            """生成选股报告"""
            return state
        
        # 构建图
        workflow = StateGraph(StockPickState)
        
        # 添加节点
        workflow.add_node("technical", filter_by_technical)
        workflow.add_node("fundamental", filter_by_fundamental)
        workflow.add_node("sentiment", sentiment_analysis)
        workflow.add_node("risk", risk_assessment)
        workflow.add_node("report", generate_report)
        
        # 添加边
        workflow.set_entry_point("technical")
        workflow.add_edge("technical", "fundamental")
        workflow.add_edge("fundamental", "sentiment")
        workflow.add_edge("sentiment", "risk")
        workflow.add_edge("risk", "report")
        workflow.add_edge("report", END)
        
        return workflow.compile()
    
    async def run(self, criteria: dict) -> StockPickState:
        """执行选股流程"""
        initial_state = StockPickState(
            criteria=criteria,
            candidates=[],
            analyzed_stocks=[],
            final_picks=[],
            current_step="start"
        )
        return await self.workflow.ainvoke(initial_state)
```

### 6.2 情感分析引擎

```python
from typing import List, Dict
import jieba
import jieba.analyse
from collections import Counter

class SentimentAnalyzer:
    """
    新闻情感分析引擎
    结合规则+LLM进行多维度情感分析
    """
    
    def __init__(self):
        # 情感词典
        self.positive_words = set([
            "上涨", "利好", "突破", "增长", "盈利", "增持", "推荐", "买入",
            "强劲", "超预期", "创新高", "扩张", "复苏", "景气"
        ])
        self.negative_words = set([
            "下跌", "利空", "跌破", "亏损", "减持", "卖出", "回避",
            "疲软", "不及预期", "创新低", "收缩", "衰退", "风险"
        ])
    
    def analyze(self, text: str) -> Dict[str, any]:
        """情感分析"""
        # 1. 基于规则的情感计算
        words = jieba.lcut(text)
        
        pos_count = sum(1 for w in words if w in self.positive_words)
        neg_count = sum(1 for w in words if w in self.negative_words)
        
        # 2. 计算情感得分
        total = pos_count + neg_count
        if total == 0:
            sentiment_score = 0
            category = "neutral"
        else:
            sentiment_score = (pos_count - neg_count) / total
            if sentiment_score > 0.2:
                category = "positive"
            elif sentiment_score < -0.2:
                category = "negative"
            else:
                category = "neutral"
        
        # 3. 提取关键词
        keywords = jieba.analyse.extract_tags(text, topK=5)
        
        return {
            "score": sentiment_score,
            "category": category,
            "positive_count": pos_count,
            "negative_count": neg_count,
            "keywords": keywords,
            "description": self._get_description(category, sentiment_score)
        }
    
    def _get_description(self, category: str, score: float) -> str:
        """获取情感描述"""
        if category == "positive":
            return f"正面({score:.2f})"
        elif category == "negative":
            return f"负面({score:.2f})"
        return f"中性({score:.2f})"
```

---

## 七、Python技术栈推荐

### 7.1 核心依赖

```txt
# Web框架
fastapi==0.109.0
uvicorn[standard]==0.27.0

# LLM框架
langchain==0.1.0
langgraph==0.0.20
openai==1.10.0

# 数据抓取
aiohttp==3.9.0
playwright==1.41.0
requests==2.31.0
beautifulsoup4==4.12.0

# 数据处理
pandas==2.1.0
numpy==1.26.0
akshare==1.12.0
tushare==1.3.0

# 数据存储
sqlalchemy==2.0.0
alembic==1.13.0
redis==5.0.0
motor==3.3.0  # MongoDB async

# 自然语言处理
jieba==0.42.1

# 任务调度
celery==5.3.0
schedule==1.2.0

# 配置管理
pydantic==2.5.0
pydantic-settings==2.1.0

# 日志
loguru==0.7.0

# 测试
pytest==7.4.0
pytest-asyncio==0.21.0
```

### 7.2 项目目录结构

```
stock_ai_analysis/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI入口
│   ├── config.py               # 配置管理
│   ├── api/
│   │   ├── __init__.py
│   │   ├── router.py           # 路由聚合
│   │   ├── stock.py            # 股票相关API
│   │   ├── analysis.py         # 分析API
│   │   └── news.py             # 新闻API
│   ├── core/
│   │   ├── __init__.py
│   │   ├── agent/
│   │   │   ├── __init__.py
│   │   │   ├── base.py         # Agent基类
│   │   │   ├── react.py        # ReAct Agent
│   │   │   ├── function_calling.py  # Function Calling Agent
│   │   │   └── tools/
│   │   │       ├── __init__.py
│   │   │       ├── base.py
│   │   │       ├── price.py
│   │   │       ├── kline.py
│   │   │       ├── news.py
│   │   │       ├── financial.py
│   │   │       └── ...
│   │   ├── llm/
│   │   │   ├── __init__.py
│   │   │   ├── router.py       # LLM路由
│   │   │   └── providers.py    # 提供商配置
│   │   └── workflow/
│   │       ├── __init__.py
│   │       ├── stock_picker.py
│   │       └── market_analysis.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── stock_service.py
│   │   ├── analysis_service.py
│   │   └── news_service.py
│   ├── data/
│   │   ├── __init__.py
│   │   ├── crawlers/
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   ├── sina.py
│   │   │   ├── tencent.py
│   │   │   ├── cls.py          # 财联社
│   │   │   └── browser.py      # 浏览器爬虫
│   │   ├── scheduler.py        # 调度器
│   │   └── cache.py            # 缓存管理
│   ├── models/
│   │   ├── __init__.py
│   │   ├── database.py         # ORM模型
│   │   └── schemas.py          # Pydantic模型
│   └── utils/
│       ├── __init__.py
│       └── helpers.py
├── tests/
├── alembic/                    # 数据库迁移
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

---

## 八、总结

本架构设计的核心思想：

1. **多Agent编排**：采用 ReAct + Function Calling 双模式，根据场景灵活选择
2. **数据驱动**：统一的数据抓取层，支持多源异构数据
3. **LLM路由**：支持多模型并行，根据任务特性选择最优模型
4. **可扩展性**：每个Agent独立设计，支持动态注册新工具
5. **实时性**：流式输出+异步处理，提供良好的用户体验

关键设计决策：
- 使用 **LangGraph** 构建复杂工作流（如智能选股）
- 使用 **Function Calling** 替代传统的Prompt工程，提高工具调用准确性
- 数据抓取采用 **分层架构**：API优先，浏览器自动化兜底
- **缓存策略**：热点数据内存缓存，历史数据持久化存储
