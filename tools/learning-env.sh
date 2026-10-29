#!/usr/bin/env bash
# Source this file in Bash to activate only the isolated xlab learning tools.
_xlab_repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export XLAB_LEARNING_HOME="${XLAB_LEARNING_HOME:-${XDG_DATA_HOME:-$HOME/.local/share}/xlab-learning}"
export ELAN_HOME="$XLAB_LEARNING_HOME/elan"
export PATH="$XLAB_LEARNING_HOME/ocaml/$(<"$_xlab_repo_root/ocaml/.ocaml-version")/bin:$XLAB_LEARNING_HOME/bin:$ELAN_HOME/bin:$PATH"
# A source-built Lean embeds flags for its chosen C compiler. Lake otherwise
# defaults to `cc`, which may be an incompatible GCC on this host. LEAN_CC is
# Lean-specific: leave the user's global CC/CXX and explicit LEAN_CC untouched.
_xlab_lean_build="$XLAB_LEARNING_HOME/sources/lean-4.35.0/build/xlab-release"
if [[ -z "${LEAN_CC:-}" && -f "$_xlab_lean_build/.xlab-complete" && -f "$_xlab_lean_build/stage1/CMakeCache.txt" ]]; then
    _xlab_lean_cc="$(sed -n 's/^CMAKE_C_COMPILER:[^=]*=//p' "$_xlab_lean_build/stage1/CMakeCache.txt")"
    if [[ -n "$_xlab_lean_cc" ]]; then export LEAN_CC="$_xlab_lean_cc"; fi
    unset _xlab_lean_cc
fi
unset _xlab_lean_build
unset _xlab_repo_root
