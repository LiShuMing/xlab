#!/usr/bin/env bash
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=dev-common.sh
source "${SCRIPT_DIR}/dev-common.sh"

load_dev_env

failures=()

run_step() {
  local name="$1"
  shift
  if ! "$@"; then
    failures+=("${name}")
  fi
}

require_dir() {
  local name="$1"
  local dir="$2"
  if [[ ! -d "${dir}" ]]; then
    echo "${name} directory does not exist: ${dir}"
    return 1
  fi
}

start_radar() {
  require_dir "py-radar" "${RADAR_DIR}" || return 1
  ensure_venv "${RADAR_DIR}" "${PYTHON_BIN}" -m pip install -e . || return 1
  start_process \
    "py-radar" \
    "${RADAR_PORT}" \
    "${RADAR_DIR}" \
    ". '${VENV_ACTIVATE}' && exec python -m dbradar serve --host 127.0.0.1 --port ${RADAR_PORT}"
}

start_invest() {
  require_dir "py-invest" "${INVEST_DIR}" || return 1
  ensure_venv "${INVEST_DIR}" "${PYTHON_BIN}" -m pip install -e . || return 1
  start_process \
    "py-invest" \
    "${INVEST_PORT}" \
    "${INVEST_DIR}" \
    ". '${VENV_ACTIVATE}' && exec python web/server.py ${INVEST_PORT}"
}

start_ego_api() {
  require_dir "py-ego backend" "${EGO_API_DIR}" || return 1
  ensure_venv "${EGO_API_DIR}" "${PYTHON_BIN}" -m pip install -r requirements.txt || return 1
  start_process \
    "py-ego-api" \
    "${EGO_API_PORT}" \
    "${EGO_API_DIR}" \
    ". '${VENV_ACTIVATE}' && DATABASE_URL='${DATABASE_URL:-sqlite+aiosqlite:///./pyego_local.db}' REDIS_URL='${REDIS_URL:-memory://}' exec python -m uvicorn app.main:app --host 127.0.0.1 --port ${EGO_API_PORT}"
}

start_ego_h5() {
  require_dir "py-ego H5" "${EGO_H5_DIR}" || return 1
  ensure_node_deps "${EGO_H5_DIR}" || return 1
  start_process \
    "py-ego-h5" \
    "${EGO_H5_PORT}" \
    "${EGO_H5_DIR}" \
    "exec npm run dev:h5 -- --host 127.0.0.1 --port ${EGO_H5_PORT}"
}

start_liminalis() {
  ensure_node_deps "${PROJECT_ROOT}" || return 1
  start_process \
    "liminalis" \
    "${LIMINALIS_PORT}" \
    "${PROJECT_ROOT}" \
    "exec npm run dev -- --host 0.0.0.0 --port ${LIMINALIS_PORT}"
}

[[ "${START_RADAR}" == "1" ]] && run_step "py-radar" start_radar
[[ "${START_INVEST}" == "1" ]] && run_step "py-invest" start_invest
[[ "${START_EGO_API}" == "1" ]] && run_step "py-ego-api" start_ego_api
[[ "${START_EGO_H5}" == "1" ]] && run_step "py-ego-h5" start_ego_h5
[[ "${START_LIMINALIS}" == "1" ]] && run_step "liminalis" start_liminalis

echo
"${SCRIPT_DIR}/check.sh"

if (( ${#failures[@]} > 0 )); then
  echo
  echo "Failed services: ${failures[*]}"
  echo "Inspect logs in ${LOG_DIR}"
  exit 1
fi

echo
echo "Started. Open http://localhost:${LIMINALIS_PORT}/"
