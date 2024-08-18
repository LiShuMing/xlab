"""Guard against unintended API contract drift.

The committed docs/openapi.json is the source of truth. Regenerate it with
`python -m scripts.dump_openapi` whenever you intentionally change a route.
"""

from pathlib import Path

from scripts.dump_openapi import SNAPSHOT_PATH, render_schema


def test_openapi_snapshot_matches() -> None:
    assert SNAPSHOT_PATH.exists(), (
        f"Missing {SNAPSHOT_PATH}; run `python -m scripts.dump_openapi` to create it."
    )
    expected = SNAPSHOT_PATH.read_text(encoding="utf-8")
    actual = render_schema()
    assert actual == expected, (
        "OpenAPI schema has drifted from docs/openapi.json. "
        "If this change is intentional, regenerate with: "
        "python -m scripts.dump_openapi"
    )


def test_snapshot_path_inside_repo() -> None:
    # Cheap regression check: prevent the snapshot escaping the repo via path
    # manipulation if anyone refactors render_schema().
    repo_root = Path(__file__).resolve().parents[1]
    assert SNAPSHOT_PATH.is_relative_to(repo_root)
