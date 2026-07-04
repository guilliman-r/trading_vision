# Trading Vision

Trading Vision is a local-first Python application for interactive financial charts and
explainable chart-pattern alerts. The current milestone provides a working chart, BIST-aware
symbol search, generic Yahoo Finance symbols, local candle caching, visible data freshness, and
closed-candle horizontal breakout detection.

See the complete [implementation plan](IMPLEMENTATION_PLAN.md).

## Requirements

- Python 3.12 or 3.13
- Internet access for fresh Yahoo Finance data

## Install

```bash
/opt/anaconda3/bin/python3.13 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e '.[dev]'
```

## Run

```bash
.venv/bin/trading-vision
```

Open <http://127.0.0.1:8050>. The first symbol load may take a few seconds; subsequent loads
use the local SQLite cache when fresh enough.

## Pattern engine

The first detector finds repeated horizontal resistance and support levels. It:

- uses locally confirmed pivots and records when each pivot became knowable;
- analyzes completed candles only;
- labels patterns as forming, confirmed, invalidated, or expired;
- scores geometry, prominence, duration, touches, breakout strength, and volume;
- draws the level, touch points, confirmation, target, and invalidation on the chart;
- stores stable pattern IDs and immutable state transitions in SQLite.

The pattern engine also detects double tops and double bottoms from confirmed three-pivot
structures. It requires explicit endpoint similarity, formation depth, leg spacing, and buffered
neckline confirmation. See [pattern definitions](docs/PATTERNS.md) for diagrams and formulas.

Scores describe how closely a chart matches the configured geometric rules. They are not a
probability of profit.

Configuration is optional. Copy `config.example.toml` to `config.toml`, then edit its plain
TOML values. Environment variables `TV_DATABASE_PATH`, `TV_HOST`, and `TV_PORT` override the
matching settings.

## Refresh the BIST catalog

The committed catalog is generated from KAP's BIST Companies page:

```bash
.venv/bin/python scripts/refresh_bist_symbols.py
```

The source list includes KAP member codes as well as listed equity codes. The application keeps
the raw catalog provenance and handles unavailable Yahoo symbols as visible provider errors.
Provider validation and an equity-only review are tracked in the implementation plan.

## Test and format

```bash
.venv/bin/ruff format .
.venv/bin/ruff check .
.venv/bin/pytest
```

## Data limitations

`yfinance` is an unofficial source intended for personal research. It can be delayed, incomplete,
or temporarily unavailable, and Yahoo limits intraday history. This project does not place trades
and is not financial advice.
