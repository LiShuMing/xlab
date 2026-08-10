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

start_liminalis() {
  ensure_node_deps "${PROJECT_ROOT}" || return 1
  start_process \
    "liminalis" \
    "${LIMINALIS_PORT}" \
    "${PROJECT_ROOT}" \
    "VITE_LLM_WIKI_URL='/llm-wiki/' exec npm run dev -- --host 0.0.0.0 --port ${LIMINALIS_PORT}"
}

start_liminalis_api() {
  ensure_venv "${PROJECT_ROOT}" "${PYTHON_BIN}" -m pip install -e . || return 1
  start_process \
    "liminalis-api" \
    "${LIMINALIS_API_PORT}" \
    "${PROJECT_ROOT}" \
    "export LLM_WIKI_SOCKET='${LLM_WIKI_SOCKET}'; . '${VENV_ACTIVATE}' && exec python -m uvicorn backend.app:app --host 127.0.0.1 --port ${LIMINALIS_API_PORT}"
}

start_llm_wiki() {
  if [[ -z "${LLM_WIKI_ROOT}" || ! -d "${LLM_WIKI_ROOT}" ]]; then
    echo "llm-wiki root not found: ${LLM_WIKI_ROOT:-<empty>}"
    return 1
  fi

  start_process_unix \
    "llm-wiki" \
    "${LLM_WIKI_SOCKET}" \
    "${LLM_WIKI_ROOT}" \
    "CTX_WEB_UNIX_SOCKET='${LLM_WIKI_SOCKET}' exec make web WEB_PROVIDER='${LLM_WIKI_PROVIDER}' DEMO_DATA='${LLM_WIKI_DATA}'"
}

[[ "${START_LIMINALIS_API}" == "1" ]] && run_step "liminalis-api" start_liminalis_api
[[ "${START_LLM_WIKI}" == "1" ]] && run_step "llm-wiki" start_llm_wiki
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
if [[ "${START_LIMINALIS}" == "1" ]]; then
  echo "Started. Open http://localhost:${LIMINALIS_PORT}/"
else
  echo "Started. Open http://localhost:${LIMINALIS_API_PORT}/"
fi
