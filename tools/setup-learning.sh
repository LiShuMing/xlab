#!/usr/bin/env bash
# Isolated Linux x86_64 learning tools; no sudo and no shell-profile changes.
set -euo pipefail

selection="${1:-all}"
case "$selection" in
    all|ocaml|lean4) ;;
    *) printf 'Usage: bash tools/setup-learning.sh [all|ocaml|lean4]\n' >&2; exit 2 ;;
esac
if [[ "$(uname -sm)" != 'Linux x86_64' ]]; then
    printf 'This bootstrap supports Linux x86_64; use the official installers on other platforms.\n' >&2
    exit 2
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$repo_root/tools/learning-env.sh"
jobs="${XLAB_LEARNING_JOBS:-4}"
[[ "$jobs" =~ ^[1-9][0-9]*$ ]] || { printf 'XLAB_LEARNING_JOBS must be positive.\n' >&2; exit 2; }
mkdir -p "$XLAB_LEARNING_HOME"/{bin,downloads,sources,logs}

download() {
    local url="$1" archive="$2" digest="$3"
    if [[ -f "$archive" ]] && printf '%s  %s\n' "$digest" "$archive" | sha256sum --check --status; then
        return
    fi
    printf 'Downloading %s\n' "${archive##*/}"
    curl --fail --location --retry 2 --connect-timeout 15 --max-time 900 \
        --continue-at - --output "$archive" "$url"
    printf '%s  %s\n' "$digest" "$archive" | sha256sum --check
}

unpack() {
    mkdir -p "$2"
    tar -xzf "$1" --strip-components=1 -C "$2"
}

run_logged() {
    local name="$1"
    shift
    if ! "$@" >> "$XLAB_LEARNING_HOME/logs/$name.log" 2>&1; then
        tail -n 60 "$XLAB_LEARNING_HOME/logs/$name.log" >&2
        return 1
    fi
}

setup_ocaml() {
    local compiler prefix src dune_src
    compiler="$(<"$repo_root/ocaml/.ocaml-version")"
    [[ "$compiler" == 5.5.2 ]] || { printf 'Update bootstrap source pins for OCaml %s.\n' "$compiler" >&2; return 1; }
    prefix="$XLAB_LEARNING_HOME/ocaml/$compiler"
    src="$XLAB_LEARNING_HOME/sources/ocaml-$compiler"
    if [[ ! -x "$prefix/bin/ocamlopt" ]]; then
        download https://codeload.github.com/ocaml/ocaml/tar.gz/c7b6787eb4c2b4a89e2c190e7ffdfa25082d1a6d \
            "$XLAB_LEARNING_HOME/downloads/ocaml.tar.gz" f501581ef634b6262eb9456bd451599592c55cb1cf5b52a68f8489e47c4c42a3
        unpack "$XLAB_LEARNING_HOME/downloads/ocaml.tar.gz" "$src"
        printf 'Building OCaml %s (%s jobs); logs: %s/logs\n' "$compiler" "$jobs" "$XLAB_LEARNING_HOME"
        (cd "$src"; run_logged ocaml ./configure --prefix="$prefix"; run_logged ocaml make -j"$jobs" world.opt; run_logged ocaml make install)
    fi
    if [[ ! -x "$XLAB_LEARNING_HOME/bin/dune" ]] || [[ "$(dune --version)" != 3.24.2 ]]; then
        download https://codeload.github.com/ocaml/dune/tar.gz/ce734ac25ffb06994a4530426bb06ee8cda19e50 \
            "$XLAB_LEARNING_HOME/downloads/dune.tar.gz" 9d548d8e6a6605f4ca607d8a74e749853164a88429c4839fd8b3e6922096d892
        dune_src="$XLAB_LEARNING_HOME/sources/dune-3.24.2"
        unpack "$XLAB_LEARNING_HOME/downloads/dune.tar.gz" "$dune_src"
        # GitHub commit archives omit release metadata. Restore the pinned tag's
        # version stanza so the built executable reports the actual source version.
        patch -d "$dune_src" -p0 < "$repo_root/tools/dune-release-version.patch"
        (cd "$dune_src"; run_logged dune ocaml boot/bootstrap.ml -j "$jobs"
         run_logged dune ./_boot/dune.exe build dune.install -p dune --profile dune-bootstrap -j "$jobs"
         run_logged dune ./_boot/dune.exe install --prefix "$XLAB_LEARNING_HOME" dune)
    fi
    ocamlc -version
    dune --version
}

