# RFC: Unify Liminalis Python Backends

## Status

Draft

## Summary

Liminalis currently depends on multiple local development processes:

```text
liminalis Vite client :5173
py-radar Flask server :5000
py-invest HTTP server :8080
py-ego API server     :8000
py-ego H5 frontend    :5174
```

This RFC proposes a Python-first refactor that keeps the existing Python business logic but collapses `py-radar` and `py-invest` from independent web servers into service modules behind one `liminalis-api` FastAPI process.

The target runtime is:

```text
development:
  Vite frontend + liminalis-api

production/local long-running:
  liminalis-api serving frontend build + API

optional later:
  liminalis-api + one background worker
```

This keeps Python's ecosystem advantages for LLM workflows, financial data, PostgreSQL, and local scripting while making deployment, configuration, logs, ports, and maintenance much simpler.

## Current Architecture

The original Vite proxy mapped three API groups to different processes:

```text
Liminalis /api        -> http://localhost:5000
Liminalis /invest-api -> http://localhost:8080/api
Liminalis /ego-api    -> http://localhost:8090/api
```

Observed boundaries:

| Area | Current implementation | Storage | Runtime role |
| --- | --- | --- | --- |
| Frontend | `liminalis` React/Vite | static build | UI shell |
| Radar | `py-radar` Flask app | DuckDB, moving to PostgreSQL | feed query, admin login, link ingestion jobs |
| Invest | `py-invest` custom HTTP server | SQLite | report cache, stock analysis endpoint |
| Ego | `py-ego-miniapp` FastAPI + H5 | SQLite | role and chat APIs |

The main complexity is not Python itself. It is that each product owns a web server, port, process lifecycle, config surface, logging path, and health check.

## Goals

1. Reduce `liminalis` plus `py-radar` plus `py-invest` to one Python API process.
2. Preserve existing `py-radar` and `py-invest` business logic during the first migration.
3. Replace multiple Vite proxies with one `/api` backend.
4. Centralize config, data directories, logs, health checks, and job state.
5. Keep migration incremental, reversible, and testable.
6. Leave room for an optional worker process if investment analysis blocks API responsiveness.

## Non-Goals

1. Do not rewrite `py-invest`'s agent pipeline in another language in this RFC.
2. Do not migrate `py-ego` in the first phase.
3. Do not change the user-facing Liminalis UI unless needed for API path updates.
4. Do not require Docker, Redis, Celery, or external infrastructure for local development.
5. Move runtime state toward PostgreSQL after API consolidation, while keeping DuckDB/SQLite as migration inputs and fallbacks.

## Proposed Architecture

Add a `liminalis/backend` package:

```text
liminalis/
  backend/
    __init__.py
    app.py
    settings.py
    deps.py
    routers/
      health.py
      radar.py
      invest.py
      admin.py
    services/
      radar_service.py
      invest_service.py
    jobs/
      models.py
      store.py
      queue.py
      runner.py
    storage/
      app_db.py
  src/
  scripts/
  docs/
  pyproject.toml
```

The new FastAPI app becomes the single server for Liminalis APIs:

```text
GET  /health

GET  /api/radar/items
POST /api/radar/admin/login
GET  /api/radar/admin/me
POST /api/radar/admin/logout
POST /api/radar/admin/links
GET  /api/radar/admin/jobs/{job_id}

GET  /api/invest/status
POST /api/invest/analyze-stock
GET  /api/invest/reports
GET  /api/invest/report/{stock_code}
```

Vite development proxy becomes:

```js
server: {
  proxy: {
    '/api': 'http://localhost:8010'
  }
}
```

Phase 1 uses `8010` by default because the current py-ego H5 API already uses `8000`. After py-ego is consolidated or moved, the unified backend can be switched to `8000` with `LIMINALIS_API_PORT=8000`.

Production can use the same FastAPI process to serve the frontend build from `liminalis/dist`.

## Service Boundaries

### Radar

`py-radar` should stop being required as a separate Flask process. The unified backend imports and reuses its internal components:

```python
from dbradar.storage import DuckDBStore
from dbradar.ingestion import ingest_link
from dbradar.job_store import IngestionJobStore
```

