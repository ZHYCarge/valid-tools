ALTER TABLE evidences RENAME TO evidences_old;

CREATE TABLE IF NOT EXISTS evidences (
    hash TEXT PRIMARY KEY,
    ots_status TEXT NOT NULL,
    tsa_status TEXT NOT NULL,
    ots_path TEXT,
    tsa_path TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

INSERT INTO evidences (hash, ots_status, tsa_status, ots_path, tsa_path, created_at, updated_at)
SELECT hash, ots_status, tsa_status, ots_path, tsa_path, created_at, updated_at
FROM evidences_old;

DROP TABLE evidences_old;

CREATE INDEX IF NOT EXISTS idx_evidences_created_at ON evidences(created_at);
