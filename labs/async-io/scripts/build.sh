#!/usr/bin/env bash
# Explicit toolchain through CXX/CXXFLAGS/LDFLAGS; no global configuration changes.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
prefix="${LIBURING_ROOT:-$root/build/deps}"
for project in uring server; do
    extra=(-DCMAKE_BUILD_TYPE=Release)
    if [[ -n "${CXXFLAGS:-}" ]]; then extra+=("-DCMAKE_CXX_FLAGS=$CXXFLAGS"); fi
    if [[ -n "${LDFLAGS:-}" ]]; then extra+=("-DCMAKE_EXE_LINKER_FLAGS=$LDFLAGS"); fi
    if [[ "$project" == server ]]; then
        extra+=(-DRINGSERVER_ENABLE_URING=ON
            "-DRINGSERVER_ENABLE_KQUEUE_COMPAT=${KQUEUE_COMPAT:-OFF}"
            "-DLIBKQUEUE_ROOT=${LIBKQUEUE_ROOT:-$root/build/deps}")
    fi
    cmake -S "$root/$project" -B "$root/build/$project" -G Ninja \
        -DLIBURING_ROOT="$prefix" "${extra[@]}"
    cmake --build "$root/build/$project" --parallel "${JOBS:-2}"
done
