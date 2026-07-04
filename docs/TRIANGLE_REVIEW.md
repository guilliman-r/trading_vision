# Triangle BIST review

Review date: 2026-07-04
Source: locally cached adjusted Yahoo Finance daily candles
Window: 500 candles per symbol
Detector: `triangle-v1` with committed defaults

## Summary

| Symbol | Matches | Confirmed | Invalidated | Expired | Score range |
|---|---:|---:|---:|---:|---:|
| THYAO | 8 | 3 | 4 | 1 | 75.4–94.3 |
| GARAN | 12 | 6 | 6 | 0 | 85.0–99.7 |
| ASELS | 7 | 6 | 0 | 1 | 78.4–96.6 |
| TUPRS | 15 | 9 | 5 | 1 | 75.3–98.2 |
| BIMAS | 20 | 10 | 6 | 4 | 72.1–97.3 |
| EREGL | 9 | 8 | 1 | 0 | 86.0–96.7 |
| **Total** | **71** | **42** | **22** | **7** | **72.1–99.7** |

The type totals were 39 symmetrical, 19 ascending, and 13 descending triangles. No candidate was
still forming at the end of these cached histories.

## Review notes

- The detector correctly rejected the committed synthetic parallel and diverging channels.
- Consecutive four-pivot windows can describe overlapping structures that later share a breakout.
  This explains the higher match count and occasional nearby candidates on the same symbol.
- High geometry scores mean a candidate closely fits the explicit rules; they do not establish
  predictive accuracy or independent opportunities.
- The projected apex is now visible on the chart so unusually long convergence windows can be
  inspected instead of hidden in detector parameters.
- No default tolerances were changed from this small cache review. Triangle alerts remain disabled
  until representative matches and false positives are manually labeled and frozen as fixtures.
- A future deduplication pass should compare overlapping candidates without breaking stable IDs or
  erasing the audit history.

This is detector-quality review, not evidence of profitability or financial advice.
