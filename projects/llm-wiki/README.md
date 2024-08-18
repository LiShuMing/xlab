# Personal Context Maintenance System POC

CLI-first implementation started from `RFC-001-v2-personal-context-maintenance-system.md`.

This first slice supports both a file-backed local repository and a Postgres repository while keeping the service layer backend-agnostic.

## Quick Start

```bash
make demo
```

Or run the CLI directly:

```bash
go run ./cmd/ctx init
go run ./cmd/ctx demo run
go run ./cmd/ctx user create kevin --name "Kevin Li" --city "上海" --bio "数据库工程师，关注 AI infra、咖啡、旅行和城市漫游"
go run ./cmd/ctx user create amy --name "Amy" --city "上海" --bio "喜欢探店、展览、夜市和轻户外"
go run ./cmd/ctx ingest note --user kevin --type preference --text "最近想认识同城、对 AI infra 和数据库系统感兴趣、周末可以一起喝咖啡或 citywalk 的人"
go run ./cmd/ctx ingest photo ./demo/night_market.png --user kevin --album demo --city 上海 --district 黄浦区
go run ./cmd/ctx match run --user kevin
go run ./cmd/ctx embed run --user kevin
go run ./cmd/ctx query self --user kevin --text "AI infra 和周末城市生活" --semantic
go run ./cmd/ctx match run --user kevin --semantic
go run ./cmd/ctx bridge --user kevin --target amy
go run ./cmd/ctx privacy audit --user kevin
go run ./cmd/ctx cost show
```

Local state is stored in `data/context_poc.json`.

Build a standalone binary:

```bash
make build
./bin/ctx demo run
```

Run the lightweight web console:

```bash
make web
```

Then open `http://127.0.0.1:8787`. By default this uses `--provider llm`, loads `~/.env`, and falls back to the mock provider if no LLM key is configured. The console is intentionally simple: seed demo data, add/edit notes, upload photos, process photos, embed contexts, run matching, generate bridge text, inspect privacy counters, and watch model-call cost summaries.

Override the web provider when needed:

```bash
WEB_PROVIDER=mock make web
./bin/ctx-web --provider llm --repo postgres
```

Set a stable local login password:

```bash
./bin/ctx-web --provider llm --password local-dev-password
```

Open `http://127.0.0.1:8787/` and enter that password in the connect panel.

## Repository Backend

The service layer depends on a `repository.Repository` interface, not directly on Postgres. The default backend is file-backed local JSON:

```bash
go run ./cmd/ctx --repo file --data ./data init
```

Postgres is available as an optional backend:

```bash
go run ./cmd/ctx --repo postgres init
make psql-demo
```

The Postgres backend reads either `--database-url` or these variables from `~/.env`:

```text
PSQL_URL
PSQL_PORT
PSQL_USER
PSQL_PASSWORD
PSQL_DEFAULT_DB
```

It uses the same `repository.Repository` interface as the file backend, so Postgres remains optional and swappable.

## LLM Provider

The CLI can use an OpenAI-compatible chat endpoint for bridge generation:

```bash
go run ./cmd/ctx --provider llm bridge --user kevin --target amy
go run ./cmd/ctx --provider llm eval run --suite bridge-llm
make psql-llm-demo
```

It loads `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`, and `LLM_TIMEOUT` from the environment, and also reads `~/.env` when those variables are not already exported. Keys are never printed by the CLI.

## Embeddings

Generate text embeddings for active context items:

```bash
go run ./cmd/ctx embed run --user kevin
go run ./cmd/ctx query self --user kevin --text "AI infra 和周末城市生活" --semantic
go run ./cmd/ctx match run --user kevin --semantic
make embed-demo
```

With `--provider llm`, embeddings use an OpenAI-compatible `/embeddings` endpoint. The provider reads:

```text
LLM_EMBEDDING_API_KEY   # optional, falls back to LLM_API_KEY
LLM_EMBEDDING_BASE_URL  # optional
LLM_EMBEDDING_MODEL     # optional, default text-embedding-v4
```

If `LLM_BASE_URL` points at `coding.dashscope.aliyuncs.com`, embedding calls automatically use DashScope's OpenAI-compatible embedding base URL: `https://dashscope.aliyuncs.com/compatible-mode/v1`. If the configured key is not valid for that embedding endpoint, the CLI falls back to deterministic local hash embeddings and records the fallback in `ctx cost show`.

## Photo Ingestion

Photo import keeps the original asset while extracting safe, deterministic metadata for later model processing:

```bash
go run ./cmd/ctx ingest photo ./photos/night_market.png \
  --user kevin \
  --album demo \
  --city 上海 \
  --district 黄浦区
```

The importer now:

- computes SHA-256 before copying, so duplicate imports are idempotent
- stores file size, content type, extension, width, height, image format, and decode status
- stores city/district as downgraded location hints and never exposes exact GPS
- keeps model-generated photo contexts in `pending_review` and `private` until approved
- lowers confidence when an image format cannot be decoded by the local metadata reader

Live provider tests are opt-in:

```bash
set -a; source ~/.env; set +a
RUN_LLM_TESTS=1 go test ./internal/provider -run TestOpenAICompatibleBridgeIntegration -count=1 -v
RUN_LLM_TESTS=1 go test ./internal/provider -run TestOpenAICompatibleEmbeddingIntegration -count=1 -v
RUN_PSQL_TESTS=1 go test ./internal/repository -run TestPostgresRepositoryIntegration -count=1 -v
```

## Python Eval Layer

Run the Python evaluation suite to validate extraction, privacy, matching, and bridge quality with mock providers:

```bash
make eval-py
```

This runs 4 eval suites (extraction, privacy, matching, bridge) and writes a markdown report to `evals/reports/`. All providers are mock — no real API calls are made. Reports are timestamped so each run produces a new file.

## Implemented RFC Slice

- User creation and listing
- One-command demo seed/run flow
- Note and photo ingestion
- Image metadata extraction, safe city-level location hints, and duplicate photo detection
- Mock photo context extraction
- Pending review lifecycle for photo-derived contexts
- Context approve, reject, edit, and delete
- Privacy gate for self memory, matching, and generation
- Self query with source metadata
- Rule-based matching and bridge generation
- Text embedding generation and semantic self query/matching
- Minimal web console for manual validation
- OpenAI-compatible LLM bridge provider
- Pluggable repository interface with file backend default and working Postgres backend
- Usage audit records for matching and bridge context access
- Model call logs with provider, model, status, fallback, and latency
- Basic eval checks for privacy and deletion invariants

## Next Backend Step

Move from the current JSONB-backed Postgres POC tables toward the fuller RFC schema, then add embeddings and replay/golden providers.
