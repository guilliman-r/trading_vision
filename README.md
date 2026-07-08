# Trading Vision

Trading Vision is a local-first Python application for interactive financial charts and
explainable chart-pattern alerts. The current milestone provides a working chart, BIST-aware
symbol search, generic Yahoo Finance symbols, local candle caching, visible data freshness, and
closed-candle horizontal breakout, reversal, and triangle detection, plus a separate scanner
process for continuous BIST monitoring.

See the complete [implementation plan](IMPLEMENTATION_PLAN.md).
See the version 1 [product contract](docs/PRODUCT_CONTRACT.md) and
[glossary](docs/GLOSSARY.md) for operating boundaries and domain terms. For day-to-day running,
updates, backup, and restore, use the [operations guide](docs/OPERATIONS.md).

## Requirements

- Python 3.12 or 3.13
- Internet access for fresh Yahoo Finance data

Version 1 is local and single-user. It has no authentication and never places orders.

## Install

```bash
/opt/anaconda3/bin/python3.13 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e '.[dev]'
```

## Run the UI

```bash
.venv/bin/trading-vision-ui
```

Open <http://127.0.0.1:8050>. The shorter `.venv/bin/trading-vision` command is kept as a
backward-compatible UI alias. The first symbol load may take a few seconds. Downloaded candles are
stored in SQLite and remain available as a visible fallback when the provider fails.

Identical chart requests made within the short provider cooldown reuse the in-process result so UI
callbacks do not repeatedly call Yahoo or rescan the same candles. **Refresh** always bypasses the
cooldown. See the [provider request guide](docs/PROVIDER_REQUESTS.md).

## Find a symbol

Start typing a BIST ticker or company name in the top symbol field and choose a suggestion. The
list comes from active symbols in SQLite and includes the full committed BIST catalog. Turkish and
plain-ASCII spellings match the same company without changing its official displayed name.

The field is still free-form: enter any Yahoo Finance ticker such as `AAPL`, `MSFT`, or `BTC-USD`
and press Enter or **Load**. Known BIST display codes resolve to their `.IS` provider symbols.
See the [symbol search guide](docs/SYMBOL_SEARCH.md) for matching and duplicate rules.

## Read the chart

The line below the symbol name identifies the data source, latest candle time in Istanbul, and
whether BIST data is current, stale, or simply unchanged because the market is closed. Freshness
uses the maintained BIST calendar and interval-specific provider grace windows. Non-BIST symbols
are not judged against BIST trading hours.

If Yahoo supplies the currently open BIST bar, the chart keeps it visible but labels it
`forming candle`. Detectors ignore it until the proper exchange boundary and provider delay have
passed. See the [candle-completion guide](docs/CANDLE_COMPLETION.md).

Ordinary symbol and interval changes reuse SQLite candles immediately when available. The
**Refresh** button explicitly asks Yahoo for new candles, so revisiting the 1H chart does not block
the interface on a repeated provider request.

Hover over a candle to see its timestamp, open, high, low, close, absolute and percentage change,
and volume in one compact summary. See the [freshness guide](docs/DATA_FRESHNESS.md) for the exact
states and thresholds.

BIST charts also compress known closed-market periods so price action is not separated by large
empty overnight, weekend, or holiday gaps. Price and volume remain synchronized, and no candle is
created or removed. See the [chart timeline guide](docs/CHART_TIMELINE.md).

Trading Vision separately checks for missing candles *inside* valid BIST sessions. A detected gap
appears beside the chart freshness status and as an instrument warning because pattern results may
then be incomplete. The application never fills a gap with invented prices. See the
[candle-gap guide](docs/CANDLE_GAPS.md).

Malformed provider rows are quarantined before caching or scanning. If any otherwise usable fetch
contains invalid rows, the chart shows the count and exact reason categories. Scanner runs retain
the same information as warnings without falsely marking a successful symbol as failed. See the
[data-quality guide](docs/DATA_QUALITY.md).

For a read-only coverage summary of stored candles, run
`.venv/bin/python scripts/check_data.py`.

## Run the scanner

Keep the UI running and start the worker in a second terminal:

```bash
.venv/bin/trading-vision-worker
```

It scans only jobs due after completed BIST candles, catches up stale symbols after a restart,
sleeps until the next relevant boundary, and stops cleanly with `Ctrl-C`. Start with a small,
non-persisting smoke run before requesting a large Yahoo universe:

```bash
.venv/bin/trading-vision-worker \
  --once --force --dry-run --max-symbols 5 --intervals 1d
```

To scan known symbols once and persist pattern transitions:

```bash
.venv/bin/trading-vision-worker \
  --once --force --symbols THYAO GARAN --intervals 1d
```

The left panel shows the last persisted scanner heartbeat when the page loads. Run counts and
concise per-symbol failures are stored in SQLite. See the [scanner operator guide](docs/SCANNER.md)
for scheduling rules, commands, configuration, and diagnostics.

To check local operational health from a terminal:

```bash
.venv/bin/trading-vision-health
```

The command exits nonzero when the database is missing or corrupt, the scanner heartbeat is missing
or stale, or the provider smoke request fails. Use `--skip-provider` for a purely local DB/scanner
check when you do not want to make a Yahoo request.

If you later want the scanner to start automatically after macOS login, use the optional
[LaunchAgent example](docs/LAUNCH_AGENT.md). It is documentation-only; nothing is installed by
default.

