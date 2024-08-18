#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=dev-common.sh
source "${SCRIPT_DIR}/dev-common.sh"

load_dev_env

echo "Process status"
if [[ "${START_LIMINALIS}" == "1" ]]; then
  print_service "liminalis" "${LIMINALIS_PORT}" "http://localhost:${LIMINALIS_PORT}/"
fi
if [[ "${START_LIMINALIS_API}" == "1" ]]; then
  print_service "liminalis-api" "${LIMINALIS_API_PORT}" "http://localhost:${LIMINALIS_API_PORT}/health"
fi
if [[ "${START_LLM_WIKI}" == "1" ]]; then
  print_service "llm-wiki" "${LLM_WIKI_PORT}" "http://localhost:${LLM_WIKI_PORT}/"
fi

echo
echo "Health checks"
if [[ "${START_LIMINALIS}" == "1" ]]; then
  if http_ok "http://localhost:${LIMINALIS_PORT}/"; then
    echo "ok   liminalis"
  else
    echo "fail liminalis"
  fi
fi

if [[ "${START_LIMINALIS_API}" == "1" ]]; then
  if http_ok "http://localhost:${LIMINALIS_API_PORT}/health"; then
    echo "ok   liminalis-api"
  else
    echo "fail liminalis-api"
  fi
fi

if [[ "${START_LLM_WIKI}" == "1" ]]; then
  if http_ok "http://localhost:${LLM_WIKI_PORT}/"; then
    echo "ok   llm-wiki"
  else
    echo "fail llm-wiki"
  fi
fi

echo
echo "Logs: ${LOG_DIR}"
echo "PID files: ${STATE_DIR}"
echo "Python venv: ${VENV_DIR}"
[[ "${START_LLM_WIKI}" == "1" ]] && echo "llm-wiki root: ${LLM_WIKI_ROOT}"
