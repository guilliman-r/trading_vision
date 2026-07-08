# Scanner operator guide

The scanner is a separate local process. It fetches due BIST candles, validates the provider
contract, upserts the cache, reads a bounded window, runs every enabled detector, and persists
pattern state transitions. One symbol failing never aborts the rest of the interval run.

The supported scanner intervals are currently `1d` and `1h`. Lower intraday intervals are deferred
until chart interaction, provider limits, and full-universe timing are measured safe.

## Start and stop

Continuous mode:

```bash
.venv/bin/python -m trading_vision.worker
```

Stop with `Ctrl-C` or `SIGTERM`. The worker finishes its current synchronous provider request,
writes a stopped heartbeat, releases `var/scanner.lock`, and exits. A second worker using the same
lock path refuses to start.

Small non-persisting smoke run:

```bash
.venv/bin/python -m trading_vision.worker \
  --once --force --dry-run --max-symbols 5 --intervals 1d
```

Selected stored symbols:

```bash
.venv/bin/python -m trading_vision.worker \
  --once --force --symbols THYAO GARAN --intervals 1d 1h
```

Options:

- `--once`: run one cycle and exit;
- `--force`: ignore due-state and request every selected job;
- `--dry-run`: cache prepared candles and execute detectors, but do not persist pattern transitions;
- `--symbols`: restrict work to known display/provider symbols;
- `--intervals`: override configured intervals;
- `--max-symbols`: cap the sorted universe for a safe smoke or timing run.

The default is all active committed BIST catalog entries on daily candles. Hourly scanning is
available but remains opt-in until provider-backed universe timing is measured.

## Scheduling rules

All decisions use timezone-aware timestamps. Storage remains UTC; exchange decisions use
`Europe/Istanbul`.

- Daily bars become eligible after the session closes plus `provider_delay_seconds`.
- Intraday bars become eligible after their exact boundary plus the same delay.
- A current job is not fetched again while BIST is closed.
- A missing or stale job is fetched once as catch-up even while the market is closed.
- After a cycle, continuous mode sleeps until the nearest configured daily or intraday boundary.
- Provider history requests return a window, so one catch-up request can fill multiple missing bars.
- Detection reads only `scanner_lookback_bars` from SQLite; the default is 500.

Normal continuous trading is modeled as 10:00–18:00 Istanbul time, with closing activity ending at
18:10. Half days use 10:00–12:30 and finish at 12:40. These times come from Borsa Istanbul's
[official equity-market session schedule](https://www.borsaistanbul.com/files/borsa-istanbul-equity-market-session-schedule-november-4-2019.pdf)
and its current [trading-hours page](https://www.borsaistanbul.com/en/markets/equity-market/trading-hours).

## Holiday maintenance

`data/calendars/bist_2026.csv` contains full closures and half-day overrides from the official
[2026 Equity Market holiday schedule](https://www.borsaistanbul.com/files/equity-market-2026-holiday-schedule.pdf).
The code reads every `bist_*.csv` file, so a new annual schedule can be added without changing
Python. This is a required annual maintenance task. Dates absent from an override file are treated
as normal weekdays; do not run a new calendar year unattended before adding its official file.

## Configuration

```toml
[scanner]
intervals = ["1d"]
batch_size = 25
export_limit = 2000
lookback_bars = 500
provider_delay_seconds = 60
lock_path = "var/scanner.lock"
```

Batch size is capped between 1 and 100. The Yahoo adapter uses batch downloads inside those
boundaries; provider failures are still recorded per symbol. Scanner lookback is capped between 350
and 5,000 candles. CSV export is capped by `export_limit`, with an absolute maximum of 2,000 rows.

## Diagnostics

Every interval cycle creates one `scan_runs` row with requested, succeeded, failed, candle, pattern
transition, status, and concise error counts. Status is:

- `completed`: no symbol failed, including a zero-due-job cycle;
- `partial`: at least one symbol succeeded and at least one failed;
- `failed`: every requested symbol failed;
- `running`: the row was created but has not reached a terminal update.

New confirmed transitions can create in-app alerts according to `config.toml`. `--dry-run` executes
detectors but persists neither pattern transitions nor alerts.

`scanner_heartbeat` is a one-row current status record containing process ID, start/update time,
next wake time, last run, and a short message. The UI reads it when the page loads.

Useful read-only checks:

```bash
sqlite3 var/trading_vision.sqlite3 \
  "SELECT id, interval, status, symbols_succeeded, symbols_failed FROM scan_runs ORDER BY id DESC LIMIT 5;"

sqlite3 var/trading_vision.sqlite3 \
  "SELECT status, updated_at_utc, next_wake_at_utc, message FROM scanner_heartbeat;"
```

Yahoo Finance is an unofficial personal-research source and can throttle a large universe. Test a
small dry run first. Partial failures are expected diagnostic outcomes, not reasons to discard the
successful symbols.

The dashboard's [scanner results workspace](SCANNER_RESULTS.md) exposes these runs, persisted
patterns, filters, CSV export, and diagnostics without requiring SQLite commands.
