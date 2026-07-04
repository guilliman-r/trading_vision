CREATE TABLE IF NOT EXISTS scan_runs (
    id INTEGER PRIMARY KEY,
    started_at_utc TEXT NOT NULL,
    finished_at_utc TEXT,
    interval TEXT NOT NULL,
    provider TEXT NOT NULL,
    symbols_requested INTEGER NOT NULL DEFAULT 0,
    symbols_succeeded INTEGER NOT NULL DEFAULT 0,
    symbols_failed INTEGER NOT NULL DEFAULT 0,
    candles_added INTEGER NOT NULL DEFAULT 0,
    patterns_added INTEGER NOT NULL DEFAULT 0,
    dry_run INTEGER NOT NULL DEFAULT 0 CHECK (dry_run IN (0, 1)),
    status TEXT NOT NULL CHECK (status IN ('running', 'completed', 'partial', 'failed')),
    error_summary TEXT
);

CREATE INDEX IF NOT EXISTS idx_scan_runs_interval_started
    ON scan_runs(interval, started_at_utc DESC);

CREATE TABLE IF NOT EXISTS scanner_heartbeat (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    status TEXT NOT NULL,
    process_id INTEGER NOT NULL,
    started_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL,
    next_wake_at_utc TEXT,
    last_run_id INTEGER REFERENCES scan_runs(id),
    message TEXT
);
