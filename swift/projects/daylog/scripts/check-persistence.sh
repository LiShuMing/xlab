#!/usr/bin/env bash
set -euo pipefail
DAYLOG_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$DAYLOG_ROOT"
DAYLOG_PROBE_SRC="$(mktemp -d "${TMPDIR:-/tmp}/daylog-save-check.XXXXXX")"
trap 'rm -rf "$DAYLOG_PROBE_SRC"' EXIT
for source in DayLog/Core/*.swift DayLog/Services/*.swift DayLog/App/AppStore.swift DayLog/App/Drafts.swift; do
    sed '/^import DayLogCore$/d' "$source" > "$DAYLOG_PROBE_SRC/$(basename "$source")"
done
cp qa/PersistenceChecks.swift "$DAYLOG_PROBE_SRC/PersistenceChecks.swift"
mkdir -p build/qa
swiftc -swift-version 6 -O -parse-as-library "$DAYLOG_PROBE_SRC/"*.swift -o build/qa/PersistenceChecks
build/qa/PersistenceChecks
