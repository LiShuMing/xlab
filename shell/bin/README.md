# Bash history to SQLite

Log interactive **Bash** commands to SQLite (cwd, exit code, session). No runtime download: `bash-preexec` lives under `vendor/`.

## Requirements

| Requirement | Notes |
|-------------|--------|
| **Bash** | Interactive Bash. If your login shell is zsh, open a `bash` session or switch the login shell. |
| **sqlite3** | CLI (often on macOS; install via your package manager if missing). |

## Database path

| Method | Notes |
|--------|--------|
| **Default** | `${HOME}/.local/state/bash_history.sqlite` (parent dirs created on first write). |
| **Environment** | `export HISTDB=/path/to/xxx.sqlite` then `source` the script. |
| **source argument** | `source .../bash-history-sqlite.sh /path/to/xxx.sqlite` (**overrides** `HISTDB` if passed; otherwise uses exported `HISTDB`, else default). |

Typical `.bashrc` snippet:

```bash
# Optional custom path
# export HISTDB="${HOME}/.local/state/bash_history.sqlite"

source /path/to/xlab/shell/bin/bash-history-sqlite.sh
# Or pin the DB file:
# source /path/to/xlab/shell/bin/bash-history-sqlite.sh "${HOME}/backup/hist.sqlite"
```

Optional: tag logins

```bash
export LOGINSESSION="$(hostname)-$(date +%s)"
```

## Commands after load

| Command | Purpose |
|---------|---------|
| `dbhistory term` / `dbhist term` | `LIKE` search on `command` |
| `dbexec ID` | Re-run row `command_id` (**unsafe** if you paste untrusted IDs) |

Example SQL:

```bash
sqlite3 "$HISTDB" "SELECT command_id, cwd, return, command FROM command ORDER BY command_id DESC LIMIT 30;"
```

## Behavior

- **Do not execute** this file; `source` it only (otherwise it prints usage and exits the subshell with status 1).
- **Why not `exit` on load errors?** If this file were ever invoked in a way where `return` is invalid, a trailing `exit` would close your **interactive** terminal. Errors after the initial guard use `return` only.
- If `vendor/bash-preexec.sh` is missing, loading fails; restore `vendor/` from the repo.
- Timestamps: `__hist_timestamp` uses sub-second on GNU `date`; on macOS/BSD it is usually second-only (still fine for ordering).
- History can contain secrets; restrict permissions on `*.sqlite` (e.g. `chmod 600`).

## Export / verify (`export-histdb.sh`)

Runnable script (not sourced). Dumps the `command` table to a **text file under the current directory** by default:

```bash
cd /path/where/you/want/the/file
/path/to/export-histdb.sh
/path/to/export-histdb.sh "$HISTDB"
/path/to/export-histdb.sh ~/other.sqlite ./my-export.txt
```

Default database: `$HISTDB` if set, else `~/.local/state/bash_history.sqlite`.  
Default output: `./bash-history-export-YYYYMMDD-HHMMSS.txt` in `$PWD`.

## Other scripts in this directory

- Point `HISTDB` at the same file for recording and exporting.
