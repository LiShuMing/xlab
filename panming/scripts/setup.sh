#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if command -v uv >/dev/null 2>&1; then
    [[ -d .venv ]] || uv venv .venv
    uv sync --extra dev --locked
else
    [[ -d .venv ]] || python3 -m venv .venv
    .venv/bin/python -m pip install -e '.[dev]'
fi
.venv/bin/python scripts/local_database.py
npm --prefix web install
npm --prefix web run build
printf '\n盘铭已准备好。运行 ./scripts/run.sh 启动。\n'
