#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=dev-common.sh
source "${SCRIPT_DIR}/dev-common.sh"

load_dev_env

echo "Process status"
print_service "liminalis" "${LIMINALIS_PORT}" "http://localhost:${LIMINALIS_PORT}/"
print_service "py-radar" "${RADAR_PORT}" "http://localhost:${RADAR_PORT}/api/news"
print_service "py-invest" "${INVEST_PORT}" "http://localhost:${INVEST_PORT}/api/status"
print_service "py-ego-api" "${EGO_API_PORT}" "http://localhost:${EGO_API_PORT}/health"
print_service "py-ego-h5" "${EGO_H5_PORT}" "http://localhost:${EGO_H5_PORT}/"

echo
echo "Health checks"
if http_ok "http://localhost:${LIMINALIS_PORT}/"; then
  echo "ok   liminalis"
else
  echo "fail liminalis"
fi

if http_ok "http://localhost:${RADAR_PORT}/api/news"; then
  echo "ok   py-radar"
else
  echo "fail py-radar"
fi

if http_ok "http://localhost:${INVEST_PORT}/api/status"; then
  echo "ok   py-invest"
else
  echo "fail py-invest"
fi

if http_ok "http://localhost:${EGO_API_PORT}/health"; then
  echo "ok   py-ego-api"
else
  echo "fail py-ego-api"
fi

if http_ok "http://localhost:${EGO_H5_PORT}/"; then
  echo "ok   py-ego-h5"
else
  echo "fail py-ego-h5"
fi

echo
echo "Logs: ${LOG_DIR}"
echo "PID files: ${STATE_DIR}"
echo "Python venv: ${VENV_DIR}"
