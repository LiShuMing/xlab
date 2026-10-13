from dataclasses import replace
from types import SimpleNamespace

import pytest

from backend.radar.analysis import PROMPT_VERSION, IngestionRequest, normalize_analysis
from backend.radar.extractor import ExtractedItem, Extractor
from backend.radar.fetcher import FetchResult
from backend.radar.normalize import Normalizer
from backend.radar.refresh import _enrich_ranked_items, _merge_incremental_items, _ranked_item_to_data
from backend.settings import Settings


def article(**kwargs):
    values = {
        "url": "https://example.test/a",
        "title": "DB 2.1.0 release",
        "product": "DB",
        "content": "The optimizer now supports partition pruning for range predicates. This feature is available in the new database release.",
        "html_content": "",
        "published_at": "2026-10-13",
        "author": None,
        "content_type": "release",
        "confidence": 0.9,
    }
    return ExtractedItem(**(values | kwargs))


def analysis_data():
    return {
        "title": "DB 分区裁剪更新",
        "summary": "优化器现在支持范围谓词的分区裁剪。正文没有给出性能测试条件，因此无法据此判断性能提升幅度。",
        "content_type": "release",
        "tags": ["optimizer"],
        "evidence": [{"claim": "支持范围谓词分区裁剪", "source_id": "S1"}],
    }


def test_model_quotes_must_be_source_spans():
    extracted = article()
    data = analysis_data()
    assert normalize_analysis(data, extracted, IngestionRequest(url=extracted.url))["evidence"]
    data["evidence"][0]["source_id"] = "S999"
    with pytest.raises(ValueError, match="source passage ID"):
        normalize_analysis(data, extracted, IngestionRequest(url=extracted.url))


@pytest.mark.parametrize(
    "field,value",
    [
        ("summary", ["wrong type"]),
        ("summary", "English only " * 8),
        ("tags", [1]),
        ("content_type", ["release"]),
    ],
)
def test_reject_malformed_model_fields(field, value):
    data = analysis_data() | {field: value}
    with pytest.raises((ValueError, TypeError)):
        normalize_analysis(data, article(), IngestionRequest(url=article().url))


def test_similar_patch_releases_and_articles_sharing_body_version_stay_separate():
    one = article()
    two = replace(one, url="https://example.test/b", title="DB 2.1.1 release")
    three = replace(
        one, url="https://example.test/c", title="Storage internals", content="Works with DB 2.1.0"
    )
    four = replace(three, url="https://example.test/d", title="Query optimization")
    assert len(Normalizer().normalize([one, two, three, four])) == 4


def test_decimal_performance_number_is_not_a_product_version():
    normalized = Normalizer().normalize(
        [
            article(
                title="Query comparison", content="Scanned 113.2 billion records.", content_type="benchmark"
            )
        ]
    )[0]
    result = _ranked_item_to_data(SimpleNamespace(item=normalized))
    assert result["version"] is None
    assert result["evidence"][0]["text"] in normalized.content


def test_fresh_short_summary_replaces_old_verbose_summary():
    old = {"url": article().url, "summary": "Old verbose stale summary " * 10, "publishedDate": "2026-10-13"}
    new = old | {"summary": "Accurate short summary"}
    assert _merge_incremental_items([new], [old], max_days=7)[0]["summary"] == new["summary"]


@pytest.mark.parametrize(
    "provider,version,model,expected",
    [
        ("extractive", PROMPT_VERSION, "test", 1),
        ("fallback", PROMPT_VERSION, "test", 1),
        ("llm", "old-prompt", "test", 1),
        ("llm", PROMPT_VERSION, "old-model", 1),
        ("llm", PROMPT_VERSION, "test", 0),
    ],
)
def test_only_successful_matching_analysis_is_cached(
    monkeypatch, tmp_path, provider, version, model, expected
):
    from backend.radar import refresh

    normalized = Normalizer().normalize([article()])[0]
    ranked = [SimpleNamespace(item=normalized)]
    item = _ranked_item_to_data(ranked[0])
    previous = item | {"analysisProvider": provider, "analysisModel": model, "promptVersion": version}
    monkeypatch.setattr(refresh, "load_radar_artifact", lambda settings: {"items": [previous]})
    calls = []

    def fake(extracted, request, *, settings):
        calls.append(settings)
        return normalize_analysis(analysis_data(), extracted, request) | {"analysis_provider": "llm"}

    monkeypatch.setattr(refresh, "analyze_with_llm", fake)
    settings = Settings(_env_file=None, data_dir=tmp_path, llm_api_key="test", llm_model="test")
    result = _enrich_ranked_items([item], ranked, settings)
    assert len(calls) == expected
    assert result[0]["analysisProvider"] == "llm"


