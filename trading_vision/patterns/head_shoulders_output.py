"""Build explainable output for head-and-shoulders detectors."""

from __future__ import annotations

import pandas as pd

from trading_vision.models import PatternPoint, Pivot
from trading_vision.patterns.head_shoulders_settings import HeadShouldersSettings
from trading_vision.patterns.indicators import percent_distance
from trading_vision.patterns.scoring import clamp_score


def score_head_shoulders(
    frame: pd.DataFrame,
    atr: pd.Series,
    volume_ratio: pd.Series,
    pivots: tuple[Pivot, Pivot, Pivot, Pivot, Pivot],
    confirmation_index: int | None,
    neckline_slope_percent: float,
    settings: HeadShouldersSettings,
) -> tuple[float, tuple[str, ...]]:
    left_shoulder, _first_reaction, head, _second_reaction, right_shoulder = pivots
    shoulder_gap = percent_distance(left_shoulder.price, right_shoulder.price)
    shoulder_score = 20 * max(0.0, 1 - shoulder_gap / settings.shoulder_tolerance_percent)
    left_span = head.index - left_shoulder.index
    right_span = right_shoulder.index - head.index
    time_imbalance = abs(left_span - right_span) / max(left_span, right_span)
    time_score = 15 * (1 - time_imbalance)
    head_height_atr = abs(head.price - (left_shoulder.price + right_shoulder.price) / 2) / max(
        (left_shoulder.atr + head.atr + right_shoulder.atr) / 3,
        1e-9,
    )
    head_score = min(20.0, head_height_atr * 7)
    slope_score = 10 * max(
        0.0,
        1 - neckline_slope_percent / settings.maximum_neckline_slope_percent_per_bar,
    )
    duration_score = min(10.0, (right_shoulder.index - left_shoulder.index) / 3)
    breakout_score = _breakout_score(frame, atr, confirmation_index, settings)
    volume_score = _volume_score(volume_ratio, confirmation_index, settings)
    reasons = (
        f"+{shoulder_score:.0f} shoulders are {shoulder_gap:.2f}% apart",
        f"+{time_score:.0f} shoulder spans are {left_span} and {right_span} bars",
        f"+{head_score:.0f} head prominence is {head_height_atr:.2f} ATR",
        f"+{slope_score:.0f} neckline slope is {neckline_slope_percent:.3f}% per bar",
        f"+{duration_score:.0f} formation spans {right_shoulder.index - left_shoulder.index} bars",
        _confirmation_reason(breakout_score, confirmation_index),
        _volume_reason(volume_score, volume_ratio, confirmation_index),
    )
    total = sum(
        (
            shoulder_score,
            time_score,
            head_score,
            slope_score,
            duration_score,
            breakout_score,
            volume_score,
        )
    )
    return clamp_score(total), reasons


def build_head_shoulders_points(
    frame: pd.DataFrame,
    pivots: tuple[Pivot, Pivot, Pivot, Pivot, Pivot],
    confirmation_index: int | None,
    inverse: bool,
) -> tuple[PatternPoint, ...]:
    first, first_reaction, head, second_reaction, second = pivots
    shoulder = "inverse_shoulder" if inverse else "shoulder"
    reaction = "neckline_high" if inverse else "neckline_low"
    points = [
        PatternPoint(f"left_{shoulder}", first.index, first.occurred_at, first.price),
        PatternPoint(
            f"{reaction}_1", first_reaction.index, first_reaction.occurred_at, first_reaction.price
        ),
        PatternPoint(
            "inverse_head" if inverse else "head", head.index, head.occurred_at, head.price
        ),
        PatternPoint(
            f"{reaction}_2",
            second_reaction.index,
            second_reaction.occurred_at,
            second_reaction.price,
        ),
        PatternPoint(f"right_{shoulder}", second.index, second.occurred_at, second.price),
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
    settings: HeadShouldersSettings,
) -> float:
    if confirmation_index is None:
        return 0.0
    candle_range = float(
        frame.loc[confirmation_index, "high"] - frame.loc[confirmation_index, "low"]
    )
    return min(15.0, 8.0 + candle_range / max(float(atr.iloc[confirmation_index]), 1e-9) * 3)


def _volume_score(
    ratios: pd.Series,
    confirmation_index: int | None,
    settings: HeadShouldersSettings,
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
    return f"+{points:.0f} completed candle cleared the sloped neckline"


def _volume_reason(points: float, ratios: pd.Series, confirmation_index: int | None) -> str:
    if confirmation_index is None or pd.isna(ratios.iloc[confirmation_index]):
        return "+0 confirmation volume has no usable baseline"
    return f"+{points:.0f} confirmation volume is {ratios.iloc[confirmation_index]:.2f}× median"
