from __future__ import annotations

from pathlib import Path


def test_business_modules_do_not_call_llm_http_endpoint_directly() -> None:
    project_root = Path(__file__).resolve().parents[1]
    backend_root = project_root / "backend"
    checked_roots = [
        backend_root / "ego",
        backend_root / "invest",
        backend_root / "radar",
    ]
    forbidden = ("/chat/completions", "chat.completions")

    offenders: list[str] = []
    for root in checked_roots:
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if any(pattern in text for pattern in forbidden):
                offenders.append(str(path.relative_to(project_root)))

    assert offenders == []
