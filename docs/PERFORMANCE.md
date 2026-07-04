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

