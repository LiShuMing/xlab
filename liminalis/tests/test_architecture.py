"""Architecture guardrails for the unified storage boundary."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_http_routers_use_shared_business_storage_boundary() -> None:
    router_paths = [
        "backend/routers/admin.py",
        "backend/routers/ego.py",
        "backend/routers/invest.py",
        "backend/routers/radar.py",
        "backend/routers/wechat.py",
    ]

    for path in router_paths:
        source = _read(path)
        assert "from backend.db.engine import get_session" not in source, path
        assert "Depends(get_session)" not in source, path
        assert "get_session_factory" not in source, path


def test_db_engine_does_not_expose_fastapi_session_dependency() -> None:
    source = _read("backend/db/engine.py")
    assert "def get_session(" not in source


def test_domain_services_do_not_control_transactions() -> None:
    service_paths = [
        "backend/services/ego_service.py",
        "backend/services/invest_service.py",
        "backend/services/radar_admin_service.py",
        "backend/services/wechat_service.py",
        "backend/ego/auth_deps.py",
        "backend/radar/tasks.py",
        "backend/radar/cli.py",
        "backend/radar/generate_summary.py",
        "backend/invest/cli.py",
        "backend/invest/scheduler/daily_job.py",
        "backend/invest/scheduler/worker.py",
        "backend/invest/notifier/email_sender.py",
        "scripts/init_postgres.py",
        "scripts/sync_py_radar_feed.py",
    ]

    for path in service_paths:
        source = _read(path)
        assert ".commit(" not in source, path
        assert ".rollback(" not in source, path


def test_http_runtime_does_not_import_legacy_storage() -> None:
    runtime_paths = [
        "backend/routers/admin.py",
        "backend/routers/ego.py",
        "backend/routers/invest.py",
        "backend/routers/radar.py",
        "backend/routers/wechat.py",
        "backend/services/invest_service.py",
        "backend/services/radar_admin_service.py",
        "backend/radar/tasks.py",
        "backend/radar/cli.py",
        "backend/radar/generate_summary.py",
        "backend/invest/cli.py",
        "backend/invest/scheduler/daily_job.py",
        "backend/invest/scheduler/worker.py",
        "backend/invest/notifier/email_sender.py",
        "scripts/init_postgres.py",
        "scripts/sync_py_radar_feed.py",
    ]
    forbidden_imports = [
        "backend.invest.storage",
        "backend.radar.storage",
        "DuckDBStore",
        "IngestionJobStore",
    ]

    for path in runtime_paths:
        source = _read(path)
        for forbidden in forbidden_imports:
            assert forbidden not in source, f"{path} imports legacy storage marker {forbidden}"


def test_runtime_code_does_not_use_ambiguous_storage_backend_switch() -> None:
    runtime_paths = [
        "backend/routers/invest.py",
        "backend/routers/radar.py",
        "backend/services/radar_service.py",
        "backend/_shared/storage.py",
    ]

    for path in runtime_paths:
        assert "storage_backend" not in _read(path), path


def test_domain_code_uses_shared_http_library() -> None:
    allowed = {
        "backend/_shared/http.py",
        "backend/_shared/llm.py",
        "backend/_shared/web_crawler.py",
        "backend/_shared/web_fetcher.py",
    }
    for path in (ROOT / "backend").rglob("*.py"):
        rel = path.relative_to(ROOT).as_posix()
        if rel in allowed or "__pycache__" in rel:
            continue
        source = path.read_text(encoding="utf-8")
        assert "import httpx" not in source, rel
        assert "from httpx" not in source, rel


def test_session_signing_uses_shared_auth_helpers() -> None:
    allowed = {"backend/_shared/auth.py"}
    for path in (ROOT / "backend").rglob("*.py"):
        rel = path.relative_to(ROOT).as_posix()
        if rel in allowed or "__pycache__" in rel:
            continue
        source = path.read_text(encoding="utf-8")
        assert "URLSafeSerializer" not in source, rel
        assert "URLSafeTimedSerializer" not in source, rel


def test_runtime_env_mutation_is_centralized() -> None:
    allowed = {
        "backend/_shared/ml_runtime.py",
        "backend/ego/cli/ui.py",
        "backend/ego/test_memory_store.py",
    }
    for path in (ROOT / "backend").rglob("*.py"):
        rel = path.relative_to(ROOT).as_posix()
        if rel in allowed or "__pycache__" in rel:
            continue
        source = path.read_text(encoding="utf-8")
        assert "os.environ" not in source, rel
        assert "os.getenv" not in source, rel


def test_services_do_not_raise_fastapi_http_exceptions() -> None:
    for path in (ROOT / "backend" / "services").rglob("*.py"):
        rel = path.relative_to(ROOT).as_posix()
        source = path.read_text(encoding="utf-8")
        assert "from fastapi" not in source, rel
        assert "HTTPException" not in source, rel


def test_collectors_use_shared_http_stack() -> None:
    for path in (ROOT / "backend" / "invest" / "modules" / "data_collector").rglob("*.py"):
        rel = path.relative_to(ROOT).as_posix()
        source = path.read_text(encoding="utf-8")
        assert "import aiohttp" not in source, rel
        assert "from aiohttp" not in source, rel


def test_invest_cli_uses_single_click_entrypoint() -> None:
    source = _read("backend/invest/cli.py")
    assert "import argparse" not in source
    assert "ArgumentParser" not in source
    assert "@click.group()" in source


def test_runtime_services_use_runtime_settings_not_domain_compat_config() -> None:
    checked_dirs = [
        ROOT / "backend" / "services",
        ROOT / "backend" / "routers",
    ]
    forbidden = [
        "backend.radar.config",
        "backend.ego.config",
    ]
    for directory in checked_dirs:
        for path in directory.rglob("*.py"):
            rel = path.relative_to(ROOT).as_posix()
            source = path.read_text(encoding="utf-8")
            for marker in forbidden:
                assert marker not in source, f"{rel} imports compatibility config {marker}"


def test_runtime_code_uses_shared_time_helpers_for_utc_api_timestamps() -> None:
    guarded_paths = [
        "backend/routers/health.py",
        "backend/services/ego_service.py",
        "backend/radar/tasks.py",
        "backend/invest/service.py",
        "backend/invest/scheduler/worker.py",
    ]
    for path in guarded_paths:
        source = _read(path)
        assert "datetime.now(UTC)" not in source, path
        assert 'strftime("%Y-%m-%dT%H:%M:%SZ")' not in source, path
