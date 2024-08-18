# Project Rules and Standards

## Overview

This document defines the engineering standards, coding conventions, and best practices for the py-invest (Invest-AI) stock analysis platform.

## Code Style

### Python Standards

- **Python Version**: 3.11+
- **Type Hints**: Strict typing required
- **Async/Await**: All I/O operations must be async
- **Formatting**: Black with 100 char line length
- **Linting**: ruff, mypy

### Commands

```bash
# Format code
black .

# Run linter
ruff check .

# Type check
mypy .

# Run tests
pytest

# Run with coverage
pytest --cov=.
```

## Project Structure

```
python/projects/py-invest/
├── apps/                      # Applications
│   ├── api/                   # FastAPI backend
│   └── web/                   # React frontend
├── agents/                    # Multi-agent system
│   ├── base.py               # Base classes
│   ├── orchestrator.py       # Pipeline orchestration
│   ├── specialist_agents.py  # Analyst agents
│   ├── synthesis_agent.py    # Report synthesis
│   └── tools.py              # Agent tools
├── modules/                   # Business modules
│   ├── data_collector/       # Data collection
│   └── report_generator/     # Report generation
├── core/                      # Infrastructure
│   ├── config.py
│   ├── llm.py
│   ├── logger.py
│   └── errors.py
├── storage/                   # Persistence
├── scheduler/                 # Job scheduling
├── notifier/                  # Notifications
├── tests/                     # Test suite
├── cli.py                     # CLI entry
└── pyproject.toml
```

## Naming Conventions

- **Modules**: `snake_case.py`
- **Classes**: `PascalCase`
- **Functions**: `snake_case()`
- **Constants**: `SCREAMING_SNAKE_CASE`
- **Private**: `_leading_underscore`
- **Async functions**: `async def` with `snake_case`

## Type Hints

Use strict typing throughout:

```python
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from datetime import datetime

@dataclass
class PriceData:
    symbol: str
    price: float
    timestamp: datetime
    volume: Optional[int] = None

async def collect_price(symbol: str) -> PriceData:
    ...
```

## Async Patterns

### Async Functions

```python
# Good - Async with proper typing
async def fetch_data(symbol: str) -> Data:
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()

# Bad - Blocking in async
def fetch_data(symbol: str) -> Data:  # Missing async
    return requests.get(url).json()  # Blocking!
```

### Concurrency

```python
# Good - Gather multiple async operations
results = await asyncio.gather(
    collect_price(symbol),
    collect_news(symbol),
    collect_financials(symbol)
)

# Good - Semaphore for rate limiting
semaphore = asyncio.Semaphore(10)

async def limited_fetch(url: str):
    async with semaphore:
        return await fetch(url)
```

## Agent Design

### Agent Base Class

```python
from dataclasses import dataclass
from typing import List, Dict, Any

@dataclass
class AgentInput:
    symbol: str
    name: str
    data: Dict[str, Any]

@dataclass
class AnalysisResult:
    agent_name: str
    summary: str
    key_points: List[str]
    confidence: str  # high/medium/low

class BaseSpecialistAgent:
    def __init__(self, name: str, system_prompt: str):
        self.name = name
        self.system_prompt = system_prompt
        self.llm = LLMClient()

    async def analyze(self, input_data: AgentInput) -> AnalysisResult:
        """Main analysis method."""
        raise NotImplementedError
```

### Specialist Agent Pattern

```python
class TechnicalAnalyst(BaseSpecialistAgent):
    """Technical analysis specialist."""

    def __init__(self):
        super().__init__(
            name="technical_analyst",
            system_prompt="""You are a technical analyst specializing in...

            Focus on:
            - Price trends and patterns
            - Support/resistance levels
            - Technical indicators
            """
        )

    async def analyze(self, input_data: AgentInput) -> AnalysisResult:
        # Get price data
        kline_data = input_data.data.get('kline')

        # Analyze with LLM
        prompt = self._build_prompt(kline_data)
        response = await self.llm.generate(prompt)

        return AnalysisResult(
            agent_name=self.name,
            summary=response.summary,
            key_points=response.key_points,
            confidence=response.confidence
        )
```

## Data Collection

### Collector Pattern

```python
from abc import ABC, abstractmethod
from typing import Generic, TypeVar

T = TypeVar('T')

class BaseCollector(ABC, Generic[T]):
    """Base class for data collectors."""

    @abstractmethod
    async def collect(self, symbol: str) -> T:
        """Collect data for the given symbol."""
        pass

    @abstractmethod
    def validate(self, data: T) -> bool:
        """Validate collected data."""
        pass

class PriceCollector(BaseCollector[PriceData]):
    """Collects real-time price data."""

    def __init__(self):
        self.source = AKShareAPI()

    async def collect(self, symbol: str) -> PriceData:
        raw_data = await self.source.get_price(symbol)
        return self._parse(raw_data)

    def validate(self, data: PriceData) -> bool:
        return data.price > 0 and data.timestamp is not None
```

### Caching

