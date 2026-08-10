"""Configuration helpers for LongCycle.

Secrets are loaded from environment variables or ``~/.env`` but are never
returned to the UI. The UI only receives redacted integration status.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, urlparse

from dotenv import load_dotenv


ENV_PATH = Path.home() / ".env"


def load_local_env() -> None:
    """Load local env values without overwriting the active shell."""

    if ENV_PATH.exists():
        load_dotenv(ENV_PATH, override=False)


def _present(name: str) -> bool:
    return bool(os.getenv(name, "").strip())


def _redact(value: str | None) -> str | None:
    if not value:
        return None
    if len(value) <= 10:
        return "***"
    return f"{value[:4]}...{value[-4:]}"


def _redact_url(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlparse(value if "://" in value else f"postgresql://{value}")
    host = parsed.hostname or value
    if len(host) <= 8:
        safe_host = "***"
    else:
        safe_host = f"{host[:4]}...{host[-4:]}"
    return safe_host


@dataclass(frozen=True)
class IntegrationStatus:
    name: str
    configured: bool
    status: str
    details: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "configured": self.configured,
            "status": self.status,
            "details": self.details,
        }


def llm_status() -> IntegrationStatus:
    load_local_env()
    base_url = os.getenv("LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL")
    model = os.getenv("LLM_MODEL") or os.getenv("OPENAI_MODEL")
    has_key = _present("LLM_API_KEY") or _present("OPENAI_API_KEY")
    configured = bool(base_url and model and has_key)
    return IntegrationStatus(
        name="LLM",
        configured=configured,
        status="configured" if configured else "missing",
        details={
            "base_url": base_url,
            "model": model,
            "api_key_configured": has_key,
            "timeout": os.getenv("LLM_TIMEOUT", "30"),
        },
    )


def psql_connection_target() -> str | None:
    load_local_env()
    direct_url = os.getenv("PSQL_URL") or os.getenv("DATABASE_URL")
    if direct_url and "://" in direct_url:
        return direct_url

    user = os.getenv("PSQL_USER") or os.getenv("PGUSER")
    password = os.getenv("PSQL_PASSWORD") or os.getenv("PGPASSWORD")
    host = direct_url or os.getenv("PSQL_HOST") or os.getenv("PGHOST") or "localhost"
    port = os.getenv("PSQL_PORT") or os.getenv("PGPORT") or "5432"
    database = os.getenv("PSQL_DEFAULT_DB") or os.getenv("PGDATABASE")
    if not (user and database):
        return None

    auth = quote_plus(user)
    if password:
        auth += f":{quote_plus(password)}"
    return f"postgresql://{auth}@{host}:{port}/{database}"


def psql_status(probe: bool = True) -> IntegrationStatus:
    load_local_env()
    target = psql_connection_target()
    configured = bool(target)
    details: dict[str, Any] = {
        "url": _redact_url(target),
        "psql_cli": shutil.which("psql"),
        "user": os.getenv("PSQL_USER") or os.getenv("PGUSER"),
        "database": os.getenv("PSQL_DEFAULT_DB") or os.getenv("PGDATABASE"),
        "port": os.getenv("PSQL_PORT") or os.getenv("PGPORT"),
    }

    if not configured:
        return IntegrationStatus("PostgreSQL", False, "missing", details)

    if not probe:
        return IntegrationStatus("PostgreSQL", True, "configured", details)

    psql = shutil.which("psql")
    if not psql:
        return IntegrationStatus("PostgreSQL", True, "configured-no-cli", details)

    env = os.environ.copy()
    if os.getenv("PSQL_PASSWORD") and not env.get("PGPASSWORD"):
        env["PGPASSWORD"] = os.getenv("PSQL_PASSWORD", "")

    try:
        result = subprocess.run(
            [psql, target, "-Atqc", "select current_database() || ' / ' || current_user;"],
            check=False,
            capture_output=True,
            text=True,
            timeout=4,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return IntegrationStatus("PostgreSQL", True, "probe-timeout", details)
    except Exception as exc:  # pragma: no cover - defensive boundary
        details["error"] = type(exc).__name__
        return IntegrationStatus("PostgreSQL", True, "probe-error", details)

    if result.returncode == 0:
        details["identity"] = result.stdout.strip()
        return IntegrationStatus("PostgreSQL", True, "connected", details)

    stderr = result.stderr.strip().splitlines()
    details["error"] = stderr[-1] if stderr else "psql returned non-zero"
    return IntegrationStatus("PostgreSQL", True, "probe-failed", details)


def integration_snapshot(probe_psql: bool = True) -> dict[str, Any]:
    return {
        "env_path": str(ENV_PATH),
        "llm": llm_status().as_dict(),
        "psql": psql_status(probe=probe_psql).as_dict(),
    }
