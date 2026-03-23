# Change Logs

All notable changes to this project will be documented in this file.

## 2026-03-23 - Feature: 中文输出 + 技术邮件过滤

### Features

#### 中文输出 (`src/my_email/llm/summarizer.py`)
- **默认中文输出** - Summary、key_points、action_items 等描述性内容使用中文
- **保留英文术语** - 技术关键词、项目名称等专有名词保留英文
- 示例: `title: "Apache Iceberg 发布 1.5.0 版本"`

#### 技术邮件过滤
- **relevance 字段扩展** - 新增 `"skip"` 值用于标记非技术邮件
- **Digest 过滤** - `build_digest()` 自动过滤 `relevance="skip"` 的邮件
- **统计显示** - HTML digest 显示"已跳过"的非技术邮件数量
- 只有与以下领域相关的邮件才会被保留：
  - 软件工程、数据工程、分布式系统
  - 数据库、云基础设施、DevOps
  - ML/AI、安全、开源项目

#### Server 改进 (`src/my_email/server/app.py`)
- **默认显示 7 天** - 主页面从 30 天改为 7 天
- **UI 中文化** - 所有标签改为中文（高优先级、中等、低、待办事项等）

### UI Changes (`src/my_email/digest/templates/digest.html.j2`)
- 统计栏: "技术邮件"、"高优先级"、"已跳过"
- 优先级标签: 高优先级、中等、低
- 侧边栏: "热门话题"、"今日话题"
- Action Items: "待办事项"

---

## 2026-03-23 - Feature: Web Server Mode

### Features

#### Server Module (`src/my_email/server/`)
- **Web interface** for browsing daily email digests
  - `GET /` - Main page with date list and digest viewer
  - `GET /api/dates` - JSON API listing all available digest dates
  - `GET /api/digest/{date}` - Get HTML digest for a specific date
  - `POST /api/generate/{date}` - Trigger sync+summarize+digest pipeline
  - `GET /api/status/{date}` - Poll generation task status

#### Background Task System
- **Async pipeline** for delayed digest generation
  - Incremental sync → Summarize → Build digest
  - Task status tracking for polling
  - Error handling with structured logging

#### UI Features
- Responsive sidebar with 30-day date list
- Visual indicators: Ready/Missing/Empty states
- "Generate" button for dates without digest
- Loading spinner during background tasks
- iframe-based HTML digest viewer

### CLI Changes (`src/my_email/cli.py`)
- **`server` command** - Start web server
  - `--host` option (default: 127.0.0.1)
  - `--port` option (default: 8080)
  - `--reload` flag for development

### Dependencies (`pyproject.toml`)
- Added: `fastapi>=0.110`, `uvicorn>=0.29`

### Usage
```bash
# Start server
my-email server

# With options
my-email server --host 0.0.0.0 --port 3000

# Development mode with auto-reload
my-email server --reload
```

---

## 2026-03-23 - Bugfix: Missing Database Tables and HTML Template

### Bug Fixes
- **`src/my_email/db/models.py`** - Added missing `topic_daily` and `topic_tracks` tables to schema
  - `topic_daily`: Per-day mention counts with composite primary key (topic, date)
  - `topic_tracks`: Lifetime aggregates with first_seen, last_seen, peak metrics
  - Added indexes for efficient querying

- **`src/my_email/digest/templates/digest.html.j2`** - Created missing HTML template
  - Responsive layout with main content and sidebar
  - Topic trends visualization
  - Action items highlighting
  - Card-based email summary display

### Schema Migration
For existing databases, run `init_db()` to create the new tables:
```python
from my_email.db.repository import init_db
init_db()
```

---

## 2026-03-23 - Email Filtering and Thread Aggregation

### Features

