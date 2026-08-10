#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

LOG_DIR="${LOG_DIR:-${PROJECT_ROOT}/logs}"
STATE_DIR="${STATE_DIR:-${PROJECT_ROOT}/.dev}"
VENV_DIR="${VENV_DIR:-${HOME}/.venv}"
PYTHON_BIN="${PYTHON_BIN:-${VENV_DIR}/bin/python}"
VENV_ACTIVATE="${VENV_ACTIVATE:-${VENV_DIR}/bin/activate}"

LIMINALIS_PORT="${LIMINALIS_PORT:-5173}"
LIMINALIS_API_PORT="${LIMINALIS_API_PORT:-8010}"
LLM_WIKI_ROOT="${LLM_WIKI_ROOT:-${PROJECT_ROOT}/llm-wiki}"
LLM_WIKI_PORT="${LLM_WIKI_PORT:-8787}"
LLM_WIKI_SOCKET="${LLM_WIKI_SOCKET:-${STATE_DIR}/llm-wiki.sock}"
LLM_WIKI_PROVIDER="${LLM_WIKI_PROVIDER:-llm}"
LLM_WIKI_DATA="${LLM_WIKI_DATA:-.demo-data}"
START_LIMINALIS="${START_LIMINALIS:-1}"
START_LIMINALIS_API="${START_LIMINALIS_API:-1}"
START_LLM_WIKI="${START_LLM_WIKI:-1}"
SKIP_DEPS="${SKIP_DEPS:-0}"
START_USE_TMUX="${START_USE_TMUX:-1}"

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

session_name() {
  printf 'liminalis-%s\n' "$1"
}

tmux_available() {
  [[ "${START_USE_TMUX}" == "1" ]] && command -v tmux >/dev/null 2>&1
}

tmux_is_running() {
  local name="$1"
  tmux has-session -t "=$(session_name "${name}")" >/dev/null 2>&1
}

