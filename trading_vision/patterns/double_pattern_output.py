"""Score and describe double-pattern matches for storage and display."""

from __future__ import annotations

import pandas as pd

from trading_vision.models import PatternPoint, Pivot
from trading_vision.patterns.double_pattern_settings import DoublePatternSettings
from trading_vision.patterns.indicators import percent_distance
from trading_vision.patterns.scoring import clamp_score


def score_double_pattern(
    frame: pd.DataFrame,
    atr: pd.Series,
    volume_ratio: pd.Series,
    first: Pivot,
    neckline: Pivot,
    second: Pivot,
    confirmation_index: int | None,
    settings: DoublePatternSettings,
) -> tuple[float, tuple[str, ...]]:
    endpoint_gap = percent_distance(first.price, second.price)
    price_symmetry = 25 * max(0.0, 1 - endpoint_gap / settings.endpoint_tolerance_percent)
    first_leg = neckline.index - first.index
    second_leg = second.index - neckline.index
    time_imbalance = abs(first_leg - second_leg) / max(first_leg, second_leg)
    time_symmetry = 10 * (1 - time_imbalance)
    prominence = min(20.0, (first.prominence_atr + second.prominence_atr) / 2 * 10)
    duration = min(10.0, (second.index - first.index) / 2)
    depth_atr = abs((first.price + second.price) / 2 - neckline.price) / max(
        (first.atr + neckline.atr + second.atr) / 3,
        1e-9,
    )
    depth_score = min(15.0, depth_atr * 5)
    breakout_score = _breakout_score(frame, atr, confirmation_index, neckline.price, settings)
    volume_score = _volume_score(volume_ratio, confirmation_index, settings)
    reasons = (
        f"+{price_symmetry:.0f} endpoints are {endpoint_gap:.2f}% apart",
        f"+{time_symmetry:.0f} leg lengths are {first_leg} and {second_leg} bars",
        f"+{prominence:.0f} endpoints average "
        f"{(first.prominence_atr + second.prominence_atr) / 2:.2f} ATR prominence",
        f"+{duration:.0f} formation spans {second.index - first.index} bars",
        f"+{depth_score:.0f} neckline depth is {depth_atr:.2f} ATR",
        _confirmation_reason(breakout_score, confirmation_index),
        _volume_reason(volume_score, volume_ratio, confirmation_index),
    )
    total = sum(
        (
            price_symmetry,
            time_symmetry,
            prominence,
            duration,
            depth_score,
            breakout_score,
            volume_score,
        )
    )
    return clamp_score(total), reasons


def build_pattern_points(
    frame: pd.DataFrame,
    first: Pivot,
    neckline: Pivot,
    second: Pivot,
    confirmation_index: int | None,
    is_top: bool,
) -> tuple[PatternPoint, ...]:
    endpoint = "peak" if is_top else "bottom"
    middle = "trough" if is_top else "reaction_high"
    points = [
        PatternPoint(f"{endpoint}_1", first.index, first.occurred_at, first.price),
        PatternPoint(middle, neckline.index, neckline.occurred_at, neckline.price),
        PatternPoint(f"{endpoint}_2", second.index, second.occurred_at, second.price),
    ]
    if confirmation_index is not None:
        points.append(
            PatternPoint(
                "confirmation",
                confirmation_index,
                pd.Timestamp(frame.loc[confirmation_index, "opened_at_utc"]).to_pydatetime(),
                float(frame.loc[confirmation_index, "close"]),
            )
        )
    return tuple(points)


def _breakout_score(
    frame: pd.DataFrame,
    atr: pd.Series,
    confirmation_index: int | None,
    neckline: float,
    settings: DoublePatternSettings,
) -> float:
    if confirmation_index is None:
        return 0.0
    distance = abs(float(frame.loc[confirmation_index, "close"]) - neckline)
    buffer = _buffer(neckline, float(atr.iloc[confirmation_index]), settings)
    return min(10.0, 5.0 + distance / max(buffer, 1e-9))


def _volume_score(
    ratios: pd.Series,
    confirmation_index: int | None,
    settings: DoublePatternSettings,
) -> float:
    if confirmation_index is None or pd.isna(ratios.iloc[confirmation_index]):
        return 0.0
    return min(
        10.0,
        float(ratios.iloc[confirmation_index]) / settings.preferred_volume_ratio * 10,
    )


def _confirmation_reason(points: float, confirmation_index: int | None) -> str:
    if confirmation_index is None:
        return "+0 neckline is not confirmed yet"
    return f"+{points:.0f} close cleared the buffered neckline"


def _volume_reason(points: float, ratios: pd.Series, confirmation_index: int | None) -> str:
    if confirmation_index is None or pd.isna(ratios.iloc[confirmation_index]):
        return "+0 confirmation volume has no usable baseline"
    return f"+{points:.0f} confirmation volume is {ratios.iloc[confirmation_index]:.2f}× median"


def _buffer(level: float, atr: float, settings: DoublePatternSettings) -> float:
    return max(
        level * settings.breakout_buffer_percent / 100,
        atr * settings.breakout_buffer_atr,
    )
