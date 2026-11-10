#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ "$(uname -s)" == "Darwin" ]]; then
  exec caffeinate -is "$script_dir/run.sh" controlled "$@"
fi
exec "$script_dir/run.sh" controlled "$@"
