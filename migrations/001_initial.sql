CREATE TABLE IF NOT EXISTS symbols (
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

CREATE INDEX IF NOT EXISTS idx_symbols_display_symbol
    ON symbols(display_symbol);

CREATE INDEX IF NOT EXISTS idx_symbols_bist_active
    ON symbols(is_bist, is_active);

CREATE TABLE IF NOT EXISTS candles (
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

CREATE INDEX IF NOT EXISTS idx_candles_chart
    ON candles(symbol_id, interval, opened_at_utc DESC);

