#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
XLAB_ROOT="$(cd "${PROJECT_ROOT}/.." && pwd)"

LOG_DIR="${LOG_DIR:-${PROJECT_ROOT}/logs}"
STATE_DIR="${STATE_DIR:-${PROJECT_ROOT}/.dev}"
VENV_DIR="${VENV_DIR:-${HOME}/.venv}"
PYTHON_BIN="${PYTHON_BIN:-${VENV_DIR}/bin/python}"
VENV_ACTIVATE="${VENV_ACTIVATE:-${VENV_DIR}/bin/activate}"

LIMINALIS_PORT="${LIMINALIS_PORT:-5173}"
RADAR_PORT="${RADAR_PORT:-5000}"
INVEST_PORT="${INVEST_PORT:-8080}"
EGO_API_PORT="${EGO_API_PORT:-8090}"
EGO_H5_PORT="${EGO_H5_PORT:-5174}"

RADAR_DIR="${RADAR_DIR:-${XLAB_ROOT}/python/projects/py-radar}"
INVEST_DIR="${INVEST_DIR:-${XLAB_ROOT}/python/projects/py-invest}"
EGO_API_DIR="${EGO_API_DIR:-${XLAB_ROOT}/python/projects/py-ego/py-ego-miniapp}"
EGO_H5_DIR="${EGO_H5_DIR:-${XLAB_ROOT}/python/projects/py-ego/miniprogram}"

START_RADAR="${START_RADAR:-1}"
START_INVEST="${START_INVEST:-1}"
START_EGO_API="${START_EGO_API:-1}"
START_EGO_H5="${START_EGO_H5:-1}"
START_LIMINALIS="${START_LIMINALIS:-1}"
SKIP_DEPS="${SKIP_DEPS:-0}"

mkdir -p "${LOG_DIR}" "${STATE_DIR}"

load_env_file() {
  local file="$1"
  if [[ -f "${file}" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "${file}"
    set +a
  fi
}

load_dev_env() {
  load_env_file "${HOME}/.env"
  load_env_file "${PROJECT_ROOT}/.env"
  load_env_file "${PROJECT_ROOT}/.env.local"
}

pid_file() {
  printf '%s/%s.pid\n' "${STATE_DIR}" "$1"
}

log_file() {
  printf '%s/%s.log\n' "${LOG_DIR}" "$1"
}

pid_is_running() {
  local pid="$1"
  [[ -n "${pid}" ]] && kill -0 "${pid}" >/dev/null 2>&1
}

read_pid() {
  local file
  file="$(pid_file "$1")"
  [[ -f "${file}" ]] && tr -d '[:space:]' < "${file}" || true
}

port_pid() {
  local port="$1"
  lsof -nP -tiTCP:"${port}" -sTCP:LISTEN 2>/dev/null | head -n 1 || true
}

http_ok() {
  local url="$1"
  curl -fsS --max-time 3 "${url}" >/dev/null 2>&1
}

print_service() {
  local name="$1"
  local port="$2"
  local url="$3"
  local pid
  local listener
  pid="$(read_pid "${name}")"
  listener="$(port_pid "${port}")"

  if [[ -n "${pid}" ]] && pid_is_running "${pid}"; then
    printf '%-14s running pid=%-8s port=%-5s %s\n' "${name}" "${pid}" "${port}" "${url}"
  elif [[ -n "${listener}" ]]; then
    printf '%-14s running pid=%-8s port=%-5s %s (external/no pid file)\n' "${name}" "${listener}" "${port}" "${url}"
  else
    printf '%-14s stopped             port=%-5s %s\n' "${name}" "${port}" "${url}"
  fi
}

ensure_node_deps() {
  local dir="$1"
  if [[ "${SKIP_DEPS}" == "1" || -d "${dir}/node_modules" ]]; then
    return 0
  fi

  echo "Installing node dependencies in ${dir}"
  (cd "${dir}" && npm install)
}

ensure_venv() {
  local dir="$1"
  shift

  if [[ "${SKIP_DEPS}" == "1" ]]; then
    return 0
  fi

  if [[ ! -x "${PYTHON_BIN}" ]]; then
    echo "Creating shared Python venv in ${VENV_DIR}"
    python3 -m venv "${VENV_DIR}"
  fi

  echo "Installing Python dependencies in ${dir} with ${PYTHON_BIN}"
  (cd "${dir}" && "${PYTHON_BIN}" -m pip install --upgrade pip >/dev/null && "$@")
}

start_process() {
  local name="$1"
  local port="$2"
  local cwd="$3"
  local command="$4"
  local pid
  local listener
  local pid_path
  local log_path

  pid="$(read_pid "${name}")"
  if [[ -n "${pid}" ]] && pid_is_running "${pid}"; then
    echo "${name} already running with pid ${pid}"
    return 0
  fi

  listener="$(port_pid "${port}")"
  if [[ -n "${listener}" ]]; then
    echo "${name} port ${port} is already used by pid ${listener}; treating it as running"
    return 0
  fi

  pid_path="$(pid_file "${name}")"
  log_path="$(log_file "${name}")"
  echo "Starting ${name} on port ${port}; log: ${log_path}"
  (
    cd "${cwd}"
    nohup bash -lc "${command}" > "${log_path}" 2>&1 &
    echo "$!" > "${pid_path}"
  )

  sleep 1
  pid="$(read_pid "${name}")"
  if ! pid_is_running "${pid}"; then
    echo "${name} failed to start; last log lines:"
    tail -n 40 "${log_path}" 2>/dev/null || true
    return 1
  fi
}
