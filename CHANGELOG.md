# Changelog

## 0.33.0 — 2026-07-07

- Add `trading-vision-config` to print effective non-secret runtime settings.
- Keep config output behind an explicit public setting allowlist.
- Add regression tests to ensure unrelated environment secrets are not printed.
- Mark `TV-0210` complete in the implementation checklist.

## 0.32.0 — 2026-07-07

- Add a pull-request template with the project safety, local-first, migration, testing, and
  documentation checklist.
- Mark `TV-0112` complete in the implementation checklist.

## 0.31.0 — 2026-07-07

- Add a direct fresh-database smoke test covering every repository module.
- Document the repository-to-test coverage map.
- Mark `TV-0312` complete in the implementation checklist.

## 0.30.0 — 2026-07-07

- Add an additive `drawings` table for saved chart annotations.
- Add a `Drawing` value object and drawing repository save, list, update, delete, and delete-all
  helpers.
- Add tests for drawing persistence, validation, and symbol-delete cascade behavior.
- Document drawing persistence as storage-only until the later UI drawing milestone.
- Mark `TV-0311` complete in the implementation checklist.

## 0.29.0 — 2026-07-07

- Add `trading-vision-db backup --output ...` using SQLite's backup API.
- Add `trading-vision-db stats` with schema version, database size, and table row counts.
- Keep the existing no-argument database command as the initialize/default action.
- Add regression tests for backup integrity and database stats output.
- Mark `TV-0314` and `TV-0315` complete in the implementation checklist.

## 0.28.0 — 2026-07-07

- Fix CI formatting by applying `ruff format` output for the files reported by GitHub Actions.
- Add the `asset_type` symbol column through an additive migration.
- Persist and load symbol asset type through catalog import, repositories, scanner queries, and
  watchlist items.
- Mark BIST catalog rows as `equity` in the generated CSV snapshot.
- Mark `TV-0401` complete in the implementation checklist.

## 0.27.0 — 2026-07-07

- Add a committed SQLite schema fixture representing the database before watchlist/settings tables.
- Test that the migration runner upgrades the committed fixture to the current schema.
- Verify the upgrade records every committed migration and creates watchlist/settings tables.
- Mark `TV-0313` complete in the implementation checklist.

## 0.26.0 — 2026-07-07

- Add an additive migration for watchlists, ordered watchlist items, and simple app settings.
- Complete the core persistence schema across committed migrations without rewriting existing
  migration history.
- Add typed watchlist and watchlist-item value objects.
- Add repository operations to create, list, add, reorder, and remove watchlist items.
- Limit watchlist scanner intervals to `1d`, `1h`, and `15m`.
- Add fresh SQLite tests for watchlist creation, ordering, compaction, and validation.
- Mark `TV-0302` and `TV-0309` complete in the implementation checklist.

## 0.25.0 — 2026-07-07

- Add a version 1 product contract covering local single-user scope, no authentication, and no
  order placement.
- Add a glossary for candle, pivot, pattern candidate, confirmation, invalidation, expiration, and
  alert.
- Define first scanner intervals as `1d`, `1h`, and `15m`.
- Keep `5m` as a manual chart interval while rejecting it in scanner configuration and CLI choices.
- Document closed-candle semantics with a concrete 15-minute BIST example.
- Record detector order and conservative BIST scan policy.
- Mark Phase 0 product-contract checklist items complete.

## 0.24.0 — 2026-07-07

- Add shared logging setup for console and rotating local file output.
- Add configurable log path and log level settings.
- Stamp UI and scanner log lines with a process label.
- Include scanner `run_id` in scanner cycle log entries.
- Wire logging into the UI and scanner command entry points.
- Add tests for logging configuration, file output, process labels, and scanner run identifiers.
- Mark `TV-0205` and `TV-0206` complete in the implementation checklist.

## 0.23.0 — 2026-07-07

- Add a typed frozen `Candle` model matching the project OHLCV contract.
- Validate candle timezone awareness, positive prices, OHLC consistency, and non-negative volume.
- Add model construction tests for candles, symbols, pivots, pattern matches, and alert events.
- Confirm domain models stay free of database and UI behavior.
- Mark `TV-0207`, `TV-0208`, and `TV-0209` complete in the implementation checklist.

## 0.22.0 — 2026-07-07