If you prefer containers, see the optional [Docker and Compose guide](docs/DOCKER.md) for UI and
scanner services that share the same local `var/` directory.

For monthly dependency review and pre-release audit steps, see the
[maintenance cadence](docs/MAINTENANCE.md).

## Alerts

Newly confirmed enabled patterns above the configured score create one deduplicated in-app alert.
The top bar shows the unread count; the right panel lists recent alerts with chart context,
acknowledge, acknowledge-all, and mute-pattern actions. By default only horizontal resistance and
support confirmations are enabled. Head-and-shoulders and triangles remain excluded until their
real-world validation backlog is complete.

See the [alert guide](docs/ALERTS.md) for freshness, deduplication, configuration, and safety rules.
Telegram is intentionally excluded. No external delivery channel is currently enabled.

## Scanner results and diagnostics

Scroll below the chart to inspect persisted detections across the scanned universe. The operations
workspace filters by symbol, interval, pattern, direction, state, score, and age. Every row links
back to its chart with a focused pattern date range and expands to show all score reasons. CSV
export uses the active filters.

The same workspace shows scanner heartbeat, next wake time, latest run duration and success/failure
counts, database path and size, package versions, provider run state, and recent errors. See the
[scanner results guide](docs/SCANNER_RESULTS.md).

Watchlist tables and repository operations are available for saved symbol groups. Full management
controls are still a later UI task. See the [watchlist guide](docs/WATCHLISTS.md).

Drawing persistence is also available at the repository layer. UI drawing tools are still tracked
as a later chart task. See the [drawing persistence guide](docs/DRAWINGS.md).

Repository modules are tested against fresh migrated SQLite databases. See the
[repository coverage note](docs/REPOSITORY_TEST_COVERAGE.md).

## Database utilities

Initialize the configured SQLite database:

```bash
.venv/bin/trading-vision-db
```

Print the schema version, database/WAL/SHM size, and row counts for every application table:

```bash
.venv/bin/trading-vision-db stats
```

Create a safe SQLite backup copy with the backup API:

```bash
.venv/bin/trading-vision-db backup --output var/trading_vision.backup.sqlite3
```

## Logs

The UI and scanner both write concise console logs and a rotating local file at
`var/trading_vision.log` by default. Each line includes the process label (`ui` or `scanner`), and
scanner cycle summaries include the persisted `run_id` for matching logs to diagnostics. Change the
path or level in the `[logging]` section of `config.toml`. Common token, password, API-key, and
Bearer fragments are redacted before messages reach console or file logs.

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

The chart intentionally shows only actionable geometry: every forming pattern and confirmations
from the latest 40 completed candles, deduplicated and limited to the three highest-priority
overlays. Invalidated, expired, and older confirmed patterns remain available in stored scanner
results but do not crowd the live chart. The initial price scale follows candle highs and lows,
not projected targets or extended trendlines.

Standard and inverse head-and-shoulders patterns use five confirmed pivots, shoulder and timing
symmetry, explicit head prominence, and a fitted sloped neckline. The chart extends a forming
neckline only through the current candle and stops a confirmed neckline at its confirmation
candle.

Ascending, descending, and symmetrical triangles use two confirmed touches on each fitted
boundary. The detector rejects parallel and diverging channels, requires a future apex, and marks
both trendlines, the projected apex, breakout, target, and invalidation on the chart. Triangle
alerts remain disabled until overlapping real-world candidates have been manually labeled.

Scores describe how closely a chart matches the configured geometric rules. They are not a
probability of profit.

Configuration is optional. Copy `config.example.toml` to `config.toml`, then edit its plain
TOML values. Environment variables `TV_DATABASE_PATH`, `TV_HOST`, and `TV_PORT` override the
matching settings.

To inspect the effective non-secret runtime configuration:

```bash
.venv/bin/trading-vision-config
```

## Refresh the BIST catalog

The committed catalog is generated from KAP's BIST Companies page:

```bash
.venv/bin/python scripts/refresh_bist_symbols.py
```

The source list includes KAP member codes as well as listed equity codes. The application keeps
the raw catalog provenance and handles unavailable Yahoo symbols as visible provider errors.
Version 1 targets ordinary listed equities and excludes ETFs, warrants, rights, funds, debt
instruments, and non-equity member codes from the active scan universe. See the
[BIST catalog policy](docs/BIST_CATALOG_POLICY.md). Provider validation and an equity-only review
are tracked in the implementation plan.

## Test and format

```bash
.venv/bin/ruff format .
.venv/bin/ruff check .
.venv/bin/pytest
```

## Troubleshooting

- `Another scanner owns .../scanner.lock`: another worker is active. Stop that process cleanly;
  do not delete the lock file while it is running.
- Yahoo errors or empty symbols: retry a small `--once --dry-run` selection. The worker records a
  partial run and continues past bad tickers.
- Non-loopback host warning: keep `host = "127.0.0.1"` for normal local use. `0.0.0.0` exposes the
  unauthenticated app to other devices on your network.
- Stale heartbeat in the UI: reload the page. Live scanner dashboards are tracked in Phase 15.
- No job fetched: due-job mode intentionally skips current candles; add `--force` for a manual run.

## Data limitations

`yfinance` is an unofficial source intended for personal research. It can be delayed, incomplete,
or temporarily unavailable, and Yahoo limits intraday history. This project does not place trades
and is not financial advice.
