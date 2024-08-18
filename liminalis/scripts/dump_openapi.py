"""Dump the FastAPI OpenAPI schema to docs/openapi.json.

Usage:
    python -m scripts.dump_openapi              # write to docs/openapi.json
    python -m scripts.dump_openapi --check      # exit non-zero if file is stale

The committed snapshot is the source of truth for API contract diffs in CI.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from backend.app import create_app
from backend.settings import get_settings

SNAPSHOT_PATH = Path(__file__).resolve().parents[1] / "docs" / "openapi.json"


def render_schema() -> str:
    get_settings.cache_clear()
    schema = create_app().openapi()
    return json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if snapshot is stale")
    args = parser.parse_args()

    rendered = render_schema()
    if args.check:
        if not SNAPSHOT_PATH.exists() or SNAPSHOT_PATH.read_text(encoding="utf-8") != rendered:
            print(
                "OpenAPI snapshot is stale. Regenerate with: python -m scripts.dump_openapi", file=sys.stderr
            )
            return 1
        print(f"OpenAPI snapshot up to date: {SNAPSHOT_PATH}")
        return 0

    SNAPSHOT_PATH.write_text(rendered, encoding="utf-8")
    print(f"Wrote {SNAPSHOT_PATH} ({len(rendered)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
