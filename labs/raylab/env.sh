#!/usr/bin/env bash
# Usage from the repository root: source labs/raylab/env.sh
RAYLAB_HOME="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
export RAYLAB_HOME
source "$RAYLAB_HOME/.venv/bin/activate"
export TMPDIR="$RAYLAB_HOME/tmp"
export RAY_TMPDIR="$RAYLAB_HOME/tmp"
export PIP_CACHE_DIR="$RAYLAB_HOME/cache/pip"
export RAY_USAGE_STATS_ENABLED=0
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
mkdir -p "$TMPDIR" "$PIP_CACHE_DIR" "$RAYLAB_HOME/results" "$RAYLAB_HOME/logs"
