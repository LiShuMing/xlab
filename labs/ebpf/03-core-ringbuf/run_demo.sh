#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
make -s all

echo "================================================================"
echo "Experiment 3A: libbpf + CO-RE + RingBuffer (exec/exit + R/W)"
echo "================================================================"

GO_FILE="/tmp/ebpf_core_go"
rm -f "$GO_FILE" /tmp/ebpf_rw_pid.txt

# Launch a Python child that waits for GO_FILE before issuing 200 writes + 200 reads.
python3 - <<'PY' >/tmp/ebpf_rw_pid.txt &
import os, time
print(os.getpid(), flush=True)
while not os.path.exists("/tmp/ebpf_core_go"):
    time.sleep(0.02)
path = "/var/tmp/ebpf_core_rw.dat"
buf = b"x" * 4096
with open(path, "wb+", buffering=0) as f:
    for _ in range(200):
        f.write(buf)
    f.flush()
    os.fsync(f.fileno())
    f.seek(0)
    for _ in range(200):
        _ = f.read(4096)
os.remove(path)
PY
PY_PID=$!

for _ in $(seq 1 50); do
    if [[ -s /tmp/ebpf_rw_pid.txt ]]; then break; fi
    sleep 0.02
done
TARGET_PID=$(cat /tmp/ebpf_rw_pid.txt)
rm -f /tmp/ebpf_rw_pid.txt

sudo ./bin/exec_rw_trace --pid "$TARGET_PID" --duration 2 --max-print 16 >/tmp/ebpf_core_trace.log 2>&1 &
TR_PID=$!

for _ in $(seq 1 50); do
    if grep -q "RingBuffer tracer active" /tmp/ebpf_core_trace.log 2>/dev/null; then break; fi
    sleep 0.05
done

# Release the R/W workload AND spawn short-lived processes concurrently.
touch "$GO_FILE"
for _ in 1 2 3 4 5; do
    /bin/true
    /bin/echo -n ""
done

wait "$PY_PID" || true
wait "$TR_PID" || true
rm -f "$GO_FILE"
cat /tmp/ebpf_core_trace.log
rm -f /tmp/ebpf_core_trace.log

echo ""
./verifier_cases/run_verifier_gallery.sh
