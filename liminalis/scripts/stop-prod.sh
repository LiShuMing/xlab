#!/usr/bin/env bash
# 生产环境停止 Liminalis FastAPI 服务
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

LOG_DIR="${LOG_DIR:-${PROJECT_ROOT}/logs}"
STATE_DIR="${STATE_DIR:-${PROJECT_ROOT}/.dev}"
PID_FILE="${STATE_DIR}/liminalis-api.pid"
LIMINALIS_API_PORT="${LIMINALIS_API_PORT:-8010}"

echo "======================================"
echo "停止 Liminalis 生产服务"
echo "======================================"

# 优先尝试 systemd 停止
if systemctl is-active --quiet liminalis 2>/dev/null; then
    echo "通过 systemd 停止 liminalis..."
    sudo systemctl stop liminalis
    echo "已停止"
    exit 0
fi

# 回退到 PID 文件方式
PID=""
if [[ -f "${PID_FILE}" ]]; then
    PID="$(cat "${PID_FILE}")"
fi

# 如果 PID 文件不存在或无效，通过端口查找
if [[ -z "${PID}" ]] || ! kill -0 "${PID}" 2>/dev/null; then
    PID="$(lsof -nP -tiTCP:"${LIMINALIS_API_PORT}" -sTCP:LISTEN 2>/dev/null || true)"
fi

if [[ -z "${PID}" ]]; then
    echo "服务未在运行 (port ${LIMINALIS_API_PORT})"
    rm -f "${PID_FILE}"
    exit 0
fi

echo "停止进程 PID ${PID} (port ${LIMINALIS_API_PORT})..."
kill "${PID}" 2>/dev/null || true

# 等待退出
for _ in {1..20}; do
    if ! kill -0 "${PID}" 2>/dev/null; then
        echo "已停止"
        rm -f "${PID_FILE}"
        exit 0
    fi
    sleep 0.3
done

echo "进程未响应，强制终止..."
kill -9 "${PID}" 2>/dev/null || true
rm -f "${PID_FILE}"
echo "已强制停止"
