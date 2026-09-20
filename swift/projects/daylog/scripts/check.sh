#!/usr/bin/env bash
set -euo pipefail
DAYLOG_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$DAYLOG_ROOT"
swift build
DAYLOG_BIN="$(swift build --show-bin-path)"
"$DAYLOG_BIN/DayLogChecks"
DAYLOG_TEST_DIR="$(mktemp -d "${TMPDIR:-/tmp}/daylog-check.XXXXXX")"
trap 'rm -rf "$DAYLOG_TEST_DIR"' EXIT
"$DAYLOG_BIN/DayLog" --storage-write "$DAYLOG_TEST_DIR"
"$DAYLOG_BIN/DayLog" --storage-read "$DAYLOG_TEST_DIR"
mkdir -p "$DAYLOG_TEST_DIR/large"
"$DAYLOG_BIN/DayLog" --storage-write-large "$DAYLOG_TEST_DIR/large"
"$DAYLOG_BIN/DayLog" --storage-read-large "$DAYLOG_TEST_DIR/large"
./scripts/check-persistence.sh
./scripts/check-workflows.sh
./scripts/check-drafts.sh
if [[ "${1:-}" == "--llm" ]]; then
    "$DAYLOG_BIN/DayLogChecks" --llm-check
fi
