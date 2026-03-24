# Change Log - py-invest

All notable changes to this project will be documented in this file.

## [2026-03-24] - Feature: Professional Investment Report Framework

### Changed
- **Synthesis Agent** (`agents/synthesis_agent.py`)
  - Upgraded to 8-section professional report framework based on py-lab/stock_module.py
  - New sections: Company Overview, Macro & Sector Context, Technical Analysis, Financial Health, Multi-Lens Investment Case, Risk Matrix, Position Sizing, Overall Recommendation
  - Added multi-perspective analysis: Buffett, Duan Yongping, Trader, Quant viewpoints
  - Risk Matrix with table format (Risk Type, Description, Probability, Impact, Mitigation)
  - Position Sizing with $30,000 portfolio calculations
  - Real-time price data integration ($250.35 for AAPL as of analysis time)
  - Precise target price and stop-loss calculations

- **Tools** (`agents/tools.py`)
  - Updated all tools to return ToolResult objects with metadata containing raw_data
  - Enables structured data extraction for synthesis agent

- **Orchestrator** (`agents/orchestrator.py`)
  - Updated to handle ToolResult objects from tools
  - Properly stores both markdown result and raw_data for downstream processing

### Added
- **Professional Report Content**
  - 52-week price position calculation
  - Moving average distance analysis
  - DCF valuation range
  - Risk/Reward ratio calculation
  - Share count calculation for position sizing
  - Sector comparables with P/E ratios

### Email Design Features
- **Gradient Header**: Purple gradient with stock name/code
- **Rating Card**: Dynamic colors (Buy=green, Hold=yellow, Sell=red)
- **Target Price**: Large, prominent display
- **Scenario Analysis**: Three-column Bull/Base/Bear layout
- **Card Sections**: Rounded corners, subtle shadows
- **Responsive**: Works on mobile and desktop email clients

## [2026-03-24] - Feature: Background Task System & HTML Email Templates

### Added
- **Background Task System** - Decoupled analysis from email sending via database queue
  - `storage/models.py`: Added `AnalysisTask` dataclass for task tracking
  - `storage/repository.py`: Added task CRUD functions (`save_analysis_task`, `get_pending_tasks`, `update_task_status`, etc.)
  - `scheduler/worker.py`: New `AnalysisWorker` class for background processing
  - Extended `pending_emails` table with `html_body` and `task_id` columns

- **HTML Email Templates** (`notifier/email_templates.py`)
  - `format_stock_report_html()`: Professional HTML formatting for single stock reports
  - `format_daily_summary_html()`: Multi-stock summary email template
  - Modern design with gradient header, rating color coding, card-based layout
  - Fully inline CSS for email client compatibility
  - Supports both Chinese and English output

- **CLI Commands**
  - `py-invest task add CODE [CODE...]`: Add stocks to analysis queue
  - `py-invest task list`: List pending tasks
  - `py-invest worker --once`: Process pending tasks once
  - `py-invest sender`: Send pending emails from queue

### Database Schema Changes
- **analysis_tasks table**: Track background analysis tasks
  - `id`, `stock_code`, `stock_name`, `status`, `priority`
  - `created_at`, `started_at`, `completed_at`, `error_message`
- **pending_emails table**: Added `html_body` and `task_id` columns

### Email Design Features
- **Gradient Header**: Purple gradient with stock name/code
- **Rating Card**: Dynamic colors (Buy=green, Hold=yellow, Sell=red)
- **Target Price**: Large, prominent display
- **Scenario Analysis**: Three-column Bull/Base/Bear layout
- **Card Sections**: Rounded corners, subtle shadows
- **Responsive**: Works on mobile and desktop email clients

### Architecture
```
[Producer]                    [Worker]                      [Sender]
    |                             |                             |
    v                             v                             v
analysis_tasks ──> 执行分析 ──> daily_reports ──> pending_emails ──> 发送邮件
(SQLite)                        (SQLite)         (SQLite)         (SMTP)
```

### Usage
```bash
# Add analysis tasks (immediate return)
py-invest task add AAPL TSLA NVDA

# Process tasks in background
py-invest worker --once

# Send pending emails
py-invest sender
```

### Cron Deployment
```cron
# Every weekday at 7:30 AM
30 7 * * 1-5 cd /path/to/py-invest && py-invest worker --once

# Every 5 minutes for email sending
*/5 * * * * cd /path/to/py-invest && py-invest sender
```

## [2026-03-24] - Performance: Parallel Data Collection & Rate Limiter Fix

