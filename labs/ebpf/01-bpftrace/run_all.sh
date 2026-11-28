#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
make -s all

# Use /var/tmp (disk-backed ext4/xfs) instead of /tmp (often tmpfs).
TEST_FILE="${TEST_FILE:-/var/tmp/ebpf_pagecache.dat}"
SIZE_MB="${SIZE_MB:-16}"

echo "================================================================"
echo "Experiment 1A: Page Cache Hit/Miss & Readahead (bpftrace)"
echo "Filesystem backing $(dirname "$TEST_FILE"):"
df -T "$(dirname "$TEST_FILE")" | tail -n 1
echo "================================================================"

# Pre-create test file so creation writes do not pollute first run.
./bin/pagecache_bench warm "$TEST_FILE" "$SIZE_MB" >/dev/null

for mode in seq rand fadv_rand fadv_will warm; do
    echo ""
    echo "--- Mode: $mode ---"
    if [[ "$mode" != "warm" ]]; then
        sync
        echo 3 | sudo tee /proc/sys/vm/drop_caches >/dev/null
    fi
    sudo bpftrace -q --no-warnings ./pagecache.bt >"/tmp/bt_pc_${mode}.log" 2>&1 &
    BT_PID=$!
    for _ in $(seq 1 40); do
        if grep -q "Tracing filemap" "/tmp/bt_pc_${mode}.log" 2>/dev/null; then
            break
        fi
        sleep 0.1
    done
    ./bin/pagecache_bench "$mode" "$TEST_FILE" "$SIZE_MB"
    sleep 0.3
    sudo kill -INT "$BT_PID" 2>/dev/null || true
    wait "$BT_PID" 2>/dev/null || true
    cat "/tmp/bt_pc_${mode}.log"
    rm -f "/tmp/bt_pc_${mode}.log"
done

echo ""
echo "================================================================"
echo "Experiment 1B: Futex 2-Stage Contention Latency (bpftrace)"
echo "================================================================"

for cfg in "4 800 200 10" "4 800 200 400"; do
    read -r nthreads iters hold_us work_us <<< "$cfg"
    echo ""
    echo "--- Futex config: threads=$nthreads iters=$iters hold_us=$hold_us work_us=$work_us ---"
    sudo bpftrace -q --no-warnings ./futex_latency.bt >"/tmp/bt_futex.log" 2>&1 &
    BT_PID=$!
    sleep 1.2
    ./bin/futex_bench "$nthreads" "$iters" "$hold_us" "$work_us"
    sleep 0.3
    sudo kill -INT "$BT_PID" 2>/dev/null || true
    wait "$BT_PID" 2>/dev/null || true
    cat "/tmp/bt_futex.log"
    rm -f "/tmp/bt_futex.log"
done

rm -f "$TEST_FILE"
