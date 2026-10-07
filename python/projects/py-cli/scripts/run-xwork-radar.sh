#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python_bin="${PYTHON_BIN:-${project_dir}/.venv/bin/python}"
config="${RADAR_CONFIG:-${project_dir}/examples/radar-xwork.toml}"

if [[ ! -x "${python_bin}" ]]; then
    echo "radar: Python environment not found: ${python_bin}" >&2
    echo "radar: create ${project_dir}/.venv with Python 3.13+ and install py-cli" >&2
    exit 2
fi

# Set this when an expired environment token shadows gh's authenticated keyring.
if [[ "${RADAR_CLEAR_GITHUB_TOKENS:-0}" == "1" ]]; then
    unset GH_TOKEN GITHUB_TOKEN
fi

cd "${project_dir}"
exec "${python_bin}" -m py_cli radar weekly \
    --config "${config}" \
    --previous-week \
    "$@"
