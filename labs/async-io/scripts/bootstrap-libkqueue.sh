#!/usr/bin/env bash
# Optional Linux compatibility dependency; never installed system-wide.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
downloads="$root/build/downloads"
archive="$downloads/libkqueue-v2.7.0.tar.gz"
digest=359702489ded4e466c721c5b02b0e569b914f13806b88c5846341efa5d05081b
mkdir -p "$downloads"
if ! [[ -f "$archive" ]] || ! printf '%s  %s\n' "$digest" "$archive" | sha256sum --check --status; then
    curl --fail --location --retry 2 --connect-timeout 10 --max-time 120 \
        --output "$archive" https://codeload.github.com/mheily/libkqueue/tar.gz/refs/tags/v2.7.0
fi
printf '%s  %s\n' "$digest" "$archive" | sha256sum --check
source_dir="$downloads/libkqueue-2.7.0"
if ! [[ -d "$source_dir" ]]; then tar -xzf "$archive" -C "$downloads"; fi
# Do not let upstream's Git version detection mistake the enclosing xlab checkout for libkqueue.
GIT_CEILING_DIRECTORIES="$downloads" cmake -S "$source_dir" -B "$root/build/libkqueue" -G Ninja \
    -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER="${CC:-gcc}" \
    -DCMAKE_INSTALL_PREFIX="$root/build/deps" -DCMAKE_INSTALL_LIBDIR=lib \
    -DVERSION_OVERRIDE=2.7.0 -DENABLE_STATIC=ON -DENABLE_SHARED=OFF -DENABLE_TESTING=OFF
cmake --build "$root/build/libkqueue" --parallel "${JOBS:-2}"
cmake --install "$root/build/libkqueue"
