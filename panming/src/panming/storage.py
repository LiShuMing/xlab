"""PostgreSQL object metadata, immutable revisions and content-addressed originals."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

ROOT = Path(__file__).resolve().parents[2]
DATA = Path(os.environ.get("PANMING_DATA_DIR", str(ROOT / "data"))).resolve()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def object_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(8)}"


def database_url() -> str:
    if os.environ.get("PANMING_DATABASE_URL"):
        return os.environ["PANMING_DATABASE_URL"]
    config = DATA / "runtime.json"
    if not config.exists():
        raise RuntimeError("运行 scripts/setup.sh 初始化盘铭，或配置 PANMING_DATABASE_URL")
    return json.loads(config.read_text())["database_url"]


class RevisionConflict(Exception):
    """Only compare-and-swap conflicts should become HTTP 409."""


class Store:
    def __init__(
        self, url: str | None = None, data_dir: Path = DATA, connect_args: dict | None = None
    ) -> None:
        self.engine = create_engine(
            url or database_url(), pool_pre_ping=True, connect_args=connect_args or {}
        )
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        with self.engine.begin() as conn:
            conn.execute(
                text("""
                CREATE TABLE IF NOT EXISTS pm_objects (
                    id text PRIMARY KEY, kind text NOT NULL, data jsonb NOT NULL,
                    revision integer NOT NULL DEFAULT 1,
                    created_at timestamptz NOT NULL DEFAULT now(),
                    updated_at timestamptz NOT NULL DEFAULT now()
                )
            """)
            )
            conn.execute(
                text("""
                CREATE TABLE IF NOT EXISTS pm_revisions (
                    object_id text NOT NULL REFERENCES pm_objects(id),
                    revision integer NOT NULL, data jsonb NOT NULL,
                    created_at timestamptz NOT NULL DEFAULT now(),
                    PRIMARY KEY(object_id, revision)
                )
            """)
            )
            conn.execute(
                text("""
                CREATE TABLE IF NOT EXISTS pm_idempotency (
                    key text PRIMARY KEY, body_hash text NOT NULL, result jsonb NOT NULL
                )
            """)
            )
            conn.execute(text("CREATE INDEX IF NOT EXISTS pm_kind ON pm_objects(kind)"))
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS pm_material_fingerprint ON pm_objects ((data->>'fingerprint')) WHERE kind='material'"
                )
            )

    @contextmanager
    def transaction(self, *, exclusive: bool = False) -> Iterator[Connection]:
        with self.engine.begin() as conn:
            lock = "pg_advisory_xact_lock" if exclusive else "pg_advisory_xact_lock_shared"
            conn.execute(text(f"SELECT {lock}(hashtext(current_schema() || '/workspace'))"))
            yield conn

    def lock_inputs(self, conn: Connection) -> None:
        # Capture/revision/report share a commit barrier. Freeze input heads before
        # measuring cutoff; a writer released later belongs to the next version.
        conn.execute(text("SELECT pg_advisory_xact_lock(hashtext(current_schema() || '/inputs'))"))

    def get_revision(self, conn: Connection, oid: str, revision: int) -> dict | None:
        return conn.execute(
            text("SELECT data FROM pm_revisions WHERE object_id=:id AND revision=:revision"),
            {"id": oid, "revision": revision},
        ).scalar_one_or_none()

    def fingerprint(self, conn: Connection, value: str) -> dict | None:
        row = conn.execute(
            text(
                "SELECT data,revision FROM pm_objects WHERE kind='material' AND data->>'fingerprint'=:value LIMIT 1"
            ),
            {"value": value},
        ).first()
        return {**row.data, "revision": row.revision} if row else None

    def list(self, conn: Connection, kind: str) -> list[dict[str, Any]]:
        rows = conn.execute(
            text("SELECT data, revision FROM pm_objects WHERE kind=:kind ORDER BY created_at DESC"),
            {"kind": kind},
        )
        return [{**row.data, "revision": row.revision} for row in rows]

    def get(self, conn: Connection, oid: str, lock: bool = False) -> dict[str, Any] | None:
        suffix = " FOR UPDATE" if lock else ""
        row = conn.execute(
            text("SELECT data,revision FROM pm_objects WHERE id=:id" + suffix), {"id": oid}
        ).first()
        return {**row.data, "revision": row.revision} if row else None

    def insert(self, conn: Connection, kind: str, data: dict[str, Any]) -> dict[str, Any]:
        data = {**data, "revision": 1}
        params = {"id": data["id"], "kind": kind, "data": json.dumps(data, ensure_ascii=False)}
        conn.execute(
            text("INSERT INTO pm_objects(id,kind,data) VALUES(:id,:kind,CAST(:data AS jsonb))"),
            params,
        )
        conn.execute(
            text(
                "INSERT INTO pm_revisions(object_id,revision,data) VALUES(:id,1,CAST(:data AS jsonb))"
            ),
            params,
        )
        return data

    def update(self, conn: Connection, data: dict[str, Any], expected: int) -> dict[str, Any]:
        updated = {**data, "revision": expected + 1}
        params = {
            "id": data["id"],
            "expected": expected,
            "revision": expected + 1,
            "data": json.dumps(updated, ensure_ascii=False),
        }
        result = conn.execute(
            text("""
            UPDATE pm_objects SET data=CAST(:data AS jsonb),revision=:revision,updated_at=now()
            WHERE id=:id AND revision=:expected
        """),
            params,
        )
        if result.rowcount != 1:
            raise RevisionConflict("REVISION_CONFLICT")
        conn.execute(
            text("""
            INSERT INTO pm_revisions(object_id,revision,data)
            VALUES(:id,:revision,CAST(:data AS jsonb))
        """),
            params,
        )
        return updated

    def revisions(self, conn: Connection, oid: str) -> list[dict[str, Any]]:
        return [
            row.data
            for row in conn.execute(
                text("SELECT data FROM pm_revisions WHERE object_id=:id ORDER BY revision DESC"),
                {"id": oid},
            )
        ]

    def put_blob(self, body: bytes) -> str:
        digest = hashlib.sha256(body).hexdigest()
        dest = self.data_dir / "blobs" / digest[:2] / digest
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            temp = dest.with_name(f".{digest}-{secrets.token_hex(4)}")
            try:
                with temp.open("xb") as out:
                    out.write(body)
                    out.flush()
                    os.fsync(out.fileno())
                os.replace(temp, dest)
                directory_fd = os.open(dest.parent, os.O_RDONLY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            finally:
                temp.unlink(missing_ok=True)
        return digest
