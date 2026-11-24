CREATE TABLE IF NOT EXISTS files (
    id TEXT PRIMARY KEY, filename TEXT NOT NULL,
    label TEXT NOT NULL, description TEXT NOT NULL,
    size INTEGER NOT NULL, sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY, file_id TEXT NOT NULL REFERENCES files(id),
    hosts TEXT NOT NULL, status TEXT NOT NULL,
    operation TEXT NOT NULL DEFAULT 'download' CHECK(operation IN ('download','install_python')),
    log TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TEXT
);
CREATE TABLE IF NOT EXISTS agents (
    name TEXT PRIMARY KEY, token_hash TEXT NOT NULL,
    last_seen TEXT
);
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(id),
    host TEXT NOT NULL REFERENCES agents(name),
    status TEXT NOT NULL DEFAULT 'queued',
    claim TEXT, lease_until INTEGER,
    log TEXT NOT NULL DEFAULT '', UNIQUE(job_id,host)
);
