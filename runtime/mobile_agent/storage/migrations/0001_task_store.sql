CREATE TABLE IF NOT EXISTS schema_migrations (
    revision TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE tasks (
    task_id TEXT PRIMARY KEY,
    task_type TEXT NOT NULL,
    device_id TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT NOT NULL,
    task_json TEXT NOT NULL
);

CREATE TABLE task_events (
    event_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    event_json TEXT NOT NULL,
    FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE CASCADE,
    UNIQUE (task_id, sequence)
);

CREATE INDEX idx_tasks_completed_at ON tasks(completed_at);
CREATE INDEX idx_task_events_task_sequence ON task_events(task_id, sequence);

INSERT INTO schema_migrations(revision) VALUES ('0001_task_store');
