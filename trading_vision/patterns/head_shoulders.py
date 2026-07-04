"""Standard and inverse head-and-shoulders detection."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime

import pandas as pd

from trading_vision.models import PatternMatch, Pivot
from trading_vision.patterns.head_shoulders_output import (
    build_head_shoulders_points,
    score_head_shoulders,
)
from trading_vision.patterns.head_shoulders_settings import HeadShouldersSettings
from trading_vision.patterns.indicators import (
    average_true_range,
    fit_line,
    line_value,
    rolling_volume_ratio,
)
from trading_vision.patterns.pivots import find_confirmed_pivots

DETECTOR_VERSION = "head-shoulders-v1"


def detect_head_shoulders_patterns(
    candles: pd.DataFrame,
    settings: HeadShouldersSettings | None = None,
) -> list[PatternMatch]:
    """Return standard and inverse matches visible in completed candles."""

    settings = (settings or HeadShouldersSettings()).validate()
    frame = candles.copy()
    if "is_complete" in frame.columns:
        frame = frame.loc[frame["is_complete"]].copy()
    frame = frame.reset_index(drop=True)
    if len(frame) < settings.pivot.atr_period + settings.pivot.right_bars + 5:
        return []

    atr = average_true_range(frame, settings.pivot.atr_period).ffill()
    volume_ratio = rolling_volume_ratio(frame["volume"], settings.volume_period)
    oldest_index = max(0, len(frame) - settings.lookback_bars)
    pivots = [
        pivot
        for pivot in find_confirmed_pivots(frame, settings.pivot, keep_same_kind=True)
        if pivot.index >= oldest_index
    ]
    standard = detect_standard_patterns(frame, pivots, atr, volume_ratio, settings)
    inverse = detect_inverse_patterns(frame, pivots, atr, volume_ratio, settings)
    return sorted([*standard, *inverse], key=lambda match: (match.started_at, match.pattern_type))


def detect_standard_patterns(
    frame: pd.DataFrame,
    pivots: list[Pivot],
    atr: pd.Series,
    volume_ratio: pd.Series,
    settings: HeadShouldersSettings,
) -> list[PatternMatch]:
    """Find high → low → higher high → low → high formations."""

    matches: list[PatternMatch] = []
    for group in _pivot_groups(pivots):
        if tuple(pivot.kind for pivot in group) != ("high", "low", "high", "low", "high"):
            continue
        geometry = _geometry(group, settings, inverse=False)
        if geometry is None:
            continue
        matches.append(_build_match(frame, atr, volume_ratio, group, geometry, settings, False))
    return matches


def detect_inverse_patterns(
    frame: pd.DataFrame,
    pivots: list[Pivot],
    atr: pd.Series,
    volume_ratio: pd.Series,
    settings: HeadShouldersSettings,
) -> list[PatternMatch]:
    """Find low → high → lower low → high → low formations."""

    matches: list[PatternMatch] = []
    for group in _pivot_groups(pivots):
        if tuple(pivot.kind for pivot in group) != ("low", "high", "low", "high", "low"):
            continue
        geometry = _geometry(group, settings, inverse=True)
        if geometry is None:
            continue
        matches.append(_build_match(frame, atr, volume_ratio, group, geometry, settings, True))
    return matches


def _pivot_groups(pivots: list[Pivot]):
    return zip(pivots, pivots[1:], pivots[2:], pivots[3:], pivots[4:], strict=False)


def _geometry(
    pivots: tuple[Pivot, Pivot, Pivot, Pivot, Pivot],
    settings: HeadShouldersSettings,
    inverse: bool,
) -> tuple[float, float, float] | None:
    first, first_reaction, head, second_reaction, second = pivots
    gaps = [pivots[index + 1].index - pivots[index].index for index in range(4)]
    duration = second.index - first.index
    if any(gap < settings.minimum_leg_bars for gap in gaps):
        return None
    if duration < settings.minimum_pattern_bars or duration > settings.maximum_pattern_bars:
        return None

    shoulder_level = (first.price + second.price) / 2
    shoulder_tolerance = max(
        shoulder_level * settings.shoulder_tolerance_percent / 100,
        (first.atr + second.atr) / 2 * settings.shoulder_tolerance_atr,
    )
    if abs(first.price - second.price) > shoulder_tolerance:
        return None
    minimum_head_height = max(
        shoulder_level * settings.minimum_head_height_percent / 100,
        (first.atr + head.atr + second.atr) / 3 * settings.minimum_head_height_atr,
    )
    head_height = (
        min(first.price, second.price) - head.price
        if inverse
        else head.price - max(first.price, second.price)
    )
    if head_height < minimum_head_height:
        return None

    left_span = head.index - first.index
    right_span = second.index - head.index
    time_imbalance = abs(left_span - right_span) / max(left_span, right_span)
    if time_imbalance > settings.maximum_time_imbalance:
        return None
    slope, intercept = fit_line(
        [first_reaction.index, second_reaction.index],
        [first_reaction.price, second_reaction.price],
    )
    average_neckline = (first_reaction.price + second_reaction.price) / 2
    slope_percent = abs(slope / average_neckline * 100)
    if slope_percent > settings.maximum_neckline_slope_percent_per_bar:
        return None
    return slope, intercept, slope_percent


def _build_match(
    frame: pd.DataFrame,
    atr: pd.Series,
    volume_ratio: pd.Series,
    pivots: tuple[Pivot, Pivot, Pivot, Pivot, Pivot],
    geometry: tuple[float, float, float],
    settings: HeadShouldersSettings,
    inverse: bool,
) -> PatternMatch:
    slope, intercept, slope_percent = geometry
    first, _reaction_one, head, _reaction_two, second = pivots
    scan_start = second.confirmation_index + 1
    confirmation_index, invalidation_index = _find_initial_outcome(
        frame, atr, scan_start, slope, intercept, head.price, settings, inverse
    )
    state, ended_at = _resolve_state(
        frame,
        atr,
        scan_start,
        confirmation_index,
        invalidation_index,
        head.price,
        settings,
        inverse,
    )
    if confirmation_index is not None:
        evaluation_index = confirmation_index
    elif invalidation_index is not None:
        evaluation_index = invalidation_index
    else:
        evaluation_index = len(frame) - 1
    boundary = line_value(slope, intercept, evaluation_index)
    head_height = abs(head.price - line_value(slope, intercept, head.index))
    target = boundary + head_height if inverse else boundary - head_height
    score, reasons = score_head_shoulders(
        frame, atr, volume_ratio, pivots, confirmation_index, slope_percent, settings
    )
    return PatternMatch(
        pattern_type="inverse_head_shoulders" if inverse else "head_shoulders",
        direction="bullish" if inverse else "bearish",
        state=state,
        started_at=first.occurred_at,
        ended_at=ended_at,
        confirmed_at=_time_at(frame, confirmation_index)
        if confirmation_index is not None
        else None,
        score=score,
        boundary_price=boundary,
        target_price=max(0.0, target),
        invalidation_price=head.price,
        points=build_head_shoulders_points(frame, pivots, confirmation_index, inverse),
        reasons=reasons,
        parameters={**asdict(settings), "neckline_slope": slope, "neckline_intercept": intercept},
        detector_version=DETECTOR_VERSION,
    )


def _find_initial_outcome(
    frame: pd.DataFrame,
    atr: pd.Series,
    start: int,
    slope: float,
    intercept: float,
    head_price: float,
    settings: HeadShouldersSettings,
    inverse: bool,
) -> tuple[int | None, int | None]:
    for index in range(start, len(frame)):
        close = float(frame.loc[index, "close"])
        neckline = line_value(slope, intercept, index)
        neckline_buffer = _buffer(neckline, float(atr.iloc[index]), settings)
        head_buffer = _buffer(head_price, float(atr.iloc[index]), settings)
        confirmed = (
            close > neckline + neckline_buffer if inverse else close < neckline - neckline_buffer
        )
        invalidated = (
            close < head_price - head_buffer if inverse else close > head_price + head_buffer
        )
        if confirmed:
            return index, None
        if invalidated:
            return None, index
    return None, None


def _resolve_state(
    frame: pd.DataFrame,
    atr: pd.Series,
    scan_start: int,
    confirmation_index: int | None,
    invalidation_index: int | None,
    head_price: float,
    settings: HeadShouldersSettings,
    inverse: bool,
) -> tuple[str, datetime | None]:
    if invalidation_index is not None:
        return "invalidated", _time_at(frame, invalidation_index)
    if confirmation_index is None:
        if len(frame) - scan_start > settings.expiry_bars:
            return "expired", _time_at(frame, len(frame) - 1)
        return "forming", None
    stop = min(len(frame), confirmation_index + settings.invalidation_bars + 1)
    for index in range(confirmation_index + 1, stop):
        buffer = _buffer(head_price, float(atr.iloc[index]), settings)
        close = float(frame.loc[index, "close"])
        invalidated = close < head_price - buffer if inverse else close > head_price + buffer
        if invalidated:
            return "invalidated", _time_at(frame, index)
    return "confirmed", None


def _buffer(level: float, atr: float, settings: HeadShouldersSettings) -> float:
    return max(
        level * settings.breakout_buffer_percent / 100,
        atr * settings.breakout_buffer_atr,
    )


def _time_at(frame: pd.DataFrame, index: int) -> datetime:
    return pd.Timestamp(frame.loc[index, "opened_at_utc"]).to_pydatetime()
