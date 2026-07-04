"""Explainable double-top and double-bottom detectors."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime

import pandas as pd

from trading_vision.models import PatternMatch, Pivot
from trading_vision.patterns.double_pattern_output import (
    build_pattern_points,
    score_double_pattern,
)
from trading_vision.patterns.double_pattern_settings import DoublePatternSettings
from trading_vision.patterns.indicators import (
    average_true_range,
    rolling_volume_ratio,
)
from trading_vision.patterns.pivots import find_confirmed_pivots

DETECTOR_VERSION = "double-pattern-v1"


def detect_double_patterns(
    candles: pd.DataFrame,
    settings: DoublePatternSettings | None = None,
) -> list[PatternMatch]:
    """Return double tops and bottoms visible in completed candles."""

    settings = (settings or DoublePatternSettings()).validate()
    frame = candles.copy()
    if "is_complete" in frame.columns:
        frame = frame.loc[frame["is_complete"]].copy()
    frame = frame.reset_index(drop=True)
    if len(frame) < settings.pivot.atr_period + settings.pivot.right_bars + 3:
        return []

    atr = average_true_range(frame, settings.pivot.atr_period).ffill()
    volume_ratio = rolling_volume_ratio(frame["volume"], settings.volume_period)
    oldest_index = max(0, len(frame) - settings.lookback_bars)
    pivots = [
        pivot
        for pivot in find_confirmed_pivots(frame, settings.pivot, keep_same_kind=True)
        if pivot.index >= oldest_index
    ]
    tops = detect_double_tops(frame, pivots, atr, volume_ratio, settings)
    bottoms = detect_double_bottoms(frame, pivots, atr, volume_ratio, settings)
    return sorted([*tops, *bottoms], key=lambda match: (match.started_at, match.pattern_type))


def detect_double_tops(
    frame: pd.DataFrame,
    pivots: list[Pivot],
    atr: pd.Series,
    volume_ratio: pd.Series,
    settings: DoublePatternSettings,
) -> list[PatternMatch]:
    """Find high → low → high structures and bearish neckline breaks."""

    matches: list[PatternMatch] = []
    for first, neckline, second in _pivot_triples(pivots):
        if (first.kind, neckline.kind, second.kind) != ("high", "low", "high"):
            continue
        if not _geometry_is_valid(first, neckline, second, settings, is_top=True):
            continue
        matches.append(
            _build_match(frame, atr, volume_ratio, first, neckline, second, settings, is_top=True)
        )
    return matches


def detect_double_bottoms(
    frame: pd.DataFrame,
    pivots: list[Pivot],
    atr: pd.Series,
    volume_ratio: pd.Series,
    settings: DoublePatternSettings,
) -> list[PatternMatch]:
    """Find low → high → low structures and bullish neckline breaks."""

    matches: list[PatternMatch] = []
    for first, neckline, second in _pivot_triples(pivots):
        if (first.kind, neckline.kind, second.kind) != ("low", "high", "low"):
            continue
        if not _geometry_is_valid(first, neckline, second, settings, is_top=False):
            continue
        matches.append(
            _build_match(
                frame,
                atr,
                volume_ratio,
                first,
                neckline,
                second,
                settings,
                is_top=False,
            )
        )
    return matches


def _pivot_triples(pivots: list[Pivot]):
    return zip(pivots, pivots[1:], pivots[2:], strict=False)


def _geometry_is_valid(
    first: Pivot,
    neckline: Pivot,
    second: Pivot,
    settings: DoublePatternSettings,
    is_top: bool,
) -> bool:
    first_leg = neckline.index - first.index
    second_leg = second.index - neckline.index
    duration = second.index - first.index
    if first_leg < settings.minimum_leg_bars or second_leg < settings.minimum_leg_bars:
        return False
    if duration < settings.minimum_pattern_bars or duration > settings.maximum_pattern_bars:
        return False

    endpoint_level = (first.price + second.price) / 2
    endpoint_tolerance = max(
        endpoint_level * settings.endpoint_tolerance_percent / 100,
        (first.atr + second.atr) / 2 * settings.endpoint_tolerance_atr,
    )
    if abs(first.price - second.price) > endpoint_tolerance:
        return False

    depth = endpoint_level - neckline.price if is_top else neckline.price - endpoint_level
    minimum_depth = max(
        endpoint_level * settings.minimum_depth_percent / 100,
        (first.atr + neckline.atr + second.atr) / 3 * settings.minimum_depth_atr,
    )
    return depth >= minimum_depth


def _build_match(
    frame: pd.DataFrame,
    atr: pd.Series,
    volume_ratio: pd.Series,
    first: Pivot,
    neckline: Pivot,
    second: Pivot,
    settings: DoublePatternSettings,
    is_top: bool,
) -> PatternMatch:
    scan_start = second.confirmation_index + 1
    confirmation_index, invalidation_index = _find_initial_outcome(
        frame,
        atr,
        scan_start,
        first,
        neckline,
        second,
        settings,
        is_top,
    )
    state, ended_at = _resolve_state(
        frame,
        atr,
        scan_start,
        confirmation_index,
        invalidation_index,
        first,
        second,
        settings,
        is_top,
    )
    endpoint_level = (first.price + second.price) / 2
    depth = abs(endpoint_level - neckline.price)
    target = neckline.price - depth if is_top else neckline.price + depth
    invalidation = max(first.price, second.price) if is_top else min(first.price, second.price)
    score, reasons = score_double_pattern(
        frame,
        atr,
        volume_ratio,
        first,
        neckline,
        second,
        confirmation_index,
        settings,
    )
    return PatternMatch(
        pattern_type="double_top" if is_top else "double_bottom",
        direction="bearish" if is_top else "bullish",
        state=state,
        started_at=first.occurred_at,
        ended_at=ended_at,
        confirmed_at=_time_at(frame, confirmation_index)
        if confirmation_index is not None
        else None,
        score=score,
        boundary_price=neckline.price,
        target_price=max(0.0, target),
        invalidation_price=invalidation,
        points=build_pattern_points(frame, first, neckline, second, confirmation_index, is_top),
        reasons=reasons,
        parameters=asdict(settings),
        detector_version=DETECTOR_VERSION,
    )


def _find_initial_outcome(
    frame: pd.DataFrame,
    atr: pd.Series,
    start: int,
    first: Pivot,
    neckline: Pivot,
    second: Pivot,
    settings: DoublePatternSettings,
    is_top: bool,
) -> tuple[int | None, int | None]:
    invalidation_level = (
        max(first.price, second.price) if is_top else min(first.price, second.price)
    )
    for index in range(start, len(frame)):
        close = float(frame.loc[index, "close"])
        neck_buffer = _buffer(neckline.price, float(atr.iloc[index]), settings)
        invalidation_buffer = _buffer(invalidation_level, float(atr.iloc[index]), settings)
        confirmed = (
            close < neckline.price - neck_buffer if is_top else close > neckline.price + neck_buffer
        )
        invalidated = (
            close > invalidation_level + invalidation_buffer
            if is_top
            else close < invalidation_level - invalidation_buffer
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
    first: Pivot,
    second: Pivot,
    settings: DoublePatternSettings,
    is_top: bool,
) -> tuple[str, datetime | None]:
    if invalidation_index is not None:
        return "invalidated", _time_at(frame, invalidation_index)
    if confirmation_index is None:
        if len(frame) - scan_start > settings.expiry_bars:
            return "expired", _time_at(frame, len(frame) - 1)
        return "forming", None

    invalidation_level = (
        max(first.price, second.price) if is_top else min(first.price, second.price)
    )
    stop = min(len(frame), confirmation_index + settings.invalidation_bars + 1)
    for index in range(confirmation_index + 1, stop):
        buffer = _buffer(invalidation_level, float(atr.iloc[index]), settings)
        close = float(frame.loc[index, "close"])
        invalidated = (
            close > invalidation_level + buffer if is_top else close < invalidation_level - buffer
        )
        if invalidated:
            return "invalidated", _time_at(frame, index)
    return "confirmed", None


def _buffer(level: float, atr: float, settings: DoublePatternSettings) -> float:
    return max(
        level * settings.breakout_buffer_percent / 100,
        atr * settings.breakout_buffer_atr,
    )


def _time_at(frame: pd.DataFrame, index: int) -> datetime:
    return pd.Timestamp(frame.loc[index, "opened_at_utc"]).to_pydatetime()
