#!/usr/bin/env bash
# 生产环境启动脚本 - 仅启动 FastAPI 服务
# 用于微信公众号部署，nginx 反代到此服务
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# 配置
LOG_DIR="${LOG_DIR:-${PROJECT_ROOT}/logs}"
STATE_DIR="${STATE_DIR:-${PROJECT_ROOT}/.dev}"
VENV_DIR="${VENV_DIR:-${HOME}/.venv}"
PYTHON_BIN="${PYTHON_BIN:-${VENV_DIR}/bin/python}"
LIMINALIS_API_PORT="${LIMINALIS_API_PORT:-8010}"

mkdir -p "${LOG_DIR}" "${STATE_DIR}"

# 加载环境变量
load_env_file() {
  local file="$1"
  if [[ -f "${file}" ]]; then
    set -a
    source "${file}"
    set +a
  fi
}

load_env_file "${HOME}/.env"
load_env_file "${PROJECT_ROOT}/.env"
load_env_file "${PROJECT_ROOT}/.env.local"

# 检查 dist 目录是否存在
if [[ ! -d "${PROJECT_ROOT}/dist" ]]; then
  echo "Error: dist/ directory not found. Run 'npm run build' first."
  exit 1
fi

# 检查 Python venv
if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "Error: Python venv not found at ${PYTHON_BIN}"
  echo "Run: python3 -m venv ${VENV_DIR}"
  exit 1
fi

# 安装依赖
echo "Installing Python dependencies..."
cd "${PROJECT_ROOT}"
"${PYTHON_BIN}" -m pip install -e . --quiet

# 启动 FastAPI
echo "Starting Liminalis FastAPI on port ${LIMINALIS_API_PORT}..."
LOG_FILE="${LOG_DIR}/liminalis-api.log"
PID_FILE="${STATE_DIR}/liminalis-api.pid"

# 检查端口是否被占用
LISTENER=$(lsof -nP -tiTCP:"${LIMINALIS_API_PORT}" -sTCP:LISTEN 2>/dev/null || true)
if [[ -n "${LISTENER}" ]]; then
  echo "Port ${LIMINALIS_API_PORT} is already in use by pid ${LISTENER}"
  exit 1
fi

# 启动服务
nohup "${PYTHON_BIN}" -m uvicorn backend.app:app \
  --host 127.0.0.1 \
  --port "${LIMINALIS_API_PORT}" \
  >> "${LOG_FILE}" 2>&1 &

echo $! > "${PID_FILE}"

# 等待服务启动
sleep 2
for i in {1..30}; do
  if curl -fsS --max-time 2 "http://127.0.0.1:${LIMINALIS_API_PORT}/health" >/dev/null 2>&1; then
    echo "Liminalis FastAPI started successfully"
    echo "PID: $(cat ${PID_FILE})"
    echo "Port: ${LIMINALIS_API_PORT}"
    echo "Log: ${LOG_FILE}"
    echo ""
    echo "Nginx should proxy to: http://127.0.0.1:${LIMINALIS_API_PORT}"
    exit 0
  fi
  sleep 0.5
done

echo "Failed to start Liminalis FastAPI"
echo "Last log lines:"
tail -n 40 "${LOG_FILE}" 2>/dev/null || true
exit 1