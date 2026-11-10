#!/usr/bin/env bash
set -euo pipefail
umask 077
lab_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -z "${VLLM_PYTHON:-}" || ! -x "$VLLM_PYTHON" ]]; then
  echo 'Set VLLM_PYTHON to the existing vLLM environment Python executable.' >&2
  exit 1
fi
export PYTHONPATH="$lab_dir/src${PYTHONPATH:+:$PYTHONPATH}"
export LLM_OBSERVE_INSTRUMENT="${LLM_OBSERVE_INSTRUMENT:-1}"
LLM_OBSERVE_PREFLIGHT=1 "$VLLM_PYTHON" -m llm_observe.vllm_launch --check "$@"
exec "$VLLM_PYTHON" -m llm_observe.vllm_launch "$@"
