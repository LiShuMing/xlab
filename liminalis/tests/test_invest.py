"""Invest router smoke tests — focuses on error envelopes."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi.testclient import TestClient


@asynccontextmanager
async def _fake_business_uow() -> AsyncIterator[object]:
    yield object()


def _configured_settings():
    from backend.settings import Settings

    return Settings(
        pgsql_host="localhost",
        pgsql_user="user",
        pgsql_password="password",
        _env_file=None,
    )


def test_missing_stock_returns_400(client: TestClient) -> None:
    response = client.post("/api/invest/analyze-stock", json={})
    assert response.status_code == 400
    assert response.json() == {"detail": "stock is required"}


def test_unhandled_exception_does_not_leak_message(
    monkeypatch,
    client: TestClient,  # noqa: ANN001
) -> None:
    from backend.settings import get_settings

    secret_marker = "SECRET_DB_PASSWORD=hunter2"

    async def boom(*_args, **_kwargs):
        raise RuntimeError(secret_marker)

    monkeypatch.setattr("backend.routers.invest.business_uow", _fake_business_uow)
    monkeypatch.setattr("backend.routers.invest.analyze_stock", boom)
    client.app.dependency_overrides[get_settings] = _configured_settings

    try:
        response = client.post(
            "/api/invest/analyze-stock",
            json={"stock": "AAPL", "use_cache": False},
        )
    finally:
        client.app.dependency_overrides.clear()
    assert response.status_code == 500
    body = response.json()
    assert body["detail"] == "internal server error"
    assert "trace_id" in body and len(body["trace_id"]) == 12
    assert secret_marker not in response.text


def test_invest_dashboard_routes_delegate_to_service(monkeypatch, client: TestClient) -> None:  # noqa: ANN001
    from backend.settings import get_settings

    async def fake_list_stocks(_session, _settings):
        return {"stocks": [{"code": "AAPL"}]}

    async def fake_list_reports(_session, _settings):
        return {"reports": [{"code": "AAPL"}]}

    async def fake_get_report(_session, _settings, stock_code):
        return {"report": {"code": stock_code}}

    async def fake_delete_reports(_session, _settings):
        return {"success": True, "deleted": 2}

    monkeypatch.setattr(
        "backend.routers.invest.list_stocks",
        fake_list_stocks,
    )
    monkeypatch.setattr(
        "backend.routers.invest.list_reports",
        fake_list_reports,
    )
    monkeypatch.setattr(
        "backend.routers.invest.get_invest_report",
        fake_get_report,
    )
    monkeypatch.setattr(
        "backend.routers.invest.delete_reports",
        fake_delete_reports,
    )
    monkeypatch.setattr("backend.routers.invest.business_uow", _fake_business_uow)
    client.app.dependency_overrides[get_settings] = _configured_settings

    try:
        assert client.get("/api/invest/stocks").json() == {"stocks": [{"code": "AAPL"}]}
        assert client.get("/api/invest/reports").json() == {"reports": [{"code": "AAPL"}]}
        assert client.get("/api/invest/report/AAPL").json() == {"report": {"code": "AAPL"}}
        assert client.delete("/api/invest/reports").json() == {"success": True, "deleted": 2}
    finally:
        client.app.dependency_overrides.clear()


def test_invest_read_routes_do_not_require_business_database(client: TestClient) -> None:
    from backend.settings import Settings, get_settings

    client.app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None)
    try:
        assert client.get("/api/invest/stocks").status_code == 200
        assert client.get("/api/invest/reports").json() == {"reports": []}
        assert client.get("/api/invest/report/AAPL").json() == {"error": "Report not found"}
        assert client.delete("/api/invest/reports").json() == {"success": True, "deleted": 0}
    finally:
        client.app.dependency_overrides.clear()


def test_invest_read_routes_fallback_when_business_database_is_not_ready(
    monkeypatch,
    client: TestClient,  # noqa: ANN001
) -> None:
    from backend.settings import get_settings

    @asynccontextmanager
    async def broken_business_uow() -> AsyncIterator[object]:
        raise RuntimeError("schema not ready")
        yield object()

    monkeypatch.setattr("backend.routers.invest.business_uow", broken_business_uow)
    client.app.dependency_overrides[get_settings] = _configured_settings
    try:
        assert client.get("/api/invest/stocks").status_code == 200
        assert client.get("/api/invest/reports").json() == {"reports": []}
        assert client.get("/api/invest/report/AAPL").json() == {"error": "Report not found"}
        assert client.delete("/api/invest/reports").json() == {"success": True, "deleted": 0}
    finally:
        client.app.dependency_overrides.clear()


def test_invest_read_routes_can_disable_business_read_fallback(
    monkeypatch,
    client: TestClient,  # noqa: ANN001
) -> None:
    from backend.settings import Settings, get_settings

    @asynccontextmanager
    async def broken_business_uow() -> AsyncIterator[object]:
        raise RuntimeError("schema not ready")
        yield object()

    monkeypatch.setattr("backend.routers.invest.business_uow", broken_business_uow)
    client.app.dependency_overrides[get_settings] = lambda: Settings(
        pgsql_host="localhost",
        pgsql_user="user",
        pgsql_password="password",
        allow_business_read_fallback=False,
        _env_file=None,
    )
    try:
        response = client.get("/api/invest/stocks")
    finally:
        client.app.dependency_overrides.clear()

    assert response.status_code == 500


def test_invest_analyze_requires_business_database(client: TestClient) -> None:
    from backend.settings import Settings, get_settings

    client.app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None)
    try:
        response = client.post("/api/invest/analyze-stock", json={"stock": "AAPL"})
    finally:
        client.app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {"detail": "business database is not configured"}


def test_format_dashboard_report_handles_legacy_report_shape() -> None:
    from backend.services.invest_service import format_dashboard_report

    report = format_dashboard_report(
        {
            "stock_code": "AAPL",
            "stock_name": "Apple",
            "rating": "BUY",
            "confidence": "HIGH",
            "target_price": 210,
            "summary": "Strong moat.",
            "raw_data": {
                "query_stock_price": {"current_price": 190, "change": 1.2, "change_percent": 0.6},
                "query_financial_metrics": {"pe_ratio": 28, "pb_ratio": 12, "market_cap": "3T"},
            },
            "sections": [{"title": "Technical Picture", "content": "Uptrend"}],
            "bull_case": "Growth",
        }
    )

    assert report["code"] == "AAPL"
    assert report["name"] == "Apple"
    assert report["price"] == 190
    assert report["rating"] == "buy"
    assert report["confidence"] == "high"
    assert report["metrics"]["pe"] == 28
    assert report["analysis"]["technical"] == "Uptrend"
    assert report["scenarios"]["bull"] == "Growth"


def test_draft_thesis_from_report_extracts_structured_fields() -> None:
    from backend.invest.workspace import draft_thesis_from_report

    draft = draft_thesis_from_report(
        {
            "stock_code": "AAPL",
            "stock_name": "Apple",
            "summary": "Strong ecosystem and cash flow.",
            "rating": "Buy",
            "confidence": "High",
            "target_price": 210,
            "sections": [
                {"title": "公司概览", "content": "Apple monetizes hardware, services and ecosystem lock-in."},
                {"title": "财务质量", "content": "High margins and recurring services revenue."},
                {"title": "风险", "content": "Hardware cycles and regulation."},
            ],
            "bear_case": "Growth slows.",
        }
    )

    assert draft["stock_code"] == "AAPL"
    assert draft["stock_name"] == "Apple"
    assert draft["status"] == "researching"
    assert "Strong ecosystem" in draft["core_thesis"]
    assert "High margins" in draft["supporting_evidence"][0]
    assert "Hardware cycles" in draft["counter_evidence"][0]
    assert draft["confidence"] == "high"


def test_invest_workspace_routes_delegate_to_services(monkeypatch, client: TestClient) -> None:  # noqa: ANN001
    from backend.settings import get_settings

    async def fake_snapshot(_session, stock_code):
        return {"thesis": {"stock_code": stock_code}, "watch_items": [], "journal_entries": [], "reviews": []}

    class FakeThesis:
        id = 7
        stock_code = "AAPL"
        stock_name = "Apple"
        status = "watchlist"
        core_thesis = "Long-term thesis"
        supporting_evidence = []
        counter_evidence = []
        disconfirming_signals = []
        margin_of_safety = ""
        expected_holding_period = ""
        confidence = "medium"
        source_report_id = None
        created_at = None
        updated_at = None

    async def fake_upsert(_session, **_kwargs):
        return FakeThesis()

    async def fake_ensure(_session, _thesis):
        return None

    def fake_serialize(row):
        return {"id": row.id, "stock_code": row.stock_code, "core_thesis": row.core_thesis}

    monkeypatch.setattr("backend.routers.invest.business_uow", _fake_business_uow)
    monkeypatch.setattr("backend.routers.invest.get_workspace_snapshot", fake_snapshot)
    monkeypatch.setattr("backend.routers.invest.invest_workspace.upsert_thesis", fake_upsert)
    monkeypatch.setattr("backend.routers.invest.invest_workspace.ensure_default_watch_items", fake_ensure)
    monkeypatch.setattr("backend.routers.invest.invest_workspace.serialize_thesis", fake_serialize)
    client.app.dependency_overrides[get_settings] = _configured_settings

    try:
        workspace = client.get("/api/invest/workspace/AAPL")
        thesis = client.put(
            "/api/invest/thesis/AAPL",
            json={"core_thesis": "Long-term thesis", "confidence": "medium"},
        )
    finally:
        client.app.dependency_overrides.clear()

    assert workspace.status_code == 200
    assert workspace.json()["thesis"]["stock_code"] == "AAPL"
    assert thesis.status_code == 200
    assert thesis.json()["thesis"] == {"id": 7, "stock_code": "AAPL", "core_thesis": "Long-term thesis"}
