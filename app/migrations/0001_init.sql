CREATE TABLE IF NOT EXISTS evidences (
    hash TEXT PRIMARY KEY,
    ots_status TEXT NOT NULL,
    tsa_status TEXT NOT NULL,
    ots_path TEXT,
    tsa_path TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_evidences_created_at ON evidences(created_at);