The first migration should preserve the response shape currently expected by `liminalis/src/App.jsx`:

```json
{
  "items": [],
  "total_items": 0,
  "products": [],
  "contentTypes": [],
  "latestSyncBatch": "2026-05-14"
}
```

### Invest

`py-invest`'s custom `web/server.py` should stop being required as a separate process. The unified backend imports the analysis pipeline:

```python
from agents.orchestrator import SimpleAgentOrchestrator
from modules.report_generator.formatter import ReportFormatter, ReportFormat
from storage import init_db, save_report, get_report
```

In the first version, `/api/invest/analyze-stock` may execute in-process, matching current behavior. If responsiveness becomes poor, move analysis into the shared job queue while preserving the API contract.

### Ego

`py-ego` remains outside this RFC's first migration for chat, auth, records, and memory. The read-only role list is now served by `/api/ego/roles` in the unified backend so Liminalis does not need a second py-ego API process just to render role cards. Full Ego consolidation should be a follow-up RFC.

## Unified Config

Introduce `liminalis/backend/settings.py` using `pydantic-settings`.

Suggested settings:

```python
class Settings(BaseSettings):
    host: str = "127.0.0.1"
    port: int = 8010
    data_dir: Path = Path.home() / ".liminalis"
    app_db_path: Path | None = None
    radar_data_dir: Path | None = None
    radar_db_name: str = "items.duckdb"
    invest_db_path: Path | None = None
    llm_api_key: str | None = None
    llm_base_url: str | None = None
    llm_model: str | None = None
    radar_admin_user: str = "admin"
    radar_admin_password: str = "change-me"
    session_secret: str = "local-dev-liminalis-session-secret"
```

Default local data layout:

```text
~/.liminalis/
  liminalis.sqlite
  radar/
    items.duckdb
  invest/
    data.db
  cache/
  logs/
```

During migration, settings may point to existing data:

```text
python/projects/py-radar/data/items.duckdb
~/.py-invest/data.db
```

This avoids a data migration on day one.

## Unified Job Model

Radar link ingestion and investment analysis are both long-running tasks. The unified backend should manage them through one job model.

Minimal job schema:

```text
jobs
- id
- kind: radar_ingest | invest_analysis
- status: pending | running | completed | failed | duplicate
- input_json
- result_json
- error
- created_at
- updated_at
```

Phase 1 can use an in-process `asyncio.Queue` and SQLite persistence. A separate worker process is optional later:

```text
single-process mode:
  uvicorn liminalis.backend.app:app

worker mode:
  uvicorn liminalis.backend.app:app
  python -m liminalis.backend.jobs.worker
```

## API Compatibility Plan

Use canonical unified endpoints. Temporary aliases can be kept only if a transition window is needed.

Canonical endpoints:

```text
/api/radar/items       preferred
/api/radar/items?...   replaces current /api/radar/items

/api/invest/analyze-stock preferred
/api/ego/roles preferred
```

Frontend migration should be small:

```text
target:
  fetchJson('/api/radar/items?...')
  fetchJson('/api/invest/analyze-stock', ...)
  fetchJson('/api/ego/roles', ...)
```

The existing `/api/radar/items` path can remain unchanged if the new backend owns `/api`.

## Execution Plan

### Phase 0: Baseline and Contracts

Deliverables:

- Capture current API response examples for radar and invest.
- Add a small contract document under `liminalis/docs/api-contracts.md`.
- Confirm current `npm run build` passes.
- Confirm current `scripts/check.sh` describes the existing multi-process state.

Tasks:

- [x] Record `GET /api/radar/items?page=1&per_page=80&type=all&product=all&q=` response shape.
- [x] Record `POST /invest-api/analyze-stock` request and response shape.
- [x] Record `GET /invest-api/status` response shape.
- [x] Decide whether the unified backend initially points to existing DB files or new `~/.liminalis` files.

Exit criteria:

- API contracts are documented.
- No runtime behavior has changed.

### Phase 1: FastAPI Skeleton

Deliverables:

- New `liminalis/backend` package.
- New `liminalis/pyproject.toml`.
- `/health` endpoint.
- Updated scripts that can start the unified API.

Tasks:

- [x] Add `liminalis/backend/app.py`.
- [x] Add `liminalis/backend/settings.py`.
- [x] Add `liminalis/backend/routers/health.py`.
- [x] Add Python dependencies: `fastapi`, `uvicorn[standard]`, `pydantic-settings`.
- [x] Update `scripts/start.sh` to support `START_LIMINALIS_API=1`.
- [x] Update `scripts/check.sh` to check `http://localhost:8010/health`.
- [x] Keep existing py-radar and py-invest start behavior during this phase.

Exit criteria:

- `uvicorn backend.app:app --port 8010` starts.
- `curl http://localhost:8010/health` returns OK.
- Existing frontend still works through old processes.

### Phase 2: Move Radar Read API

Deliverables:

- `GET /api/radar/items` implemented in the unified backend.
- Vite `/api` proxy points to port `8010`.
- py-radar Flask is no longer required for read-only radar browsing.

Tasks:

- [x] Add `backend/services/radar_service.py`.
- [x] Import `DuckDBStore` from `py-radar`.
- [x] Implement item query, product aggregation, content type aggregation, and latest sync batch.
- [x] Match the current Liminalis response casing: `originalTitle`, `publishedDate`, `contentType`, `latestSyncBatch`.
- [x] Update `vite.config.js`: `/api/radar` -> `http://localhost:8010`.
- [x] Run `/radar` API smoke test against unified backend.
- [x] Keep static snapshot fallback unchanged.

Exit criteria:

- `/radar` loads from unified backend.
- Stopping py-radar Flask does not break radar read browsing.

### Phase 3: Move Radar Admin and Ingestion

Deliverables:

- Radar admin endpoints implemented under unified backend.
- Link ingestion jobs run through unified job manager.
- py-radar Flask process is fully retired.

Tasks:

- [x] Add admin session/auth utilities or adapt `dbradar.admin_auth`.
- [x] Implement `POST /api/admin/login`.
- [x] Implement `GET /api/admin/me`.
- [x] Implement `POST /api/admin/logout`.
- [x] Implement `POST /api/admin/radar/links`.
- [x] Implement `GET /api/admin/radar/jobs/{job_id}`.
- [x] Reuse py-radar `IngestionJobStore` for job persistence.
- [x] Run `ingest_link` through in-process background executor.
- [x] Update `scripts/start.sh` to stop starting py-radar by default.
- [x] Update `docs/deployment.md`.

Exit criteria:

- Radar admin UI can submit a URL and poll job status.
- `START_RADAR` is no longer needed by default.

### Phase 4: Move Invest API Shell

Deliverables:

- `GET /api/invest/status` and `POST /api/invest/analyze-stock` implemented in unified backend.
- py-invest HTTP server is no longer required.

Current status:

- Unified API exists for `/api/invest/status` and `/api/invest/analyze-stock`.
- Frontend uses `/api/invest/analyze-stock`.
- `py-invest` installs into the shared venv after moving unavailable technical-analysis packages into an optional extra.

Tasks:

- [x] Add `backend/services/invest_service.py`.
- [x] Import `SimpleAgentOrchestrator` lazily inside the analysis path.
- [x] Import `ReportFormatter` lazily inside the analysis path.
- [x] Preserve cache behavior for today's report in the wrapper.
- [x] Preserve request fields: `stock`, `query`, `lang`, `mode`, `use_cache`.
- [x] Preserve response fields: `success`, `stock`, `name`, `rating`, `confidence`, `target_price`, `duration`, `mode`, `cached`, `markdown`.
- [x] Update frontend from `/invest-api/analyze-stock` to `/api/invest/analyze-stock`.
- [x] Update `vite.config.js` to remove `/invest-api`.
- [x] Update scripts to stop starting py-invest by default.

Exit criteria:

- `/invest` can generate or read cached reports through unified backend.
- Stopping py-invest HTTP server does not break Liminalis invest page.

### Phase 5: Static Frontend Serving

Deliverables:

- Production can run one Python process serving both API and built frontend.