### Changed
- **Parallel Data Collection** (`agents/orchestrator.py`)
  - Changed sequential tool execution to parallel using `asyncio.gather()`
  - Data collection time reduced from ~20s to ~5s
  - Added detailed timing logs for each specialist agent

- **Rate Limiter Model Property** (`core/llm.py`)
  - Fixed `RateLimitedLLMClient.model` to return `ModelProperty(self)` instead of `self._client.model`
  - Previously, specialist agents bypassed rate limiting by calling `model.ainvoke()`
  - Now all LLM calls go through rate-limited `chat()` method

- **Increased Max Tokens** (`core/llm.py`)
  - Changed `LLMConfig.max_tokens` default from 4000 to 8000
  - Synthesis reports require more tokens for 9-section output
  - Prevents truncation and potential retries

- **Concurrency Limit** (`agents/orchestrator.py`)
  - Increased `max_concurrent` from 2 to 4 for parallel specialist agents
  - Allows all 4 agents (Technical, Fundamental, Risk, Sector) to run truly parallel

### Performance Impact
- Data collection: ~20s → ~5s (75% faster)
- Specialist analysis: runs in parallel (max ~115s for 4 agents)
- Note: Synthesis step remains slow (~360s) due to long prompt and model speed

## [2026-03-24] - Fix: Config Module dotenv Loading

### Fixed
- **Environment Variable Loading** (`config/settings.py`)
  - Added `dotenv` import and `load_dotenv()` call to automatically load `~/.env`
  - Previously, `GMAIL_APP_PASSWORD` was not loaded unless environment was pre-configured
  - Now config module self-contained: importing `config` auto-loads credentials

### Technical Details
- `load_dotenv(Path.home() / ".env", override=True)` ensures env vars are available
- Email password now correctly retrieved via `os.getenv("GMAIL_APP_PASSWORD")`
- Tested with email sender - SMTP authentication now works

## [2026-03-24] - Fix: Daily Analysis Timeout & API Quota Issues

### Fixed
- **Rate Limiting Integration** (`agents/orchestrator.py`)
  - Orchestrator now wraps `LLMClient` with `RateLimitedLLMClient`
  - Set `max_concurrent=2` to limit parallel LLM calls per stock analysis
  - Prevents timeout when 4 specialist agents run in parallel

- **Timeout Configuration** (`scheduler/daily_job.py`)
  - Increased `SINGLE_STOCK_TIMEOUT` from 120s to 300s (5 minutes)
  - Reduced `MAX_CONCURRENT_ANALYSES` from 5 to 3 stocks
  - Provides more time for multi-agent analysis pipeline to complete

- **Batch Processing** (`scheduler/daily_job.py`)
  - Added `STOCKS_PER_BATCH = 3` configuration
  - Added `BATCH_DELAY_SECONDS = 3600` (1 hour) between batches
  - Implemented `_analyze_batch()` helper function
  - Modified `run_daily_analysis()` to process stocks in batches
  - Dry-run mode processes only first batch for quick testing

### Technical Details
- Each stock analysis runs 4 specialist agents in parallel (Technical, Fundamental, Risk, Sector)
- Each LLM call takes ~6-7 seconds, so 4 concurrent calls need ~25-30 seconds
- With synthesis agent added, total time can exceed 120s
- Rate limiting ensures controlled concurrency and prevents API quota exhaustion
- Batch processing spreads 10 stocks across ~4 hours to stay within API quotas

### Batch Schedule
- Batch 1: Stocks 1-3 (TSLA, VOO, AAPL) - immediate
- Batch 2: Stocks 4-6 (NVDA, BRK.B, AMZN) - +1 hour
- Batch 3: Stocks 7-9 (GOOGL, TSM, MU) - +2 hours
- Batch 4: Stock 10 (CRWV) - +3 hours
- Email sent after all batches complete

## [2026-03-24] - User Configuration Setup

### Added
- **User Stock Configuration** (`~/.py-invest/config.yaml`)
  - Configured 10 US stocks: TSLA, VOO, AAPL, NVDA, BRK.B, AMZN, GOOGL, TSM, MU, CRWV
  - Email settings: ming.moriarty@gmail.com (sender and recipient)
  - SMTP: Gmail (smtp.gmail.com:587)
  - Password loaded from `GMAIL_APP_PASSWORD` environment variable in `~/.env`

### Configuration Details
```yaml
stocks:
  - code: TSLA / VOO / AAPL / NVDA / BRK.B
  - code: AMZN / GOOGL / TSM / MU / CRWV

email:
  sender: ming.moriarty@gmail.com
  recipient: ming.moriarty@gmail.com
  smtp_host: smtp.gmail.com
  smtp_port: 587
```

