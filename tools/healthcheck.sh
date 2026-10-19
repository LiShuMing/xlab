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
    du -sh "$1" 2>/dev/null | awk 'NR == 1 {print $1}'
}

require_git_repo() {
    if ! git rev-parse --show-toplevel >/dev/null 2>&1; then
        printf 'FAIL: not inside a git repository\n' >&2
        exit 2
    fi
}

print_repo_size() {
    section "Repository Size"

    local root_kib metadata_kib git_dir root_size git_size worktree_size
    # Separate du calls: GNU du deduplicates .git when . and .git share one call.
    root_size="$(human_du .)"
    root_kib="$(du -sk . | awk '{print $1}')"
    metadata_kib=0
    if [[ -e .git ]]; then
        metadata_kib="$(du -sk .git | awk '{print $1}')"
    fi
    git_dir="$(git rev-parse --absolute-git-dir)"
    git_size="$(human_du "$git_dir")"
    # In linked worktrees .git is a file; external Git objects are not in root.
    worktree_size="$(awk -v root="$root_kib" -v meta="$metadata_kib" \
        'BEGIN {if (root >= meta) printf "%.1fM", (root-meta)/1024; else print "n/a"}')"

    printf 'total:    %s\n' "$root_size"
    printf 'git metadata: %s\n' "$git_size"
    printf 'worktree: %s\n' "$worktree_size"

    if git --git-dir="$(git rev-parse --git-common-dir)" count-objects -vH >/dev/null 2>&1; then
        git --git-dir="$(git rev-parse --git-common-dir)" count-objects -vH | awk '/^(count|size|in-pack|packs|size-pack|garbage|size-garbage):/ {print}'
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
        while IFS= read -r -d '' path; do
            printf '%s\t%q\n' "$(human_du "$path")" "$path"
        done
    )"

    if [[ -z "$output" ]]; then
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

    local declarations=() gitlinks=() record key path url entry found other
    local declaration_count=0 gitlink_count=0
    # Bash 3.2 (macOS) treats an empty array as unset under nounset.
    if [[ -f .gitmodules ]]; then
        if ! git config --file .gitmodules --list >/dev/null; then
            fail ".gitmodules cannot be parsed"
            return
        fi
        # -z separates records with NUL and key/value with newline, preserving spaces.
        while IFS= read -r -d '' record; do
            key="${record%%$'\n'*}"
            path="${record#*$'\n'}"
            if [[ -z "$path" ]]; then
                fail "empty submodule path declaration"
                continue
            fi
            for other in ${declarations[@]+"${declarations[@]}"}; do
                [[ "$path" != "$other" ]] || fail "duplicate submodule path: $path"
            done
            declarations[declaration_count]="$path"
            declaration_count=$((declaration_count + 1))
            url="$(git config --file .gitmodules --get "${key%.path}.url" || true)"
            if [[ -z "$url" || "$url" == *git@github.com:git@github.com* ]]; then
                fail "missing or suspicious submodule URL for: $path"
            fi
        done < <(git config -z --file .gitmodules --get-regexp '^submodule\..*\.path$' || true)
    fi

    while IFS= read -r -d '' entry; do
        [[ "$entry" == 160000\ * ]] || continue
        gitlinks[gitlink_count]="${entry#*$'\t'}"
        gitlink_count=$((gitlink_count + 1))
    done < <(git ls-files --stage -z)
    printf 'declarations: %d\ngitlinks: %d\n' "$declaration_count" "$gitlink_count"
    for path in ${declarations[@]+"${declarations[@]}"}; do
        found=0
        for other in ${gitlinks[@]+"${gitlinks[@]}"}; do
            [[ "$path" != "$other" ]] || found=1
        done
        [[ "$found" == 1 ]] || fail "declaration without gitlink: $path"
    done
    for path in ${gitlinks[@]+"${gitlinks[@]}"}; do
        found=0
        for other in ${declarations[@]+"${declarations[@]}"}; do
            [[ "$path" != "$other" ]] || found=1
        done
        [[ "$found" == 1 ]] || fail "gitlink without declaration: $path"
    done
    if [[ $gitlink_count == 0 ]]; then
        if [[ $declaration_count == 0 ]]; then
            ok "no submodules declared or tracked"
        fi
        return
    fi
    local status
    if status="$(git submodule status --recursive 2>/dev/null)"; then
        if [[ "$status" == +* || "$status" == U* || "$status" == *$'\n+'* || "$status" == *$'\nU'* ]]; then
            fail "submodule checkout differs from its recorded commit or is conflicted"
        elif [[ "$status" == -* || "$status" == *$'\n-'* ]]; then
            warn "tracked submodules are not initialized"
        else
            ok "tracked submodule checkouts match recorded commits"
        fi
    else
        fail "git submodule status failed"
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
    if [[ -f tools/check_dependencies.py && -f docs/meta/dependency-declarations.json ]]; then
        section "Dependency Catalog"
        if command -v python3 >/dev/null; then
            python3 tools/check_dependencies.py || fail "dependency catalog validation failed"
            warn "legacy experiments require separate package/source validation; metadata health is not a full build pass"
        else
            fail "python3 is required to validate the dependency catalog"
        fi
    fi
    print_git_status_summary

    section "Summary"
    printf 'warnings: %d\n' "$warn_count"
    printf 'failures: %d\n' "$fail_count"

    if [ "$fail_count" -gt 0 ]; then
        exit 1
    fi
}

main "$@"
