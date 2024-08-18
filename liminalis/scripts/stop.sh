#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=dev-common.sh
source "${SCRIPT_DIR}/dev-common.sh"

stop_service() {
  local name="$1"
  local file
  local pid
  file="$(pid_file "${name}")"
  pid="$(read_pid "${name}")"

  if [[ -z "${pid}" ]]; then
    echo "${name}: no pid file"
    return 0
  fi

  if ! pid_is_running "${pid}"; then
    echo "${name}: pid ${pid} is not running"
    rm -f "${file}"
    return 0
  fi

  echo "Stopping ${name} pid ${pid}"
  kill "${pid}" 2>/dev/null || true

  for _ in {1..20}; do
    if ! pid_is_running "${pid}"; then
      rm -f "${file}"
      return 0
    fi
    sleep 0.2
  done

  echo "${name}: pid ${pid} did not exit after TERM; sending KILL"
  kill -9 "${pid}" 2>/dev/null || true
  rm -f "${file}"
}

stop_service "liminalis"
stop_service "py-ego-h5"
stop_service "py-ego-api"
stop_service "py-invest"
stop_service "py-radar"

echo
"${SCRIPT_DIR}/check.sh"