- Add an explicit `timezone` setting with `Europe/Istanbul` as the default.
- Validate configured timezones at startup using the standard-library `zoneinfo` database.
- Document the timezone field in `config.example.toml`.
- Add tests for valid and invalid timezone configuration.
- Mark `TV-0204` complete in the implementation checklist.

## 0.21.0 — 2026-07-07

- Keep the documented default server bind address on loopback-only `127.0.0.1`.
- Add a startup warning when the unauthenticated local app is bound to a non-loopback host.
- Document the host-setting safety tradeoff in `config.example.toml`.
- Add tests for loopback and non-loopback host warning behavior.
- Mark `TV-1708` and `TV-1709` complete in the implementation checklist.

## 0.20.0 — 2026-07-07

- Add a schema-version helper that reports the latest applied SQLite migration and total count.
- Show the Trading Vision application version in scanner diagnostics.
- Show the database schema version in scanner diagnostics.
- Add regression tests for migration-version reporting and visible diagnostics.
- Mark `TV-1804` complete in the implementation checklist.

## 0.19.0 — 2026-07-07

- Add repository helpers to list active symbols with optional BIST filtering.
- Add a safe symbol inactive marker that keeps historical candles and patterns intact.
- Add date-bounded candle range queries for focused chart and future diagnostics work.
- Add latest-candle lookup for status and health checks without reloading full chart windows.
- Add fresh SQLite tests for active/inactive symbol behavior and candle range/latest queries.
- Mark `TV-0304` and `TV-0306` complete in the implementation checklist.

## 0.18.0 — 2026-07-07

- Add focused scanner result links with `range_from` and `range_to` chart context.
- Open charts around the selected pattern window instead of only loading the symbol and interval.
- Keep invalid, missing, or mismatched range parameters harmless by falling back to the normal
  recent-candles viewport.
- Include the same focused chart link in scanner CSV exports.
- Mark `TV-1503` complete in the implementation checklist.
- Add chart-focus and scanner-link regression tests.

## 0.17.0 — 2026-07-06

- Load previously fetched chart candles from SQLite during ordinary symbol and interval changes.
- Reserve the Refresh button for explicit Yahoo Finance network requests.
- Reduce repeat 1H switches from provider-bound waits to local cache and detector work.
- Align BIST hourly completion, scanner scheduling, gap checks, and chart range breaks with Yahoo's
  half-hour candle timestamps.
- Treat the final 17:30 hourly candle as complete at the 18:00 exchange data close plus provider
  delay.
- Replace hundreds of false hourly gap warnings with the actual missing provider bars.
- Label locally restored chart results as `Cached` while retaining the independent freshness state.
- Add hourly phase, final-bar, scanner wake, gap, cache-reuse, and range-break regression tests.

## 0.16.0 — 2026-07-06

- Centralize BIST candle-completion decisions in one calendar-aware function.
- Keep daily candles forming until the exchange data close plus provider delay.
- Keep intraday candles forming until their interval boundary plus provider delay.
- Resolve pre-open, weekend, holiday, and half-day completion through the maintained calendar.
- Use identical completion flags in chart loads, cached fallback data, and scanner jobs.
- Show a `forming candle` label above the chart when the newest BIST bar is still open.
- Add daily, intraday, provider-delay, weekend, market-service, scanner, and UI tests.

## 0.15.0 — 2026-07-05

- Add a configurable short in-process cooldown for identical UI chart loads.
- Reuse the complete chart result, including detector output, without reopening SQLite or Yahoo.
- Serialize concurrent requests for the same symbol and interval so only one provider call runs.
- Treat BIST display and `.IS` provider symbols as the same cooldown key.
- Keep different symbols and intervals independent.
- Make the Refresh button explicitly bypass the cooldown.
- Add expiry, forced refresh, interval isolation, concurrency, settings, and Dash callback tests.

## 0.14.0 — 2026-07-05

- Classify invalid timestamps, duplicates, missing/non-numeric prices, non-positive prices,
  inconsistent OHLC values, non-numeric volume, and negative volume.
- Quarantine invalid rows while retaining valid provider candles unchanged.
- Carry structured input, valid, quarantined, and per-reason counts through provider and chart
  service boundaries.
- Display quarantine counts in chart metadata and a reasoned instrument warning.
- Persist scanner quality warnings separately from failures so successful scans remain successful.
- Add a migration and diagnostics card for recent scanner quality warnings.
- Add clean, malformed, all-invalid, cache-boundary, scanner, persistence, diagnostics, and UI
  regression tests.

