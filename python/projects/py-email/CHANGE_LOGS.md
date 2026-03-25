# Change Logs

All notable changes to this project will be documented in this file.

## 2026-03-25 - UI Redesign: Zeli-inspired Design System

### Design Changes

#### Color Palette
- **Background**: `#f5f0e8` (温暖米黄色) - 替代原来的冷灰色 `#f5f5f5`
- **Primary Accent**: `#d97706` (琥珀色) - 替代原来的蓝色 `#667eea`
- **Text Primary**: `#1a1a1a` (近黑色) - 更好的对比度
- **Text Secondary**: `#6b7280` (中性灰) - 层次分明的辅助文字
- **Card Background**: `white` - 纯白卡片悬浮在米黄背景上

#### Visual Style
- **Border Radius**: 更大的圆角 (12px-20px) 营造现代感
  - 小元素: 8px-10px (按钮、标签)
  - 卡片: 16px-20px
  - 统计卡片: 16px
- **Shadows**: 更柔和的阴影 `0 1px 3px rgba(0,0,0,0.04)`
- **Typography**: Inter 字体优先，更紧凑的字间距
- **Spacing**: 更宽松的留白 (24px 默认 padding)

#### Interactive Elements
- **Buttons**:
  - 主按钮: 琥珀色背景 + 悬停阴影效果
  - 次按钮: 浅灰背景 + 悬停加深
  - 更大的圆角 (10px-12px)
- **Cards**: 悬停时轻微上浮 + 阴影加深
- **Filters**: 圆角胶囊形状，激活状态琥珀色

#### Updated Templates
- `src/my_email/server/templates/inbox.html.j2` - Inbox 页面
- `src/my_email/server/templates/index.html.j2` - Digest 浏览器
- `src/my_email/server/templates/settings.html.j2` - 设置页面
- `src/my_email/server/templates/projects.html.j2` - 项目列表
- `src/my_email/server/templates/project_detail.html.j2` - 项目详情
- `src/my_email/digest/templates/digest.html.j2` - 日报模板

### Design Philosophy
参考 [Zeli](https://zeli.app/zh) 的设计语言:
- 温暖、亲和的配色
- 充足留白，内容优先
- 圆润的边角处理
- 微妙但流畅的交互动画

---

## 2026-03-24 - Feature: Thread Merging and Unified Summary

### Features

#### Thread Merging (`src/my_email/db/repository.py`)
- **`thread_subject` field** - Normalized subject (without Re:/Fwd: prefixes) stored in database
- **`upsert_message()`** - Automatically computes thread_subject during message insertion
- **`get_unsummarized_threads()`** - Groups messages by thread_subject for batch summarization
- **`save_thread_summary()`** - Saves same summary for all messages in a thread

#### Thread-Aware Summarization (`src/my_email/scheduler/sync_task.py`)
- **Automatic thread detection** - Messages with same normalized subject are grouped
- **Unified summaries** - Single LLM call generates summary for entire thread
- **Thread prompts** - Uses specialized prompts for thread analysis:
  - Discussion evolution
  - Key decisions and consensus
  - Action items across participants

#### UI Updates (`src/my_email/server/templates/inbox.html.j2`)
- **Thread count badge** - Shows "N messages" for threads with multiple messages
- **Thread styling** - New `.tag-thread` CSS class

#### Blocked Senders (`src/my_email/gmail/sync.py`)
- **Auto-filter notifications** - Blocks notification emails from:
  - `notifications@github.com`, `noreply@github.com`
  - `no-reply@accounts.google.com`, `no-reply@google.com`
  - Wildcard patterns: `noreply@*`, `no-reply@*`, `bounce@*`
- **Configurable** - `BLOCKED_SENDERS` set can be extended

### Database Schema (`src/my_email/db/models.py`)
- Added `thread_subject TEXT` column to messages table
- Index on `thread_subject` for efficient grouping

---

## 2026-03-24 - Feature: Automatic Project Identification

### Features

#### Project Discovery (`src/my_email/project/`)
- **Automatic project clustering** using Union-Find algorithm
  - Groups emails by topic co-occurrence patterns
  - Configurable thresholds: `min_emails` (default: 3), `co_occurrence_threshold` (default: 5)
  - Hybrid approach: topic clustering + sender domain grouping
- **Project models** (`models.py`):
  - `Project`: id, name, keywords, sender_domains, email_count, first_seen, last_seen
  - `ProjectAssignment`: message_id, project_id, confidence (0.0-1.0), reasons
- **Email assignment** with weighted scoring:
  - Topic overlap: 60% weight
  - Domain match: 40% weight
  - Confidence threshold: 0.3 minimum

#### Database Schema (`src/my_email/db/models.py`)
- **`message_topics`** - Junction table linking messages to topics
- **`projects`** - Project clusters with metadata
- **`email_projects`** - Email-to-project assignments with confidence scores

#### Pipeline Integration (`src/my_email/db/repository.py`)
- **Automatic topic extraction** - `save_summary()` and `save_thread_summary()` now populate `message_topics`
- **Backfill support** - Migrate existing summaries to topic tracking

#### CLI Commands (`src/my_email/cli.py`)
- **`projects discover`** - Discover projects from email patterns
  - `--min-emails` - Minimum emails per project
  - `--threshold` - Co-occurrence threshold for topic linking
  - `--backfill` - Populate message_topics from existing summaries
- **`projects list`** - List all discovered projects
- **`projects show <id>`** - Show emails for a specific project
- **`projects backfill`** - Backfill message_topics from existing summaries

### Tests
- `tests/test_project.py` - Unit tests for slugify and assign_email
- `tests/test_project_integration.py` - Integration tests for clustering, persistence, and pipeline

### Technical Details
- Union-Find with path compression for O(n²) topic clustering
- Module-level functions with explicit `conn` parameter for transaction control
- INSERT OR IGNORE for idempotent backfill operations
- Foreign key constraints with CASCADE delete

---

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