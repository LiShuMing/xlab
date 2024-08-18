# pia — Product Intelligence Agent

Track official release notes for database and big-data products, analyze them with an LLM, and build a persistent report library.

## Features

- Fetch release notes from GitHub Releases or generic HTML docs pages
- Normalize raw content to clean Markdown snapshots
- Two-stage LLM analysis: structured extraction → expert report
- Report caching keyed by `(product, version, model, prompt_version, content_hash)` — no duplicate API calls
- Multi-product weekly / monthly digest reports
- All output paths configurable via `--output-dir`

## Tracked Products (built-in)

| ID | Product | Category |
|----|---------|----------|
| `clickhouse` | ClickHouse | OLAP database |
| `starrocks` | StarRocks | OLAP database |
| `doris` | Apache Doris | OLAP database |
| `duckdb` | DuckDB | Embedded analytics |
| `trino` | Trino | Distributed SQL |

Add your own by dropping a YAML file into `products/`.

## Requirements

- Python 3.11+
- An OpenAI-compatible LLM endpoint (OpenAI, local via Ollama, etc.)

## Installation

```bash
git clone <repo>
cd py-pia
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Configuration

Create `~/.env` (loaded automatically, never overrides existing env vars):

```dotenv
# Required for analysis commands
LLM_API_KEY=sk-...
LLM_BASE_URL=https://api.openai.com/v1   # default; change for local models
LLM_MODEL=gpt-4o                          # default model

# Optional — raises GitHub API rate limit from 60 → 5000 req/hr
GITHUB_TOKEN=ghp_...

# Optional — override data directory (default: ./data)
PIA_DATA_DIR=/path/to/data

# Optional — override products directory (default: ./products)
PIA_PRODUCTS_DIR=/path/to/products
```

## Usage

### Product catalog

```bash
pia product list                  # list all tracked products
pia product show clickhouse       # detailed info + sources
pia product add --config my.yaml  # register a new product
pia product validate clickhouse   # check source URLs are reachable
```

### Sync releases

```bash
pia sync clickhouse    # fetch latest releases for one product
pia sync all           # sync every tracked product
```

### List versions

```bash
pia versions clickhouse
```

### Analyze a release

```bash
# Analyze the latest release (uses cache if available)
pia analyze latest clickhouse

# Analyze a specific version
pia analyze version clickhouse 25.1.1

# Force regeneration even if cached
pia analyze latest clickhouse --force

# Save report to a custom directory
pia analyze latest clickhouse --output-dir ~/reports/today
```

Each report contains:

- **TL;DR** — one-paragraph summary
- **What changed** — feature breakdown
- **Why it matters** — significance for users
- **Product direction inference** — strategic read
- **Impact on users** — migration / API implications
- **Competitive view** — positioning vs peers
- **Caveats** — known issues, regressions, missing context
- **Evidence links** — source references

### Digest reports

```bash
# Weekly digest across multiple products
pia digest weekly --products starrocks,clickhouse,duckdb

# Monthly digest, save to a custom directory
pia digest monthly \
    --products starrocks,clickhouse,duckdb,doris,trino \
    --output-dir ~/work/my-docs/2026-03

# Skip printing to terminal
pia digest weekly --products clickhouse --no-show
```

## Data layout

```
data/
  app.db              # SQLite metadata (releases, reports, cache keys)
  raw/<product>/      # fetched HTML / API JSON
  normalized/<product>/  # cleaned Markdown snapshots
  reports/<product>/  # final analysis reports (.md)
  reports/            # digest reports (digest_weekly_*.md, digest_monthly_*.md)
```

## Adding a product

Create `products/<id>.yaml`:

```yaml
id: spark
name: Apache Spark
category: open_source
homepage: https://spark.apache.org/
description: "Unified analytics engine for large-scale data processing"

sources:
  - type: github_releases
    url: https://api.github.com/repos/apache/spark/releases
    priority: 100

analysis:
  audience:
    - data_engineer
    - platform_engineer
  competitor_set:
    - flink
    - trino
  prompt_profile: database_olap

version_rules:
  strategy: semver_loose
```

Supported source types: `github_releases`, `docs_html`.

## Automation (daily cron)

`cron.sh` syncs all products and writes a weekly digest to `~/work/my-docs/<date>/`:

```bash
# Add to crontab (runs at 08:00 every day):
0 8 * * * /home/lism/work/xlab/python/projects/cron.sh >> ~/work/my-docs/cron.log 2>&1
```

## Development

```bash
pip install -e ".[dev]"
pytest
```

## License

MIT