## [2026-03-24] - Feature: Test Suite (Phase 5)

### Added
- **Test Files** (`tests/`):
  - `tests/test_comparator.py`: Unit tests for diff comparator (22 tests)
  - `tests/test_repository.py`: Unit tests for storage repository (15 tests)
  - `tests/test_daily_job.py`: Tests for scheduler module (10 tests)

- **Comparator Tests** (`test_comparator.py`):
  - Tests for `Change` and `IncrementalReport` dataclasses
  - Tests for `compare_reports()` function
  - Price change threshold tests (2% trigger)
  - PE/PB ratio change tests (5% trigger)
  - Rating and target price change detection
  - New news item detection with deduplication
  - Support/resistance break detection
  - Edge cases: missing data, zero prices, None values

- **Repository Tests** (`test_repository.py`):
  - Module structure verification
  - Dataclass `from_row()` factory method tests
  - Function signature validation
  - Database path verification

- **Scheduler Tests** (`test_daily_job.py`):
  - Trading day detection (weekend vs weekday)
  - `DailyJobResult` dataclass tests
  - Non-trading day skip logic
  - Module integration tests

- **Test Coverage**:
  - 47 tests passing
  - Core comparison logic fully covered
  - Edge cases tested for robustness

## [2026-03-24] - Feature: Daily Job Scheduler (Phase 4)

### Added
- **Scheduler Module** (`scheduler/`) - Main orchestration for daily stock analysis
  - `scheduler/daily_job.py`: Main orchestration logic
  - `scheduler/__init__.py`: Module exports

- **Trading Day Detection**:
  - `is_trading_day(date)`: Checks if a date is a trading day
  - Uses `chinese_calendar` package for Chinese holiday detection
  - Falls back to weekday check if package not installed
  - Excludes weekend make-up workdays (Chinese stock market rule)

- **Daily Job Functions**:
  - `run_daily_analysis(dry_run)`: Main entry point for daily analysis
  - `analyze_single_stock(stock_code, stock_name)`: Analyze single stock with timeout
  - `process_pending_emails()`: Send pending emails from retry queue

- **DailyJobResult Dataclass**:
  - success, stocks_analyzed, stocks_failed, changes_detected
  - email_sent, error, failed_stocks

- **CLI Daily Command**:
  - `py-invest daily`: Run daily analysis and send email
  - `py-invest daily --dry-run`: Print email without sending
  - Graceful error handling with informative output

- **Orchestration Flow**:
  1. Check if today is a trading day
  2. Load config and stock list from `~/.py-invest/config.yaml`
  3. Run analysis for each stock in parallel (max 5 concurrent)
  4. Save reports to storage (`~/.py-invest/data.db`)
  5. Compare with yesterday using `diff.comparator`
  6. Format incremental email using `diff.formatter`
  7. Send email using `notifier.email_sender`

- **Error Handling**:
  - Single stock timeout: Skip and continue, note in email
  - All stocks fail: Return error with details
  - Email send fails: Saved to pending_emails for retry

- **Configuration**:
  - `SINGLE_STOCK_TIMEOUT = 120` (seconds)
  - `MAX_CONCURRENT_ANALYSES = 5`

- **Dependency** (`pyproject.toml`):
  - Added `chinesecalendar>=4.0.0` for Chinese holiday detection
  - Added `scheduler` to build packages

### Usage
```bash
# Run daily analysis and send email
python cli.py daily

# Dry run - print email without sending
python cli.py daily --dry-run
```

### Technical Details
- Parallel execution with `asyncio.gather()` and semaphore for concurrency control
- Timeout wrapper using `asyncio.wait_for()` for individual stock analysis
- Uses `json.dumps(ensure_ascii=False)` for Chinese text in reports
- Database initialized on each run via `init_db()`
- Stock configs synced from config.yaml to database

## [2026-03-24] - Feature: Email Sender with Retry Logic (Phase 3)

### Added
- **Notifier Module** (`notifier/`) - Email sending with SMTP and retry logic
  - `notifier/email_sender.py`: EmailSender class with Gmail SMTP support
  - `notifier/__init__.py`: Module exports

- **EmailConfig Dataclass**:
  - `smtp_host`, `smtp_port`, `sender`, `password`, `recipient`
  - `from_env()` class method loads from `GMAIL_APP_PASSWORD` and `EMAIL_RECIPIENT` env vars

