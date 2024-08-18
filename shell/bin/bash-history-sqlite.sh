#!/usr/bin/env bash
# Record interactive Bash commands to SQLite (uses vendored bash-preexec).
# Usage: source /path/to/bash-history-sqlite.sh [path/to/history.db]

if [[ "${BASH_SOURCE[0]:-$0}" == "$0" ]]; then
	echo "Source this file: source ${BASH_SOURCE[0]:-$0} [path/to/history.db]" >&2
	exit 1
fi

if ! _SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)" || [[ -z "${_SCRIPT_DIR}" ]]; then
	echo "bash-history-sqlite: cannot resolve script directory for ${BASH_SOURCE[0]:-unknown}" >&2
	return 1 2>/dev/null || true
fi
_PREEXEC_SH="${_SCRIPT_DIR}/vendor/bash-preexec.sh"
if [[ ! -r "$_PREEXEC_SH" ]]; then
	echo "bash-history-sqlite: missing ${_PREEXEC_SH} (keep the vendor/ directory)" >&2
	# Never use exit here: if this file was run without a proper source, exit would
	# close the interactive terminal. return-only is safe when sourced.
	return 1 2>/dev/null || true
fi
# shellcheck source=vendor/bash-preexec.sh
source "$_PREEXEC_SH"

# HISTDB: first arg to source wins, else exported HISTDB, else default below.
: "${HISTDB:=${HOME}/.local/state/bash_history.sqlite}"
if [[ -n "${1:-}" ]]; then
	HISTDB="$1"
fi

# Second source is a no-op (hooks already registered by bash-preexec).
[[ -n "${_SQLITE_HIST:-}" ]] && return 0
readonly _SQLITE_HIST=1

HISTSESSION="$(dd if=/dev/urandom bs=32 count=1 2>/dev/null | base64)"
mkdir -p "$(dirname "$HISTDB")"

# GNU date: %3N ms; macOS/BSD date has no %N, fall back to seconds only.
__hist_timestamp() {
	local ts
	ts="$(date +%s%3N 2>/dev/null)" || true
	if [[ -z "$ts" || "$ts" == *%3N* ]]; then
		date +%s
	else
		printf '%s\n' "$ts"
	fi
}

dbhistory() {
	[[ -z "${HISTDB:-}" || ! -f "$HISTDB" ]] && return 1
	sqlite3 -separator '#' "${HISTDB}" "select command_id, command from command where command like '%${*}%';" | awk -F'#' '/^[0-9]+#/ {printf "%8s    %s\n", $1, substr($0,index($0,FS)+1); next} { print $0; }'
}

dbhist() {
	dbhistory "$@"
}

dbexec() {
	[[ -z "${HISTDB:-}" || ! -f "$HISTDB" ]] && return 1
	bash -c "$(sqlite3 "${HISTDB}" "select command from command where command_id='${1}';")"
}

__quote_str() {
	local str quoted
	str="$1"
	quoted="'$(printf '%s' "$str" | sed -e "s/'/''/g")'"
	printf '%s\n' "$quoted"
}

__create_histdb() {
	mkdir -p "$(dirname "$HISTDB")"
	if bash -c "set -o noclobber; > \"$HISTDB\" ;" &>/dev/null; then
		sqlite3 "$HISTDB" <<-EOD
		CREATE TABLE command (
			command_id INTEGER PRIMARY KEY,
			shell TEXT,
			command TEXT,
			cwd TEXT,
			return INTEGER,
			started INTEGER,
			ended INTEGER,
			shellsession TEXT,
			loginsession TEXT
		);
		EOD
	fi
}

preexec_bash_history_sqlite() {
	[[ -z "${HISTDB:-}" ]] && return 0
	local cmd
	cmd="$1"
	__create_histdb
	local quotedloginsession
	if [[ -n "${LOGINSESSION:-}" ]]; then
		quotedloginsession="$(__quote_str "$LOGINSESSION")"
	else
		quotedloginsession="NULL"
	fi
	LASTHISTID="$(sqlite3 "$HISTDB" <<-EOD
		INSERT INTO command (shell, command, cwd, started, shellsession, loginsession)
		VALUES (
			'bash',
			$(__quote_str "$cmd"),
			$(__quote_str "$PWD"),
			'$(__hist_timestamp)',
			$(__quote_str "$HISTSESSION"),
			$quotedloginsession
		);
		SELECT last_insert_rowid();
		EOD
	)"
}

precmd_bash_history_sqlite() {
	local ret_value=$?
	# LASTHISTID must be numeric; empty or failed INSERT would break UPDATE and is noisy under set -e.
	if [[ -n "${LASTHISTID:-}" && "$LASTHISTID" =~ ^[0-9]+$ ]]; then
		__create_histdb
		sqlite3 "$HISTDB" <<-EOD
			UPDATE command SET
				ended='$(__hist_timestamp)',
				return=$ret_value
			WHERE
				command_id=$LASTHISTID;
		EOD
	fi
}

preexec_functions+=(preexec_bash_history_sqlite)
precmd_functions+=(precmd_bash_history_sqlite)
