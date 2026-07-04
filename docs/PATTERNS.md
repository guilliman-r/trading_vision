# Pattern definitions

Pattern scores describe geometric quality from 0–100. They are not probabilities of profit.
Every detector uses completed candles and confirmed pivots only.

## Shared pivot rule

A pivot high must be the unique highest high in its configured left/right window. A pivot low must
be the unique lowest low. If the right window is three candles, the pivot is not knowable until
those three later candles close. The model stores both the pivot candle and its confirmation candle.

Pivots must also pass configurable percentage and ATR prominence limits.

## Horizontal resistance breakout

```text
resistance  ─────●────────●──────── breakout close ▲
                 │        │
                 └─ price remains below the level ─┘
```

- At least two confirmed pivot highs touch one horizontal level.
- Touches must meet minimum spacing and tolerance rules.
- A completed close above the level plus a percent/ATR buffer confirms the pattern.
- A quick return below the buffered level invalidates it.
- The target projects the formation height above the level.

Support breakdowns use the mirrored rules.

## Double top

```text
              peak 1                     peak 2
                ●                           ●
               / \                         / \
              /   \                       /   \
neckline  ───────────────●────────────────────────────
                          trough                    \  confirmation ▼
```

Required pivot order: `high → low → high`.

- The peaks must be within the configured percent/ATR tolerance.
- Both legs and the full formation must meet duration limits.
- Peak-to-neckline depth must pass percentage and ATR minimums.
- The pattern becomes `forming` only after the second peak's right-side pivot window closes.
- A completed close below the neckline plus a buffer confirms it.
- A close above the higher peak plus a buffer invalidates it before confirmation.
- The measured target is `neckline - (average peak - neckline)`.
- The higher peak is the initial invalidation reference.

## Double bottom

```text
neckline  ───────────── reaction high ───────────────────────
              \            ●             /        confirmation ▲
               \          / \           /
                ●────────     ─────────●
              bottom 1                 bottom 2
```

Required pivot order: `low → high → low`.

- The bottoms must be within the configured percent/ATR tolerance.
- Bottom-to-neckline depth and timing use the same explicit limits as double tops.
- A completed close above the neckline plus a buffer confirms it.
- A close below the lower bottom plus a buffer invalidates it before confirmation.
- The measured target projects the formation depth above the neckline.

## States

- `forming`: valid geometry exists, but no buffered neckline/level close has occurred.
- `confirmed`: a completed candle closed through the buffered confirmation boundary.
- `invalidated`: price crossed the structural invalidation boundary.
- `expired`: confirmation did not occur within the configured candle window.

State transitions are stored separately from the current pattern row. Re-running the same scan does
not create a new transition or alert candidate.

