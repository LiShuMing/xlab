#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${1:-8890}"

cd "${PROJECT_DIR}"
mkdir -p logs
source .venv/bin/activate

exec jupyter lab \
    --notebook-dir="${PROJECT_DIR}" \
    --ip=127.0.0.1 \
    --port="${PORT}" \
    --no-browser \
    --ServerApp.token='' \
    --ServerApp.password=''