- **EmailSender Class**:
  - `send()`: Send email with retry logic, saves to pending_emails on failure
  - `send_with_retry()`: Exponential backoff retry (3 retries, 5-minute intervals)
  - `test_connection()`: Test SMTP connection without sending
  - `send_pending_emails()`: Process failed emails from retry queue
  - Supports both HTML and plain text emails via MIMEMultipart

- **Error Handling**:
  - `SMTPAuthenticationError`: Log and save to pending_emails
  - `SMTPException`: Log and save to pending_emails
  - `socket.timeout`/`ConnectionError`: Retry with backoff
  - All failures logged via `log_email()` to email_logs table

- **Retry Configuration**:
  - `DEFAULT_MAX_RETRIES = 3`
  - `RETRY_DELAY_SECONDS = 300` (5 minutes)
  - `RETRY_BACKOFF_MULTIPLIER = 2` (exponential backoff)

### Technical Details
- Uses Python's built-in `smtplib` with STARTTLS for Gmail
- Async-compatible via `run_in_executor()` for SMTP operations
- Integrates with storage module for retry queue and logging
- Default Gmail SMTP: `smtp.gmail.com:587`

### Usage
```python
from notifier import EmailConfig, EmailSender

# From environment variables
config = EmailConfig.from_env()

# Or manually
config = EmailConfig(
    smtp_host="smtp.gmail.com",
    smtp_port=587,
    sender="your@gmail.com",
    password="your_app_password",
    recipient="recipient@example.com"
)

sender = EmailSender(config)

# Test connection
if sender.test_connection():
    # Send email
    await sender.send_with_retry(
        subject="Daily Stock Analysis",
        body="Plain text body",
        html_body="<html>HTML body</html>"
    )

# Retry pending emails
successful, failed = await sender.send_pending_emails()
```

## [2026-03-24] - Feature: Diff Module for Incremental Reporting (Phase 2)

### Added
- **Diff Module** (`diff/`) - Incremental report comparison and email formatting
  - `diff/comparator.py`: Comparison logic with threshold-based change detection
  - `diff/formatter.py`: Email formatting with English language output
  - `diff/__init__.py`: Module exports

- **Dataclasses for Change Detection**:
  - `Change`: field, old_value, new_value, change_pct, triggers_analysis, details
  - `IncrementalReport`: stock_code, stock_name, is_first_run, changes, report_data

- **Threshold Configuration**:
  - Price change: >2% triggers detailed analysis
  - PE/PB change: >5% triggers detailed analysis
  - Rating/Confidence: Any change triggers detailed analysis
  - News: New items (deduplicated by title + hour) trigger analysis
  - Support/Resistance: Any breakout/breakdown triggers analysis

- **Comparator Functions**:
  - `compare_reports(today, yesterday)`: Main comparison function
  - `_check_price_change()`: Compare prices against threshold
  - `_check_rating_change()`: Detect rating/confidence changes
  - `_check_target_price_change()`: Track target price updates
  - `_check_news_change()`: Find new news items (deduplicated)
  - `_check_pe_pb_change()`: Valuation ratio changes
  - `_check_support_resistance_break()`: Technical breakout detection

- **Formatter Functions**:
  - `format_incremental_email(reports, date_str)`: Format multiple reports as email
  - `format_single_stock(report)`: Format single stock changes
  - `format_change(change)`: Format individual change
  - `format_email_subject(reports, date_str)`: Generate email subject line

### Technical Details
- First run handling: Returns all current state as "changes" when no yesterday data
- News deduplication: Uses title + hour as deduplication key
- Supports both raw_data access and Report section access
- Structured logging with `structlog` for debugging

### Usage
```python
from diff import compare_reports, format_incremental_email, format_email_subject

# Compare today vs yesterday
incremental = compare_reports(today_report, yesterday_report)

# Check for significant changes
if incremental.has_significant_changes:
    email_body = format_incremental_email([incremental], "2024-03-24")
    subject = format_email_subject([incremental], "2024-03-24")
```

## [2026-03-24] - Feature: SQLite Storage Layer (Phase 1)

### Added
- **Storage Module** (`storage/`) - SQLite-based persistence for Daily Stock Analysis system
  - `storage/models.py`: Database models and initialization
  - `storage/repository.py`: CRUD operations for reports, emails, configs
  - `storage/__init__.py`: Module exports

- **Database Tables**:
  - `daily_reports`: Stock analysis reports by code and date (UNIQUE constraint)
  - `stock_configs`: Active stock configurations synced from config.yaml
  - `pending_emails`: Retry queue for failed email sends
  - `email_logs`: Optional debugging logs for email sends

