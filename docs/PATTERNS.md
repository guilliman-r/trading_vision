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

## Head and shoulders

```text
                               head
                                ●
                              /   \
             left shoulder  ●     ●  right shoulder
                           /  \   /  \
neckline  ───────────────●─────\─●────────────────── breakdown ▼
```

Required pivot order: `high → low → higher high → low → high`.

- Left and right shoulders must meet explicit percentage and ATR similarity limits.
- The head must exceed both shoulders by configurable percentage and ATR minimums.
- Shoulder-to-head timing may differ, but only within the configured imbalance limit.
- The neckline is a fitted line through both reaction lows; it is not assumed horizontal.
- Neckline slope is measured as percentage per candle and rejected above the configured limit.
- The pattern becomes knowable only after the right shoulder's pivot confirmation window closes.
- A completed close below the fitted neckline plus a buffer confirms it.
- A close above the head plus a buffer invalidates it.
- The target projects head-to-neckline height below the neckline at confirmation.

## Inverse head and shoulders

```text
neckline  ───────────────●─────/─●────────────────── breakout ▲
                           \  /   \  /
             left shoulder  ●     ●  right shoulder
                              \   /
                                ●
                          inverse head
```

Required pivot order: `low → high → lower low → high → low`. Shoulder, timing, slope, and
prominence checks mirror the standard form. Confirmation requires a completed close above the
fitted neckline, and the target projects the formation height upward.

## Triangles

```text
ascending             descending            symmetrical

upper  ●────●         upper  ●              upper  ●
       /    /                \\ ●                  \\   ●
lower ●───●           lower ●────●           lower ●──●
             × apex               × apex              × apex
```

All three classes use exactly four consecutive, alternating confirmed pivots as their first
candidate: two upper touches and two lower touches. A separate straight line is fitted to each
side. The committed defaults require:

- 8–120 candles between the first and fourth touch;
- at least two touches on each side;
- a flat side no steeper than 0.08% of price per candle;
- a trending side at least 0.03% of price per candle;
- at least 10% narrowing between the first and fourth touch;
- an intersection 2–120 candles beyond the fourth touch.

Ascending triangles combine approximately flat resistance with rising support. Descending
triangles combine falling resistance with approximately flat support. Symmetrical triangles
require both falling resistance and rising support. Parallel, widening, insufficient-touch, and
already-past-apex structures are rejected.

A completed close beyond either fitted boundary plus the larger of the percentage and ATR buffers
confirms direction. A return decisively inside during the configured invalidation window marks the
match invalidated. If price does not break before the apex or expiry window, it expires. The target
projects the triangle's starting height from the confirmation boundary; it is an estimate, not a
forecast. The chart shows both boundaries, touch sequence, projected apex, confirmation, target,
and invalidation.

## States

- `forming`: valid geometry exists, but no buffered neckline, level, or boundary close has occurred.
- `confirmed`: a completed candle closed through the buffered confirmation boundary.
- `invalidated`: price crossed the structural invalidation boundary.
- `expired`: confirmation did not occur within the configured candle window.

State transitions are stored separately from the current pattern row. Re-running the same scan does
not create a new transition or alert candidate.
