CREATE TABLE IF NOT EXISTS alert_rules (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    minimum_score REAL NOT NULL CHECK (minimum_score BETWEEN 0 AND 100),
    required_state TEXT NOT NULL DEFAULT 'confirmed',
    pattern_types_json TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pattern_mutes (
    pattern_id TEXT PRIMARY KEY REFERENCES patterns(id) ON DELETE CASCADE,
    muted_at_utc TEXT NOT NULL,
    reason TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS alert_events (
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

CREATE INDEX IF NOT EXISTS idx_alert_events_unread
    ON alert_events(acknowledged_at_utc, created_at_utc DESC);

CREATE INDEX IF NOT EXISTS idx_alert_events_pattern
    ON alert_events(pattern_id, created_at_utc DESC);
