#!/usr/bin/env bash
set -euo pipefail
DAYLOG_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$DAYLOG_ROOT"
DAYLOG_PROBE_SRC="$(mktemp -d "${TMPDIR:-/tmp}/daylog-draft-check.XXXXXX")"
trap 'rm -rf "$DAYLOG_PROBE_SRC"' EXIT
for source in DayLog/Core/*.swift DayLog/Services/*.swift DayLog/App/AppStore.swift DayLog/App/Drafts.swift; do
    sed '/^import DayLogCore$/d' "$source" > "$DAYLOG_PROBE_SRC/$(basename "$source")"
done
cp qa/DraftChecks.swift "$DAYLOG_PROBE_SRC/DraftChecks.swift"
mkdir -p build/qa
swiftc -swift-version 6 -O -parse-as-library "$DAYLOG_PROBE_SRC/"*.swift -o build/qa/DraftChecks
build/qa/DraftChecks
