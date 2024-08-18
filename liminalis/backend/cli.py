"""Top-level liminalis CLI.

Each absorbed domain registers its sub-commands here:
- M1: `liminalis radar fetch | summarize | add-url | sync`
- M2: `liminalis invest analyze`
- M3: `liminalis ego ...`

For now the CLI exposes runtime + admin scaffolding so it's not empty.
"""

from __future__ import annotations

import click

from backend._shared.logging import configure_logging, get_logger
from backend.settings import get_settings

logger = get_logger("liminalis.cli")


@click.group()
@click.version_option(package_name="liminalis")
def main() -> None:
    """liminalis: unified backend + frontend for radar / invest / ego."""
    configure_logging(get_settings())


@main.command()
def serve() -> None:
    """Run the FastAPI app via uvicorn (equivalent to `python -m backend.app`)."""
    import uvicorn

    settings = get_settings()
    uvicorn.run("backend.app:app", host=settings.host, port=settings.port)


@main.command()
def worker() -> None:
    """Run the arq worker (M1+ tasks register themselves into WorkerSettings)."""
    from arq.worker import run_worker

    from backend.workers import WorkerSettings

    run_worker(WorkerSettings)


@main.group()
def db() -> None:
    """Database administration helpers."""


@db.command("upgrade")
@click.argument("revision", default="head")
def db_upgrade(revision: str) -> None:
    """Run alembic upgrade. Equivalent to `alembic upgrade <rev>`."""
    from alembic import command
    from alembic.config import Config

    cfg = Config("alembic.ini")
    command.upgrade(cfg, revision)


@db.command("current")
def db_current() -> None:
    """Show the current alembic revision."""
    from alembic import command
    from alembic.config import Config

    cfg = Config("alembic.ini")
    command.current(cfg)


# Domain command groups (wired in by milestones)
# M1: radar CLI
from backend.radar.cli import cli as radar_cli  # noqa: E402

main.add_command(radar_cli, name="radar")

# M2: invest CLI
from backend.invest.cli import cli as invest_cli  # noqa: E402

main.add_command(invest_cli, name="invest")


# M3: ego CLI
from backend.ego.main import cli as ego_cli  # noqa: E402

main.add_command(ego_cli, name="ego")


if __name__ == "__main__":  # pragma: no cover
    main()
