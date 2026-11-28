#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
mkdir -p bin

ARCH="$(uname -m | sed 's/x86_64/x86/;s/aarch64/arm64/')"
CFLAGS="-g -O2 -target bpf -D__TARGET_ARCH_${ARCH} -I../../common -I/usr/include/$(uname -m)-linux-gnu"

run_one() {
    local src="$1"
    local expect="$2" # FAIL or PASS
    local name="${src%.bpf.c}"
    local obj="bin/${name}.bpf.o"
    local pin="/sys/fs/bpf/xlab_verif_${name}"

    clang $CFLAGS -c "$src" -o "$obj"
    sudo rm -f "$pin"

    echo ""
    echo ">>> [$expect expected] $src"
    if out=$(sudo bpftool prog load "$obj" "$pin" 2>&1); then
        echo "RESULT: VERIFIER ACCEPTED"
        sudo rm -f "$pin"
        if [[ "$expect" == "FAIL" ]]; then
            echo "UNEXPECTED: expected rejection!"
            return 1
        fi
    else
        echo "RESULT: VERIFIER REJECTED (excerpt):"
        echo "$out" | grep -E "invalid|R[0-9]|loop|processed|libbpf:|failed|offset|outside|unbounded|too large" | tail -n 12
        if [[ "$expect" == "PASS" ]]; then
            echo "UNEXPECTED: expected acceptance!"
            echo "$out"
            return 1
        fi
    fi
}

echo "================================================================"
echo "BPF Verifier Gallery: 3 Classic Rejections & Fixes"
echo "================================================================"

run_one case1_null_deref_bad.bpf.c   FAIL
run_one case1_null_deref_fixed.bpf.c PASS
run_one case2_unbounded_loop_bad.bpf.c   FAIL
run_one case2_unbounded_loop_fixed.bpf.c PASS
run_one case3_pkt_oob_bad.bpf.c   FAIL
run_one case3_pkt_oob_fixed.bpf.c PASS