## 0.13.0 — 2026-07-05

- Detect missing daily and intraday candles inside valid BIST sessions.
- Exclude weekends, configured holidays, half-day closures, and out-of-range endpoints.
- Restrict gap judgments to years backed by a committed exchange-calendar file.
- Preserve source OHLCV exactly; gap detection never creates replacement candles.
- Show gap counts in chart metadata and a plain warning in instrument details.
- Add daily, weekend, holiday, intraday, uncovered-year, and end-to-end UI tests.

## 0.12.0 — 2026-07-05

- Compress BIST chart timelines using the maintained exchange-session calendar.
- Hide weekends and official full-day holidays without inventing or deleting candle data.
- Hide the regular 18:00–10:00 BIST intraday closure on intraday charts.
- Hide the non-trading remainder after configured BIST half-day closes.
- Apply identical range breaks to the synchronized price and volume axes.
- Leave arbitrary Yahoo symbols untouched because their exchange calendars are not yet modeled.
- Add weekend, holiday, overnight, half-day, BIST-only, and synchronized-axis tests.

## 0.11.0 — 2026-07-05

- Add explicit post-boundary freshness grace windows for every supported interval.
- Reuse the BIST session calendar to distinguish current closed-market data from a stale feed.
- Avoid guessing freshness for arbitrary Yahoo symbols whose exchange calendar is unavailable.
- Show data source, latest candle time in Istanbul, and freshness state directly above the chart.
- Add a complete candle hover summary with timestamp, OHLC, absolute change, percentage change,
  and volume.
- Add calendar, grace-window, generic-symbol, callback metadata, and hover-content tests.

## 0.10.0 — 2026-07-05

- Populate the chart symbol typeahead from every active symbol in SQLite.
- Show ticker and company name together while submitting the unambiguous display ticker.
- Preserve free-form entry for arbitrary Yahoo Finance symbols outside the catalog.
- Normalize Turkish characters only for matching so ASCII searches find official Turkish names
  without altering stored or displayed company data.
- Prioritize exact display/provider tickers ahead of prefix and company-name matches.
- Remove duplicate visible suggestions when legacy generic and curated BIST records share a ticker.
- Add repository and rendered-layout tests for search fields, inactive rows, Turkish normalization,
  database population, and BIST preference.

## 0.9.0 — 2026-07-05

- Replace the all-history overlay pile-up with a small actionable chart set.
- Show forming patterns and confirmations from the latest 40 completed candles only.
- Hide invalidated, expired, stale confirmed, and overlapping same-family candidates.
- Prefer forming patterns and cap the visible set at three overlays.
- Stop confirmed fitted boundaries at confirmation instead of projecting them indefinitely.
- Draw target and invalidation guides only after confirmation and hide forming targets.
- Base the initial price scale on visible candle highs and lows so overlay estimates cannot flatten
  the chart.
- Open charts on the latest 180 candles while preserving normal zoom and pan controls.
- Add selection, extrapolation, reference-line, scale, and viewport regression tests.

## 0.8.0 — 2026-07-05

- Add a full-width scanner operations workspace below the interactive chart.
- Add server-side symbol, interval, pattern, direction, state, score, and age filters.
- Link every persisted result back to its symbol and interval chart context.
- Show score-reason previews with native expandable full explanations in each result row.
- Add CSV export that uses the exact active server-side filters.
- Display heartbeat, next wake, last run duration/counts, database path/size, package versions,
  provider run state, and recent scanner errors.
- Use a plain HTML table rather than adopting Dash's deprecated built-in DataTable.
- Add repository, SQL-binding, CSV, diagnostics, rendering, and callback tests.
- Record Telegram as explicitly excluded from the external notification roadmap.

## 0.7.0 — 2026-07-04

- Add configurable in-app alert rules evaluated only for newly persisted pattern transitions.
- Enable recent confirmed horizontal breakouts by default while keeping ambiguous detectors off.
- Add stable alert fingerprints and database uniqueness so rescans and restarts cannot duplicate.
- Create pattern transitions and matching alert events in the same SQLite transaction.
- Suppress stale historical confirmations while preserving forming-pattern catch-up alerts.
- Add an unread counter, recent alert cards, chart context links, acknowledge-all, and mute actions.
- Include symbol, interval, type, direction, state, score, event time, boundary, target, and app link.
- Add a replaceable notification adapter contract without enabling an external delivery channel.
- Add lifecycle, threshold, mute, inactive-rule, rollback, restart, fingerprint, and Dash tests.

