"""SQLite database initialization and connection management."""

import sqlite3

from pia.config.settings import get_settings

CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS products (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT,
    homepage TEXT,
    description TEXT,
    config_path TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS releases (
    id TEXT PRIMARY KEY,
    product_id TEXT NOT NULL,
    version TEXT NOT NULL,
    title TEXT,
    published_at TEXT,
    source_url TEXT,
    source_type TEXT,
    source_hash TEXT,
    raw_snapshot_path TEXT,
    normalized_snapshot_path TEXT,
    discovered_at TEXT NOT NULL,
    UNIQUE(product_id, version)
);

CREATE TABLE IF NOT EXISTS reports (
    id TEXT PRIMARY KEY,
    product_id TEXT NOT NULL,
    release_id TEXT NOT NULL,
    report_type TEXT NOT NULL,
    model_name TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    content_md TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    generated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS digest_reports (
    id TEXT PRIMARY KEY,
    product_ids TEXT NOT NULL,
    time_window TEXT NOT NULL,
    model_name TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    content_md TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    generated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_releases_product ON releases(product_id);
CREATE INDEX IF NOT EXISTS idx_reports_release ON reports(release_id);
CREATE INDEX IF NOT EXISTS idx_reports_cache ON reports(product_id, release_id, report_type, model_name, prompt_version);
"""


def get_connection() -> sqlite3.Connection:
    """Open a SQLite connection to the application database.

    Returns:
        An sqlite3 Connection with row_factory set to sqlite3.Row.
    """
    settings = get_settings()
    conn = sqlite3.connect(str(settings.db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create all database tables and indexes if they do not already exist."""
    conn = get_connection()
    conn.executescript(CREATE_TABLES)
    conn.commit()
    conn.close()