setup_elan() {
    [[ -x "$ELAN_HOME/bin/elan" ]] && return
    download https://github.com/leanprover/elan/releases/download/v4.2.4/elan-x86_64-unknown-linux-gnu.tar.gz \
        "$XLAB_LEARNING_HOME/downloads/elan.tar.gz" 42b94d4244e8353142c456ec0e4ca6528fd898a6c604d4059f494e706e431f63
    local installer="$XLAB_LEARNING_HOME/sources/elan-4.2.4"
    mkdir -p "$installer"
    tar -xzf "$XLAB_LEARNING_HOME/downloads/elan.tar.gz" -C "$installer"
    "$installer/elan-init" -y --no-modify-path --default-toolchain none
}

build_lean_source() {
    local native="$XLAB_LEARNING_HOME/native" src="$XLAB_LEARNING_HOME/sources/lean-4.35.0"
    local libuv_src="$XLAB_LEARNING_HOME/sources/libuv-1.51.0"
    local cadical_src="$XLAB_LEARNING_HOME/sources/cadical-2.1.2"
    local ssl_root="${OPENSSL_ROOT_DIR:-}"
    if [[ -z "$ssl_root" && -f "$HOME/miniconda3/include/openssl/opensslv.h" ]]; then
        ssl_root="$HOME/miniconda3"
    fi
    local runtime_rpath="-Wl,-rpath,$native/lib64 -Wl,-rpath,$native/lib"
    if [[ -n "$ssl_root" ]]; then
        runtime_rpath+=" -Wl,-rpath,$ssl_root/lib64 -Wl,-rpath,$ssl_root/lib"
    fi
    # CMake may prefer /usr/bin/gmake over the newer make already on PATH.
    # Older make jobservers are incompatible with Lean's parallel bootstrap.
    local -a compiler_args=("-DCMAKE_MAKE_PROGRAM:FILEPATH=$(command -v make)"
        "-DLEAN_EXTRA_LINKER_FLAGS=$runtime_rpath"
        "-DSTAGE0_LEAN_EXTRA_LINKER_FLAGS=$runtime_rpath")
    # Older GCC installations may need an explicitly selected Clang/libc++ pair.
    # Keep machine-specific compiler locations out of the portable installer.
    if [[ -z "${CXX:-}" && -n "${XLAB_CLANG_ROOT:-}" ]]; then
        local clang_root="$XLAB_CLANG_ROOT" gcc_root
        [[ -x "$clang_root/bin/clang" && -x "$clang_root/bin/clang++" ]] || {
            printf 'XLAB_CLANG_ROOT must contain bin/clang and bin/clang++.\n' >&2; return 1;
        }
        gcc_root="$(dirname "$(dirname "$(readlink -f "$(command -v gcc)")")")"
        runtime_rpath+=" --gcc-toolchain=$gcc_root -L$clang_root/lib64 -Wl,-rpath,$clang_root/lib64"
        compiler_args+=("-DCMAKE_C_COMPILER=$clang_root/bin/clang" "-DCMAKE_CXX_COMPILER=$clang_root/bin/clang++"
            "-DLEAN_EXTRA_LINKER_FLAGS=$runtime_rpath" "-DSTAGE0_LEAN_EXTRA_LINKER_FLAGS=$runtime_rpath"
            "-DCMAKE_C_FLAGS:STRING=--gcc-toolchain=$gcc_root"
            "-DCMAKE_CXX_FLAGS:STRING=--gcc-toolchain=$gcc_root -stdlib=libc++"
            "-DCMAKE_EXE_LINKER_FLAGS:STRING=-L$clang_root/lib64 -Wl,-rpath,$clang_root/lib64"
            "-DCMAKE_SHARED_LINKER_FLAGS:STRING=-L$clang_root/lib64 -Wl,-rpath,$clang_root/lib64"
            "-DLEANC_EXTRA_CC_FLAGS=--gcc-toolchain=$gcc_root -L$clang_root/lib64 -Wl,-rpath,$clang_root/lib64"
            "-DSTAGE0_LEANC_EXTRA_CC_FLAGS=--gcc-toolchain=$gcc_root -L$clang_root/lib64 -Wl,-rpath,$clang_root/lib64"
            '-DLEAN_CXX_STDLIB=-lc++' '-DSTAGE0_LEAN_CXX_STDLIB=-lc++')
    fi
    if [[ -n "$ssl_root" ]]; then
        compiler_args+=("-DOPENSSL_ROOT_DIR=$ssl_root" "-DSTAGE0_OPENSSL_ROOT_DIR=$ssl_root")
    fi
    # Lean's stage1 configure does not inherit typed CMake cache entries.
    # Explicit prefixes keep resumed and clean builds on the same compiler.
    local arg
    for arg in "${compiler_args[@]}"; do
        [[ "$arg" == -DSTAGE0_* ]] || compiler_args+=("-DSTAGE1_${arg#-D}")
    done
    export PKG_CONFIG_PATH="$native/lib64/pkgconfig:$native/lib/pkgconfig${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}"
    if ! pkg-config --exists libuv; then
        download https://codeload.github.com/libuv/libuv/tar.gz/refs/tags/v1.51.0 \
            "$XLAB_LEARNING_HOME/downloads/libuv.tar.gz" 27e55cf7083913bfb6826ca78cde9de7647cded648d35f24163f2d31bb9f51cd
        unpack "$XLAB_LEARNING_HOME/downloads/libuv.tar.gz" "$libuv_src"
        run_logged libuv cmake -S "$libuv_src" -B "$libuv_src/build" \
            -DCMAKE_INSTALL_PREFIX="$native" -DLIBUV_BUILD_TESTS=OFF -DCMAKE_BUILD_TYPE=Release
        run_logged libuv cmake --build "$libuv_src/build" --parallel "$jobs"
        run_logged libuv cmake --install "$libuv_src/build"
    fi
    if [[ ! -x "$XLAB_LEARNING_HOME/bin/cadical" ]]; then
        download https://codeload.github.com/arminbiere/cadical/tar.gz/refs/tags/rel-2.1.2 \
            "$XLAB_LEARNING_HOME/downloads/cadical.tar.gz" 292c2bb8d712d6d05fce3d3df63b922b8fa45e03974a79f7bae5bf68c284f131
        unpack "$XLAB_LEARNING_HOME/downloads/cadical.tar.gz" "$cadical_src"
        (cd "$cadical_src"; run_logged cadical ./configure; run_logged cadical make -j"$jobs")
        install -m755 "$cadical_src/build/cadical" "$XLAB_LEARNING_HOME/bin/cadical"
    fi
    if [[ ! -x "$XLAB_LEARNING_HOME/bin/leantar" ]]; then
        download https://github.com/digama0/leangz/releases/download/v0.1.20/leantar-v0.1.20-x86_64-unknown-linux-musl.tar.gz \
            "$XLAB_LEARNING_HOME/downloads/leantar.tar.gz" 1789878731efbd6eb56515dbe511f7836547defde237cf5e4b29e78eaedaeb86
        local leantar_src="$XLAB_LEARNING_HOME/sources/leantar-0.1.20"
        mkdir -p "$leantar_src"
        tar -xzf "$XLAB_LEARNING_HOME/downloads/leantar.tar.gz" --strip-components=1 -C "$leantar_src"
        install -m755 "$leantar_src/leantar" "$XLAB_LEARNING_HOME/bin/leantar"
    fi
    if [[ ! -f "$src/build/xlab-release/.xlab-complete" ]]; then
        download https://codeload.github.com/leanprover/lean4/tar.gz/eb6cafb7290e8bd5f2937522d8d804f58f02bafc \
            "$XLAB_LEARNING_HOME/downloads/lean4.tar.gz" a947ac7d535edf26ca5a2542615f8ba4b50756e099cd6c8913f789de96b6b92c
        unpack "$XLAB_LEARNING_HOME/downloads/lean4.tar.gz" "$src"
        if ! printf '#include <sys/random.h>\n' | "${CC:-cc}" -E -x c - >/dev/null 2>&1; then
            # Lean's pinned source includes this glibc >=2.25 header but never
            # uses its API: random bytes are read from /dev/urandom instead.
            patch -d "$src" -p1 < "$repo_root/tools/lean-glibc217.patch"
        fi
        printf 'Building Lean 4.35.0 (%s jobs); logs: %s/logs/lean.log\n' "$jobs" "$XLAB_LEARNING_HOME"
        # Built-in bignums avoid the known soundness bugs in system GMP < 6.3.
        # The system allocator avoids fetching an additional mimalloc checkout.
        run_logged lean cmake -S "$src" -B "$src/build/xlab-release" \
            -DCMAKE_BUILD_TYPE=Release -DUSE_GMP=OFF -DUSE_MIMALLOC=OFF \
            -DLEAN_VERSION_IS_RELEASE=1 -DUSE_GITHASH=OFF \
            -DCADICAL="$XLAB_LEARNING_HOME/bin/cadical" -DLEANTAR="$XLAB_LEARNING_HOME/bin/leantar" \
            "${compiler_args[@]}"
        run_logged lean cmake --build "$src/build/xlab-release" --parallel "$jobs"
        "$src/build/xlab-release/stage1/bin/lean" --version
        "$src/build/xlab-release/stage1/bin/lake" --version
        touch "$src/build/xlab-release/.xlab-complete"
    fi
    local registered="$ELAN_HOME/toolchains/xlab-lean-4.35.0"
    if [[ -e "$registered" || -L "$registered" ]]; then
        if [[ "$(readlink -f "$registered")" != "$(readlink -f "$src/build/xlab-release/stage1")" ]]; then
            printf 'Existing custom Lean toolchain points elsewhere: %s\n' "$registered" >&2
            return 1
        fi
    else
        elan toolchain link xlab-lean-4.35.0 "$src/build/xlab-release/stage1"
    fi
    elan default xlab-lean-4.35.0
    (cd "$repo_root/lean4"; elan override set xlab-lean-4.35.0)
}

setup_lean() {
    local toolchain from_source="${XLAB_LEAN_FROM_SOURCE:-0}" libc_major libc_minor
    toolchain="$(<"$repo_root/lean4/lean-toolchain")"
    [[ "$toolchain" == leanprover/lean4:v4.35.0 ]] || { printf 'Update bootstrap source pins for %s.\n' "$toolchain" >&2; return 1; }
    setup_elan
    read -r libc_major libc_minor < <(getconf GNU_LIBC_VERSION | awk '{split($2,v,"."); print v[1],v[2]}')
    if (( libc_major == 2 && libc_minor < 27 )); then from_source=1; fi
    if [[ "$from_source" == 1 ]]; then
        build_lean_source
    else
        elan toolchain install "$toolchain"
        elan default "$toolchain"
    fi
    (cd "$repo_root/lean4"; lean --version; lake --version)
}

case "$selection" in
    ocaml) setup_ocaml ;;
    lean4) setup_lean ;;
    all) setup_ocaml; setup_lean ;;
esac
printf 'Activate in each new terminal: source %q/tools/learning-env.sh\n' "$repo_root"
