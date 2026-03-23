SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sync_state (
    id          INTEGER PRIMARY KEY CHECK (id = 1),
    history_id  TEXT NOT NULL,
    last_sync   TEXT NOT NULL        -- ISO-8601 UTC
);

CREATE TABLE IF NOT EXISTS messages (
    id           TEXT PRIMARY KEY,   -- Gmail message ID (stable, used for dedup)
    thread_id    TEXT NOT NULL,
    subject      TEXT,
    sender       TEXT,
    received_at  TEXT NOT NULL,      -- ISO-8601 UTC
    labels       TEXT,               -- JSON array of Gmail label IDs
    body_text    TEXT,               -- cleaned plain text, truncated at 8k chars
    processed    INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_messages_received   ON messages(received_at);
CREATE INDEX IF NOT EXISTS idx_messages_processed  ON messages(processed);

CREATE TABLE IF NOT EXISTS summaries (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id   TEXT NOT NULL UNIQUE REFERENCES messages(id) ON DELETE CASCADE,
    summary_json TEXT NOT NULL,      -- serialized EmailSummary (Pydantic model)
    model        TEXT NOT NULL,      -- model used, e.g. "qwen2.5:7b"
    created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE IF NOT EXISTS digests (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    date         TEXT NOT NULL UNIQUE,  -- YYYY-MM-DD
    digest_json  TEXT NOT NULL,         -- serialized DailyDigest
    created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

-- Topic arc tracking tables

CREATE TABLE IF NOT EXISTS topic_daily (
    topic       TEXT NOT NULL,
    date        TEXT NOT NULL,        -- YYYY-MM-DD
    count       INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (topic, date)
);

CREATE TABLE IF NOT EXISTS topic_tracks (
    topic           TEXT PRIMARY KEY,
    first_seen_date TEXT NOT NULL,    -- YYYY-MM-DD
    last_seen_date  TEXT NOT NULL,    -- YYYY-MM-DD
    total_mentions  INTEGER NOT NULL DEFAULT 0,
    peak_date       TEXT NOT NULL,    -- YYYY-MM-DD
    peak_count      INTEGER NOT NULL DEFAULT 0,
    sample_titles   TEXT NOT NULL     -- JSON array of up to 3 email titles
);

CREATE INDEX IF NOT EXISTS idx_topic_daily_date    ON topic_daily(date);
CREATE INDEX IF NOT EXISTS idx_topic_tracks_last   ON topic_tracks(last_seen_date);
"""