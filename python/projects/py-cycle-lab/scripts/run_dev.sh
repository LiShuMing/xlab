#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-}"

if [[ -z "${PYTHON_BIN}" ]]; then
  if [[ -x "${HOME}/.pyenv/shims/python3" ]]; then
    PYTHON_BIN="${HOME}/.pyenv/shims/python3"
  else
    PYTHON_BIN="python3"
  fi
fi

cd "${ROOT}"
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:${PYTHONPATH}}"
exec "${PYTHON_BIN}" scripts/run_app.py
