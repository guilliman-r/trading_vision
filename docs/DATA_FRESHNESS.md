# Chart data freshness

The chart heading reports three facts together:

```text
Yahoo Finance · Latest 03 Jul 2026 · 00:00 · Market closed · data current
```

The timestamp is the candle's opening timestamp displayed in `Europe/Istanbul`.

## BIST states

Trading Vision compares the latest candle with the most recent candle that should be available
according to the maintained BIST session calendar:

- `Market open · data current`: the latest eligible interval is present during the session.
- `Market closed · data current`: no newer candle is expected outside the session.
- `Stale feed · market open`: an eligible in-session candle is missing after its grace window.
- `Stale feed · market closed`: the last completed session is still missing.

Weekends, configured holidays, and half days are handled by the same calendar used by the scanner.
The UI therefore does not label Friday's daily candle stale merely because it is viewed on Sunday.

## Grace windows

Yahoo may publish a completed candle shortly after its nominal boundary. The configured provider
delay is applied first, followed by this explicit per-interval freshness grace:

| Interval | Additional grace |
|---|---:|
| 5 minutes | 2 minutes |
| 15 minutes | 3 minutes |
| 1 hour | 5 minutes |
| 1 day | 15 minutes |

These values determine when the UI calls data stale; they do not alter candle prices or detector
timing. The constants live in `trading_vision/freshness.py` and have direct boundary tests.

## Other Yahoo symbols

Trading Vision does not yet maintain calendars for every exchange supported by Yahoo Finance.
Non-BIST symbols show `Exchange schedule unavailable` instead of borrowing BIST hours or making a
potentially false stale/current claim. Their source and latest timestamp remain visible.

## Candle hover

Each candlestick hover summary includes its Istanbul timestamp, OHLC prices, change from the prior
close, percentage change, and volume. The first loaded candle uses its open as the comparison base
because no earlier close exists in the chart frame.