#### Email Filtering (`src/my_email/llm/email_filter.py`)
- **EmailFilter class** - Configurable email filtering before summarization
  - Filters StarRocks-related emails (keyword matching in subject/sender)
  - Filters auto-reply messages (Out of Office, vacation replies, delivery failures)
  - Supports both English and Chinese auto-reply patterns
  - Optional noreply/automated sender filtering
  - Returns filter statistics for visibility

**Design Decision:** By default, noreply senders are kept as they may contain useful notifications (e.g., GitHub notifications, service alerts).

#### Thread Aggregation (`src/my_email/llm/thread_aggregator.py`)
- **ThreadAggregator class** - Groups related emails for unified summarization
  - Two-tier grouping: `thread_id` first, then normalized subject matching
  - `normalize_subject()` removes Re:/Fwd:/[list-name] prefixes
  - Creates structured combined body format for LLM thread analysis
  - Intelligently truncates long bodies (3000 chars for threads, 8000 for singles)

**Design Decision:** Thread summarization helps LLM understand conversation evolution, key decisions, and consensus rather than treating each message in isolation.

#### Thread-Aware Summarization (`src/my_email/llm/summarizer.py`)
- **`summarize_thread()` function** - Specialized summarization for email threads
  - Uses `_THREAD_SYSTEM_PROMPT` and `_THREAD_USER_TEMPLATE`
  - Focuses LLM on discussion evolution, key decisions, action items
  - Synthesizes information across all messages

### CLI Changes (`src/my_email/cli.py`)
- `summarize` command enhanced with:
  - `--no-filter` flag to disable email filtering
  - `--no-aggregate` flag to disable thread aggregation
  - Displays filter statistics and thread counts
  - Integration with EmailFilter and ThreadAggregator

### Database Changes (`src/my_email/db/repository.py`)
- **`save_thread_summary()`** - Saves one summary for multiple message IDs
  - Stores summary against first message ID
  - Marks all messages in thread as processed

### Public API Updates
- `src/my_email/llm/__init__.py` - Exports new modules and functions
- `src/my_email/db/__init__.py` - Exports `save_thread_summary`

---

## 2026-03-23 - Type Safety and Error Handling Refactor

### Core Infrastructure

#### Configuration (`src/my_email/config.py`)
- Migrated to Pydantic v2 `BaseSettings` with `frozen=True` for immutability
- Added comprehensive field descriptions and validators
- Environment variable mapping with `env_prefix` and nested settings

#### Error Handling (`src/my_email/llm/summarizer.py`)
- Custom exception hierarchy:
  - `LLMSummarizationError` - Base exception
  - `LLMOutputValidationError` - JSON parsing/validation failures
  - `LLMConnectionError` - Connection failures after retries
- Retry logic with `tenacity`:
  - 3 attempts with exponential backoff (2-10 seconds)
  - Retries on `RateLimitError` and `APIConnectionError`

#### Gmail Module (`src/my_email/gmail/`)
- `auth.py`: `GmailAuthError` for credential/token issues
- `sync.py`: `GmailSyncError` for sync failures, date filtering with validation

### Database Layer (`src/my_email/db/`)
- `repository.py`: Comprehensive docstrings, type annotations
- `topic_repository.py`: Topic arc tracking with trend detection

### Digest Module (`src/my_email/digest/`)
- `builder.py`: Type annotations, docstrings
- `renderer.py`: HTML rendering with Jinja2 templates
- Templates: `templates/digest.html.j2` for responsive HTML output

### CLI (`src/my_email/cli.py`)
- `topics` command - Display topic arc tracking table
- `digest --html [--open]` - Generate and open HTML digest

### Dependencies (`pyproject.toml`)
- Added: `jinja2>=3.1`, `tenacity>=8.2`
- Template packaging in `package-data`

### Tests
- Updated `test_summarizer.py` to use `LLMOutputValidationError`
- All 13 tests passing

---

## Initial Release

### Core Features
- Gmail sync (full and incremental)
- LLM summarization with OpenAI-compatible APIs
- Daily digest generation
- SQLite persistence with WAL mode
- Structured logging with structlog