#!/usr/bin/env bash
# Compatibility entry point: use the topic's explicit local-dependency build.
set -euo pipefail
exec bash "$(dirname "${BASH_SOURCE[0]}")/../scripts/build.sh"
