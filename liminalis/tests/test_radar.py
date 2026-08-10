"""Radar route tests."""

from pathlib import Path

from fastapi.testclient import TestClient


def test_radar_items_falls_back_to_static_snapshot(client: TestClient, tmp_path: Path) -> None:
    from backend.settings import Settings, get_settings

    snapshot_dir = tmp_path / "liminalis" / "src" / "data"
    snapshot_dir.mkdir(parents=True)
    (snapshot_dir / "pyRadarFeed.js").write_text(
        """
const pyRadarFeed = {
  "items": [
    {
      "id": "item-1",
      "title": "Snapshot item",
      "originalTitle": "Snapshot item",
      "url": "https://example.com/post",
      "site": "example.com",
      "product": "DuckDB",
      "summary": "Static fallback",
      "tags": ["database"],
      "sources": ["snapshot"],
      "publishedDate": null,
      "contentType": "release",
      "fetchedAt": null,
      "syncBatch": null
    }
  ],
  "products": ["DuckDB"],
  "contentTypes": ["release"],
  "latestSyncBatch": null
}; export default pyRadarFeed
""".strip(),
        encoding="utf-8",
    )
    client.app.dependency_overrides[get_settings] = lambda: Settings(xlab_root=tmp_path, _env_file=None)
    try:
        response = client.get("/api/radar/items?per_page=1")
    finally:
        client.app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["total_items"] == 1
    assert body["items"][0]["title"] == "Snapshot item"
