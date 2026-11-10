#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
case "${1:-help}" in
    setup) uv sync --locked ;;
    test)
        uv run --locked pytest -q
        uv run --locked ruff check .
        uv run --locked ruff format --check .
        ;;
    help)
        printf '%s\n' './lab.sh setup | test | doctor | smoke | data | fetch | parity'
        printf '%s\n' './lab.sh run --config configs/base.yaml'
        printf '%s\n' './lab.sh report RUN_DIRECTORY'
        ;;
    *) uv run --locked reasoning-lab "$@" ;;
esac