## 0.6.0 — 2026-07-04

- Add a standalone scanner with continuous, one-shot, forced, limited-universe, and dry-run modes.
- Add a one-process file lock, graceful `SIGINT`/`SIGTERM` shutdown, and boundary-aware sleeping.
- Add data-driven BIST normal-day, weekend, holiday, and half-day scheduling for 2026.
- Catch up missing history, bound detector input, and isolate every provider/symbol failure.
- Persist scan-run counts, concise errors, and a scanner heartbeat visible in the UI on page load.
- Mark BIST daily candles complete after the verified exchange session close.
- Add fake-provider end-to-end worker, calendar, lock, partial-failure, dry-run, and UI tests.
- Record a 713-symbol local dry-pipeline baseline without making Yahoo part of automated tests.

## 0.5.0 — 2026-07-04

- Add ascending, descending, and symmetrical triangle detection from confirmed four-pivot shapes.
- Fit separate upper and lower boundaries and reject parallel, diverging, and passed-apex shapes.
- Add buffered two-direction breakouts, invalidation, expiry, score reasons, and measured targets.
- Render both fitted boundaries, all touches, the projected apex, confirmation, and risk levels.
- Preserve stable identities as forming triangles become confirmed and persist each state change.
- Add synthetic positive, mirrored, false-channel, no-leakage, lifecycle, chart, and persistence tests.
- Review default behavior across six cached BIST histories and document its overlapping candidates.

## 0.4.0 — 2026-07-04

- Add standard and inverse head-and-shoulders detection from confirmed five-pivot structures.
- Fit and enforce a sloped neckline with a percentage-per-candle slope limit.
- Add shoulder price/time symmetry, head prominence, duration, breakout, and volume scoring.
- Add forming, confirmed, invalidated, and expired states with measured targets.
- Extend fitted necklines correctly on the chart and stop invalidated lines at invalidation time.
- Add standard, inverse, timing, prominence, slope, invalidation, persistence, and leakage tests.
- Review default detector behavior across six cached BIST daily histories.

## 0.3.0 — 2026-07-04

- Add double-top and double-bottom detection from confirmed pivot triples.
- Add buffered neckline confirmation, pre-confirmation invalidation, expiry, and measured targets.
- Add transparent price symmetry, time symmetry, prominence, depth, breakout, and volume scores.
- Preserve raw same-kind pivots for time-forward invalidation evaluation.
- Render peaks, troughs, reaction highs, necklines, confirmations, targets, and invalidations.
- Add forming, confirmation-timing, false-break, shallow, wide, mirrored, and persistence tests.
- Review default behavior on six cached BIST daily histories and record the results.

## 0.2.1 — 2026-07-04

- Fix Dash callbacks reusing a SQLite connection created in another thread.
- Open one short-lived connection inside each callback and close it deterministically.
- Add explicit transaction commit/rollback behavior around connection scopes.
- Add a regression test that executes a chart callback on a different thread.

## 0.2.0 — 2026-07-04

- Add true range, ATR, line, volume-ratio, and confirmed-pivot calculations.
- Add explainable horizontal resistance-breakout and support-breakdown detection.
- Add forming, confirmed, invalidated, and expired pattern states.
- Add stable pattern identities and immutable SQLite transition history.
- Add chart overlays for levels, touches, confirmations, targets, and invalidations.
- Add plain-language pattern scores and reasons to the instrument panel.
- Add synthetic, no-future-leakage, persistence, and mirrored bearish tests.
- Prefer curated BIST symbols over generic symbols with the same display code.

## 0.1.0 — 2026-07-03

- Initialize the clean Python project and Git repository.
- Add the official-source KAP/BIST symbol catalog snapshot.
- Add SQLite migrations and local OHLCV caching.
- Add a replaceable Yahoo Finance provider with explicit adjusted prices.
- Add the first Dash/Plotly chart workspace with candlesticks and volume.
- Add BIST quick access, arbitrary Yahoo symbols, intervals, refresh, and theme controls.
- Add data-quality, repository, service, UI endpoint, and callback tests.
