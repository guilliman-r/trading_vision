"""Choose the small set of actionable patterns shown on the chart."""

from __future__ import annotations

import pandas as pd

from trading_vision.models import PatternMatch

RECENT_CONFIRMATION_BARS = 40
MAX_VISIBLE_PATTERNS = 3


def select_visible_patterns(
    candles: pd.DataFrame,
    patterns: tuple[PatternMatch, ...],
) -> tuple[PatternMatch, ...]:
    """Return forming and recently confirmed patterns, strongest duplicate first."""

    if candles.empty:
        return ()
    completed = candles.loc[candles["is_complete"]] if "is_complete" in candles else candles
    if completed.empty:
        return ()
    cutoff_index = max(0, len(completed) - RECENT_CONFIRMATION_BARS)
    cutoff = pd.Timestamp(completed.iloc[cutoff_index]["opened_at_utc"])
    candidates = [
        pattern
        for pattern in patterns
        if pattern.state == "forming"
        or (
            pattern.state == "confirmed"
            and pattern.confirmed_at is not None
            and pd.Timestamp(pattern.confirmed_at) >= cutoff
        )
    ]
    candidates.sort(key=_display_rank)
    deduplicated: list[PatternMatch] = []
    seen: set[tuple] = set()
    for pattern in candidates:
        key = _display_key(pattern)
        if key in seen:
            continue
        seen.add(key)
        deduplicated.append(pattern)
        if len(deduplicated) == MAX_VISIBLE_PATTERNS:
            break
    return tuple(deduplicated)


def _display_rank(pattern: PatternMatch) -> tuple:
    state_priority = 0 if pattern.state == "forming" else 1
    newest_index = max(point.index for point in pattern.points)
    return state_priority, -newest_index, -pattern.score


def _display_key(pattern: PatternMatch) -> tuple:
    family = _pattern_family(pattern.pattern_type)
    if pattern.state == "forming":
        return family, pattern.direction, "forming"
    return family, pattern.direction, pattern.confirmed_at


def _pattern_family(pattern_type: str) -> str:
    if "triangle" in pattern_type:
        return "triangle"
    if "head_shoulders" in pattern_type:
        return "head_shoulders"
    if pattern_type.startswith("double_"):
        return "double"
    if pattern_type in {"resistance_breakout", "support_breakdown"}:
        return "horizontal"
    return pattern_type
