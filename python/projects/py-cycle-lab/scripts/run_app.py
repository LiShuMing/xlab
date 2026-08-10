#!/usr/bin/env python3
"""Run the LongCycle Flask prototype."""

from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from cycle_lab.app import create_app  # noqa: E402


def main() -> None:
    host = os.getenv("LONGCYCLE_HOST", "127.0.0.1")
    port = int(os.getenv("LONGCYCLE_PORT", "19021"))
    debug = os.getenv("LONGCYCLE_DEBUG", "0") == "1"
    create_app().run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    main()
