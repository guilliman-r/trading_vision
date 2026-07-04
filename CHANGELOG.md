# Changelog

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
