from __future__ import annotations

import pandas as pd

from trading_vision.models import PatternMatch, PatternPoint
from trading_vision.ui.overlay_selection import (
    MAX_VISIBLE_PATTERNS,
    select_visible_patterns,
)


def _candles(count: int = 100) -> pd.DataFrame:
    times = pd.date_range("2025-01-01", periods=count, freq="D", tz="UTC")
    return pd.DataFrame(
        {
            "opened_at_utc": times,
            "is_complete": [True] * count,
        }
    )


def _pattern(
    candles: pd.DataFrame,
    pattern_type: str,
    state: str,
    point_index: int,
    *,
    direction: str = "bullish",
    score: float = 75,
) -> PatternMatch:
    time = candles.iloc[point_index]["opened_at_utc"].to_pydatetime()
    confirmed_at = time if state in {"confirmed", "invalidated", "expired"} else None
    return PatternMatch(
        pattern_type=pattern_type,
        direction=direction,
        state=state,
        started_at=time,
        ended_at=time if state in {"invalidated", "expired"} else None,
        confirmed_at=confirmed_at,
        score=score,
        boundary_price=100,
        target_price=110,
        invalidation_price=95,
        points=(PatternPoint("confirmation", point_index, time, 102),),
        reasons=("test pattern",),
        parameters={},
        detector_version="test-v1",
    )


def test_selects_forming_and_recently_confirmed_patterns_only() -> None:
    candles = _candles()
    forming = _pattern(candles, "support_breakdown", "forming", 30)
    recent = _pattern(candles, "double_bottom", "confirmed", 80)
    old = _pattern(candles, "double_top", "confirmed", 40)
    invalidated = _pattern(candles, "ascending_triangle", "invalidated", 90)
    expired = _pattern(candles, "head_shoulders", "expired", 95)

    selected = select_visible_patterns(
        candles,
        (old, invalidated, recent, expired, forming),
    )

    assert selected == (forming, recent)


def test_forming_patterns_are_ranked_before_confirmed_patterns() -> None:
    candles = _candles()
    recent = _pattern(candles, "double_bottom", "confirmed", 99, score=99)
    forming = _pattern(candles, "support_breakdown", "forming", 20, score=60)

    selected = select_visible_patterns(candles, (recent, forming))

    assert selected == (forming, recent)


def test_overlapping_detector_results_are_deduplicated_by_family() -> None:
    candles = _candles()
    lower_score = _pattern(candles, "ascending_triangle", "forming", 90, score=60)
    higher_score = _pattern(candles, "symmetrical_triangle", "forming", 90, score=90)

    selected = select_visible_patterns(candles, (lower_score, higher_score))

    assert selected == (higher_score,)


def test_visible_overlays_are_limited_to_a_small_actionable_set() -> None:
    candles = _candles()
    patterns = tuple(
        _pattern(candles, f"custom_{index}", "forming", 90 + index, score=50 + index)
        for index in range(5)
    )

    selected = select_visible_patterns(candles, patterns)

    assert len(selected) == MAX_VISIBLE_PATTERNS
    assert [pattern.pattern_type for pattern in selected] == [
        "custom_4",
        "custom_3",
        "custom_2",
    ]
