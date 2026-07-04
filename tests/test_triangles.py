from __future__ import annotations

import numpy as np
import pandas as pd

from trading_vision.patterns.pivots import PivotSettings
from trading_vision.patterns.scoring import stable_pattern_id
from trading_vision.patterns.triangle_settings import TriangleSettings
from trading_vision.patterns.triangles import detect_triangles


def triangle_settings() -> TriangleSettings:
    return TriangleSettings(
        pivot=PivotSettings(
            left_bars=2,
            right_bars=2,
            atr_period=3,
            minimum_prominence_atr=0.2,
            minimum_prominence_percent=0.2,
        ),
        minimum_pattern_bars=8,
        maximum_pattern_bars=80,
        flat_slope_percent_per_bar=0.08,
        minimum_trend_slope_percent_per_bar=0.03,
        minimum_convergence_percent=10,
        minimum_apex_distance_bars=2,
        maximum_apex_distance_bars=100,
        expiry_bars=30,
        volume_period=10,
        lookback_bars=120,
    )


def ascending_triangle_fixture(length: int = 50, confirm: bool = True) -> pd.DataFrame:
    positions = [0, 10, 18, 26, 34]
    values = [95.0, 100.0, 90.0, 100.4, 94.0]
    if confirm:
        positions.extend([41, 42, length - 1])
        values.extend([100.0, 103.0, 104.0])
    else:
        positions.append(length - 1)
        values.append(98.0)
    closes = np.interp(range(length), positions, values)
    frame = _frame_from_closes(closes)
    if confirm:
        frame.loc[42, "volume"] = 450.0
    return frame


def symmetrical_triangle_fixture() -> pd.DataFrame:
    positions = [0, 10, 18, 26, 34, 37, 38, 44]
    values = [94.0, 100.0, 88.0, 96.0, 92.0, 93.0, 97.0, 98.0]
    frame = _frame_from_closes(np.interp(range(45), positions, values))
    frame.loc[38, "volume"] = 450.0
    return frame


def _frame_from_closes(closes) -> pd.DataFrame:
    length = len(closes)
    return pd.DataFrame(
        {
            "opened_at_utc": pd.date_range("2025-01-01", periods=length, freq="D", tz="UTC"),
            "open": closes - 0.1,
            "high": closes + 0.6,
            "low": closes - 0.6,
            "close": closes,
            "volume": [100.0] * length,
            "is_complete": [True] * length,
        }
    )


def intended_match(frame: pd.DataFrame, pattern_type: str):
    matches = detect_triangles(frame, triangle_settings())
    return next(match for match in matches if match.pattern_type == pattern_type)


def test_ascending_triangle_confirms_upward_breakout() -> None:
    frame = ascending_triangle_fixture()
    match = intended_match(frame, "ascending_triangle")
    assert match.state == "confirmed"
    assert match.direction == "bullish"
    assert match.confirmed_at == frame.loc[42, "opened_at_utc"].to_pydatetime()
    assert match.target_price > match.boundary_price
    assert match.invalidation_price < match.boundary_price
    assert match.score >= 70
    assert [point.label for point in match.points[:4]] == [
        "upper_touch_1",
        "lower_touch_1",
        "upper_touch_2",
        "lower_touch_2",
    ]
    assert match.points[4].label == "apex"
    assert match.points[4].index > match.points[3].index


def test_triangle_is_forming_before_breakout_candle() -> None:
    frame = ascending_triangle_fixture()
    forming = intended_match(frame.iloc[:42], "ascending_triangle")
    confirmed = intended_match(frame.iloc[:43], "ascending_triangle")
    assert forming.state == "forming"
    assert confirmed.state == "confirmed"


def test_triangle_id_is_stable_across_confirmation() -> None:
    frame = ascending_triangle_fixture()
    forming = intended_match(frame.iloc[:42], "ascending_triangle")
    confirmed = intended_match(frame, "ascending_triangle")
    assert stable_pattern_id("TEST", "1d", forming) == stable_pattern_id("TEST", "1d", confirmed)


def test_incomplete_breakout_candle_is_ignored() -> None:
    frame = ascending_triangle_fixture()
    frame.loc[42:, "is_complete"] = False
    match = intended_match(frame, "ascending_triangle")
    assert match.state == "forming"


def test_confirmed_triangle_invalidates_on_return_inside() -> None:
    frame = ascending_triangle_fixture()
    frame.loc[45, ["open", "high", "low", "close"]] = [98, 99, 96, 97]
    match = intended_match(frame, "ascending_triangle")
    assert match.state == "invalidated"
    assert match.confirmed_at == frame.loc[42, "opened_at_utc"].to_pydatetime()
    assert match.ended_at == frame.loc[45, "opened_at_utc"].to_pydatetime()


def test_descending_triangle_uses_mirrored_boundaries() -> None:
    frame = ascending_triangle_fixture()
    original_open = frame["open"].copy()
    original_high = frame["high"].copy()
    original_low = frame["low"].copy()
    original_close = frame["close"].copy()
    frame["open"] = 200 - original_open
    frame["high"] = 200 - original_low
    frame["low"] = 200 - original_high
    frame["close"] = 200 - original_close
    match = intended_match(frame, "descending_triangle")
    assert match.direction == "bearish"
    assert match.state == "confirmed"
    assert match.target_price < match.boundary_price


def test_symmetrical_triangle_classification() -> None:
    match = intended_match(symmetrical_triangle_fixture(), "symmetrical_triangle")
    assert match.state == "confirmed"
    assert match.direction == "bullish"


def test_parallel_channel_is_rejected() -> None:
    positions = [0, 10, 18, 26, 34, 44]
    values = [95, 100, 90, 104, 94, 98]
    frame = _frame_from_closes(np.interp(range(45), positions, values))
    assert detect_triangles(frame, triangle_settings()) == []


def test_diverging_lines_are_rejected() -> None:
    positions = [0, 10, 18, 26, 34, 44]
    values = [95, 100, 90, 104, 86, 95]
    frame = _frame_from_closes(np.interp(range(45), positions, values))
    assert detect_triangles(frame, triangle_settings()) == []


def test_passed_apex_shape_expires_without_breakout() -> None:
    frame = ascending_triangle_fixture(length=75, confirm=False)

    def upper(index: int) -> float:
        return 100.35 + 0.025 * index

    def lower(index: int) -> float:
        return 84.9 + 0.25 * index

    for index in range(35, 75):
        midpoint = (upper(index) + lower(index)) / 2
        frame.loc[index, ["open", "high", "low", "close"]] = [
            midpoint - 0.1,
            midpoint + 0.6,
            midpoint - 0.6,
            midpoint,
        ]
    match = intended_match(frame, "ascending_triangle")
    assert match.state == "expired"


def test_detector_does_not_mutate_input() -> None:
    frame = ascending_triangle_fixture()
    before = frame.copy(deep=True)
    detect_triangles(frame, triangle_settings())
    pd.testing.assert_frame_equal(frame, before)
