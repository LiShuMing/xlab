#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=dev-common.sh
source "${SCRIPT_DIR}/dev-common.sh"

load_dev_env
ensure_node_deps "${PROJECT_ROOT}"
ensure_venv "${PROJECT_ROOT}" "${PYTHON_BIN}" -m pip install -e .

(cd "${PROJECT_ROOT}" && VITE_LLM_WIKI_URL="http://127.0.0.1:${LLM_WIKI_PORT}/" npm run build)
(cd "${PROJECT_ROOT}" && . "${VENV_ACTIVATE}" && exec python -m backend.app)
