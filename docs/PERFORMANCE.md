# Performance baselines

These are development-machine smoke baselines, not production guarantees.

## 2026-07-04 — Horizontal breakout milestone

- Python: 3.13.9
- Input: 500 cached daily `THYAO.IS` candles
- Confirmed-pivot extraction: 250 passes in 10.424 seconds; 41.70 ms average
- Complete horizontal breakout scan: 100 passes in 4.140 seconds; 41.40 ms average

Pivot extraction dominates the current detector runtime. This is already comfortably below the
latency relevant to daily, hourly, and 15-minute closed-candle scans, so readability remains more
valuable than optimization at this stage.

## 2026-07-04 — Double-pattern milestone

- Input: 500 cached daily `THYAO.IS` candles
- Double-top/bottom scan: 100 passes in 4.387 seconds; 43.87 ms average

The breakout and double-pattern detectors currently calculate pivots independently. Sharing that
calculation is a possible later optimization, but the present separation keeps each detector easy
to test and understand.

