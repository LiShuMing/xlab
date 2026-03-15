# Stock Analyzer 系统设计文档

**版本**：v1.0.0  
**日期**：2026-03-14  
**语言**：Python 3.11+

---

## 目录

1. [设计目标](#1-设计目标)
2. [架构总览](#2-架构总览)
3. [分层设计](#3-分层设计)
   - 3.1 接入层 Interface Layer
   - 3.2 编排层 Orchestration Layer
   - 3.3 分析层 Analysis Layer
   - 3.4 数据层 Data Layer
   - 3.5 输出层 Output Layer
   - 3.6 基础设施层 Infrastructure Layer
4. [模块设计](#4-模块设计)
5. [数据流设计](#5-数据流设计)
6. [扩展性设计](#6-扩展性设计)
7. [配置管理](#7-配置管理)
8. [项目目录结构](#8-项目目录结构)
9. [依赖清单](#9-依赖清单)

---

## 1. 设计目标

### 1.1 核心目标

本系统面向个人投资者，基于 LLM AI 工具链，自动生成具备参考价值的股票投资分析报告。报告涵盖宏观背景、技术面、基本面、多视角投资论点及仓位建议，并支持 Web 页面展示与邮件推送。

### 1.2 设计原则

| 原则 | 说明 |
|---|---|
| 单一职责 Single Responsibility | 每个模块仅负责一项明确功能，避免耦合 |
| 开闭原则 Open/Closed | 对扩展开放，对修改封闭；新增数据源或 LLM 无需改动核心逻辑 |
| 依赖倒置 Dependency Inversion | 上层模块依赖抽象接口，不依赖具体实现 |
| 分层隔离 Layer Isolation | 相邻层之间通过标准接口通信，层内实现对外透明 |
| 可观测性 Observability | 各层均提供结构化日志与错误上报能力 |

### 1.3 非功能需求

- **响应时间**：单次报告生成 ≤ 90 秒（含数据采集与 LLM 推理）
- **可用性**：单一数据源故障不影响核心分析流程（降级策略）
- **可扩展性**：新增 LLM 提供商、数据源、输出渠道，无需修改已有模块
- **安全性**：API Key 与敏感配置通过环境变量管理，不硬编码

---

## 2. 架构总览

系统采用**六层架构**，从上至下依次为：接入层、编排层、分析层、数据层、输出层、基础设施层。各层职责清晰，通过标准接口向下依赖。

```
┌─────────────────────────────────────────────────────┐
│              接入层  Interface Layer                 │
│         Web UI  /  CLI  /  REST API  /  Schedule     │
├─────────────────────────────────────────────────────┤
│             编排层  Orchestration Layer              │
│          LangChain Agent  /  Chain  /  Router        │
├─────────────────────────────────────────────────────┤
│              分析层  Analysis Layer                  │
│    Macro Analyst  /  Technical  /  Fundamental       │
│    Multi-Lens Synthesizer  /  Risk Matrix Builder    │
├─────────────────────────────────────────────────────┤
│               数据层  Data Layer                     │
│   Market Data  /  Financials  /  News  /  Macro      │
├─────────────────────────────────────────────────────┤
│               输出层  Output Layer                   │
│        HTML Report  /  Email  /  PDF  /  JSON        │
├─────────────────────────────────────────────────────┤
│           基础设施层  Infrastructure Layer           │
│      Config  /  Logger  /  Cache  /  Rate Limiter    │
└─────────────────────────────────────────────────────┘
```

---

## 3. 分层设计

### 3.1 接入层 Interface Layer

**职责**：接收用户输入，路由至编排层，返回最终结果。该层不包含业务逻辑。

**组件**：

| 组件 | 技术实现 | 说明 |
|---|---|---|
| Web UI | FastAPI + Jinja2 | 表单提交，浏览器展示 HTML 报告 |
| REST API | FastAPI Router | 供外部系统调用，返回 JSON 或 HTML |
| CLI | Click / Typer | 命令行直接生成报告，适合脚本集成 |
| Scheduler | APScheduler | 定时任务，支持每日定时推送 |

**接口规范**：

```python
# 统一请求结构
class AnalysisRequest(BaseModel):
    ticker: str               # 股票代码，如 "AAPL"
    query: str                # 用户自然语言问题
    output_format: str        # "html" | "json" | "pdf"
    email: Optional[str]      # 邮件推送地址（选填）
    language: str = "zh-CN"   # 报告语言

# 统一响应结构
class AnalysisResponse(BaseModel):
    ticker: str
    company_name: str
    generated_at: str         # ISO 8601 时间戳
    report_html: Optional[str]
    report_json: Optional[dict]
    error: Optional[str]
```

---

### 3.2 编排层 Orchestration Layer

**职责**：协调各分析模块的执行顺序，管理 LLM 调用链路，处理工具调用（Tool Use）与 Agent 循环。

**核心设计**：

```
AnalysisOrchestrator
├── build_chain()       → 组装 LangChain 链路
├── build_agent()       → 构建 ReAct Agent（工具调用模式）
├── route_query()       → 根据查询类型选择链路
└── execute()           → 执行并返回 AnalysisResult
```

**两种执行模式**：

| 模式 | 适用场景 | 实现 |
|---|---|---|
| Chain 模式 | 标准报告生成（确定性强） | `ANALYSIS_PROMPT \| LLM \| OutputParser` |
| Agent 模式 | 复杂查询、需多轮工具调用 | `create_react_agent(llm, tools)` |

**Prompt 注入策略**：

System Prompt 通过 `ChatPromptTemplate` 统一管理，分析视角（Buffett / 段永平 / Trader 等）以结构化文本注入，支持按查询类型动态调整视角权重。

---

### 3.3 分析层 Analysis Layer

**职责**：将原始数据转化为结构化分析结论。各分析器相互独立，结果由 `Synthesizer` 合并。

**模块划分**：

```
analysis/
├── macro_analyst.py       # 宏观背景分析（VIX、Fed、DXY、市场结构）
├── technical_analyst.py   # 技术面分析（MA、RSI、MACD、Support/Resistance）
├── fundamental_analyst.py # 基本面分析（P/E、FCF、ROE、同业对比）
├── risk_analyst.py        # 风险矩阵构建（五类风险、概率×影响评级）
├── position_advisor.py    # 仓位建议（止损位、目标价、分批方案）
└── synthesizer.py         # 多视角合并与综合评级输出
```

**各模块标准接口**：

```python
from abc import ABC, abstractmethod

class BaseAnalyst(ABC):
    @abstractmethod
    def analyze(self, data: dict) -> dict:
        """
        输入：标准化数据字典
        输出：结构化分析结论字典
        """
        pass

    @abstractmethod
    def get_prompt_fragment(self, result: dict) -> str:
        """将分析结论转为 Prompt 片段，供 Synthesizer 使用"""
        pass
```

所有分析器继承 `BaseAnalyst`，`Synthesizer` 收集各模块输出后统一调用 LLM 生成最终报告。

---

### 3.4 数据层 Data Layer

**职责**：从外部数据源采集原始数据，标准化后向上提供，屏蔽数据源差异。

**数据源分类**：

| 数据类型 | 主数据源 | 备用数据源 | 数据内容 |
|---|---|---|---|
| 价格 / 行情 | yfinance | Alpha Vantage | OHLCV、MA、52W区间 |
| 财务报表 | yfinance | Polygon.io | Revenue、EPS、FCF、资产负债 |
| 技术指标 | pandas-ta | Alpha Vantage | RSI、MACD、Bollinger Bands |
| 宏观数据 | FRED API | World Bank API | CPI、利率、GDP |
| 新闻 / 舆情 | Tavily Search | SerpAPI | 公司新闻、行业动态 |
| 分析师评级 | yfinance | Finviz | 目标价、推荐评级 |

**数据提供者接口**：

```python
from abc import ABC, abstractmethod

class BaseDataProvider(ABC):
    @abstractmethod
    def fetch(self, ticker: str, **kwargs) -> dict:
        """返回标准化数据字典"""
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """数据源健康检查，用于降级策略"""
        pass

# 示例实现
class YFinanceProvider(BaseDataProvider):
    def fetch(self, ticker: str, **kwargs) -> dict: ...
    def health_check(self) -> bool: ...

class AlphaVantageProvider(BaseDataProvider):
    def fetch(self, ticker: str, **kwargs) -> dict: ...
    def health_check(self) -> bool: ...
```

**数据聚合器（DataAggregator）**：

统一管理多个 Provider，实现主备切换与数据合并：

```python
class DataAggregator:
    def __init__(self, providers: list[BaseDataProvider]): ...

    def fetch_all(self, ticker: str) -> dict:
        """
        按优先级依次调用 Provider。
        若主数据源失败，自动降级至备用源，并记录告警日志。
        """
        pass
```

**标准化数据结构（StockData）**：

```python
class StockData(BaseModel):
    ticker: str
    company_name: str
    sector: str
    price: PriceData         # latest, ma50, ma200, 52w_high, 52w_low
    financials: Financials   # revenue, eps, fcf, net_margin, roe
    valuation: Valuation     # pe, ps, pb, ev_ebitda, vs_sector_avg
    macro: MacroContext      # vix, dxy, fed_rate, cpi
    news: list[NewsItem]     # title, summary, source, published_at
    fetched_at: str          # 数据采集时间戳
```

---

### 3.5 输出层 Output Layer

**职责**：将结构化分析结果渲染为目标格式，并通过指定渠道分发。

**渲染器（Renderer）**：

```python
from abc import ABC, abstractmethod

class BaseRenderer(ABC):
    @abstractmethod
    def render(self, report: AnalysisReport) -> str:
        """将 AnalysisReport 转换为目标格式字符串"""
        pass

class HtmlRenderer(BaseRenderer):
    """Markdown → HTML，内嵌 CSS，支持 Dark Mode，响应式布局"""
    def render(self, report: AnalysisReport) -> str: ...

class JsonRenderer(BaseRenderer):
    """输出结构化 JSON，供 API 消费者使用"""
    def render(self, report: AnalysisReport) -> str: ...

class PdfRenderer(BaseRenderer):
    """HTML → PDF，使用 WeasyPrint"""
    def render(self, report: AnalysisReport) -> str: ...
```

**分发器（Dispatcher）**：

```python
class BaseDispatcher(ABC):
    @abstractmethod
    def dispatch(self, content: str, destination: str, **kwargs) -> bool:
        """发送内容至目标地址，返回是否成功"""
        pass

class EmailDispatcher(BaseDispatcher):
    """支持 SMTP 与 SendGrid 双通道，HTML 邮件格式"""
    def dispatch(self, content: str, destination: str, **kwargs) -> bool: ...

class WebDispatcher(BaseDispatcher):
    """直接返回 HTTP 响应，由 FastAPI 路由层调用"""
    def dispatch(self, content: str, destination: str, **kwargs) -> bool: ...

class SlackDispatcher(BaseDispatcher):
    """推送摘要到 Slack 频道（扩展预留）"""
    def dispatch(self, content: str, destination: str, **kwargs) -> bool: ...
```

---

### 3.6 基础设施层 Infrastructure Layer

**职责**：提供横切关注点（Cross-cutting Concerns），所有上层模块均可依赖。

| 组件 | 实现 | 说明 |
|---|---|---|
| 配置管理 Config | `pydantic-settings` | 环境变量统一读取，类型安全，支持 `.env` 文件 |
| 日志 Logger | `structlog` | 结构化日志，JSON 格式，支持日志级别动态调整 |
| 缓存 Cache | `diskcache` / Redis | 数据层结果缓存，TTL 可配置（默认 30 分钟） |
| 限流 Rate Limiter | `limits` | API 调用频率控制，防止超出第三方限额 |
| 重试 Retry | `tenacity` | 网络请求自动重试，指数退避策略 |
| 异常处理 Exception | 自定义异常层级 | 各层异常标准化，统一向上传播 |

**配置管理示例**：

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # LLM
    anthropic_api_key: str
    openai_api_key: str = ""
    llm_provider: str = "anthropic"        # "anthropic" | "openai" | "deepseek"
    llm_model: str = "claude-sonnet-4-20250514"
    llm_temperature: float = 0.3
    llm_max_tokens: int = 4000

    # 数据源
    tavily_api_key: str = ""
    alpha_vantage_api_key: str = ""
    fred_api_key: str = ""

    # 邮件
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    sendgrid_api_key: str = ""

    # 缓存
    cache_ttl_seconds: int = 1800          # 30 分钟
    cache_dir: str = ".cache"

    # 账户
    portfolio_size_usd: float = 30000.0

    class Config:
        env_file = ".env"

settings = Settings()
```

---

## 4. 模块设计

### 4.1 模块依赖关系

```
Interface Layer
    └── depends on → Orchestration Layer
                         └── depends on → Analysis Layer
                                              └── depends on → Data Layer
                         └── depends on → Output Layer
                                              └── depends on → Renderer / Dispatcher
All Layers
    └── depends on → Infrastructure Layer (Config, Logger, Cache)
```

**依赖方向**：单向向下，上层依赖下层，下层不感知上层。

### 4.2 LLM 提供商抽象

通过 LangChain 的统一接口，屏蔽不同 LLM 提供商的 API 差异：

```python
from langchain_core.language_models import BaseChatModel

class LLMFactory:
    @staticmethod
    def create(provider: str, **kwargs) -> BaseChatModel:
        if provider == "anthropic":
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(model=kwargs.get("model", "claude-sonnet-4-20250514"), ...)
        elif provider == "openai":
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(model=kwargs.get("model", "gpt-4o"), ...)
        elif provider == "deepseek":
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(base_url="https://api.deepseek.com/v1", ...)
        raise ValueError(f"Unsupported provider: {provider}")
```

切换 LLM 提供商只需修改 `.env` 中的 `LLM_PROVIDER` 配置项。

---

## 5. 数据流设计

### 5.1 标准请求流程

```
用户输入 (ticker + query)
    │
    ▼
[接入层] 参数校验 → AnalysisRequest
    │
    ▼
[编排层] 路由选择 (Chain / Agent)
    │
    ├──► [数据层] DataAggregator.fetch_all(ticker)
    │         ├── YFinanceProvider.fetch()     → 价格、财务
    │         ├── TavilySearchProvider.fetch() → 新闻、宏观
    │         └── FREDProvider.fetch()         → CPI、利率
    │         ↓
    │    StockData（标准化数据结构）
    │
    ├──► [分析层] 并行执行各分析器
    │         ├── MacroAnalyst.analyze()
    │         ├── TechnicalAnalyst.analyze()
    │         ├── FundamentalAnalyst.analyze()
    │         ├── RiskAnalyst.analyze()
    │         └── PositionAdvisor.analyze()
    │         ↓
    │    各模块分析结论 → Synthesizer
    │
    ├──► [LLM] 注入 Prompt → 生成 Markdown 报告
    │
    ▼
[输出层]
    ├── HtmlRenderer.render()  → HTML 页面
    ├── EmailDispatcher.dispatch() → 邮件推送
    └── JsonRenderer.render()  → API 响应
```

### 5.2 缓存策略

```
数据层 fetch() 调用
    │
    ▼
Cache.get(key=f"{ticker}:{date}:{source}")
    ├── 命中 → 直接返回缓存数据
    └── 未命中 → 调用外部 API → 写入缓存（TTL=30min）→ 返回数据
```

缓存键格式：`{ticker}:{data_type}:{YYYYMMDD}`，相同股票同日多次查询复用缓存，减少 API 调用次数。

---

## 6. 扩展性设计

### 6.1 新增数据源

仅需实现 `BaseDataProvider` 接口，在 `DataAggregator` 中注册，无需修改其他模块：

```python
# 新增 Polygon.io 数据源
class PolygonProvider(BaseDataProvider):
    def fetch(self, ticker: str, **kwargs) -> dict:
        # 实现 Polygon.io API 调用
        ...
    def health_check(self) -> bool: ...

# 在 DataAggregator 中注册（配置文件驱动）
aggregator = DataAggregator(providers=[
    YFinanceProvider(),       # 主数据源
    PolygonProvider(),        # 备用数据源（新增）
    AlphaVantageProvider(),   # 技术指标补充
])
```

### 6.2 新增 LLM 提供商

在 `LLMFactory` 中新增 `elif` 分支，配置文件切换 `LLM_PROVIDER` 即可：

```python
elif provider == "gemini":
    from langchain_google_genai import ChatGoogleGenerativeAI
    return ChatGoogleGenerativeAI(model="gemini-1.5-pro", ...)
```

### 6.3 新增输出渠道

实现 `BaseDispatcher` 接口，在输出层注册：

```python
# 新增 Telegram 推送
class TelegramDispatcher(BaseDispatcher):
    def dispatch(self, content: str, destination: str, **kwargs) -> bool:
        # destination 为 chat_id
        ...

# 新增企业微信推送
class WeChatWorkDispatcher(BaseDispatcher):
    def dispatch(self, content: str, destination: str, **kwargs) -> bool: ...
```

### 6.4 新增分析视角

在 `analysis/` 目录新增分析器，继承 `BaseAnalyst`，在 `Synthesizer` 中注册：

```python
# 新增 ESG 分析视角
class ESGAnalyst(BaseAnalyst):
    def analyze(self, data: dict) -> dict:
        # 分析 ESG 评级、碳排放、治理结构
        ...
    def get_prompt_fragment(self, result: dict) -> str: ...
```

---

## 7. 配置管理

所有可变参数通过 `.env` 文件统一配置，系统启动时由 `Settings` 类读取并校验。业务代码通过 `from config import settings` 引用，不直接读取 `os.environ`。

**配置分类**：

| 类别 | 变量前缀 | 示例 |
|---|---|---|
| LLM 提供商 | `LLM_` | `LLM_PROVIDER`, `LLM_TEMPERATURE` |
| 数据源 API Key | `*_API_KEY` | `TAVILY_API_KEY`, `FRED_API_KEY` |
| 邮件发送 | `SMTP_` / `SENDGRID_` | `SMTP_HOST`, `SENDGRID_API_KEY` |
| 缓存 | `CACHE_` | `CACHE_TTL_SECONDS`, `CACHE_DIR` |
| 账户参数 | `PORTFOLIO_` | `PORTFOLIO_SIZE_USD` |
| 服务部署 | `APP_` | `APP_HOST`, `APP_PORT`, `APP_DEBUG` |

---

## 8. 项目目录结构

```
stock_analyzer/
│
├── config.py                    # Settings（pydantic-settings）
│
├── interface/                   # 接入层
│   ├── __init__.py
│   ├── web.py                   # FastAPI 路由
│   ├── cli.py                   # Click CLI 入口
│   └── scheduler.py             # APScheduler 定时任务
│
├── orchestration/               # 编排层
│   ├── __init__.py
│   ├── orchestrator.py          # AnalysisOrchestrator
│   ├── chains.py                # LangChain Chain 定义
│   ├── agents.py                # LangChain Agent 定义
│   └── prompts.py               # Prompt Template 管理
│
├── analysis/                    # 分析层
│   ├── __init__.py
│   ├── base.py                  # BaseAnalyst 抽象类
│   ├── macro_analyst.py
│   ├── technical_analyst.py
│   ├── fundamental_analyst.py
│   ├── risk_analyst.py
│   ├── position_advisor.py
│   └── synthesizer.py
│
├── data/                        # 数据层
│   ├── __init__.py
│   ├── base.py                  # BaseDataProvider 抽象类
│   ├── aggregator.py            # DataAggregator
│   ├── providers/
│   │   ├── yfinance_provider.py
│   │   ├── tavily_provider.py
│   │   ├── fred_provider.py
│   │   └── alpha_vantage_provider.py
│   └── models.py                # StockData, PriceData 等 Pydantic 模型
│
├── output/                      # 输出层
│   ├── __init__.py
│   ├── renderers/
│   │   ├── base.py              # BaseRenderer 抽象类
│   │   ├── html_renderer.py
│   │   ├── json_renderer.py
│   │   └── pdf_renderer.py
│   └── dispatchers/
│       ├── base.py              # BaseDispatcher 抽象类
│       ├── email_dispatcher.py
│       ├── web_dispatcher.py
│       └── slack_dispatcher.py  # 扩展预留
│
├── infrastructure/              # 基础设施层
│   ├── __init__.py
│   ├── logger.py                # structlog 配置
│   ├── cache.py                 # diskcache / Redis 封装
│   ├── rate_limiter.py          # API 调用限流
│   └── exceptions.py            # 自定义异常层级
│
├── templates/                   # Jinja2 HTML 模板
│   └── report.html
│
├── tests/                       # 测试
│   ├── unit/
│   ├── integration/
│   └── fixtures/
│
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## 9. 依赖清单

```
# LangChain 工具链
langchain>=0.3.0
langchain-anthropic>=0.3.0
langchain-openai>=0.2.0
langchain-community>=0.3.0

# 数据采集
yfinance>=0.2.40
tavily-python>=0.5.0
fredapi>=0.5.0
pandas-ta>=0.3.14b

# Web 服务
fastapi>=0.115.0
uvicorn[standard]>=0.32.0
python-multipart>=0.0.12
jinja2>=3.1.0

# 数据处理
pydantic>=2.7.0
pydantic-settings>=2.3.0
pandas>=2.2.0
markdown2>=2.5.0

# 输出
weasyprint>=62.0           # PDF 导出
sendgrid>=6.11.0           # 邮件推送

# 基础设施
structlog>=24.0.0          # 结构化日志
diskcache>=5.6.0           # 磁盘缓存
tenacity>=8.3.0            # 自动重试
limits>=3.13.0             # 限流

# CLI
typer>=0.12.0

# 测试
pytest>=8.0.0
pytest-asyncio>=0.23.0
respx>=0.21.0              # HTTP Mock

# 任务调度（可选）
apscheduler>=3.10.0
```
