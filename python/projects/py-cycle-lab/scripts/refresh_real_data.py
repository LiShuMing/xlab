#!/usr/bin/env python3
"""Refresh real market data into the local DuckDB cache."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from cycle_lab.data.store import init_db, refresh_real_data  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", default="20100101", help="AKShare start date, e.g. 20100101")
    args = parser.parse_args()
    init_db()
    result = refresh_real_data(start_date=args.start_date)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result.get("ok"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
