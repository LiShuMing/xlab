# my-email

Gmail newsletter digest tool. Pulls Apache mailing list / newsletter emails, summarizes them with a local LLM (Ollama/qwen), and generates a structured daily digest.

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
cli.py               ← Click commands: sync / summarize / digest / show
```

## Stack

| Layer       | Choice                            | Rationale                                      |
|-------------|-----------------------------------|------------------------------------------------|
| Gmail       | google-api-python-client          | Official SDK; historyId for incremental sync   |
| HTML clean  | html2text + BeautifulSoup         | Robust; handles malformed HTML                 |
| DB          | SQLite (stdlib sqlite3, WAL mode) | Zero-dep, single-file, easy upgrade to Postgres|
| LLM         | openai SDK (configurable base_url)| Works with Ollama, OpenAI, vLLM, LMStudio      |
| Config      | pydantic-settings + .env          | Typed, validated, env-overridable              |
| CLI         | Click                             | Composable, testable                           |

## Database Schema

```sql
sync_state   (id=1, history_id, last_sync)
messages     (id PK, thread_id, subject, sender, received_at, labels, body_text, processed)
summaries    (id, message_id FK, summary_json, model, created_at)
digests      (id, date UNIQUE, digest_json, created_at)
```

## Setup

### 1. Python environment

```bash
cd python/projects/my-email
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. Gmail API credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project → Enable **Gmail API**
3. Create OAuth 2.0 credentials (Desktop app) → Download JSON
4. Save as `credentials/client_secret.json`

### 3. Ollama + qwen

```bash
# Install Ollama: https://ollama.com
ollama pull qwen2.5:7b
ollama serve          # runs on http://localhost:11434
```

### 4. Configuration

```bash
cp .env.example .env
# Edit .env — adjust GMAIL_FILTER_QUERY to match your newsletter senders
```

Key env vars:

```
GMAIL_FILTER_QUERY=from:(*-dev@lists.apache.org) OR label:newsletters
GMAIL_TIMEOUT=60
GMAIL_PROXY=http://127.0.0.1:7890  # Required in regions where Google is blocked
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=qwen2.5:7b
```

> **Note**: If you are in a region that requires a proxy to access Google services (e.g., mainland China),
> you must set `GMAIL_PROXY` to your HTTP proxy address (e.g., `http://127.0.0.1:7890`).

## Usage

```bash
# First run: OAuth browser flow, full message sync
my-email sync

# Subsequent runs: incremental (uses stored historyId)
my-email sync

# Summarize today's unprocessed messages
my-email summarize --date 2026-03-19

# Build digest
my-email digest --date 2026-03-19

# Pretty-print
my-email show --date 2026-03-19

# Export digest JSON
my-email digest --date 2026-03-19 --out digest_2026-03-19.json
```

## Example digest output (show)

```
============================================================
  Daily Digest — 2026-03-19
============================================================
  Emails: 12  |  High relevance: 5
  Top topics: iceberg, spark, deletion-vectors, partitioning, arrow

[HIGH] Apache Iceberg v1.5 Release
  Apache Iceberg  |  2026-03-19
  Topics: iceberg, table-format, deletion-vectors, v1.5
  Iceberg 1.5 ships with deletion vectors for faster deletes and improved planning.
  • Deletion vectors reduce small file overhead significantly
  • Planning is 30% faster on large tables with many snapshots
  • Java and Python APIs updated

[MEDIUM] Spark 3.5.2 patch release
  Apache Spark  |  2026-03-18
  ...
```

## Example EmailSummary JSON

```json
{
  "title": "Apache Iceberg v1.5 Release",
  "sender_org": "Apache Iceberg",
  "topics": ["iceberg", "table-format", "deletion-vectors", "schema-evolution"],
  "summary": "Iceberg 1.5 introduces deletion vectors as the default delete mode, reducing write amplification. Planning performance is improved by 30% for tables with high snapshot counts.",
  "key_points": [
    "Deletion vectors replace positional deletes as the default",
    "Snapshot planning is 30% faster",
    "Flink sink now supports upsert mode"
  ],
  "relevance": "high"
}
```

## Tests

```bash
pytest tests/ -v
```

Not covered by tests (requires real credentials / LLM):
- Gmail OAuth flow
- Actual LLM API calls (mocked in tests)
- End-to-end sync → summarize → digest pipeline

## Switching to OpenAI

```bash
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4o-mini
```

## Upgrading to Postgres

The schema and queries use standard SQL with no SQLite-specific types except `TEXT` for everything. To migrate:
1. Replace `sqlite3.connect(db_path)` in `repository.py` with `psycopg2.connect(dsn)` (or `asyncpg`)
2. Change `strftime(...)` defaults to `NOW()` in schema
3. `PRAGMA` calls become no-ops to remove

## Next steps

1. **Cron / scheduling** — `crontab` or a simple `systemd` timer calling `sync && summarize && digest`
2. **Label-based filtering** — create a Gmail filter to auto-label newsletters; query by label ID for precision
3. **Web UI** — FastAPI + simple Jinja2 template to browse digests by date
4. **Ollama model swap** — `LLM_MODEL=qwen2.5-coder:7b` or `llama3.2:3b` for speed/quality tradeoff
5. **Embedding-based search** — store embeddings of summaries for semantic retrieval
6. **Multi-user** — add `user_id` FK to messages/summaries; one DB row per user