- **Dataclasses for Typed Access**:
  - `DailyReport`: id, stock_code, report_date, analysis_json, created_at
  - `StockConfig`: stock_code, stock_name, is_active, created_at
  - `PendingEmail`: id, recipient, subject, body, retry_count
  - `EmailLog`: id, recipient, subject, stock_count, status, error_message

- **Repository Functions**:
  - `save_report()`: Insert or replace daily report
  - `get_report()`: Get specific report by stock and date
  - `get_latest_report()`: Get most recent report for a stock
  - `save_pending_email()`: Add to retry queue
  - `get_pending_emails()`: Get all pending emails under retry limit
  - `delete_pending_email()`: Remove from queue
  - `increment_retry_count()`: Update retry count
  - `log_email()`: Log email send attempt
  - `sync_stock_configs()`: Sync from config.yaml

### Technical Details
- Database location: `~/.py-invest/data.db`
- Explicit error handling for `sqlite3.OperationalError` on all write operations
- Indexes on `stock_code`, `report_date`, `retry_count`, `sent_at` for query performance
- `init_db()` creates tables and indexes if not exist

### Usage
```python
from storage import init_db, save_report, get_latest_report

init_db()  # Initialize database
save_report('sh600519', date.today(), json.dumps(analysis))
report = get_latest_report('sh600519')
```

## [2026-03-24] - Feature: Configuration Module for Daily Stock Analysis

### Added
- **Configuration Module** (`config/settings.py`) - YAML-based configuration loader
  - `CONFIG_PATH` points to `~/.py-invest/config.yaml`
  - `load_config()` loads YAML with environment variable override for sensitive values
  - Dataclasses for typed access: `StockConfig`, `EmailConfig`, `AnalysisConfig`, `AppConfig`
  - `ConfigError` exception with helpful error messages for missing/invalid config

- **Security Enhancement** - `GMAIL_APP_PASSWORD` environment variable override
  - Email password is loaded from `GMAIL_APP_PASSWORD` env var if set
  - Avoids storing Gmail App Password in plaintext in config.yaml

- **Dependency** (`pyproject.toml`)
  - Added `pyyaml>=6.0.0` for YAML parsing
  - Added `config` to build packages

### Config File Schema
```yaml
stocks:
  - code: sh600519
    name: Guizhou Moutai
email:
  smtp_host: smtp.gmail.com
  smtp_port: 587
  sender: your_email@gmail.com
  recipient: your_email@gmail.com
analysis:
  start_time: "07:30"
  timezone: "Asia/Shanghai"
```

### Usage
```python
from config import load_config, CONFIG_PATH

config = load_config()
for stock in config.stocks:
    print(f"{stock.code}: {stock.name}")
```

## [2026-03-24] - Feature: Rate-Limited LLM Client

### Added
- **RateLimitedLLMClient** (`core/llm.py`) - Wrapper class for concurrency control and retry logic
  - Semaphore-based concurrency limiting (default max 5 concurrent calls)
  - Token usage tracking via `RateLimitStats` dataclass
  - Exponential backoff retry for 429 rate limit errors
  - `wrap(client)` class method for easy instantiation
  - Transparent delegation to underlying `LLMClient` methods

### Technical Details
- `RateLimitStats` dataclass tracks: `total_requests`, `total_tokens`, `rate_limit_retries`, `max_concurrent_reached`
- Retry configuration: `max_retries=3`, `base_delay=1.0s`, `max_delay=60.0s`
- `with_temperature()` and `with_max_tokens()` return new `RateLimitedLLMClient` instances

### Rationale
The Daily Stock Analysis system proposes 40 concurrent LLM calls (10 stocks × 4 specialists).
Without rate limiting, this could exhaust API quota, hit provider limits (429 errors), or
generate unexpected costs. This wrapper provides controlled concurrency for safe parallel execution.

## [2026-03-24] - Refactor: Extract Helper Functions to utils.py

### Changed
- **DRY Compliance** (`agents/specialist_agents.py`)
  - Extracted `_strip_markdown_fences()` to `agents/utils.py` as `strip_markdown_fences()`
  - Extracted `_parse_output()` to `agents/utils.py` as `parse_llm_json()`
  - Extracted `format_relevant_data()` to `agents/utils.py`
  - Updated imports to use centralized utilities

### Added
- **agents/utils.py** - Centralized helper functions for agents module
  - `strip_markdown_fences(text)` - Strip markdown JSON fences from text
  - `parse_llm_json(text, llm_client, retry_prompt)` - Parse LLM JSON with retry
  - `format_relevant_data(data, keys, max_chars)` - Format relevant data from dict

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
