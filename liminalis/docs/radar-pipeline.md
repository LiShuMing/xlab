# DB Radar collection pipeline

DB Radar treats a source, a product, and an article as separate identities. The source registry is
`backend/radar/data/feeds.json`; every entry declares `source_id`, `product`, `channel`, `authority`,
and optional `filter_tags`. Blog and release feeds for the same engine therefore share one product
facet while retaining their channel provenance.

The startup pipeline is:

```text
source registry
  -> bounded concurrent conditional fetch
  -> RSS/Atom extraction and tag filtering
  -> recent-window filter
  -> cached full-article extraction
  -> canonical URL / title-and-version event deduplication
  -> relevance ranking with per-product diversity
  -> extractive summary and optional evidence-bound LLM enrichment
  -> PostgreSQL batch upsert -> atomic published artifact
```

Feed responses use a local cache, ETag, Last-Modified, and content hashes. Article pages use a
24-hour cache. Only the highest-ranked items without a matching successful analysis consume the optional LLM budget; an absent or
failed LLM falls back to deterministic extraction. The local artifact retains recent items from a
previous run when one source temporarily fails and records `feedHealth` plus fetch/enrichment
metrics.

Each enriched item carries provenance and ranking fields in addition to the public title and
summary: `channel`, `sourceId`, `authority`, `author`, `version`, `components`, `evidence`,
`confidence`, `score`, `rankReasons`, `contentHash`, `analysisProvider`, `analysisModel`, and
`promptVersion`. PostgreSQL search uses a GIN expression index over title, original title, product,
and summary.

Operational quality should be reviewed with these artifact metrics:

- feed success and failure counts;
- total fetch duration and cache use;
- article candidates and successfully enriched articles;
- percentage of items with tags and evidence;
- item concentration by product and content type;
- summary length and LLM fallback rate.

Apply schema changes before enabling PostgreSQL persistence:

```bash
cd liminalis
.venv/bin/alembic upgrade head
```

## Reproducible quality audit

```bash
cd liminalis
.venv/bin/python -m scripts.radar_quality --refresh --rounds 2
```

This uses the normal Settings precedence (`~/.env`, project `.env`, `.env.local`,
then process environment). It calls real feeds and the configured model, persists
through the real PostgreSQL unit of work, and requests the actual ASGI API and
built frontend. It checks source hashes, exact quotation spans, stored-summary
parity, negative filters and Chinese search. JSON reports and public source
samples go to `~/.liminalis/artifacts/radar/quality/`, never the repository.
A nonzero exit means the reported acceptance checks failed. Browser interaction
and factual review remain separate checks.

LLM cache reuse requires a matching body hash, original title, model, prompt
version and a successful LLM result. An extractive/fallback item remains eligible
for a later run. The per-run `RADAR_TOP_K` counts attempts, including rejected
responses; `llmAttempts`, `llmSucceeded`, `llmFailed`, `llmReused` and
`analysisDurationMs` expose the cost and failure rate. Requests run with at most
four workers, bounded also by `LLM_MAX_CONCURRENCY`.

The evidence prompt requires Chinese summaries and 1–3 source passage IDs.
The server attaches the exact text of each selected passage, avoiding model copying
errors. Schema, length and ID validation reject malformed/unknown references.
This proves quotation provenance, **not** that every generated claim follows from
it. Vendor performance claims still require attribution and test conditions, and
are never independent benchmark reproductions. Known PostgreSQL and GitHub
layouts are scoped before extraction; release pages with dated historical
changelog headings are trimmed after the current release.

For Alibaba Model Studio Qwen3 models, Radar sends `enable_thinking=false` for
this extraction workload, following the [provider's hybrid-thinking API](https://www.alibabacloud.com/help/en/model-studio/deep-thinking).
Other providers receive no vendor-specific parameter. The startup timeout defaults
to 600 seconds; individual model calls still use `DB_RADAR_TIMEOUT`/`LLM_TIMEOUT`.

PostgreSQL updates replace a complete generation of summary, raw source, hash and
evidence together. A failed database write leaves `pending.json` with the source
and analyses for retry, without replacing the published `latest.json`. Matching
pending analyses can be reused after restoring the database. Reads explicitly
return `storage=postgres|snapshot` and `degraded=true` on database fallback; the
page displays a warning. Chinese queries use escaped substring matching in
addition to PostgreSQL full-text search; tags are searchable as well.

GitHub release Atom feeds often provide only `updated`, not `published`. The page
labels those dates as source updates, not initial release dates. Entries with less
than 80 characters of source text do not consume LLM calls; empty release notes
receive an explicit missing-content notice rather than an invented changelog.

## E2E without PostgreSQL

```bash
.venv/bin/python -m scripts.radar_quality --storage local --refresh --rounds 2
.venv/bin/uvicorn scripts.radar_quality:create_local_app --factory --host 127.0.0.1 --port 18763
```

The explicit local mode clears PostgreSQL settings in memory and uses
`~/.liminalis/e2e-local/`. It seeds the analysis cache from an existing pending
checkpoint once, then runs real feeds, extraction and model enrichment as needed.
Neither `~/.env` nor the production artifact/database is changed. The preview
factory disables unrelated startup jobs and uses the same Radar API router and
frontend as the application. Open `http://127.0.0.1:18763/radar` to inspect it.

Local acceptance checks cover source hashes and quotes, published/checkpoint
parity, all served items (including pagination), search, empty filters and frontend
availability. Browser interactions are verified separately. Reports explicitly
skip PostgreSQL migrations, upsert and database search/indexes. A local success
must not be described as a PostgreSQL acceptance result.

A published artifact (even an empty one) is authoritative for file-backed reads.
Bundled example data is used only when no published artifact is available; it is
not merged back into a fresh collection. The API distinguishes `storage=artifact`
from `storage=snapshot`, and the page labels the former as local collection mode.
