#!/usr/bin/env bash
set -euo pipefail
LAB_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "$LAB_ROOT/env.sh"
exec "$LAB_ROOT/.venv/bin/python" -u "$LAB_ROOT/lab.py" "$@"
