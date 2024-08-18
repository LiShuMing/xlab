"""Tests for src/server.py."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.server import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


class TestReportsEndpoint:
    def test_returns_list(self, client: TestClient) -> None:
        with patch("src.server.list_reports", return_value=[]) as mock_list:
            response = client.get("/reports")
        assert response.status_code == 200
        data = response.json()
        assert "reports" in data

    def test_returns_reports(self, client: TestClient) -> None:
        sample = [{"product": "Claude", "filename": "claude_20250101_120000.md"}]
        with patch("src.server.list_reports", return_value=sample):
            response = client.get("/reports")
        assert response.status_code == 200
        assert response.json()["reports"] == sample


class TestRefreshEndpoint:
    def test_refresh_success(self, client: TestClient) -> None:
        with (
            patch(
                "src.server.generate_report_async",
                new=AsyncMock(return_value="# Report"),
            ),
            patch("src.server.save_report", return_value=Path("reports/test.md")),
            patch("src.server._build_mkdocs"),
        ):
            response = client.get("/refresh?product=Claude+API")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_refresh_api_error(self, client: TestClient) -> None:
        from src.exceptions import ResearcherError

        with patch(
            "src.server.generate_report_async",
            new=AsyncMock(side_effect=ResearcherError("API down")),
        ):
            response = client.get("/refresh?product=Claude+API")
        assert response.status_code == 502

    def test_refresh_missing_product(self, client: TestClient) -> None:
        response = client.get("/refresh")
        assert response.status_code == 422

    def test_mkdocs_build_error(self, client: TestClient) -> None:
        from src.exceptions import MkDocsError

        with (
            patch(
                "src.server.generate_report_async",
                new=AsyncMock(return_value="# Report"),
            ),
            patch("src.server.save_report", return_value=Path("reports/test.md")),
            patch("src.server._build_mkdocs", side_effect=MkDocsError("build failed")),
        ):
            response = client.get("/refresh?product=Claude+API")
        assert response.status_code == 500
