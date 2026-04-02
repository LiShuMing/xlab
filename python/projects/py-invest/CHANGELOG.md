# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### In Progress
- Web interface improvements
- Additional data sources
- Report template customization

## [0.3.0] - 2024-XX-XX

### Added
- **Scheduler System**
  - Daily job scheduling for stock analysis
  - Background worker with Redis queue
  - Cron-like scheduling configuration
  - Email notifications for completed reports

- **Notifier Module**
  - Email sender with SMTP support
  - HTML email templates for reports
  - Report diff and comparison alerts

- **Report Comparison**
  - Compare reports across time periods
  - Track rating changes
  - Price target adjustments
  - Sentiment analysis trends

- **Additional Tests**
  - Daily job tests
  - Repository tests
  - Comparator tests

## [0.2.0] - 2024-XX-XX

### Added
- **Multi-Agent System**
  - 4 specialist analyst agents:
    - Technical Analyst - Charts, patterns, indicators
    - Fundamental Analyst - Financials, valuation
    - Risk Analyst - Volatility, downside risks
    - Sector Analyst - Industry trends
  - Agent orchestration pipeline
  - Parallel specialist execution
  - Synthesis agent for final report

- **Report Generator**
  - 9-section GS-style report format
  - Bull/Bear/Base case analysis
  - Target price with methodology
  - Investment rating (Buy/Hold/Sell)
  - Markdown and HTML formatters
  - Report builder pattern

- **Data Collectors**
  - Price collector (real-time)
  - K-line/OHLC collector
  - Financial statement collector
  - News and events collector
  - AKShare integration (A股)
  - yfinance integration (港股/美股)

- **CLI Interface**
  - `analyze` command for stock analysis
  - Verbose mode for debugging
  - Report output to stdout or file

### Changed
- Improved LLM client with better error handling
- Enhanced logging system
- Refactored configuration management

## [0.1.0] - 2024-XX-XX

### Added
- **Project Structure**
  - FastAPI backend scaffold
  - React frontend scaffold
  - Modular architecture
  - Docker support

- **Core Infrastructure**
  - Configuration management (Pydantic Settings)
  - LLM client abstraction
  - Logging system
  - Error handling framework

- **Storage Layer**
  - SQLAlchemy models
  - PostgreSQL repository
  - Redis caching

- **Initial Documentation**
  - README.md
  - ARCHITECTURE_DESIGN.md
  - IMPLEMENTATION_SUMMARY.md
  - CLI_USAGE.md
  - QUICKSTART.md

### Project Structure
```
py-invest/
├── apps/
│   ├── api/              # FastAPI backend
│   └── web/              # React frontend
├── agents/               # Multi-agent system
├── modules/
│   ├── data_collector/   # Data collection
│   └── report_generator/ # Report generation
├── core/                 # Infrastructure
├── storage/              # Persistence
├── scheduler/            # Job scheduling
├── notifier/             # Notifications
├── tests/                # Test suite
└── cli.py                # CLI interface
```

### Dependencies
- FastAPI, Uvicorn
- LangChain, LangGraph
- SQLAlchemy, asyncpg
- Redis
- AKShare, yfinance
- pytest, black, ruff

### Features
- Multi-market support (A股, 港股, 美股)
- AI-driven analysis with LLM
- Real-time data integration
- Professional report generation
- 8 investment perspectives

## [0.0.1] - 2024-XX-XX

### Added
- Project initialization
- Basic project structure
- Initial design documents

## Roadmap

### Short Term
- [ ] More data sources (institutional holdings, analyst ratings)
- [ ] Real-time price alerts
- [ ] Portfolio analysis
- [ ] Backtesting framework

### Medium Term
- [ ] WeChat integration for notifications
- [ ] Mobile app
- [ ] Multi-language support
- [ ] Advanced charting

### Long Term
- [ ] Quantitative strategies
- [ ] Social features (sharing, discussions)
- [ ] AI model fine-tuning
- [ ] Alternative data integration
