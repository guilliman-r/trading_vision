# Head-and-shoulders BIST review

Review date: 2026-07-04  
Source: locally cached adjusted Yahoo Finance daily candles  
Window: 500 candles per symbol  
Detector: `head-shoulders-v1` with committed defaults

## Summary

| Symbol | Matches | Confirmed | Invalidated | Expired | Score range |
|---|---:|---:|---:|---:|---:|
| THYAO | 1 | 0 | 0 | 1 | — |
| GARAN | 0 | 0 | 0 | 0 | — |
| ASELS | 1 | 0 | 1 | 0 | 27.0 |
| TUPRS | 0 | 0 | 0 | 0 | — |
| BIMAS | 1 | 1 | 0 | 0 | 66.6 |
| EREGL | 1 | 0 | 1 | 0 | 42.1 |
| **Total** | **4** | **1** | **2** | **1** | **27.0–66.6** |

## Review notes

- The five-pivot and head-prominence requirements are deliberately selective: only four patterns
  appeared across 3,000 inspected candles.
- BIMAS produced the only confirmed default match, an inverse head-and-shoulders scoring 66.6.
- The low-scoring ASELS and EREGL invalidations remain stored for audit but rank below stronger
  forming/confirmed candidates in the detail panel.
- The review found and fixed a state-value bug: an invalidated sloped neckline was initially
  extrapolated to the final chart candle. Invalidated patterns now stop at the invalidation candle.
- Default tolerances remain unchanged. Alerts for this detector must stay disabled until frozen,
  manually labeled real examples are reviewed.

This is detector-quality review, not evidence of profitability or financial advice.

