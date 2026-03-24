"""Database schema for email inbox MVP."""

# Schema for new database creation (doesn't drop existing data)
SCHEMA_SQL = """
-- Messages table (simplified schema)
CREATE TABLE IF NOT EXISTS messages (
    id           TEXT PRIMARY KEY,      -- Gmail message ID
    thread_id    TEXT NOT NULL,
    subject      TEXT,
    sender       TEXT,
    sender_email TEXT,                  -- Extracted email address
    received_at  TEXT NOT NULL,         -- ISO-8601 UTC
    body_text    TEXT,                  -- Original email body
    msg_state    TEXT NOT NULL DEFAULT 'unread',  -- 'unread', 'read', 'starred'
    relevance    TEXT,                  -- 'high', 'medium', 'low', 'skip', NULL
    summary_json TEXT,                  -- AI summary JSON
    created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_messages_received ON messages(received_at);
CREATE INDEX IF NOT EXISTS idx_messages_state ON messages(msg_state);
CREATE INDEX IF NOT EXISTS idx_messages_relevance ON messages(relevance);

-- Settings table
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Default settings
INSERT OR IGNORE INTO settings (key, value) VALUES
    ('retention_days', '7'),
    ('auto_sync_interval_minutes', '30'),
    ('last_history_id', '');
"""

# One-time migration script (drops old tables)
MIGRATION_SQL = """
-- Drop old tables (run only during migration)
DROP TABLE IF EXISTS messages;
DROP TABLE IF EXISTS summaries;
DROP TABLE IF EXISTS digests;
DROP TABLE IF EXISTS topic_daily;
DROP TABLE IF EXISTS topic_tracks;
DROP TABLE IF EXISTS message_topics;
DROP TABLE IF EXISTS projects;
DROP TABLE IF EXISTS email_projects;
DROP TABLE IF EXISTS sync_state;

-- Then run SCHEMA_SQL
"""