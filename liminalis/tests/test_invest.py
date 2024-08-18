"""Invest router smoke tests — focuses on error envelopes."""

from fastapi.testclient import TestClient


def test_missing_stock_returns_400(client: TestClient) -> None:
    response = client.post("/api/invest/analyze-stock", json={})
    assert response.status_code == 400
    assert response.json() == {"detail": "stock is required"}


def test_unhandled_exception_does_not_leak_message(
    monkeypatch,
    client: TestClient,  # noqa: ANN001
) -> None:
    secret_marker = "SECRET_DB_PASSWORD=hunter2"

    async def boom(*_args, **_kwargs):
        raise RuntimeError(secret_marker)

    monkeypatch.setattr("backend.routers.invest.analyze_stock", boom)

    response = client.post(
        "/api/invest/analyze-stock",
        json={"stock": "AAPL", "use_cache": False},
    )
    assert response.status_code == 500
    body = response.json()
    assert body["detail"] == "internal server error"
    assert "trace_id" in body and len(body["trace_id"]) == 12
    assert secret_marker not in response.text
