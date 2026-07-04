# Double-pattern BIST review

Review date: 2026-07-04  
Source: locally cached adjusted Yahoo Finance daily candles  
Window: 500 candles per symbol  
Detector: `double-pattern-v1` with committed defaults

## Summary

| Symbol | Matches | Confirmed | Invalidated | Score range |
|---|---:|---:|---:|---:|
| THYAO | 3 | 2 | 1 | 50.1–77.0 |
| GARAN | 6 | 3 | 3 | 38.7–79.4 |
| ASELS | 6 | 4 | 2 | 47.5–82.6 |
| TUPRS | 3 | 1 | 2 | 47.5–85.8 |
| BIMAS | 7 | 2 | 5 | 41.6–84.5 |
| EREGL | 4 | 2 | 2 | 60.1–74.9 |
| **Total** | **29** | **14** | **15** | **38.7–85.8** |

## Review notes

- High-score confirmed examples exist in both directions; TUPRS produced an 85.8 double bottom
  and BIMAS an 84.5 double top.
- Ten results scored below 60. All are retained for auditability, but the UI ranks higher-quality
  confirmed/forming results first.
- Alternating pivot triples can create adjacent double-top and double-bottom labels from the same
  extended swing sequence. This is geometrically valid but can be visually noisy.
- Invalidated results are useful for detector review but should eventually have a chart visibility
  toggle and scanner filter.
- No default tolerance was loosened after this review. Future tuning should use labeled examples,
  not a desire to produce more matches.

This review records detector behavior, not investment performance or trading recommendations.

