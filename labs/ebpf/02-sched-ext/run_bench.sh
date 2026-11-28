#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
make -s all

HOGS=4
SAMPLES=150
PERIOD_MS=15
WORK_LOOPS=50000
HOG_SEC=10

run_case() {
    local label="$1"
    local scx_mode="$2" # none | fifo | prio_nopreempt | prio
    echo ""
    echo "================================================================"
    echo "Case: $label"
    echo "================================================================"

    local hog_log="/tmp/scx_hogs_${scx_mode}.log"
    rm -f "$hog_log"
    local hog_pids=()
    for _ in $(seq 1 "$HOGS"); do
        ./bin/cpu_compete hog "$HOG_SEC" >>"$hog_log" &
        hog_pids+=("$!")
    done

    local probe_log="/tmp/scx_probe_${scx_mode}.log"
    rm -f "$probe_log"
    ./bin/cpu_compete probe "$SAMPLES" "$PERIOD_MS" "$WORK_LOOPS" >"$probe_log" &
    local probe_pid=$!

    local scx_pid=""
    if [[ "$scx_mode" == "fifo" ]]; then
        sudo ./bin/scx_prio_fifo --short-us 0 >"/tmp/scx_ctl_${scx_mode}.log" 2>&1 &
        scx_pid=$!
        sleep 0.25
        echo "sched_ext state: $(cat /sys/kernel/sched_ext/state) ops=$(cat /sys/kernel/sched_ext/root/ops 2>/dev/null || echo none)"
    elif [[ "$scx_mode" == "prio_nopreempt" ]]; then
        sudo ./bin/scx_prio_fifo --pid "$probe_pid" --short-us 500 --no-preempt >"/tmp/scx_ctl_${scx_mode}.log" 2>&1 &
        scx_pid=$!
        sleep 0.25
        echo "sched_ext state: $(cat /sys/kernel/sched_ext/state) ops=$(cat /sys/kernel/sched_ext/root/ops 2>/dev/null || echo none)"
    elif [[ "$scx_mode" == "prio" ]]; then
        sudo ./bin/scx_prio_fifo --pid "$probe_pid" --short-us 500 >"/tmp/scx_ctl_${scx_mode}.log" 2>&1 &
        scx_pid=$!
        sleep 0.25
        echo "sched_ext state: $(cat /sys/kernel/sched_ext/state) ops=$(cat /sys/kernel/sched_ext/root/ops 2>/dev/null || echo none)"
    else
        echo "sched_ext state: $(cat /sys/kernel/sched_ext/state) (default EEVDF)"
    fi

    wait "$probe_pid" || true

    for hp in "${hog_pids[@]}"; do
        kill -TERM "$hp" 2>/dev/null || true
        wait "$hp" 2>/dev/null || true
    done

    if [[ -n "$scx_pid" ]]; then
        sudo kill -INT "$scx_pid" 2>/dev/null || true
        wait "$scx_pid" 2>/dev/null || true
        cat "/tmp/scx_ctl_${scx_mode}.log"
        rm -f "/tmp/scx_ctl_${scx_mode}.log"
        echo "post-detach sched_ext state: $(cat /sys/kernel/sched_ext/state)"
    fi

    cat "$probe_log"
    awk '/iters_per_s=/{split($5,a,"="); sum+=a[2]; n++} END{printf("hogs_agg_throughput: count=%d total_iters_per_s=%.1f\n", n, sum)}' "$hog_log"
    rm -f "$probe_log" "$hog_log"
}

run_case "1) Default Linux 7.0 EEVDF (baseline)" "none"
run_case "2) sched_ext Global FIFO (--short-us 0)" "fifo"
run_case "3) sched_ext Priority DSQ WITHOUT preempt kick (--no-preempt)" "prio_nopreempt"
run_case "4) sched_ext Priority DSQ WITH preempt kick (--pid + --short-us 500)" "prio"
