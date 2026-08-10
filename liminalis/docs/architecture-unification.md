# Liminalis Architecture Unification

## Module Boundaries

`backend/_shared` contains cross-domain primitives only:

- `storage.py`: business unit-of-work and storage layout introspection.
- `errors.py`: shared API error and read fallback semantics.
- `auth.py`: JWT, password verification, signed cookie/state helpers.
- `jobs.py`: queue pool, job ids, and common job status vocabulary.
- `http.py`, `web_*`: shared HTTP, cache, feed, crawler, fetch, and extraction helpers.
- `llm.py`, `json_tools.py`: OpenAI-compatible LLM calls and robust JSON parsing.
- `serializers.py`: small API serialization helpers.
- `service.py`: service-layer call shape and naming helpers.

Domain packages keep domain rules and persistence:

- `backend/radar/service.py`: Radar SQLAlchemy repository/service functions.
- `backend/invest/service.py`: Invest SQLAlchemy repository functions.
- `backend/ego/*`: Ego domain models, roles, chat, records, and auth dependencies.
- `backend/wechat/*`: WeChat identity/OAuth mapping.

HTTP-facing services under `backend/services` adapt domain services to API shapes. Routers should stay thin:

- validate request payloads
- open `business_uow()` or use `get_business_session`
- call service functions
- return response envelopes

## Transaction Rule

Only `backend._shared.storage.business_uow()` commits or rolls back. Domain services and repositories may call `flush()` when they need generated values, but must not control transactions.

## Storage Classes

Liminalis uses three explicit storage classes:

- Business database: PostgreSQL/Supabase via SQLAlchemy async sessions.
- Runtime cache: local HTTP/feed caches and other acceleration data.
- Static snapshot/local artifacts: read-only frontend snapshots and generated files.

`allow_business_read_fallback` controls whether read APIs may fall back to snapshots/config after business database errors. Write APIs require the business database.

## Guardrails

`tests/test_architecture.py` prevents common drift:

- routers cannot import raw DB sessions
- services cannot commit or roll back
- runtime code cannot import legacy DuckDB/SQLite storage
- runtime code cannot use ambiguous storage backend switches
- domain code must use shared HTTP and auth helpers
- environment mutation is centralized
