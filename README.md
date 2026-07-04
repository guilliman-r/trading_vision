# Trading Vision

Trading Vision is a local-first Python application for interactive financial charts and
explainable chart-pattern alerts. The current milestone provides a working chart, BIST-aware
symbol search, generic Yahoo Finance symbols, local candle caching, and visible data freshness.

Pattern detection is the next milestone. See the complete [implementation plan](IMPLEMENTATION_PLAN.md).

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

