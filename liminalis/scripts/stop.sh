#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=dev-common.sh
source "${SCRIPT_DIR}/dev-common.sh"

load_dev_env

stop_service() {
  local name="$1"
  local port="$2"
  local file
  local pid
  local listener
  local session
  file="$(pid_file "${name}")"
  pid="$(read_pid "${name}")"
  session="$(session_name "${name}")"

  if tmux_available && tmux_is_running "${name}"; then
    echo "Stopping ${name} tmux session ${session}"
    tmux kill-session -t "=${session}" 2>/dev/null || true
    rm -f "${file}"
    listener="$(port_pid "${port}")"
    if [[ -n "${listener}" ]]; then
      echo "Stopping ${name} listener pid ${listener} on port ${port}"
      kill "${listener}" 2>/dev/null || true
    fi
    return 0
  fi

  if [[ -z "${pid}" ]]; then
    listener="$(port_pid "${port}")"
    if [[ -n "${listener}" ]]; then
      echo "Stopping ${name} listener pid ${listener} on port ${port}"
      kill "${listener}" 2>/dev/null || true
    else
      echo "${name}: no pid file"
    fi
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

[[ "${START_LIMINALIS}" == "1" ]] && stop_service "liminalis" "${LIMINALIS_PORT}"
[[ "${START_LIMINALIS_API}" == "1" ]] && stop_service "liminalis-api" "${LIMINALIS_API_PORT}"
if [[ "${START_LLM_WIKI}" == "1" ]]; then
  stop_service "llm-wiki" "${LLM_WIKI_PORT}"
  rm -f "${LLM_WIKI_SOCKET}"
fi

echo
"${SCRIPT_DIR}/check.sh"
