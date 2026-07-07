CREATE TABLE IF NOT EXISTS drawings (
    id INTEGER PRIMARY KEY,
    symbol_id INTEGER NOT NULL REFERENCES symbols(id) ON DELETE CASCADE,
    interval TEXT NOT NULL,
    drawing_type TEXT NOT NULL,
    shape_json TEXT NOT NULL,
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_drawings_symbol_interval
    ON drawings(symbol_id, interval, updated_at_utc DESC);
