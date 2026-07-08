# Scanner results and diagnostics

The operations workspace sits below the interactive chart. It reads persisted SQLite results; it
does not rerun detectors or call Yahoo when filters change.

## Filters

Every filter is applied in the repository query with bound SQL values:

- symbol substring;
- exact interval;
- exact pattern type;
- bullish, bearish, or neutral direction;
- forming, confirmed, invalidated, or expired state;
- minimum score from 0–100;
- last 7, 30, or 90 days, or all history.

Results are ordered by confirmation/current observation time and score. The UI returns at most 500
rows to keep rendering bounded. CSV export uses the identical filter object and is capped by
`scanner.export_limit`, which cannot exceed 2,000 rows. Filters never interpolate user-entered
values into SQL.

## Result rows

Each row shows symbol, interval, pattern, direction, state, score, confirmation/start time,
boundary, target, and the first score reason. Expand `Reasons` to inspect the full explainable score
without opening source code. `Open` navigates through the same application URL contract used by
alerts and loads the corresponding symbol, interval, and a focused date range around the pattern.
If the range parameters are missing or malformed, the chart safely falls back to the normal recent
candles viewport.

Rows are immutable result views over the current `patterns` state. Historical state changes remain
in `pattern_transitions`; the table does not erase audit history.

## CSV export

`Export CSV` downloads `trading-vision-patterns.csv` with:

- symbol, interval, pattern type, direction, state, and score;
- start and confirmation timestamps in UTC;
- boundary, target, and invalidation prices;
- all reasons joined into one field;
- local chart context link with symbol, interval, pattern id, and focused date range.

CSV generation happens server-side from the current filters, not from whichever rows happen to be
visible in the browser.

## Diagnostics

The diagnostic cards refresh with the result table every 30 seconds and include:

- Trading Vision application version;
- current SQLite schema migration version;
- current scanner heartbeat and update timestamp;
- next scheduled wake;
- latest interval run, terminal status, and duration;
- last success/failure counts;
- absolute SQLite path and file size;
- last provider run status without making a new health request;
- Python, Dash, Plotly, pandas, NumPy, and yfinance versions;
- concise errors from the newest failed/partial runs.

Provider status is deliberately based on persisted scanner evidence. Opening the diagnostics view
does not create a hidden Yahoo request.

## Scope

This milestone is read-only apart from CSV download. Detector settings forms, watchlist management,
retention controls, and reset-to-default actions remain separate roadmap tasks. Telegram is not in
scope and is explicitly excluded from the project.
