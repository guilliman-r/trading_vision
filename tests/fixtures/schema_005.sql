CREATE TABLE schema_migrations (
    filename TEXT PRIMARY KEY,
    applied_at_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO schema_migrations(filename) VALUES
    ('001_initial.sql'),
    ('002_patterns.sql'),
    ('003_scanner.sql'),
    ('004_alerts.sql'),
    ('005_quality_warnings.sql');

CREATE TABLE symbols (
    id INTEGER PRIMARY KEY,
    display_symbol TEXT NOT NULL,
    provider_symbol TEXT NOT NULL UNIQUE,
    name TEXT,
    exchange TEXT,
    currency TEXT,
    is_bist INTEGER NOT NULL DEFAULT 0 CHECK (is_bist IN (0, 1)),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    source TEXT,
    source_date TEXT,
    created_at_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_symbols_display_symbol
    ON symbols(display_symbol);

CREATE INDEX idx_symbols_bist_active
    ON symbols(is_bist, is_active);

CREATE TABLE candles (
    symbol_id INTEGER NOT NULL REFERENCES symbols(id) ON DELETE CASCADE,
    interval TEXT NOT NULL,
    opened_at_utc TEXT NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume REAL,
    is_complete INTEGER NOT NULL CHECK (is_complete IN (0, 1)),
    is_adjusted INTEGER NOT NULL CHECK (is_adjusted IN (0, 1)),
    source TEXT NOT NULL,
    fetched_at_utc TEXT NOT NULL,
    PRIMARY KEY (symbol_id, interval, opened_at_utc)
);

CREATE INDEX idx_candles_chart
    ON candles(symbol_id, interval, opened_at_utc DESC);

CREATE TABLE patterns (
    id TEXT PRIMARY KEY,
    symbol_id INTEGER NOT NULL REFERENCES symbols(id) ON DELETE CASCADE,
    interval TEXT NOT NULL,
    pattern_type TEXT NOT NULL,
    direction TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('forming', 'confirmed', 'invalidated', 'expired')),
    started_at_utc TEXT NOT NULL,
    ended_at_utc TEXT,
    confirmed_at_utc TEXT,
    score REAL NOT NULL,
    boundary_price REAL NOT NULL,
    target_price REAL,
    invalidation_price REAL,
    points_json TEXT NOT NULL,
    reasons_json TEXT NOT NULL,
    parameters_json TEXT NOT NULL,
    detector_version TEXT NOT NULL,
    first_seen_at_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_patterns_symbol_interval
    ON patterns(symbol_id, interval, state, last_seen_at_utc DESC);

CREATE INDEX idx_patterns_recent
    ON patterns(state, pattern_type, confirmed_at_utc DESC);

CREATE TABLE pattern_transitions (
    id INTEGER PRIMARY KEY,
    pattern_id TEXT NOT NULL REFERENCES patterns(id) ON DELETE CASCADE,
    old_state TEXT,
    new_state TEXT NOT NULL,
    changed_at_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reason TEXT NOT NULL
);

CREATE INDEX idx_pattern_transitions_pattern
    ON pattern_transitions(pattern_id, changed_at_utc);

CREATE TABLE scan_runs (
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
    error_summary TEXT,
    warning_summary TEXT
);

CREATE INDEX idx_scan_runs_interval_started
    ON scan_runs(interval, started_at_utc DESC);

CREATE TABLE scanner_heartbeat (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    status TEXT NOT NULL,
    process_id INTEGER NOT NULL,
    started_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL,
    next_wake_at_utc TEXT,
    last_run_id INTEGER REFERENCES scan_runs(id),
    message TEXT
);

CREATE TABLE alert_rules (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    minimum_score REAL NOT NULL CHECK (minimum_score BETWEEN 0 AND 100),
    required_state TEXT NOT NULL DEFAULT 'confirmed',
    pattern_types_json TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL
);

CREATE TABLE pattern_mutes (
    pattern_id TEXT PRIMARY KEY REFERENCES patterns(id) ON DELETE CASCADE,
    muted_at_utc TEXT NOT NULL,
    reason TEXT NOT NULL
);

CREATE TABLE alert_events (
    id INTEGER PRIMARY KEY,
    fingerprint TEXT NOT NULL UNIQUE,
    rule_id INTEGER NOT NULL REFERENCES alert_rules(id),
    transition_id INTEGER NOT NULL REFERENCES pattern_transitions(id),
    pattern_id TEXT NOT NULL REFERENCES patterns(id) ON DELETE CASCADE,
    symbol_id INTEGER NOT NULL REFERENCES symbols(id) ON DELETE CASCADE,
    provider_symbol TEXT NOT NULL,
    interval TEXT NOT NULL,
    pattern_type TEXT NOT NULL,
    direction TEXT NOT NULL,
    state TEXT NOT NULL,
    score REAL NOT NULL,
    event_at_utc TEXT NOT NULL,
    boundary_price REAL NOT NULL,
    target_price REAL,
    app_link TEXT NOT NULL,
    created_at_utc TEXT NOT NULL,
    acknowledged_at_utc TEXT
);

CREATE INDEX idx_alert_events_unread
    ON alert_events(acknowledged_at_utc, created_at_utc DESC);

CREATE INDEX idx_alert_events_pattern
    ON alert_events(pattern_id, created_at_utc DESC);
