CREATE TABLE IF NOT EXISTS patterns (
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

CREATE INDEX IF NOT EXISTS idx_patterns_symbol_interval
    ON patterns(symbol_id, interval, state, last_seen_at_utc DESC);

CREATE INDEX IF NOT EXISTS idx_patterns_recent
    ON patterns(state, pattern_type, confirmed_at_utc DESC);

CREATE TABLE IF NOT EXISTS pattern_transitions (
    id INTEGER PRIMARY KEY,
    pattern_id TEXT NOT NULL REFERENCES patterns(id) ON DELETE CASCADE,
    old_state TEXT,
    new_state TEXT NOT NULL,
    changed_at_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reason TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_pattern_transitions_pattern
    ON pattern_transitions(pattern_id, changed_at_utc);

