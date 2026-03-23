# Change Log - py-invest

All notable changes to this project will be documented in this file.

## [2026-03-23] - Engineering Review Fixes

### Fixed
- **Fake Data Removal** (`modules/data_collector/news_collector.py`)
  - Removed hardcoded fake news that was presented as real data
  - `_fetch_macro_news()` now returns empty list with TODO for API integration

- **Async LLM Calls** (`agents/specialist_agents.py`)
  - Fixed `_parse_output()` to use `ainvoke()` instead of blocking `invoke()`
  - Fixed `SectorOutput.with_llm_fallback()` to be async classmethod
  - Prevents event loop blocking in parallel agent execution

- **Missing Report Section** (`agents/synthesis_agent.py`)
  - Added Scenario Analysis section (order=3) to report sections
  - Bull/Base/Bear cases now appear in the correct order

- **Hardcoded Chinese** (`agents/synthesis_agent.py`)
  - Language instruction in prompt now respects `--en` flag
  - Reports generated in correct language based on CLI option

- **DRY Violation** (`agents/tools.py`)
  - Fixed all 4 tools to use `self._collector` instead of creating new instances

### Removed
- **Dead Code**
  - Removed `apps/web/` (unused TypeScript frontend)
  - Removed `apps/api/` (unused FastAPI routes)
  - Removed `storage/` (empty directory)
  - Updated `pyproject.toml` package list

### Added
- `TODOS.md` - Tracking open items for LLM rate limiting, HTTPS migration, and test suite

## [2026-03-23] - Feature: Chinese Language Output

### Added
- **Chinese Output Support** - CLI now outputs reports in Chinese by default
  - `cli.py`: Added `--en` flag for English output
  - `types.py`: Added `OutputLanguage` enum (ZH/EN)
  - `formatter.py`: Added `TRANSLATIONS` dictionary with all UI labels
  - `synthesis_agent.py`: Added `SECTION_TITLES` translations

### Usage
```bash
# Chinese output (default)
python cli.py analyze sh600519 "综合分析"

# English output
python cli.py analyze sh600519 "综合分析" --en
```

## [2026-03-23] - Hotfix

### Fixed
- **LLM Async Client Proxy Issue** (`core/llm.py`)
  - AsyncOpenAI client now bypasses proxy for better async compatibility
  - Added httpx.AsyncClient with proxy=None when proxy env vars are set
  - Fixes hanging issue on `model.ainvoke()` when http_proxy/https_proxy is configured

## [Unreleased] - 2026-03-23

### Added
- **Multi-Agent Report Pipeline** - Perspective-decomposed investment analysis system
  - `agents/specialist_agents.py`: 4 specialist analyst agents
    - `TechnicalAnalystAgent`: Technical analysis (K-line, momentum, support/resistance)
    - `FundamentalAnalystAgent`: Fundamental analysis (valuation, quality, DCF)
    - `RiskOfficerAgent`: Risk analysis (top 3 risks with probability/impact)
    - `SectorStrategistAgent`: Sector analysis (comps, catalysts)
  - `agents/synthesis_agent.py`: Synthesizes specialist outputs into GS-style report
  - Parallel execution via `asyncio.gather()` - latency reduced from ~20-40s to ~5-10s

- **Report Type Extensions** (`modules/report_generator/types.py`)
  - Added `bull_case: Optional[str]` field to `Report`
  - Added `bear_case: Optional[str]` field to `Report`
  - Added `base_case: Optional[str]` field to `Report`

- **Formatter Updates** (`modules/report_generator/formatter.py`)
  - `_to_markdown()`: Renders Scenario Analysis section with bull/bear/base cases
  - `_to_json()`: Serializes bull/bear/base case fields

- **AgentState Extension** (`agents/base.py`)
  - Added `report: Optional["Report"] = None` field
  - Uses `TYPE_CHECKING` to avoid circular imports

- **CLI Interface** (`cli.py`)
  - `py-invest analyze <code> [query] [-v]` - Analyze stocks
  - `py-invest version` - Version info
  - Supports A-share, HK-share, US-share codes
  - Markdown output to stdout

- **LLM Configuration Enhancement** (`core/llm.py`)
  - `from_env()` now loads `~/.env` first, then project `.env`
  - Supports both `LLM_API_KEY` and `ANTHROPIC_API_KEY`
  - Supports both `LLM_BASE_URL` and `ANTHROPIC_BASE_URL`
  - Default model: `qwen3.5-plus`

### Changed
- **Orchestrator Upgrade** (`agents/orchestrator.py`)
  - `_generate_report()` now returns `Report` object (not `str`)
  - Uses multi-agent pipeline instead of single LLM prompt
  - Exception handling: failed agents use default outputs
  - `analyze()` sets both `state.report` and `state.final_response`

- **pyproject.toml**
  - Added `[project.scripts]` entry point: `py-invest = cli:main`

- **LLM Refactor** (`core/llm.py`)
  - Rewritten to use OpenAI SDK directly (like py-ego)
  - Removed langchain-anthropic dependency
  - Added `LLMClient.chat()` and `chat_sync()` methods
  - Added `AIMessage`, `HumanMessage`, `SystemMessage` for langchain compatibility
  - `ModelProperty.invoke/ainvoke()` wraps OpenAI for langchain-like usage

### Documentation
- `CLI_USAGE.md` - CLI usage guide with examples
- `IMPLEMENTATION_SUMMARY_MULTIAGENT.md` - Multi-agent architecture summary
- `CHANGE_LOGS.md` - This changelog
- `QUICKSTART.md` - Quick start guide

### Technical Details
- **GS-Style Report Sections** (9 total):
  1. Investment Thesis
  2. Price Target & Methodology
  3. Bull / Base / Bear Cases
  4. Technical Picture
  5. Fundamental Analysis
  6. Sector & Comparables
  7. Key Catalysts
  8. Risk Factors
  9. Recommendation

- **Fallback Strategy**:
  - AKShare unavailable → LLM estimates labeled "(estimated)"
  - Agent exception → Default output (no crash)
  - LLM parse failure → Default report structure

---