```python
from functools import wraps
import aioredis

def cached(ttl: int = 3600):
    """Cache decorator for collector results."""
    def decorator(func):
        @wraps(func)
        async def wrapper(self, symbol: str, *args, **kwargs):
            cache_key = f"{func.__name__}:{symbol}"

            # Try cache
            cached = await redis.get(cache_key)
            if cached:
                return json.loads(cached)

            # Fetch fresh data
            result = await func(self, symbol, *args, **kwargs)

            # Cache result
            await redis.setex(cache_key, ttl, json.dumps(result))

            return result
        return wrapper
    return decorator
```

## Error Handling

### Custom Exceptions

```python
# core/errors.py

class InvestError(Exception):
    """Base exception for Invest-AI."""
    def __init__(self, message: str, code: str = None):
        super().__init__(message)
        self.code = code
        self.message = message

class DataCollectionError(InvestError):
    """Data collection failed."""
    pass

class LLMError(InvestError):
    """LLM API error."""
    pass

class ValidationError(InvestError):
    """Data validation error."""
    pass
```

### Error Handling Pattern

```python
async def analyze_stock(symbol: str) -> Report:
    try:
        # Collect data
        data = await collect_all_data(symbol)
    except DataCollectionError as e:
        logger.error(f"Data collection failed for {symbol}: {e}")
        raise InvestError(f"无法获取股票 {symbol} 的数据") from e

    try:
        # Run agent analysis
        results = await run_agent_pipeline(data)
    except LLMError as e:
        logger.error(f"LLM analysis failed: {e}")
        # Return partial report or retry
        raise

    return generate_report(results)
```

## Configuration

### Settings Management

```python
# core/config.py

from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # LLM
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    model_name: str = "gpt-4o"

    # Database
    database_url: str = "postgresql://localhost/invest_ai"
    redis_url: str = "redis://localhost:6379/0"

    # App
    log_level: str = "info"
    env: str = "development"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

@lru_cache()
def get_settings() -> Settings:
    return Settings()
```

## Testing

### Test Structure

```python
# tests/test_specialist_agents.py

import pytest
from agents.specialist_agents import TechnicalAnalyst

@pytest.fixture
async def technical_analyst():
    return TechnicalAnalyst()

@pytest.fixture
def sample_kline_data():
    return {
        "open": [100.0, 101.0, 102.0],
        "high": [105.0, 106.0, 107.0],
        "low": [99.0, 100.0, 101.0],
        "close": [104.0, 105.0, 106.0],
        "volume": [10000, 12000, 11000]
    }

@pytest.mark.asyncio
async def test_technical_analyze(technical_analyst, sample_kline_data):
    from agents.base import AgentInput

    input_data = AgentInput(
        symbol="sh600519",
        name="贵州茅台",
        data={"kline": sample_kline_data}
    )

    result = await technical_analyst.analyze(input_data)

    assert result.agent_name == "technical_analyst"
    assert result.confidence in ["high", "medium", "low"]
    assert len(result.key_points) > 0
```

### Mocking External APIs

```python
@pytest.fixture
def mock_llm_client(mocker):
    mock = mocker.patch("core.llm.LLMClient.generate")
    mock.return_value = {
        "summary": "Test summary",
        "key_points": ["Point 1", "Point 2"],
        "confidence": "high"
    }
    return mock
```

## Documentation

### Docstrings

Use Google-style docstrings:

```python
async def analyze_stock(symbol: str, analysis_type: str = "comprehensive") -> Report:
    """Analyze a stock and generate an investment report.

    Args:
        symbol: Stock symbol (e.g., "sh600519", "AAPL")
        analysis_type: Type of analysis to perform
            - "comprehensive": Full analysis (default)
            - "technical": Technical analysis only
            - "fundamental": Fundamental analysis only

    Returns:
        Report object containing analysis results

    Raises:
        DataCollectionError: If data cannot be collected
        LLMError: If analysis fails

    Example:
        >>> report = await analyze_stock("sh600519")
        >>> print(report.rating)
        'Buy'
    """
    ...
```

## Git Workflow

### Commit Messages

Format: `<type>(<scope>): <description>`

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Formatting
- `refactor`: Code restructuring
- `perf`: Performance
- `test`: Tests

Scopes:
- `agents`, `collector`, `report`, `api`, `scheduler`

Examples:
```
feat(agents): add macroeconomic analyst agent
fix(collector): handle missing financial data
docs(readme): add installation guide
perf(llm): batch api requests
```

## Dependencies

### Core Dependencies

```
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
pydantic>=2.5.0
pydantic-settings>=2.1.0
langchain>=0.1.0
langgraph>=0.0.50
sqlalchemy[asyncio]>=2.0.0
asyncpg>=0.29.0
redis>=5.0.0
httpx>=0.25.0
akshare>=1.11.0
yfinance>=0.2.28
```

### Dev Dependencies

```
pytest>=7.4.0
pytest-asyncio>=0.21.0
pytest-cov>=4.1.0
black>=23.0.0
ruff>=0.1.0
mypy>=1.7.0
```

## Performance Guidelines

- Use async/await for all I/O
- Cache data collector results
- Use connection pooling
- Batch LLM requests when possible
- Monitor API rate limits
- Use Redis for distributed caching

## Security

- Never commit API keys
- Use environment variables for secrets
- Validate all inputs
- Sanitize data before storage
- Use HTTPS in production
- Rate limit API endpoints
