#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="${ROOT_DIR}/build"

export PKG_CONFIG_PATH="/home/disk1/sr-deps/thirdparty-latest/installed/lib64/pkgconfig:/home/disk1/sr-deps/thirdparty-latest/installed/lib/pkgconfig:${PKG_CONFIG_PATH:-}"

cmake -S "${ROOT_DIR}" -B "${BUILD_DIR}" "$@"
cmake --build "${BUILD_DIR}"
