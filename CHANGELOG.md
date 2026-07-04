# Changelog

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
