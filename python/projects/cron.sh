#!/usr/bin/env bash
# Daily cron script for pia — runs weekly digest and saves output to ~/work/my-docs/<date>/
# Suggested crontab entry (runs at 08:00 every day):
#   0 8 * * * /home/lism/work/xlab/python/projects/cron.sh >> ~/work/my-docs/cron.log 2>&1

set -euo pipefail

DATE=$(date +%Y-%m-%d)
OUT_DIR="$HOME/work/my-docs/reports/$DATE"
mkdir -p "$OUT_DIR"

PIA_DIR="/home/lism/work/xlab/python/projects/py-pia"
PRODUCTS="starrocks,clickhouse,duckdb,doris,trino"

export PIA_PRODUCTS_DIR="$PIA_DIR/products"
export PIA_DATA_DIR="$PIA_DIR/data"

pia sync starrocks
pia sync clickhouse
pia sync duckdb
pia sync doris
pia sync trino

pia digest weekly \
    --products "$PRODUCTS" \
    --no-show \
    --output-dir "$OUT_DIR"

echo "[$DATE] pia digest written to $OUT_DIR"

# ── my-email daily digest ──────────────────────────────────────────────────────
EMAIL_DIR="/home/lism/work/xlab/python/projects/py-email"

cd "$EMAIL_DIR"
.venv/bin/my-email sync
.venv/bin/my-email summarize --date "$DATE"
.venv/bin/my-email digest --date "$DATE" --output-dir "$OUT_DIR"

echo "[$DATE] my-email digest written to $OUT_DIR/digest-$DATE.json"

# ── Rebuild MkDocs index ────────────────────────────────────────────────────
DOCS_DIR="$HOME/work/my-docs"
REPORTS_DIR="$DOCS_DIR/reports"
INDEX="$DOCS_DIR/index.md"

{
  echo "# Product Intelligence Reports"
  echo ""
  echo "Daily release notes analysis for database and big-data products."
  echo ""
  echo "## Reports"
  echo ""
  echo "| Date | Files |"
  echo "|------|-------|"
  for d in $(ls -r "$REPORTS_DIR" 2>/dev/null | grep -E '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'); do
    files=$(ls "$REPORTS_DIR/$d"/*.md 2>/dev/null | wc -l)
    echo "| [$d](reports/$d/index.md) | $files |"
  done
} > "$INDEX"

# Create per-day index
{
  echo "# $DATE"
  echo ""
  for f in "$OUT_DIR"/*.md; do
    [ -f "$f" ] || continue
    name=$(basename "$f" .md)
    echo "- [$name]($name.md)"
  done
} > "$OUT_DIR/index.md"

echo "[$DATE] MkDocs index updated"
