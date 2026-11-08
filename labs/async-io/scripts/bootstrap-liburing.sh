#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
downloads="$root/build/downloads"
archive="$downloads/liburing-2.6.tar.gz"
digest=682f06733e6db6402c1f904cbbe12b94942a49effc872c9e01db3d7b180917cc
mkdir -p "$downloads"
if ! [[ -f "$archive" ]] || ! printf '%s  %s\n' "$digest" "$archive" | sha256sum --check --status; then
    curl --fail --location --connect-timeout 10 --max-time 120 \
        --output "$archive" https://codeload.github.com/axboe/liburing/tar.gz/refs/tags/liburing-2.6
fi
printf '%s  %s\n' "$digest" "$archive" | sha256sum --check
source_dir="$downloads/liburing-liburing-2.6"
if ! [[ -d "$source_dir" ]]; then tar -xzf "$archive" -C "$downloads"; fi
cd "$source_dir"
./configure --prefix="$root/build/deps" --cc="${CC:-gcc}"
# Build the library, not upstream hardware-specific tests (NVMe headers are optional).
make -C src -j"${JOBS:-2}"
make install
