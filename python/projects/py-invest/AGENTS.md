# AI Agent Guidelines

## Overview

This document provides guidelines for AI Agents working on the py-invest (Invest-AI) stock analysis platform.

## Project Architecture

Invest-AI is an LLM-powered stock investment analysis system that generates professional-grade investment reports using multi-agent orchestration.

```
python/projects/py-invest/
├── apps/                       # Applications
│   ├── api/                    # FastAPI backend
│   └── web/                    # React frontend
├── agents/                     # Multi-agent system
│   ├── base.py                 # Base agent classes
│   ├── orchestrator.py         # Agent orchestration pipeline
│   ├── specialist_agents.py    # 4 specialist analysts
│   ├── synthesis_agent.py      # Report synthesizer
│   └── tools.py                # Agent tools
├── modules/                    # Business modules
│   ├── data_collector/         # Data collection
│   │   ├── base.py
│   │   ├── price_collector.py
│   │   ├── kline_collector.py
│   │   ├── financial_collector.py
│   │   └── news_collector.py
│   └── report_generator/       # Report generation
│       ├── types.py
│       ├── formatter.py
│       └── builder.py
├── core/                       # Core infrastructure
│   ├── config.py
│   ├── llm.py                  # LLM client
│   ├── logger.py
│   └── errors.py
├── storage/                    # Data persistence
│   ├── models.py
│   └── repository.py
├── scheduler/                  # Job scheduling
│   ├── daily_job.py
│   └── worker.py
├── notifier/                   # Notifications
│   ├── email_sender.py
│   └── email_templates.py
├── web/                        # Simple web interface
├── tests/                      # Test suite
├── cli.py                      # CLI interface
└── pyproject.toml
```

## Key Components

### Multi-Agent System (`agents/`)

The system uses a 3-stage pipeline:

1. **Data Collection** (Sequential)
   - Price data
   - K-line/OHLC data
   - Financial statements
   - News and events

2. **Specialist Analysis** (Parallel)
   - Technical Analyst - Charts, patterns, indicators
   - Fundamental Analyst - Financials, valuation, business model
   - Risk Analyst - Volatility, downside, macro risks
   - Sector Analyst - Industry trends, competitive position

3. **Synthesis**
   - Combines specialist outputs
   - Generates 9-section GS-style report
   - Produces final recommendation

### Agent Base Classes (`agents/base.py`)

```python
class AgentState:
    """Maintains agent conversation state."""
    messages: List[Message]
    context: Dict[str, Any]

class ToolResult:
    """Result from tool execution."""
    success: bool
    data: Any
    error: Optional[str]

class BaseAgentTool:
    """Base class for agent tools."""
    async def execute(self, **kwargs) -> ToolResult:
        ...
```

### Data Collectors (`modules/data_collector/`)

Each collector inherits from `BaseCollector`:

```python
class PriceCollector(BaseCollector):
    """Collects real-time price data."""
    async def collect(self, symbol: str) -> PriceData:
        ...

class FinancialCollector(BaseCollector):
    """Collects financial statement data."""
    async def collect(self, symbol: str) -> FinancialData:
        ...
```

Data sources:
- **A股**: AKShare
- **港股/美股**: yfinance
- **News**: Web scraping + APIs

### Report Generation (`modules/report_generator/`)

Report structure:
```python
@dataclass
class Report:
    symbol: str
    name: str
    date: datetime
    rating: str  # Buy/Hold/Sell
    target_price: float
    confidence: str  # high/medium/low

    # Scenario analysis
    bull_case: str
    bear_case: str
    base_case: str

    # 9 sections
    sections: List[ReportSection]
```

## Dependencies

- **FastAPI** - Web framework
- **LangChain + LangGraph** - Agent orchestration
- **PostgreSQL + Redis** - Data storage
- **yfinance, AKShare** - Financial data
- **React + TypeScript** - Frontend

## Configuration

Create `.env` file:

```env
# LLM Configuration
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.openai.com/v1
MODEL_NAME=gpt-4o

# Alternative: Anthropic
ANTHROPIC_API_KEY=sk-ant-xxx

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/invest_ai
REDIS_URL=redis://localhost:6379/0

# Application
LOG_LEVEL=info
ENV=development
```

## Building and Running

```bash
# Install dependencies
pip install -e ".[dev]"

# Run CLI
python cli.py analyze sh600519 "综合分析" -v

# Start backend
cd apps/api
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Start frontend
cd apps/web
npm run dev
```

## Common Tasks

### Adding a New Agent

1. Create agent class in `agents/specialist_agents.py` or new file
2. Inherit from base agent pattern
3. Define system prompt and tools
4. Register in orchestrator

```python
class MacroAgent(BaseSpecialistAgent):
    """Macroeconomic analysis agent."""

    def __init__(self):
        super().__init__(
            name="macro_analyst",
            system_prompt="You are a macroeconomic analyst..."
        )

    async def analyze(self, data: AgentInput) -> AnalysisResult:
        # Implementation
        ...
```

### Adding a New Data Collector

1. Create collector in `modules/data_collector/`
2. Inherit from `BaseCollector`
3. Implement `collect()` method
4. Register in orchestrator

```python
class ESGCollector(BaseCollector):
    """Collects ESG data."""

    async def collect(self, symbol: str) -> ESGData:
        # Fetch ESG ratings
        return ESGData(...)
```

### Adding a Report Formatter

1. Add formatter in `modules/report_generator/formatter.py`
2. Implement format method
3. Register in builder

```python
def format_pdf(report: Report) -> bytes:
    """Generate PDF report."""
    # Implementation
    ...
```

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=.

# Run specific test
pytest tests/test_specialist_agents.py -v
```

## Prohibited Actions

1. **DO NOT** commit API keys
2. **DO NOT** make blocking I/O calls in async code
3. **DO NOT** cache sensitive financial data without TTL
4. **DO NOT** ignore LLM rate limits
5. **DO NOT** modify production database without migration

## Performance Considerations

- Use async/await for all I/O operations
- Cache data collector results in Redis
- Batch LLM requests when possible
- Use connection pooling for database

## Error Handling

```python
from core.errors import InvestError

try:
    data = await collector.collect(symbol)
except InvestError as e:
    logger.error(f"Collection failed: {e}")
    # Fallback or retry logic
```

## Change Log Policy

**IMPORTANT**: Every code change MUST be documented in `CHANGE_LOGS.md`.

Format:
```markdown
## [Date] - YYYY-MM-DD

### Added/Changed/Removed
- **Feature Name** (`path/to/file.py`)
  - Description
  - Technical details
```

## Resources

- [LangChain Docs](https://python.langchain.com/)
- [LangGraph Docs](https://langchain-ai.github.io/langgraph/)
- [AKShare Docs](https://www.akshare.xyz/)
- [yfinance Docs](https://pypi.org/project/yfinance/)

## Communication Style

- Include stock ticker examples (e.g., sh600519 for Kweichow Moutai)
- Reference Chinese market context when relevant
- Explain financial concepts briefly
- Show example CLI commands
