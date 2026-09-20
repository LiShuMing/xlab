#!/usr/bin/env bash
set -euo pipefail
DAYLOG_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
"$DAYLOG_ROOT/scripts/build-app.sh"
open "$DAYLOG_ROOT/build/DayLog.app"
