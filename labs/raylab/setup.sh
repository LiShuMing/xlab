#!/usr/bin/env bash
# Recreate only this laboratory's virtual environment, using the existing Ray build.
set -euo pipefail
LAB_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BASE_PYTHON="${RAYLAB_BASE_PYTHON:-$(command -v python3)}"
if ! "$BASE_PYTHON" -c 'import ray; import numpy' >/dev/null 2>&1; then
  echo "Set RAYLAB_BASE_PYTHON to a Python interpreter with Ray and NumPy installed." >&2
  exit 1
fi
mkdir -p "$LAB_ROOT"/{tmp,cache/pip,results,logs}
if [[ ! -x "$LAB_ROOT/.venv/bin/python" ]]; then
  "$BASE_PYTHON" -m venv --system-site-packages "$LAB_ROOT/.venv"
fi
export TMPDIR="$LAB_ROOT/tmp"
export PIP_CACHE_DIR="$LAB_ROOT/cache/pip"
"$LAB_ROOT/.venv/bin/python" -m pip install --only-binary=:all: \
  --index-url "${RAYLAB_PIP_INDEX_URL:-https://mirrors.huaweicloud.com/repository/pypi/simple}" \
  -r "$LAB_ROOT/requirements.txt"
"$LAB_ROOT/run.sh" doctor