tmux_pid() {
  local name="$1"
  tmux display-message -p -t "$(session_name "${name}")" '#{pane_pid}' 2>/dev/null || true
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

socket_is_ready() {
  local socket="$1"
  [[ -S "${socket}" ]]
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

  if tmux_available && tmux_is_running "${name}"; then
    pid="$(tmux_pid "${name}")"
    printf '%-14s running pid=%-8s port=%-5s %s (tmux:%s)\n' "${name}" "${pid:-unknown}" "${port}" "${url}" "$(session_name "${name}")"
  elif [[ -n "${pid}" ]] && pid_is_running "${pid}"; then
    printf '%-14s running pid=%-8s port=%-5s %s\n' "${name}" "${pid}" "${port}" "${url}"
  elif [[ -n "${listener}" ]]; then
    printf '%-14s running pid=%-8s port=%-5s %s (external/no pid file)\n' "${name}" "${listener}" "${port}" "${url}"
  else
    printf '%-14s stopped             port=%-5s %s\n' "${name}" "${port}" "${url}"
  fi
}

print_unix_service() {
  local name="$1"
  local socket="$2"
  local url="$3"
  local pid
  pid="$(read_pid "${name}")"

  if tmux_available && tmux_is_running "${name}"; then
    pid="$(tmux_pid "${name}")"
    printf '%-14s running pid=%-8s socket=%s %s (tmux:%s)\n' "${name}" "${pid:-unknown}" "${socket}" "${url}" "$(session_name "${name}")"
  elif [[ -n "${pid}" ]] && pid_is_running "${pid}"; then
    printf '%-14s running pid=%-8s socket=%s %s\n' "${name}" "${pid}" "${socket}" "${url}"
  elif socket_is_ready "${socket}"; then
    printf '%-14s running             socket=%s %s (external/no pid file)\n' "${name}" "${socket}" "${url}"
  else
    printf '%-14s stopped             socket=%s %s\n' "${name}" "${socket}" "${url}"
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
  listener="$(port_pid "${port}")"
  if tmux_available && tmux_is_running "${name}"; then
    if [[ -z "${listener}" ]]; then
      echo "${name} is running in tmux session $(session_name "${name}") but port ${port} is not listening"
      return 1
    fi
    echo "${name} already running in tmux session $(session_name "${name}")"
    return 0
  elif [[ -n "${pid}" ]] && pid_is_running "${pid}"; then
    if [[ -z "${listener}" ]]; then
      echo "${name} is running with pid ${pid} but port ${port} is not listening"
      return 1
    fi
    echo "${name} already running with pid ${pid}"
    return 0
  fi

  if [[ -n "${listener}" ]]; then
    echo "${name} port ${port} is already used by pid ${listener}; treating it as running"
    return 0
  fi

  pid_path="$(pid_file "${name}")"
  log_path="$(log_file "${name}")"
  echo "Starting ${name} on port ${port}; log: ${log_path}"
  if tmux_available; then
    local session
    local run_path
    local run_path_quoted
    local log_path_quoted
    session="$(session_name "${name}")"
    run_path="${STATE_DIR}/${name}.run.sh"
    {
      printf '#!/usr/bin/env bash\n'
      printf 'set -euo pipefail\n'
      printf 'cd %q\n' "${cwd}"
      printf '%s\n' "${command}"
    } > "${run_path}"
    chmod +x "${run_path}"
    printf -v run_path_quoted '%q' "${run_path}"
    printf -v log_path_quoted '%q' "${log_path}"
    tmux new-session -d -s "${session}" -c "${cwd}" "bash ${run_path_quoted} >> ${log_path_quoted} 2>&1"
    tmux_pid "${name}" > "${pid_path}"
  else
    (
      cd "${cwd}"
      nohup bash -lc "${command}" > "${log_path}" 2>&1 &
      echo "$!" > "${pid_path}"
    )
  fi

  sleep 1
  for _ in {1..30}; do
    listener="$(port_pid "${port}")"
    if [[ -n "${listener}" ]]; then
      return 0
    fi
    if tmux_available && ! tmux_is_running "${name}"; then
      break
    fi
    sleep 0.2
  done

  pid="$(read_pid "${name}")"
  if ! pid_is_running "${pid}"; then
    echo "${name} failed to start; last log lines:"
    tail -n 40 "${log_path}" 2>/dev/null || true
    return 1
  fi

  echo "${name} started but port ${port} is not listening yet; last log lines:"
  tail -n 40 "${log_path}" 2>/dev/null || true
  return 1
}

start_process_unix() {
  local name="$1"
  local socket="$2"
  local cwd="$3"
  local command="$4"
  local pid
  local pid_path
  local log_path

  pid="$(read_pid "${name}")"
  if tmux_available && tmux_is_running "${name}"; then
    echo "${name} already running in tmux session $(session_name "${name}")"
    return 0
  elif [[ -n "${pid}" ]] && pid_is_running "${pid}"; then
    echo "${name} already running with pid ${pid}"
    return 0
  fi

  rm -f "${socket}"
  pid_path="$(pid_file "${name}")"
  log_path="$(log_file "${name}")"
  echo "Starting ${name} on unix socket ${socket}; log: ${log_path}"
  if tmux_available; then
    local session
    local run_path
    local run_path_quoted
    local log_path_quoted
    session="$(session_name "${name}")"
    run_path="${STATE_DIR}/${name}.run.sh"
    {
      printf '#!/usr/bin/env bash\n'
      printf 'set -euo pipefail\n'
      printf 'cd %q\n' "${cwd}"
      printf '%s\n' "${command}"
    } > "${run_path}"
    chmod +x "${run_path}"
    printf -v run_path_quoted '%q' "${run_path}"
    printf -v log_path_quoted '%q' "${log_path}"
    tmux new-session -d -s "${session}" -c "${cwd}" "bash ${run_path_quoted} >> ${log_path_quoted} 2>&1"
    tmux_pid "${name}" > "${pid_path}"
  else
    (
      cd "${cwd}"
      nohup bash -lc "${command}" > "${log_path}" 2>&1 &
      echo "$!" > "${pid_path}"
    )
  fi

  sleep 1
  for _ in {1..30}; do
    if socket_is_ready "${socket}"; then
      return 0
    fi
    if tmux_available && ! tmux_is_running "${name}"; then
      break
    fi
    sleep 0.2
  done

  pid="$(read_pid "${name}")"
  if ! pid_is_running "${pid}"; then
    echo "${name} failed to start; last log lines:"
    tail -n 40 "${log_path}" 2>/dev/null || true
    return 1
  fi

  echo "${name} started but socket ${socket} is not ready yet; last log lines:"
  tail -n 40 "${log_path}" 2>/dev/null || true
  return 1
}
