# BIST candle-gap detection

Trading Vision checks whether an expected completed candle is absent inside a valid BIST trading
session. Gap detection reports data-quality risk; it never generates a replacement candle.

## Daily candles

For daily data, the detector compares local trading dates between the first and last completed
candle. Weekends and full-day closures from the BIST calendar are not expected and therefore are
not gaps.

## Intraday candles

For `5m` and `15m` data, expected candle openings begin at the configured session open. Yahoo's
BIST `1h` feed instead uses half-hour labels from `09:30` through `17:30`, so gap checks use that
same provider grid. Half-day closing times are honored. Only missing intervals between the first
and last loaded candle are reported; trailing freshness is handled separately by the freshness
evaluator.

## Calendar coverage

A year is evaluated only when a committed BIST calendar file supplies its holiday overrides. This
prevents ordinary historical holidays from being mislabeled when the repository does not yet have
that year's official calendar. Add a reviewed `data/calendars/bist_YYYY.csv` file to extend
coverage.

## User interface

When gaps exist, the chart heading adds a count such as `2 data gaps`. The instrument panel also
warns that pattern results may be incomplete. A clean result produces no extra visual noise.

The implementation in `trading_vision/candle_gaps.py` is pure and read-only. It receives a candle
frame and returns expected timestamps that are absent; it does not modify the frame or database.
