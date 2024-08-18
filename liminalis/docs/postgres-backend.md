# Liminalis PostgreSQL Backend Plan

## Goal

Use the `pgsql_*` credentials from `~/.env` and `liminalis_db` as the durable backend database for Liminalis. PostgreSQL should become the source of truth for queryable product data, while DuckDB files, SQLite files, local JSON snapshots, and OSS/parquet sync files become migration or backup artifacts rather than runtime dependencies.

## Environment

The backend reads `~/.env`, `.env`, and `.env.local` in that order. Expected keys:

```bash
pgsql_host=...
# or
PSQL_URL=...
pgsql_port=5432
pgsql_user=...
pgsql_password=...
pgsql_database=liminalis_db
pgsql_maintenance_database=postgres
pgsql_sslmode=prefer
```

The key names are case-insensitive and also accept the `PSQL_*` spelling used by local RDS credentials, including `PSQL_URL`, `PSQL_PORT`, `PSQL_USER`, `PSQL_PASSWORD`, `PSQL_DATABASE`, and `PSQL_DB`. `PSQL_DEFAULT_DB` is intentionally ignored because it may be shared by other local projects. If no database key is present, the database defaults to `liminalis_db`.

## Current Implementation

- `backend.settings.Settings` now loads `~/.env` and exposes `postgres_dsn`.
- `backend.db.postgres` owns the initial schema for:
  - `radar_items`
  - `radar_ingestion_jobs`
- `GET /api/radar/items` tries PostgreSQL first when `pgsql_*` credentials are present, then falls back to DuckDB and finally the bundled static snapshot.
- `scripts/init_postgres.py` initializes schema and can migrate radar rows from the existing DuckDB file or bundled snapshot.

## Migration Commands

```bash
cd /Users/lism/work/xlab/liminalis

# Install the new PostgreSQL client dependency.
~/.venv/bin/python -m pip install -e .

# Create liminalis_db if needed, then create tables and indexes.
~/.venv/bin/python scripts/init_postgres.py --create-db

# Import existing radar data from py-radar DuckDB.
~/.venv/bin/python scripts/init_postgres.py --migrate-radar --source duckdb

# Fallback import if DuckDB is unavailable.
~/.venv/bin/python scripts/init_postgres.py --migrate-radar --source snapshot
```

## Optimization Direction

PostgreSQL lets Liminalis simplify around one durable store:

- Radar feed: keep `radar_items` normalized enough for filters, but store tags and sources as arrays for simple ingestion.
- Search: current migration keeps query semantics first. For performance, add a maintained `tsvector` search column with a GIN index instead of an expression index.
- Admin jobs: use `radar_ingestion_jobs` for status tracking instead of DuckDB job tables.
- Invest reports: move today's report cache from `~/.py-invest/data.db` into `invest_reports`, keyed by `(stock_code, report_date, mode)`.
- Ego state: keep role definitions in code for now, but move chat sessions, records, memories, and profile snapshots into namespaced tables under the same DB.
- OSS/parquet sync: replace runtime dependency with explicit export/import jobs from PostgreSQL, only for backup or sharing.

## Suggested Next Refactor Steps

1. Make radar ingestion write new items directly to `radar_items`.
2. Move admin job store reads/writes to `radar_ingestion_jobs`.
3. Add `invest_reports` and migrate `py-invest` cache reads/writes.
4. Add database health metadata to `/health` without exposing credentials.
5. Remove DuckDB imports from the normal request path once migration is verified.
