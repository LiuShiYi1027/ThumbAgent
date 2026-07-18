CREATE TABLE task_executions (
    task_id TEXT PRIMARY KEY,
    task_type TEXT NOT NULL,
    device_id TEXT NOT NULL,
    status TEXT NOT NULL,
    submitted_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    idempotency_key TEXT UNIQUE,
    request_fingerprint TEXT,
    execution_json TEXT NOT NULL
);

CREATE TABLE task_execution_events (
    event_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    event_json TEXT NOT NULL,
    FOREIGN KEY (task_id) REFERENCES task_executions(task_id) ON DELETE CASCADE,
    UNIQUE (task_id, sequence)
);

CREATE INDEX idx_task_executions_submitted_at ON task_executions(submitted_at);
CREATE INDEX idx_task_execution_events_task_sequence ON task_execution_events(task_id, sequence);

INSERT INTO schema_migrations(revision) VALUES ('0002_task_executions');
