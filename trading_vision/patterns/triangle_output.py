"""Build explainable triangle scores and structural points."""

from __future__ import annotations

import pandas as pd

from trading_vision.models import PatternPoint, Pivot
from trading_vision.patterns.scoring import clamp_score
from trading_vision.patterns.triangle_settings import TriangleSettings


def score_triangle(
    frame: pd.DataFrame,
    atr: pd.Series,
    volume_ratio: pd.Series,
    upper_pivots: list[Pivot],
    lower_pivots: list[Pivot],
    upper_slope_percent: float,
    lower_slope_percent: float,
    convergence_percent: float,
    confirmation_index: int | None,
    settings: TriangleSettings,
) -> tuple[float, tuple[str, ...]]:
    convergence_score = min(25.0, convergence_percent / settings.minimum_convergence_percent * 12.5)
    slope_strength = abs(upper_slope_percent) + abs(lower_slope_percent)
    slope_score = min(20.0, slope_strength / settings.minimum_trend_slope_percent_per_bar * 5)
    all_pivots = sorted([*upper_pivots, *lower_pivots], key=lambda pivot: pivot.index)
    duration = all_pivots[-1].index - all_pivots[0].index
    duration_score = min(10.0, duration / 2)
    touch_score = min(15.0, (len(upper_pivots) + len(lower_pivots)) * 3.75)
    prominence = sum(pivot.prominence_atr for pivot in all_pivots) / len(all_pivots)
    prominence_score = min(10.0, prominence * 5)
    breakout_score = _breakout_score(frame, atr, confirmation_index)
    volume_score = _volume_score(volume_ratio, confirmation_index, settings)
    reasons = (
        f"+{convergence_score:.0f} boundaries converge {convergence_percent:.1f}%",
        f"+{slope_score:.0f} upper/lower slopes are "
        f"{upper_slope_percent:.3f}% and {lower_slope_percent:.3f}% per bar",
        f"+{duration_score:.0f} formation spans {duration} bars",
        f"+{touch_score:.0f} formation has {len(upper_pivots)} upper and "
        f"{len(lower_pivots)} lower touches",
        f"+{prominence_score:.0f} pivots average {prominence:.2f} ATR prominence",
        _confirmation_reason(breakout_score, confirmation_index),
        _volume_reason(volume_score, volume_ratio, confirmation_index),
    )
    total = sum(
        (
            convergence_score,
            slope_score,
            duration_score,
            touch_score,
            prominence_score,
            breakout_score,
            volume_score,
        )
    )
    return clamp_score(total), reasons


def build_triangle_points(
    frame: pd.DataFrame,
    upper_pivots: list[Pivot],
    lower_pivots: list[Pivot],
    apex_index: float,
    apex_price: float,
    confirmation_index: int | None,
) -> tuple[PatternPoint, ...]:
    points = [
        PatternPoint(f"upper_touch_{position}", pivot.index, pivot.occurred_at, pivot.price)
        for position, pivot in enumerate(upper_pivots, start=1)
    ]
    points.extend(
        PatternPoint(f"lower_touch_{position}", pivot.index, pivot.occurred_at, pivot.price)
        for position, pivot in enumerate(lower_pivots, start=1)
    )
    points.sort(key=lambda point: point.index)
    points.append(
        PatternPoint(
            "apex",
            round(apex_index),
            _time_for_index(frame, round(apex_index)),
            apex_price,
        )
    )
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


def _time_for_index(frame: pd.DataFrame, index: int):
    if index < len(frame):
        return pd.Timestamp(frame.loc[index, "opened_at_utc"]).to_pydatetime()
    times = pd.to_datetime(frame["opened_at_utc"], utc=True)
    recent_steps = times.diff().dropna().tail(20)
    step = recent_steps.median()
    projected = times.iloc[-1] + step * (index - len(frame) + 1)
    return projected.to_pydatetime()


def _breakout_score(
    frame: pd.DataFrame,
    atr: pd.Series,
    confirmation_index: int | None,
) -> float:
    if confirmation_index is None:
        return 0.0
    candle_range = float(
        frame.loc[confirmation_index, "high"] - frame.loc[confirmation_index, "low"]
    )
    return min(10.0, 5.0 + candle_range / max(float(atr.iloc[confirmation_index]), 1e-9) * 2)


def _volume_score(
    ratios: pd.Series,
    confirmation_index: int | None,
    settings: TriangleSettings,
) -> float:
    if confirmation_index is None or pd.isna(ratios.iloc[confirmation_index]):
        return 0.0
    return min(
        10.0,
        float(ratios.iloc[confirmation_index]) / settings.preferred_volume_ratio * 10,
    )


def _confirmation_reason(points: float, confirmation_index: int | None) -> str:
    if confirmation_index is None:
        return "+0 neither boundary is confirmed broken"
    return f"+{points:.0f} completed candle cleared a buffered boundary"


def _volume_reason(points: float, ratios: pd.Series, confirmation_index: int | None) -> str:
    if confirmation_index is None or pd.isna(ratios.iloc[confirmation_index]):
        return "+0 confirmation volume has no usable baseline"
    return f"+{points:.0f} confirmation volume is {ratios.iloc[confirmation_index]:.2f}× median"