def test_github_release_body_excludes_navigation():
    body = article().content * 3
    fetched = FetchResult(
        url="https://github.com/org/db/releases/tag/v2.1.0",
        product="DB",
        status_code=200,
        content_type="html",
        content=f'<nav>Repository navigation wrong release</nav><div class="markdown-body"><h2>2.1.0</h2><p>{body}</p></div>',
    )
    text = Extractor().extract_html_items(fetched)[0].content
    assert "Repository navigation" not in text
    assert "partition pruning" in text


@pytest.mark.asyncio
async def test_database_failure_keeps_unpublished_checkpoint(monkeypatch, tmp_path):
    import json
    from contextlib import asynccontextmanager

    from backend.radar import refresh

    settings = Settings(
        _env_file=None, data_dir=tmp_path, pgsql_host="localhost", pgsql_user="test", pgsql_password="test"
    )
    item = {"url": article().url, "summary": "New accurate summary", "rawContent": article().content}
    monkeypatch.setattr(refresh, "_collect_latest_news", lambda _: ([item], 1, 1))

    @asynccontextmanager
    async def unavailable():
        raise ConnectionError("unavailable")
        yield

    monkeypatch.setattr(refresh, "business_uow", unavailable)
    with pytest.raises(ConnectionError):
        await refresh.refresh_latest_radar_news(settings)
    assert not refresh.radar_artifact_path(settings).exists()
    pending = json.loads((tmp_path / "artifacts/radar/pending.json").read_text())
    assert pending["items"][0]["rawContent"] == article().content
    assert refresh.get_radar_refresh_status()["state"] == "failed"


def test_release_extraction_preserves_version_boundaries():
    from backend.radar.refresh import _enrich_with_full_articles

    item = article(title="DB 2.1.1", channel="release")
    body = "<h2>2.1.1 (2026-10-13)</h2><p>Fixed corruption when closing read-only database instances.</p><h2>2.1.0 (2026-09-01)</h2><p>Old breaking API changes must not leak into this release.</p>"

    class CachedFetcher:
        def fetch_targets_concurrent(self, targets, *, use_cache):
            return [
                FetchResult(
                    url=item.url,
                    product="DB",
                    status_code=200,
                    content_type="html",
                    content=f'<div class="markdown-body">{body}</div>',
                )
            ]

    item.url = "https://github.com/org/db/releases/tag/v2.1.1"
    result = _enrich_with_full_articles([item], fetcher=CachedFetcher(), limit=1)
    assert "Fixed corruption" in result[0].content
    assert "Old breaking API" not in result[0].content


def test_empty_github_release_does_not_turn_navigation_into_evidence():
    fetched = FetchResult(
        url="https://github.com/org/db/releases/tag/v2.1.0",
        product="DB",
        status_code=200,
        content_type="html",
        content="<h1>Repository navigation</h1><p>12345 commits since this release.</p>",
    )
    assert Extractor().extract_html_items(fetched) == []


@pytest.mark.asyncio
async def test_local_e2e_never_opens_postgres(monkeypatch, tmp_path):
    from backend.radar import refresh
    from backend.routers import radar
    from scripts import radar_quality

    configured = Settings(
        _env_file=None, data_dir=tmp_path, pgsql_host="db.example", pgsql_user="user", pgsql_password="secret"
    )
    settings = radar_quality.local_settings(configured)
    assert not settings.postgres_configured
    assert settings.data_dir == tmp_path / "e2e-local"

    def forbidden():
        raise AssertionError("Local E2E must never connect to PostgreSQL")

    for module in (refresh, radar, radar_quality):
        monkeypatch.setattr(module, "business_uow", forbidden)
    normalized = Normalizer().normalize([article()])[0]
    item = _ranked_item_to_data(SimpleNamespace(item=normalized))
    monkeypatch.setattr(refresh, "_collect_latest_news", lambda _: ([item], 1, 1))
    result = await refresh.refresh_latest_radar_news(settings)
    assert result["persisted"] == 0
    report = await radar_quality.audit(settings, storage="local")
    assert report["errors"] == []
    assert report["storageMode"] == "local"
    assert "PostgreSQL upsert" in report["skippedChecks"]
    assert report["apiTotalItems"] == 1


@pytest.mark.parametrize("items", [[], [{"url": "https://example.test/new", "title": "Current"}]])
def test_published_artifact_does_not_mix_in_old_bundled_content(monkeypatch, items):
    from backend.services import radar_service

    monkeypatch.setattr(
        radar_service, "load_radar_artifact", lambda _: {"generatedAt": "2026-10-13", "items": items}
    )
    monkeypatch.setattr(
        radar_service,
        "load_py_radar_snapshot",
        lambda _: {"items": [{"url": "https://example.test/old", "title": "Old bundled item"}]},
    )
    result = radar_service.read_snapshot_radar_items(Settings(_env_file=None), radar_service.RadarQuery())
    assert result["storage"] == "artifact"
    assert result["total_items"] == len(items)
    assert all(item["url"] != "https://example.test/old" for item in result["items"])
