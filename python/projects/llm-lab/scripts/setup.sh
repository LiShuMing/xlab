#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export UV_PYTHON_INSTALL_DIR="$PWD/.python"
export UV_CACHE_DIR="$PWD/.uv-cache"
if [[ ! -x .tools/bootstrap/bin/uv ]]; then
    python3 -m pip install --target .tools/bootstrap 'uv==0.12.17'
fi
.tools/bootstrap/bin/uv sync --python 3.12 --locked
.venv/bin/llm-lab doctor
