#!/usr/bin/env bash
set -euo pipefail

BIG_FILE_THRESHOLD="${BIG_FILE_THRESHOLD:-10M}"
GENERATED_NAMES="${GENERATED_NAMES:-node_modules .venv venv env ENV dist build target __pycache__ .pytest_cache .mypy_cache .ruff_cache .ipynb_checkpoints}"

warn_count=0
fail_count=0

section() {
    printf '\n== %s ==\n' "$1"
}

warn() {
    warn_count=$((warn_count + 1))
    printf 'WARN: %s\n' "$*"
}

fail() {
    fail_count=$((fail_count + 1))
    printf 'FAIL: %s\n' "$*"
}

ok() {
    printf 'OK: %s\n' "$*"
}

human_du() {
    du -sh "$1" 2>/dev/null | awk '{print $1}'
}

require_git_repo() {
    if ! git rev-parse --show-toplevel >/dev/null 2>&1; then
        printf 'FAIL: not inside a git repository\n' >&2
        exit 2
    fi
}

print_repo_size() {
    section "Repository Size"

    local root_size git_size worktree_size
    root_size="$(human_du .)"
    git_size="$(human_du .git || true)"
    worktree_size="n/a"
    if [ -n "$root_size" ] && [ -n "$git_size" ]; then
        worktree_size="$(du -sk . .git 2>/dev/null | awk 'NR==1 {root=$1} NR==2 {git=$1} END {if (root >= git) printf "%.1fM", (root-git)/1024; else print "n/a"}')"
    fi

    printf 'total:    %s\n' "${root_size:-unknown}"
    printf '.git:     %s\n' "${git_size:-unknown}"
    printf 'worktree: %s\n' "$worktree_size"

    if git count-objects -vH >/dev/null 2>&1; then
        git count-objects -vH | awk '/^(count|size|in-pack|packs|size-pack|garbage|size-garbage):/ {print}'
    fi
}

check_big_files() {
    section "Large Files"
    printf 'threshold: %s\n' "$BIG_FILE_THRESHOLD"

    local output
    output="$(
        find . \
            -path ./.git -prune -o \
            -path './*/thirdparty/*' -prune -o \
            -type f -size +"$BIG_FILE_THRESHOLD" -print0 |
        xargs -0 ls -lh 2>/dev/null |
        awk '{print $5 "\t" $9}'
    )"

    if [ -z "$output" ]; then
        ok "no files larger than ${BIG_FILE_THRESHOLD}"
    else
        warn "large files found"
        printf '%s\n' "$output"
    fi
}

check_generated_dirs() {
    section "Generated Directories"

    local find_expr=()
    local name
    for name in $GENERATED_NAMES; do
        find_expr+=( -name "$name" -o )
    done
    unset 'find_expr[${#find_expr[@]}-1]'

    local output
    output="$(
        find . \
            -path ./.git -prune -o \
            -path './*/thirdparty/*' -prune -o \
            -type d \( "${find_expr[@]}" \) -print |
        sort
    )"

    if [ -z "$output" ]; then
        ok "no generated dependency/cache directories found"
    else
        warn "generated directories found"
        printf '%s\n' "$output"
    fi
}

check_bad_symlinks() {
    section "Broken Symlinks"

    local output
    output="$(
        find . \
            -path ./.git -prune -o \
            -type l ! -exec test -e {} \; -print |
        sort
    )"

    if [ -z "$output" ]; then
        ok "no broken symlinks"
    else
        fail "broken symlinks found"
        printf '%s\n' "$output"
    fi
}

check_gitmodules() {
    section "Git Submodules"

    if [ ! -f .gitmodules ]; then
        ok "no .gitmodules file"
        return
    fi

    if ! git config --file .gitmodules --get-regexp '^submodule\..*\.(path|url)$' >/dev/null; then
        fail ".gitmodules cannot be parsed"
        return
    fi

    local duplicate_paths
    duplicate_paths="$(
        git config --file .gitmodules --get-regexp '^submodule\..*\.path$' |
        awk '{print $2}' |
        sort |
        uniq -d
    )"
    if [ -n "$duplicate_paths" ]; then
        fail "duplicate submodule paths found"
        printf '%s\n' "$duplicate_paths"
    else
        ok "no duplicate submodule paths"
    fi

    local bad_urls
    bad_urls="$(
        git config --file .gitmodules --get-regexp '^submodule\..*\.url$' |
        awk '$2 ~ /git@github.com:git@github.com/ || ($2 ~ /github.com/ && $2 !~ /\.git$/) {print}'
    )"
    if [ -n "$bad_urls" ]; then
        fail "suspicious submodule URLs found"
        printf '%s\n' "$bad_urls"
    else
        ok "no suspicious submodule URLs"
    fi

    if git submodule status --recursive >/dev/null 2>&1; then
        ok "git submodule status works"
    else
        fail "git submodule status failed"
        git submodule status --recursive || true
    fi
}

check_env_tracking() {
    section "Tracked Env/Secret Files"

    local output
    output="$(
        git ls-files |
        grep -E '(^|/)\.env($|[.])|(^|/)\.secrect_key$|(^|/).*secret.*$|(^|/).*credentials.*$' |
        grep -Ev '\.env\.example$' |
        sort
    )" || true

    if [ -z "$output" ]; then
        ok "no tracked env/secret files"
    else
        fail "tracked env/secret-like files found"
        printf '%s\n' "$output"
    fi
}

print_git_status_summary() {
    section "Git Status Summary"

    git status --short |
    awk '
        {
            key=$1
            counts[key]++
        }
        END {
            if (NR == 0) {
                print "clean"
                exit
            }
            for (key in counts) print key, counts[key]
        }
    ' |
    sort
}

main() {
    require_git_repo
    cd "$(git rev-parse --show-toplevel)"

    print_repo_size
    check_big_files
    check_generated_dirs
    check_bad_symlinks
    check_gitmodules
    check_env_tracking
    print_git_status_summary

    section "Summary"
    printf 'warnings: %d\n' "$warn_count"
    printf 'failures: %d\n' "$fail_count"

    if [ "$fail_count" -gt 0 ]; then
        exit 1
    fi
}

main "$@"
