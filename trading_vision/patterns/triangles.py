"""Ascending, descending, and symmetrical triangle detection."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime

import pandas as pd

from trading_vision.models import PatternMatch, Pivot
from trading_vision.patterns.indicators import (
    average_true_range,
    fit_line,
    line_value,
    rolling_volume_ratio,
)
from trading_vision.patterns.pivots import find_confirmed_pivots
from trading_vision.patterns.triangle_output import build_triangle_points, score_triangle
from trading_vision.patterns.triangle_settings import TriangleSettings

DETECTOR_VERSION = "triangle-v1"


@dataclass(frozen=True, slots=True)
class TriangleGeometry:
    pattern_type: str
    upper_slope: float
    upper_intercept: float
    lower_slope: float
    lower_intercept: float
    upper_slope_percent: float
    lower_slope_percent: float
    apex_index: float
    convergence_percent: float


def detect_triangles(
    candles: pd.DataFrame,
    settings: TriangleSettings | None = None,
) -> list[PatternMatch]:
    """Return four-touch triangle formations visible in completed candles."""

    settings = (settings or TriangleSettings()).validate()
    frame = candles.copy()
    if "is_complete" in frame.columns:
        frame = frame.loc[frame["is_complete"]].copy()
    frame = frame.reset_index(drop=True)
    if len(frame) < settings.pivot.atr_period + settings.pivot.right_bars + 4:
        return []

    atr = average_true_range(frame, settings.pivot.atr_period).ffill()
    volume_ratio = rolling_volume_ratio(frame["volume"], settings.volume_period)
    oldest_index = max(0, len(frame) - settings.lookback_bars)
    pivots = [
        pivot
        for pivot in find_confirmed_pivots(frame, settings.pivot)
        if pivot.index >= oldest_index
    ]
    matches: list[PatternMatch] = []
    for group in _pivot_groups(pivots):
        upper = [pivot for pivot in group if pivot.kind == "high"]
        lower = [pivot for pivot in group if pivot.kind == "low"]
        if len(upper) < settings.minimum_touches_per_side:
            continue
        if len(lower) < settings.minimum_touches_per_side:
            continue
        geometry = _classify_geometry(upper, lower, settings)
        if geometry is None:
            continue
        matches.append(_build_match(frame, atr, volume_ratio, upper, lower, geometry, settings))
    return sorted(matches, key=lambda match: (match.started_at, match.pattern_type))


def _pivot_groups(pivots: list[Pivot]):
    return zip(pivots, pivots[1:], pivots[2:], pivots[3:], strict=False)


def _classify_geometry(
    upper: list[Pivot],
    lower: list[Pivot],
    settings: TriangleSettings,
) -> TriangleGeometry | None:
    all_pivots = sorted([*upper, *lower], key=lambda pivot: pivot.index)
    start_index = all_pivots[0].index
    end_index = all_pivots[-1].index
    duration = end_index - start_index
    if duration < settings.minimum_pattern_bars or duration > settings.maximum_pattern_bars:
        return None

    upper_slope, upper_intercept = fit_line(
        [pivot.index for pivot in upper], [pivot.price for pivot in upper]
    )
    lower_slope, lower_intercept = fit_line(
        [pivot.index for pivot in lower], [pivot.price for pivot in lower]
    )
    upper_average = sum(pivot.price for pivot in upper) / len(upper)
    lower_average = sum(pivot.price for pivot in lower) / len(lower)
    upper_percent = upper_slope / upper_average * 100
    lower_percent = lower_slope / lower_average * 100
    initial_gap = line_value(upper_slope, upper_intercept, start_index) - line_value(
        lower_slope, lower_intercept, start_index
    )
    final_gap = line_value(upper_slope, upper_intercept, end_index) - line_value(
        lower_slope, lower_intercept, end_index
    )
    if initial_gap <= 0 or final_gap <= 0 or final_gap >= initial_gap:
        return None
    convergence = (initial_gap - final_gap) / initial_gap * 100
    if convergence < settings.minimum_convergence_percent:
        return None
    slope_difference = upper_slope - lower_slope
    if slope_difference == 0:
        return None
    apex = (lower_intercept - upper_intercept) / slope_difference
    apex_distance = apex - end_index
    if apex_distance < settings.minimum_apex_distance_bars:
        return None
    if apex_distance > settings.maximum_apex_distance_bars:
        return None

    pattern_type = _triangle_type(upper_percent, lower_percent, settings)
    if pattern_type is None:
        return None
    return TriangleGeometry(
        pattern_type=pattern_type,
        upper_slope=upper_slope,
        upper_intercept=upper_intercept,
        lower_slope=lower_slope,
        lower_intercept=lower_intercept,
        upper_slope_percent=upper_percent,
        lower_slope_percent=lower_percent,
        apex_index=apex,
        convergence_percent=convergence,
    )


def _triangle_type(
    upper_slope_percent: float,
    lower_slope_percent: float,
    settings: TriangleSettings,
) -> str | None:
    upper_flat = abs(upper_slope_percent) <= settings.flat_slope_percent_per_bar
    lower_flat = abs(lower_slope_percent) <= settings.flat_slope_percent_per_bar
    upper_falling = upper_slope_percent <= -settings.minimum_trend_slope_percent_per_bar
    lower_rising = lower_slope_percent >= settings.minimum_trend_slope_percent_per_bar
    if upper_flat and lower_rising:
        return "ascending_triangle"
    if upper_falling and lower_flat:
        return "descending_triangle"
    if upper_falling and lower_rising:
        return "symmetrical_triangle"
    return None


def _build_match(
    frame: pd.DataFrame,
    atr: pd.Series,
    volume_ratio: pd.Series,
    upper: list[Pivot],
    lower: list[Pivot],
    geometry: TriangleGeometry,
    settings: TriangleSettings,
) -> PatternMatch:
    all_pivots = sorted([*upper, *lower], key=lambda pivot: pivot.index)
    scan_start = max(pivot.confirmation_index for pivot in all_pivots) + 1
    confirmation_index, direction = _find_breakout(frame, atr, scan_start, geometry, settings)
    state, ended_at = _resolve_state(
        frame, atr, scan_start, confirmation_index, direction, geometry, settings
    )
    evaluation_index = (
        confirmation_index
        if confirmation_index is not None
        else min(len(frame) - 1, int(geometry.apex_index))
    )
    upper_boundary = line_value(geometry.upper_slope, geometry.upper_intercept, evaluation_index)
    lower_boundary = line_value(geometry.lower_slope, geometry.lower_intercept, evaluation_index)
    boundary = lower_boundary if direction == "bearish" else upper_boundary
    start_index = all_pivots[0].index
    height = line_value(geometry.upper_slope, geometry.upper_intercept, start_index) - line_value(
        geometry.lower_slope, geometry.lower_intercept, start_index
    )
    target = None
    invalidation = None
    if direction == "bullish":
        target = boundary + height
        invalidation = lower_boundary
    elif direction == "bearish":
        target = max(0.0, boundary - height)
        invalidation = upper_boundary
    score, reasons = score_triangle(
        frame,
        atr,
        volume_ratio,
        upper,
        lower,
        geometry.upper_slope_percent,
        geometry.lower_slope_percent,
        geometry.convergence_percent,
        confirmation_index,
        settings,
    )
    return PatternMatch(
        pattern_type=geometry.pattern_type,
        direction=direction or _expected_direction(geometry.pattern_type),
        state=state,
        started_at=all_pivots[0].occurred_at,
        ended_at=ended_at,
        confirmed_at=_time_at(frame, confirmation_index)
        if confirmation_index is not None
        else None,
        score=score,
        boundary_price=boundary,
        target_price=target,
        invalidation_price=invalidation,
        points=build_triangle_points(
            frame,
            upper,
            lower,
            geometry.apex_index,
            line_value(geometry.upper_slope, geometry.upper_intercept, geometry.apex_index),
            confirmation_index,
        ),
        reasons=reasons,
        parameters={
            **asdict(settings),
            "upper_slope": geometry.upper_slope,
            "upper_intercept": geometry.upper_intercept,
            "lower_slope": geometry.lower_slope,
            "lower_intercept": geometry.lower_intercept,
            "apex_index": geometry.apex_index,
        },
        detector_version=DETECTOR_VERSION,
    )


def _find_breakout(
    frame: pd.DataFrame,
    atr: pd.Series,
    start: int,
    geometry: TriangleGeometry,
    settings: TriangleSettings,
) -> tuple[int | None, str | None]:
    stop = min(len(frame), int(geometry.apex_index) + 1)
    for index in range(start, stop):
        close = float(frame.loc[index, "close"])
        upper = line_value(geometry.upper_slope, geometry.upper_intercept, index)
        lower = line_value(geometry.lower_slope, geometry.lower_intercept, index)
        buffer = _buffer((upper + lower) / 2, float(atr.iloc[index]), settings)
        if close > upper + buffer:
            return index, "bullish"
        if close < lower - buffer:
            return index, "bearish"
    return None, None


def _resolve_state(
    frame: pd.DataFrame,
    atr: pd.Series,
    scan_start: int,
    confirmation_index: int | None,
    direction: str | None,
    geometry: TriangleGeometry,
    settings: TriangleSettings,
) -> tuple[str, datetime | None]:
    if confirmation_index is None:
        passed_apex = len(frame) - 1 >= geometry.apex_index
        if passed_apex or len(frame) - scan_start > settings.expiry_bars:
            return "expired", _time_at(frame, len(frame) - 1)
        return "forming", None
    stop = min(len(frame), confirmation_index + settings.invalidation_bars + 1)
    for index in range(confirmation_index + 1, stop):
        close = float(frame.loc[index, "close"])
        upper = line_value(geometry.upper_slope, geometry.upper_intercept, index)
        lower = line_value(geometry.lower_slope, geometry.lower_intercept, index)
        buffer = _buffer((upper + lower) / 2, float(atr.iloc[index]), settings)
        returned_inside = (
            close < upper - buffer if direction == "bullish" else close > lower + buffer
        )
        if returned_inside:
            return "invalidated", _time_at(frame, index)
    return "confirmed", None


def _expected_direction(pattern_type: str) -> str:
    if pattern_type == "ascending_triangle":
        return "bullish"
    if pattern_type == "descending_triangle":
        return "bearish"
    return "neutral"


def _buffer(level: float, atr: float, settings: TriangleSettings) -> float:
    return max(
        level * settings.breakout_buffer_percent / 100,
        atr * settings.breakout_buffer_atr,
    )


def _time_at(frame: pd.DataFrame, index: int) -> datetime:
    return pd.Timestamp(frame.loc[index, "opened_at_utc"]).to_pydatetime()
