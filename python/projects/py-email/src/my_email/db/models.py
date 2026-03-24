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

-- Project identification tables

-- Link topics to individual messages (enables clustering)
CREATE TABLE IF NOT EXISTS message_topics (
    message_id TEXT NOT NULL,
    topic TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    PRIMARY KEY (message_id, topic),
    FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_message_topics_topic ON message_topics(topic);

-- Project definitions (auto-discovered)
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    keywords TEXT,              -- JSON array of primary keywords
    sender_domains TEXT,        -- JSON array of associated domains
    email_count INTEGER DEFAULT 0,
    first_seen DATE,
    last_seen DATE,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

-- Email-to-project assignments
CREATE TABLE IF NOT EXISTS email_projects (
    message_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    confidence REAL,
    reasons TEXT,               -- JSON array of assignment reasons
    assigned_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_email_projects_project ON email_projects(project_id);
"""