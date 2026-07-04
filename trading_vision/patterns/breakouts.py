"""Horizontal support and resistance breakout detection."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime

import pandas as pd

from trading_vision.models import PatternMatch, PatternPoint, Pivot
from trading_vision.patterns.indicators import (
    average_true_range,
    crossed_boundary,
    percent_distance,
    rolling_volume_ratio,
)
from trading_vision.patterns.pivots import PivotSettings, find_confirmed_pivots
from trading_vision.patterns.scoring import clamp_score

DETECTOR_VERSION = "horizontal-breakout-v1"


@dataclass(frozen=True, slots=True)
class BreakoutSettings:
    pivot: PivotSettings = field(default_factory=PivotSettings)
    minimum_touches: int = 2
    minimum_touch_spacing_bars: int = 4
    level_tolerance_atr: float = 0.35
    level_tolerance_percent: float = 1.0
    breakout_buffer_atr: float = 0.10
    breakout_buffer_percent: float = 0.10
    minimum_pattern_bars: int = 5
    maximum_pattern_bars: int = 160
    expiry_bars: int = 30
    invalidation_bars: int = 10
    volume_period: int = 20
    preferred_volume_ratio: float = 1.2
    lookback_bars: int = 300

    def validate(self) -> BreakoutSettings:
        self.pivot.validate()
        if self.minimum_touches < 2:
            raise ValueError("A level requires at least two touches")
        if self.minimum_touch_spacing_bars < 1:
            raise ValueError("Touch spacing must be positive")
        if self.minimum_pattern_bars < 1 or self.maximum_pattern_bars <= self.minimum_pattern_bars:
            raise ValueError("Pattern duration limits are invalid")
        if self.expiry_bars < 1 or self.invalidation_bars < 1:
            raise ValueError("State windows must be positive")
        if self.volume_period < 2 or self.lookback_bars < self.maximum_pattern_bars:
            raise ValueError("Volume period or lookback is too short")
        return self


def detect_horizontal_breakouts(
    candles: pd.DataFrame,
    settings: BreakoutSettings | None = None,
) -> list[PatternMatch]:
    """Detect forming and completed horizontal level breaks on closed candles."""

    settings = (settings or BreakoutSettings()).validate()
    frame = candles.copy()
    if "is_complete" in frame.columns:
        frame = frame.loc[frame["is_complete"]].copy()
    frame = frame.reset_index(drop=True)
    if len(frame) < settings.pivot.atr_period + settings.pivot.right_bars + 2:
        return []

    pivots = find_confirmed_pivots(frame, settings.pivot)
    oldest_index = max(0, len(frame) - settings.lookback_bars)
    pivots = [pivot for pivot in pivots if pivot.index >= oldest_index]
    atr = average_true_range(frame, settings.pivot.atr_period).ffill()
    volume_ratio = rolling_volume_ratio(frame["volume"], settings.volume_period)

    matches: list[PatternMatch] = []
    for kind in ("high", "low"):
        clusters = _cluster_pivots([pivot for pivot in pivots if pivot.kind == kind], settings)
        for cluster in clusters:
            match = _build_match(frame, atr, volume_ratio, cluster, settings)
            if match:
                matches.append(match)
    return sorted(matches, key=lambda match: (match.started_at, match.pattern_type))


def _cluster_pivots(pivots: list[Pivot], settings: BreakoutSettings) -> list[list[Pivot]]:
    clusters: list[list[Pivot]] = []
    for pivot in pivots:
        compatible: list[tuple[float, list[Pivot]]] = []
        for cluster in clusters:
            level = sum(item.price for item in cluster) / len(cluster)
            tolerance = max(
                level * settings.level_tolerance_percent / 100,
                pivot.atr * settings.level_tolerance_atr,
            )
            spacing = pivot.index - cluster[-1].index
            if (
                abs(pivot.price - level) <= tolerance
                and spacing >= settings.minimum_touch_spacing_bars
            ):
                compatible.append((abs(pivot.price - level), cluster))
        if compatible:
            min(compatible, key=lambda item: item[0])[1].append(pivot)
        else:
            clusters.append([pivot])
    return [cluster for cluster in clusters if len(cluster) >= settings.minimum_touches]


def _build_match(
    frame: pd.DataFrame,
    atr: pd.Series,
    volume_ratio: pd.Series,
    touches: list[Pivot],
    settings: BreakoutSettings,
) -> PatternMatch | None:
    span = touches[-1].index - touches[0].index
    if span < settings.minimum_pattern_bars or span > settings.maximum_pattern_bars:
        return None

    level = sum(touch.price for touch in touches) / len(touches)
    bullish = touches[0].kind == "high"
    direction = "above" if bullish else "below"
    scan_start = max(touch.confirmation_index for touch in touches) + 1
    confirmation_index = _find_confirmation(frame, atr, scan_start, level, direction, settings)
    state, ended_at = _state_after_confirmation(
        frame,
        atr,
        confirmation_index,
        scan_start,
        level,
        bullish,
        settings,
    )
    if confirmation_index is None and state not in {"forming", "expired"}:
        return None

    confirmation_time = (
        _time_at(frame, confirmation_index) if confirmation_index is not None else None
    )
    height = _pattern_height(frame, touches, level, bullish)
    target = level + height if bullish else max(0.0, level - height)
    tolerance = _level_tolerance(level, touches, settings)
    invalidation = level - tolerance if bullish else level + tolerance
    points = _pattern_points(touches, frame, confirmation_index)
    score, reasons = _score_match(
        frame,
        atr,
        volume_ratio,
        touches,
        level,
        confirmation_index,
        settings,
    )
    return PatternMatch(
        pattern_type="resistance_breakout" if bullish else "support_breakdown",
        direction="bullish" if bullish else "bearish",
        state=state,
        started_at=touches[0].occurred_at,
        ended_at=ended_at,
        confirmed_at=confirmation_time,
        score=score,
        boundary_price=level,
        target_price=target,
        invalidation_price=invalidation,
        points=points,
        reasons=reasons,
        parameters=asdict(settings),
        detector_version=DETECTOR_VERSION,
    )


def _find_confirmation(
    frame: pd.DataFrame,
    atr: pd.Series,
    start: int,
    level: float,
    direction: str,
    settings: BreakoutSettings,
) -> int | None:
    for index in range(start, len(frame)):
        buffer = _breakout_buffer(level, float(atr.iloc[index]), settings)
        if crossed_boundary(float(frame.loc[index, "close"]), level, buffer, direction):
            return index
    return None


def _state_after_confirmation(
    frame: pd.DataFrame,
    atr: pd.Series,
    confirmation_index: int | None,
    scan_start: int,
    level: float,
    bullish: bool,
    settings: BreakoutSettings,
) -> tuple[str, datetime | None]:
    if confirmation_index is None:
        age = len(frame) - scan_start
        if age > settings.expiry_bars:
            return "expired", _time_at(frame, len(frame) - 1)
        return "forming", None

    stop = min(len(frame), confirmation_index + settings.invalidation_bars + 1)
    for index in range(confirmation_index + 1, stop):
        buffer = _breakout_buffer(level, float(atr.iloc[index]), settings)
        close = float(frame.loc[index, "close"])
        returned_inside = close < level - buffer if bullish else close > level + buffer
        if returned_inside:
            return "invalidated", _time_at(frame, index)
    return "confirmed", None


def _pattern_height(
    frame: pd.DataFrame,
    touches: list[Pivot],
    level: float,
    bullish: bool,
) -> float:
    window = frame.loc[touches[0].index : touches[-1].index]
    if bullish:
        return max(0.0, level - float(window["low"].min()))
    return max(0.0, float(window["high"].max()) - level)


def _pattern_points(
    touches: list[Pivot],
    frame: pd.DataFrame,
    confirmation_index: int | None,
) -> tuple[PatternPoint, ...]:
    points = [
        PatternPoint(
            label=f"touch_{position}",
            index=touch.index,
            occurred_at=touch.occurred_at,
            price=touch.price,
        )
        for position, touch in enumerate(touches, start=1)
    ]
    if confirmation_index is not None:
        points.append(
            PatternPoint(
                label="confirmation",
                index=confirmation_index,
                occurred_at=_time_at(frame, confirmation_index),
                price=float(frame.loc[confirmation_index, "close"]),
            )
        )
    return tuple(points)


def _score_match(
    frame: pd.DataFrame,
    atr: pd.Series,
    volume_ratio: pd.Series,
    touches: list[Pivot],
    level: float,
    confirmation_index: int | None,
    settings: BreakoutSettings,
) -> tuple[float, tuple[str, ...]]:
    dispersion = sum(percent_distance(touch.price, level) for touch in touches) / len(touches)
    geometry = 35 * max(0.0, 1 - dispersion / settings.level_tolerance_percent)
    prominence = min(20.0, sum(touch.prominence_atr for touch in touches) / len(touches) * 10)
    duration = min(10.0, (touches[-1].index - touches[0].index) / 2)
    touch_quality = min(15.0, len(touches) * 5.0)
    breakout_strength = _breakout_score(frame, atr, confirmation_index, level, settings)
    volume = _volume_score(volume_ratio, confirmation_index, settings)
    values = [geometry, prominence, duration, touch_quality, breakout_strength, volume]
    reasons = (
        f"+{geometry:.0f} level dispersion is {dispersion:.2f}%",
        f"+{prominence:.0f} average pivot prominence is "
        f"{sum(touch.prominence_atr for touch in touches) / len(touches):.2f} ATR",
        f"+{duration:.0f} formation spans {touches[-1].index - touches[0].index} bars",
        f"+{touch_quality:.0f} level has {len(touches)} confirmed touches",
        _breakout_reason(breakout_strength, confirmation_index),
        _volume_reason(volume, volume_ratio, confirmation_index),
    )
    return clamp_score(sum(values)), reasons


def _breakout_score(
    frame: pd.DataFrame,
    atr: pd.Series,
    confirmation_index: int | None,
    level: float,
    settings: BreakoutSettings,
) -> float:
    if confirmation_index is None:
        return 0.0
    distance = abs(float(frame.loc[confirmation_index, "close"]) - level)
    buffer = _breakout_buffer(level, float(atr.iloc[confirmation_index]), settings)
    return min(10.0, 5.0 + distance / max(buffer, 1e-9))


def _volume_score(
    ratios: pd.Series,
    confirmation_index: int | None,
    settings: BreakoutSettings,
) -> float:
    if confirmation_index is None or pd.isna(ratios.iloc[confirmation_index]):
        return 0.0
    ratio = float(ratios.iloc[confirmation_index])
    return min(10.0, ratio / settings.preferred_volume_ratio * 10)


def _breakout_reason(points: float, confirmation_index: int | None) -> str:
    if confirmation_index is None:
        return "+0 breakout is not confirmed yet"
    return f"+{points:.0f} close cleared the buffered level"


def _volume_reason(
    points: float,
    ratios: pd.Series,
    confirmation_index: int | None,
) -> str:
    if confirmation_index is None or pd.isna(ratios.iloc[confirmation_index]):
        return "+0 confirmation volume has no usable baseline"
    return f"+{points:.0f} confirmation volume is {ratios.iloc[confirmation_index]:.2f}× median"


def _breakout_buffer(level: float, atr: float, settings: BreakoutSettings) -> float:
    return max(
        level * settings.breakout_buffer_percent / 100,
        atr * settings.breakout_buffer_atr,
    )


def _level_tolerance(
    level: float,
    touches: list[Pivot],
    settings: BreakoutSettings,
) -> float:
    average_atr = sum(touch.atr for touch in touches) / len(touches)
    return max(
        level * settings.level_tolerance_percent / 100,
        average_atr * settings.level_tolerance_atr,
    )


def _time_at(frame: pd.DataFrame, index: int) -> datetime:
    return pd.Timestamp(frame.loc[index, "opened_at_utc"]).to_pydatetime()
