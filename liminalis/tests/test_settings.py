"""Settings validation tests — production env must reject placeholder secrets."""

import os
from pathlib import Path

import pytest
from pydantic import ValidationError


def test_dev_defaults_load(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "development")
    from backend.settings import Settings, get_settings

    get_settings.cache_clear()
    settings = Settings(_env_file=None)
    assert settings.is_production is False
    assert settings.cors_allowed_origins == []


def test_supabase_database_url_configures_remote_business_database(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "SUPABASE_DB_URL",
        "postgresql://postgres.example:secret@db.supabase.co:6543/postgres?sslmode=require",
    )
    monkeypatch.delenv("PGSQL_USER", raising=False)
    monkeypatch.delenv("PGSQL_PASSWORD", raising=False)
    monkeypatch.delenv("PGSQL_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("PGSQL_DATABASE", raising=False)

    from backend.settings import Settings

    settings = Settings(_env_file=None)

    assert settings.postgres_configured is True
    assert settings.business_database_backend == "supabase_postgres"
    assert settings.business_database_remote is True
    assert settings.business_database_name == "postgres"
    assert settings.postgres_async_dsn.startswith(
        "postgresql+asyncpg://postgres.example:secret@db.supabase.co:6543/postgres"
    )
    assert "ssl=require" in settings.postgres_async_dsn


def test_psql_host_url_and_default_db_configure_business_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PSQL_URL", "db.example.supabase.co")
    monkeypatch.setenv("PSQL_PORT", "6543")
    monkeypatch.setenv("PSQL_USER", "postgres")
    monkeypatch.setenv("PSQL_PASSWORD", "secret")
    monkeypatch.setenv("PSQL_DEFAULT_DB", "postgres")
    monkeypatch.delenv("PGSQL_HOST", raising=False)
    monkeypatch.delenv("PGSQL_USER", raising=False)
    monkeypatch.delenv("PGSQL_PASSWORD", raising=False)
    monkeypatch.delenv("PGSQL_DATABASE", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_DB_URL", raising=False)

    from backend.settings import Settings

    settings = Settings(_env_file=None)

    assert settings.postgres_configured is True
    assert settings.business_database_backend == "supabase_postgres"
    assert settings.business_database_remote is True
    assert settings.business_database_name == "postgres"
    assert settings.postgres_async_dsn == (
        "postgresql+asyncpg://postgres:secret@db.example.supabase.co:6543/postgres"
    )


def test_shared_storage_layout_classifies_storage_boundaries(tmp_path: Path) -> None:
    from backend._shared.storage import allow_business_read_fallback, describe_storage
    from backend.settings import Settings

    settings = Settings(data_dir=tmp_path, _env_file=None)
    layout = describe_storage(settings)

    assert layout.business_backend == "unconfigured"
    assert layout.business_read_fallback is True
    assert layout.runtime_cache_dir == tmp_path / "cache"
    assert layout.local_artifact_dir == tmp_path / "artifacts"
    assert allow_business_read_fallback(settings) is True


def test_ego_settings_view_uses_runtime_settings() -> None:
    from backend.ego.config import Settings as EgoSettings
    from backend.settings import Settings

    runtime = Settings(
        llm_base_url="https://llm.example/v1",
        llm_api_key="key",
        llm_model="model-x",
        llm_timeout=42,
        llm_max_tokens=2048,
        llm_max_retries=3,
        embedding_model="embedding-x",
        embedding_use_local=False,
        ego_chat_history_limit=7,
        ego_chat_memory_top_k=5,
        ego_chat_max_context_tokens=4096,
        log_level="debug",
    )

    settings = EgoSettings.from_runtime(runtime)

    assert settings.llm_base_url == "https://llm.example/v1"
    assert settings.llm_api_key == "key"
    assert settings.llm_model == "model-x"
    assert settings.llm_timeout == 42
    assert settings.llm_max_tokens == 2048
    assert settings.llm_max_retries == 3
    assert settings.embedding_model == "embedding-x"
    assert settings.use_local_embedding is False
    assert settings.chat_history_limit == 7
    assert settings.chat_memory_top_k == 5
    assert settings.chat_max_context_tokens == 4096
    assert settings.log_level == "DEBUG"


def test_ego_embedding_mode_uses_runtime_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend._shared.ml_runtime import configure_ml_environment
    from backend.settings import Settings

    monkeypatch.delenv("USE_SIMPLE_EMBEDDING", raising=False)
    monkeypatch.delenv("USE_REAL_EMBEDDING", raising=False)

    assert Settings().ego_simple_embedding_enabled is True
    assert Settings(ego_use_real_embedding=True).ego_simple_embedding_enabled is False
    assert (
        Settings(
            ego_use_real_embedding=True,
            ego_use_simple_embedding=True,
        ).ego_simple_embedding_enabled
        is True
    )

    settings = Settings(ego_use_real_embedding=True)
    configure_ml_environment(settings)

    assert os.environ["USE_SIMPLE_EMBEDDING"] == "false"


def test_radar_config_keeps_domain_specific_llm_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("DB_RADAR_BASE_URL", "https://radar.example/v1")
    monkeypatch.setenv("LLM_BASE_URL", "https://global.example/v1")

    from backend.radar.config import Config, get_dotenv_values
    from backend.radar.config import get_settings as get_radar_settings
    from backend.settings import get_settings as get_runtime_settings

    get_runtime_settings.cache_clear()
    get_radar_settings.cache_clear()
    get_dotenv_values.cache_clear()

    assert Config().base_url == "https://radar.example/v1"


def test_radar_settings_view_uses_runtime_domain_config(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cache_dir = tmp_path / "cache"
    output_dir = tmp_path / "out"
    feeds_file = tmp_path / "feeds.json"
    monkeypatch.setenv("DB_RADAR_CACHE_DIR", str(cache_dir))
    monkeypatch.setenv("DB_RADAR_OUTPUT_DIR", str(output_dir))
    monkeypatch.setenv("DB_RADAR_FEEDS_FILE", str(feeds_file))
    monkeypatch.setenv("DB_RADAR_MAX_ITEMS", "42")
    monkeypatch.setenv("DB_RADAR_TOP_K", "6")
    monkeypatch.setenv("DB_RADAR_DAYS", "5")
    monkeypatch.setenv("DB_RADAR_LANGUAGE", "zh")
    monkeypatch.setenv("DB_RADAR_OSS_ACCESS_KEY_ID", "oss-id")
    monkeypatch.setenv("DB_RADAR_OSS_ACCESS_KEY_SECRET", "oss-secret")
    monkeypatch.setenv("DB_RADAR_OSS_BUCKET", "oss-bucket")

    from backend.radar.config import Config
    from backend.radar.config import get_settings as get_radar_settings
    from backend.settings import get_settings as get_runtime_settings

    get_runtime_settings.cache_clear()
    get_radar_settings.cache_clear()

    settings = get_radar_settings()
    config = Config()

    assert settings.cache_dir == cache_dir
    assert settings.output_dir == output_dir
    assert settings.feeds_file == feeds_file
    assert settings.max_items == 42
    assert settings.top_k == 6
    assert settings.days == 5
    assert settings.language == "zh"
    assert settings.oss_access_key_id == "oss-id"
    assert settings.get_oss_secret() == "oss-secret"
    assert config.oss_bucket == "oss-bucket"


def test_radar_admin_auth_uses_runtime_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RADAR_ADMIN_USER", "owner")
    monkeypatch.setenv("RADAR_ADMIN_PASSWORD", "plain-secret")
    monkeypatch.delenv("RADAR_ADMIN_PASSWORD_HASH", raising=False)

    from backend.radar.admin_auth import admin_username, verify_admin_password
    from backend.settings import get_settings as get_runtime_settings

    get_runtime_settings.cache_clear()

    assert admin_username() == "owner"
    assert verify_admin_password("plain-secret") is True
    assert verify_admin_password("wrong") is False


def test_radar_admin_service_uses_passed_runtime_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RADAR_ADMIN_USER", "env-owner")
    monkeypatch.setenv("RADAR_ADMIN_PASSWORD", "env-secret")

    from backend.services.radar_admin_service import admin_username, verify_admin_password
    from backend.settings import Settings

    settings = Settings(
        radar_admin_user="runtime-owner",
        radar_admin_password="runtime-secret",
        radar_admin_password_hash=None,
    )

    assert admin_username(settings) == "runtime-owner"
    assert verify_admin_password(settings, "runtime-secret") is True
    assert verify_admin_password(settings, "env-secret") is False


def test_radar_enhanced_sources_use_runtime_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "google-key")
    monkeypatch.setenv("GOOGLE_CX", "google-cx")
    monkeypatch.setenv("NEWSAPI_KEY", "news-key")

    from backend.radar.enhanced_sources import GoogleSearchSource, NewsAPISource
    from backend.settings import get_settings as get_runtime_settings

    get_runtime_settings.cache_clear()
    google = GoogleSearchSource()
    news = NewsAPISource()

    try:
        assert google.api_key == "google-key"
        assert google.cx == "google-cx"
        assert news.api_key == "news-key"
    finally:
        google.client.close()
        news.client.close()


def test_invest_config_path_uses_runtime_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config_path = tmp_path / "invest.yaml"
    monkeypatch.setenv("PY_INVEST_CONFIG_PATH", str(config_path))

    from backend.invest.config import get_config_path
    from backend.settings import get_settings as get_runtime_settings

    get_runtime_settings.cache_clear()

    assert get_config_path() == config_path


def test_invest_config_view_supports_from_runtime(tmp_path: Path) -> None:
    config_path = tmp_path / "invest.yaml"
    config_path.write_text(
        """
stocks:
  - code: AAPL
    name: Apple
email:
  sender: yaml-sender@example.com
  recipient: yaml-recipient@example.com
analysis:
  start_time: "08:30"
  timezone: "UTC"
""",
        encoding="utf-8",
    )

    from backend.invest.config import AppConfig
    from backend.settings import Settings

    settings = Settings(
        invest_config_path=config_path,
        gmail_app_password="runtime-password",
        _env_file=None,
    )

    config = AppConfig.from_runtime(settings)

    assert config.stocks[0].code == "AAPL"
    assert config.email.password == "runtime-password"
    assert config.analysis.timezone == "UTC"


def test_business_read_fallback_uses_runtime_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALLOW_BUSINESS_READ_FALLBACK", "false")

    from backend.settings import get_settings as get_runtime_settings

    get_runtime_settings.cache_clear()

    assert get_runtime_settings().allow_business_read_fallback is False


def test_invest_yaml_password_is_overridden_by_runtime_settings(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
stocks:
  - code: sh600519
    name: Guizhou Moutai
email:
  sender: yaml-sender@example.com
  recipient: yaml-recipient@example.com
  password: yaml-password
analysis:
  start_time: "07:30"
  timezone: "Asia/Shanghai"
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "runtime-password")

    from backend.invest.config import load_config
    from backend.settings import get_settings as get_runtime_settings

    get_runtime_settings.cache_clear()

    config = load_config(config_path)

    assert config.email.password == "runtime-password"
    assert config.email.sender == "yaml-sender@example.com"
    assert config.email.recipient == "yaml-recipient@example.com"


def test_invest_email_sender_config_uses_runtime_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "runtime-password")
    monkeypatch.setenv("EMAIL_RECIPIENT", "recipient@example.com")
    monkeypatch.setenv("EMAIL_SENDER", "sender@example.com")

    from backend.invest.notifier.email_sender import EmailConfig
    from backend.settings import get_settings as get_runtime_settings

    get_runtime_settings.cache_clear()

    config = EmailConfig.from_env()

    assert config.password == "runtime-password"
    assert config.recipient == "recipient@example.com"
    assert config.sender == "sender@example.com"


def test_invest_runtime_knobs_keep_legacy_env_aliases(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PY_INVEST_TOOL_TIMEOUT", "17")
    monkeypatch.setenv("PY_INVEST_FAST_MAX_TOKENS", "1234")
    monkeypatch.setenv("PY_INVEST_FAST_TEMPERATURE", "0.11")
    monkeypatch.setenv("PY_INVEST_AUTO_ANALYZER", "1")

    from backend.settings import Settings, get_settings

    get_settings.cache_clear()
    settings = Settings()

    assert settings.invest_tool_timeout == 17
    assert settings.invest_fast_max_tokens == 1234
    assert settings.invest_fast_temperature == 0.11
    assert settings.invest_auto_analyzer is True


def test_production_rejects_default_session_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("RADAR_ADMIN_PASSWORD", "real-secret")
    # session_secret left as the dev default.

    from backend.settings import Settings, get_settings

    get_settings.cache_clear()
    with pytest.raises(ValidationError) as exc:
        Settings()
    assert "session_secret" in str(exc.value)


def test_production_rejects_default_admin_password(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SESSION_SECRET", "x" * 40)
    monkeypatch.delenv("RADAR_ADMIN_PASSWORD", raising=False)
    monkeypatch.delenv("RADAR_ADMIN_PASSWORD_HASH", raising=False)

    from backend.settings import Settings, get_settings

    get_settings.cache_clear()
    with pytest.raises(ValidationError) as exc:
        Settings()
    assert "radar_admin_password" in str(exc.value)


def test_production_passes_with_real_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SESSION_SECRET", "x" * 40)
    monkeypatch.setenv("RADAR_ADMIN_PASSWORD", "real-secret")

    from backend.settings import Settings, get_settings

    get_settings.cache_clear()
    settings = Settings()
    assert settings.is_production is True
    assert len(settings.session_secret) >= 32
