#!/usr/bin/env bash
set -euo pipefail
umask 077
lab_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
python_bin="${PYTHON:-python3}"
export UV_CACHE_DIR="$lab_dir/.local/uv-cache"
export PIP_CACHE_DIR="$lab_dir/.local/pip-cache"
if command -v uv >/dev/null 2>&1; then
  uv venv --allow-existing --python "$python_bin" "$lab_dir/.local/venv"
  uv pip install --python "$lab_dir/.local/venv/bin/python" -r "$lab_dir/requirements.lock"
  uv pip install --python "$lab_dir/.local/venv/bin/python" --no-deps -e "$lab_dir"
else
  "$python_bin" -m venv "$lab_dir/.local/venv"
  "$lab_dir/.local/venv/bin/python" -m pip install -r "$lab_dir/requirements.lock"
  "$lab_dir/.local/venv/bin/python" -m pip install --no-deps -e "$lab_dir"
fi
echo "Environment ready. Run scripts/download.sh next."
