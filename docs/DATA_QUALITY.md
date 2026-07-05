# Provider row validation and quarantine

Every fetched row passes explicit validation before it can enter SQLite or a pattern detector.
Invalid rows are removed from the prepared frame and summarized in a structured quality report.
Trading Vision never repairs an invalid market price by guessing a replacement value.

## Issue categories

- invalid timestamp;
- duplicate timestamp, where the last supplied row is retained;
- missing or non-numeric OHLC price;
- zero or negative OHLC price;
- high below an open, close, or low value;
- low above an open, close, or high value;
- non-numeric supplied volume;
- negative volume.

One quarantined row may have more than one reason, so reason counts can exceed the number of
quarantined rows. Missing volume remains allowed because some Yahoo instruments do not publish it.

## Successful partial fetch

If at least one row is valid, valid rows continue through caching and detection. The chart metadata
adds a count such as `2 quarantined rows`, and instrument details list each reason. Invalid rows are
neither cached nor scanned.

If every row is invalid, the provider result fails with the same report attached. Existing cached
data may still be shown with a visible provider warning.

## Scanner diagnostics

Background scans store quality summaries in `scan_runs.warning_summary`, separate from provider
errors. A symbol with usable data remains a successful scan; the operations workspace displays the
quality summary under **Recent warnings**. This separation prevents a partial-quality fetch from
inflating the scanner failure count.

The pure normalization entry point is `prepare_candles_with_report` in
`trading_vision/data_quality.py`. The original `prepare_candles` helper remains as a compact wrapper
for callers that only need the valid frame.
