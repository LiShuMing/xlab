#!/usr/bin/env bash
set -euo pipefail
DAYLOG_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$DAYLOG_ROOT"
DAYLOG_AUDIT_SRC="$(mktemp -d "${TMPDIR:-/tmp}/daylog-audit-src.XXXXXX")"
trap 'rm -rf "$DAYLOG_AUDIT_SRC"' EXIT
# Compile production code unchanged except the module import, into one isolated
# diagnostic module. This needs neither XCTest nor a production app modification.
for source in DayLog/Core/*.swift DayLog/Services/*.swift DayLog/App/AppStore.swift DayLog/App/Drafts.swift; do
    sed '/^import DayLogCore$/d' "$source" > "$DAYLOG_AUDIT_SRC/$(basename "$source")"
done
cp qa/AuditMain.swift "$DAYLOG_AUDIT_SRC/AuditMain.swift"
mkdir -p build/qa
swiftc -swift-version 6 -O -parse-as-library "$DAYLOG_AUDIT_SRC/"*.swift -o build/qa/DayLogAudit
build/qa/DayLogAudit | tee build/qa/audit-results.txt
