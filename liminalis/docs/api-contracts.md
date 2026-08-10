# Liminalis API Contracts

This document captures the API shapes served by the unified Python backend.

Status: aligned with `backend/routers/` implementation as of 2026-05.

Machine-readable contract: `docs/openapi.json` (regenerate with
`python -m scripts.dump_openapi`). CI should diff against the committed snapshot
to catch unintended drift.

## Radar Items

Current frontend call:

```text
GET /api/radar/items?page=1&per_page=80&type=all&product=all&q=
```

Current provider:

```text
Liminalis unified backend on port 8010
```

Response shape expected by Liminalis:

```json
{
  "items": [
    {
      "id": "string",
      "title": "string",
      "originalTitle": "string",
      "url": "https://example.com/post",
      "site": "example.com",
      "product": "DuckDB",
      "summary": "string",
      "tags": ["optimizer", "storage"],
      "sources": ["https://example.com/post"],
      "publishedDate": "2026-05-14",
      "contentType": "blog",
      "fetchedAt": "2026-05-14T00:00:00",
      "syncBatch": "2026-05-14"
    }
  ],
  "total_items": 1,
  "products": [
    {
      "name": "DuckDB",
      "count": 1
    }
  ],
  "contentTypes": ["blog", "release", "benchmark", "news", "tutorial", "other"],
  "latestSyncBatch": "2026-05-14"
}
```

Compatibility notes:

- The backend falls back to `src/data/pyRadarFeed.js` when PostgreSQL has no matching rows.
- `type=all` means no content-type filter.
- `product=all` means no product filter.
- `q` performs a search over title, summary, tags, and related text in the current server.
- Date fields may be `null` when source metadata is missing.

## Radar Admin Login

Current frontend call:

```text
POST /api/admin/login
Content-Type: application/json
```

Request:

```json
{
  "username": "admin",
  "password": "secret"
}
```

Expected success response (HTTP 200):

```json
{
  "ok": true,
  "user": "admin"
}
```

A `Set-Cookie: liminalis_radar_admin=...` header is included. The cookie is
`HttpOnly`, `SameSite=Lax`, and gains the `Secure` flag when
`COOKIE_SECURE=true` or `ENVIRONMENT=production` is set.

Expected failure (HTTP 401):

```json
{
  "detail": "invalid credentials"
}
```

Compatibility notes:

- The `user` field is a plain string (username), not a nested object.
- Frontend must call with `credentials: 'include'` so the cookie is stored.

## Radar Admin Me

Current frontend call:

```text
GET /api/admin/me
```

Expected authenticated response (HTTP 200):

```json
{
  "authenticated": true,
  "user": "admin"
}
```

Expected unauthenticated response (HTTP 200):

```json
{
  "authenticated": false,
  "user": null
}
```

The endpoint never returns 401; check the `authenticated` boolean instead.

## Radar Link Ingestion

Current frontend call:

```text
POST /api/admin/radar/links
Content-Type: application/json
```

Request:

```json
{
  "url": "https://example.com/post",
  "product": "DuckDB",
  "source": "manual",
  "tags": ["optimizer", "storage"],
  "note": "optional note"
}
```

Expected response (HTTP 202):

```json
{
  "jobId": "job_20260516_193015_a1b2c3d4",
  "status": "pending",
  "job": {
    "id": "job_20260516_193015_a1b2c3d4",
    "status": "pending",
    "url": "https://example.com/post",
    "error": null
  }
}
```

The top-level `jobId` and `status` are convenience aliases for
`job.id` / `job.status`; the canonical record is the nested `job` object.

Job listing:

```text
GET /api/admin/radar/jobs?limit=30
```

Response: `{ "jobs": [ { ...job }, ... ] }` (newest first, capped at `limit`).

Job polling:

```text
GET /api/admin/radar/jobs/{job_id}
```

Expected response (HTTP 200):

```json
{
  "job": {
    "id": "uuid",
    "status": "pending|running|completed|failed|duplicate",
    "url": "https://example.com/post",
    "error": null
  }
}
```

Returns HTTP 404 with `{"detail": "job not found"}` for unknown job IDs.

## Invest Status

Current frontend call:

```text
GET /api/invest/status
```

Current provider:

```text
Liminalis unified backend on port 8010
```

Response shape:

```json
{
  "auto_analysis": false,
  "queue_size": 0
}
```

## Invest Analyze Stock

Current frontend call:

```text
POST /api/invest/analyze-stock
Content-Type: application/json
```

Current provider:

```text
Liminalis unified backend on port 8010
```

Request:

```json
{
  "stock": "AAPL",
  "query": "价值投资分析",
  "lang": "zh",
  "mode": "fast",
  "use_cache": true
}
```

Success response:

```json
{
  "success": true,
  "stock": "AAPL",
  "name": "Apple Inc.",
  "rating": "string",
  "confidence": "string",
  "target_price": 123.45,
  "duration": 12.34,
  "mode": "fast",
  "cached": false,
  "markdown": "# Report"
}
```

Cached response:

```json
{
  "success": true,
  "cached": true,
  "stock": "AAPL",
  "name": "Apple Inc.",
  "rating": "string",
  "confidence": "string",
  "target_price": 123.45,
  "duration": 0,
  "mode": "fast",
  "markdown": "# Report"
}
```

Failure response (HTTP 500):

```json
{
  "detail": "internal server error",
  "trace_id": "0211d5ad16e2"
}
```

Validation failures return HTTP 400 with `{"detail": "..."}`. Internal
exceptions are caught by the global handler and never leak the original
exception message to clients — use the `trace_id` to locate the full stack
trace in server logs.

Target unified endpoint:

```text
POST /api/invest/analyze-stock
```

Compatibility notes:

- Preserve `mode=fast|deep`.
- Preserve today's cache behavior before changing execution model.
- Long-running analysis may later become job-based, but the first migration should preserve synchronous compatibility.
