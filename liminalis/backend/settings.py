"""Runtime settings for the unified Liminalis API."""

from functools import lru_cache
from pathlib import Path
from urllib.parse import quote, urlsplit

from pydantic import AliasChoices, Field, model_validator
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
    storage_backend: str = "auto"
    radar_db_name: str = "items.duckdb"

    pgsql_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("pgsql_url", "PGSQL_URL", "psql_url", "PSQL_URL"),
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

    llm_api_key: str | None = None
    llm_base_url: str | None = None
    llm_model: str | None = None

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
    def app_db_path(self) -> Path:
        return self.data_dir / "liminalis.sqlite"

    @property
    def postgres_configured(self) -> bool:
        return bool((self.pgsql_host or self.pgsql_url) and self.pgsql_user and self.pgsql_password)

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
    def radar_data_dir(self) -> Path:
        return self.data_dir / "radar"

    @property
    def invest_data_dir(self) -> Path:
        return self.data_dir / "invest"

    @property
    def frontend_dist_dir(self) -> Path:
        return Path(__file__).resolve().parents[1] / "dist"

    @property
    def py_ego_dir(self) -> Path:
        return self.xlab_root / "python" / "projects" / "py-ego" / "py-ego-miniapp"


@lru_cache
def get_settings() -> Settings:
    return Settings()
