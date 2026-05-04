"""DuckDB-backed ingestion job tracking for admin-submitted links."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class IngestionJobStore:
    def __init__(self, data_dir: Path, db_name: str = "items.duckdb"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / db_name
        self._conn = None

    def _get_conn(self):
        if self._conn is None:
            import duckdb

            self._conn = duckdb.connect(str(self.db_path))
            self._init_schema()
        return self._conn

    def _init_schema(self) -> None:
        conn = self._conn
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ingestion_jobs (
                id VARCHAR PRIMARY KEY,
                url VARCHAR NOT NULL,
                status VARCHAR NOT NULL,
                error VARCHAR,
                item_id VARCHAR,
                submitted_by VARCHAR,
                submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                metadata VARCHAR
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_status ON ingestion_jobs(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_submitted_at ON ingestion_jobs(submitted_at)")

    def create_job(self, job_id: str, url: str, submitted_by: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        conn = self._get_conn()
        conn.execute(
            """
            INSERT INTO ingestion_jobs
            (id, url, status, submitted_by, metadata)
            VALUES (?, ?, ?, ?, ?)
            """,
            [job_id, url, "queued", submitted_by, json.dumps(metadata, ensure_ascii=False)],
        )
        conn.commit()
        return self.get_job(job_id)

    def update_job(
        self,
        job_id: str,
        status: str,
        *,
        error: Optional[str] = None,
        item_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        conn = self._get_conn()
        existing = self.get_job(job_id)
        merged_metadata = existing.get("metadata", {}) if existing else {}
        if metadata:
            merged_metadata.update(metadata)

        started_at = existing.get("started_at") if existing else None
        completed_at = existing.get("completed_at") if existing else None
        if status in {"fetching", "extracting", "analyzing", "saving"} and not started_at:
            started_at = datetime.now()
        if status in {"completed", "failed", "duplicate"} and not completed_at:
            completed_at = datetime.now()

        conn.execute(
            """
            UPDATE ingestion_jobs
            SET status = ?,
                error = ?,
                item_id = COALESCE(?, item_id),
                started_at = ?,
                completed_at = ?,
                metadata = ?
            WHERE id = ?
            """,
            [
                status,
                error,
                item_id,
                started_at,
                completed_at,
                json.dumps(merged_metadata, ensure_ascii=False),
                job_id,
            ],
        )
        conn.commit()

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        row = conn.execute(
            """
            SELECT id, url, status, error, item_id, submitted_by,
                   submitted_at, started_at, completed_at, metadata
            FROM ingestion_jobs
            WHERE id = ?
            """,
            [job_id],
        ).fetchone()
        return self._row_to_dict(row) if row else None

    def list_jobs(self, limit: int = 50) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        rows = conn.execute(
            """
            SELECT id, url, status, error, item_id, submitted_by,
                   submitted_at, started_at, completed_at, metadata
            FROM ingestion_jobs
            ORDER BY submitted_at DESC
            LIMIT ?
            """,
            [limit],
        ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def _row_to_dict(self, row) -> Dict[str, Any]:
        metadata = {}
        if row[9]:
            try:
                metadata = json.loads(row[9])
            except json.JSONDecodeError:
                metadata = {}

        return {
            "id": row[0],
            "url": row[1],
            "status": row[2],
            "error": row[3],
            "item_id": row[4],
            "submitted_by": row[5],
            "submitted_at": row[6].isoformat() if row[6] else None,
            "started_at": row[7].isoformat() if row[7] else None,
            "completed_at": row[8].isoformat() if row[8] else None,
            "metadata": metadata,
        }

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
