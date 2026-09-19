-- Initial schema for skillscope snapshot store.

CREATE TABLE IF NOT EXISTS schema_meta (
    version     INTEGER NOT NULL,
    applied_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

INSERT INTO schema_meta (version) VALUES (1);

CREATE TABLE IF NOT EXISTS ingest_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conversations (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    harness_id              TEXT    NOT NULL,
    native_conversation_id  TEXT    NOT NULL,
    contract_version        INTEGER NOT NULL,
    source_revision         TEXT    NOT NULL,
    source_updated_at       TEXT    NOT NULL,
    readiness_basis         TEXT    NOT NULL,
    title                   TEXT,
    workspace_paths         TEXT,   -- JSON array
    started_at              TEXT,
    ended_at                TEXT,
    UNIQUE (harness_id, native_conversation_id)
);

CREATE TABLE IF NOT EXISTS events (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id         INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    contract_version        INTEGER NOT NULL,
    event_id                TEXT    NOT NULL,
    event_type              TEXT    NOT NULL,
    harness_id              TEXT    NOT NULL,
    native_conversation_id  TEXT    NOT NULL,
    sequence                INTEGER NOT NULL,
    native_turn_id          TEXT,
    turn_index              INTEGER,
    occurred_at             TEXT,
    time_provenance         TEXT    NOT NULL,
    evidence                TEXT    NOT NULL,  -- JSON
    payload                 TEXT    NOT NULL   -- JSON
);

CREATE INDEX IF NOT EXISTS idx_events_conversation ON events(conversation_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);

CREATE TABLE IF NOT EXISTS diagnostics (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id         INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    code                    TEXT    NOT NULL,
    message                 TEXT    NOT NULL,
    path                    TEXT,
    record_position         INTEGER
);

CREATE INDEX IF NOT EXISTS idx_diagnostics_conversation ON diagnostics(conversation_id);
