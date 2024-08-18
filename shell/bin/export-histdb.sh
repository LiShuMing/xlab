#!/usr/bin/env bash
# Dump bash-history-sqlite DB rows to a text file. Default output is under $PWD.
set -euo pipefail

usage() {
	cat <<'EOF'
Usage: export-histdb.sh [DATABASE] [OUTPUT]

  DATABASE  SQLite file (default: $HISTDB or ~/.local/state/bash_history.sqlite)
  OUTPUT    Text file to write (default: ./bash-history-export-YYYYMMDD-HHMMSS.txt)

Examples:
  export-histdb.sh
  export-histdb.sh ~/other/hist.sqlite
  export-histdb.sh "$HISTDB" ./my-export.txt
EOF
	exit "${1:-0}"
}

[[ "${1:-}" == "-h" || "${1:-}" == "--help" ]] && usage 0

DB="${1:-${HISTDB:-${HOME}/.local/state/bash_history.sqlite}}"
if [[ -n "${2:-}" ]]; then
	OUT="$2"
else
	OUT="${PWD}/bash-history-export-$(date +%Y%m%d-%H%M%S).txt"
fi

if [[ ! -f "$DB" ]]; then
	printf 'export-histdb: database not found: %s\n' "$DB" >&2
	exit 1
fi

{
	printf '# exported_at: %s\n' "$(date -Iseconds 2>/dev/null || date)"
	printf '# database: %s\n' "$DB"
	printf '\n'
	sqlite3 -header -column "$DB" "SELECT command_id, shell, cwd, return, started, ended, length(command) AS cmd_len, command FROM command ORDER BY command_id;"
} >"$OUT"

printf 'Wrote %s (%s rows)\n' "$OUT" "$(sqlite3 "$DB" 'SELECT COUNT(*) FROM command;')"
