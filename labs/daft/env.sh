#!/usr/bin/env bash
set -euo pipefail
project=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
rootfs="$project/.local/rootfs"
if [[ ! -f "$rootfs/.daft-lab-ready" ]]; then
    printf 'Run python3 %s/bootstrap.py first.\n' "$project" >&2
    exit 1
fi
mkdir -p "$project/.local/tmp" "$project/.local/data" "$project/.local/runs"
cpu_list=$(python3 -c 'import os; print(",".join(map(str, sorted(os.sched_getaffinity(0))[:int(os.environ.get("DAFT_LAB_CPUS", "4"))])))')
exec taskset --cpu-list "$cpu_list" unshare --user --map-root-user --mount --pid --fork \
    bash -c '
        set -euo pipefail
        project=$1
        rootfs=$2
        shift 2
        mount --make-rprivate /
        mount --bind "$project" "$rootfs/lab"
        mount -t proc proc "$rootfs/proc"
        mount --rbind /dev "$rootfs/dev"
        mount -t tmpfs -o size=512m tmpfs "$rootfs/dev/shm"
        exec chroot "$rootfs" /usr/bin/env -i \
            HOME=/lab/.local PATH=/lab/.local/venv/bin:/usr/local/bin:/usr/bin:/bin \
            LANG=C.UTF-8 LC_ALL=C.UTF-8 \
            SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt UV_SYSTEM_CERTS=true \
            UV_CACHE_DIR=/lab/.local/uv-cache UV_PROJECT_ENVIRONMENT=/lab/.local/venv \
            TMPDIR=/lab/.local/tmp DAFT_ANALYTICS_ENABLED=0 DAFT_PROGRESS_BAR=0 \
            OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 RAYON_NUM_THREADS=4 \
            /bin/sh -c '\''cd /lab; exec "$@"'\'' sh "$@"
    ' bash "$project" "$rootfs" "$@"
