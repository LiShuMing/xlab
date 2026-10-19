#!/usr/bin/env bash
set -euo pipefail

# Build an explicitly selected Folly checkout against installed development
# packages. Never install packages or mutate xlab's Git metadata here.
if [[ $# -lt 1 || $# -gt 2 ]]; then
    echo "Usage: $0 /path/to/folly-source [/path/to/build-directory]" >&2
    exit 2
fi
folly_source=$(cd "$1" && pwd)
folly_build=${2:-"$folly_source/build"}
if [[ ! -f "$folly_source/folly/FBString.h" || ! -f "$folly_source/CMakeLists.txt" ]]; then
    echo "Expected a Folly source checkout; no build was attempted." >&2
    exit 2
fi
command -v cmake >/dev/null || { echo "CMake is required." >&2; exit 2; }

# Install platform development packages separately, including fast_float.
# CMAKE_PREFIX_PATH and Folly's package discovery select installed inputs.
cmake -S "$folly_source" -B "$folly_build" \
    -DBUILD_SHARED_LIBS=ON -DCMAKE_BUILD_TYPE=Release
cmake --build "$folly_build" --parallel "${BUILD_JOBS:-4}"
