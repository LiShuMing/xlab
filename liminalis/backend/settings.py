"""Runtime settings for the unified Liminalis API."""

from functools import lru_cache
from pathlib import Path
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_SESSION_SECRET = "local-dev-liminalis-session-secret"
DEV_ADMIN_PASSWORD = "change-me"
PRODUCTION_ENVS = {"production", "prod"}


class Settings(BaseSettings):
    """Application settings loaded from environment and local env files."""

    model_config = SettingsConfigDict(
        env_file=(str(Path.home() / ".env"), ".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Liminalis API"
    environment: str = Field(
        default="development",
        validation_alias=AliasChoices("environment", "ENVIRONMENT", "env", "ENV", "app_env", "APP_ENV"),
    )
    host: str = "127.0.0.1"
    port: int = 8010
    data_dir: Path = Field(default_factory=lambda: Path.home() / ".liminalis")
    xlab_root: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[2])
    allow_business_read_fallback: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "allow_business_read_fallback",
            "ALLOW_BUSINESS_READ_FALLBACK",
            "business_read_fallback",
            "BUSINESS_READ_FALLBACK",
            "allow_static_snapshot_fallback",
            "ALLOW_STATIC_SNAPSHOT_FALLBACK",
        ),
    )
    google_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("google_api_key", "GOOGLE_API_KEY"),
    )
    google_cx: str | None = Field(
        default=None,
        validation_alias=AliasChoices("google_cx", "GOOGLE_CX"),
    )
    newsapi_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("newsapi_key", "NEWSAPI_KEY"),
    )
    invest_config_path: Path = Field(
        default_factory=lambda: Path.home() / ".py-invest" / "config.yaml",
        validation_alias=AliasChoices(
            "invest_config_path",
            "INVEST_CONFIG_PATH",
            "py_invest_config_path",
            "PY_INVEST_CONFIG_PATH",
        ),
    )
    gmail_app_password: str | None = Field(
        default=None,
        validation_alias=AliasChoices("gmail_app_password", "GMAIL_APP_PASSWORD"),
    )
    email_sender: str | None = Field(
        default=None,
        validation_alias=AliasChoices("email_sender", "EMAIL_SENDER"),
    )
    email_recipient: str | None = Field(
        default=None,
        validation_alias=AliasChoices("email_recipient", "EMAIL_RECIPIENT"),
    )
    invest_auto_analyzer: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "invest_auto_analyzer", "INVEST_AUTO_ANALYZER", "PY_INVEST_AUTO_ANALYZER"
        ),
    )
    invest_tool_timeout: int = Field(
        default=20,
        validation_alias=AliasChoices("invest_tool_timeout", "INVEST_TOOL_TIMEOUT", "PY_INVEST_TOOL_TIMEOUT"),
    )
    invest_deep_max_tokens: int = Field(
        default=6500,
        validation_alias=AliasChoices(
            "invest_deep_max_tokens",
            "INVEST_DEEP_MAX_TOKENS",
            "PY_INVEST_DEEP_MAX_TOKENS",
        ),
    )
    invest_deep_temperature: float = Field(
        default=0.25,
        validation_alias=AliasChoices(
            "invest_deep_temperature",
            "INVEST_DEEP_TEMPERATURE",
            "PY_INVEST_DEEP_TEMPERATURE",
        ),
    )
    invest_deep_synthesis_max_tokens: int = Field(
        default=9000,
        validation_alias=AliasChoices(
            "invest_deep_synthesis_max_tokens",
            "INVEST_DEEP_SYNTHESIS_MAX_TOKENS",
            "PY_INVEST_DEEP_SYNTHESIS_MAX_TOKENS",
        ),
    )
    invest_deep_synthesis_temperature: float = Field(
        default=0.22,
        validation_alias=AliasChoices(
            "invest_deep_synthesis_temperature",
            "INVEST_DEEP_SYNTHESIS_TEMPERATURE",
            "PY_INVEST_DEEP_SYNTHESIS_TEMPERATURE",
        ),
    )
    invest_synthesis_timeout: int = Field(
        default=210,
        validation_alias=AliasChoices(
            "invest_synthesis_timeout",
            "INVEST_SYNTHESIS_TIMEOUT",
            "PY_INVEST_SYNTHESIS_TIMEOUT",
        ),
    )
    invest_fast_timeout: int = Field(
        default=120,
        validation_alias=AliasChoices("invest_fast_timeout", "INVEST_FAST_TIMEOUT", "PY_INVEST_FAST_TIMEOUT"),
    )
    invest_fast_max_tokens: int = Field(
        default=2200,
        validation_alias=AliasChoices(
            "invest_fast_max_tokens",
            "INVEST_FAST_MAX_TOKENS",
            "PY_INVEST_FAST_MAX_TOKENS",
        ),
    )
    invest_fast_temperature: float = Field(
        default=0.2,
        validation_alias=AliasChoices(
            "invest_fast_temperature",
            "INVEST_FAST_TEMPERATURE",
            "PY_INVEST_FAST_TEMPERATURE",
        ),
    )

    pgsql_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "pgsql_url",
            "PGSQL_URL",
            "psql_url",
            "PSQL_URL",
            "database_url",
            "DATABASE_URL",
            "supabase_db_url",
            "SUPABASE_DB_URL",
            "supabase_database_url",
            "SUPABASE_DATABASE_URL",
        ),
    )
    pgsql_host: str | None = Field(
        default=None,
        validation_alias=AliasChoices("pgsql_host", "PGSQL_HOST", "psql_host", "PSQL_HOST"),
    )
    pgsql_port: int = Field(
        default=5432,
        validation_alias=AliasChoices("pgsql_port", "PGSQL_PORT", "psql_port", "PSQL_PORT"),
    )
    pgsql_user: str | None = Field(
        default=None,
        validation_alias=AliasChoices("pgsql_user", "PGSQL_USER", "psql_user", "PSQL_USER"),
    )
    pgsql_password: str | None = Field(
        default=None,
        validation_alias=AliasChoices("pgsql_password", "PGSQL_PASSWORD", "psql_password", "PSQL_PASSWORD"),
    )
    pgsql_database: str = Field(
        default="liminalis_db",
        validation_alias=AliasChoices(
            "pgsql_database",
            "PGSQL_DATABASE",
            "pgsql_db",
            "PGSQL_DB",
            "psql_database",
            "PSQL_DATABASE",
            "psql_db",
            "PSQL_DB",
            "psql_default_db",
            "PSQL_DEFAULT_DB",
        ),
    )
    pgsql_maintenance_database: str = Field(
        default="postgres",
        validation_alias=AliasChoices(
            "pgsql_maintenance_database",
            "PGSQL_MAINTENANCE_DATABASE",
            "pgsql_admin_database",
            "PGSQL_ADMIN_DATABASE",
            "psql_maintenance_database",
            "PSQL_MAINTENANCE_DATABASE",
            "psql_admin_database",
            "PSQL_ADMIN_DATABASE",
        ),
    )
    pgsql_sslmode: str | None = Field(
        default=None,
        validation_alias=AliasChoices("pgsql_sslmode", "PGSQL_SSLMODE", "psql_sslmode", "PSQL_SSLMODE"),
    )

    db_radar_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("db_radar_api_key", "DB_RADAR_API_KEY"),
    )
    db_radar_base_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("db_radar_base_url", "DB_RADAR_BASE_URL"),
    )
    db_radar_model: str | None = Field(
        default=None,
        validation_alias=AliasChoices("db_radar_model", "DB_RADAR_MODEL"),
    )
    db_radar_timeout: float | None = Field(
        default=None,
        validation_alias=AliasChoices("db_radar_timeout", "DB_RADAR_TIMEOUT"),
    )
    radar_cache_dir: Path = Field(
        default=Path("cache"),
        validation_alias=AliasChoices("radar_cache_dir", "RADAR_CACHE_DIR", "DB_RADAR_CACHE_DIR"),
    )
    radar_output_dir: Path = Field(
        default=Path("out"),
        validation_alias=AliasChoices("radar_output_dir", "RADAR_OUTPUT_DIR", "DB_RADAR_OUTPUT_DIR"),
    )
    radar_feeds_file: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parent / "radar" / "data" / "feeds.json",
        validation_alias=AliasChoices("radar_feeds_file", "RADAR_FEEDS_FILE", "DB_RADAR_FEEDS_FILE"),
    )
    radar_refresh_on_startup: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "radar_refresh_on_startup",
            "RADAR_REFRESH_ON_STARTUP",
            "DB_RADAR_REFRESH_ON_STARTUP",
        ),
    )
    radar_refresh_startup_delay: float = Field(
        default=2.0,
        ge=0,
        le=60,
        validation_alias=AliasChoices(
            "radar_refresh_startup_delay",
            "RADAR_REFRESH_STARTUP_DELAY",
        ),
    )
    radar_refresh_timeout: float = Field(
        default=180.0,
        ge=10,
        le=900,
        validation_alias=AliasChoices("radar_refresh_timeout", "RADAR_REFRESH_TIMEOUT"),
    )
    radar_refresh_min_interval_minutes: int = Field(
        default=15,
        ge=0,
        le=1440,
        validation_alias=AliasChoices(
            "radar_refresh_min_interval_minutes",
            "RADAR_REFRESH_MIN_INTERVAL_MINUTES",
        ),
    )
    radar_max_items: int = Field(
        default=80,
        ge=1,
        le=500,
        validation_alias=AliasChoices("radar_max_items", "RADAR_MAX_ITEMS", "DB_RADAR_MAX_ITEMS"),
    )
    radar_top_k: int = Field(
        default=10,
        ge=1,
        le=100,
        validation_alias=AliasChoices("radar_top_k", "RADAR_TOP_K", "DB_RADAR_TOP_K"),
    )
    radar_days: int = Field(
        default=7,
        ge=1,
        le=30,
        validation_alias=AliasChoices("radar_days", "RADAR_DAYS", "DB_RADAR_DAYS"),
    )
    radar_language: str = Field(
        default="en",
        validation_alias=AliasChoices("radar_language", "RADAR_LANGUAGE", "DB_RADAR_LANGUAGE"),
    )
    radar_oss_access_key_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "radar_oss_access_key_id",
            "RADAR_OSS_ACCESS_KEY_ID",
            "db_radar_oss_access_key_id",
            "DB_RADAR_OSS_ACCESS_KEY_ID",
            "oss_access_key_id",
            "OSS_ACCESS_KEY_ID",
        ),
    )
    radar_oss_access_key_secret: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "radar_oss_access_key_secret",
            "RADAR_OSS_ACCESS_KEY_SECRET",
            "db_radar_oss_access_key_secret",
            "DB_RADAR_OSS_ACCESS_KEY_SECRET",
            "oss_access_key_secret",
            "OSS_ACCESS_KEY_SECRET",
        ),
    )
    radar_oss_endpoint: str = Field(
        default="oss-cn-hangzhou.aliyuncs.com",
        validation_alias=AliasChoices("radar_oss_endpoint", "RADAR_OSS_ENDPOINT", "DB_RADAR_OSS_ENDPOINT"),
    )
    radar_oss_bucket: str = Field(
        default="dbradar-sync",
        validation_alias=AliasChoices("radar_oss_bucket", "RADAR_OSS_BUCKET", "DB_RADAR_OSS_BUCKET"),
    )
    radar_oss_prefix: str = Field(
        default="sync/",
        validation_alias=AliasChoices("radar_oss_prefix", "RADAR_OSS_PREFIX", "DB_RADAR_OSS_PREFIX"),
    )

    llm_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("llm_api_key", "LLM_API_KEY", "OPENAI_API_KEY"),
    )
    llm_base_url: str = Field(
        default="https://api.openai.com/v1",
        validation_alias=AliasChoices("llm_base_url", "LLM_BASE_URL"),
    )
    llm_model: str = Field(
        default="gpt-4o-mini",
        validation_alias=AliasChoices("llm_model", "LLM_MODEL"),
    )
    llm_timeout: float = Field(
        default=120.0,
        validation_alias=AliasChoices("llm_timeout", "LLM_TIMEOUT"),
    )
    llm_temperature: float = Field(
        default=0.7,
        validation_alias=AliasChoices("llm_temperature", "LLM_TEMPERATURE"),
    )
    llm_max_tokens: int = Field(
        default=1024,
        validation_alias=AliasChoices("llm_max_tokens", "LLM_MAX_TOKENS"),
    )
    llm_max_retries: int = Field(
        default=1,
        validation_alias=AliasChoices("llm_max_retries", "LLM_MAX_RETRIES"),
    )
    llm_max_concurrency: int = Field(
        default=4,
        validation_alias=AliasChoices("llm_max_concurrency", "LLM_MAX_CONCURRENCY"),
    )
    embedding_model: str = Field(
        default="BAAI/bge-small-zh-v1.5",
        validation_alias=AliasChoices("embedding_model", "EMBEDDING_MODEL"),
    )
    embedding_use_local: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "embedding_use_local",
            "EMBEDDING_USE_LOCAL",
            "use_local_embedding",
            "USE_LOCAL_EMBEDDING",
        ),
    )
    ego_use_real_embedding: bool = Field(
        default=False,
        validation_alias=AliasChoices("ego_use_real_embedding", "USE_REAL_EMBEDDING"),
    )
    ego_use_simple_embedding: bool | None = Field(
        default=None,
        validation_alias=AliasChoices("ego_use_simple_embedding", "USE_SIMPLE_EMBEDDING"),
    )
    ego_chat_history_limit: int = Field(
        default=20,
        validation_alias=AliasChoices("ego_chat_history_limit", "EGO_CHAT_HISTORY_LIMIT"),
    )
    ego_chat_memory_top_k: int = Field(
        default=3,
        validation_alias=AliasChoices("ego_chat_memory_top_k", "EGO_CHAT_MEMORY_TOP_K"),
    )
    ego_chat_max_context_tokens: int = Field(
        default=8000,
        validation_alias=AliasChoices("ego_chat_max_context_tokens", "EGO_CHAT_MAX_CONTEXT_TOKENS"),
    )
    llm_wiki_url: str = Field(
        default="http://127.0.0.1:8787",
        validation_alias=AliasChoices("llm_wiki_url", "LLM_WIKI_URL"),
    )
    llm_wiki_socket: Path | None = Field(
        default=None,
        validation_alias=AliasChoices("llm_wiki_socket", "LLM_WIKI_SOCKET"),
    )
    llm_wiki_timeout: float = Field(
        default=60.0,
        validation_alias=AliasChoices("llm_wiki_timeout", "LLM_WIKI_TIMEOUT"),
    )

    wechat_official_app_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("wechat_official_app_id", "WECHAT_OFFICIAL_APP_ID"),
    )
    wechat_official_app_secret: str | None = Field(
        default=None,
        validation_alias=AliasChoices("wechat_official_app_secret", "WECHAT_OFFICIAL_APP_SECRET"),
    )
    wechat_official_oauth_redirect_uri: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "wechat_official_oauth_redirect_uri",
            "WECHAT_OFFICIAL_OAUTH_REDIRECT_URI",
        ),
    )
    wechat_official_oauth_scope: str = Field(
        default="snsapi_base",
        validation_alias=AliasChoices("wechat_official_oauth_scope", "WECHAT_OFFICIAL_OAUTH_SCOPE"),
    )
    wechat_official_mock_openid: str | None = Field(
        default=None,
        validation_alias=AliasChoices("wechat_official_mock_openid", "WECHAT_OFFICIAL_MOCK_OPENID"),
    )
    wechat_oauth_state_max_age_seconds: int = Field(
        default=600,
        validation_alias=AliasChoices(
            "wechat_oauth_state_max_age_seconds",
            "WECHAT_OAUTH_STATE_MAX_AGE_SECONDS",
        ),
    )

    radar_admin_user: str = "admin"
    radar_admin_password: str = DEV_ADMIN_PASSWORD
    radar_admin_password_hash: str | None = Field(
        default=None,
        validation_alias=AliasChoices("radar_admin_password_hash", "RADAR_ADMIN_PASSWORD_HASH"),
    )
    session_secret: str = DEV_SESSION_SECRET

    cookie_secure: bool = Field(
        default=False,
        validation_alias=AliasChoices("cookie_secure", "COOKIE_SECURE"),
    )
    cors_origins: str = Field(
        default="",
        validation_alias=AliasChoices("cors_origins", "CORS_ORIGINS"),
        description="Comma-separated list of allowed CORS origins. Empty disables CORS middleware.",
    )

    redis_url: str = Field(
        default="redis://localhost:6379/0",
        validation_alias=AliasChoices("redis_url", "REDIS_URL"),
        description="arq queue broker. Override to redis://localhost:6380/0 if using bundled docker-compose.",
    )
    health_check_timeout: float = Field(
        default=3.0,
        validation_alias=AliasChoices("health_check_timeout", "HEALTH_CHECK_TIMEOUT"),
    )
    http_max_connections: int = Field(
        default=20,
        validation_alias=AliasChoices("http_max_connections", "HTTP_MAX_CONNECTIONS"),
    )
    http_max_keepalive: int = Field(
        default=10,
        validation_alias=AliasChoices("http_max_keepalive", "HTTP_MAX_KEEPALIVE"),
    )
    http_timeout: float = Field(
        default=30.0,
        validation_alias=AliasChoices("http_timeout", "HTTP_TIMEOUT"),
    )
    circuit_breaker_failure_threshold: int = Field(
        default=5,
        validation_alias=AliasChoices(
            "circuit_breaker_failure_threshold",
            "CIRCUIT_BREAKER_FAILURE_THRESHOLD",
        ),
    )
    circuit_breaker_recovery_timeout: int = Field(
        default=30,
        validation_alias=AliasChoices(
            "circuit_breaker_recovery_timeout",
            "CIRCUIT_BREAKER_RECOVERY_TIMEOUT",
        ),
    )
    log_level: str = Field(
        default="INFO",
        validation_alias=AliasChoices("log_level", "LOG_LEVEL"),
    )

    @field_validator("radar_language", mode="before")
    @classmethod
    def _validate_radar_language(cls, value: str) -> str:
        language = str(value).lower()
        if language not in {"en", "zh"}:
            raise ValueError("radar_language must be one of {'en', 'zh'}")
        return language

    @field_validator("log_level", mode="before")
    @classmethod
    def _validate_log_level(cls, value: str) -> str:
        level = str(value).upper()
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if level not in valid_levels:
            raise ValueError(f"Invalid log level: {value}. Must be one of {valid_levels}")
        return level

    @model_validator(mode="after")
    def _enforce_production_secrets(self) -> "Settings":
        if self.environment.lower() not in PRODUCTION_ENVS:
            return self
        errors: list[str] = []
        if self.session_secret == DEV_SESSION_SECRET or len(self.session_secret) < 32:
            errors.append(
                "session_secret must be set to a non-default value of at least 32 characters "
                "(env: SESSION_SECRET)"
            )
        has_hash = bool(self.radar_admin_password_hash)
        has_plain = self.radar_admin_password and self.radar_admin_password != DEV_ADMIN_PASSWORD
        if not has_hash and not has_plain:
            errors.append("radar_admin_password (or RADAR_ADMIN_PASSWORD_HASH) must be set in production")
        if errors:
            raise ValueError("Insecure production configuration:\n  - " + "\n  - ".join(errors))
        return self

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in PRODUCTION_ENVS

    @property
    def cors_allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def postgres_configured(self) -> bool:
        if self.pgsql_url:
            parsed = urlsplit(self.pgsql_url)
            if parsed.scheme.startswith("postgres") and parsed.hostname:
                return bool(
                    (parsed.username and parsed.password) or (self.pgsql_user and self.pgsql_password)
                )
            if not parsed.scheme:
                return bool(self.pgsql_user and self.pgsql_password)
        return bool(self.pgsql_host and self.pgsql_user and self.pgsql_password)

    @property
    def business_database_backend(self) -> str:
        if not self.postgres_configured:
            return "unconfigured"
        endpoint = self.pgsql_url or self.pgsql_host or ""
        if "supabase" in endpoint.lower():
            return "supabase_postgres"
        return "postgres"

    @property
    def business_database_remote(self) -> bool:
        if not self.postgres_configured:
            return False
        endpoint = self.pgsql_url or self.pgsql_host or ""
        host = urlsplit(endpoint).hostname if "://" in endpoint else endpoint.split("/", 1)[0]
        host = (host or "").split(":", 1)[0].lower()
        return bool(host and host not in {"localhost", "127.0.0.1", "::1"})

    @property
    def business_database_name(self) -> str | None:
        if not self.postgres_configured:
            return None
        return self._effective_postgres_database(self.pgsql_database)

    @property
    def ego_simple_embedding_enabled(self) -> bool:
        if self.ego_use_simple_embedding is not None:
            return self.ego_use_simple_embedding
        return not self.ego_use_real_embedding

    @property
    def postgres_dsn(self) -> str:
        return self._postgres_dsn_for_database(self.pgsql_database)

    @property
    def postgres_async_dsn(self) -> str:
        return self._postgres_dsn_for_database(self.pgsql_database, driver="asyncpg")

    @property
    def postgres_maintenance_dsn(self) -> str:
        return self._postgres_dsn_for_database(self.pgsql_maintenance_database)

    def _postgres_dsn_for_database(self, database: str, *, driver: str | None = None) -> str:
        if not self.postgres_configured:
            return ""
        if self.pgsql_url and "://" in self.pgsql_url:
            return self._postgres_dsn_from_url(database, driver=driver)
        host, port = self._postgres_host_port()
        user = quote(self.pgsql_user or "", safe="")
        password = quote(self.pgsql_password or "", safe="")
        scheme = f"postgresql+{driver}" if driver else "postgresql"
        dsn = f"{scheme}://{user}:{password}@{host}:{port}/{quote(database, safe='')}"
        if self.pgsql_sslmode:
            # asyncpg uses 'ssl' in URL params instead of 'sslmode'
            param = "ssl" if driver == "asyncpg" else "sslmode"
            dsn = f"{dsn}?{param}={quote(self.pgsql_sslmode, safe='')}"
        return dsn

    def _postgres_dsn_from_url(self, database: str, *, driver: str | None = None) -> str:
        parsed = urlsplit(self.pgsql_url or "")
        scheme = f"postgresql+{driver}" if driver else "postgresql"
        effective_database = self._effective_postgres_database(database)
        path = f"/{quote(effective_database, safe='')}" if effective_database else parsed.path

        query_items = dict(parse_qsl(parsed.query, keep_blank_values=True))
        if self.pgsql_sslmode:
            query_items["ssl" if driver == "asyncpg" else "sslmode"] = self.pgsql_sslmode
        elif driver == "asyncpg" and "sslmode" in query_items and "ssl" not in query_items:
            query_items["ssl"] = query_items.pop("sslmode")

        return urlunsplit(
            (
                scheme,
                parsed.netloc,
                path,
                urlencode(query_items),
                "",
            )
        )

    def _effective_postgres_database(self, database: str) -> str:
        if (
            self.pgsql_url
            and "://" in self.pgsql_url
            and database == "liminalis_db"
            and "pgsql_database" not in self.model_fields_set
        ):
            parsed = urlsplit(self.pgsql_url)
            url_database = parsed.path.lstrip("/")
            if url_database:
                return url_database
        return database

    def _postgres_host_port(self) -> tuple[str, int]:
        endpoint = self.pgsql_host or self.pgsql_url or "localhost"
        if "://" in endpoint:
            parsed = urlsplit(endpoint)
            return parsed.hostname or "localhost", parsed.port or self.pgsql_port
        if "/" in endpoint:
            endpoint = endpoint.split("/", 1)[0]
        if ":" in endpoint:
            host, port = endpoint.rsplit(":", 1)
            if port.isdigit():
                return host, int(port)
        return endpoint, self.pgsql_port

    @property
    def frontend_dist_dir(self) -> Path:
        return Path(__file__).resolve().parents[1] / "dist"

    @property
    def py_ego_dir(self) -> Path:
        return self.xlab_root / "python" / "projects" / "py-ego" / "py-ego-miniapp"


@lru_cache
def get_settings() -> Settings:
    return Settings()
