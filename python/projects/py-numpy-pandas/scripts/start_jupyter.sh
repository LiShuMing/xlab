#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${PROJECT_DIR}"

if [[ ! -d .venv ]]; then
    python3 -m venv .venv
fi

source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m ipykernel install --user --name xlab-numpy-pandas --display-name "xlab numpy/pandas"

exec jupyter lab --notebook-dir="${PROJECT_DIR}" --ip=127.0.0.1
