#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
[[ -x .venv/bin/python && -f web/dist/index.html ]] || ./scripts/setup.sh
.venv/bin/python scripts/local_database.py
exec .venv/bin/python -m panming.server --workspace-root "$(pwd -P)"
