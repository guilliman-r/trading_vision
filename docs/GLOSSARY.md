# Glossary

## Candle

A single OHLCV price bar for one symbol and interval. It has an opening time, open, high, low,
close, optional volume, source, adjustment flag, and completion flag. Trading Vision stores candle
times in UTC and converts to Istanbul time only for display and BIST session decisions.

## Pivot

A locally significant high or low confirmed by candles on both sides. The pivot's price occurred at
one candle, but it becomes knowable only after the right-side confirmation window closes.

## Pattern candidate

A geometric structure that matches a detector's formation rules but has not crossed its confirmation
boundary. In persisted scanner state this is usually called `forming`.

## Confirmation

The completed-candle event that crosses a detector's boundary with the configured buffer. A
confirmation records the boundary price, confirming time, score reasons, target estimate, and
invalidation level when available.

## Invalidation

The completed-candle event that violates a pattern's structure before or after confirmation. An
invalidated pattern remains in scanner history but is not shown as an actionable live overlay.

## Expiration

A pattern state used when a candidate stays unconfirmed beyond its allowed candle window. Expiration
is separate from invalidation because the structure may simply have become too old rather than
actively broken.

## Alert

An immutable in-app event created when a persisted pattern transition matches an enabled rule.
Alerts are deduplicated, can be acknowledged or muted, and do not place trades.
