#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
.venv/bin/python -m ruff check src tests scripts
.venv/bin/python -m pytest -q
npm --prefix web run test:unit
npm --prefix web run build
