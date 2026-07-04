from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd

from trading_vision.patterns.double_patterns import (
    DoublePatternSettings,
    detect_double_patterns,
)
from trading_vision.patterns.pivots import PivotSettings
from trading_vision.patterns.scoring import stable_pattern_id


def double_settings() -> DoublePatternSettings:
    return DoublePatternSettings(
        pivot=PivotSettings(
            left_bars=2,
            right_bars=2,
            atr_period=3,
            minimum_prominence_atr=0.2,
            minimum_prominence_percent=0.2,
        ),
        endpoint_tolerance_percent=2.0,
        endpoint_tolerance_atr=0.75,
        minimum_depth_percent=1.0,
        minimum_depth_atr=0.5,
        minimum_leg_bars=3,
        minimum_pattern_bars=8,
        maximum_pattern_bars=80,
        expiry_bars=25,
        volume_period=10,
        lookback_bars=100,
    )


def double_top_fixture(
    length: int = 45,
    second_peak: float = 100.5,
    confirm: bool = True,
) -> pd.DataFrame:
    confirmation_price = 87.0 if confirm else 95.0
    positions = [0, 12, 20, 28, 34, length - 1]
    values = [82.0, 100.0, 90.0, second_peak, confirmation_price, confirmation_price - 1]
    closes = np.interp(range(length), positions, values)
    frame = pd.DataFrame(
        {
            "opened_at_utc": pd.date_range("2025-01-01", periods=length, freq="D", tz="UTC"),
            "open": closes - 0.15,
            "high": closes + 0.8,
            "low": closes - 0.8,
            "close": closes,
            "volume": [100.0] * length,
            "is_complete": [True] * length,
        }
    )
    if confirm:
        frame.loc[34, "volume"] = 450.0
    return frame


def path_fixture(length: int, positions: list[int], values: list[float]) -> pd.DataFrame:
    closes = np.interp(range(length), positions, values)
    return pd.DataFrame(
        {
            "opened_at_utc": pd.date_range("2025-01-01", periods=length, freq="D", tz="UTC"),
            "open": closes - 0.15,
            "high": closes + 0.8,
            "low": closes - 0.8,
            "close": closes,
            "volume": [100.0] * length,
            "is_complete": [True] * length,
        }
    )


def intended_match(frame: pd.DataFrame, pattern_type: str = "double_top"):
    matches = detect_double_patterns(frame, double_settings())
    return next(match for match in matches if match.pattern_type == pattern_type)


def test_double_top_confirms_on_first_buffered_neckline_close() -> None:
    frame = double_top_fixture()
    match = intended_match(frame)
    assert match.state == "confirmed"
    assert match.confirmed_at == frame.loc[34, "opened_at_utc"].to_pydatetime()
    assert match.boundary_price < 91
    assert match.target_price < match.boundary_price
    assert match.invalidation_price > 100
    assert match.score >= 70
    assert [point.label for point in match.points] == [
        "peak_1",
        "trough",
        "peak_2",
        "confirmation",
    ]


def test_candidate_is_forming_until_confirmation_candle_is_available() -> None:
    full = double_top_fixture()
    forming = intended_match(full.iloc[:34])
    confirmed = intended_match(full.iloc[:35])
    assert forming.state == "forming"
    assert forming.confirmed_at is None
    assert confirmed.state == "confirmed"
    assert confirmed.confirmed_at == full.loc[34, "opened_at_utc"].to_pydatetime()


def test_stable_id_does_not_change_when_candidate_confirms() -> None:
    frame = double_top_fixture()
    forming = intended_match(frame.iloc[:34])
    confirmed = intended_match(frame)
    assert stable_pattern_id("TEST", "1d", forming) == stable_pattern_id("TEST", "1d", confirmed)


def test_double_top_invalidates_before_neckline_break() -> None:
    frame = double_top_fixture(confirm=False)
    frame.loc[34, ["open", "high", "low", "close"]] = [103.0, 106.0, 102.0, 105.0]
    match = intended_match(frame)
    assert match.state == "invalidated"
    assert match.confirmed_at is None
    assert match.ended_at == frame.loc[34, "opened_at_utc"].to_pydatetime()


def test_unconfirmed_double_top_expires() -> None:
    frame = double_top_fixture(length=70, confirm=False)
    match = intended_match(frame)
    assert match.state == "expired"


def test_endpoint_outside_tolerance_is_rejected() -> None:
    frame = double_top_fixture(second_peak=108.0)
    matches = detect_double_patterns(frame, double_settings())
    assert not any(match.pattern_type == "double_top" for match in matches)


def test_too_shallow_structure_is_rejected() -> None:
    frame = path_fixture(
        length=45,
        positions=[0, 12, 20, 28, 34, 44],
        values=[96.0, 100.0, 99.0, 100.3, 97.0, 96.0],
    )
    settings = replace(double_settings(), minimum_depth_percent=3.0)
    matches = detect_double_patterns(frame, settings)
    assert not any(match.pattern_type == "double_top" for match in matches)


def test_structure_wider_than_maximum_duration_is_rejected() -> None:
    frame = path_fixture(
        length=80,
        positions=[0, 12, 40, 68, 74, 79],
        values=[82.0, 100.0, 90.0, 100.4, 87.0, 86.0],
    )
    settings = replace(double_settings(), maximum_pattern_bars=40)
    matches = detect_double_patterns(frame, settings)
    assert not any(match.pattern_type == "double_top" for match in matches)


def test_close_inside_breakout_buffer_does_not_confirm() -> None:
    frame = double_top_fixture(confirm=False)
    match_before = intended_match(frame.iloc[:34])
    neckline = match_before.boundary_price
    frame.loc[34, ["open", "high", "low", "close"]] = [
        neckline,
        neckline + 0.5,
        neckline - 0.5,
        neckline - 0.01,
    ]
    match = intended_match(frame.iloc[:35])
    assert match.state == "forming"


def test_double_bottom_uses_mirrored_rules() -> None:
    frame = double_top_fixture()
    original_open = frame["open"].copy()
    original_high = frame["high"].copy()
    original_low = frame["low"].copy()
    original_close = frame["close"].copy()
    frame["open"] = 200 - original_open
    frame["high"] = 200 - original_low
    frame["low"] = 200 - original_high
    frame["close"] = 200 - original_close
    match = intended_match(frame, "double_bottom")
    assert match.direction == "bullish"
    assert match.state == "confirmed"
    assert match.target_price > match.boundary_price
    assert [point.label for point in match.points[:3]] == [
        "bottom_1",
        "reaction_high",
        "bottom_2",
    ]


def test_detector_does_not_mutate_candle_input() -> None:
    frame = double_top_fixture()
    before = frame.copy(deep=True)
    detect_double_patterns(frame, double_settings())
    pd.testing.assert_frame_equal(frame, before)