Tasks:

- [x] Add static file serving for `liminalis/dist`.
- [x] Add SPA fallback to `index.html` for `/`, `/logos`, `/reports`, `/blogs`, `/radar`, `/invest`, `/ego`, `/praxis`, `/about`.
- [x] Add script command: `npm run build && python -m backend.app`.
- [x] Add `scripts/serve.sh` or extend `scripts/start.sh` with `MODE=prod`.

Exit criteria:

- One process serves `http://localhost:8010/` and `/api/*`.
- No Vite dev server is needed in production/local long-running mode.

### Phase 6: Optional Worker Split

Deliverables:

- Long-running jobs can run in one worker process when needed.

Tasks:

- [ ] Add `python -m backend.jobs.worker`.
- [ ] Move in-process queue runner behind an interface.
- [ ] Add `WORKER_MODE=in_process|external`.
- [ ] Add check script support for worker process.

Exit criteria:

- Default remains one Python process.
- Heavy invest analysis can be isolated without changing API contracts.

### Phase 7: Ego Follow-Up RFC

Deliverables:

- A separate RFC for py-ego consolidation.

Tasks:

- [x] Move Liminalis role list from `/ego-api/roles` to `/api/ego/roles`.
- [ ] Decide whether Liminalis should embed Ego UI instead of jumping to H5.
- [ ] Decide whether `py-ego-miniapp` API should be mounted into unified backend.
- [ ] Define data migration and auth/session strategy.

Exit criteria:

- Ego migration is planned without blocking radar/invest consolidation.

## Testing Plan

Required checks by phase:

```bash
npm run build
bash scripts/check.sh
curl http://localhost:8010/health
curl 'http://localhost:8010/api/radar/items?page=1&per_page=10&type=all&product=all&q='
```

Invest smoke test:

```bash
curl -X POST http://localhost:8010/api/invest/analyze-stock \
  -H 'Content-Type: application/json' \
  -d '{"stock":"AAPL","query":"价值投资分析","lang":"zh","mode":"fast","use_cache":true}'
```

Regression expectations:

- `/radar` still falls back to static `pyRadarFeed` when API is unavailable.
- `/invest` displays cached reports without re-running analysis.
- Admin auth failures remain explicit and do not silently submit jobs.
- Existing data files can be reused during migration.

## Risks

| Risk | Impact | Mitigation |
| --- | --- | --- |
| `py-radar` imports assume current working directory | Radar service may fail when called from Liminalis | Normalize settings and pass explicit paths |
| DuckDB connection thread safety | Intermittent query failures | Open per-request connections or use a small connection factory |
| Invest analysis blocks API process | UI may hang during long analysis | Run in background job or optional worker |
| Python package path conflicts | Imports may resolve incorrectly | Convert projects to editable packages and avoid `sys.path` hacks |
| Data directory migration mistakes | Missing reports/feed items | Point to existing DBs first, migrate later |
| Session/auth behavior changes | Admin UI regression | Preserve API shape and add focused auth smoke tests |

## Open Questions

1. Should unified local data live under `~/.liminalis` or `liminalis/.data` by default?
2. Should `py-radar` and `py-invest` become editable dependencies of `liminalis`, or should selected modules be moved into a shared `python/libs` package?
3. Should invest analysis initially stay synchronous for simpler compatibility, or become job-based immediately?
4. Should the unified backend serve the frontend in development, or only in production?
5. Should Ego chat move into Liminalis, or should Liminalis keep jumping to py-ego H5?

## Recommended First PR

The first PR should be intentionally small:

```text
Add liminalis FastAPI skeleton and health check
```

Files:

```text
liminalis/pyproject.toml
liminalis/backend/__init__.py
liminalis/backend/app.py
liminalis/backend/settings.py
liminalis/backend/routers/__init__.py
liminalis/backend/routers/health.py
liminalis/scripts/start.sh
liminalis/scripts/check.sh
liminalis/docs/deployment.md
```

Acceptance:

```bash
cd /Users/lism/work/xlab/liminalis
npm run build
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8010
curl http://localhost:8010/health
```

No frontend API migration should happen in the first PR.
