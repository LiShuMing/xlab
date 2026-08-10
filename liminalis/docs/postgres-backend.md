# Liminalis PostgreSQL Backend Plan

## Goal

Use the `pgsql_*` / `DATABASE_URL` / `SUPABASE_DB_URL` credentials from `~/.env` as the durable backend database for Liminalis. PostgreSQL, usually Supabase in remote deployments, is the source of truth for queryable business data. Local files are limited to runtime caches, generated artifacts, logs, and static read-only snapshots.

## Environment

The backend reads `~/.env`, `.env`, and `.env.local` in that order. Expected keys:

```bash
pgsql_host=...
# or
PSQL_URL=...
# or a full remote/Supabase DSN
SUPABASE_DB_URL=postgresql://...?...sslmode=require
pgsql_port=5432
pgsql_user=...
pgsql_password=...
# or PSQL_DEFAULT_DB from shared ~/.env credentials
pgsql_database=liminalis_db
pgsql_maintenance_database=postgres
pgsql_sslmode=prefer
allow_business_read_fallback=true
```

The key names are case-insensitive and also accept the `PSQL_*` spelling used by shared RDS/Supabase credentials, including `PSQL_URL`, `PSQL_PORT`, `PSQL_USER`, `PSQL_PASSWORD`, `PSQL_DATABASE`, `PSQL_DB`, and `PSQL_DEFAULT_DB`. `PSQL_URL` may be either a bare host/endpoint or a full PostgreSQL DSN. `DATABASE_URL`, `SUPABASE_DB_URL`, and `SUPABASE_DATABASE_URL` may contain a full DSN with credentials. If a full DSN includes a database path and no explicit database key is set, that path is used.

## Current Implementation

- `backend.settings.Settings` now loads `~/.env` and exposes `postgres_dsn` / `postgres_async_dsn`.
- `backend._shared.storage` defines the shared storage boundary:
  - business database: remote PostgreSQL/Supabase through SQLAlchemy async sessions
  - runtime cache: local cache files such as HTTP/feed caches
  - static snapshot: bundled frontend JSON/JS snapshots for read-only fallback
  - local artifacts: generated files that are not a business source of truth
- `allow_business_read_fallback` explicitly controls whether read routes may fall back after a configured business database errors. Write routes still require the business database.
- Alembic owns the business schema; runtime code accesses it through SQLAlchemy async sessions.
- Liminalis-owned identity tables use a `liminalis_` prefix (`liminalis_users`, `liminalis_user_identities`) so a shared database can coexist with other apps that already have generic tables such as `users`.
- `GET /api/radar/items` uses SQLAlchemy against the business database when configured, then falls back to the bundled static snapshot.
- `GET /api/invest/*` and `POST /api/invest/analyze-stock` use SQLAlchemy Invest tables instead of the legacy SQLite repository.
- `scripts/init_postgres.py` runs Alembic and can import the bundled Radar snapshot.

## Migration Commands

```bash
cd /Users/lism/work/xlab/liminalis

# Install the new PostgreSQL client dependency.
~/.venv/bin/python -m pip install -e .

# Preferred schema path for the unified SQLAlchemy storage layer.
~/.venv/bin/python -m backend.cli db upgrade head

# Or run migrations and import the bundled Radar snapshot in one command.
~/.venv/bin/python scripts/init_postgres.py --migrate-radar
```

## Optimization Direction

PostgreSQL lets Liminalis simplify around one durable store:

- Radar feed: keep `radar_items` normalized enough for filters, but store tags and sources as arrays for simple ingestion.
- Search: current migration keeps query semantics first. For performance, add a maintained `tsvector` search column with a GIN index instead of an expression index.
- Admin jobs: use `radar_ingestion_jobs` for status tracking.
- Invest reports: today's report cache now uses `invest_daily_reports` through SQLAlchemy. CLI, scheduler, notifier, and HTTP routes all share the same service layer.
- Ego state: keep role definitions in code for now, but move chat sessions, records, memories, and profile snapshots into namespaced tables under the same DB.
- OSS/parquet sync: keep only explicit artifact transfer/export jobs from PostgreSQL, for backup or sharing.

For module-level boundaries and shared library conventions, see
`docs/architecture-unification.md`.

## Suggested Next Refactor Steps

1. Add a maintained `tsvector` column/index for Radar search if query volume grows.
2. Split long-running Radar fetch/LLM work so database transactions are opened only for status/item writes.
3. Add storage drift checks to CI for Alembic head, table presence, and service-layer transaction boundaries.
