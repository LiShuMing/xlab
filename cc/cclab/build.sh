#!/usr/bin/env bash
set -euo pipefail

# Supported portable build by default. Legacy experiments require explicit opt-in.
source_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
build_type=${1:-${BUILD_TYPE:-ASAN}}
build_type=$(printf '%s' "$build_type" | tr '[:lower:]' '[:upper:]')
case "$build_type" in
    DEBUG) configuration=Debug; sanitizer=none ;;
    RELEASE) configuration=Release; sanitizer=none ;;
    ASAN) configuration=Debug; sanitizer=address ;;
    UBSAN) configuration=Debug; sanitizer=undefined ;;
    LSAN) configuration=Debug; sanitizer=leak ;;
    *) echo "Expected DEBUG, RELEASE, ASAN, UBSAN or LSAN." >&2; exit 2 ;;
esac
cmake_bin=${CMAKE_BIN:-cmake}
command -v "$cmake_bin" >/dev/null || { echo "CMake >= 3.22 is required." >&2; exit 2; }
if [[ -n ${GCC_HOME:-} ]]; then
    export CC="$GCC_HOME/bin/gcc" CXX="$GCC_HOME/bin/g++"
fi
build_dir=${BUILD_DIR:-"$source_dir/build_$build_type"}
portable=${CCLAB_PORTABLE_ONLY:-ON}
if [[ "$portable" == OFF ]]; then
    # Legacy CMake owns its sanitizer flags and uses uppercase build types.
    configuration=$build_type
    sanitizer=none
fi
"$cmake_bin" -S "$source_dir" -B "$build_dir" \
    -DCMAKE_BUILD_TYPE="$configuration" \
    -DCCLAB_PORTABLE_ONLY="$portable" \
    -DXLAB_SANITIZER="$sanitizer" \
    -DXLAB_FETCH_DEPENDENCIES="${XLAB_FETCH_DEPENDENCIES:-OFF}" \
    -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
"$cmake_bin" --build "$build_dir" --parallel "${BUILD_JOBS:-4}"
"${CTEST_BIN:-ctest}" --test-dir "$build_dir" --output-on-failure --no-tests=error --timeout 60
