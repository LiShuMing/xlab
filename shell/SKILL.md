# Shell Lab (shell)

## Overview
Shell scripting laboratory for automation, DevOps tasks, system administration, and command-line tool development. Covers bash/zsh scripting and various utilities.

## Build System
- **Shell**: Primary shell scripts (`.sh`)
- **Executables**: Binaries and scripts in `bin/`
- **Docker**: Container-related scripts in `docker/`
- **Environment**: Review each script before running; some operate on personal systems.

## Project Structure

```text
shell/
├── bin/             # Executable scripts
├── docker/          # Docker-related scripts
├── mysql/           # MySQL utilities
└── fio/             # FIO benchmarks
```

## Key Concepts
- **POSIX Compliance**: Portable across shells
- **Bashisms**: Bash-specific features
- **Pipeline**: Unix philosophy, chaining commands
- **Subshells**: Isolated execution contexts
- **Exit Codes**: 0 for success, non-zero for errors

## Coding Conventions
- `#!/usr/bin/env bash` or `#!/bin/bash` shebang
- Use `set -e` (exit on error), `set -u` (undefined vars)
- Double quotes around variable expansions: `"$var"`
- Use `[[ ]]` over `[ ]` in bash
- `readonly` for constants
- `local` for function-local variables
- Functions: `function_name()` or `function function_name`
- Exit explicitly with `exit $?`

## AI Vibe Coding Tips
- Quote variables to prevent word splitting
- Use `$(command)` over backticks `` `command` ``
- `[[ -z "$var" ]]` for empty checks
- `[[ -f "$file" ]]` for file existence
- Use `read -r` to preserve backslashes
- Arrays: `("${array[@]}")` for proper expansion
- Use `getopts` for argument parsing
- Stderr: `echo "error" >&2`
- `trap` for cleanup on exit
- Test with `bash -n script.sh` for syntax
- Use `shellcheck` for linting
- Consider `yq`, `jq`, `fzf` for data processing
