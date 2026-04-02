# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

my-email is a Gmail newsletter digest tool that pulls Apache mailing list / newsletter emails, summarizes them with a local LLM (Ollama/qwen), and generates structured daily digests. It also supports a web-based inbox interface and project-based email organization.

## Architecture

```
Gmail API
   │  OAuth2, incremental historyId sync
   ▼
gmail/sync.py        ← fetch + dedup into SQLite
   │
parser/cleaner.py    ← HTML → clean plain text (html2text + BS4)
   │
db/repository.py     ← messages / summaries / digests / sync_state
   │
llm/summarizer.py    ← OpenAI-compatible client → EmailSummary JSON
   │
digest/builder.py    ← aggregate summaries → DailyDigest JSON
   │
cli.py / server/     ← CLI commands or web UI
```

Key modules:
- `gmail/` — Gmail API OAuth and sync (historyId-based incremental sync)
- `parser/` — HTML email cleaning (html2text + BeautifulSoup)
- `db/` — SQLite repository with WAL mode, repositories for messages/summaries/digests/topics
- `llm/` — OpenAI-compatible LLM client with structured output (Pydantic models)
- `digest/` — Digest building and Jinja2 HTML rendering
- `project/` — Topic-based project discovery and clustering
- `server/` — FastAPI web server for browsing digests and inbox
- `scheduler/` — Background sync and cleanup tasks

## Common Commands

### Development Setup
```bash
cd /home/lism/work/xlab/python/projects/py-email
source .venv/bin/activate
pip install -e ".[dev]"
```

### Running Tests
```bash
# All tests
pytest tests/ -v

# Single test file
pytest tests/test_cleaner.py -v

# Single test with output
pytest -s tests/test_repository.py::test_init_db
```

### Linting and Formatting
```bash
ruff check src/ tests/
ruff format src/ tests/
mypy --strict src/
```

### Daily CLI Workflow
```bash
# First run: OAuth browser flow, full message sync
my-email sync

# Subsequent runs: incremental (uses stored historyId)
my-email sync

# Summarize today's unprocessed messages (with thread aggregation)
my-email summarize --date 2026-03-19

# Build digest JSON + HTML
my-email digest --date 2026-03-19 --html --open

# Pretty-print digest to terminal
my-email show --date 2026-03-19

# Show ongoing topic arcs
my-email topics
```

### Web Server
```bash
my-email server --host 127.0.0.1 --port 8080 --reload
```

### Project Discovery Workflow
```bash
# Discover projects from topic co-occurrence patterns
my-email projects discover --min-emails 3

# List discovered projects
my-email projects list

# Show emails for a specific project
my-email projects show apache-iceberg --days 30
```

## Configuration

Configuration is managed via `pydantic-settings` with the following priority:
1. Environment variables (highest)
2. Local `.env` file
3. Global `~/.env` file (for LLM settings shared across projects)

Key environment variables:
```bash
# Gmail API (OAuth credentials downloaded from Google Cloud Console)
GMAIL_CREDENTIALS_FILE=~/.credentials/my-email/client_secret.json
GMAIL_TOKEN_FILE=~/.credentials/my-email/token.json
GMAIL_FILTER_QUERY=from:(*-dev@lists.apache.org) OR label:newsletters
GMAIL_PROXY=http://127.0.0.1:7890  # Required in regions where Google is blocked

# LLM (OpenAI-compatible)
LLM_BASE_URL=http://localhost:11434/v1  # Ollama
LLM_API_KEY=ollama
LLM_MODEL=qwen2.5:7b

# Database
DB_PATH=data/my_email.db
```

## Database Schema

```sql
sync_state   (id=1, history_id, last_sync)
messages     (id PK, thread_id, subject, sender, received_at, labels, body_text, processed)
summaries    (id, message_id FK, summary_json, model, created_at)
digests      (id, date UNIQUE, digest_json, created_at)
topic_tracks (topic PK, first_seen_date, total_mentions, ...)
projects     (id PK, name, keywords, email_count, ...)
```

## Project Conventions

- **Strict typing:** Use `str | None` instead of `Optional[str]`, modern Python 3.11+ syntax
- **Data validation:** All LLM I/O uses Pydantic v2 models in `db/models.py`
- **Logging:** Use `structlog` — never use `print()`
- **Error handling:** Custom exception classes, fail fast at boundaries
- **Change tracking:** Document all changes in `CHANGE_LOGS.md`
- **Thread safety:** SQLite with WAL mode, connection-per-request pattern

## Key Design Patterns

### LLM Summarization Flow
1. `EmailFilter` — filters out StarRocks/auto-reply emails
2. `ThreadAggregator` — groups emails by thread_id or subject similarity
3. `summarize_message()` / `summarize_thread()` — OpenAI-compatible structured output
4. `build_digest()` — aggregates summaries with topic clustering

### Web Server (FastAPI + Jinja2)
- Templates in `src/my_email/server/templates/*.html.j2`
- Zeli-inspired design system (warm beige `#f5f0e8`, amber accent `#d97706`)
- HTMX for dynamic interactions without full page reloads

## Superpowers Integration

This project uses the Claude Code superpowers system:
- `/docs/superpowers/specs/` — Implementation plans from brainstorming
- `/docs/superpowers/plans/` — Execution checklists
- Use `/plan` to create implementation plans before complex changes

## Collaboration Style (from ROLE.md)

The user is an experienced infrastructure/database engineer who values:
- First-principles reasoning and architecture clarity
- Minimal, correct, extensible solutions
- Concrete outputs over buzzwords
- Performance awareness and realistic constraints
- Working in milestones for larger tasks

When designing: problem → current state → goals → proposed design → tradeoffs → risks → plan.
When implementing: current behavior → target behavior → files to change → plan → code → validation → risks.

## File Modification Safety

- **DO NOT** modify `.env`, `pyproject.toml`, or credential files without explicit user approval
- **DO NOT** modify files outside the current project directory
- All changes must be documented in `CHANGE_LOGS.md`

## Testing Notes

- Tests use `pytest-mock` to isolate LLM network calls
- Gmail OAuth and actual LLM calls are not covered by unit tests
- Database tests use temporary SQLite files
- Run `pytest tests/ -v` before claiming completion
