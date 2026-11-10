#!/usr/bin/env bash
set -euo pipefail
umask 077
lab_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ ! -x "$lab_dir/.local/venv/bin/python" ]]; then
  echo "Run $lab_dir/scripts/bootstrap.sh first." >&2
  exit 1
fi
exec "$lab_dir/.local/venv/bin/python" -m llm_observe.cli "$@"
